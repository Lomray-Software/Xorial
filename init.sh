#!/usr/bin/env bash
# Eidolon — new project setup
# Usage: ./init.sh /path/to/your/project

set -euo pipefail

EIDOLON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Args ─────────────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/your/project"
  exit 1
fi

PROJECT_ROOT="$(cd "$1" && pwd)"
EIDOLON_CONTEXT="$PROJECT_ROOT/.eidolon/context"

echo ""
echo "Setting up Eidolon for: $PROJECT_ROOT"
echo ""

# ── Directory structure ───────────────────────────────────────────────────────

mkdir -p "$PROJECT_ROOT/.eidolon"
mkdir -p "$EIDOLON_CONTEXT/features"
mkdir -p "$EIDOLON_CONTEXT/knowledge"
mkdir -p "$EIDOLON_CONTEXT/rules"

echo "✓ Created .eidolon/ structure"

# ── config.json ──────────────────────────────────────────────────────────────

CONFIG="$PROJECT_ROOT/.eidolon/config.json"
if [ -f "$CONFIG" ]; then
  echo "  config.json already exists — skipping"
else
  sed "s|/absolute/path/to/Eidolon|$EIDOLON_DIR|g" \
    "$EIDOLON_DIR/core/templates/config.json" > "$CONFIG"
  echo "✓ Created .eidolon/config.json"
fi

# ── run.sh ────────────────────────────────────────────────────────────────────

RUN_SH="$PROJECT_ROOT/.eidolon/run.sh"
if [ -f "$RUN_SH" ]; then
  echo "  run.sh already exists — skipping"
else
  cp "$EIDOLON_DIR/core/templates/run.sh" "$RUN_SH"
  chmod +x "$RUN_SH"
  echo "✓ Created .eidolon/run.sh"
fi

# ── PROJECT_CONTEXT.md ────────────────────────────────────────────────────────

PC="$EIDOLON_CONTEXT/PROJECT_CONTEXT.md"
if [ -f "$PC" ]; then
  echo "  PROJECT_CONTEXT.md already exists — skipping"
else
  cat > "$PC" << 'EOF'
# Project Context

This file is read by all Eidolon agents. Fill in every section accurately.
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
  echo "✓ Created .eidolon/context/PROJECT_CONTEXT.md"
fi

# ── knowledge/README.md ────────────────────────────────────────────────────────

KNOW_README="$EIDOLON_CONTEXT/knowledge/README.md"
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
- Knowledge specific to a single feature — put that in `features/<name>/` instead
- Temporary notes from a single run that won't repeat

## Rules

- **Append-only**: add new files, do not rewrite existing ones
- **Deletion allowed**: remove outdated entries, log every deletion in `CHANGELOG.md`
- **One topic per file**: kebab-case filename, e.g. `animation-timing.md`

## Current files

| File | Topic |
|------|-------|
| [CHANGELOG.md](CHANGELOG.md) | Log of additions and deletions |
EOF
  echo "✓ Created .eidolon/context/knowledge/README.md"
fi

# ── knowledge/CHANGELOG.md ────────────────────────────────────────────────────

KNOW_CHANGELOG="$EIDOLON_CONTEXT/knowledge/CHANGELOG.md"
if [ ! -f "$KNOW_CHANGELOG" ]; then
  cat > "$KNOW_CHANGELOG" << 'EOF'
# Knowledge Base Changelog

Log of additions and deletions. Append a row for every change.

| Date | Action | File | Reason |
|------|--------|------|--------|
EOF
  echo "✓ Created .eidolon/context/knowledge/CHANGELOG.md"
fi

# ── .gitignore ────────────────────────────────────────────────────────────────

GITIGNORE="$PROJECT_ROOT/.gitignore"
IGNORE_LINES=".eidolon/config.json
.eidolon/context/features/**/tmp/"

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
    echo "  .gitignore already contains Eidolon entries — skipping"
  fi
else
  echo "$IGNORE_LINES" > "$GITIGNORE"
  echo "✓ Created .gitignore"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "✓ Done. Next steps:"
echo ""
echo "  1. Fill in .eidolon/config.json:"
echo "       instance_name   — name for this machine (e.g. \"MacBook Pro\")"
echo "       telegram_bot_token — from @BotFather"
echo "       telegram_chat_id   — your Telegram chat ID"
echo ""
echo "  2. Fill in .eidolon/context/PROJECT_CONTEXT.md:"
echo "       Project structure, commands, E2E paths, helpers"
echo ""
echo "  3. Install conductor dependencies:"
echo "       pip install -r $EIDOLON_DIR/conductor/requirements.txt"
echo ""
echo "  4. Start the conductor:"
echo "       cd $PROJECT_ROOT && ./.eidolon/run.sh"
echo ""
