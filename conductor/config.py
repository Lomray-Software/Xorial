import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    xorial_path: str
    telegram_bot_token: str
    telegram_chat_id: str
    project_root: str
    instance_name: str = "local"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # Max agent runs per feature without human /resume before forcing a pause.
    # Set to 0 to disable. Default: 10.
    max_auto_iterations: int = 10
    # Minutes of log-file inactivity before the agent is considered hung and killed.
    # Set to 0 to disable. Default: 20.
    hang_timeout_minutes: int = 20
    # When true (default): try subscription first, fall back to API key on usage limit.
    # When false: subscription only — never fall back to API key.
    api_key_fallback: bool = True
    # Model to retry with when usage limit is hit, per agent type.
    # None/false = disabled. Example: {"claude": "claude-sonnet-4-5", "codex": "o4-mini"}
    usage_limit_fallback_model: Optional[dict] = None
    # Agent model/type overrides. None/false = use built-in defaults.
    # "default" applies to all roles; per-role keys override default.
    # Each entry: {"type": "claude"|"codex", "model": "...", "reasoning": "low|medium|high|xhigh"}
    # Example: {"default": {"type": "claude", "model": "claude-opus-4-6"}}
    agents: Optional[dict] = None

    @property
    def xorial_core(self) -> str:
        return os.path.join(self.xorial_path, "core")

    @property
    def project_context(self) -> str:
        return os.path.join(self.project_root, ".xorial", "context")

    @property
    def work_dir(self) -> str:
        return os.path.join(self.project_context, "work")

    def feature_path(self, feature_name: str) -> str:
        # feature_name is "feat/name", "fix/name", or "refactor/name"
        return os.path.join(self.work_dir, feature_name)

    def substitute(self, text: str) -> str:
        return (
            text
            .replace("{{xorial_core}}", self.xorial_core)
            .replace("{{project_context}}", self.project_context)
        )


def load_config(project_root: str) -> Config:
    config_path = os.path.join(project_root, ".xorial", "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path) as f:
        data = json.load(f)

    return Config(
        xorial_path=data["xorial_path"],
        telegram_bot_token=data.get("telegram_bot_token", ""),
        telegram_chat_id=data.get("telegram_chat_id", ""),
        instance_name=data.get("instance_name", "local"),
        anthropic_api_key=data.get("anthropic_api_key", ""),
        openai_api_key=data.get("openai_api_key", ""),
        max_auto_iterations=data.get("max_auto_iterations", 10),
        hang_timeout_minutes=data.get("hang_timeout_minutes", 20),
        api_key_fallback=bool(data.get("api_key_fallback", True)),
        usage_limit_fallback_model=data.get("usage_limit_fallback_model") or None,
        agents=data.get("agents") or None,
        project_root=project_root,
    )
