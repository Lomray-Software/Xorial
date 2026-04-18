import logging
import os
import shlex
import shutil

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from . import storage, thread_state
from .attribution import resolve_speaker
from .config import Config, Project
from .files import download_attachments
from .git_push import commit_and_push
from .locks import FeatureLocks
from .router import RoutingError, feature_for_channel, project_for_workspace
from .runner import run_pass


log = logging.getLogger(__name__)


VALID_TYPES = {"feat", "fix", "refactor", "chore"}
AGENT_COMMANDS = {"intake", "orchestrate", "orchestrator", "critic"}
# Slack-visible -> canonical role name
ROLE_ALIAS = {
    "intake": "intake",
    "orchestrate": "orchestrator",
    "orchestrator": "orchestrator",
    "critic": "critic",
}


def _parse(text: str) -> list[str]:
    try:
        return shlex.split(text or "")
    except ValueError:
        return (text or "").split()


def register(app: AsyncApp, cfg: Config, locks: FeatureLocks) -> None:

    @app.command("/xorial")
    async def xorial_command(ack, body, client: AsyncWebClient, respond):
        await ack()
        text = body.get("text", "").strip()
        args = _parse(text)
        if not args:
            await respond(help_text())
            return

        sub = args[0].lower()
        rest = args[1:]
        team_id = body.get("team_id", "")
        channel_id = body.get("channel_id", "")
        user_id = body.get("user_id", "")
        user_name = body.get("user_name", "")
        speaker = resolve_speaker(cfg, user_id, user_name)

        try:
            project = project_for_workspace(cfg, team_id)
        except RoutingError as e:
            await respond(f":warning: {e}")
            return

        if sub == "help":
            await respond(help_text())
            return

        if sub == "whoami":
            await respond(f"Speaker: *{speaker}*  ·  project: *{project.name}*")
            return

        if sub == "list":
            await _list_features(respond, project)
            return

        if sub == "new":
            await _cmd_new(respond, cfg, project, channel_id, rest)
            return

        if sub == "bind":
            await _cmd_bind(respond, cfg, project, channel_id, rest)
            return

        if sub == "unbind":
            storage.unbind_channel(channel_id)
            cfg.channels.pop(channel_id, None)
            await respond(":white_check_mark: channel unbound")
            return

        if sub == "delete":
            await _cmd_delete(respond, cfg, locks, project, speaker, channel_id, rest)
            return

        if sub == "status":
            await _cmd_status(respond, cfg, channel_id)
            return

        if sub == "register":
            # /xorial register <name>   — user registers their own instance_name
            if not rest:
                await respond("Usage: `/xorial register <your name>`")
                return
            name = " ".join(rest)
            storage.set_user(user_id, name)
            cfg.users[user_id] = name
            await respond(f":white_check_mark: recorded you as *{name}*")
            return

        if sub in AGENT_COMMANDS:
            await _cmd_run_role(
                app=app,
                cfg=cfg,
                locks=locks,
                client=client,
                respond=respond,
                body=body,
                project=project,
                speaker=speaker,
                role=ROLE_ALIAS[sub],
                message=" ".join(rest),
            )
            return

        await respond(f":question: unknown subcommand `{sub}`. Try `/xorial help`.")


def help_text() -> str:
    return (
        "*Xorial commands*\n"
        "• `/xorial list` — features in this project\n"
        "• `/xorial new <feat|fix|refactor|chore> <name>` — create feature + bind channel\n"
        "• `/xorial bind <type>/<name>` — bind this channel to an existing feature\n"
        "• `/xorial unbind` — remove channel binding\n"
        "• `/xorial delete <type>/<name> [confirm]` — hard-delete feature (folder + bindings + threads)\n"
        "• `/xorial status` — show feature status\n"
        "• `/xorial intake` — run intake role in a thread\n"
        "• `/xorial orchestrate` — run orchestrator\n"
        "• `/xorial critic` — run critic\n"
        "• `/xorial whoami` — show who you are recorded as\n"
        "• `/xorial register <name>` — register your speaker identity\n"
        "• `@xorial <anything>` — ask me questions in chat mode"
    )


async def _list_features(respond, project: Project) -> None:
    work = project.work_dir
    if not os.path.isdir(work):
        await respond("_no features yet_")
        return
    lines = []
    for t in sorted(os.listdir(work)):
        tdir = os.path.join(work, t)
        if not os.path.isdir(tdir):
            continue
        for name in sorted(os.listdir(tdir)):
            if os.path.isdir(os.path.join(tdir, name)):
                lines.append(f"• `{t}/{name}`")
    await respond("\n".join(lines) if lines else "_no features yet_")


def _bind_in_memory(cfg: Config, channel_id: str, project_key: str, feature: str) -> None:
    cfg.channels[channel_id] = {"project": project_key, "feature": feature}


async def _cmd_new(respond, cfg: Config, project: Project, channel_id: str, rest: list[str]) -> None:
    if len(rest) < 2:
        await respond("Usage: `/xorial new <feat|fix|refactor|chore> <name>`")
        return
    ftype, name = rest[0].lower(), rest[1]
    if ftype not in VALID_TYPES:
        await respond(f"Invalid type `{ftype}`. One of: {', '.join(sorted(VALID_TYPES))}")
        return
    feature = f"{ftype}/{name}"
    path = project.feature_path(feature)
    if os.path.exists(path):
        await respond(f":warning: `{feature}` already exists")
    else:
        os.makedirs(path, exist_ok=True)

    storage.bind_channel(channel_id, project.key, feature)
    _bind_in_memory(cfg, channel_id, project.key, feature)
    await respond(
        f":white_check_mark: created `{feature}` and bound this channel.\n"
        f"Next: `/xorial intake` to start the interview (or `/xorial orchestrate` for fix/refactor)."
    )


async def _cmd_bind(respond, cfg: Config, project: Project, channel_id: str, rest: list[str]) -> None:
    if not rest:
        await respond("Usage: `/xorial bind <type>/<name>`  (e.g. `feat/auth`)")
        return
    feature = rest[0]
    if "/" not in feature:
        await respond(":warning: feature must include type prefix, e.g. `feat/auth`")
        return
    ftype = feature.split("/", 1)[0]
    if ftype not in VALID_TYPES:
        await respond(f"Invalid type `{ftype}`.")
        return
    path = project.feature_path(feature)
    if not os.path.isdir(path):
        await respond(f":warning: feature `{feature}` not found — run `/xorial new ...` first")
        return
    storage.bind_channel(channel_id, project.key, feature)
    _bind_in_memory(cfg, channel_id, project.key, feature)
    await respond(f":link: channel bound to `{feature}`")


async def _cmd_status(respond, cfg: Config, channel_id: str) -> None:
    binding = feature_for_channel(cfg, channel_id)
    if binding is None:
        await respond("_channel is not bound. Use `/xorial bind <feature>`._")
        return
    project, feature = binding
    status_path = os.path.join(project.feature_path(feature), "status.json")
    if not os.path.exists(status_path):
        await respond(f"`{feature}` — _no status.json yet_")
        return
    import json
    with open(status_path) as f:
        st = json.load(f)
    await respond(
        f"*{feature}*\n"
        f"status: `{st.get('status', '?')}`  ·  "
        f"stage: `{st.get('stage', '?')}`  ·  "
        f"owner: `{st.get('owner', '?')}`"
    )


async def _cmd_run_role(
    app: AsyncApp,
    cfg: Config,
    locks: FeatureLocks,
    client: AsyncWebClient,
    respond,
    body: dict,
    project: Project,
    speaker: str,
    role: str,
    message: str,
) -> None:
    channel_id = body.get("channel_id", "")
    binding = feature_for_channel(cfg, channel_id)
    if binding is None:
        await respond(":warning: channel is not bound. Use `/xorial new ...` or `/xorial bind <feature>` first.")
        return
    bound_project, feature = binding
    if bound_project.key != project.key:
        await respond(":warning: channel is bound to a different project than this workspace.")
        return

    if locks.is_busy(project.key, feature):
        await respond(f":hourglass: `{feature}` already has an agent running. Wait for it to finish.")
        return

    # Post a parent message so streamed output lives in a thread.
    parent = await client.chat_postMessage(
        channel=channel_id,
        text=f":robot_face: *{role}* on `{feature}` — by {speaker}",
    )
    thread_ts = parent["ts"]

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
        user_message=message,
        attachments=None,
        resume_session=None,
    )


async def _cmd_delete(
    respond,
    cfg: Config,
    locks: FeatureLocks,
    project: Project,
    speaker: str,
    channel_id: str,
    rest: list[str],
) -> None:
    """Hard-delete a feature. Two-step (`confirm`) and only runnable from
    the channel bound to that feature. Also pushes the deletion so main
    stays clean — history keeps the old content, current tree doesn't."""
    if not rest:
        await respond(
            "Usage: `/xorial delete <type>/<name>` — preview what will be dropped.\n"
            "Add `confirm` to actually delete: `/xorial delete feat/hello confirm`"
        )
        return
    feature = rest[0]
    if "/" not in feature:
        await respond(":warning: feature must include type prefix, e.g. `feat/auth`")
        return
    ftype = feature.split("/", 1)[0]
    if ftype not in VALID_TYPES:
        await respond(f"Invalid type `{ftype}`. One of: {', '.join(sorted(VALID_TYPES))}")
        return

    binding = feature_for_channel(cfg, channel_id)
    if binding is None or binding[1] != feature or binding[0].key != project.key:
        await respond(
            f":warning: run `/xorial delete {feature}` from the channel bound to `{feature}`. "
            "This keeps destructive ops tied to their owning channel."
        )
        return

    if locks.is_busy(project.key, feature):
        await respond(f":hourglass: `{feature}` has an agent running — can't delete now.")
        return

    path = project.feature_path(feature)
    if not os.path.isdir(path):
        await respond(f":warning: feature folder not found at `{path}` — nothing to delete.")
        return

    # Count impact for the preview (and for the confirmation message).
    ch_count = sum(
        1 for b in cfg.channels.values()
        if b.get("project") == project.key and b.get("feature") == feature
    )
    th_data = storage.read("threads").get("threads", {})
    th_count = sum(
        1 for e in th_data.values()
        if e.get("project") == project.key and e.get("feature") == feature
    )

    confirm = len(rest) > 1 and rest[1].lower() == "confirm"
    if not confirm:
        await respond(
            f":warning: *preview — nothing deleted yet.* `/xorial delete {feature} confirm` to proceed.\n"
            f"• remove folder `{path}`\n"
            f"• unbind {ch_count} channel(s) pointing at `{feature}`\n"
            f"• drop {th_count} tracked thread session(s)\n"
            f"• commit + push the deletion to `origin/{project.git_branch}`"
        )
        return

    # Execute.
    shutil.rmtree(path)
    dropped_ch = storage.unbind_feature_everywhere(project.key, feature)
    for cid in [
        cid for cid, b in list(cfg.channels.items())
        if b.get("project") == project.key and b.get("feature") == feature
    ]:
        cfg.channels.pop(cid, None)
    dropped_th = thread_state.drop_for_feature(project.key, feature)

    push_result = await commit_and_push(project, "delete", feature, speaker)

    await respond(
        f":wastebasket: deleted `{feature}` · unbound {dropped_ch} channel(s) · "
        f"dropped {dropped_th} thread(s) · {push_result}"
    )
