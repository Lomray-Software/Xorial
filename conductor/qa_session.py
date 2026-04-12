from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM = """\
You are a concise assistant answering questions about an in-progress software feature.
You have access to the feature's files (plan, decisions, implementation, reviews, etc.).
Answer based only on these files. Be direct and brief.

If the user disagrees with something or says it should work differently, acknowledge it
and end your reply with exactly one line in this format:
SAVE_CORRECTION: <one-sentence summary of what the user wants changed>

Only add SAVE_CORRECTION when the user is expressing a correction or disagreement,
not for regular questions.

Always write the SAVE_CORRECTION summary in English, regardless of the language the user writes in.
"""

_CONFIRM_WORDS = {"confirm", "yes", "ok", "yep", "save"}


class QASession:
    """
    Stateful Q&A conversation about a feature.
    Maintains history so follow-up messages have context.
    Detects user corrections and saves them to human-input.md.
    """

    def __init__(self, feature: str, feature_path: str, client):
        self.feature = feature
        self.feature_path = Path(feature_path)
        self.client = client
        self.history: list[dict] = []
        self._context = self._load_context()
        self._pending_correction: str | None = None

    def _load_context(self) -> str:
        FILE_NAMES = [
            "feature.md", "plan.md", "decisions.md", "handoff.md",
            "implementation.md", "review-final.md", "behavior-review.md",
            "status.json",
        ]
        parts = []
        for fname in FILE_NAMES:
            p = self.feature_path / fname
            if p.exists():
                content = p.read_text().strip()
                if content:
                    parts.append(f"## {fname}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else "(no files found)"

    def ask(self, question: str) -> str:
        """Send a message and get a response. Prompts for confirmation before saving corrections."""
        # If there's a pending correction, check if this message is a confirmation
        if self._pending_correction is not None:
            word = question.strip().lower()
            if word in _CONFIRM_WORDS:
                self._save_correction(self._pending_correction)
                self._pending_correction = None
                return "✅ Correction saved — the next agent will see it."
            else:
                # User didn't confirm — discard and treat this as a new question
                self._pending_correction = None

        # Refresh context on first message of session (files may have changed)
        if not self.history:
            self._context = self._load_context()
            preamble = f"Feature: `{self.feature}`\n\nFiles:\n\n{self._context}\n\n---\n\n"
            first_message = preamble + question
            self.history.append({"role": "user", "content": first_message})
        else:
            self.history.append({"role": "user", "content": question})

        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=SYSTEM,
                messages=self.history,
            )
            reply = response.content[0].text.strip()
            self.history.append({"role": "assistant", "content": reply})

            # Detect correction — ask for confirmation instead of saving immediately
            correction = self._extract_correction(reply)
            if correction:
                self._pending_correction = correction
                # Remove the SAVE_CORRECTION line from the visible reply
                reply = "\n".join(
                    line for line in reply.splitlines()
                    if not line.startswith("SAVE_CORRECTION:")
                ).strip()
                reply += f"\n\n✍️ _Detected correction:_\n> {correction}\n\nReply `confirm` to save, or ask something else to discard."

            return reply
        except Exception as e:
            logger.error("QA session error: %s", e)
            self.history.pop()
            return "Error — try again."

    def _extract_correction(self, reply: str) -> str:
        for line in reply.splitlines():
            if line.startswith("SAVE_CORRECTION:"):
                return line[len("SAVE_CORRECTION:"):].strip()
        return ""

    def _save_correction(self, correction: str) -> None:
        path = self.feature_path / "human-input.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(path, "a") as f:
            f.write(f"\n## {timestamp} — User correction (via Q&A)\n\n{correction}\n")
        logger.info("[%s] Correction saved to human-input.md: %s", self.feature, correction)
