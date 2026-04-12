# Xorial Conductor

Python daemon that drives the Xorial workflow automatically.

## Prerequisites

- Python 3.11+
- `claude` CLI — for Orchestrator, Critic, Intake roles
- `codex` CLI — for Implementer, Reviewer, Behavior Reviewer roles

## Setup

```bash
pip install -r requirements.txt
```

Fill in `.xorial/config.json`:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "openai_api_key":    "sk-..."
}
```

- `anthropic_api_key` — used by Dispatcher and Intake (Claude API)
- `openai_api_key` — used for voice transcription (Whisper)

## Run

```bash
# From project root (recommended):
./.xorial/run.sh

# Or directly:
python /path/to/Xorial/conductor/main.py --project /path/to/project
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--project` | cwd | Project root path |
| `--dry-run` | false | Print actions without spawning agents |

## Telegram commands

| Command | Description |
|---------|-------------|
| `/status` | Status of all watched features |
| `/list` | Alias for /status |
| `/resume [feature]` | Resume paused feature (or all if no arg) |

## How it works

1. Reads `.xorial/config.json` from the project root.
2. Watches `status.json` in the feature folder (polls every 10 seconds).
3. Routes to the right agent based on `owner` field.
4. Pre-substitutes `{{xorial_core}}` and `{{project_context}}` in prompts — agents receive resolved paths directly.
5. Sends Telegram notifications on every handoff, PASS, FAIL, BLOCKED, NEEDS_HUMAN_INPUT.
6. Pauses and waits for `/resume` from Telegram when human action is required.

## Telegram setup

Fill in `.xorial/config.json`:
```json
{
  "xorial_path": "/absolute/path/to/Xorial",
  "telegram_bot_token": "your-bot-token",
  "telegram_chat_id": "your-chat-id"
}
```

If token/chat_id are empty, notifications are printed to stdout and pauses require keyboard ENTER.

## Agent CLIs required

- `claude` — Claude Code CLI (for orchestrator, critic)
- `codex` — OpenAI Codex CLI (for implementer, reviewer, behavior-reviewer)
