import asyncio
import logging
import sys

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from . import events as slack_events
from . import handlers as slack_handlers
from . import restart_watcher
from .activity import tracker
from .config import ConfigError, load
from .locks import FeatureLocks


async def amain() -> None:
    cfg = load()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = AsyncApp(
        token=cfg.bot_token,
        signing_secret=cfg.signing_secret,
    )
    # Resolve our own bot user id + bot id up front. `bot_user_id` lets the
    # member_joined handler tell "I was added" from a normal join. `self_bot_id`
    # lets the message filter skip OUR OWN bot's posts without dropping
    # events from other apps — e.g. a user-token xoxp post made via a
    # different Slack app, which Slack still tags with that app's bot_id.
    try:
        auth = await app.client.auth_test()
        bot_user_id = auth.get("user_id", "")
        self_bot_id = auth.get("bot_id", "")
    except Exception as e:
        logging.warning("auth.test failed, welcome posts disabled: %s", e)
        bot_user_id = ""
        self_bot_id = ""

    locks = FeatureLocks()
    slack_handlers.register(app, cfg, locks)
    slack_events.register(
        app, cfg, locks,
        bot_user_id=bot_user_id, self_bot_id=self_bot_id,
    )

    # Background task: watches for a restart flag from the post-merge hook,
    # self-exits when idle so launchd respawns us with fresh code.
    asyncio.create_task(restart_watcher.run(tracker))

    handler = AsyncSocketModeHandler(app, cfg.app_token)
    await handler.start_async()


def main() -> None:
    try:
        asyncio.run(amain())
    except ConfigError as e:
        print(f"\n[config error]\n{e}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
