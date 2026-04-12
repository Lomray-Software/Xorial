import json
import logging

logger = logging.getLogger(__name__)

SYSTEM = """You are the assistant for Xorial conductor — an AI-driven software workflow system.

The project owner sends you natural language messages. Your job is to understand what they want and return the right action.

Current feature statuses:
{statuses}

Paused features (waiting for human input or review):
{paused}

Available actions:
- resume: resume a specific paused feature
- new: start intake for a new feature/bugfix/refactor/chore
- status: show status of all features
- artifacts: user wants to see screenshots, videos, or other files from the latest run of a feature
- qa: user is asking a question about a feature — what was done, why, what changed, current state, decisions, etc.
- reply: you cannot determine the action clearly — ask a short clarifying question

Rules:
- If the message clearly maps to one action — return it directly, no confirmation needed.
- If ambiguous — return "reply" with a focused clarifying question (mention the specific ambiguity).
- Never guess a feature name if multiple are paused — ask which one.
- "new" requires a type (feat/fix/refactor/chore) and a short kebab-case name. If missing, ask for them via "reply".
- "qa": use when the user asks anything about implementation details, decisions, progress, changes, reasons — even if phrased casually. Include the feature name (pick the most relevant one if multiple exist) and the question verbatim.
- "artifacts": use when the user asks to see/send/attach screenshots, videos, logs, or files from a feature run.
- Feature IDs are in "type/name" format, e.g. "feat/k-id", "fix/login-crash".

Return ONLY valid JSON. No markdown. No explanation. Examples:
{{"action": "resume", "feature": "feat/k-id"}}
{{"action": "new", "type": "fix", "name": "auth-crash"}}
{{"action": "status"}}
{{"action": "artifacts", "feature": "feat/k-id"}}
{{"action": "qa", "feature": "feat/k-id", "question": "why was the country detection implemented this way?"}}
{{"action": "reply", "text": "Which feature should I resume? Both feat/k-id and fix/login are paused."}}
"""


class Dispatcher:
    def __init__(self, client, state):
        self.client = client
        self.state = state

    def process(self, message: str) -> dict:
        statuses = self.state.get_all_statuses()
        paused = list(self.state.paused.keys())

        status_lines = [
            f"- {name}: owner={s.get('owner')} stage={s.get('stage')} status={s.get('status')}"
            for name, s in sorted(statuses.items())
        ] or ["none"]

        system = SYSTEM.format(
            statuses="\n".join(status_lines),
            paused=", ".join(paused) if paused else "none",
        )

        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": message}],
            )
            text = response.content[0].text.strip()
            action = json.loads(text)
            logger.info("Dispatcher: %s", text)
            return action
        except json.JSONDecodeError as e:
            logger.error("Dispatcher returned invalid JSON: %s", e)
            return {"action": "reply", "text": "Не понял — попробуй /status или /new <type> <name>."}
        except Exception as e:
            logger.error("Dispatcher error: %s", e)
            return {"action": "reply", "text": "Ошибка при обработке. Попробуй ещё раз."}
