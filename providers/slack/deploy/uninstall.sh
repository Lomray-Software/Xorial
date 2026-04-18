#!/usr/bin/env bash
# Tear down the launchd agents installed by install.sh.
# Leaves config.json / projects.json / workspaces.json untouched.
set -u

LAUNCH_DIR="$HOME/Library/LaunchAgents"

for plist in com.jani.xorial-sync.plist com.jani.xorial-slack.plist; do
  f="$LAUNCH_DIR/$plist"
  launchctl unload "$f" 2>/dev/null || true
  rm -f "$f"
done

echo "launchd agents removed. Git hook left in place; delete manually if wanted:"
echo "  rm <xorial>/.git/hooks/post-merge"
