from __future__ import annotations

import os
from config import Config
from pipeline import Pipeline
from router import Route
from skills import load_skills_for_role


def build_prompt(config: Config, route: Route, feature_name: str, pipeline: Pipeline | None = None) -> str:
    """
    Builds the agent prompt with placeholders pre-substituted.
    Pipeline config and skills applicable to this role are appended automatically.
    """
    role_file_path = os.path.join(config.xorial_core, "roles", route.role_file)
    feature_path = config.feature_path(feature_name)

    suggestions_path = os.path.join(config.xorial_path, "suggestions")
    os.makedirs(suggestions_path, exist_ok=True)

    lines = [
        f"Take role: {role_file_path}",
        f"Work on: {feature_path}/",
        "Start your pass.",
        "",
        "# Resolved paths (pre-filled by conductor)",
        f"xorial_core = {config.xorial_core}",
        f"project_context = {config.project_context}",
        f"feature_path = {feature_path}",
        f"suggestions = {suggestions_path}",
    ]

    if pipeline:
        pipeline_section = pipeline.prompt_section()
        if pipeline_section:
            lines += ["", pipeline_section]

    skills_block = load_skills_for_role(
        xorial_core=config.xorial_core,
        project_context=config.project_context,
        role_file=route.role_file,
    )
    if skills_block:
        lines += ["", skills_block]

    return "\n".join(lines)
