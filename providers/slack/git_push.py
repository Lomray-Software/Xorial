import asyncio
from .config import Project


async def commit_and_push(project: Project, role: str, feature: str, speaker: str) -> str:
    """git add .xorial + current scope, commit with attribution, push.
    Returns a short status line. Non-fatal on failure — we report it to the
    thread but do not raise, so the pass result is preserved."""
    if not project.auto_push:
        return "auto_push=false — skipped git push"

    msg = f"xorial({role}): {feature} — by {speaker}"
    cwd = project.project_root
    cmds = [
        ["git", "-C", cwd, "add", ".xorial"],
        ["git", "-C", cwd, "diff", "--cached", "--quiet"],  # exit 1 means there ARE changes
    ]

    # Stage .xorial. Then see if there's anything to commit.
    add_proc = await asyncio.create_subprocess_exec(*cmds[0])
    await add_proc.wait()

    diff_proc = await asyncio.create_subprocess_exec(*cmds[1])
    rc = await diff_proc.wait()
    if rc == 0:
        return "no changes to commit"

    commit = await asyncio.create_subprocess_exec(
        "git", "-C", cwd, "commit", "-m", msg,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, c_err = await commit.communicate()
    if commit.returncode != 0:
        return f"commit failed: {c_err.decode(errors='replace').strip()[:200]}"

    push = await asyncio.create_subprocess_exec(
        "git", "-C", cwd, "push", "origin", project.git_branch,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, p_err = await push.communicate()
    if push.returncode != 0:
        return f"push failed: {p_err.decode(errors='replace').strip()[:200]}"

    return f"pushed to {project.git_branch}"
