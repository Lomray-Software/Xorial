# Xorial

**You no longer write features. You direct them.**

Xorial runs the complete software delivery cycle — planning, critique, implementation, code review, and behavior validation — through a coordinated team of AI agents. Each agent reads the current state, does its job, and hands off to the next.

You define the vision. You approve the key decisions. Everything else is executed for you.

**No chat history. No lost context. No repeated explanations.**  
Files hold the truth. Agents are interchangeable workers that pick up exactly where the last one left off.

---

Designed for the AI era: stay focused on architecture and observation, delegate execution to agents.

---

## What it does

Xorial drives a feature from raw idea to shipped code through a sequence of AI agent roles:

```
Intake → Orchestrator → Critic → Orchestrator → Implementer → Reviewer → Human → Orchestrator (done)
```

Each role reads the feature folder, does its job, writes output files, updates `status.json`, and hands off.  
The **Conductor** (automated mode) watches `status.json` and spawns the right agent automatically.

---

## Directory map

```
Xorial/
  README.md                      ← you are here
  SETUP.md                       ← how to connect a new project
  attach.sh                      ← one-command project setup
  core/
    AI_IMPLEMENTATION_FLOW.md    ← full workflow spec, status.json schema, roles overview
    ROLES_COMMON_RULES.md        ← mandatory rules for every role (read this first)
    CUSTOM_ROLES.md              ← guide for adding custom agent roles
    roles/
      00-conductor.md            ← conductor system spec
      05-intake.md               ← intake agent (interviews human, creates feature folder)
      10-orchestrator.md
      20-critic.md
      30-implementer.md
      40-reviewer.md
      50-behavior-reviewer.md
    coding-standards/            ← base engineering & coding standards (all roles follow these)
    knowledge/                   ← knowledge base template + guidelines
    templates/
      config.json                ← .xorial/config.json template
      pipeline.json              ← default pipeline sequence
      run.sh                     ← conductor launch script template
      chat.md                    ← quick-start guide for interactive agent chats
  conductor/                     ← Python daemon (automated mode)
    main.py                      ← entry point

<project>/.xorial/              ← per-project (not in this repo)
  config.json                    ← xorial_path, instance_name, telegram credentials
  run.sh                         ← launch conductor for this project
  chat.md                        ← reference this in interactive chats to load roles and features
  context/
    project-context.md           ← project structure, commands, paths for agents
    pipeline.json                ← skip, scopes, custom_agents overrides
    work/
      feat/<name>/               ← new features
      fix/<name>/                ← bug fixes
      refactor/<name>/           ← refactoring
      chore/<name>/              ← dependency updates, tooling
        feature.md, plan.md, handoff.md, status.json, ...
    knowledge/                   ← cross-feature knowledge base
    coding-standards/            ← project-specific coding standard extensions
```

---

## How to connect a new project

```bash
./attach.sh /path/to/your/project
```

`attach.sh` sets up `.xorial/` structure, installs dependencies, and — for Node.js projects — automatically injects two scripts into `package.json`:

```json
"xorial":          ".xorial/run.sh",
"xorial:dry-run":  ".xorial/run.sh --dry-run"
```

Then fill in `.xorial/config.json` and `.xorial/context/project-context.md`.

Open `.xorial/context/` as an [Obsidian](https://obsidian.md) vault — this is your visual project interface (dashboard, kanban, feature map). Install the required plugins listed in `SETUP.md`.

Full steps: see `SETUP.md`.

---

## How to run (automated mode)

```bash
cd /path/to/project
./.xorial/run.sh
```

Telegram commands: `/status`, `/resume [feature]`, `/new <type> <name>`

Types: `feat`, `fix`, `refactor`, `chore`  
Example: `/new feat age-verification`

---

## How to run (manual mode)

Reference `.xorial/chat.md` in your conversation with Claude.  
It will ask what you want to do and route you to the right role automatically.

Or give an agent a direct prompt:

**New feature** (vague idea → intake interviews you and creates the feature folder):
```
Take role: /path/to/Xorial/core/roles/05-intake.md
Project context: /path/to/project/.xorial/context/project-context.md
Start your pass.
```

**Existing feature** (orchestrate, implement, review, etc.):
```
Take role: /path/to/Xorial/core/roles/10-orchestrator.md
Work on: /path/to/project/.xorial/context/work/feat/<name>/
Start your pass.
```

When in doubt, use `chat.md` — it maps your intent to the correct role.

---

## Workflow summary

| Stage | Owner | Output |
|-------|-------|--------|
| Intake | Intake agent | `feature.md`, `context.md`, `status.json` |
| Planning | Orchestrator | `plan.md`, `decisions.md` |
| Critique | Critic | `review.md` |
| Finalization | Orchestrator | `spec-final.md`, `handoff.md` |
| Implementation | Implementer | code, `implementation.md` |
| Code review | Reviewer | `review-final.md` |
| Human review | Human | feedback, scope changes |
| Behavior review | Behavior Reviewer | `behavior-review.md` |
| Done | Orchestrator | `changelog.md`, cleanup |

Full spec: `core/AI_IMPLEMENTATION_FLOW.md`

---

## Recommended models

| Role | Model |
|------|-------|
| Orchestrator, Critic | `claude-opus-4-6` |
| Implementer, Reviewer, Behavior Reviewer | Codex (`o3`, `high` reasoning) |

---

## Customizing the pipeline

Configure the agent sequence per project via `.xorial/context/pipeline.json`:

- **Skip agents**: `"skip": ["behavior-reviewer"]`
- **Define app scopes**: `"scopes": {"mobile": "apps/mobile", "backend": "services/api"}`
- **Add custom agents**: define in `custom_agents`, create role file in `.xorial/context/roles/`
- **Insert between agents**: override `sequence` entries

Full guide: `core/CUSTOM_ROLES.md`

---

## Working on Xorial itself

- `core/roles/` — edit role files to change agent behavior
- `core/coding-standards/` — base engineering & coding standards, apply to all projects
- `conductor/` — Python automation daemon
- Do not put project-specific content in `core/` — that belongs in `<project>/.xorial/context/`
- Read `ROLES_COMMON_RULES.md` before editing any role file

---

## License

Apache 2.0 with Commons Clause. Free to use, including commercially.  
Selling or offering Xorial as a service requires a commercial license.

Contact: mikhail.yarmaliuk@lomray.com  
See `LICENSE` and `NOTICE` for full terms.
