# AI Implementation Flow

This file explains the AI-driven implementation workflow used in this
project.

## Purpose

This workflow helps structure feature planning, critique,
implementation, review, behavior validation, human review, iteration, and future follow-up
using multiple AI agents and persistent markdown files.

The main idea is:

-   files = memory
-   agents = temporary workers

Agents should not rely on chat history. They should rely on the files
inside `{{xorial_core}}/` (core) and `{{project_context}}/` (project-specific).

------------------------------------------------------------------------

## Directory Structure

```text
{{xorial_core}}/                        ← Xorial core (shared, versioned)
  AI_IMPLEMENTATION_FLOW.md
  ROLES_COMMON_RULES.md
  roles/
    10-orchestrator.md
    20-critic.md
    30-implementer.md
    40-reviewer.md
    50-behavior-reviewer.md
  coding-standards/              ← base engineering & coding conventions
    00-core.md
    10-architecture.md
    ...
  knowledge/
    README.md                    ← boilerplate only
  features/
    _template/                   ← feature folder template

{{project_context}}/                     ← project-specific (.xorial/context/)
  project-context.md
  pipeline.json                  ← skip, scopes, custom_agents
  knowledge/                     ← accumulated project knowledge
    README.md
    <topic>.md
  coding-standards/              ← project extensions on top of base standards
  work/
    feat/                        ← new features
      <name>/
    fix/                         ← bug fixes
      <name>/
    refactor/                    ← refactoring
      <name>/
    chore/                       ← dependency updates, config, tooling
      <name>/
    <any-type>/<name>/
      feature.md
      context.md
      plan.md
      review.md
      decisions.md
      spec-final.md
      handoff.md
      implementation.md
      review-final.md
      changelog.md
      behavior-review.md
      status.json
      tmp/
      history/
```

### Portability

When reusing this workflow in a new project:
- Copy as-is: `AI_IMPLEMENTATION_FLOW.md`, `roles/`
- Clear and adapt: `project-context.md`, `coding-standards/`, `knowledge/`, `work/`

------------------------------------------------------------------------

## Global Principles

-   Each role has a separate responsibility.
-   Each file has a clear purpose.
-   Do not depend on chat memory.
-   Always read the current feature folder before acting.
-   If rules conflict, global rules win over role-specific instructions.
-   Agents should update only the files they own unless explicitly
    instructed otherwise.

### Source of Truth Rule

-   `review.md` is input only.
-   `spec-final.md` and `handoff.md` are the source of truth for
    implementation.
-   Approved changes must not remain only in `review.md`.
-   All approved changes must be merged into spec/handoff before
    implementation continues.

### Re-iteration Rule

-   Do not reimplement from scratch.
-   Treat current implementation as baseline.
-   Implement only delta changes.
-   Preserve working code unless spec requires change.

------------------------------------------------------------------------

## Roles

### Orchestrator

Planner and finalizer.

-   Owns: plan.md, decisions.md, spec-final.md, handoff.md,
    changelog.md, status.json
-   Incorporates human review into source of truth
-   Finalizes feature

### Critic

Pre-implementation reviewer.

-   Owns: review.md, status.json
-   Finds risks, gaps, edge cases

### Implementer

Code executor.

-   Owns: code, implementation.md, status.json
-   Implements delta only
-   Logs what was done

### Reviewer

Final code reviewer.

-   Owns: review-final.md, status.json
-   Validates correctness and quality

### Behavior Reviewer

Validates real runtime behavior of the implemented feature on a simulator/device.

Responsibilities:
- read the latest approved scope and implementation state
- detect whether simulator/device is already running
- detect whether the app is already installed/launched
- detect whether debug tooling is available
- detect whether Detox is configured and runnable
- prepare a short execution plan
- run behavior checks with minimal manual intervention
- collect logs, screenshots, and test evidence
- compare expected vs actual behavior
- produce a verdict

Owns:
- `behavior-review.md`
- `status.json`

------------------------------------------------------------------------

## File Roles

-   review.md → input only
-   spec-final.md → final scope
-   handoff.md → executable instructions
-   implementation.md → actual result
-   review-final.md → quality check
-   behavior-review.md → runtime behavior validation
-   changelog.md → history

------------------------------------------------------------------------

## status.json Schema

Every role that completes a pass must update `status.json`.

```json
{
    "feature": "",
    "type": "feat | fix | refactor | chore",
    "scope": [],
    "depends_on": "",
    "iteration": 1,
    "owner": "orchestrator | critic | implementer | reviewer | behavior-reviewer | human",
    "stage": "planning | critic | implementation | code-review | human-review | behavior-review | done",
    "status": "",
    "roles_skip": [],
    "roles_force": [],
    "blocked_reason": "",
    "last_updated": "YYYY-MM-DD HH:MM:SS"
}
```

### Field descriptions

| Field | Set by | Description |
|-------|--------|-------------|
| `feature` | intake / human | Feature name (folder name inside `work/{type}/`) |
| `type` | intake / human | Work type: `feat`, `fix`, `refactor`, `chore` |
| `scope` | orchestrator | App scopes this feature touches, e.g. `["mobile", "backend"]`. Keys from `pipeline.json` scopes map. Empty = not scope-specific. |
| `depends_on` | orchestrator | Feature ID (`type/name`) this feature must wait for before starting. Used for child features in cross-scope parallel work. |
| `iteration` | orchestrator | Increments each time the full cycle restarts |
| `owner` | current role | Role responsible for the next action |
| `stage` | current role | Current phase of the workflow |
| `status` | current role | Exit marker of the last completed pass (e.g. `READY_FOR_IMPLEMENTATION`, `AWAITING_HUMAN_REVIEW`, `PASS`) |
| `roles_skip` | orchestrator | Roles to skip for this feature only. `fix/` and `refactor/` always include `["intake"]`. |
| `roles_force` | orchestrator | Roles to un-skip for this feature even if globally skipped in `pipeline.json`. Use to opt-in to optional agents like `behavior-reviewer`. |
| `blocked_reason` | any role | Required when status is `BLOCKED_*` or `NEEDS_HUMAN_INPUT` |
| `last_updated` | current role | ISO datetime of last update — format `YYYY-MM-DD HH:MM:SS` |

------------------------------------------------------------------------

## Feature folder structure

Work items live under `work/{type}/{name}/`:

| Type | Folder | Example path |
|------|--------|--------------|
| New feature | `work/feat/` | `work/feat/age-verification/` |
| Bug fix | `work/fix/` | `work/fix/auth-crash-on-logout/` |
| Refactoring | `work/refactor/` | `work/refactor/api-client-cleanup/` |
| Chore | `work/chore/` | `work/chore/upgrade-react-native/` |

- Use kebab-case for the name
- Keep names short and descriptive
- `"feature"` field in `status.json` = the folder name (not the full path)

------------------------------------------------------------------------

## Workflow

The active pipeline is configured per project in `.xorial/context/pipeline.json`.
**Default pipeline skips `behavior-reviewer`** — steps 11–12 are optional.

0.  **Intake** (optional automated path) → Intake agent interviews human, creates feature folder + `feature.md` + `context.md` + `status.json`
1.  Human writes feature.md + context.md (manual path)
2.  Orchestrator → plan + decisions
3.  Critic → review
4.  **Loop** (planning ↔ critic): exit when review.md has no BLOCKERS and Orchestrator sets READY_FOR_IMPLEMENTATION
5.  Orchestrator → spec-final + handoff
6.  Implementer → code + implementation.md
7.  Reviewer → review-final.md
8.  **Loop** (implementer ↔ reviewer): exit when review-final.md has no MUST FIX and Reviewer sets AWAITING_HUMAN_REVIEW
9.  Human review
10. If scope changed → back to step 2 (Orchestrator), repeat cycle
11. *(optional)* **Behavior Reviewer** → behavior-review.md — enabled via `pipeline.json`
12. *(optional)* **Loop** (behavior): exit when Behavior Reviewer sets PASS or PASS WITH NOTES
    - If FAIL → implementer (fix) → reviewer → behavior reviewer
      - **Fast-track**: if implementer marks fix as `MINOR` and reviewer agrees → `MINOR_FIX_AWAITING_HUMAN_REVIEW` → skip human review → behavior reviewer directly
      - **Standard**: if fix is `SIGNIFICANT` → `AWAITING_HUMAN_REVIEW` → human review → back to step 10
13. Orchestrator finalizes: changelog → clean up `tmp/run-NNN/` (keep `INDEX.md`) → status `DONE`
    - If behavior-reviewer skipped: finalizes after step 9 when `status: AWAITING_HUMAN_REVIEW`
    - If behavior-reviewer active: finalizes after step 12 when `status: PASS`

------------------------------------------------------------------------

## Decision Rule

-   plan changed → orchestrator
-   code changed → implementer
-   behavior validation needed → behavior reviewer

------------------------------------------------------------------------

## Human Review Rule

If human introduces changes:

-   Do NOT leave them in review.md
-   Orchestrator must merge them into:
-   spec-final.md
-   handoff.md

------------------------------------------------------------------------

## Reopening Feature

-   Update feature/context
-   Increment iteration
-   Update changelog
-   Restart orchestrator

------------------------------------------------------------------------

## Core Rule

spec-final.md + handoff.md = source of truth  
implementation.md = reality  
behavior-review.md = runtime truth  
review.md = discussion only

## Recommended Models

- Orchestrator → `claude-opus-4-6`
- Implementer → Codex (latest)  (`high`)
- Reviewer → Codex (latest) (`medium` or `high`)
- Behavior Reviewer → Codex (latest) (`high`)

### Notes

- Use `claude-opus-4-6` for orchestration, planning, and architecture-heavy work.
- Use Codex (latest) for implementation and behavior review — optimized for coding, tools, software environments, and long agentic workflows.
- Use `high` reasoning by default for implementation and behavior review.
- Use `x-high` only for unusually complex debugging, flaky runtime behavior, or heavy async/state issues.
