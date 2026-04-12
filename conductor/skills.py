"""
Skills loader — reads skill .md files from core/skills/ and project/skills/.
Filters by role using subdirectory structure:

    skills/
      all/              ← injected into every role
      orchestrator/     ← injected only into orchestrator
      implementer/      ← injected only into implementer
      behavior-reviewer/
      ...

Project skills override core skills with the same filename stem.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Warn if injected skills exceed this many estimated tokens (~4 chars/token)
MAX_SKILLS_TOKENS = 4000

# Maps role_file basename → normalized role name (= subdirectory name)
ROLE_FILE_TO_NAME: dict[str, str] = {
    "05-intake.md": "intake",
    "10-orchestrator.md": "orchestrator",
    "20-critic.md": "critic",
    "30-implementer.md": "implementer",
    "40-reviewer.md": "reviewer",
    "50-behavior-reviewer.md": "behavior-reviewer",
}


def _load_dir(directory: Path) -> dict[str, str]:
    """Load all .md files from a directory. Returns {stem: content}."""
    result: dict[str, str] = {}
    if not directory.exists():
        return result
    for md_file in sorted(directory.glob("*.md")):
        if md_file.name.lower() == "readme.md":
            continue
        try:
            result[md_file.stem] = md_file.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning("Could not read skill %s: %s", md_file, e)
    return result


def _load_skills_from_root(root: Path, role_name: str) -> dict[str, str]:
    """
    Load applicable skills from a skills root directory.
    Merges all/ and role-specific subdirectory. Role-specific wins on name conflict.
    """
    skills = _load_dir(root / "all")
    skills.update(_load_dir(root / role_name))
    return skills


def load_skills_for_role(
    xorial_core: str,
    project_context: str,
    role_file: str,
) -> str:
    """
    Returns a formatted block of all skills applicable to `role_file`.
    Returns empty string if no skills apply.

    Project skills override core skills with the same filename stem.
    """
    role_name = ROLE_FILE_TO_NAME.get(
        os.path.basename(role_file),
        os.path.basename(role_file).lstrip("0123456789-").replace(".md", ""),
    )

    # Core skills first, project overrides by stem name
    skill_map: dict[str, str] = _load_skills_from_root(
        Path(xorial_core) / "skills", role_name
    )
    skill_map.update(_load_skills_from_root(
        Path(project_context) / "skills", role_name
    ))

    if not skill_map:
        return ""

    total_chars = sum(len(c) for c in skill_map.values())
    if total_chars // 4 > MAX_SKILLS_TOKENS:
        logger.warning(
            "Skills for role '%s' are large (~%d tokens). "
            "Consider reducing skill size.",
            role_name, total_chars // 4,
        )

    parts = [
        "---",
        "",
        "# Agent Skills",
        "",
        f"_The following skills are injected by the Xorial conductor for the `{role_name}` role._",
    ]
    for content in skill_map.values():
        parts += ["", "---", "", content]

    parts += ["", "---"]
    return "\n".join(parts)
