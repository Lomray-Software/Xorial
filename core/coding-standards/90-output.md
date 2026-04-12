---
apply: always
---

# Output and collaboration rules

## General output behavior
For simple tasks:
- answer concisely;
- provide the code directly;
- avoid unnecessary explanation.

For non-trivial tasks:
1. Briefly restate the chosen approach.
2. Mention the minimal implementation strategy.
3. If there is architectural risk, say it directly.
4. Then provide the code.

## Challenge bad ideas
If the user's requested implementation is weak, fragile, or inconsistent with the project architecture:
- say so directly;
- explain briefly why;
- propose the smallest better alternative.

Do not blindly agree with bad technical decisions.

## Scope discipline
Only change what is necessary for the task.
Do not widen the task unless required for correctness.

## Code style adaptation
When writing code, imitate the surrounding codebase:
- same component shape;
- same naming;
- same decomposition style;
- same comment style;
- same order of members.

The existing project style has priority.

## Code comments
Where appropriate, generate short block comments in this form:

/**
 * Description
 */

Use comments for:
- component purpose;
- store purpose;
- method intent;
- important properties;
- non-obvious logic.

Do not generate verbose JSDoc-by-template unless explicitly requested.

## Delivery checklist
Before finalizing, verify:
- only relevant files are touched;
- business logic is not leaking into UI;
- large components are decomposed when needed;
- stores/services remain responsible for behavior;
- no unnecessary dependency was introduced;
- public contracts were not silently broken;
- code matches local project style.

## When project context is insufficient
If the task depends on local project conventions that are not visible yet:
- first inspect nearby relevant files;
- infer the local pattern;
- then generate code aligned with that pattern.

Do not produce disconnected “generic tutorial style” code if real project context is available.

## Preferred tone
Keep tone professional, direct, and efficient.
Match the user's language **only in interactive chat replies**. Every written artifact (code, comments, Markdown, docs, commit messages, status fields) is English-only. See `00-core.md` → Response language.
