"""Polls for a "please restart" flag and self-exits when idle.

The flow:
  xorial-sync launchd agent -> `git pull` -> post-merge hook -> if
  providers/slack/ changed, `touch /tmp/xorial-slack.restart-pending`.

  xorial-slack launchd agent keeps this process alive with KeepAlive.
  This watcher polls the flag every POLL_SECONDS; if present AND no
  agent pass is running, it removes the flag and calls os._exit(0).
  launchd respawns us immediately with the new code.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from .activity import ActivityTracker


log = logging.getLogger(__name__)

FLAG_PATH = Path("/tmp/xorial-slack.restart-pending")
POLL_SECONDS = 15


async def run(tracker: ActivityTracker) -> None:
    while True:
        await asyncio.sleep(POLL_SECONDS)
        if not FLAG_PATH.exists():
            continue
        if tracker.busy():
            log.info("restart flag set; %d pass(es) in flight — waiting.", tracker.count)
            continue
        log.info("restart flag set and idle — exiting for launchd respawn.")
        try:
            FLAG_PATH.unlink(missing_ok=True)
        except OSError as e:
            log.warning("could not remove flag file: %s", e)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
