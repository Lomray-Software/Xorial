# Xorial Onboarding Playbook

**Audience:** an AI agent with file-edit and shell-execution tools (Claude Code, Codex CLI, Cursor agent, etc.).

**Trigger:** a developer has cloned Xorial Core and asks their AI to "onboard me", "connect me to my project", "set this up", or equivalent.

**Goal:** leave the developer with a fully configured `.xorial/` folder inside their project and a working `./.xorial/run.sh --dry-run`. Zero manual steps — you do all the work.

Execute the steps below in order. Do not skip. Ask the user only when a value must come from them (a path, a secret, a yes/no). Never guess secrets.

---

## 0. Locate yourself

- Verify you can see `attach.sh`, `README.md`, `SETUP.md`, and `core/` in your current working directory.
- If not, ask the user for the absolute path to the Xorial Core repository and `cd` there before continuing.
- Verify prerequisites: `python3 --version` (need 3.11+), `git --version`. If any is missing, stop and tell the user.

## 1. Ask for the project path

Ask exactly one question:

> "What's the absolute path to the project you want to connect to Xorial?"

Validate: the path exists, is a directory, and is a git repository (`git -C <path> rev-parse` succeeds). If not, re-prompt.

## 2. Detect scenario

Look at `<project>/.xorial/context/project-context.md`:

- **File does not exist** → `scenario = first-time` (Xorial has never been attached to this project).
- **File exists and contains the literal string `TODO: fill in`** → `scenario = first-time-partial` (attach.sh was run before but project-context was never filled).
- **File exists and contains no `TODO: fill in` markers** → `scenario = second-dev` (teammate already configured Xorial for this project; you only need config.json).

Remember the scenario — step 6 depends on it.

## 3. Run attach.sh

```bash
./attach.sh <project-path>
```

Report the script's summary output to the user. If it fails, stop and show the error.

`attach.sh` is idempotent: existing files are preserved, only missing ones are created. For `scenario = second-dev`, this will essentially only create `.xorial/config.json` (which is gitignored).

## 4. Fill config.json

Read `<project>/.xorial/config.json`. For every field still at a placeholder value — `"your-..."`, `"/absolute/path/to/..."`, `"MacBook Pro"` (literal template value), or similar — collect the real value.

**Skip semantics.** For every optional field, the user may type `skip`. On skip, write an empty string (`""`) for that field and tell the user which Xorial feature is now disabled. Do not silently leave the placeholder — placeholders look like real values and will cause cryptic errors later.

Ask questions in **grouped batches**, not one by one. For each group, first explain **what the value is for** and **what breaks if you skip it**, then ask.

---

**Group A — machine identity (required)**

> "`instance_name` is a human-readable label written into feature history entries, so when you look back at a feature you can tell which developer or machine did a given pass. It's required because history entries need an author. Detected hostname: `<hostname>` — press enter to use it, or type a custom name (e.g. 'Mikhail MBP', 'CI-runner')."

No skip option here — if user insists on skipping, fall back to `<hostname>`.

---

**Group B — AI provider API keys**

> "Two API keys. Both are optional depending on how you plan to use Xorial.
>
> **1. Anthropic API key** — used by:
>   - the dispatcher that turns your Telegram messages into conductor commands
>   - the intake agent that interviews you in natural language when you start a new feature
>   - fallback to the direct API if your Claude Code subscription hits a usage limit mid-run
>
>   Skip if: you'll only launch agents manually via `claude` CLI, never use Telegram, and are fine with a run stopping when your subscription limit is hit. Get it at https://console.anthropic.com/settings/keys. Paste key or `skip`:
>
> **2. OpenAI API key** — used by:
>   - Whisper voice transcription (if you send voice messages to the Telegram bot)
>   - fallback to the direct API for Codex-based agents (implementer, reviewer) if your Codex subscription hits a usage limit
>
>   Skip if: you don't send voice commands and don't use Codex agents (or accept that a subscription limit stops the run). Get it at https://platform.openai.com/api-keys. Paste key or `skip`:"

After skipping, say: "Skipped — voice commands and Codex API fallback disabled" (or whatever applies).

---

**Group C — Telegram (optional)**

> "Telegram is used for:
>   - **notifications** — agent finished a pass, needs human review, hit a blocker, asked a question (NEEDS_HUMAN_INPUT)
>   - **remote control** — commands like `/status`, `/new feat auth-fix`, `/resume`, and voice messages to start/steer features
>
> Without Telegram, the conductor still runs — you just manage it from the machine (editing `human-input.md`, reading `status.json`). For remote/async workflow Telegram is the main interface.
>
> Skip both fields if you don't want Telegram. Otherwise:
>   1. **Bot token** — create a bot with @BotFather in Telegram, paste the token it gives you (or `skip`)
>   2. **Chat ID** — your personal chat ID. Easiest way: message @userinfobot, it replies with your numeric ID. Paste it (or `skip`)."

If user skips one of the two but not the other — warn: "Telegram needs both values to work. Skipping one effectively disables it." Then ask if they want to skip the other too.

---

After collecting, write the values into `<project>/.xorial/config.json`. Preserve the existing JSON structure — only change placeholder values. Skipped fields become empty strings (`""`). Do not echo collected secrets back to the user.

## 5. Optional: Linear block

Explain first, then ask:

> "Linear integration is a **side-channel for the orchestrator only**. During planning passes, the orchestrator may offload non-blocking research questions into Linear tickets (e.g. 'confirm rate limits of API X', 'ask designer about empty state'). On the next pass it checks whether those tickets have been answered and folds the answer back into the feature spec. It is **not** a kanban sync — `status.json` and `kanban.md` remain the source of truth for pipeline state.
>
> Skip if: you don't use Linear, or you prefer to keep all research questions inside Xorial (`NEEDS_HUMAN_INPUT` + `decisions.md`). Nothing breaks — the orchestrator just won't touch Linear.
>
> Enable? [y/N]"

If `y`:

> "Two values:
> 1. **Team key** — the prefix of Linear issue IDs, e.g. `XOR`, `ENG`, `API`
> 2. **Project UUID** — optional, press enter to skip"

Replace `"linear": false` in config.json with:
```json
"linear": {
  "team_key": "<value>",
  "project_id": "<value-or-null>",
  "label_prefix": "xorial"
}
```

Then tell the user:

> "Linear config saved. One more thing: the Linear MCP server must be registered in your Claude Code setup. If you use Claude Code, add this to `<project>/.mcp.json` (or `~/.claude.json` globally):
> ```json
> { "mcpServers": { "linear": { "command": "npx", "args": ["-y", "mcp-remote", "https://mcp.linear.app/sse"] } } }
> ```
> First run opens a browser for OAuth."

If user says no — leave `"linear": false` as-is.

## 6. Project-context

- If `scenario = second-dev` → skip this step entirely. The file is already filled and committed by a teammate.
- If `scenario = first-time` or `first-time-partial` → project-context.md has TODOs that agents need. Offer:

  > "Your project-context.md has empty sections (project structure, behavior-reviewer commands, E2E paths). I can analyze the project and draft these sections now. Proceed? [Y/n]"

  If yes: glob the project, detect stack (React Native / NestJS / Next.js / Expo / monorepo layout), draft the sections based on what you find, write them into `project-context.md`. Mark anything uncertain with `<!-- VERIFY: ... -->` comments the user can review.

  If no: leave the file with its TODOs and tell the user "fill these before running the conductor — agents depend on them".

## 7. Verify

```bash
cd <project-path> && ./.xorial/run.sh --dry-run
```

- Exits cleanly → report "Setup verified."
- Fails → show the error, help diagnose. Common causes: missing API key the user marked `skip`, python venv issue, missing `project-context.md` content.

## 8. Summary to user

Print a short summary:

- Config file: `<project>/.xorial/config.json`
- To start the conductor: `cd <project> && ./.xorial/run.sh` (or `npm run xorial` if it's a Node project)
- Obsidian vault: open `<project>/.xorial/context/` as a vault. Required plugins listed in `SETUP.md` section "Open the Obsidian vault".
- Telegram commands once running: `/status`, `/new <type> <name>`, `/resume [feature]`
- Full docs: `README.md` and `SETUP.md` in the Xorial Core repo.

---

## Guardrails

- **Never write a secret (API key, token) to any file other than `<project>/.xorial/config.json`.** Do not put it in `.md`, `.sh`, commit messages, or chat history files.
- **Never echo collected secrets back to the user after writing.** Confirm with "saved" — nothing more.
- **Do not run `git add`, `git commit`, or any git write command** in either repo. Onboarding is local-only; committing is the user's call.
- **Do not modify files outside `<project>/.xorial/`** except for `<project>/.xorial/context/project-context.md` in step 6, and only with user consent.
- **If a pasted value looks wrong** (API key too short, chat ID not numeric, path doesn't exist) — warn and re-ask before writing.
- **If the user is already half-onboarded** (config.json has some real values, some placeholders) — only fill the placeholders. Do not overwrite real values.
