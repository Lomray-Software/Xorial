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
from .config import Config, Project
from .git_push import commit_and_push
from .invoker import run_role
from .locks import FeatureLocks
from .slack_streamer import SlackStreamer


log = logging.getLogger(__name__)


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
        try:
            session_id = ""
            cost = None
            async for ev in run_role(
                cfg=cfg,
                project=project,
                role=role,
                feature=feature,
                speaker=speaker,
                user_message=user_message,
                attachments=attachments,
                resume_session=resume_session,
            ):
                if ev.kind == "text":
                    await streamer.push(ev.text)
                elif ev.kind == "tool":
                    await streamer.push(f"\n{ev.text}\n")
                elif ev.kind == "thinking":
                    await streamer.push(ev.text)
                elif ev.kind == "result":
                    session_id = ev.session_id
                    cost = ev.cost_usd

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
