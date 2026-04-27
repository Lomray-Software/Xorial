# Xorial Onboarding Playbook

**Audience:** an AI agent with file-edit and shell-execution tools (Claude Code, Codex CLI, Cursor agent, etc.).

**Trigger:** a developer has cloned Xorial Core and asks their AI to "onboard me", "connect me to my project", "set this up", or equivalent.

**Goal:** leave the developer with a configured `.xorial/` folder inside their project so they can run agents **manually** (via `chat.md` or a direct role prompt). The automated conductor and Slack/Telegram providers are out of scope here — manual mode only.

Execute the steps below in order. Do not skip. Ask the user only when a value must come from them (a path, a yes/no). Never guess.

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

Remember the scenario — step 5 depends on it.

## 3. Run attach.sh

```bash
./attach.sh <project-path>
```

Report the script's summary output to the user. If it fails, stop and show the error.

`attach.sh` is idempotent: existing files are preserved, only missing ones are created. For `scenario = second-dev`, this will essentially only create `.xorial/config.json` (which is gitignored).

## 4. Fill config.json

Read `<project>/.xorial/config.json`. The template has many fields, **but only two are required for manual mode** — fill those and leave the rest as-is. They drive the conductor and Slack/Telegram providers, which are not part of this onboarding.

**Required: `instance_name`**

> "`instance_name` identifies **who is using Xorial on this machine**. Two jobs:
>   1. Written into every feature history entry as the author of that pass.
>   2. Read by the chat agent (via `chat.md`) to know **who it is talking to** — so when you say things like 'these are edits from Misha' or 'Ian wanted this refactored', the agent knows those are third parties, not you.
>
> **Prefer a personal name or name + machine** (e.g. `Mikhail`, `Misha MBP`, `ian-linux`) over a pure machine label — the agent uses the personal part to address you."

Ask, with the detected hostname as a fallback suggestion:

> "Detected hostname: `<hostname>`. Use it, or type the name you want recorded in history and used by the chat agent:"

**Required: `xorial_path`**

`attach.sh` already filled this with the absolute path to the Xorial Core repo. Verify the value is a real directory containing `core/roles/`. If not — fix it; if yes — leave it.

**Everything else** (`anthropic_api_key`, `openai_api_key`, `telegram_bot_token`, `telegram_chat_id`, `linear`, etc.) — **leave at template defaults**. Tell the user:

> "Other fields in `config.json` are for the automated conductor and Slack/Telegram bots, which we're not setting up here. Leave them as-is. If you decide to wire those up later, see `SETUP.md`."

Do not write secrets to any file.

## 5. Project-context

- If `scenario = second-dev` → skip this step entirely. The file is already filled and committed by a teammate.
- If `scenario = first-time` or `first-time-partial` → project-context.md has TODOs that agents need. Offer:

  > "Your `project-context.md` has empty sections (project structure, behavior-reviewer commands, E2E paths). I can analyze the project and draft these sections now. Proceed? [Y/n]"

  If yes: glob the project, detect stack (React Native / NestJS / Next.js / Expo / monorepo layout), draft the sections based on what you find, write them into `project-context.md`. Mark anything uncertain with `<!-- VERIFY: ... -->` comments the user can review.

  If no: leave the file with its TODOs and tell the user "fill these before running agents — they depend on this file".

## 6. Summary to user

Print a short summary:

- Config file: `<project>/.xorial/config.json`
- Project context: `<project>/.xorial/context/project-context.md`
- **How to run a role manually** — open any AI agent (Claude Code, Codex CLI, Cursor) inside `<project>` and paste one of:

  **Plan a new feature** (intake will interview you and create the feature folder):
  ```
  Take role: <xorial_path>/core/roles/05-intake.md
  Project context: <project>/.xorial/context/project-context.md
  Start your pass.
  ```

  **Work on an existing feature** (orchestrator):
  ```
  Take role: <xorial_path>/core/roles/10-orchestrator.md
  Work on: <project>/.xorial/context/work/feat/<name>/
  Start your pass.
  ```

  **Or — easiest** — paste this single line and let `chat.md` route you:
  ```
  Read <project>/.xorial/chat.md and follow it.
  ```

- Obsidian vault (optional, for visual overview): open `<project>/.xorial/context/` as a vault. Required plugins listed in `SETUP.md` section "Open the Obsidian vault".
- Full docs: `README.md` and `SETUP.md` in the Xorial Core repo.

Tell the user explicitly: **the automated conductor (`./.xorial/run.sh`) and Slack/Telegram bots are not set up here.** This onboarding leaves them in manual mode only.

---

## Guardrails

- **Do not run `./.xorial/run.sh`** as part of this onboarding (not even `--dry-run`). Conductor is out of scope.
- **Never write a secret (API key, token) to any file.** This onboarding does not collect secrets.
- **Do not run `git add`, `git commit`, or any git write command** in either repo. Onboarding is local-only; committing is the user's call.
- **Do not modify files outside `<project>/.xorial/`** except for `<project>/.xorial/context/project-context.md` in step 5, and only with user consent.
- **If a pasted value looks wrong** (path doesn't exist, hostname empty) — warn and re-ask before writing.
- **If the user is already half-onboarded** (config.json has some real values, some placeholders) — only fill the placeholders. Do not overwrite real values.
