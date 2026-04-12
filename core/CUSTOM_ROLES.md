# Custom Roles in Xorial

This guide explains how to add a custom agent role to a project — without touching Xorial core.

---

## How the pipeline works

The pipeline is a **transition map**: "after agent X finishes, run agent Y".

```
core/templates/pipeline.json → defines the default sequence
.xorial/context/pipeline.json → project overrides (merged on top)
```

When conductor sees `owner: X` in `status.json`, it looks up X in the sequence, applies skip rules, and routes to the effective next agent.

**Important:** Orchestrator is NOT in the sequence — it decides its own next step based on feature state (e.g., `owner: critic` after planning, `owner: implementer` after spec is ready). This means you cannot intercept orchestrator's decisions via `sequence` alone. See [Inserting before critic](#inserting-before-critic) below.

---

## Case 1 — Insert agent in a deterministic transition

Use this when you want to insert between two agents that have a fixed, automatic transition:
`implementer → reviewer`, `reviewer → human`, `human → behavior-reviewer`, etc.

**Example: add `security-reviewer` between `reviewer` and `human`**

### Step 1 — Create the role file

```
.xorial/context/roles/security-reviewer.md
```

```markdown
# Security Reviewer

## Global Rules
See `{{xorial_core}}/ROLES_COMMON_RULES.md`.

## Role
You are the security reviewer for this feature.

## Goal
Check the implementation for common security issues before human review.

## Read first
- `{{xorial_core}}/ROLES_COMMON_RULES.md`
- `{feature_path}/handoff.md`
- `{feature_path}/implementation.md`
- current diff / changed files

## You own
- `security-review.md`
- `status.json`

## Responsibilities
1. Check for injection vulnerabilities, auth bypass, insecure data handling.
2. Flag MUST FIX issues with clear remediation steps.

## Exit marker
- `SECURITY_PASS` — no blocking issues, hand off to human review
- `SECURITY_FAIL` — blocking issues found, send back to implementer

## Handoff
On SECURITY_PASS: set `owner: human` in status.json.
On SECURITY_FAIL: set `owner: implementer` in status.json.
```

### Step 2 — Update `pipeline.json`

```json
{
  "sequence": {
    "reviewer": "security-reviewer",
    "security-reviewer": "human"
  },
  "skip": ["behavior-reviewer"],
  "custom_agents": {
    "security-reviewer": {
      "type": "claude",
      "model": "claude-opus-4-6",
      "role_file": ".xorial/context/roles/security-reviewer.md"
    }
  }
}
```

**How the merge works:**

Base sequence has `"reviewer": "human"`. Your project adds:
- `"reviewer": "security-reviewer"` — overrides the base entry
- `"security-reviewer": "human"` — new entry

Result: `reviewer → security-reviewer → human`.  
No entries in Xorial core are modified.

---

## Case 2 — Insert before critic (or any orchestrator-directed step)

Orchestrator decides its own next step — it writes `owner: critic` directly when planning is done. The sequence cannot intercept this. Use a **skill** instead.

**Example: add `security-reviewer` before `critic`**

### Step 1 — Create the role file (same as above)

The role file must set `owner: critic` when done (so orchestrator's intent is preserved).

```markdown
## Handoff
On SECURITY_PASS: set `owner: critic` in status.json.
On SECURITY_FAIL: set `owner: implementer` in status.json.
```

### Step 2 — Create a skill that modifies orchestrator behavior

```
.xorial/context/skills/security-review-before-critic.md
```

```markdown
# Skill: Security Review Before Critic

**Applies to**: orchestrator

When you are ready to hand off to the critic (planning complete, spec ready):
Do NOT set `owner: critic` directly.
Instead, set `owner: security-reviewer` — it will run first and then pass to critic.
```

### Step 3 — Register the custom agent in `pipeline.json`

```json
{
  "sequence": {
    "security-reviewer": "critic"
  },
  "skip": ["behavior-reviewer"],
  "custom_agents": {
    "security-reviewer": {
      "type": "claude",
      "model": "claude-opus-4-6",
      "role_file": ".xorial/context/roles/security-reviewer.md"
    }
  }
}
```

The skill tells orchestrator to write `owner: security-reviewer`.  
The sequence entry `security-reviewer → critic` tells conductor what comes after.  
No core files modified.

---

## custom_agents format

```json
"custom_agents": {
  "<agent-name>": {
    "type": "claude" | "codex",
    "model": "claude-opus-4-6",
    "reasoning": "high",
    "role_file": ".xorial/context/roles/<name>.md"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | no | `"claude"` (default) or `"codex"` |
| `model` | no | Model override. Default: `claude-opus-4-6` for claude, ignored for codex |
| `reasoning` | no | Codex only: `"high"`, `"x-high"` |
| `role_file` | yes | Path to role `.md` file. Relative to project root or absolute. |

---

## Checklist

- [ ] Role file created in `.xorial/context/roles/`
- [ ] Role file has clear **Handoff** section — specifies what `owner` to write on each exit
- [ ] `custom_agents` entry added to `pipeline.json`
- [ ] `sequence` entries added/overridden in `pipeline.json` (for deterministic insertions)
- [ ] If inserting before an orchestrator-directed step: skill created in `.xorial/context/skills/`
