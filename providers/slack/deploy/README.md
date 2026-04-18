# Slack provider deployment (macOS launchd)

One-shot setup for the machine hosting the Xorial Slack bot. Covers
both the auto-`git pull` loop and the bot process itself, with a
clean restart pipeline so `git pull`-ing new provider code rolls the
bot without dropping an in-flight pass.

## What gets installed

| Piece | Where | Purpose |
|-------|-------|---------|
| `com.jani.xorial-sync` launchd agent | `~/Library/LaunchAgents/` | Runs `git pull` every 60s in `~/work/Xorial`. |
| `com.jani.xorial-slack` launchd agent | `~/Library/LaunchAgents/` | Keeps `providers/slack/run.sh` alive (`KeepAlive=true`). |
| `post-merge` git hook | `<xorial>/.git/hooks/post-merge` | On every pull that touches `providers/slack/`, writes a flag file. |
| `restart_watcher.py` (in-process) | already in the repo | Polls the flag every 15s; self-exits when idle so launchd respawns with fresh code. |

Net effect: push new provider code → mac-jani pulls within 60s →
hook sets the flag → bot self-exits at the next idle moment → launchd
respawns with fresh code. Never mid-pass.

## Prerequisites

1. `~/work/Xorial` — this repo, cloned with a writable `origin` remote
   (git push works without prompts; typically via SSH key).
2. Target project clones under `~/work/` (e.g. `~/work/monojai-xorial`).
3. `providers/slack/config.json`, `projects.json`, `workspaces.json`
   filled in per `providers/slack/README.md` and `SLACK_APP_SETUP.md`.
4. Homebrew Python 3.10+ — `brew install python@3.12` (or newer).
   Apple's system Python is 3.9 and `claude-agent-sdk` refuses it.
5. Claude Code CLI installed and authenticated
   (`ANTHROPIC_API_KEY` in `config.json`).

## Install

```bash
./providers/slack/deploy/install.sh
```

Idempotent. Renders templates with your `$HOME` and the absolute
Xorial path, unloads any previous agents, writes the hook, loads both
launchd agents.

## Verify

```bash
launchctl list | grep xorial
# expect two lines:
#   -      0   com.jani.xorial-sync
#   <pid>  0   com.jani.xorial-slack

tail -f ~/work/logs/xorial-slack.stdout.log
# should show: "⚡️ Bolt app is running!"
```

Then in Slack: `/xorial help` → gets the command list. Done.

## Uninstall

```bash
./providers/slack/deploy/uninstall.sh
```

Removes both launchd agents. Leaves git hook, config files, and logs
for manual cleanup.

## Rebuilding on a fresh Mac

1. Install Homebrew, then `brew install python@3.12 git`.
2. Install Claude Code CLI (see claude-agent-sdk docs).
3. Set up SSH key with GitHub access to this repo + target projects.
4. Clone:
   ```bash
   mkdir -p ~/work && cd ~/work
   git clone git@github.com:Lomray-Software/Xorial.git
   git clone git@github.com:janitorai/monojai.git monojai-xorial
   ```
5. Fill Slack provider configs:
   ```bash
   cd ~/work/Xorial/providers/slack
   cp config.example.json config.json      # edit: tokens + API key + projects_dir
   cp projects.example.json projects.json  # edit: project entries
   cp workspaces.example.json workspaces.json  # edit: team_id -> project
   chmod 600 config.json
   ```
6. Run the installer:
   ```bash
   ~/work/Xorial/providers/slack/deploy/install.sh
   ```

That's everything. An AI agent with shell access can do steps 4-6
unattended if tokens and SSH access are already set up.

## Troubleshooting

- **`launchctl list | grep xorial` shows exit code non-zero**  
  Bot is crash-looping. Read `~/work/logs/xorial-slack.stderr.log`.
  Common cause: stale `config.json` or `projects.json` — the `[config error]`
  block points at the exact problem.

- **Pushed new code but bot still runs old version**  
  Check `~/work/logs/xorial-sync.last` (unix timestamp of last
  successful pull). If stale, `xorial-sync` is broken; inspect
  `~/work/logs/xorial-sync.log`. Otherwise check
  `ls /tmp/xorial-slack.restart-pending` — if present and bot is
  idle, watcher should have picked it up within 15s. If it keeps
  re-appearing, something is wedged; `pkill -f providers.slack.main`
  to force respawn.

- **Hook didn't fire on pull**  
  Confirm `<xorial>/.git/hooks/post-merge` exists and is executable.
  Note: hooks only run on standard `git pull` / `git merge`, not on
  `git fetch + reset --hard`. The xorial-sync agent uses `git pull`.
