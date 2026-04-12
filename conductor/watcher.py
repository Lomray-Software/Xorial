from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from state import ConductorState

logger = logging.getLogger(__name__)


def load_status(feature_path: str) -> dict | None:
    path = Path(feature_path) / "status.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _add_obsidian_icon(context_dir: str, feature: str) -> None:
    """Register LiArrowRightToLine icons for the feature entry file and history index."""
    data_path = Path(context_dir) / ".obsidian/plugins/obsidian-icon-folder/data.json"
    if not data_path.exists():
        return
    feature_name = feature.split("/")[-1]
    keys = [
        f"work/{feature}/{feature_name}.md",
        f"work/{feature}/history/history.md",
    ]
    try:
        with open(data_path) as f:
            data = json.load(f)
        added = [k for k in keys if k not in data]
        if added:
            for k in added:
                data[k] = "LiArrowRightToLine"
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("[%s] Obsidian icons registered: %s", feature, added)
    except Exception as e:
        logger.warning("[%s] Failed to update obsidian icon: %s", feature, e)


def watch_all(
    work_dir: str,
    state: ConductorState,
    on_change,  # callable(feature_id: str, status: dict)
    poll_interval: float = 10.0,
    stop_event: threading.Event | None = None,
    context_dir: str | None = None,
) -> None:
    """
    Watches all feature folders in work_dir for status.json changes.
    work_dir contains type subdirectories (feat/, fix/, refactor/, chore/)
    each containing individual feature folders.
    Calls on_change(feature_id, status) where feature_id is "type/name".
    Runs until stop_event is set (or forever if stop_event is None).
    """
    mtimes: dict[str, float] = {}

    while not (stop_event and stop_event.is_set()):
        try:
            _scan(work_dir, mtimes, state, on_change, context_dir)
        except Exception as e:
            logger.error("Watcher error: %s", e)

        time.sleep(poll_interval)


def _scan(
    work_dir: str,
    mtimes: dict[str, float],
    state: ConductorState,
    on_change,
    context_dir: str | None = None,
) -> None:
    if not os.path.exists(work_dir):
        return

    for type_entry in os.scandir(work_dir):
        if not type_entry.is_dir():
            continue

        for feature_entry in os.scandir(type_entry.path):
            if not feature_entry.is_dir():
                continue

            feature = f"{type_entry.name}/{feature_entry.name}"
            status_path = Path(feature_entry.path) / "status.json"

            if not status_path.exists():
                continue

            try:
                mtime = status_path.stat().st_mtime
            except OSError:
                continue

            if mtimes.get(feature) == mtime:
                continue

            is_new = feature not in mtimes
            mtimes[feature] = mtime
            status = load_status(feature_entry.path)
            if status is None:
                continue

            if is_new and context_dir:
                _add_obsidian_icon(context_dir, feature)

            last = state.last_status.get(feature)
            if status != last:
                state.update_status(feature, status)
                logger.info("[%s] Status changed: owner=%s stage=%s status=%s",
                            feature, status.get("owner"), status.get("stage"), status.get("status"))
                on_change(feature, status)
