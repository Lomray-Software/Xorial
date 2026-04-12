from __future__ import annotations

import threading
from dataclasses import dataclass, field
from queue import Queue


@dataclass
class ConductorState:
    # feature_name → last known status dict
    last_status: dict[str, dict] = field(default_factory=dict)

    # features currently waiting for human (/resume)
    # feature_name → Event that gets set when /resume is received
    paused: dict[str, threading.Event] = field(default_factory=dict)

    # features ready for agent processing (sequential queue)
    queue: Queue = field(default_factory=Queue)

    # feature currently being processed by an agent
    running: str | None = None

    # active intake session (only one at a time)
    # type: IntakeSession | None — stored as Any to avoid circular import
    active_intake: object = None

    # active Q&A sessions per feature — type: dict[str, QASession]
    active_qa: dict = field(default_factory=dict)

    # per-feature auto-iteration counter — resets on human /resume
    auto_iterations: dict = field(default_factory=dict)

    # protects last_status, paused, running, active_intake
    lock: threading.Lock = field(default_factory=threading.Lock)

    def is_paused(self, feature: str) -> bool:
        with self.lock:
            return feature in self.paused

    def pause(self, feature: str) -> threading.Event:
        event = threading.Event()
        with self.lock:
            self.paused[feature] = event
        return event

    def resume(self, feature: str) -> bool:
        """Returns True if feature was paused and got resumed."""
        with self.lock:
            event = self.paused.pop(feature, None)
        if event:
            event.set()
            return True
        return False

    def resume_any(self) -> list[str]:
        """Resume all paused features. Returns list of resumed feature names."""
        with self.lock:
            names = list(self.paused.keys())
            for event in self.paused.values():
                event.set()
            self.paused.clear()
        return names

    def get_all_statuses(self) -> dict[str, dict]:
        with self.lock:
            return dict(self.last_status)

    def update_status(self, feature: str, status: dict) -> None:
        with self.lock:
            self.last_status[feature] = status

    def increment_iterations(self, feature: str) -> int:
        """Increment auto-iteration counter. Returns new count."""
        with self.lock:
            count = self.auto_iterations.get(feature, 0) + 1
            self.auto_iterations[feature] = count
            return count

    def reset_iterations(self, feature: str) -> None:
        """Reset auto-iteration counter (call on human /resume)."""
        with self.lock:
            self.auto_iterations.pop(feature, None)

    def get_iterations(self, feature: str) -> int:
        with self.lock:
            return self.auto_iterations.get(feature, 0)
