# Conductor

The conductor is an automated daemon that drives the Xorial workflow without manual agent invocation.
It is not an AI agent — it is a Python process that watches `status.json` and spawns the right agent at the right time.

---

## What it does

1. Reads `.xorial/config.json` to get `xorial_path`, `telegram_bot_token`, `telegram_chat_id`.
2. Watches `status.json` in the given feature folder.
3. Maps `owner` + `status` to the next action using the routing table below.
4. Builds an agent prompt: reads the role file, pre-substitutes `{{xorial_core}}` and `{{project_context}}`.
5. Spawns the agent (Claude, Codex) and waits for it to finish.
6. When the agent writes a new `status.json`, the cycle repeats.
7. Sends Telegram notifications on: role handoffs, PASS, FAIL, BLOCKED, NEEDS_HUMAN_INPUT, DONE.
8. On NEEDS_HUMAN_INPUT: sends Telegram message and waits for human reply via bot before continuing.

---

## Routing table

| `owner`            | `status`                   | Action                                        |
|--------------------|----------------------------|-----------------------------------------------|
| `orchestrator`     | *(any)*                    | Spawn orchestrator (claude-opus-4-6)          |
| `critic`           | *(any)*                    | Spawn critic (claude-opus-4-6)                |
| `implementer`      | *(any)*                    | Spawn implementer (codex, high)               |
| `reviewer`         | *(any)*                    | Spawn reviewer (codex, high)                  |
| `behavior-reviewer`| *(any)*                    | Spawn behavior reviewer (codex, high)         |
| `human`            | `NEEDS_HUMAN_INPUT`        | Notify Telegram, pause, wait for `/resume`    |
| `human`            | `AWAITING_HUMAN_REVIEW` / *(other)*  | Notify Telegram, pause, wait for `/resume`    |
| `orchestrator`     | `DONE`                     | Notify Telegram (feature complete), stop      |

---

## Placeholder substitution

Before spawning any agent, the conductor pre-fills:
- `{{xorial_core}}` → `{xorial_path}/core`
- `{{project_context}}` → `{project_root}/.xorial/context`
- `{{feature_path}}` → absolute path to the feature folder

This means agents receive fully resolved paths. They do not need to self-resolve from `config.json`.

---

## Telegram integration

- On every role handoff: short message with feature name, new owner, status.
- On PASS: success message with feature name.
- On FAIL or BLOCKED: message + attach screenshots/videos from `tmp/run-NNN/`.
- On NEEDS_HUMAN_INPUT: message with `blocked_reason` from `status.json`. Bot waits.
- On human review needed (`owner: human`, not NEEDS_HUMAN_INPUT): message prompting human review. Bot waits.
- Human sends `/resume` to the bot to unblock and continue the loop.

---

## How to start

```bash
# From project root:
./.xorial/run.sh

# With dry-run:
./.xorial/run.sh --dry-run
```

Options:
- `--project <path>` — project root (default: current directory)
- `--dry-run` — print what would be spawned, don't actually spawn

Conductor watches **all** features in `{project_context}/work/` automatically (scanning `feat/`, `fix/`, `refactor/`, `chore/` subdirectories).
No need to specify a feature — it discovers them via filesystem polling.

Telegram commands:
- `/status` — status of all features
- `/list` — alias
- `/resume [feature]` — resume a paused feature (or all if no arg)

---

## Agent invocation

**Claude** (orchestrator, critic):
```bash
claude --model claude-opus-4-6 --print "<prompt>"
```

**Codex** (implementer, reviewer, behavior reviewer):
```bash
codex --model o3 --approval-mode full-auto "<prompt>"
```

The conductor captures exit codes and stdout. If an agent exits non-zero, it retries once, then sets `status: BLOCKED` and notifies Telegram.

---

## Prompt template

```
Take role: {xorial_core}/roles/{role_file}
Work on: {feature_path}/
Start your pass.
```

The conductor writes this into a temp file and passes it to the agent.

---

## Implementation

Source: `{xorial_path}/conductor/`

| File              | Purpose                                                   |
|-------------------|-----------------------------------------------------------|
| `main.py`         | CLI entry point, arg parsing, main loop                   |
| `config.py`       | Load `.xorial/config.json`, resolve paths                |
| `watcher.py`      | Poll `status.json`, detect changes                        |
| `router.py`       | Routing table: owner + status → action                    |
| `runner.py`       | Spawn agents, capture output, handle errors               |
| `prompts.py`      | Build prompts, substitute placeholders                    |
| `telegram.py`     | Send notifications, handle `/resume` command              |
| `requirements.txt`| Python dependencies                                       |
