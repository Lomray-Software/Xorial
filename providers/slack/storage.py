import json
import os
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _path(name: str) -> Path:
    return HERE / f"{name}.json"


def read(name: str) -> dict[str, Any]:
    p = _path(name)
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def write(name: str, data: dict[str, Any]) -> None:
    # Atomic write: temp file in same dir, then rename.
    p = _path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{name}.", suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def bind_channel(channel_id: str, project_key: str, feature: str) -> None:
    data = read("channels")
    data.setdefault("channels", {})[channel_id] = {
        "project": project_key,
        "feature": feature,
    }
    write("channels", data)


def unbind_channel(channel_id: str) -> None:
    data = read("channels")
    channels = data.get("channels", {})
    if channel_id in channels:
        del channels[channel_id]
        write("channels", data)


def set_user(user_id: str, instance_name: str) -> None:
    data = read("users")
    data.setdefault("users", {})[user_id] = {"instance_name": instance_name}
    write("users", data)
