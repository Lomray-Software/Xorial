from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

from router import AgentType, Route

logger = logging.getLogger(__name__)

MAX_RETRIES = 1
HANG_CHECK_INTERVAL = 30   # seconds between activity polls
MAX_TOTAL_SECONDS = 7200   # 2-hour absolute ceiling (regardless of activity)

# Currently running agent process — used by kill_current_agent()
_current_proc: subprocess.Popen | None = None


def _pid_file_path(config) -> Path:
    return Path(config.project_root) / ".xorial" / "agent.pid"


def pid_file_path(config) -> str:
    return str(_pid_file_path(config))


def kill_current_agent() -> None:
    """Kill the currently running agent (called from signal handler on shutdown)."""
    global _current_proc
    if _current_proc is not None:
        try:
            _current_proc.kill()
            _current_proc.wait()
            logger.info("Killed current agent (pid=%d)", _current_proc.pid)
        except OSError:
            pass
        _current_proc = None


def kill_stale_agent(config) -> None:
    """On startup: kill any agent left over from a previous crashed conductor."""
    pid_path = _pid_file_path(config)
    if not pid_path.exists():
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGKILL)
        logger.warning("Killed stale agent from previous run (pid=%d)", pid)
    except (ValueError, ProcessLookupError, PermissionError):
        pass  # already gone or invalid
    try:
        pid_path.unlink()
    except OSError:
        pass


USAGE_LIMIT_PATTERNS = [
    "you've hit your usage limit",
    "usage limit",
    "rate limit exceeded",
]


def _usage_limit_info(log_path: Path) -> tuple[bool, str]:
    """
    Check whether the last agent run failed due to a subscription usage/rate limit.
    Returns (is_limit_error, retry_time_str).
    retry_time_str is e.g. "3:42 AM" if parseable from the error, else "".
    """
    import re
    try:
        tail = log_path.read_text(errors="replace")[-2000:]
        lower = tail.lower()
        if not any(p in lower for p in USAGE_LIMIT_PATTERNS):
            return False, ""
        match = re.search(r"try again at\s+(\d+:\d+\s*(?:am|pm))", tail, re.IGNORECASE)
        retry_time = match.group(1).strip() if match else ""
        return True, retry_time
    except OSError:
        return False, ""


def _is_usage_limit_error(log_path: Path) -> bool:
    return _usage_limit_info(log_path)[0]


def _build_env(config, inject_api_key: bool = False) -> dict | None:
    """
    Returns None (inherit parent env) for subscription mode.
    Returns env with API keys injected when falling back after a usage limit.
    """
    if not inject_api_key:
        return None  # subscription mode — inherit parent env
    env = os.environ.copy()
    if config.anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = config.anthropic_api_key
    if config.openai_api_key:
        env["OPENAI_API_KEY"] = config.openai_api_key
    return env


def spawn_agent(config, route: Route, prompt: str, dry_run: bool = False) -> tuple[bool, str]:
    """
    Spawns the agent with the given prompt.
    Monitors log-file activity — kills and retries if silent for hang_timeout_minutes.
    Returns (success, failure_reason). failure_reason is "" on success.
    """
    cmd = _build_command(route, prompt)

    if dry_run:
        logger.info("[DRY RUN] Would run: %s", " ".join(cmd))
        return True, ""

    feature_name = getattr(config, "_current_feature", "unknown")
    log_path = _agent_log_path(config, feature_name)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    hang_timeout = (config.hang_timeout_minutes or 0) * 60
    pid_path = _pid_file_path(config)
    api_key_fallback = False   # flipped after usage-limit failure
    model_fallback = None      # set to fallback model string after usage-limit failure

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            parts = []
            if api_key_fallback:
                parts.append("API key")
            if model_fallback:
                parts.append(f"model={model_fallback}")
            label = " + ".join(parts) if parts else "retry"
            logger.warning("Usage limit hit — retrying with %s (attempt %d)...", label, attempt + 1)
            time.sleep(5)

        logger.info(
            "Spawning agent: %s (attempt %d) — log: %s",
            route.role_file, attempt + 1, log_path,
        )

        try:
            with open(log_path, "a") as log_f:
                log_f.write(f"\n{'='*60}\n")
                log_f.write(f"attempt {attempt + 1} — {datetime.now().isoformat()}\n")
                log_f.write(f"cmd: {' '.join(cmd)}\n")
                log_f.write(f"{'='*60}\n\n")
                log_f.flush()

            attempt_cmd = _build_command(route, prompt, model_override=model_fallback) if model_fallback else cmd
            rc, hung = _run_with_hang_detection(
                cmd=attempt_cmd,
                log_path=log_path,
                input_data=prompt.encode() if route.agent_type == AgentType.CODEX else None,
                hang_timeout=hang_timeout,
                pid_path=pid_path,
                env=_build_env(config, inject_api_key=api_key_fallback),
            )

            if hung:
                logger.error(
                    "Agent hung (no log activity for %d min) — see %s",
                    config.hang_timeout_minutes, log_path,
                )
                continue  # retry

            if rc == 0:
                return True, ""

            logger.error("Agent exited with code %d — see %s", rc, log_path)

            # Usage limit: apply available fallbacks once, then give up.
            is_limit, retry_time = _usage_limit_info(log_path)
            if is_limit:
                fallback_applied = False

                if not api_key_fallback and config.api_key_fallback:
                    has_key = (
                        route.agent_type == AgentType.CLAUDE and bool(config.anthropic_api_key)
                    ) or (
                        route.agent_type == AgentType.CODEX and bool(config.openai_api_key)
                    )
                    if has_key:
                        api_key_fallback = True
                        fallback_applied = True

                if model_fallback is None and config.usage_limit_fallback_model:
                    agent_key = "claude" if route.agent_type == AgentType.CLAUDE else "codex"
                    fb_model = config.usage_limit_fallback_model.get(agent_key, "")
                    if fb_model:
                        model_fallback = fb_model
                        fallback_applied = True

                if fallback_applied:
                    continue  # retry with whatever fallbacks were just enabled

                # No fallbacks available or all already tried
                reason = "Usage limit hit"
                if retry_time:
                    reason += f" — resets at {retry_time}"
                return False, reason

        except Exception as e:
            logger.error("Agent spawn error: %s", e)

    return False, f"Agent {route.role_file} failed after retries"


def set_current_feature(config, feature_name: str) -> None:
    """Called by main loop before spawning so the log path is scoped to the feature."""
    config._current_feature = feature_name


def _run_with_hang_detection(
    cmd: list[str],
    log_path: Path,
    input_data: bytes | None,
    hang_timeout: int,
    pid_path: Path | None = None,
    env: dict | None = None,
) -> tuple[int | None, bool]:
    """
    Run cmd, appending stdout/stderr to log_path.
    Polls every HANG_CHECK_INTERVAL seconds.
    If the log file shows no new bytes for hang_timeout seconds → kill → return (None, True).
    Returns (returncode, hung).
    """
    global _current_proc

    with open(log_path, "a") as log_f:
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=log_f,
            stdin=subprocess.PIPE if input_data else None,
            env=env,
        )

    _current_proc = proc
    if pid_path is not None:
        try:
            pid_path.write_text(str(proc.pid))
        except OSError:
            pass

    if input_data:
        try:
            proc.stdin.write(input_data)
            proc.stdin.close()
        except OSError:
            pass  # process may have exited already

    last_size = log_path.stat().st_size
    last_activity = time.time()
    started_at = time.time()

    try:
        while True:
            time.sleep(HANG_CHECK_INTERVAL)

            rc = proc.poll()
            if rc is not None:
                return rc, False

            # Absolute ceiling
            if time.time() - started_at > MAX_TOTAL_SECONDS:
                logger.error("Agent exceeded absolute 2-hour limit — killing")
                proc.kill()
                proc.wait()
                return None, True

            # Activity check
            if hang_timeout > 0:
                try:
                    current_size = log_path.stat().st_size
                except OSError:
                    current_size = last_size

                if current_size > last_size:
                    last_size = current_size
                    last_activity = time.time()
                elif time.time() - last_activity > hang_timeout:
                    proc.kill()
                    proc.wait()
                    return None, True
    finally:
        _current_proc = None
        if pid_path is not None:
            try:
                pid_path.unlink()
            except OSError:
                pass


def _agent_log_path(config, feature_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(config.feature_path(feature_name)) / "tmp" / "agent-runs" / f"{timestamp}.log"


def _build_command(route: Route, prompt: str, model_override: str | None = None) -> list[str]:
    model = model_override or route.model
    if route.agent_type == AgentType.CLAUDE:
        return [
            "claude",
            "--model", model or "claude-opus-4-6",
            "--dangerously-skip-permissions",
            "--print",
            prompt,
        ]

    if route.agent_type == AgentType.CODEX:
        cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"]
        if model:
            cmd += ["--model", model]
        if route.reasoning:
            cmd += ["-c", f'model_reasoning_effort="{route.reasoning}"']
        cmd.append("-")
        return cmd

    raise ValueError(f"Unsupported agent type: {route.agent_type}")
