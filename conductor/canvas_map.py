from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Static IDs that belong to the fixed scaffold — never touched by auto-update
_STATIC_IDS = {
    "dashboard", "project-context", "kanban",
    "knowledge", "skills", "coding-standards", "roles",
    "grp-work", "grp-feat", "grp-fix", "grp-refactor", "grp-chore",
    "grp-ref",
    "e1", "e2", "e3", "e4",
}

# Layout constants for auto-placed feature nodes
_FEAT_START_X = -700   # x of first feature entry node in feat group
_FEAT_Y       = 680    # y of feature entry nodes
_FEAT_W       = 280
_FEAT_H       = 80
_FEAT_GAP_X   = 320    # horizontal gap between features

_SUB_Y_OFFSET = 200    # plan/handoff/history below entry node
_SUB_W        = 220
_SUB_H        = 70
_SUB_GAP_X    = 260    # horizontal gap between sub-nodes


def _feature_nodes(feature: str, entry_x: int) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges) for one feature positioned at entry_x."""
    ftype, name = feature.split("/", 1)
    base = f"work/{feature}"
    entry_id = f"feat-{name}"

    nodes = [
        {
            "id": entry_id,
            "type": "file",
            "file": f"{base}/{name}.md",
            "x": entry_x,
            "y": _FEAT_Y,
            "width": _FEAT_W,
            "height": _FEAT_H,
        }
    ]

    sub_files = [
        ("plan",    f"{base}/plan.md"),
        ("handoff", f"{base}/handoff.md"),
        ("history", f"{base}/history/history.md"),
        ("links",   f"{base}/links.md"),
    ]

    sub_x = entry_x - _SUB_GAP_X
    for key, path in sub_files:
        sub_id = f"{name}-{key}"
        nodes.append({
            "id": sub_id,
            "type": "file",
            "file": path,
            "x": sub_x,
            "y": _FEAT_Y + _SUB_Y_OFFSET,
            "width": _SUB_W,
            "height": _SUB_H,
        })
        sub_x += _SUB_GAP_X

    edges = [
        {"id": f"e-dash-{name}", "fromNode": "dashboard",
         "fromSide": "bottom", "toNode": entry_id, "toSide": "top"},
        {"id": f"e-{name}-plan",    "fromNode": entry_id, "fromSide": "bottom",
         "toNode": f"{name}-plan",    "toSide": "top"},
        {"id": f"e-{name}-handoff", "fromNode": entry_id, "fromSide": "bottom",
         "toNode": f"{name}-handoff", "toSide": "top"},
        {"id": f"e-{name}-history", "fromNode": entry_id, "fromSide": "bottom",
         "toNode": f"{name}-history", "toSide": "top"},
    ]

    return nodes, edges


def rebuild(context_dir: str, all_statuses: dict[str, dict]) -> None:
    """Rebuild dynamic (work) section of project-map.canvas."""
    canvas_path = Path(context_dir) / "project-map.canvas"
    if not canvas_path.exists():
        logger.debug("project-map.canvas not found — skipping")
        return

    try:
        data = json.loads(canvas_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read project-map.canvas: %s", e)
        return

    # Keep only static nodes/edges; drop previously auto-generated ones
    static_nodes = [n for n in data.get("nodes", []) if n["id"] in _STATIC_IDS]
    static_edges = [e for e in data.get("edges", []) if e["id"] in _STATIC_IDS]

    # Add nodes for every known feature
    features = sorted(f for f in all_statuses if all_statuses[f].get("feature"))
    new_nodes: list[dict] = []
    new_edges: list[dict] = []

    for i, feature in enumerate(features):
        x = _FEAT_START_X + i * _FEAT_GAP_X
        fn, fe = _feature_nodes(feature, x)
        new_nodes.extend(fn)
        new_edges.extend(fe)

    data["nodes"] = static_nodes + new_nodes
    data["edges"] = static_edges + new_edges

    try:
        canvas_path.write_text(
            json.dumps(data, indent="\t", ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("project-map.canvas rebuilt (%d features)", len(features))
    except Exception as e:
        logger.warning("Failed to write project-map.canvas: %s", e)
