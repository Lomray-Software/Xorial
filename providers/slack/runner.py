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
from .git_push import commit_and_push
from .invoker import run_chat, run_role
from .locks import FeatureLocks
from .slack_streamer import SlackStreamer


log = logging.getLogger(__name__)


_ACTIVITY = ("tool", "thinking")


async def _pump(streamer: SlackStreamer, events) -> tuple[str, float | None]:
    """Render RunEvents into the streamer, keeping tool/thinking markers on
    the same line (`🔧 Read · Read · Bash`) and breaking to a new line only
    around real text content. Returns (session_id, cost) from ResultMessage.
    """
    session_id, cost = "", None
    prev: str | None = None
    async for ev in events:
        if ev.kind == "result":
            session_id, cost = ev.session_id, ev.cost_usd
            continue
        if ev.kind == "text":
            if prev in _ACTIVITY:
                await streamer.push("\n")
            await streamer.push(ev.text)
        elif ev.kind == "tool":
            if prev in _ACTIVITY:
                await streamer.push(" · ")
            elif prev == "text":
                await streamer.push("\n")
            await streamer.push(ev.text)
        elif ev.kind == "thinking":
            if prev == "text":
                await streamer.push("\n")
            await streamer.push(ev.text)
        prev = ev.kind
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

    streamer = SlackStreamer(
        client=client,
        channel=channel_id,
        thread_ts=thread_ts,
        prefix=f"*{role}*" if not resume_session else f"*{role}* (cont.)",
    )
    await streamer.start()

    lock = await locks.get(project.key, feature)
    async with lock:
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

            await streamer.finalize(" · ".join(suffix))
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

    streamer = SlackStreamer(
        client=client,
        channel=channel_id,
        thread_ts=thread_ts,
    )
    await streamer.start()

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
        await streamer.finalize(" · ".join(suffix))
    except Exception as e:
        log.exception("run_chat_pass failed")
        await streamer.finalize(f":x: failed: {e}")
    finally:
        tracker.end()
