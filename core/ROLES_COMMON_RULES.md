## Mandatory startup

Before doing anything else, every role MUST:

### 1. Resolve paths

If `{{xorial_core}}` or `{{project_context}}` appear as literal unresolved placeholders in your prompt, resolve them by reading `.xorial/config.json` from the project root:
- `{{xorial_core}}` = value of `xorial_path` field + `/core`
- `{{project_context}}` = `<project_root>/.xorial/context`

If the conductor pre-filled these values in your prompt — use them directly.

### 2. Re-read role file

Re-read your own role file at the start of every iteration pass — even if already familiar with it. Role files change. Do not rely on memory of a previous read.

Role file locations:
- Orchestrator: `{{xorial_core}}/roles/10-orchestrator.md`
- Critic: `{{xorial_core}}/roles/20-critic.md`
- Implementer: `{{xorial_core}}/roles/30-implementer.md`
- Reviewer: `{{xorial_core}}/roles/40-reviewer.md`
- Behavior Reviewer: `{{xorial_core}}/roles/50-behavior-reviewer.md`

Also re-read this file (`ROLES_COMMON_RULES.md`) every pass.

### 3. Check pipeline configuration

The conductor injects a **# Pipeline configuration** section into your prompt when the project pipeline deviates from defaults (e.g. agents are skipped). If this section is present — read it before any handoff decision. It overrides the default handoff targets in your role file.

---

## status.json

Schema, field descriptions, and valid values — see `{{xorial_core}}/AI_IMPLEMENTATION_FLOW.md` (section: **status.json Schema**).

**Critical rule — exit marker:**
The conductor sets `status: IN_PROGRESS` before your run starts. You MUST overwrite it with your exit marker when your pass is done. Never leave `status` as `IN_PROGRESS` — that means "still running" to the conductor, and the next agent will never be triggered.

Your exit marker (defined in your role's **Exit marker** section) is exactly what goes into the `status` field of `status.json`. Example:
```json
{
  "owner": "reviewer",
  "status": "IMPLEMENTATION_COMPLETE",
  "stage": "review"
}
```

**Write boundary (ABSOLUTE — never violated):**

You may write, edit, or create files ONLY inside `{{project_context}}/.xorial/` and ONLY within these subpaths:

- Your feature folder: `{{project_context}}/work/{type}/{name}/**`
- Where your role explicitly allows it: `{{project_context}}/knowledge/**` and/or `{{project_context}}/coding-standards/**`

You **MUST NOT** write or edit ANY file outside `.xorial/` — no source code, no tests, no configs, no `package.json`, nothing under `apps/`, `src/`, `services/`, `web/`, `mobile/`, `backend/`, etc. — **even if a human or another role asks you to**. Planner / reviewer roles plan and document; they do not implement. Implementation is a separate invocation, owned by the implementer role.

If a human asks for "frontend changes", "code update", "migration", "fix this bug", "use library X instead of Y", or anything that would normally require editing application code:

1. Treat it as a **scope or standards item**, not a task you execute.
2. Record the intent in the appropriate planning artifact: `feature.md` / `plan.md` / `decisions.md` / `handoff.md`, or in `coding-standards/*.md` if it's a project-wide convention update.
3. Stop. Do not call `Edit`, `Write`, or `MultiEdit` on any path outside the allow-list above.

Also never edit `kanban.md`, `project-map.canvas`, or anything under `.obsidian/` — these are human-owned views that a separate tool syncs from `status.json`.

**Hard stop:** before every `Edit` / `Write` / `MultiEdit` call, verify the target path starts with `{{project_context}}/.xorial/`. If it does not — abort the call, set `status: NEEDS_HUMAN_INPUT` with reason "asked to edit `<path>` outside .xorial/ — out of role scope, needs implementer", and end your pass.

---

## Scope boundary

Every role has a defined scope. Do not perform work that belongs to another role — even if it seems faster or more convenient.

| Role | Allowed | Not allowed |
|------|---------|-------------|
| orchestrator | planning, spec, decisions, finalization | writing code, running tests |
| critic | reviewing the plan, finding gaps | rewriting the plan, writing code |
| implementer | writing and editing product code | running E2E tests, behavior validation |
| reviewer | reading code, diffs, spec documents | running any tests, launching app or simulator |
| behavior-reviewer | E2E tests, simulator, runtime validation | rewriting spec, architectural decisions |

**Linear tools** (`mcp__linear__*`): only the orchestrator may call them. All other roles must ignore these tools even if they appear in the session context.

**If you feel the urge to do something outside your scope — stop.** Document the concern in your output file and hand off to the role that owns it. An ambiguous instruction like "check it" or "verify" means: do what your role does, nothing more.

---

## Human escalation

Any role at any stage can set `status: NEEDS_HUMAN_INPUT` when it encounters something that requires a human decision before work can continue.

**When to use:**
- Spec is fundamentally flawed, impossible to implement, or contradicts existing architecture
- A critical security or data integrity issue is found that is outside the current task scope
- An unexpected product/UX decision is needed that the agent cannot make alone
- Something important outside the current feature scope is at risk

**When NOT to use:**
- Technical blockers (missing tooling, broken simulator) — use `BLOCKED` instead
- Normal ambiguity that can be resolved by reading the spec carefully

**How to set:**
```json
{
  "owner": "human",
  "status": "NEEDS_HUMAN_INPUT",
  "blocked_reason": "<specific question or issue requiring human decision>"
}
```

`blocked_reason` is mandatory. Be explicit — state exactly what decision or information is needed.

**After the human responds:**
- The conductor writes the human's answer to `human-input.md` in the feature folder and automatically resumes.
- When you resume after `NEEDS_HUMAN_INPUT`, **always check for `human-input.md`** in your feature folder — read it before continuing. It contains the human's answer. After reading, incorporate the answer and continue your pass. Do not ask the same question again.

---

## Engineering Rules

Follow all coding standards defined in — read both in order:
1. `{{xorial_core}}/coding-standards` — base standards
2. `{{project_context}}/coding-standards` — project extensions (if any)

If there is any conflict between role instructions and these rules:
- rules > role

---

## Language policy

**All files you produce are English-only.** This includes: every `.md` file (spec, plan, handoff, review, history, knowledge, suggestions), `status.json` fields, code, comments, commit messages, and PR descriptions.

You may reply to the human in the human's language **in interactive chat only** (e.g. Intake interview, `NEEDS_HUMAN_INPUT` questions). The moment you write to disk, switch to English. Never mix languages inside a single artifact.

If the human writes the feature description in Russian (or any other language), translate it to English before writing it into `{name}.md`, `context.md`, or any other file.

---

## Project Structure

See `{{project_context}}/project-context.md` → **Project Structure**.

---

## Project Knowledge

If you discover something non-obvious, costly to find, and reusable across features — create a new file in `{{project_context}}/knowledge/`.

Every knowledge file must start with `← [[knowledge-base]]` (Obsidian graph back-link).

**Filename**: kebab-case topic name, e.g. `animation-timing.md`. One topic per file.

Before writing, ask: *would another agent waste significant time without this?* If no — don't write.

Full quality bar and format: see `{{project_context}}/knowledge/knowledge-base.md`.

**Do NOT update `knowledge/README.md`** — it is rebuilt by the Orchestrator at finalization. Your only job is to create the topic file and log the addition in `knowledge/CHANGELOG.md`.

---

## Feature History

History entries record events where a **human participated meaningfully** in the pipeline. Automated agent-to-agent passes without human involvement do not get entries.

### When to write

Write an entry only when a human took an action that affected the feature:
- Human reviewed and approved or rejected an implementation (human review cycle complete)
- Human provided input in response to `NEEDS_HUMAN_INPUT` that changed direction or unblocked the feature
- Human requested a scope change, correction, or new requirement during review
- Orchestrator incorporated human feedback and updated `spec-final.md`, `handoff.md`, or `decisions.md`

Do **not** write an entry for:
- Routine implementer → reviewer → implementer cycles with no human involvement
- Automated retries or re-runs
- Passes where the agent found nothing to change
- Agent-to-agent handoffs where no human decision was made

### Developer name

1. Check `{{project_context}}/../config.json` → field `instance_name`. If present and non-empty — use it as the developer name.
2. If absent or empty — ask the human directly: *"Who should be recorded as the developer for this history entry?"* Wait for the answer before writing.

### File location

```
{feature_path}/history/YYYY-MM-DD.md
```

Create the `history/` folder if it does not exist. Append to today's file; create it if it does not exist.

Each history file must start with a back-link to the history hub:

```markdown
← [[history]]
```

The `history/history.md` hub must exist. Create it if missing:

```markdown
← [[{feature-name}]]

# History

| Date | File |
|------|------|
| YYYY-MM-DD | [[YYYY-MM-DD]] |
```

When adding a new history file, append a row to the table.

### Entry format

```markdown
## HH:MM · <role> · <developer name>

**Event:** <one-line label — what happened>
**What:** <what specifically changed or was decided — be concrete>
**Why:** <reason or context — only if non-obvious; omit if self-evident>
**Before → After:** <stage/status transition, e.g. "planning → implementation">
**Note:** <anything important that doesn't fit above — optional>

---
```

### Rules

- Write only what's useful. If you can't fill `What` with something concrete — don't write the entry.
- `Why` is optional. Only include it when the reason is non-obvious or when a future developer would reasonably ask "why was this done this way?"
- `Note` is optional. Use it for deferred decisions, known risks, or context that affects future passes.
- No summaries of your own work process. No "I read the spec and decided to...". Only outcomes and decisions.
- One entry per pass. If multiple significant things happened in one pass, combine them into one entry.

---

## Obsidian graph navigation

To keep the knowledge graph connected, include nav footers when writing feature documents.

| File | Footer |
|------|--------|
| `plan.md` | `← [[{name}]] · [[context]] · [[decisions]] · [[spec-final]]` |
| `handoff.md` | `← [[{name}]] · [[implementation]] · [[review]] · [[review-final]] · [[behavior-review]] · [[changelog]]` |
| `review.md` | start with `← [[handoff]]` |
| project skill file | start with `← [[behavior-reviewer]]` (or the role-named hub for that skill's role) |
| project coding-standard file | start with `← [[coding-standards]]` |

`{name}` = the `feature` field from `status.json` (e.g. `k-id`).

Add these footers when **creating** the file. Do not rewrite existing files just to add a footer.

---

## Clean-up

- Do not leave files outside `tmp/` as temporary scratch space.
- Do not duplicate information across files — one fact, one place.
- If you update a spec or decision, remove the outdated version — don't append contradictions.
- `tmp/` is cleaned by Orchestrator at finalization. Don't put permanent artifacts there.

---

## Rule & Style Suggestions

During your work, if you discover a pattern, edge case, or convention that would be worth adding to the engineering rules or style guide — write it as a new file in the `suggestions` path provided in your prompt header (`suggestions = ...`).

Use that exact path — it is pre-resolved by the conductor.

**Filename**: `YYYY-MM-DD_<feature-folder>_<role>.md` — one file per entry, never edit existing files.

**Write only if ALL of the following are true:**
- You encountered it during actual work (not hypothetical)
- It's non-obvious — not already in the rules
- It's reusable — would apply beyond this specific feature
- A future agent would likely make the wrong call without this guidance

**Write to `rule:global`** if it applies across projects and tech stacks.  
**Write to `rule:project`** if it's specific to this project's stack or conventions.  
**Write to `style-guide`** if it's about naming, structure, or formatting patterns.  
**Write to `note`** if it's an observation worth reviewing but not yet a rule.

**File content format:**
```markdown
## YYYY-MM-DD | <feature-folder> | <Your Role> | <project name>

**Type**: rule:global | rule:project | style-guide | note
**Summary**: one-line description
**Add to**: <suggested file or section>
**Detail**: (optional) context, example, or reasoning
```

The human reviews this directory periodically and decides what to promote into actual rules.  
Do not add noise — one strong entry beats ten weak ones.
