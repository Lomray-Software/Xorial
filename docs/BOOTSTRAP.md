# BOOTSTRAP

Sole dev entry doc for the Xorial core repo. If you are a coding agent or
a new human developer, read this before touching anything.

## What this is

Xorial is an AI-driven software-delivery framework. It ships as a **core**
(this repo) that gets attached to downstream projects. A Python
**conductor** runs a role pipeline (intake → orchestrator → critic →
implementer → reviewer → behavior-reviewer) against feature folders.
**Providers** (currently Slack, scaffolded Telegram) let humans trigger
and steer the pipeline.

State lives in two places:

- **Core repo** (this one) — role prompts, coding standards, templates,
  conductor code, provider code. Versioned.
- **Downstream project** — per-project `.xorial/` tree: `context/work/{type}/{name}/`
  for each feature, plus `context/knowledge/`, `context/coding-standards/`,
  `context/pipeline.json`, `context/project-context.md`, Obsidian views
  (`kanban.md`, `project-map.canvas`, `.obsidian/**`). That state lives
  in the downstream repo, not here.

This repo is a normal human git repo. No live state to snapshot — it is
stateless library + templates + CLI + provider daemons.

## Read now (cold start, ≤6 files)

1. [`core/AI_IMPLEMENTATION_FLOW.md`](../core/AI_IMPLEMENTATION_FLOW.md)
   — pipeline, role list, status schema, write boundary, utility roles.
2. [`core/ROLES_COMMON_RULES.md`](../core/ROLES_COMMON_RULES.md) — rules
   injected into every role prompt.
3. [`providers/slack/handlers.py`](../providers/slack/handlers.py) —
   slash-command surface: every `/xorial <sub>` goes through
   `xorial_command`.
4. [`providers/slack/invoker.py`](../providers/slack/invoker.py) —
   `ROLE_FILES` dict mapping slash aliases to role markdown files, plus
   `_build_prompt` (how role prompts are assembled) and `CHAT_SYSTEM_PROMPT`.
5. [`providers/slack/runner.py`](../providers/slack/runner.py) —
   streamer, per-feature lock, auto-commit + push glue.
6. [`core/coding-standards/`](../core/coding-standards/) — engineering
   conventions that apply to every Xorial project.

## Read if touching X

| If you touch | Read |
|---|---|
| A pipeline role's behavior | `core/roles/<name>.md` + `core/ROLES_COMMON_RULES.md` |
| Adding / removing a role | `providers/slack/invoker.py` (ROLE_FILES), `core/AI_IMPLEMENTATION_FLOW.md` (Roles section), `core/roles/<name>.md` |
| Adding / removing a slash command | `providers/slack/handlers.py` (dispatch + `help_text()`), `core/AI_IMPLEMENTATION_FLOW.md` if it's user-facing |
| Git push / commit flow from a pass | `providers/slack/git_push.py` (safety invariants docstring — read before editing) |
| Role prompt format | `providers/slack/invoker.py` `_build_prompt` + the role file itself |
| `status.json` lifecycle | `core/AI_IMPLEMENTATION_FLOW.md` status.json schema, every role that writes exit markers |
| Coding-standards | `core/coding-standards/*.md` + `core/ROLES_COMMON_RULES.md` engineering section |
| Obsidian views (kanban / canvas / icons) | `core/roles/view-sync.md` + `AI_IMPLEMENTATION_FLOW.md` Write Boundary section. Don't let pipeline roles write these. |
| Template-sync to downstream projects | `conductor/sync_cli.py` (OVERWRITE / KEY_MERGE / ARRAY_MERGE / BOOTSTRAP lists) |
| Chat mode system prompt | `providers/slack/invoker.py` `CHAT_SYSTEM_PROMPT` |

## Hard rules

- Behavior change and its doc update ship in the **same patch**. If you
  can't update the doc yet, don't land the code yet.
- Run `./scripts/audit` before handing back. Non-zero exit = fix first.
- If you are an AI agent, re-read the **Runtime-persona files** rule in
  [`AGENTS.md`](../AGENTS.md). You edit role prompts; you do not follow
  them as your own instructions.

## One-time setup

To wire the audit into git commits locally:

```
./scripts/install-hooks
```

This points `core.hooksPath` at `.githooks/` so `pre-commit` runs
`scripts/audit --strict`. If you prefer not to install the hook, you
still run the audit manually before each handoff.

## Commit hygiene

See [`core/coding-standards/15-git-conventions.md`](../core/coding-standards/15-git-conventions.md).
TL;DR: Conventional Commits, branch name == feature folder name when
applicable, no AI-attribution trailers.
