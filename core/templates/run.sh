#!/usr/bin/env bash
# Xorial Conductor — project launch script
# Run from project root: ./.xorial/run.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$SCRIPT_DIR/config.json"

if [ ! -f "$CONFIG" ]; then
  echo ""
  echo "Welcome to Xorial!"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "No config found. Creating .xorial/config.json from template..."
  echo ""

  # Find Xorial — check common locations
  XORIAL_GUESS=""
  for candidate in \
    "$HOME/Xorial" \
    "$HOME/work/AI/Xorial" \
    "$HOME/projects/Xorial" \
    "$(dirname "$SCRIPT_DIR")/Xorial" \
    "$(dirname "$SCRIPT_DIR")/../Xorial"
  do
    if [ -f "$candidate/conductor/main.py" ]; then
      XORIAL_GUESS="$candidate"
      break
    fi
  done

  if [ -n "$XORIAL_GUESS" ]; then
    TEMPLATE_CONFIG="$XORIAL_GUESS/core/templates/config.json"
    cp "$TEMPLATE_CONFIG" "$CONFIG"
    # Pre-fill xorial_path with the detected path
    python3 -c "
import json, sys
with open('$CONFIG') as f: c = json.load(f)
c['xorial_path'] = '$XORIAL_GUESS'
c['instance_name'] = '$(whoami)'
with open('$CONFIG', 'w') as f: json.dump(c, f, indent=2)
"
    echo "✓ Created: .xorial/config.json"
    echo "  xorial_path auto-detected: $XORIAL_GUESS"
    echo ""
    echo "Fill in the remaining fields:"
    echo "  anthropic_api_key   — get from console.anthropic.com"
    echo "  telegram_bot_token  — optional, for notifications"
    echo "  telegram_chat_id    — optional, for notifications"
    echo ""
    echo "Then run: ./.xorial/run.sh"
  else
    # Can't find Xorial — copy template with placeholder and tell user
    # Try to find Xorial template relative to script or from a sibling directory
    FOUND_TEMPLATE=""
    for t in \
      "$SCRIPT_DIR/../core/templates/config.json" \
      "$HOME/Xorial/core/templates/config.json"
    do
      if [ -f "$t" ]; then
        FOUND_TEMPLATE="$t"
        break
      fi
    done

    if [ -n "$FOUND_TEMPLATE" ]; then
      cp "$FOUND_TEMPLATE" "$CONFIG"
    else
      # Write minimal config inline
      cat > "$CONFIG" <<'JSON'
{
  "xorial_path": "/absolute/path/to/Xorial",
  "instance_name": "local",
  "anthropic_api_key": "",
  "openai_api_key": "",
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "max_auto_iterations": 10,
  "hang_timeout_minutes": 20,
  "api_key_fallback": true,
  "usage_limit_fallback_model": false,
  "agents": false
}
JSON
    fi

    echo "✓ Created: .xorial/config.json"
    echo ""
    echo "Fill in these required fields:"
    echo "  xorial_path         — absolute path to your Xorial installation"
    echo "  anthropic_api_key   — get from console.anthropic.com"
    echo "  telegram_bot_token  — optional, for notifications"
    echo "  telegram_chat_id    — optional, for notifications"
    echo ""
    echo "Then run: ./.xorial/run.sh"
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
fi

XORIAL_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['xorial_path'])")
CONDUCTOR="$XORIAL_PATH/conductor/main.py"
REQUIREMENTS="$XORIAL_PATH/conductor/requirements.txt"
VENV="$XORIAL_PATH/.venv"
TEMPLATE="$XORIAL_PATH/core/templates/run.sh"

if [ ! -f "$CONDUCTOR" ]; then
  echo "Error: conductor not found at $CONDUCTOR" >&2
  exit 1
fi

# ── Auto-sync: update run.sh if Xorial template has changed ─────────────────

if [ -f "$TEMPLATE" ] && ! cmp -s "$TEMPLATE" "$SCRIPT_DIR/run.sh"; then
  echo "Xorial: run.sh is out of sync with core — updating..."
  cp "$TEMPLATE" "$SCRIPT_DIR/run.sh"
  chmod +x "$SCRIPT_DIR/run.sh"
  echo "Xorial: Updated. Restarting..."
  exec "$SCRIPT_DIR/run.sh" "$@"
fi

# ── Auto-sync: sync project files with Xorial core ───────────────────────────

python3 "$XORIAL_PATH/conductor/sync_cli.py" \
  --project "$PROJECT_ROOT" \
  --xorial-path "$XORIAL_PATH" \
  --auto

# ── Ensure venv exists ────────────────────────────────────────────────────────

if [ ! -d "$VENV" ]; then
  echo "Creating Xorial virtual environment..."
  python3 -m venv "$VENV"
fi

# ── Auto-install dependencies if missing ─────────────────────────────────────

if ! "$VENV/bin/python" -c "import anthropic, openai, requests" 2>/dev/null; then
  echo "Installing Xorial conductor dependencies..."
  "$VENV/bin/pip" install -q -r "$REQUIREMENTS"
  echo "Done."
fi

# ── Subcommands ───────────────────────────────────────────────────────────────

if [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo ""
  echo "Xorial Conductor"
  echo ""
  echo "Usage: ./.xorial/run.sh [command] [options]"
  echo ""
  echo "Commands:"
  echo "  (none)              Start the conductor daemon"
  echo "  --dry-run           Start in dry-run mode (no agents spawned)"
  echo ""
  echo "  skills install <source>   Install a skill or skill pack"
  echo "  skills list               List active skills"
  echo "  skills remove <name>      Remove a skill"
  echo "  skills update             Re-download remotely installed skills"
  echo ""
  echo "  roles new <name>          Scaffold a new custom role"
  echo "  roles install <source>    Install a role or role pack"
  echo "  roles list                List custom roles"
  echo "  roles remove <name>       Remove a custom role"
  echo "  roles update              Re-download remotely installed roles"
  echo ""
  echo "  sync                      Sync project files with Xorial core"
  echo ""
  echo "  logs [feature]            Stream the latest agent log (tail -f)"
  echo "                            With no arg — most recent log across all features"
  echo ""
  echo "  help                      Show this help"
  echo ""
  echo "Sources (for skills/roles install):"
  echo "  https://raw.githubusercontent.com/...   raw URL to a .md file"
  echo "  github:user/repo                         full pack from GitHub repo"
  echo "  github:user/repo/path/to/file.md         single file from GitHub"
  echo ""
  exit 0
fi

if [ "${1:-}" = "skills" ]; then
  shift
  exec "$VENV/bin/python" "$XORIAL_PATH/conductor/skills_cli.py" \
    --project "$PROJECT_ROOT" \
    --xorial-core "$XORIAL_PATH/core" \
    "$@"
fi

if [ "${1:-}" = "roles" ]; then
  shift
  exec "$VENV/bin/python" "$XORIAL_PATH/conductor/roles_cli.py" \
    --project "$PROJECT_ROOT" \
    "$@"
fi

if [ "${1:-}" = "sync" ]; then
  exec "$VENV/bin/python" "$XORIAL_PATH/conductor/sync_cli.py" \
    --project "$PROJECT_ROOT" \
    --xorial-path "$XORIAL_PATH"
fi

if [ "${1:-}" = "logs" ]; then
  WORK_DIR="$PROJECT_ROOT/.xorial/context/work"
  FEATURE="${2:-}"
  if [ -n "$FEATURE" ]; then
    # FEATURE is "type/name", e.g. "feat/k-id"
    SEARCH_DIR="$WORK_DIR/$FEATURE/tmp/agent-runs"
  else
    SEARCH_DIR="$WORK_DIR"
  fi

  _latest_log() {
    find "$SEARCH_DIR" -name "*.log" -type f 2>/dev/null \
      | xargs ls -t 2>/dev/null \
      | head -1 || true
  }

  CURRENT_LOG=""
  TAIL_PID=""

  _cleanup() {
    [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null
    exit 0
  }
  trap _cleanup INT TERM

  echo "Watching agent logs${FEATURE:+ for $FEATURE}… (Ctrl+C to stop)"

  while true; do
    LATEST=$(_latest_log)
    if [ -n "$LATEST" ] && [ "$LATEST" != "$CURRENT_LOG" ]; then
      [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null
      CURRENT_LOG="$LATEST"
      echo ""
      echo "▶ $CURRENT_LOG"
      echo "────────────────────────────────────────────────────────"
      tail -f "$CURRENT_LOG" &
      TAIL_PID=$!
    fi
    sleep 5
  done
fi

# ── Launch ────────────────────────────────────────────────────────────────────

exec "$VENV/bin/python" "$CONDUCTOR" --project "$PROJECT_ROOT" "$@"
