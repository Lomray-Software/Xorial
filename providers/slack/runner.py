"""Shared role-pass driver.

Both `/xorial <role>` (slash command) and a thread reply (event handler)
converge here. Responsibilities:
  - manage per-feature lock
  - stream role output into a Slack thread
  - persist session_id for resume
  - auto-commit + push planning artifacts
"""

import logging

from slack_sdk.web.async_client import AsyncWebClient

from . import thread_state
from .activity import tracker
from .config import Config, Project
from .git_push import commit_and_push, pull_rebase
from .invoker import run_chat, run_role
from .locks import FeatureLocks
from .slack_streamer import SlackStreamer


log = logging.getLogger(__name__)


_TOOL_VERBS = {
    "Read": "reading files",
    "Glob": "searching files",
    "Grep": "searching code",
    "Write": "writing files",
    "Edit": "editing files",
    "MultiEdit": "editing files",
    "NotebookEdit": "editing notebook",
    "Bash": "running commands",
    "BashOutput": "reading command output",
    "WebFetch": "fetching web",
    "WebSearch": "searching web",
    "TodoWrite": "tracking tasks",
    "Task": "delegating to subagent",
}

# Session state is per-thread — reply-in-thread resumes, new thread starts fresh.
_ROLE_FOLLOW_UP_HINT = (
    "_:speech_balloon: Reply in this thread to refine or ask about this pass — "
    "start a new thread for a new turn or different feature._"
)
_CHAT_FOLLOW_UP_HINT = (
    "_:speech_balloon: Reply in this thread to follow up — "
    "start a new thread for a new topic._"
)


def _verb_for_tool(name: str) -> str:
    return _TOOL_VERBS.get(name, name.lower())


async def _pump(streamer: SlackStreamer, events) -> tuple[str, float | None]:
    """Render RunEvents into the streamer.

    Tool calls drive a live status footer that replaces in place
    (`⚙️ reading files ×5`) instead of accumulating one emoji per call.
    Real text blocks clear the status and stream into the message body.
    Returns (session_id, cost) from ResultMessage.
    """
    session_id, cost = "", None
    cur_tool: str | None = None
    cur_count = 0
    async for ev in events:
        if ev.kind == "result":
            session_id, cost = ev.session_id, ev.cost_usd
            continue
        if ev.kind == "text":
            cur_tool, cur_count = None, 0
            await streamer.set_status("✍️ writing…")
            await streamer.push(ev.text)
        elif ev.kind == "tool":
            name = ev.text
            if name == cur_tool:
                cur_count += 1
            else:
                cur_tool = name
                cur_count = 1
            label = _verb_for_tool(name)
            if cur_count > 1:
                label = f"{label} ×{cur_count}"
            await streamer.set_status(f"⚙️ {label}…")
        elif ev.kind == "thinking":
            # Don't clobber an active tool status with a generic "thinking"
            # — only show it when nothing else is happening.
            if cur_tool is None:
                await streamer.set_status("⚙️ thinking…")
    return session_id, cost


async def run_pass(
    *,
    cfg: Config,
    locks: FeatureLocks,
    client: AsyncWebClient,
    project: Project,
    channel_id: str,
    thread_ts: str,
    role: str,
    feature: str,
    speaker: str,
    user_message: str,
    attachments: list[str] | None = None,
    resume_session: str | None = None,
) -> None:
    # Remember this thread so subsequent replies can resume the session.
    if thread_state.get(channel_id, thread_ts) is None:
        thread_state.start(channel_id, thread_ts, project.key, feature, role, speaker)

    lock = await locks.get(project.key, feature)
    async with lock:
        # Re-fetch session_id *after* acquiring the lock — if a prior pass
        # on this thread finished while we were queued, its session_id is
        # now persisted and we should resume from it instead of starting
        # fresh. Without this, a reply typed mid-pass loses all context.
        latest = thread_state.get(channel_id, thread_ts)
        if latest and latest.get("session_id") and not resume_session:
            resume_session = latest["session_id"]

        # Sync local to origin before the agent reads anything. Skips the
        # pass if remote moved and rebase can't auto-resolve — better to
        # stop here than let the role write decisions onto a stale base.
        pull_err = await pull_rebase(project)
        if pull_err:
            await client.chat_postMessage(
                channel=channel_id, thread_ts=thread_ts,
                text=f":warning: {pull_err}",
            )
            return

        streamer = SlackStreamer(
            client=client,
            channel=channel_id,
            thread_ts=thread_ts,
            prefix=f"*{role}*" if not resume_session else f"*{role}* (cont.)",
        )
        await streamer.start(initial_status="⚙️ thinking…")

        tracker.start()
        try:
            session_id, cost = await _pump(
                streamer,
                run_role(
                    cfg=cfg,
                    project=project,
                    role=role,
                    feature=feature,
                    speaker=speaker,
                    user_message=user_message,
                    attachments=attachments,
                    resume_session=resume_session,
                ),
            )

            if session_id:
                thread_state.update_session(channel_id, thread_ts, session_id, speaker)

            suffix = [":white_check_mark: done"]
            if cost is not None:
                suffix.append(f"${cost:.4f}")
            if session_id:
                suffix.append(f"session `{session_id[:8]}`")

            push_result = await commit_and_push(project, role, feature, speaker)
            suffix.append(push_result)

            await streamer.finalize(" · ".join(suffix) + "\n" + _ROLE_FOLLOW_UP_HINT)
        except Exception as e:
            log.exception("run_pass failed")
            await streamer.finalize(f":x: failed: {e}")
        finally:
            tracker.end()


async def run_chat_pass(
    *,
    cfg: Config,
    client: AsyncWebClient,
    project: Project,
    channel_id: str,
    thread_ts: str,
    speaker: str,
    user_message: str,
    attachments: list[str] | None = None,
    resume_session: str | None = None,
) -> None:
    """Chat-mode pass. No feature lock (chat isn't tied to a feature), no
    git commit (nothing changes in .xorial), read-only tools.
    """
    if thread_state.get(channel_id, thread_ts) is None:
        thread_state.start(channel_id, thread_ts, project.key, "", "chat", speaker)

    # Chat answers read the repo — same fresh-state requirement as roles.
    pull_err = await pull_rebase(project)
    if pull_err:
        await client.chat_postMessage(
            channel=channel_id, thread_ts=thread_ts,
            text=f":warning: {pull_err}",
        )
        return

    streamer = SlackStreamer(
        client=client,
        channel=channel_id,
        thread_ts=thread_ts,
    )
    await streamer.start(initial_status="⚙️ thinking…")

    tracker.start()
    try:
        session_id, cost = await _pump(
            streamer,
            run_chat(
                cfg=cfg,
                project=project,
                user_message=user_message,
                resume_session=resume_session,
                attachments=attachments,
            ),
        )

        if session_id:
            thread_state.update_session(channel_id, thread_ts, session_id, speaker)

        suffix = [":speech_balloon: done"]
        if cost is not None:
            suffix.append(f"${cost:.4f}")
        if session_id:
            suffix.append(f"session `{session_id[:8]}`")
        await streamer.finalize(" · ".join(suffix) + "\n" + _CHAT_FOLLOW_UP_HINT)
    except Exception as e:
        log.exception("run_chat_pass failed")
        await streamer.finalize(f":x: failed: {e}")
    finally:
        tracker.end()
