"""Persistent mapping thread_ts -> active agent session.

A thread lifecycle:
  /xorial intake   ->  parent message posted; we record the thread with
                       an empty session_id (the first pass fills it in).
  human replies    ->  events.py finds the thread, calls run_pass with
                       resume=session_id, updates session_id with the new
                       one the agent returns on ResultMessage.

The file `threads.json` is the durable state — restarts preserve sessions.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from . import storage

HERE = Path(__file__).resolve().parent


class ThreadEntry(TypedDict, total=False):
    channel: str
    project: str
    feature: str
    role: str
    session_id: str
    last_speaker: str
    started_at: str
    updated_at: str


def _key(channel_id: str, thread_ts: str) -> str:
    return f"{channel_id}:{thread_ts}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(channel_id: str, thread_ts: str) -> ThreadEntry | None:
    data = storage.read("threads").get("threads", {})
    return data.get(_key(channel_id, thread_ts))


def start(
    channel_id: str,
    thread_ts: str,
    project: str,
    feature: str,
    role: str,
    speaker: str,
) -> None:
    data = storage.read("threads")
    threads = data.setdefault("threads", {})
    threads[_key(channel_id, thread_ts)] = {
        "channel": channel_id,
        "project": project,
        "feature": feature,
        "role": role,
        "session_id": "",
        "last_speaker": speaker,
        "started_at": _now(),
        "updated_at": _now(),
    }
    storage.write("threads", data)


def update_session(
    channel_id: str,
    thread_ts: str,
    session_id: str,
    speaker: str | None = None,
) -> None:
    data = storage.read("threads")
    threads = data.setdefault("threads", {})
    entry = threads.get(_key(channel_id, thread_ts))
    if entry is None:
        return
    if session_id:
        entry["session_id"] = session_id
    if speaker:
        entry["last_speaker"] = speaker
    entry["updated_at"] = _now()
    storage.write("threads", data)


def close(channel_id: str, thread_ts: str) -> None:
    data = storage.read("threads")
    threads = data.setdefault("threads", {})
    threads.pop(_key(channel_id, thread_ts), None)
    storage.write("threads", data)


def drop_for_feature(project_key: str, feature: str) -> int:
    """Purge every thread entry tied to this project's feature.
    Returns number of entries removed."""
    data = storage.read("threads")
    threads = data.setdefault("threads", {})
    to_drop = [
        k for k, e in threads.items()
        if e.get("project") == project_key and e.get("feature") == feature
    ]
    for k in to_drop:
        del threads[k]
    if to_drop:
        storage.write("threads", data)
    return len(to_drop)
