from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Columns in display order — first matching predicate wins
_COLUMNS = [
    ("🔴 Needs Input", lambda stage, st: st in ("NEEDS_HUMAN_INPUT", "BLOCKED")),
    ("🔵 In Progress", lambda stage, st: st == "IN_PROGRESS" and stage != "review"),
    ("👀 Review",      lambda stage, st: stage == "review"),
    ("✅ Done",        lambda stage, st: stage == "done" or st == "DONE"),
    ("⏳ Queued",      lambda stage, st: True),  # catch-all
]

_SETTINGS = (
    "\n%% kanban:settings\n"
    "```\n"
    '{"kanban-plugin":"basic","list-collapse":[false,false,false,false,false]}\n'
    "```\n"
    "%%\n"
)


def _column_for(status: dict) -> str:
    stage = status.get("stage", "")
    st = status.get("status", "")
    for name, pred in _COLUMNS:
        if pred(stage, st):
            return name
    return "⏳ Queued"


def rebuild(context_dir: str, all_statuses: dict[str, dict]) -> None:
    """Rebuild kanban.md from all current feature statuses."""
    kanban_path = Path(context_dir) / "kanban.md"

    buckets: dict[str, list[str]] = {col: [] for col, _ in _COLUMNS}

    for feature, status in sorted(all_statuses.items()):
        if not status.get("feature"):
            continue
        col = _column_for(status)
        name = feature.split("/")[-1]
        buckets[col].append(f"- [ ] [[work/{feature}/{name}|{name}]]")

    lines = ["---", "", "kanban-plugin: basic", "", "---", ""]
    for col, _ in _COLUMNS:
        lines.append(f"## {col}")
        lines.append("")
        lines.extend(buckets[col])
        lines.append("")

    content = "\n".join(lines) + _SETTINGS

    try:
        kanban_path.write_text(content, encoding="utf-8")
        logger.debug("Kanban rebuilt (%d features)", sum(len(v) for v in buckets.values()))
    except Exception as e:
        logger.warning("Failed to rebuild kanban: %s", e)
