import json
import logging
import os
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

BOOTSTRAP_MESSAGE = (
    "Start the intake process. "
    "Greet the user briefly and ask the first group of questions."
)


class IntakeSession:
    """
    Manages an interactive intake conversation via Claude API.
    The conductor mediates: user message → Claude → response → Telegram.
    """

    def __init__(self, feature_name: str, config, client):
        self.feature_name = feature_name
        self.config = config
        self.client = client
        self.history: list[dict] = []
        self._system = self._load_system()
        self._confirmed = False  # set to True only after user explicitly confirms

    def _load_system(self) -> str:
        role_path = os.path.join(self.config.xorial_core, "roles", "05-intake.md")
        try:
            with open(role_path) as f:
                content = f.read()
            return self.config.substitute(content)
        except Exception as e:
            logger.error("Could not load intake role: %s", e)
            return "You are an intake agent. Interview the user and create feature.md, context.md, status.json."

    def start(self) -> str:
        """Bootstrap: gets the opening question from the intake agent."""
        return self._call(BOOTSTRAP_MESSAGE)

    def send(self, user_message: str) -> str:
        """Send a user message and get intake agent response."""
        if user_message.strip().lower() == "confirm":
            self._confirmed = True
        return self._call(user_message)

    def is_complete(self) -> bool:
        """
        Intake is complete when:
        1. The agent has written status.json (owner=orchestrator, status=INTAKE_DONE)
        2. AND the user has explicitly confirmed (sent a message after files were created)
        This prevents the session from closing before the user says "yes, looks good".
        """
        return self._confirmed and self._files_exist()

    def _files_exist(self) -> bool:
        status_path = Path(self.config.feature_path(self.feature_name)) / "status.json"
        if not status_path.exists():
            return False
        try:
            with open(status_path) as f:
                s = json.load(f)
            return s.get("owner") == "orchestrator" and s.get("status") == "INTAKE_DONE"
        except Exception:
            return False

    def _call(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=self._system,
                messages=self.history,
            )
            reply = response.content[0].text.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            logger.error("Intake session error: %s", e)
            self.history.pop()  # remove the failed user message
            return "Ошибка. Попробуй ещё раз."
