"""Download Slack-attached files into the project's .xorial/tmp area so
the agent (running with cwd=project_root) can Read them by path.

Slack file events include a `files` array with `url_private_download`.
The Bot token authorizes those downloads via `Authorization: Bearer ...`.
"""

import asyncio
import logging
import os
import re
from pathlib import Path

import httpx

from .config import Project


log = logging.getLogger(__name__)


# Claude Code can Read these natively. Binary/unknown types still download
# so the agent sees the path and can choose what to do.
TEXT_EXTS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ts", ".tsx",
             ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".swift", ".sql",
             ".sh", ".toml", ".ini", ".csv", ".log"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTS = {".pdf"}


def _safe_name(name: str) -> str:
    # Strip anything that could escape the tmp dir or break shells.
    name = os.path.basename(name or "file")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:120] or "file"


def _safe_ts(ts: str) -> str:
    return re.sub(r"[^0-9]", "", ts) or "nots"


def tmp_dir(project: Project, thread_ts: str) -> Path:
    d = Path(project.project_root) / ".xorial" / "tmp" / _safe_ts(thread_ts)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _download_one(
    client: httpx.AsyncClient,
    bot_token: str,
    url: str,
    dest: Path,
) -> bool:
    try:
        async with client.stream(
            "GET",
            url,
            headers={"Authorization": f"Bearer {bot_token}"},
            follow_redirects=True,
            timeout=60.0,
        ) as resp:
            if resp.status_code >= 400:
                log.warning("slack file download failed: %s -> %s", url, resp.status_code)
                return False
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        return True
    except Exception as e:
        log.warning("slack file download error %s: %s", url, e)
        return False


async def download_attachments(
    bot_token: str,
    project: Project,
    thread_ts: str,
    slack_files: list[dict],
) -> list[str]:
    """Returns absolute paths of successfully downloaded files. Empty list
    if none / all failed. Never raises — file ingestion is best-effort."""
    if not slack_files:
        return []
    dest_dir = tmp_dir(project, thread_ts)
    paths: list[str] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        targets: list[tuple[Path, dict]] = []
        for f in slack_files:
            url = f.get("url_private_download") or f.get("url_private")
            if not url:
                continue
            name = _safe_name(f.get("name") or f.get("id") or "file")
            # Prefix with file id to avoid name collisions in the same thread.
            fid = re.sub(r"[^A-Za-z0-9]+", "", f.get("id", ""))[:12]
            dest = dest_dir / (f"{fid}_{name}" if fid else name)
            targets.append((dest, f))
            tasks.append(_download_one(client, bot_token, url, dest))
        results = await asyncio.gather(*tasks, return_exceptions=False)
    for (dest, meta), ok in zip(targets, results):
        if ok:
            paths.append(str(dest))
    return paths


def classify(paths: list[str]) -> dict[str, list[str]]:
    """Group paths by {text, image, pdf, other} for prompt hints."""
    out: dict[str, list[str]] = {"text": [], "image": [], "pdf": [], "other": []}
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in TEXT_EXTS:
            out["text"].append(p)
        elif ext in IMAGE_EXTS:
            out["image"].append(p)
        elif ext in PDF_EXTS:
            out["pdf"].append(p)
        else:
            out["other"].append(p)
    return out
