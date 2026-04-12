from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class VoiceTranscriptionError(Exception):
    """Raised when voice transcription fails — carries a user-facing reason."""


class TelegramBot:
    def __init__(self, token: str, chat_id: str, openai_api_key: str = ""):
        self.token = token
        self.chat_id = chat_id
        self._enabled = bool(token and chat_id)
        self._last_update_id = 0
        self._openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")

        if not self._enabled:
            logger.info("Telegram not configured — notifications disabled, using keyboard fallback")

    # ── Sending ────────────────────────────────────────────────────────────

    def send(self, text: str, attachments: list[str] | None = None) -> None:
        if not self._enabled:
            logger.info("[TELEGRAM] %s", text)
            return

        if not REQUESTS_AVAILABLE:
            logger.warning("requests not installed — cannot send Telegram message")
            return

        self._send_message(text)
        for path in (attachments or []):
            self._send_file(path)

    # ── Command polling (runs in background thread) ─────────────────────────

    def poll_commands(
        self,
        on_resume: Callable[[str | None], None],   # arg: feature name or None (resume any)
        on_status: Callable[[], str],              # returns formatted status text
        on_new: Callable[[str], None],             # arg: raw "feature my-name" tail (without /new)
        on_message: Callable[[str], None],         # arg: any free-form message (dispatcher)
        stop_event=None,
    ) -> None:
        """
        Polls Telegram for commands indefinitely.
        Call in a daemon thread.

        Explicit commands:
          /resume [feature]    — resume a paused feature (or all if no arg)
          /status / /list      — show status of all features
          /new <type> <name>   — start intake for a new feature/bugfix/refactor/chore

        Everything else → on_message (dispatcher or active intake session)
        """
        import time

        KNOWN_COMMANDS = {"/resume", "/status", "/list", "/new"}

        fail_backoff = 0  # seconds to wait after consecutive failures

        while not (stop_event and stop_event.is_set()):
            if not self._enabled or not REQUESTS_AVAILABLE:
                time.sleep(5)
                continue

            if fail_backoff > 0:
                time.sleep(fail_backoff)

            updates = self._get_updates()
            if updates is None:
                # Network error — back off: 5 → 15 → 30 → 60 → 120 → 300 max
                fail_backoff = min(fail_backoff * 2 + 5, 300) if fail_backoff else 5
                continue

            # Successful response (possibly empty list — no new messages)
            fail_backoff = 0
            if not updates:
                time.sleep(1)
                continue

            for update in updates:
                self._last_update_id = update["update_id"] + 1
                try:
                    self._handle_update(update, on_resume, on_status, on_new, on_message)
                except Exception as e:
                    logger.error("Error handling Telegram update: %s", e, exc_info=True)

            # no sleep here — loop immediately to check for next update

    def _handle_update(self, update, on_resume, on_status, on_new, on_message) -> None:
        msg = update.get("message", {})
        text = msg.get("text", "").strip()

        # Voice message — transcribe first
        if not text and msg.get("voice"):
            try:
                text = self._transcribe_voice(msg["voice"])
                logger.info("Voice transcribed: %s", text[:80])
            except VoiceTranscriptionError as e:
                self.send(f"🎤 Can't transcribe voice: {e}\n\nPlease type your message.")
                return

        if not text:
            return

        # Extract reply context if the user replied to a specific message
        reply_prefix = ""
        reply_to = msg.get("reply_to_message", {})
        if reply_to:
            replied_text = reply_to.get("text", "").strip()
            if replied_text:
                preview = replied_text[:300] + "…" if len(replied_text) > 300 else replied_text
                reply_prefix = f"[Replying to: \"{preview}\"]\n\n"

        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "/resume":
            feature = parts[1] if len(parts) > 1 else None
            on_resume(feature)

        elif cmd in ("/status", "/list"):
            self.send(on_status())

        elif cmd == "/new":
            tail = " ".join(parts[1:]) if len(parts) > 1 else ""
            on_new(tail)

        else:
            # Free-form text or transcribed voice → dispatcher or intake
            on_message(reply_prefix + text)

    # ── Blocking wait (for human review pauses) ────────────────────────────

    def wait_for_resume(self, feature: str, resume_event=None) -> None:
        """
        Waits until resume_event is set (by poll_commands) or keyboard ENTER.
        resume_event is a threading.Event set by on_resume callback.
        """
        if not self._enabled or not REQUESTS_AVAILABLE:
            input(f"\n[Conductor paused — {feature}] Press ENTER to resume...\n")
            return

        if resume_event is not None:
            # Block until poll_commands thread sets the event
            resume_event.wait()
        else:
            # Fallback: spin-wait
            import time
            logger.info("Waiting for /resume %s from Telegram...", feature)
            while True:
                time.sleep(1)

    # ── Internal ───────────────────────────────────────────────────────────

    def _send_message(self, text: str) -> None:
        import requests as req
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = req.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            data = resp.json()
            if not data.get("ok"):
                # Markdown parse error — retry without formatting
                logger.warning("Telegram send failed (Markdown error): %s — retrying as plain text", data.get("description"))
                resp2 = req.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                }, timeout=10)
                if not resp2.json().get("ok"):
                    logger.error("Telegram send failed: %s", resp2.json().get("description"))
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)

    def _send_file(self, file_path: str) -> None:
        import requests as req
        if not os.path.exists(file_path):
            return

        ext = Path(file_path).suffix.lower()
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            name = Path(file_path).name

            if ext in (".png", ".jpg", ".jpeg"):
                url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
                req.post(url, data={"chat_id": self.chat_id},
                         files={"photo": (name, data)}, timeout=30)
            elif ext in (".mp4", ".mov"):
                url = f"https://api.telegram.org/bot{self.token}/sendVideo"
                req.post(url, data={"chat_id": self.chat_id},
                         files={"video": (name, data)}, timeout=60)
            else:
                url = f"https://api.telegram.org/bot{self.token}/sendDocument"
                req.post(url, data={"chat_id": self.chat_id},
                         files={"document": (name, data)}, timeout=30)
        except Exception as e:
            logger.warning("Telegram file send failed (%s): %s", file_path, e)

    def _transcribe_voice(self, voice: dict) -> str:
        """
        Download voice message and transcribe via OpenAI Whisper.
        Raises VoiceTranscriptionError with a user-facing reason on any failure.
        """
        if not REQUESTS_AVAILABLE:
            raise VoiceTranscriptionError("requests package not installed")

        if not self._openai_api_key:
            raise VoiceTranscriptionError("OpenAI API key not configured")

        import requests as req
        import tempfile

        try:
            # Get file path from Telegram
            file_id = voice["file_id"]
            r = req.get(
                f"https://api.telegram.org/bot{self.token}/getFile",
                params={"file_id": file_id},
                timeout=10,
            )
            file_path = r.json()["result"]["file_path"]

            # Download audio
            audio_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            audio_data = req.get(audio_url, timeout=30).content

            # Write to temp file
            suffix = "." + file_path.split(".")[-1] if "." in file_path else ".ogg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name

            # Transcribe via Whisper
            with open(tmp_path, "rb") as f:
                resp = req.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._openai_api_key}"},
                    data={"model": "whisper-1"},
                    files={"file": (Path(tmp_path).name, f)},
                    timeout=60,
                )
            Path(tmp_path).unlink(missing_ok=True)

            if resp.status_code == 429:
                logger.error("Whisper API 429: quota exceeded")
                raise VoiceTranscriptionError("OpenAI quota exceeded — top up your balance at platform.openai.com")
            if resp.status_code == 401:
                logger.error("Whisper API 401: invalid key")
                raise VoiceTranscriptionError("OpenAI API key is invalid")
            if resp.status_code != 200:
                logger.error("Whisper API error %d: %s", resp.status_code, resp.text[:300])
                raise VoiceTranscriptionError(f"Whisper API error {resp.status_code}")

            text = resp.json().get("text", "")
            if not text:
                raise VoiceTranscriptionError("Whisper returned empty transcription")
            return text

        except VoiceTranscriptionError:
            raise
        except Exception as e:
            logger.error("Voice transcription failed: %s", e)
            raise VoiceTranscriptionError(f"Transcription error: {e}")

    def _get_updates(self) -> list[dict] | None:
        """Returns list of updates on success, None on network error."""
        import requests as req
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            resp = req.get(url, params={"offset": self._last_update_id, "timeout": 5}, timeout=10)
            return resp.json().get("result", [])
        except Exception as e:
            logger.warning("Telegram getUpdates failed: %s", e)
            return None


def collect_artifacts(feature_path: str) -> list[str]:
    """Collect screenshots and videos from the latest tmp/run-NNN/ folder."""
    tmp_dir = Path(feature_path) / "tmp"
    if not tmp_dir.exists():
        return []

    run_dirs = sorted(tmp_dir.glob("run-*/"), key=lambda p: p.name, reverse=True)
    if not run_dirs:
        return []

    latest = run_dirs[0]
    artifacts = []
    for ext in ("*.png", "*.jpg", "*.mp4", "*.mov"):
        artifacts.extend(str(p) for p in sorted(latest.rglob(ext)))

    return artifacts[:10]
