import asyncio
import logging
import sys

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from . import events as slack_events
from . import handlers as slack_handlers
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
    locks = FeatureLocks()
    slack_handlers.register(app, cfg, locks)
    slack_events.register(app, cfg, locks)

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
