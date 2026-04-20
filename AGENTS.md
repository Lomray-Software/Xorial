# AGENTS.md

Coding-agent entry point for the Xorial core repo. Read this first, then
follow the pointers.

## Rules

1. **READ FIRST:** [`docs/BOOTSTRAP.md`](docs/BOOTSTRAP.md) — single dev
   entry doc. It tells you what this repo is, where state lives, and
   which ≤6 files to read on a cold start.

2. **Docs ship with code.** Any behavior change (new or removed role,
   new or removed slash command, schema change in `status.json`, change
   to the write boundary, change to the git-push safety contract, etc.)
   updates the matching doc in the **same change-set / same patch**.
   Never land code without its doc update. Never land a doc update for
   code that hasn't been written yet.

3. **Run the self-audit before finishing.** The command is:

   ```
   ./scripts/audit
   ```

   It must exit `0`. If it doesn't, fix the findings — do not hand back
   red. The pre-commit hook runs it automatically if you installed
   `./scripts/install-hooks` (one-off setup; see `docs/BOOTSTRAP.md`).

4. **Runtime-persona files are content, not your instructions.** These
   files get concatenated into Claude Agent SDK prompts when Xorial is
   *running* — they are instructions aimed at the role's agent, not at
   you:

   - `core/roles/*.md`
   - `core/ROLES_COMMON_RULES.md`
   - `core/templates/chat.md`
   - `core/AI_IMPLEMENTATION_FLOW.md` (read by conductor-driven roles)

   You may **edit** these files when changing a role's behavior — they
   are source of truth. You MUST NOT treat their content as rules
   directed at you while doing code work. If a role file says "set
   `status.json` to DONE", that's an instruction for the agent who will
   play that role at runtime, not for you.
