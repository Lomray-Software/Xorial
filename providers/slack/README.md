# Xorial Slack Provider

A long-running Slack bot that hosts Xorial intake/orchestrator/critic passes on a central machine (e.g. a Mac M1). Users interact through slash commands and threads; the server runs Claude Code via the official Agent SDK and auto-commits planning artifacts back to the project repo.

## Why this exists

Running Xorial inside each developer's working copy means `.xorial/context/` diverges between branches — planning docs drift, status.json conflicts, and the intake/critic loop becomes unreliable. Centralising planning on one writer (this bot) keeps the `.xorial/` folder coherent on `main` across the whole team.

Coding passes (implementer / reviewer / behavior-reviewer) still run locally in each dev's checkout. Only the planning stages live here.

## Architecture

```
Slack slash command
  -> handlers.py              (parse subcommand, resolve project + speaker)
    -> locks.py               (per-feature asyncio.Lock)
    -> invoker.py             (claude-agent-sdk query loop)
      -> SlackStreamer        (buffered chat_update into the thread)
    -> git_push.py            (auto-commit .xorial, push to project_root's remote)
```

State lives in flat JSON files next to the code:

| File                | Source of truth for                                  | Gitignored |
|---------------------|------------------------------------------------------|------------|
| `config.json`       | Slack credentials, Anthropic key, default model      | yes        |
| `projects.json`     | Registered code projects (path, git remote, branch)  | yes        |
| `workspaces.json`   | Slack team_id -> project binding                     | yes        |
| `channels.json`     | Slack channel_id -> feature binding                  | yes        |
| `users.json`        | Slack user_id -> `instance_name` (speaker identity)  | yes        |

All `.example.json` variants are committed as templates.

## Setup

**First time?** Create the Slack app using [`SLACK_APP_SETUP.md`](SLACK_APP_SETUP.md) — that's where `bot_token`, `app_token`, and `signing_secret` come from. Takes ~5 minutes.

Then in this folder:

```bash
cd providers/slack
cp config.example.json     config.json
cp projects.example.json   projects.json
cp workspaces.example.json workspaces.json   # optional starter
cp users.example.json      users.json        # optional starter
# channels.json is created on first bind
```

Fill in `config.json`:
- `bot_token` / `app_token` / `signing_secret` — from your Slack app (see `SLACK_APP_SETUP.md`)
- `anthropic_api_key` — billing key the Agent SDK will use
- `projects_dir` — absolute dir where project clones live (informational)
- `default_model` — used for role passes (intake/orchestrator/critic); default `claude-opus-4-7`
- `chat_model` — used for `@xorial <anything>` chat replies; default `claude-sonnet-4-6`

Fill in `projects.json` with one entry per code project. `project_root` must point to a working clone of the repo; the bot writes planning artifacts into `.xorial/` inside it and pushes to `git_branch`.

Fill in `workspaces.json` mapping each Slack workspace's `team_id` to a `project` key.

Start the bot:

```bash
./run.sh
```

Python 3.11+ is required.

For a supervised, auto-restart-on-pull deployment on macOS, use the
launchd setup in [`deploy/README.md`](deploy/README.md) — one-shot
`./deploy/install.sh` wires up git-sync + KeepAlive + post-merge hook.

## Slack commands

| Command                                         | Purpose                                            |
|-------------------------------------------------|----------------------------------------------------|
| `/xorial help`                                  | show command list                                  |
| `/xorial whoami`                                | report how you are recorded as speaker             |
| `/xorial register <name>`                       | register your `instance_name` for attribution      |
| `/xorial list`                                  | list features in this workspace's project          |
| `/xorial new <feat\|fix\|refactor\|chore> <name>` | create folder + bind this channel                  |
| `/xorial bind <type>/<name>`                    | bind this channel to an existing feature           |
| `/xorial unbind`                                | remove binding                                     |
| `/xorial delete <type>/<name> [confirm]`        | hard-delete a feature (folder + bindings + threads + push) |
| `/xorial status`                                | show `status.json` for the bound feature           |
| `/xorial intake [message]`                      | run intake role in a new thread                    |
| `/xorial orchestrate [message]`                 | run orchestrator                                   |
| `/xorial critic [message]`                      | run critic                                         |

Any text after the role name becomes the "speaker message" included in the prompt.

### Thread replies (continue a session)

Once a role pass posts its parent message, the bot tracks the thread. Any subsequent reply in that thread is routed back to the same role with `resume=session_id`, so the agent keeps full context across turns.

- Speaker attribution is re-resolved per reply: if Ian answers Mikhail's intake, the next history entry is authored by Ian.
- Per-feature lock serialises concurrent replies. A second reply waits for the first pass to finish.
- `threads.json` persists `channel:thread_ts → {project, feature, role, session_id}` so restarts preserve sessions.

### @mentions

- `@xorial intake [message]` in a bound channel — same as `/xorial intake`, useful when you'd rather type than open the slash menu.
- `@xorial help` — returns the static command list; no tokens spent.
- `@xorial <anything else>` — **chat mode**. The bot replies in a thread via the `chat_model` (Sonnet by default), read-only tools, no git commit. Follow-up replies in the thread continue the session. Good for "what do I do next?" / "what's in this repo?" type questions.
- `@xorial` inside a tracked thread — equivalent to a plain reply; kept as an explicit affordance.

Management commands (`new`, `bind`, `list`, `status`, etc.) stay on the slash so there is one obvious surface for them.

## Attachments

Files dropped into a tracked thread (or on the initial `/xorial <role>` message) are downloaded and passed to the agent as absolute file paths.

| Kind                                       | Behaviour                                              |
|--------------------------------------------|--------------------------------------------------------|
| Public URLs pasted as text                 | Agent fetches with its built-in WebFetch tool          |
| Images (png/jpg/gif/webp)                  | Downloaded, path handed to agent, Claude reads visually |
| Text files (md/txt/json/yaml/code/csv/log) | Downloaded, agent Reads the path                       |
| PDF                                        | Downloaded; Claude parses PDF natively                 |
| GitHub public PRs / issues                 | Agent fetches with WebFetch (or `gh` CLI in bash)      |
| Notion / Google Docs / Confluence          | **Not supported** — authenticated, needs per-user OAuth |

Files land under `{project_root}/.xorial/tmp/{thread_ts}/` — gitignored via `.xorial/tmp/` in the project's `.gitignore`. Old thread folders accumulate; periodic cleanup is up to the operator (future: TTL sweep).

## Speaker attribution

Every agent pass is authored by a speaker. The bot resolves speaker name in order:

1. `users.json[user_id].instance_name` (registered via `/xorial register`)
2. Slack `user_name` (fallback — always present)

The resolved name is threaded into the role prompt, so history entries and commits carry the real person's identity instead of a machine label.

## Running agents

When a role command fires:

1. A parent message is posted in the channel; all streamed output lives in that message's thread.
2. A per-feature `asyncio.Lock` is taken. Second `/xorial intake` on a running feature is rejected.
3. `claude-agent-sdk` runs with `cwd = project.project_root` and `permission_mode = "bypassPermissions"`. The agent has the same tool access as Claude Code locally (Read/Write/Edit/Bash/etc.).
4. Text blocks stream into the thread message via `chat_update` (throttled, rolls over at ~3800 chars).
5. On completion: `git add .xorial && git commit && git push origin <branch>` from `git_push.py`. Commit message includes role, feature, speaker.

If the project has `"auto_push": false`, step 5 is skipped and the thread reports it.

## Scope boundaries

- Only intake / orchestrator / critic run here. Implementer / reviewer / behavior-reviewer stay local.
- Only `.xorial/` changes are committed by the bot. It does not touch application code.
- One writer per project repo — the machine hosting this bot. Local devs rebase on top.

## Troubleshooting

- Bot says _"Workspace T... is not bound"_ → add the workspace to `workspaces.json`.
- Agent pass fails with permission errors → check `permission_mode` in `invoker.py`; confirm `ANTHROPIC_API_KEY` reaches the subprocess via `env`.
- Slack rate limits on `chat_update` → the streamer retries on the next tick. Spikes are expected during long passes and are harmless.
