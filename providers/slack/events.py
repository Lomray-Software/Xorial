"""Event handlers for thread replies and @mentions.

Thread reply flow:
  - filter: has thread_ts, not a bot, not a subtype (real user message)
  - look up thread_state[channel:thread_ts] → project, feature, role, session_id
  - dedup on client_msg_id (Slack redelivers on ack timeout)
  - download attached files into .xorial/tmp
  - invoke runner.run_pass with resume_session

@mention flow (in a bound channel, not in thread):
  - strip the bot mention, parse remaining text as a /xorial subcommand
  - reuse the same dispatch path via handlers — but we only wire the role
    subcommands here (intake/orchestrate/critic). Management commands
    stay on the slash so there is one obvious surface.
"""

import logging
import re

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from . import thread_state
from .attribution import resolve_speaker
from .config import Config
from .dedup import DedupCache
from .files import download_attachments
from .handlers import help_text
from .locks import FeatureLocks
from .router import RoutingError, feature_for_channel, project_for_workspace
from .runner import run_chat_pass, run_pass


log = logging.getLogger(__name__)


ROLE_ALIAS = {
    "intake": "intake",
    "orchestrate": "orchestrator",
    "orchestrator": "orchestrator",
    "critic": "critic",
}

# Message subtypes we accept. Slack uses subtype=None for normal user messages
# and "file_share" for messages carrying file attachments (legacy but still
# seen). Anything else (message_changed, message_deleted, channel_join, etc.)
# is noise for our purposes.
ACCEPTED_MSG_SUBTYPES: set[str | None] = {None, "file_share"}


def _dedup_key(event: dict) -> str:
    """Stable key for a logical inbound message. IMPORTANT: app_mention and
    message events for the same user message share the same client_msg_id,
    so using it as-is lets one handler beat the other to the punch."""
    cmid = event.get("client_msg_id")
    if cmid:
        return f"cmid:{cmid}"
    return f"ts:{event.get('channel','')}:{event.get('ts','')}"


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[UW][A-Z0-9]+>\s*", "", text or "").strip()


def register(
    app: AsyncApp,
    cfg: Config,
    locks: FeatureLocks,
    bot_user_id: str = "",
    self_bot_id: str = "",
) -> None:
    dedup = DedupCache(maxsize=2000)

    @app.event("member_joined_channel")
    async def on_member_joined(event, client: AsyncWebClient):
        # Fires for every join in a subscribed channel. We only care about
        # our own bot joining — post a welcome. Needs channels:read / groups:read
        # scopes and member_joined_channel event subscription in the Slack app.
        if not bot_user_id:
            return
        if event.get("user") != bot_user_id:
            return
        channel_id = event.get("channel", "")
        binding = feature_for_channel(cfg, channel_id)
        if binding:
            _, feature = binding
            text = (
                f"*Xorial is back.* This channel is already bound to `{feature}`.\n"
                f"`/xorial status` for where we stand — or `/xorial intake ...` to kick off a pass."
            )
        else:
            text = (
                "*Xorial has entered the chat.* Things just got serious.\n"
                "`/xorial help` for the manifesto. `/xorial new feat <name>` to start a new feature — "
                "or `/xorial bind feat/<name>` if it already exists."
            )
        try:
            await client.chat_postMessage(channel=channel_id, text=text)
        except Exception as e:
            log.warning("welcome post failed in %s: %s", channel_id, e)

    @app.event("message")
    async def on_message(event, client: AsyncWebClient):
        # Skip OUR OWN bot's posts (prevent self-loops), edits/deletes/
        # channel events, DMs without thread. We match bot_id against our own
        # rather than any bot_id so messages authored via another app's token
        # (e.g. a user's xoxp via a different Slack app) still reach the
        # agent as a real speaker turn. Fail-safe: if we couldn't resolve
        # our own bot_id at startup, fall back to "filter any bot_id" —
        # loses the cross-app feature but prevents streamer-echo loops.
        bot_id = event.get("bot_id")
        if bot_id and (not self_bot_id or bot_id == self_bot_id):
            return
        if event.get("subtype") not in ACCEPTED_MSG_SUBTYPES:
            return
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return
        if event.get("ts") == thread_ts:
            # The parent message itself (posted by the bot) — ignore.
            return

        key = _dedup_key(event)
        if dedup.seen(key):
            log.debug("dedup: skipping %s", key)
            return

        channel_id = event.get("channel", "")
        entry = thread_state.get(channel_id, thread_ts)
        if entry is None:
            return  # Thread not tracked — just chatter, not for us.

        team_id = event.get("team", "")
        try:
            project = project_for_workspace(cfg, team_id)
        except RoutingError:
            return
        if project.key != entry.get("project"):
            log.warning("thread project mismatch for %s", key)
            return

        user_id = event.get("user", "")
        speaker = resolve_speaker(cfg, user_id, "")
        text = event.get("text", "")

        attachments = await download_attachments(
            cfg.bot_token, project, thread_ts, event.get("files") or [],
        )

        role = entry.get("role", "")
        feature = entry.get("feature", "")
        resume = entry.get("session_id") or None
        if not role:
            return

        if role == "chat":
            # Chat threads aren't bound to a feature and aren't locked.
            await run_chat_pass(
                cfg=cfg,
                client=client,
                project=project,
                channel_id=channel_id,
                thread_ts=thread_ts,
                speaker=speaker,
                user_message=text,
                attachments=attachments or None,
                resume_session=resume,
            )
            return

        if not feature:
            return

        if locks.is_busy(project.key, feature):
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=":hourglass: previous pass still running — your message is queued behind it.",
            )
            # Fall through — lock will serialize.

        await run_pass(
            cfg=cfg,
            locks=locks,
            client=client,
            project=project,
            channel_id=channel_id,
            thread_ts=thread_ts,
            role=role,
            feature=feature,
            speaker=speaker,
            user_message=text,
            attachments=attachments or None,
            resume_session=resume,
        )

    @app.event("app_mention")
    async def on_app_mention(event, client: AsyncWebClient):
        thread_ts = event.get("thread_ts")
        channel_id = event.get("channel", "")

        # In a thread: on_message handles tracked threads. We only step in for
        # UNTRACKED threads (to give the user a clear "start a new pass" hint).
        # Shared dedup on client_msg_id means whichever handler wins, the other
        # exits. Order is non-deterministic but both paths are harmless:
        #   - tracked   → on_message wins, runs pass; we exit via dedup
        #   - untracked → on_message returns silently; we post warning
        if thread_ts:
            key = _dedup_key(event)
            if dedup.seen(key):
                return
            entry = thread_state.get(channel_id, thread_ts)
            if entry is None:
                await client.chat_postMessage(
                    channel=channel_id, thread_ts=thread_ts,
                    text=":warning: this thread isn't tracked. Start a new pass with `/xorial intake`.",
                )
            # Tracked thread case: on_message will process (or already did).
            return

        # Not in a thread → figure out what the user wants:
        #   "@xorial help"              → static help text (zero-cost)
        #   "@xorial intake ..."        → start a role pass
        #   "@xorial anything else"     → free-form chat-mode pass
        key = _dedup_key(event)
        if dedup.seen(key):
            return
        team_id = event.get("team", "")
        user_id = event.get("user", "")
        text = _strip_mention(event.get("text", ""))

        try:
            project = project_for_workspace(cfg, team_id)
        except RoutingError as e:
            await client.chat_postMessage(channel=channel_id, text=f":warning: {e}")
            return

        speaker = resolve_speaker(cfg, user_id, "")
        parts = text.split(maxsplit=1)
        first = parts[0].lower() if parts else ""

        # Cheap path: no text or "help" → static help, no LLM.
        if not parts or first == "help":
            await client.chat_postMessage(channel=channel_id, text=help_text())
            return

        # Role shortcut.
        if first in ROLE_ALIAS:
            role = ROLE_ALIAS[first]
            message = parts[1] if len(parts) > 1 else ""

            binding = feature_for_channel(cfg, channel_id)
            if binding is None:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=":warning: channel is not bound. Use `/xorial new ...` or `/xorial bind <feature>` first.",
                )
                return
            bound_project, feature = binding
            if bound_project.key != project.key:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=":warning: channel bound to a different project.",
                )
                return
            if locks.is_busy(project.key, feature):
                await client.chat_postMessage(
                    channel=channel_id,
                    text=f":hourglass: `{feature}` already has an agent running.",
                )
                return

            parent = await client.chat_postMessage(
                channel=channel_id,
                text=f":robot_face: *{role}* on `{feature}` — by {speaker}",
            )
            thread_ts = parent["ts"]
            attachments = await download_attachments(
                cfg.bot_token, project, thread_ts, event.get("files") or [],
            )
            await run_pass(
                cfg=cfg, locks=locks, client=client,
                project=project, channel_id=channel_id, thread_ts=thread_ts,
                role=role, feature=feature, speaker=speaker,
                user_message=message, attachments=attachments or None,
                resume_session=None,
            )
            return

        # Fallthrough: chat mode. Reply in a thread rooted at the user's own
        # message (its `ts` becomes the thread parent) so we don't litter the
        # channel with bot parent posts.
        thread_ts = event.get("ts", "")
        attachments = await download_attachments(
            cfg.bot_token, project, thread_ts, event.get("files") or [],
        )
        await run_chat_pass(
            cfg=cfg, client=client, project=project,
            channel_id=channel_id, thread_ts=thread_ts,
            speaker=speaker, user_message=text,
            attachments=attachments or None,
            resume_session=None,
        )
