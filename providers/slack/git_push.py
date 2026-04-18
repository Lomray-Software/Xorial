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

    If the push is rejected because the remote moved ahead (someone else
    pushed between our last pull and now), we attempt a single
    `git pull --rebase` + retry — planning artifacts rarely conflict, so
    this covers the common case without surfacing a scary stderr dump.

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

    # Non-fast-forward / fetch-first → pull --rebase and retry once.
    if "rejected" in err.lower() or "fetch first" in err.lower() or "non-fast-forward" in err.lower():
        rb_rc, _, rb_err = await _run(
            "git", "-C", cwd, "pull", "--rebase", "origin", branch,
        )
        if rb_rc != 0:
            return (
                f":warning: push rejected and auto-rebase failed — resolve manually in `{cwd}`. "
                f"Commit is local, not pushed. ({rb_err.strip()[:120]})"
            )
        rc2, err2 = await _push(cwd, branch)
        if rc2 == 0:
            return f":arrow_up: pushed to `{branch}` (rebased on remote first)"
        return (
            f":warning: push still rejected after rebase — push manually from `{cwd}`. "
            f"({err2[:120]})"
        )

    return f":x: push failed: {err[:200]}"
