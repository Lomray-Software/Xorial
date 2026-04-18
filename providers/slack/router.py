from .config import Config, Project


class RoutingError(Exception):
    pass


def project_for_workspace(cfg: Config, team_id: str) -> Project:
    """Slack team_id -> Project. Raises if workspace is not registered."""
    key = cfg.workspaces.get(team_id)
    if not key:
        raise RoutingError(
            f"Workspace {team_id} is not bound to any project. "
            f"Ask an admin to add it to workspaces.json."
        )
    project = cfg.projects.get(key)
    if not project:
        raise RoutingError(
            f"Workspace {team_id} points to project '{key}' which is not registered in projects.json."
        )
    return project


def feature_for_channel(cfg: Config, channel_id: str) -> tuple[Project, str] | None:
    """Slack channel_id -> (Project, feature). None if channel is not bound."""
    entry = cfg.channels.get(channel_id)
    if not entry:
        return None
    project = cfg.projects.get(entry["project"])
    if not project:
        return None
    return project, entry["feature"]
