import asyncio
import time
from dataclasses import dataclass, field

from slack_sdk.web.async_client import AsyncWebClient


# Slack's per-message text limit is 4000 chars; leave headroom for the prefix.
MAX_CHARS = 3800
# Minimum seconds between chat_update calls for the same message. Slack
# rate-limits updates; 1s is a safe practical floor.
MIN_EDIT_INTERVAL = 1.0


@dataclass
class SlackStreamer:
    """Buffers text and streams it into a Slack thread by editing the
    current message, rolling over to a new message when the limit is hit.

    Also supports a one-line status footer that is replaced in place — used
    to show live tool activity without bloating the transcript with a line
    per tool call.

    Usage:
        streamer = SlackStreamer(client, channel, thread_ts, prefix="🤖 intake")
        await streamer.start()
        await streamer.set_status("reading files…")
        await streamer.push("first chunk\\n")
        await streamer.clear_status()
        ...
        await streamer.finalize("✓ done")
    """

    client: AsyncWebClient
    channel: str
    thread_ts: str
    prefix: str = ""
    _buffer: str = ""
    _status: str = ""
    _current_ts: str | None = None
    _last_edit: float = 0.0
    _dirty: bool = False
    _flusher: asyncio.Task | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _stopped: bool = False

    async def start(self) -> None:
        resp = await self.client.chat_postMessage(
            channel=self.channel,
            thread_ts=self.thread_ts,
            text=self._render(""),
        )
        self._current_ts = resp["ts"]
        self._flusher = asyncio.create_task(self._flush_loop())

    async def push(self, text: str) -> None:
        if not text:
            return
        async with self._lock:
            # Roll over if we'd overflow the current message.
            if len(self._buffer) + len(text) > MAX_CHARS:
                await self._flush_locked(force=True)
                # Start a fresh message for the remainder.
                resp = await self.client.chat_postMessage(
                    channel=self.channel,
                    thread_ts=self.thread_ts,
                    text=self._render(""),
                )
                self._current_ts = resp["ts"]
                self._buffer = ""
                self._last_edit = time.monotonic()
            self._buffer += text
            self._dirty = True

    async def set_status(self, status: str) -> None:
        """Replace the live status footer (one line, shown below the buffer)."""
        async with self._lock:
            if self._status == status:
                return
            self._status = status
            self._dirty = True

    async def clear_status(self) -> None:
        async with self._lock:
            if not self._status:
                return
            self._status = ""
            self._dirty = True

    async def finalize(self, suffix: str = "") -> None:
        self._stopped = True
        async with self._lock:
            self._status = ""
            if suffix:
                self._buffer += ("\n" if self._buffer and not self._buffer.endswith("\n") else "") + suffix
                self._dirty = True
            await self._flush_locked(force=True)
        if self._flusher:
            self._flusher.cancel()
            try:
                await self._flusher
            except asyncio.CancelledError:
                pass

    async def _flush_loop(self) -> None:
        try:
            while not self._stopped:
                await asyncio.sleep(MIN_EDIT_INTERVAL)
                async with self._lock:
                    if self._dirty:
                        await self._flush_locked()
        except asyncio.CancelledError:
            return

    async def _flush_locked(self, force: bool = False) -> None:
        if not self._current_ts or not self._dirty:
            return
        now = time.monotonic()
        if not force and now - self._last_edit < MIN_EDIT_INTERVAL:
            return
        try:
            await self.client.chat_update(
                channel=self.channel,
                ts=self._current_ts,
                text=self._render(self._buffer),
            )
            self._last_edit = now
            self._dirty = False
        except Exception:
            # Slack 429 / transient errors: drop this edit, next tick retries.
            self._last_edit = now

    def _render(self, body: str) -> str:
        footer = f"\n\n_{self._status}_" if self._status else ""
        core = body + footer
        if self.prefix:
            return f"{self.prefix}\n{core}" if core else self.prefix
        return core or "…"
