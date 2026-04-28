import asyncio

from .config import Project


async def _run(*argv: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def _push(cwd: str, branch: str) -> tuple[int, str]:
    rc, _, err = await _run("git", "-C", cwd, "push", "origin", branch)
    return rc, err.strip()


async def pull_rebase(project: Project) -> str | None:
    """Fast-forward local to origin before a role runs, so the agent reads
    and edits the CURRENT repo state — not stale files that predate a
    teammate's merge.

    Returns None on success. Returns an error string on failure (dirty
    tree, rebase conflict, network error) — caller should surface it to
    the thread and skip the pass rather than letting the agent write on a
    stale base.

    Respects `project.auto_push`: if the user opted out of auto-push, we
    also stay out of their git state on the pull side.
    """
    if not project.auto_push:
        return None

    cwd = project.project_root
    branch = project.git_branch

    rc, _, _ = await _run("git", "-C", cwd, "diff", "--quiet")
    rc_cached, _, _ = await _run("git", "-C", cwd, "diff", "--cached", "--quiet")
    if rc != 0 or rc_cached != 0:
        return (
            "working tree has uncommitted changes — pre-pull skipped. "
            "Commit or stash them before re-running."
        )

    rc, _, err = await _run(
        "git", "-C", cwd, "pull", "--rebase", "origin", branch,
    )
    if rc == 0:
        return None

    # Rebase failed mid-way. Abort to leave a clean tree — local commits
    # (if any) return to their original base, remote is untouched.
    await _run("git", "-C", cwd, "rebase", "--abort")
    return (
        f"pre-pull `git pull --rebase origin {branch}` failed — remote moved "
        f"and local couldn't rebase cleanly. Resolve manually, then re-run. "
        f"({err.strip()[:160]})"
    )


async def commit_and_push(
    project: Project,
    role: str,
    feature: str,
    speaker: str,
    scope_paths: list[str],
) -> str:
    """git add <scope_paths> + current scope, commit with attribution, push.

    `scope_paths` is the explicit allow-list of paths to stage,
    relative to the project root. Caller MUST scope this to what the
    role actually owns (typically `.xorial/context/work/<type>/<name>`
    plus shared standards/knowledge dirs for role passes; the view
    files for view-sync). Scoping is what makes concurrent passes safe:
    if we did a blanket `git add .xorial` here, it would sweep up a
    sibling pass's in-progress writes into this commit.

    SAFETY INVARIANTS (read before editing this function):
      - We NEVER use `--force`, `--force-with-lease`, or any other flag
        that can overwrite remote refs. Every push is a plain
        `git push origin <branch>`. If the remote has moved, the push
        is rejected by the server and remote history is untouched —
        there is no code path here that can drop a teammate's commits
        from origin.
      - On a non-fast-forward rejection we try ONE `git pull --rebase`.
        Rebase only rewrites LOCAL history: it fetches the remote tip,
        rewinds our local branch to it, then replays ONLY the single
        xorial commit we just made. Remote commits are preserved and
        appear below our replayed commit in the final history.
      - If the rebase hits a conflict, we abort it (`git rebase --abort`)
        so the working tree is clean. Our local commit is preserved on
        its original base; the remote still has only its own commits.
        Nothing is pushed until a human resolves the conflict.
      - Worst case: our planning artifacts stay local and the thread
        gets a :warning: asking for manual resolution. Remote never
        loses data.

    Non-fatal on failure — we return a short status line for the thread
    but do not raise, so the pass result is preserved.
    """
    if not project.auto_push:
        return "auto_push=false — skipped git push"

    cwd = project.project_root
    branch = project.git_branch
    # Project-level roles (e.g. view-sync) pass feature="" — drop the empty
    # slot so the commit message reads `xorial(view-sync) — by X` instead of
    # `xorial(view-sync):  — by X`.
    msg = (
        f"xorial({role}): {feature} — by {speaker}"
        if feature
        else f"xorial({role}) — by {speaker}"
    )

    # `git add -A -- <path>` handles three shapes of input cleanly:
    #   - path exists on disk    → stages additions/modifications
    #   - path was tracked, gone → stages the deletion (delete flow)
    #   - path neither tracked nor on disk → "pathspec did not match",
    #     which we silently skip (e.g. view-sync's first run before
    #     `kanban.md` has been created, or a role pass that listed
    #     `knowledge/` in scope but did not actually touch it).
    for p in scope_paths:
        rc, _, a_err = await _run("git", "-C", cwd, "add", "-A", "--", p)
        if rc == 0:
            continue
        if "did not match" in a_err:
            continue
        return f":x: git add {p} failed: {a_err.strip()[:160]}"
    rc, _, _ = await _run("git", "-C", cwd, "diff", "--cached", "--quiet")
    if rc == 0:
        return "no changes to commit"

    rc, _, c_err = await _run("git", "-C", cwd, "commit", "-m", msg)
    if rc != 0:
        return f":x: commit failed: {c_err.strip()[:200]}"

    rc, err = await _push(cwd, branch)
    if rc == 0:
        return f":arrow_up: pushed to `{branch}`"

    low = err.lower()
    is_non_ff = "rejected" in low or "fetch first" in low or "non-fast-forward" in low
    if not is_non_ff:
        return f":x: push failed: {err[:200]}"

    # Remote moved ahead. Rebase our one local commit on top and retry.
    # Non-destructive for remote: rebase touches only local history.
    rb_rc, _, rb_err = await _run(
        "git", "-C", cwd, "pull", "--rebase", "origin", branch,
    )
    if rb_rc != 0:
        # Rebase hit a conflict (or some other failure). Abort to leave
        # the tree in a clean state — our commit remains on its original
        # base and nothing is pushed. Remote is untouched.
        await _run("git", "-C", cwd, "rebase", "--abort")
        return (
            f":warning: push rejected and auto-rebase hit a conflict — aborted. "
            f"Your xorial commit is safe locally in `{cwd}`; remote is unchanged. "
            f"Resolve manually with `git pull --rebase && git push`. "
            f"({rb_err.strip()[:120]})"
        )

    rc2, err2 = await _push(cwd, branch)
    if rc2 == 0:
        return f":arrow_up: pushed to `{branch}` (rebased on remote first)"
    # Second reject usually means a third party pushed during our rebase
    # window. Still a plain push, still no data loss on either side.
    return (
        f":warning: rebase succeeded but second push was rejected too — "
        f"someone pushed during the retry. Commit is local in `{cwd}`; "
        f"remote is unchanged. Push manually. ({err2[:120]})"
    )
