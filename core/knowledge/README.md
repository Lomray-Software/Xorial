# Knowledge Base

This folder accumulates project-specific knowledge discovered during feature work.

## Purpose

Agents write here when they encounter non-obvious discoveries that future agents would likely waste significant time rediscovering — tricks, workarounds, quirks, and hard-won patterns.

## Write only if ALL of the following are true

- **Non-obvious**: not derivable from reading the code or standard documentation
- **Costly to discover**: required real investigation — multiple failed attempts, debugging sessions, or significant time
- **Reusable across features**: not tied to one specific feature's logic
- **Future agents would likely hit the same issue**: a reasonable agent starting fresh would make the same mistake

## Do NOT write

- Standard RN, Detox, or library patterns already in official docs
- Things obvious from reading the codebase
- Knowledge specific to a single feature — put that in `work/{type}/{name}/` instead
- Temporary notes or observations from a single run that won't repeat

## Feature-specific vs global knowledge

| Where it belongs | Condition |
|-----------------|-----------|
| `knowledge/` | Reusable across features, non-obvious, costly to discover |
| `work/{type}/{name}/` | Specific to that feature's logic, flow, or test setup |

When in doubt: if another feature's agent would benefit from reading it, it goes in `knowledge/`. If not, it stays in the feature folder.

## Rules

- **Append-only for files**: add new files, do not rewrite existing ones.
- **Deletion allowed**: remove entries that are confirmed outdated — but log every deletion in `CHANGELOG.md` with a reason.
- **One topic per file**: keep files focused. If a new topic emerges, create a new file.
- **Filename convention**: kebab-case describing the topic, e.g. `animation-timing.md`, `auth-flow-quirks.md`.

## Who writes here

- **Behavior Reviewer** — primary contributor: tricks, workarounds, stability patterns discovered during test runs
- **Implementer** — may add architecture quirks discovered during implementation
- Other roles — only if a discovery clearly meets the quality bar above

## Who reads here

All roles should scan this folder at the start of their work.

## Deletion policy

Before deleting an entry or file:
1. Confirm the knowledge is no longer valid (e.g. library upgrade, behavior changed)
2. Log the deletion in `CHANGELOG.md` — file, topic, reason
3. Then delete

Git history preserves the content. The CHANGELOG preserves the *why*.

## Current files

| File | Topic |
|------|-------|
| [CHANGELOG.md](CHANGELOG.md) | Log of additions and deletions |
