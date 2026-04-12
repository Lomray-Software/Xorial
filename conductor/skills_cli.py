#!/usr/bin/env python3
"""
Xorial Skills CLI — install, list, and remove agent skills.

Usage (via run.sh):
    ./.xorial/run.sh skills install <source>
    ./.xorial/run.sh skills list
    ./.xorial/run.sh skills remove <name>
    ./.xorial/run.sh skills update

Sources:
    https://raw.githubusercontent.com/...        raw URL to a .md file
    github:user/repo                             install all skills from repo's skills/ dir
    github:user/repo/path/to/skill.md           install one skill from a GitHub repo
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"
MANIFEST_FILE = "manifest.json"


def _skills_dir(project_context: str) -> Path:
    return Path(project_context) / "skills"


def _manifest_path(project_context: str) -> Path:
    return _skills_dir(project_context) / MANIFEST_FILE


def _load_manifest(project_context: str) -> dict:
    path = _manifest_path(project_context)
    if not path.exists():
        return {"installed": []}
    with open(path) as f:
        return json.load(f)


def _save_manifest(project_context: str, manifest: dict) -> None:
    path = _manifest_path(project_context)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def _write_skill(project_context: str, name: str, content: str) -> Path:
    dest = _skills_dir(project_context) / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def _download_url(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def _github_raw_url(user: str, repo: str, path: str, branch: str = "main") -> str:
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"


def _list_github_skills(user: str, repo: str, directory: str = "skills") -> list[dict]:
    """Returns list of {name, download_url} for .md files in repo/directory."""
    url = f"{GITHUB_API}/repos/{user}/{repo}/contents/{directory}"
    resp = requests.get(url, timeout=15)
    if resp.status_code == 404:
        # Try root directory
        url = f"{GITHUB_API}/repos/{user}/{repo}/contents"
        resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    files = resp.json()
    return [
        {"name": Path(f["name"]).stem, "download_url": f["download_url"]}
        for f in files
        if f["type"] == "file" and f["name"].endswith(".md") and f["name"].lower() != "readme.md"
    ]


def cmd_install(project_context: str, source: str) -> None:
    manifest = _load_manifest(project_context)
    installed_names = {e["name"] for e in manifest["installed"]}
    added = []

    if source.startswith("github:"):
        # github:user/repo  or  github:user/repo/path/skill.md
        ref = source[len("github:"):]
        parts = ref.split("/", 2)
        user, repo = parts[0], parts[1]
        skill_path = parts[2] if len(parts) > 2 else None

        if skill_path and skill_path.endswith(".md"):
            # Single skill file
            raw_url = _github_raw_url(user, repo, skill_path)
            name = Path(skill_path).stem
            print(f"Downloading {name} from {raw_url}...")
            content = _download_url(raw_url)
            _write_skill(project_context, name, content)
            added.append({"name": name, "source": source, "installed_at": str(date.today())})
        else:
            # Skill pack: download all .md from skills/ directory
            directory = skill_path or "skills"
            print(f"Fetching skill list from github:{user}/{repo}/{directory}...")
            skills_list = _list_github_skills(user, repo, directory)
            if not skills_list:
                print(f"No skills found in {directory}/")
                return
            for item in skills_list:
                name = item["name"]
                print(f"  Installing {name}...")
                content = _download_url(item["download_url"])
                _write_skill(project_context, name, content)
                added.append({"name": name, "source": source, "installed_at": str(date.today())})

    elif source.startswith("http://") or source.startswith("https://"):
        # Raw URL
        name = Path(source.split("?")[0]).stem
        print(f"Downloading {name} from {source}...")
        content = _download_url(source)
        _write_skill(project_context, name, content)
        added.append({"name": name, "source": source, "installed_at": str(date.today())})

    else:
        print(f"Unknown source format: {source}", file=sys.stderr)
        print("Supported: https://... | github:user/repo | github:user/repo/path/skill.md")
        sys.exit(1)

    # Update manifest (replace existing entries with same name)
    new_installed = [e for e in manifest["installed"] if e["name"] not in {a["name"] for a in added}]
    new_installed.extend(added)
    manifest["installed"] = sorted(new_installed, key=lambda e: e["name"])
    _save_manifest(project_context, manifest)

    for a in added:
        print(f"  ✓ {a['name']}")
    print(f"\nInstalled {len(added)} skill(s) → .xorial/context/skills/")


def cmd_list(project_context: str, xorial_core: str) -> None:
    from skills import _load_dir

    core_skills = _load_dir(os.path.join(xorial_core, "skills"))
    project_skills = _load_dir(os.path.join(project_context, "skills"))
    manifest = _load_manifest(project_context)
    sourced = {e["name"]: e.get("source", "local") for e in manifest["installed"]}

    if core_skills:
        print("\n── Core skills (built-in) ───────────────────────────────")
        for s in core_skills:
            roles = ", ".join(sorted(s.applies_to)) if s.applies_to else "all roles"
            print(f"  {s.name:<30} [{roles}]")

    if project_skills:
        print("\n── Project skills ───────────────────────────────────────")
        for s in project_skills:
            if s.name == Path(MANIFEST_FILE).stem:
                continue
            roles = ", ".join(sorted(s.applies_to)) if s.applies_to else "all roles"
            src = sourced.get(s.name, "local")
            print(f"  {s.name:<30} [{roles}]  ← {src}")

    if not core_skills and not project_skills:
        print("No skills installed.")


def cmd_remove(project_context: str, name: str) -> None:
    skill_file = _skills_dir(project_context) / f"{name}.md"
    if not skill_file.exists():
        print(f"Skill '{name}' not found in project skills.", file=sys.stderr)
        sys.exit(1)
    skill_file.unlink()

    manifest = _load_manifest(project_context)
    manifest["installed"] = [e for e in manifest["installed"] if e["name"] != name]
    _save_manifest(project_context, manifest)
    print(f"✓ Removed {name}")


def cmd_update(project_context: str) -> None:
    manifest = _load_manifest(project_context)
    if not manifest["installed"]:
        print("Nothing to update.")
        return
    for entry in manifest["installed"]:
        source = entry.get("source", "")
        if not source or source == "local":
            print(f"  {entry['name']}: skipping (local)")
            continue
        print(f"  Updating {entry['name']}...")
        cmd_install(project_context, source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Xorial Skills CLI")
    parser.add_argument("--project", required=True, help="Project root")
    parser.add_argument("--xorial-core", default="", help="Xorial core path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="Install a skill or skill pack")
    p_install.add_argument("source", help="URL or github:user/repo[/path]")

    sub.add_parser("list", help="List installed skills")

    p_remove = sub.add_parser("remove", help="Remove a skill")
    p_remove.add_argument("name", help="Skill name (without .md)")

    sub.add_parser("update", help="Re-download all remotely-installed skills")

    args = parser.parse_args()

    from config import load_config
    config = load_config(args.project)
    project_context = config.project_context
    xorial_core = config.xorial_core

    if args.command == "install":
        cmd_install(project_context, args.source)
    elif args.command == "list":
        cmd_list(project_context, xorial_core)
    elif args.command == "remove":
        cmd_remove(project_context, args.name)
    elif args.command == "update":
        cmd_update(project_context)


if __name__ == "__main__":
    main()
