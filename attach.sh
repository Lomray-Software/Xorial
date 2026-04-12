#!/usr/bin/env bash
# Xorial — new project setup
# Usage: ./attach.sh /path/to/your/project

set -euo pipefail

XORIAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$XORIAL_DIR/.venv"
REQUIREMENTS="$XORIAL_DIR/conductor/requirements.txt"

# ── Args ─────────────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/your/project"
  exit 1
fi

PROJECT_ROOT="$(cd "$1" && pwd)"
XORIAL_CONTEXT="$PROJECT_ROOT/.xorial/context"

echo ""
echo "Setting up Xorial for: $PROJECT_ROOT"
echo ""

# ── Ensure venv + dependencies ───────────────────────────────────────────────

if [ ! -d "$VENV" ]; then
  echo "Creating Xorial virtual environment..."
  python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import anthropic, openai, requests" 2>/dev/null; then
  echo "Installing Xorial conductor dependencies..."
  "$VENV/bin/pip" install -q -r "$REQUIREMENTS"
  echo "✓ Dependencies installed"
else
  echo "✓ Dependencies already installed"
fi
echo ""

# ── Directory structure ───────────────────────────────────────────────────────

mkdir -p "$PROJECT_ROOT/.xorial"
mkdir -p "$XORIAL_CONTEXT/work/feat"
mkdir -p "$XORIAL_CONTEXT/work/fix"
mkdir -p "$XORIAL_CONTEXT/work/refactor"
mkdir -p "$XORIAL_CONTEXT/work/chore"
mkdir -p "$XORIAL_CONTEXT/knowledge"
mkdir -p "$XORIAL_CONTEXT/coding-standards"
mkdir -p "$XORIAL_CONTEXT/skills"
mkdir -p "$XORIAL_CONTEXT/roles"

echo "✓ Created .xorial/ structure"

# ── Section index files (coding-standards, skills, roles) ────────────────────

for stub in "coding-standards/coding-standards.md" "skills/skills.md" "roles/roles.md"; do
  dst="$XORIAL_CONTEXT/$stub"
  src="$XORIAL_DIR/core/templates/${stub##*/}"
  if [ -f "$dst" ]; then
    echo "  $stub already exists — skipping"
  elif [ -f "$src" ]; then
    cp "$src" "$dst"
    echo "✓ Created .xorial/context/$stub"
  fi
done

# ── suggestions/ (Xorial-level, shared across all projects) ──────────────────

mkdir -p "$XORIAL_DIR/suggestions"
if [ ! -f "$XORIAL_DIR/suggestions/.gitkeep" ]; then
  touch "$XORIAL_DIR/suggestions/.gitkeep"
fi
echo "✓ Ensured suggestions/ directory"

# ── config.json ──────────────────────────────────────────────────────────────

CONFIG="$PROJECT_ROOT/.xorial/config.json"
if [ -f "$CONFIG" ]; then
  echo "  config.json already exists — skipping"
else
  sed "s|/absolute/path/to/Xorial|$XORIAL_DIR|g" \
    "$XORIAL_DIR/core/templates/config.json" > "$CONFIG"
  echo "✓ Created .xorial/config.json"
fi

# ── run.sh ────────────────────────────────────────────────────────────────────

RUN_SH="$PROJECT_ROOT/.xorial/run.sh"
if [ -f "$RUN_SH" ]; then
  echo "  run.sh already exists — skipping"
else
  cp "$XORIAL_DIR/core/templates/run.sh" "$RUN_SH"
  chmod +x "$RUN_SH"
  echo "✓ Created .xorial/run.sh"
fi

# ── pipeline.json ────────────────────────────────────────────────────────────

PIPELINE="$XORIAL_CONTEXT/pipeline.json"
if [ -f "$PIPELINE" ]; then
  echo "  pipeline.json already exists — skipping"
else
  cp "$XORIAL_DIR/core/templates/pipeline.json" "$PIPELINE"
  echo "✓ Created .xorial/context/pipeline.json"
fi

# ── .xorial/.gitignore ───────────────────────────────────────────────────────

XORIAL_GITIGNORE="$PROJECT_ROOT/.xorial/.gitignore"
if [ -f "$XORIAL_GITIGNORE" ]; then
  echo "  .xorial/.gitignore already exists — skipping"
else
  cp "$XORIAL_DIR/core/templates/xorial.gitignore" "$XORIAL_GITIGNORE"
  echo "✓ Created .xorial/.gitignore"
fi

# ── .obsidian/ ───────────────────────────────────────────────────────────────

OBSIDIAN_DEST="$XORIAL_CONTEXT/.obsidian"
OBSIDIAN_SRC="$XORIAL_DIR/core/templates/.obsidian"

if [ -d "$OBSIDIAN_DEST" ]; then
  echo "  .obsidian/ already exists — skipping"
else
  cp -r "$OBSIDIAN_SRC" "$OBSIDIAN_DEST"
  echo "✓ Created .xorial/context/.obsidian/ (Obsidian vault config)"
fi

# ── chat.md ───────────────────────────────────────────────────────────────────

CHAT_MD="$PROJECT_ROOT/.xorial/chat.md"
if [ -f "$CHAT_MD" ]; then
  echo "  chat.md already exists — skipping"
else
  cp "$XORIAL_DIR/core/templates/chat.md" "$CHAT_MD"
  echo "✓ Created .xorial/chat.md"
fi

# ── project-map.canvas ───────────────────────────────────────────────────────

PROJECT_MAP="$XORIAL_CONTEXT/project-map.canvas"
if [ -f "$PROJECT_MAP" ]; then
  echo "  project-map.canvas already exists — skipping"
else
  cp "$XORIAL_DIR/core/templates/project-map.canvas" "$PROJECT_MAP"
  echo "✓ Created .xorial/context/project-map.canvas"
fi

# ── project-context.md ────────────────────────────────────────────────────────

PC="$XORIAL_CONTEXT/project-context.md"
if [ -f "$PC" ]; then
  echo "  project-context.md already exists — skipping"
else
  cat > "$PC" << 'EOF'
# Project Context

This file is read by all Xorial agents. Fill in every section accurately.
Behavior Reviewer depends on this file for commands, paths, and helpers.

---

## Project Structure

<!-- Describe the main app directories, entry points, and key modules. -->
<!-- Example:
- `apps/mobile/` — React Native mobile app (Expo / bare RN)
- `apps/backend/` — NestJS API
- `apps/frontend/` — React SSR web app
-->

---

## Behavior Reviewer — Commands

### Build & run

```bash
# Start Metro bundler
# TODO: fill in

# Build and launch on simulator
# TODO: fill in

# Run Detox tests (no video)
# TODO: fill in
```

### Video recording

```bash
# Run Detox with video recording enabled (use only for FAIL/BLOCKED re-run)
# TODO: fill in
```

---

## Behavior Reviewer — E2E Test Paths

<!-- Paths relative to project root -->

| What | Path |
|------|------|
| E2E test files | `TODO` |
| Test helpers | `TODO` |
| Detox config | `TODO` |
| Test credentials | `TODO` |

---

## Behavior Reviewer — Project-Specific Helpers

<!-- Describe custom helpers available in E2E tests. -->
<!-- Example:
- `waitForElementVisible(id)` — waits up to 5s for a testID to appear
- `loginAs(role)` — logs in with preset credentials for a given role
-->

<!-- TODO: fill in -->
EOF
  echo "✓ Created .xorial/context/project-context.md"
fi

# ── knowledge/README.md ────────────────────────────────────────────────────────

KNOW_README="$XORIAL_CONTEXT/knowledge/README.md"
if [ -f "$KNOW_README" ]; then
  echo "  knowledge/README.md already exists — skipping"
else
  cat > "$KNOW_README" << 'EOF'
# Knowledge Base

Cross-feature knowledge discovered during feature work.

## Write only if ALL of the following are true

- **Non-obvious**: not derivable from reading the code or standard docs
- **Costly to discover**: required real investigation — multiple failed attempts, debugging sessions
- **Reusable across features**: not tied to one specific feature's logic
- **Future agents would likely hit the same issue**

## Do NOT write

- Standard patterns already in official documentation
- Things obvious from reading the codebase
- Knowledge specific to a single feature — put that in `work/{type}/{name}/` instead
- Temporary notes from a single run that won't repeat

## Rules

- **Add new files only** — do not rewrite existing ones
- **Deletion allowed**: remove outdated files, log every change in `CHANGELOG.md`
- **One topic per file**: kebab-case filename, e.g. `animation-timing.md`
- **Do NOT update this README** — it is rebuilt by the Orchestrator at finalization. Create topic files and log in `CHANGELOG.md`.
EOF
  echo "✓ Created .xorial/context/knowledge/README.md"
fi

# ── knowledge/CHANGELOG.md ────────────────────────────────────────────────────

KNOW_CHANGELOG="$XORIAL_CONTEXT/knowledge/CHANGELOG.md"
if [ ! -f "$KNOW_CHANGELOG" ]; then
  cat > "$KNOW_CHANGELOG" << 'EOF'
# Knowledge Base Changelog

Log of additions and deletions. Append a row for every change.

| Date | Action | File | Reason |
|------|--------|------|--------|
EOF
  echo "✓ Created .xorial/context/knowledge/CHANGELOG.md"
fi

# ── package.json scripts (Node projects only) ────────────────────────────────

PKG_JSON="$PROJECT_ROOT/package.json"
if [ -f "$PKG_JSON" ]; then
  "$VENV/bin/python" - "$PKG_JSON" << 'PYEOF'
import json, sys

path = sys.argv[1]
with open(path, "r") as f:
    pkg = json.load(f)

scripts = pkg.setdefault("scripts", {})
added = []

if "xorial" not in scripts:
    scripts["xorial"] = ".xorial/run.sh"
    added.append("xorial")

if "xorial:dry-run" not in scripts:
    scripts["xorial:dry-run"] = ".xorial/run.sh --dry-run"
    added.append("xorial:dry-run")

# Keep scripts sorted
pkg["scripts"] = dict(sorted(scripts.items()))

with open(path, "w") as f:
    json.dump(pkg, f, indent=4, ensure_ascii=False)
    f.write("\n")

if added:
    print(f"✓ Added scripts to package.json: {', '.join(added)}")
else:
    print("  package.json already has xorial scripts — skipping")
PYEOF
else
  echo "  No package.json found — skipping script injection"
fi

# ── .gitignore ────────────────────────────────────────────────────────────────

GITIGNORE="$PROJECT_ROOT/.gitignore"
IGNORE_LINES=".xorial/config.json
.xorial/agent.pid
.xorial/context/work/**/tmp/"

if [ -f "$GITIGNORE" ]; then
  ADDED=0
  while IFS= read -r line; do
    if ! grep -qF "$line" "$GITIGNORE"; then
      echo "$line" >> "$GITIGNORE"
      ADDED=1
    fi
  done <<< "$IGNORE_LINES"
  if [ "$ADDED" -eq 1 ]; then
    echo "✓ Updated .gitignore"
  else
    echo "  .gitignore already contains Xorial entries — skipping"
  fi
else
  echo "$IGNORE_LINES" > "$GITIGNORE"
  echo "✓ Created .gitignore"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "✓ Done. Next steps:"
echo ""
echo "  1. Fill in .xorial/config.json:"
echo "       instance_name      — name for this machine (e.g. \"MacBook Pro\")"
echo "       anthropic_api_key  — from console.anthropic.com"
echo "       openai_api_key     — from platform.openai.com (used for voice transcription)"
echo "       telegram_bot_token — from @BotFather"
echo "       telegram_chat_id   — your Telegram chat ID"
echo ""
echo "  2. Fill in .xorial/context/project-context.md:"
echo "       Project structure, commands, E2E paths, helpers"
echo ""
echo "  3. Start the conductor:"
echo "       cd $PROJECT_ROOT && ./.xorial/run.sh --dry-run   # verify"
echo "       cd $PROJECT_ROOT && ./.xorial/run.sh             # run"
echo ""
