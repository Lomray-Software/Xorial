import json
import os
from dataclasses import dataclass, field
from pathlib import Path


HERE = Path(__file__).resolve().parent


@dataclass
class Project:
    key: str
    name: str
    xorial_path: str
    project_root: str
    git_remote: str = ""
    git_branch: str = "main"
    auto_push: bool = True

    @property
    def xorial_core(self) -> str:
        return os.path.join(self.xorial_path, "core")

    @property
    def project_context(self) -> str:
        return os.path.join(self.project_root, ".xorial", "context")

    @property
    def work_dir(self) -> str:
        return os.path.join(self.project_context, "work")

    def feature_path(self, feature: str) -> str:
        # feature is "feat/name", "fix/name", etc.
        return os.path.join(self.work_dir, feature)


class ConfigError(Exception):
    """Raised for human-facing configuration problems. main() prints the
    message and exits cleanly, no stacktrace."""


@dataclass
class Config:
    bot_token: str
    app_token: str
    signing_secret: str
    anthropic_api_key: str
    projects_dir: str
    default_model: str = "claude-opus-4-6"
    log_level: str = "INFO"
    projects: dict[str, Project] = field(default_factory=dict)
    workspaces: dict[str, str] = field(default_factory=dict)   # team_id -> project_key
    channels: dict[str, dict] = field(default_factory=dict)    # channel_id -> {project, feature}
    users: dict[str, str] = field(default_factory=dict)        # user_id -> instance_name


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


REQUIRED_CONFIG_KEYS = (
    "bot_token",
    "app_token",
    "signing_secret",
    "anthropic_api_key",
    "projects_dir",
)


def _require_file(path: Path, hint: str) -> dict:
    if not path.exists():
        raise ConfigError(
            f"Missing {path.name}\n"
            f"  path:  {path}\n"
            f"  fix:   {hint}"
        )
    try:
        return _load_json(path)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}") from None


def load() -> Config:
    cfg = _require_file(
        HERE / "config.json",
        "cp config.example.json config.json && edit it (see SLACK_APP_SETUP.md)",
    )

    missing = [k for k in REQUIRED_CONFIG_KEYS if not cfg.get(k)]
    if missing:
        raise ConfigError(
            "config.json is missing required fields: " + ", ".join(missing)
            + "\n  see SLACK_APP_SETUP.md for where to get Slack tokens."
        )

    projects_data = _require_file(
        HERE / "projects.json",
        "cp projects.example.json projects.json && add at least one project entry",
    ).get("projects", {})
    if not projects_data:
        raise ConfigError(
            "projects.json has no projects — add at least one entry before starting."
        )

    workspaces_data = _require_file(
        HERE / "workspaces.json",
        "cp workspaces.example.json workspaces.json && map your Slack team_id to a project key",
    ).get("workspaces", {})
    if not workspaces_data:
        raise ConfigError(
            "workspaces.json has no entries — map your Slack team_id (T...) to a project key."
        )

    channels_data = _load_json(HERE / "channels.json").get("channels", {})
    users_data = _load_json(HERE / "users.json").get("users", {})

    try:
        projects = {
            key: Project(
                key=key,
                name=p.get("name", key),
                xorial_path=p["xorial_path"],
                project_root=p["project_root"],
                git_remote=p.get("git_remote", ""),
                git_branch=p.get("git_branch", "main"),
                auto_push=bool(p.get("auto_push", True)),
            )
            for key, p in projects_data.items()
        }
    except KeyError as e:
        raise ConfigError(
            f"projects.json entry is missing field {e}. Each project needs xorial_path and project_root."
        ) from None

    workspaces = {team_id: w["project"] for team_id, w in workspaces_data.items()}
    users = {uid: u["instance_name"] for uid, u in users_data.items()}

    return Config(
        bot_token=cfg["bot_token"],
        app_token=cfg["app_token"],
        signing_secret=cfg["signing_secret"],
        anthropic_api_key=cfg["anthropic_api_key"],
        projects_dir=cfg["projects_dir"],
        default_model=cfg.get("default_model", "claude-opus-4-6"),
        log_level=cfg.get("log_level", "INFO"),
        projects=projects,
        workspaces=workspaces,
        channels=channels_data,
        users=users,
    )
