"""Process-wide counter of in-flight agent passes.

Used by restart_watcher to know when it is safe to self-exit so that
launchd can respawn with new code — we never kill the process while
a role or chat pass is streaming to Slack.
"""


class ActivityTracker:
    def __init__(self) -> None:
        self._count = 0

    def start(self) -> None:
        self._count += 1

    def end(self) -> None:
        if self._count > 0:
            self._count -= 1

    def busy(self) -> bool:
        return self._count > 0

    @property
    def count(self) -> int:
        return self._count


tracker = ActivityTracker()
