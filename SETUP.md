# Setting up a new project with Xorial

## Prerequisites

Before starting, make sure you have:

| What | Why |
|------|-----|
| Python 3.11+ | Conductor runtime |
| `claude` CLI | Orchestrator, Critic, Intake roles |
| `codex` CLI | Implementer, Reviewer, Behavior Reviewer roles |
| Anthropic API key | Dispatcher + Intake (natural language, intake sessions) |
| OpenAI API key | Voice transcription (Whisper) |
| Telegram bot token + chat ID | Notifications and control |

Install conductor dependencies (once per machine):
```bash
pip install -r /path/to/Xorial/conductor/requirements.txt
```

---

## Quick setup (recommended)

```bash
/path/to/Xorial/attach.sh /path/to/your/project
```

Creates the full `.xorial/` structure, copies config and launch script, generates `project-context.md` and knowledge base stubs, updates `.gitignore`. Then fill in what it asks.

---

## Manual steps (if needed)

### 1. Create the Xorial folder in your project

```bash
mkdir -p .xorial/context/work/{feat,fix,refactor,chore}
mkdir -p .xorial/context/knowledge
mkdir -p .xorial/context/coding-standards
```

### 2. Create config.json from template

```bash
cp /path/to/Xorial/core/templates/config.json .xorial/config.json
```

Then edit `.xorial/config.json` and fill in:

**Required:**
- `xorial_path` — absolute path to your local Xorial folder
- `instance_name` — human-readable name for this machine (e.g. `"MacBook Pro"`, `"CI"`)
- `telegram_bot_token` — your Telegram bot token (from @BotFather)
- `telegram_chat_id` — your Telegram chat ID for this project

**API keys:**
- `anthropic_api_key` — Anthropic API key (for dispatcher, intake, and Claude agent API fallback)
- `openai_api_key` — OpenAI API key (for voice transcription and Codex agent API fallback)

**Limits & safety:**
- `max_auto_iterations` — max agent runs per feature before forcing a human review pause (default: `10`, set to `0` to disable)
- `hang_timeout_minutes` — minutes of log inactivity before killing a hung agent (default: `20`, set to `0` to disable)

**Usage limit fallbacks:**
- `api_key_fallback` — when `true` (default), retries with API key if subscription hits usage limit; `false` = subscription only
- `usage_limit_fallback_model` — model to retry with when usage limit is hit, per agent type; `false` = disabled. Example:
  ```json
  "usage_limit_fallback_model": {
    "claude": "claude-sonnet-4-5",
    "codex": "o4-mini"
  }
  ```

**Linear research tickets (optional):**
- `linear` — when `false` (default), Linear integration is disabled. To enable, replace with:
  ```json
  "linear": {
    "team_key": "XOR",
    "project_id": "optional-project-uuid",
    "label_prefix": "xorial"
  }
  ```
  Requires the Linear MCP server to be configured in your Claude Code setup (`.mcp.json` in the project, or a user-level MCP config). Only the orchestrator uses this — it creates non-blocking research tickets during planning passes, checks their resolution on subsequent passes, and folds answers back into the feature scope. It is **not** a full kanban sync; `status.json` and `kanban.md` remain the source of truth for pipeline state.

**Agent model overrides:**
- `agents` — override agent type, model, and reasoning per role; `false` = use built-in defaults.

  `"default"` applies to all roles. Per-role keys (`"orchestrator"`, `"implementer"`, etc.) override the default for that role. Any unset field falls back to the built-in default.

  Each entry supports: `"type"` (`"claude"` or `"codex"`), `"model"`, `"reasoning"` (`"low"`, `"medium"`, `"high"`, `"xhigh"` — Codex only).

  **Use only Claude everywhere:**
  ```json
  "agents": {
    "default": { "type": "claude", "model": "claude-opus-4-6" }
  }
  ```

  **Use only Codex everywhere:**
  ```json
  "agents": {
    "default": { "type": "codex", "reasoning": "high" }
  }
  ```

  **Mixed — Claude for planning, Codex for execution:**
  ```json
  "agents": {
    "default":            { "type": "claude", "model": "claude-opus-4-6" },
    "implementer":        { "type": "codex",  "reasoning": "xhigh" },
    "reviewer":           { "type": "codex",  "reasoning": "high" },
    "behavior-reviewer":  { "type": "codex",  "reasoning": "high" }
  }
  ```

### 3. Add to .gitignore

```
.xorial/config.json
.xorial/context/work/**/tmp/
```

### 4. Create project-context.md

Copy and fill in `.xorial/context/project-context.md` with:
- Project structure (app paths)
- Behavior reviewer commands
- E2E test paths
- Project-specific helpers

See `core/roles/50-behavior-reviewer.md` for what is expected.

### 5. Open the Obsidian vault

Xorial uses [Obsidian](https://obsidian.md) as its visual interface — a free desktop app for working with markdown vaults.

**Install Obsidian:** download from [obsidian.md](https://obsidian.md) and install.

**Open the vault:**
1. Launch Obsidian → **Open folder as vault**
2. Select `.xorial/context/` inside your project
3. Trust the vault when prompted

**Enable Community Plugins** (required once per vault):
Settings → Community plugins → Turn off Safe mode → Enable

**Install required plugins** — open each link in Obsidian or search by name in the Community plugins browser:

| Plugin | ID | Purpose |
|--------|----|---------|
| Dataview | `dataview` | Powers dashboard tables and queries |
| Kanban | `obsidian-kanban` | Kanban board view |
| Buttons | `buttons` | Navigation buttons in notes |
| Icon Folder | `obsidian-icon-folder` | File and folder icons |
| Omnisearch | `omnisearch` | Full-text search (`Cmd+Shift+O`) |
| Timeline | `obsidian-timeline` | History timeline view |
| Commander | `obsidian-commander` | Custom toolbar buttons |

After installing all plugins, open `dashboard.md` — this is your project home screen.

**Project map:** open `project-map.canvas` for a visual tree of all features and their artifacts.

### 7. (Optional) Add project-specific coding standards

Place additional coding standards in `.xorial/context/coding-standards/`.
They extend the base standards in `core/coding-standards/` — base standards are read first, project standards second.

### 8. Create the launch script

```bash
cp /path/to/Xorial/core/templates/run.sh .xorial/run.sh
chmod +x .xorial/run.sh
```

### 9. Start working

**Manual mode** — give agents this starting prompt:
```
Take role: {{xorial_core}}/roles/10-orchestrator.md
Work on: {{project_context}}/work/feat/<name>/
Start your pass.
```

The agent will resolve `{{xorial_core}}` and `{{project_context}}` from `.xorial/config.json` automatically.

**Automated mode** — run the conductor (watches all features, one command):
```bash
pip install -r /path/to/Xorial/conductor/requirements.txt
./.xorial/run.sh
# or with dry-run:
./.xorial/run.sh --dry-run
```

Telegram commands once running:
- `/status` — status of all features
- `/resume [feature]` — resume after human review
- `/list` — alias for /status
