# Creating the Slack app

One-time setup for the workspace admin. ~5 minutes. At the end you'll have three values to paste into `config.json`: `bot_token`, `app_token`, `signing_secret`.

---

## 1. Create the app

1. Go to <https://api.slack.com/apps> → **Create New App** → **From scratch**.
2. Name: `Xorial` (or whatever). Pick the workspace.

## 2. Enable Socket Mode

Settings → **Socket Mode** → toggle on.

When prompted, **generate an App-Level Token** with scope `connections:write`. Copy the `xapp-...` token — this is `app_token` in `config.json`.

Socket Mode means the bot connects outbound to Slack over WebSocket. No public URL, no ngrok, works from a Mac M1 behind NAT.

## 3. Bot Token Scopes

Features → **OAuth & Permissions** → **Scopes** → **Bot Token Scopes**. Add all of:

| Scope               | Why                                             |
|---------------------|-------------------------------------------------|
| `app_mentions:read` | receive `@xorial` events                        |
| `channels:history`  | read replies in public channels                 |
| `channels:read`     | receive `member_joined_channel` for public channels (welcome post) |
| `groups:history`    | read replies in private channels                |
| `groups:read`       | receive `member_joined_channel` for private channels (welcome post) |
| `chat:write`        | post + edit streaming messages                  |
| `commands`          | register the `/xorial` slash command            |
| `files:read`        | download attachments users drop into a thread   |
| `users:read`        | look up display names when a user isn't registered |
| `channels:manage`   | archive public channels on `/xorial ship`           |
| `groups:write`      | archive private channels on `/xorial ship`          |

No user scopes needed.

## 4. Slash command

Features → **Slash Commands** → **Create New Command**:

| Field          | Value                                                    |
|----------------|----------------------------------------------------------|
| Command        | `/xorial`                                                |
| Request URL    | (leave blank — Socket Mode does not use it)              |
| Short descr.   | `Run Xorial intake / orchestrator / critic`              |
| Usage hint     | `help \| new feat <name> \| intake \| orchestrate \| critic` |
| Escape channels / users / links | **off** (we parse raw text)             |

## 5. Event Subscriptions

Features → **Event Subscriptions** → toggle on. Request URL is not needed in Socket Mode.

**Subscribe to bot events:**

- `app_mention`
- `message.channels`
- `message.groups`
- `member_joined_channel` — so the bot can post a welcome when invited

(`message.im` and `message.mpim` are not needed — Xorial doesn't do DM flows.)

## 6. Install the app

Settings → **Install App** → **Install to Workspace** → approve.

Copy the **Bot User OAuth Token** (`xoxb-...`) — this is `bot_token` in `config.json`.

## 7. Signing secret

Settings → **Basic Information** → App Credentials → **Signing Secret** → copy. This is `signing_secret` in `config.json`.

Not strictly required in Socket Mode (no inbound HTTP to verify) but slack_bolt wants it for the `AsyncApp` constructor. Any non-empty string works locally; use the real one for correctness.

## 8. Workspace ID (for workspaces.json)

Open any channel in Slack web → URL is `https://app.slack.com/client/T01ABCDE.../C01XYZ...`. The `T...` segment is the workspace ID. Copy it into `workspaces.json`:

```json
{ "workspaces": { "T01ABCDE": { "project": "myapp" } } }
```

(You can also run `curl -H "Authorization: Bearer <bot_token>" https://slack.com/api/auth.test` — the response's `team_id` is the same value.)

## 9. Invite the bot

In the Slack channel you want to use, run:

```
/invite @Xorial
```

Then run `/xorial help` — if the bot replies, you're done.

## 10. Pick how the bundled Claude Code CLI authenticates

The Xorial bot runs roles via the Claude Agent SDK, which shells out to the bundled Claude Code CLI. You choose how that CLI authenticates via `auth_mode` in `config.json`:

### `"auth_mode": "api"` (default)

Billed per token against the Anthropic API. The bot injects `ANTHROPIC_API_KEY` (from `config.json`'s `anthropic_api_key`) into the SDK subprocess.

Setup: fill in `anthropic_api_key` in `config.json`. Nothing else to do.

### `"auth_mode": "subscription"`

Billed against the Claude Pro/Max subscription quota of the user running the bot. The bot strips `ANTHROPIC_API_KEY` from the subprocess env so the CLI falls back to OAuth creds stored in `~/.claude/`.

Setup — **do this before starting the bot**:

```bash
# As the same OS user that will run the bot (e.g. `janitor` on the deploy host):
claude login
# → interactive browser flow, drops creds into ~/.claude/
```

Then set `"auth_mode": "subscription"` in `config.json`. You can leave `anthropic_api_key` unset or empty.

Swap between modes freely — it's just a config field; restart the bot to pick up the change.

### Which to pick

- Solo / dogfooding on your own Max subscription → `subscription` (no per-token burn).
- Team deployment where the bot should not eat one person's subscription → `api` with a dedicated workspace key.

---

## Troubleshooting

- **`/xorial` returns "dispatch_failed"** → bot not running, or Socket Mode not connected. Check `run.sh` logs.
- **Slash command not showing up** → reinstall the app (Install App → Reinstall).
- **Bot doesn't react to @mentions** → missing `app_mentions:read` scope, or the app wasn't reinstalled after adding scopes.
- **Bot doesn't see replies in a thread** → missing `channels:history` / `groups:history`, or the bot was never invited into the channel.
- **File attachments not reaching the agent** → missing `files:read`, or the file is in a private channel the bot isn't in.

## Adding more workspaces

For each additional workspace, either:
- Install the same app into that workspace via the **Manage Distribution** (Slack Marketplace–style) flow, or
- Create a separate app per workspace and run multiple provider instances with different `app_token`s.

Single-app + distribution is the scalable path; two-apps is fine for a two-team MVP.
