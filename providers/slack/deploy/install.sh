#!/usr/bin/env bash
# One-shot installer for the Xorial Slack provider on macOS.
# Installs two launchd agents (auto git pull + supervised slack bot)
# and a post-merge git hook that links them.
#
# Idempotent — safe to re-run. Unloads an existing agent before
# reloading so edits to the templates take effect.
#
# Prereqs: see deploy/README.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XORIAL_ROOT="$(cd "$HERE/../../.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/work/logs"

echo "[install] xorial root: $XORIAL_ROOT"
echo "[install] logs dir:    $LOGS_DIR"

mkdir -p "$LAUNCH_DIR" "$LOGS_DIR"

render() {
  local tmpl="$1" out="$2"
  sed -e "s|__HOME__|$HOME|g" \
      -e "s|__XORIAL_ROOT__|$XORIAL_ROOT|g" \
      -e "s|__LOGS_DIR__|$LOGS_DIR|g" \
      "$tmpl" > "$out"
}

SYNC_PLIST="$LAUNCH_DIR/com.jani.xorial-sync.plist"
SLACK_PLIST="$LAUNCH_DIR/com.jani.xorial-slack.plist"

echo "[install] rendering launchd plists"
render "$HERE/xorial-sync.plist.template"  "$SYNC_PLIST"
render "$HERE/xorial-slack.plist.template" "$SLACK_PLIST"

echo "[install] installing post-merge git hook"
HOOK="$XORIAL_ROOT/.git/hooks/post-merge"
cp "$HERE/post-merge-hook" "$HOOK"
chmod +x "$HOOK"

echo "[install] (re)loading launchd agents"
launchctl unload "$SYNC_PLIST"  2>/dev/null || true
launchctl unload "$SLACK_PLIST" 2>/dev/null || true
launchctl load "$SYNC_PLIST"
launchctl load "$SLACK_PLIST"

echo
echo "[install] done. Verify with:"
echo "  launchctl list | grep xorial"
echo "  tail -f $LOGS_DIR/xorial-slack.stdout.log"
