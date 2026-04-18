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


async def commit_and_push(project: Project, role: str, feature: str, speaker: str) -> str:
    """git add .xorial + current scope, commit with attribution, push.

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
    msg = f"xorial({role}): {feature} — by {speaker}"

    await _run("git", "-C", cwd, "add", ".xorial")
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
