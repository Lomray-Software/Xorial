from .config import Config


def resolve_speaker(cfg: Config, user_id: str, fallback_display: str = "") -> str:
    """Resolve Slack user_id to the speaker identity used in agent artifacts
    (history entries, commits, etc.). Falls back to the Slack display name
    so an unregistered user is still attributable. Never returns empty."""
    name = cfg.users.get(user_id)
    if name:
        return name
    if fallback_display:
        return fallback_display
    return user_id


def format_thread_line(speaker: str, text: str) -> str:
    """Single-line format when we replay thread history into a prompt.
    Keep it compact — this gets embedded into role prompts."""
    return f"{speaker}: {text}"


def format_thread(entries: list[tuple[str, str]]) -> str:
    """entries: [(speaker, text), ...]"""
    return "\n".join(format_thread_line(s, t) for s, t in entries)
