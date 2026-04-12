#!/usr/bin/env python3
"""
Xorial Roles CLI — scaffold, install, list, and remove custom agent roles.

Usage (via run.sh):
    ./.xorial/run.sh roles new <name>              scaffold a new role
    ./.xorial/run.sh roles install <source>         install from URL or GitHub
    ./.xorial/run.sh roles list                     list custom roles
    ./.xorial/run.sh roles remove <name>            remove a role
    ./.xorial/run.sh roles update                   re-download remotely installed roles

Sources:
    https://raw.githubusercontent.com/...            raw URL to a .md file
    github:user/repo                                 install all roles from repo's roles/ dir
    github:user/repo/path/to/role.md                 install one role from GitHub
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

ROLE_SCAFFOLD = """\
# Role: {title}

## Global Rules

See `{{{{xorial_core}}}}/ROLES_COMMON_RULES.md`.

## Role

You are the {title} for the current feature.

## Goal

<!-- Describe the goal of this role -->

## Read first

- `{{{{xorial_core}}}}/ROLES_COMMON_RULES.md`
- `{{{{feature_path}}}}/handoff.md`
- `{{{{feature_path}}}}/implementation.md`

## You own

- `{name}-review.md`
- `status.json`

## Responsibilities

<!-- List responsibilities -->
1. TODO

## Rules

- Always update `status.json`.
- Read the **Pipeline configuration** section in your prompt before any handoff.

## Exit marker

At the end of your pass, write one of:
- `PASS` — no issues, hand off to next agent
- `FAIL` — issues found, send back to implementer
- `NEEDS_HUMAN_INPUT` — escalate (see ROLES_COMMON_RULES.md)

## Handoff

On PASS: set `owner: <next-agent>` in `status.json`.
On FAIL: set `owner: implementer` in `status.json`.
"""


def _roles_dir(project_context: str) -> Path:
    return Path(project_context) / "roles"


def _manifest_path(project_context: str) -> Path:
    return _roles_dir(project_context) / MANIFEST_FILE


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


def _write_role(project_context: str, name: str, content: str) -> Path:
    dest = _roles_dir(project_context) / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def _download_url(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def _github_list(user: str, repo: str, directory: str = "roles") -> list[dict]:
    url = f"{GITHUB_API}/repos/{user}/{repo}/contents/{directory}"
    resp = requests.get(url, timeout=15)
    if resp.status_code == 404:
        url = f"{GITHUB_API}/repos/{user}/{repo}/contents"
        resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    files = resp.json()
    return [
        {"name": Path(f["name"]).stem, "download_url": f["download_url"]}
        for f in files
        if f["type"] == "file"
        and f["name"].endswith(".md")
        and f["name"].lower() != "readme.md"
    ]


def cmd_new(project_context: str, name: str) -> None:
    dest = _roles_dir(project_context) / f"{name}.md"
    if dest.exists():
        print(f"Role '{name}' already exists at {dest}", file=sys.stderr)
        sys.exit(1)

    title = name.replace("-", " ").title()
    content = ROLE_SCAFFOLD.format(name=name, title=title)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    print(f"✓ Created {dest}")
    print()
    print("Next steps:")
    print(f"  1. Edit the role file: {dest}")
    print(f"  2. Add to .xorial/context/pipeline.json:")
    print(f'     "sequence": {{ "prev-agent": "{name}", "{name}": "next-agent" }}')
    print(f'     "custom_agents": {{ "{name}": {{ "type": "claude", "role_file": ".xorial/context/roles/{name}.md" }} }}')


def cmd_install(project_context: str, source: str) -> None:
    manifest = _load_manifest(project_context)
    added = []

    if source.startswith("github:"):
        ref = source[len("github:"):]
        parts = ref.split("/", 2)
        user, repo = parts[0], parts[1]
        role_path = parts[2] if len(parts) > 2 else None

        if role_path and role_path.endswith(".md"):
            raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/{role_path}"
            name = Path(role_path).stem
            print(f"Downloading {name}...")
            content = _download_url(raw_url)
            _write_role(project_context, name, content)
            added.append({"name": name, "source": source, "installed_at": str(date.today())})
        else:
            directory = role_path or "roles"
            print(f"Fetching role list from github:{user}/{repo}/{directory}...")
            roles_list = _github_list(user, repo, directory)
            if not roles_list:
                print(f"No roles found in {directory}/")
                return
            for item in roles_list:
                print(f"  Installing {item['name']}...")
                content = _download_url(item["download_url"])
                _write_role(project_context, item["name"], content)
                added.append({"name": item["name"], "source": source, "installed_at": str(date.today())})

    elif source.startswith("http://") or source.startswith("https://"):
        name = Path(source.split("?")[0]).stem
        print(f"Downloading {name}...")
        content = _download_url(source)
        _write_role(project_context, name, content)
        added.append({"name": name, "source": source, "installed_at": str(date.today())})

    else:
        print(f"Unknown source format: {source}", file=sys.stderr)
        print("Supported: https://... | github:user/repo | github:user/repo/path/role.md")
        sys.exit(1)

    new_installed = [e for e in manifest["installed"] if e["name"] not in {a["name"] for a in added}]
    new_installed.extend(added)
    manifest["installed"] = sorted(new_installed, key=lambda e: e["name"])
    _save_manifest(project_context, manifest)

    for a in added:
        print(f"  ✓ {a['name']}")
    print(f"\nInstalled {len(added)} role(s) → .xorial/context/roles/")
    print("\nDon't forget to wire the role into pipeline.json (sequence + custom_agents).")
    print("See: core/CUSTOM_ROLES.md")


def cmd_list(project_context: str) -> None:
    roles_dir = _roles_dir(project_context)
    manifest = _load_manifest(project_context)
    sourced = {e["name"]: e.get("source", "local") for e in manifest["installed"]}

    roles = [
        f for f in sorted(roles_dir.glob("*.md"))
        if f.name.lower() != "readme.md" and f.stem != Path(MANIFEST_FILE).stem
    ]

    if not roles:
        print("No custom roles in this project.")
        return

    print("\n── Custom roles (.xorial/context/roles/) ───────────────────────────")
    for role_file in roles:
        name = role_file.stem
        src = sourced.get(name, "local")
        print(f"  {name:<35} ← {src}")


def cmd_remove(project_context: str, name: str) -> None:
    role_file = _roles_dir(project_context) / f"{name}.md"
    if not role_file.exists():
        print(f"Role '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    role_file.unlink()

    manifest = _load_manifest(project_context)
    manifest["installed"] = [e for e in manifest["installed"] if e["name"] != name]
    _save_manifest(project_context, manifest)
    print(f"✓ Removed {name}")
    print(f"Remember to remove '{name}' from pipeline.json (sequence + custom_agents).")


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
    parser = argparse.ArgumentParser(description="Xorial Roles CLI")
    parser.add_argument("--project", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Scaffold a new role file")
    p_new.add_argument("name", help="Role name in kebab-case, e.g. security-reviewer")

    p_install = sub.add_parser("install", help="Install a role or role pack")
    p_install.add_argument("source", help="URL or github:user/repo[/path]")

    sub.add_parser("list", help="List custom roles")

    p_remove = sub.add_parser("remove", help="Remove a custom role")
    p_remove.add_argument("name", help="Role name (without .md)")

    sub.add_parser("update", help="Re-download all remotely installed roles")

    args = parser.parse_args()

    from config import load_config
    config = load_config(args.project)
    project_context = config.project_context

    if args.command == "new":
        cmd_new(project_context, args.name)
    elif args.command == "install":
        cmd_install(project_context, args.source)
    elif args.command == "list":
        cmd_list(project_context)
    elif args.command == "remove":
        cmd_remove(project_context, args.name)
    elif args.command == "update":
        cmd_update(project_context)


if __name__ == "__main__":
    main()
