from __future__ import annotations

"""
Xorial Pipeline — configurable agent sequence per project.

The default sequence and skip list live in:
    core/templates/pipeline.json   ← owned by Xorial, defines all transitions

Project overrides live in:
    .xorial/context/pipeline.json ← owned by project, defines skip + custom_agents

Python code has no hardcoded role names or sequences.
To add a new role: edit core/templates/pipeline.json only.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        sequence: dict[str, str],
        skip: set[str],
        custom_agents: dict,
        project_root: str = "",
        xorial_core: str = "",
    ):
        self.sequence = sequence        # "after X → Y" transition map
        self.skip = skip                # agents to skip
        self.custom_agents = custom_agents
        self.project_root = project_root
        self.xorial_core = xorial_core

    def effective_owner(self, owner: str, extra_skip: set[str] | None = None, force: set[str] | None = None) -> str:
        """
        Resolve actual owner after applying skip rules.
        Follows sequence chain until a non-skipped agent is found.
        extra_skip — per-feature skip set merged on top of global pipeline skip.
        force — per-feature agents to un-skip even if globally skipped.
        """
        combined = (self.skip | (extra_skip or set())) - (force or set())
        visited: set[str] = set()
        current = owner
        while current in combined:
            if current in visited:
                logger.warning("Pipeline skip loop detected at '%s' — breaking", current)
                break
            visited.add(current)
            nxt = self.sequence.get(current)
            if nxt is None:
                logger.warning("No sequence entry for skipped agent '%s'", current)
                break
            current = nxt
        return current

    def prompt_section(self) -> str:
        """
        Returns a pipeline configuration block to inject into agent prompts.
        Empty string if no agents are skipped.
        """
        if not self.skip:
            return ""

        lines = [
            "# Pipeline configuration (this project)",
            "",
            f"Skipped agents: {', '.join(sorted(self.skip))}",
            "",
            "Handoff rules (after applying skips):",
        ]

        for agent, default_next in self.sequence.items():
            effective = self.effective_owner(default_next)
            if effective != default_next:
                lines.append(
                    f"  - After `{agent}`: hand off to `{effective}` "
                    f"(skipping `{default_next}`)"
                )

        # Orchestrator finalization note: if the agent that sets PASS is skipped,
        # orchestrator must finalize on AWAITING_HUMAN_REVIEW instead.
        # Detect this by checking if any agent whose sequence leads to orchestrator is skipped.
        orchestrator_via_skip = [
            agent for agent, nxt in self.sequence.items()
            if nxt in self.skip and self.effective_owner(nxt) == "orchestrator"
        ]
        if orchestrator_via_skip:
            skipped_before_orch = [self.sequence[a] for a in orchestrator_via_skip]
            lines += [
                "",
                "## Orchestrator finalization note",
                "",
                f"Skipped before orchestrator: {', '.join(f'`{a}`' for a in skipped_before_orch)}",
                "Since these agents are skipped, orchestrator MUST finalize when called",
                "after human review is complete (e.g. `status: AWAITING_HUMAN_REVIEW`).",
                "Do NOT wait for a PASS status that will never arrive.",
            ]

        return "\n".join(lines)

    def get_route(self, owner: str):
        """
        Return a Route for a custom agent defined in pipeline.json, or None if
        the owner is not a custom agent (fall back to built-in OWNER_TO_ROUTE).

        custom_agents entry format:
            "security-reviewer": {
                "type": "claude" | "codex",        # default: "claude"
                "model": "claude-opus-4-6",         # optional
                "reasoning": "high",                # optional, codex only
                "role_file": ".xorial/context/roles/security-reviewer.md"
                             # path relative to project_root, or absolute
            }
        """
        if owner not in self.custom_agents:
            return None

        from router import AgentType, Route  # avoid circular at module level

        agent_def = self.custom_agents[owner]
        role_file_raw = agent_def.get("role_file", "")

        # Resolve role_file: project-relative, absolute, or core/roles/ name
        if not role_file_raw:
            logger.warning("Custom agent '%s' has no role_file defined", owner)
            return None

        if role_file_raw.startswith("/"):
            role_file = role_file_raw
        elif role_file_raw.startswith(".xorial/") and self.project_root:
            role_file = str(Path(self.project_root) / role_file_raw)
        else:
            # Treat as a filename inside core/roles/
            role_file = str(Path(self.xorial_core) / "roles" / role_file_raw)

        type_str = agent_def.get("type", "claude").lower()
        agent_type = AgentType.CLAUDE if type_str == "claude" else AgentType.CODEX

        return Route(
            agent_type=agent_type,
            role_file=role_file,
            model=agent_def.get("model"),
            reasoning=agent_def.get("reasoning"),
        )


def load_pipeline(project_context: str, xorial_core: str) -> Pipeline:
    """
    Load pipeline config.

    Base sequence and default skip come from core/templates/pipeline.json.
    Project overrides (skip, custom_agents) come from .xorial/context/pipeline.json.
    Project skip completely replaces base skip — allows re-enabling skipped agents.
    """
    # ── Base (core template) ──────────────────────────────────────────────────
    base_path = Path(xorial_core) / "templates" / "pipeline.json"
    base: dict = {}
    if base_path.exists():
        try:
            base = json.loads(base_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read base pipeline template: %s", e)

    sequence: dict[str, str] = {
        k: v for k, v in base.get("sequence", {}).items()
        if not k.startswith("_")
    }
    base_skip: set[str] = set(base.get("skip", []))

    # ── Project overrides ─────────────────────────────────────────────────────
    project_path = Path(project_context) / "pipeline.json"
    project: dict = {}
    if project_path.exists():
        try:
            project = json.loads(project_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read project pipeline.json: %s", e)

    # Project skip replaces base skip entirely (so agents can be re-enabled)
    skip = set(project["skip"]) if "skip" in project else base_skip

    # Project can extend sequence (e.g. add a custom agent step)
    if "sequence" in project:
        sequence.update({
            k: v for k, v in project["sequence"].items()
            if not k.startswith("_")
        })

    custom_agents: dict = project.get("custom_agents", {})

    logger.info(
        "Pipeline loaded — skip: [%s], sequence entries: %d, custom agents: %d",
        ", ".join(sorted(skip)) if skip else "none",
        len(sequence),
        len(custom_agents),
    )
    return Pipeline(
        sequence=sequence,
        skip=skip,
        custom_agents=custom_agents,
        project_root=str(Path(project_context).parent.parent),  # project root = context/../..
        xorial_core=xorial_core,
    )
