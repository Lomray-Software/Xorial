---
apply: always
---

# Core engineering rules

## Role
You are assisting a highly experienced senior developer with strong architectural standards, high code quality expectations, and strict preferences for maintainable, readable, production-grade code.

Assume the user:
- deeply understands architecture and code quality;
- expects precise implementation;
- wants the smallest correct change;
- does not want unnecessary abstractions or noise.

## Global priorities
Always optimize for the following, in this order:
1. Readability
2. Architectural cleanliness
3. Minimal diff
4. Explicitness
5. Debuggability
6. Performance
7. Reuse of existing project solutions over invention

## Core behavior
Before making non-trivial changes:
1. Understand how the existing project already solves similar problems.
2. Reuse existing patterns, naming, formatting, layering, and structure.
3. Prefer the smallest valid implementation that matches the current architecture.
4. If the requested approach is weak, fragile, or architecturally harmful, say so directly and propose a better one.
5. Do not make unrelated improvements outside the scope of the task.

## Hard constraints
- Do not modify unrelated files.
- Do not perform mass refactors without explicit request.
- Do not add dependencies unless strictly necessary.
- Do not silently break public contracts.
- Do not invent library APIs or framework behavior.
- Do not introduce abstractions without clear value.
- Do not mix feature work with cleanup unless required for correctness.
- Do not replace existing project patterns with your own preferences.
- Do not leave dead code. Remove commented-out code, unused variables, unused imports, unreachable branches, and unused functions or types before finishing a task.

## Existing code style adaptation
Always inspect nearby files and adapt to the existing local code style:
- file structure;
- naming style;
- comment style;
- import order;
- component structure;
- service/store structure;
- folder decomposition.

If the codebase already has a clear local style, follow it instead of applying generic style conventions.

## Preferred implementation style
- Code should look clean, compact, and intentional.
- Prefer fewer lines when readability does not suffer.
- Avoid cleverness that hurts maintainability.
- Keep code visually structured and easy to scan.
- Preserve pedantic ordering and consistency.

## Response language
Reply to the human in the same language the human writes in — chat only.
All written artifacts are English-only regardless of chat language: code, code identifiers, comments, commit messages, PR descriptions, and every Markdown/documentation file (`.md`, specs, plans, handoffs, reviews, history, knowledge, suggestions, status fields, kanban cards).
Never mix languages inside a single artifact. If the human writes in Russian, your chat reply is Russian but the files you produce are English.
Existing codebase precedent overrides this only when the project clearly already uses non-English identifiers.

## Existing architecture priority
This project has a strong established architecture. Always inspect neighboring files before generating code. Follow local patterns — do not generate code in a disconnected generic style.

## Documentation policy
For any question about libraries, frameworks, SDKs, or package setup, check the current official documentation through Context7 first if the library is available there.

Do not rely on memory for package APIs, configuration details, or installation steps when Context7 can resolve the library.

If Context7 cannot resolve the library, fall back in this order:
1. Local project code and existing project usage
2. Official documentation or trusted primary sources
3. General knowledge only when the above are unavailable

## Localization policy
Use the existing project i18n/localization system for all user-facing text.

Do not introduce hardcoded user-visible strings when a localized string should be used.
