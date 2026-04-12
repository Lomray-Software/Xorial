from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AgentType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    HUMAN = "human"
    DONE = "done"


@dataclass
class Route:
    agent_type: AgentType
    role_file: str          # filename under core/roles/, e.g. "10-orchestrator.md"
    model: Optional[str] = None
    reasoning: Optional[str] = None  # codex reasoning level: "high", "x-high"


VALID_TYPES = {"feat", "fix", "refactor", "chore"}

OWNER_TO_ROUTE: dict[str, Route] = {
    "intake": Route(
        agent_type=AgentType.CLAUDE,
        role_file="05-intake.md",
        model="claude-opus-4-6",
    ),
    "orchestrator": Route(
        agent_type=AgentType.CLAUDE,
        role_file="10-orchestrator.md",
        model="claude-opus-4-6",
    ),
    "critic": Route(
        agent_type=AgentType.CLAUDE,
        role_file="20-critic.md",
        model="claude-opus-4-6",
    ),
    "implementer": Route(
        agent_type=AgentType.CODEX,
        role_file="30-implementer.md",
        reasoning="high",
    ),
    "reviewer": Route(
        agent_type=AgentType.CODEX,
        role_file="40-reviewer.md",
        reasoning="high",
    ),
    "behavior-reviewer": Route(
        agent_type=AgentType.CODEX,
        role_file="50-behavior-reviewer.md",
        reasoning="high",
    ),
}


def apply_agent_config(route: Route, owner: str, agents_config: dict | None) -> Route:
    """
    Apply per-project agent overrides (from config.json "agents") onto a resolved route.

    Merge order: built-in defaults → agents.default → agents.<owner>
    Each level only overrides fields that are explicitly set.
    Supported keys per entry: "type" ("claude"|"codex"), "model", "reasoning".
    """
    if not agents_config:
        return route

    overrides: dict = {}
    if "default" in agents_config and isinstance(agents_config["default"], dict):
        overrides.update(agents_config["default"])
    if owner in agents_config and isinstance(agents_config[owner], dict):
        overrides.update(agents_config[owner])

    if not overrides:
        return route

    agent_type = route.agent_type
    model = route.model
    reasoning = route.reasoning

    if "type" in overrides:
        type_str = str(overrides["type"]).lower()
        agent_type = AgentType.CLAUDE if type_str == "claude" else AgentType.CODEX

    if "model" in overrides:
        model = overrides["model"] or None

    if "reasoning" in overrides:
        reasoning = overrides["reasoning"] or None

    return Route(agent_type=agent_type, role_file=route.role_file, model=model, reasoning=reasoning)


def resolve(status: dict) -> tuple[Route | None, bool]:
    """
    Returns (route, needs_human_pause).

    needs_human_pause=True when a human must act before the conductor can proceed.
    In that case route is None.
    """
    owner = status.get("owner", "")
    current_status = status.get("status", "")
    stage = status.get("stage", "")

    # Feature complete
    if stage == "done" and current_status == "DONE":
        return Route(agent_type=AgentType.DONE, role_file=""), False

    # Human must act
    if owner == "human":
        return None, True

    route = OWNER_TO_ROUTE.get(owner)
    return route, False
