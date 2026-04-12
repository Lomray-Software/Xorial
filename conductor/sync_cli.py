#!/usr/bin/env python3
"""
Xorial Sync — checks and updates project files owned by Xorial core.

Usage (via run.sh):
    ./.xorial/run.sh sync

What gets synced:

  run.sh            — pure template copy, safe to overwrite
  chat.md           — pure template copy, safe to overwrite
  config.json       — KEY MERGE only: adds missing keys from template,
                      never overwrites user-filled values
  community-plugins — ARRAY MERGE: adds missing plugin IDs, never removes
  core-plugins      — KEY MERGE: adds missing plugin keys, never removes
  project-context   — BOOTSTRAP only: created from template if missing,
                      never overwritten after that
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Files that are safe to overwrite verbatim (no project-specific content)
OVERWRITE: list[tuple[str, str]] = [
    # (src relative to xorial_path, dst relative to project .xorial/)
    ("core/templates/run.sh", "run.sh"),
    ("core/templates/chat.md", "chat.md"),
    # Obsidian vault config (vault root = .xorial/context/)
    ("core/templates/.obsidian/app.json",                           "context/.obsidian/app.json"),
    ("core/templates/.obsidian/plugins/dataview/data.json",         "context/.obsidian/plugins/dataview/data.json"),
    ("core/templates/.obsidian/plugins/omnisearch/data.json",       "context/.obsidian/plugins/omnisearch/data.json"),
    ("core/templates/.obsidian/snippets/xorial-ui.css",             "context/.obsidian/snippets/xorial-ui.css"),
    ("core/templates/.obsidian/plugins/cmdr/data.json",             "context/.obsidian/plugins/cmdr/data.json"),
    ("core/templates/dashboard.md",                                 "context/dashboard.md"),
    ("core/templates/.obsidian/graph.json",                         "context/.obsidian/graph.json"),
    ("core/templates/xorial.gitignore",                             ".gitignore"),
    ("core/templates/.obsidian/appearance.json",                    "context/.obsidian/appearance.json"),
]

# JSON arrays: add missing items from template, never remove existing entries
ARRAY_MERGE: list[tuple[str, str]] = [
    # community-plugins.json: user may install extra plugins — never wipe them
    ("core/templates/.obsidian/community-plugins.json", "context/.obsidian/community-plugins.json"),
]

# Files that need key-merge (JSON object: add missing keys, keep existing values)
KEY_MERGE: list[tuple[str, str]] = [
    ("core/templates/config.json", "config.json"),
    ("core/templates/pipeline.json", "context/pipeline.json"),
    # core-plugins: user may toggle plugins — add new ones, never remove
    ("core/templates/.obsidian/core-plugins.json",
     "context/.obsidian/core-plugins.json"),
    # Icon assignments grow dynamically (conductor adds per-feature icons) — never overwrite
    ("core/templates/.obsidian/plugins/obsidian-icon-folder/data.json",
     "context/.obsidian/plugins/obsidian-icon-folder/data.json"),
]

# Placeholder values in template — keys with these values are NOT copied
# (they would overwrite a user's real value with a placeholder)
PLACEHOLDER_PREFIXES = ("your-", "/absolute/path/")

# Files created from template only if missing — never overwritten after that
BOOTSTRAP: list[tuple[str, str]] = [
    # (src relative to xorial_path, dst relative to project .xorial/)
    ("core/templates/project-context.md",               "context/project-context.md"),
    ("core/templates/project-map.canvas",               "context/project-map.canvas"),
    ("core/templates/kanban.md",                        "context/kanban.md"),
    ("core/templates/.obsidian/bookmarks.json",         "context/.obsidian/bookmarks.json"),
    ("core/templates/coding-standards.md",              "context/coding-standards/coding-standards.md"),
    ("core/templates/skills.md",                        "context/skills/skills.md"),
    ("core/templates/roles.md",                         "context/roles/roles.md"),
]

# Keys to skip during key-merge for specific destination files.
# Use this for keys that live in core but are intentionally absent from project overrides.
KEY_MERGE_EXCLUDE: dict[str, list[str]] = {
    # 'sequence' lives in core/templates/pipeline.json only — project files only override
    # 'skip' and 'custom_agents'. Never auto-add sequence to the project file.
    "context/pipeline.json": ["sequence"],
}


def _is_placeholder(value) -> bool:
    if not isinstance(value, str):
        return False
    return any(value.startswith(p) for p in PLACEHOLDER_PREFIXES)


def _sync_overwrite(xorial_path: str, xorial_dir: str) -> list[str]:
    """Copy template files that have changed. Returns list of updated labels."""
    updated = []
    for src_rel, dst_rel in OVERWRITE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists():
            continue
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if dst.suffix == ".sh":
                os.chmod(dst, 0o755)
            updated.append(dst_rel)
    return updated


def _sync_array_merge(xorial_path: str, xorial_dir: str) -> list[str]:
    """
    Merge missing items from template JSON arrays into project arrays.
    Never removes existing items. Creates file from template if missing.
    """
    added = []
    for src_rel, dst_rel in ARRAY_MERGE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists():
            continue

        with open(src) as f:
            template: list = json.load(f)

        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "w") as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
                f.write("\n")
            added.append(f"created {dst_rel}")
            continue

        with open(dst) as f:
            project: list = json.load(f)

        missing = [item for item in template if item not in project]
        if missing:
            project.extend(missing)
            with open(dst, "w") as f:
                json.dump(project, f, indent=2, ensure_ascii=False)
                f.write("\n")
            for item in missing:
                added.append(f"{dst_rel}: +{item}")

    return added


def _sync_bootstrap(xorial_path: str, xorial_dir: str) -> list[str]:
    """Create files from template only if they don't exist. Never overwrites."""
    created = []
    for src_rel, dst_rel in BOOTSTRAP:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists() or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        created.append(f"created {dst_rel}")
    return created


def _sync_config(xorial_path: str, xorial_dir: str) -> list[str]:
    """
    Merge missing keys from config template into project config.
    If the destination file does not exist, creates it from the template.
    Returns list of keys that were added or files that were created.
    """
    added_keys = []
    for src_rel, dst_rel in KEY_MERGE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists():
            continue

        with open(src) as f:
            template = json.load(f)

        if not dst.exists():
            # Bootstrap: create from template, replace placeholders with empty strings
            dst.parent.mkdir(parents=True, exist_ok=True)
            project = {
                k: ("" if _is_placeholder(v) else v)
                for k, v in template.items()
            }
            with open(dst, "w") as f:
                json.dump(project, f, indent=4, ensure_ascii=False)
                f.write("\n")
            added_keys.append(f"created {dst_rel}")
            continue

        with open(dst) as f:
            project = json.load(f)

        exclude = KEY_MERGE_EXCLUDE.get(dst_rel, [])
        changed = False
        for key, default_value in template.items():
            if key in exclude:
                continue
            if key not in project:
                project[key] = "" if _is_placeholder(default_value) else default_value
                added_keys.append(f"{dst_rel}: +{key}")
                changed = True

        if changed:
            with open(dst, "w") as f:
                json.dump(project, f, indent=4, ensure_ascii=False)
                f.write("\n")

    return added_keys


def _check_status(xorial_path: str, xorial_dir: str) -> dict:
    """Returns sync status without making changes."""
    out_of_sync = []

    for src_rel, dst_rel in OVERWRITE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if src.exists() and (not dst.exists() or src.read_bytes() != dst.read_bytes()):
            out_of_sync.append(f"{dst_rel} (template updated)")

    for src_rel, dst_rel in ARRAY_MERGE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists() or not dst.exists():
            continue
        with open(src) as f:
            template = json.load(f)
        with open(dst) as f:
            project = json.load(f)
        missing = [item for item in template if item not in project]
        if missing:
            out_of_sync.append(f"{dst_rel} (missing: {', '.join(str(i) for i in missing)})")

    for src_rel, dst_rel in KEY_MERGE:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if not src.exists() or not dst.exists():
            continue
        with open(src) as f:
            template = json.load(f)
        with open(dst) as f:
            project = json.load(f)
        exclude = KEY_MERGE_EXCLUDE.get(dst_rel, [])
        missing = [k for k in template if k not in project and k not in exclude]
        if missing:
            out_of_sync.append(f"{dst_rel} (missing keys: {', '.join(missing)})")

    for src_rel, dst_rel in BOOTSTRAP:
        src = Path(xorial_path) / src_rel
        dst = Path(xorial_dir) / dst_rel
        if src.exists() and not dst.exists():
            out_of_sync.append(f"{dst_rel} (not created yet)")

    return {"out_of_sync": out_of_sync}


def main() -> None:
    parser = argparse.ArgumentParser(description="Xorial Sync")
    parser.add_argument("--project", required=True)
    parser.add_argument("--xorial-path", required=True)
    parser.add_argument("--check", action="store_true", help="Report only, do not apply")
    parser.add_argument("--auto", action="store_true", help="Startup mode: sync silently, print only if changes were made")
    args = parser.parse_args()

    xorial_dir = os.path.join(args.project, ".xorial")

    if args.check:
        status = _check_status(args.xorial_path, xorial_dir)
        if not status["out_of_sync"]:
            print("✓ Project is up to date with Xorial core.")
        else:
            print("Out of sync:")
            for item in status["out_of_sync"]:
                print(f"  ✗ {item}")
        sys.exit(0)

    updated_files = _sync_overwrite(args.xorial_path, xorial_dir)
    merged_arrays = _sync_array_merge(args.xorial_path, xorial_dir)
    added_keys = _sync_config(args.xorial_path, xorial_dir)
    bootstrapped = _sync_bootstrap(args.xorial_path, xorial_dir)

    total = len(updated_files) + len(merged_arrays) + len(added_keys) + len(bootstrapped)
    if total == 0:
        if not args.auto:
            print("✓ Project is up to date with Xorial core.")
        sys.exit(0)

    if args.auto:
        for label in updated_files:
            print(f"Xorial: synced {label}")
        for label in merged_arrays:
            if label.startswith("created "):
                print(f"Xorial: {label} — fill in required fields before running")
            else:
                print(f"Xorial: {label} (new plugin — fill in value if needed)")
        for label in added_keys:
            if label.startswith("created "):
                print(f"Xorial: {label} — fill in required fields before running")
            else:
                print(f"Xorial: {label} (new key — fill in value if needed)")
        for label in bootstrapped:
            print(f"Xorial: {label} — fill in project details")
    else:
        print(f"Synced {total} change(s):\n")
        for label in updated_files:
            print(f"  ✓ {label}  (template updated)")
        for label in merged_arrays:
            if label.startswith("created "):
                print(f"  ✓ {label}  — fill in required fields before running")
            else:
                print(f"  ✓ {label}  (new plugin added)")
        for label in added_keys:
            if label.startswith("created "):
                print(f"  ✓ {label}  — fill in required fields before running")
            else:
                print(f"  ✓ {label}  (new key — fill in value if needed)")
        for label in bootstrapped:
            print(f"  ✓ {label}  — fill in project details")
        print("\nDone.")


if __name__ == "__main__":
    main()
