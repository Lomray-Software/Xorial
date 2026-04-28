import asyncio


class ProjectLocks:
    """Per-project mutex + active-pass counter.

    Coordinates concurrent passes within a single project so they do not
    trample each other on the shared git working tree:

      - First pass to enter does `git pull --rebase`. Subsequent passes
        arriving while another is still active skip the pull —
        re-pulling on top of a sibling agent's in-progress edits would
        see those edits as "uncommitted" and abort the pre-pull guard
        for everyone behind it.
      - Commits are serialized through the mutex so two passes cannot
        interleave their `git add` / `git commit` / `git push` calls,
        and each pass `git add`s a feature-scoped path so it does not
        sweep up a sibling's mid-pass writes.
      - View-sync rebuilds project-wide views (kanban, canvas, icons)
        and reads every `status.json`. It refuses to start while any
        feature pass is active, and holds the mutex for its entire run
        so feature passes wait for it before pulling or committing.

    The agent subprocess itself runs OUTSIDE the mutex for feature
    passes — the long, costly LLM step overlaps with siblings. Only the
    git ceremony at the start and end is serialized.
    """

    def __init__(self) -> None:
        self._mutexes: dict[str, asyncio.Lock] = {}
        self._active: dict[str, int] = {}
        self._registry_lock = asyncio.Lock()

    async def mutex(self, project_key: str) -> asyncio.Lock:
        async with self._registry_lock:
            m = self._mutexes.get(project_key)
            if m is None:
                m = asyncio.Lock()
                self._mutexes[project_key] = m
            return m

    def active_count(self, project_key: str) -> int:
        return self._active.get(project_key, 0)

    def inc(self, project_key: str) -> None:
        self._active[project_key] = self._active.get(project_key, 0) + 1

    def dec(self, project_key: str) -> None:
        cur = self._active.get(project_key, 0)
        self._active[project_key] = max(0, cur - 1)
