import asyncio


class FeatureLocks:
    """Per-feature asyncio.Lock registry.

    Key is "{project_key}:{feature}" so the same feature in two projects
    does not collide.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def get(self, project_key: str, feature: str) -> asyncio.Lock:
        key = f"{project_key}:{feature}"
        async with self._registry_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def is_busy(self, project_key: str, feature: str) -> bool:
        key = f"{project_key}:{feature}"
        lock = self._locks.get(key)
        return lock is not None and lock.locked()
