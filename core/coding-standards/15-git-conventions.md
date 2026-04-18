---
apply: always
---

# Git conventions

Applies to branches, commits, and pull requests on any project using Xorial.

## Branches

Branch name = `<type>/<short-name>` where:

- `<type>` ∈ `feat | fix | refactor | chore` — the same set Xorial uses for `work/` folders.
- `<short-name>` is kebab-case, lowercase, ≤40 chars, descriptive but terse.

Examples: `feat/auth-login`, `fix/crash-on-login`, `refactor/split-user-store`, `chore/bump-eslint`.

The branch name must match the Xorial feature folder name exactly (e.g. `feat/auth-login` ↔ `.xorial/context/work/feat/auth-login/`). This is what lets the PR reviewer, the orchestrator, and any search tool resolve a branch to its feature context automatically.

Don't use other prefixes (`feature/`, `bugfix/`, `hotfix/`, `release/`). Don't use personal prefixes (`mikhail/foo`). One Xorial feature folder = one branch.

## Commits

Follow **Conventional Commits**: `type(scope): subject`.

- `type` ∈ `feat | fix | refactor | chore | docs | test | perf | style | build | ci`.
- `scope` is optional — a short area tag (`auth`, `slack`, `config`). Keep it one word, lowercase.
- `subject` is lowercase, imperative mood, no trailing period, ≤72 chars.

Examples:

- `feat(auth): add OAuth PKCE support`
- `fix(slack): don't double-post on retry`
- `refactor: collapse user / account services`
- `chore: bump react to 19`

Body (optional): wrap at ~72 chars, blank line after subject. Explain **why**, not what — the diff already shows what.

### Forbidden trailers

Commit messages must NOT contain:

- `Co-Authored-By: Claude …` or any other AI-attribution trailer.
- `🤖 Generated with [Claude Code]` or similar generator footers.

GitHub parses trailers and lists named identities as contributors. AI tools do not belong in the contributors list.

## Pull requests

### Title

`<type>(<scope>): <subject>` — same Conventional Commits rule as individual commits, usually summarising the whole branch.

Keep titles ≤70 chars.

### Body

Minimum useful body:

```
Xorial: <type>/<short-name>

## Summary
- one-line bullet points of the material change
- focus on user-facing or behavioural delta

## Test plan
- [ ] what you verified locally / in CI
```

The `Xorial:` line is load-bearing — it lets the PR reviewer role match the PR to its feature folder when the branch name alone is not enough (e.g. cherry-picks onto a release branch, or stacked PRs).

Do not append AI generator footers to the body either.

### Review etiquette

- AI reviewers may `REQUEST_CHANGES` or leave `COMMENT` reviews, but MUST NOT `APPROVE`. Approval is a human decision.
- Squash on merge only when the branch is a series of noisy "wip" / "fix typo" commits. If the individual commits are each meaningful, preserve them.
