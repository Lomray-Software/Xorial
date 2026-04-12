#!/usr/bin/env python3
"""
Xorial Conductor — multi-feature automated AI workflow driver.

Usage:
    ./.xorial/run.sh [--dry-run]
    python main.py --project <path> [--dry-run]

Telegram commands:
    /status           — show status of all watched features
    /list             — alias for /status
    /resume [feature] — resume paused feature (or all if no arg)
    /new <type> <name>— start intake for a new feature/bugfix/refactor/chore

Free-form messages:
    Anything else goes through the Dispatcher (understands natural language)
    or to the active Intake session.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue as _queue_module
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config import load_config
from dispatcher import Dispatcher
from intake_session import IntakeSession
from pipeline import load_pipeline
from router import AgentType, VALID_TYPES, resolve, apply_agent_config
from prompts import build_prompt
from runner import spawn_agent, set_current_feature, kill_current_agent, kill_stale_agent, pid_file_path
from state import ConductorState
from telegram import TelegramBot, collect_artifacts
from canvas_map import rebuild as rebuild_canvas
from kanban import rebuild as rebuild_kanban
from watcher import watch_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _footer(config) -> str:
    return f"_via {config.instance_name}_"


def format_status(config, state: ConductorState) -> str:
    statuses = state.get_all_statuses()
    if not statuses:
        return f"📋 *Feature Status*\n\n_No features being watched yet._"

    with state.lock:
        running = state.running
        active_intake = state.active_intake

    lines = ["📋 *Feature Status*", "━━━━━━━━━━━━━━━"]
    for name, s in sorted(statuses.items()):
        owner = s.get("owner", "?")
        stage = s.get("stage", "?")
        status = s.get("status", "?")
        if name == running:
            marker = " 🔄"
            status_display = "▶ agent running"
        elif state.is_paused(name):
            marker = " ⏸"
            status_display = f"⏸ waiting for /resume"
        else:
            marker = ""
            status_display = status
        iters = state.get_iterations(name)
        iter_line = f"\n   🔁 {iters}/{config.max_auto_iterations} iterations" if iters > 0 else ""
        lines.append(f"\n📦 `{name}`{marker}\n   👤 {owner} · {stage}\n   📊 {status_display}{iter_line}")

    if active_intake:
        lines.append(f"\n💬 _Intake active:_ `{active_intake.feature_name}`")

    lines.append(f"\n{_footer(config)}")
    return "\n".join(lines)


def _now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _seconds_until_retry(failure_reason: str) -> float | None:
    """Parse 'resets at H:MM AM/PM' from failure_reason → seconds until then. None if unparseable."""
    import re
    from datetime import datetime, timedelta
    match = re.search(r"resets at\s+(\d+:\d+\s*(?:AM|PM))", failure_reason, re.IGNORECASE)
    if not match:
        return None
    try:
        now = datetime.now()
        target = datetime.strptime(match.group(1).strip().upper(), "%I:%M %p").replace(
            year=now.year, month=now.month, day=now.day,
        )
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()
    except ValueError:
        return None


def _patch_status(feature_path: str, patch: dict) -> None:
    """Merge patch into status.json, always updating last_updated."""
    status_path = Path(feature_path) / "status.json"
    try:
        with open(status_path) as f:
            current = json.load(f)
        current.update(patch)
        current["last_updated"] = _now_str()
        with open(status_path, "w") as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        logger.error("Could not update status.json: %s", e)


def set_blocked(feature_path: str, reason: str) -> None:
    _patch_status(feature_path, {"status": "BLOCKED", "blocked_reason": reason})


def set_in_progress(feature_path: str, role: str) -> None:
    _patch_status(feature_path, {"status": "IN_PROGRESS", "blocked_reason": ""})



def reset_stale_in_progress(work_dir: str, pid_file: str) -> list[str]:
    """
    On startup: find any feature stuck in IN_PROGRESS with no live agent process
    and reset it to BLOCKED so the conductor can handle it normally.

    Called after kill_stale_agent, so the orphan process is already gone.
    The PID file check is a safety guard — if somehow a live process still holds
    the PID file, we skip the reset rather than corrupt a running agent's state.

    Returns list of feature IDs (type/name) that were reset.
    """
    import glob as _glob

    # If PID file still exists, a live process is using it — do not touch anything.
    if os.path.exists(pid_file):
        return []

    reset = []
    for status_file in _glob.glob(os.path.join(work_dir, "*", "*", "status.json")):
        try:
            with open(status_file) as f:
                data = json.load(f)
            if data.get("status") == "IN_PROGRESS":
                feature = os.path.relpath(os.path.dirname(status_file), work_dir)
                data["status"] = "BLOCKED"
                data["blocked_reason"] = "Conductor restarted while agent was running"
                with open(status_file, "w") as f:
                    json.dump(data, f, indent=2)
                reset.append(feature)
        except (OSError, json.JSONDecodeError):
            pass
    return reset


def _make_anthropic_client(config):
    try:
        import anthropic
        api_key = config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("anthropic_api_key not set — dispatcher and intake unavailable")
            return None
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic package not installed — run: pip install -r conductor/requirements.txt")
        return None
    except Exception as e:
        logger.warning("Could not create Anthropic client: %s", e)
        return None


def main():
    parser = argparse.ArgumentParser(description="Xorial Conductor")
    parser.add_argument("--project", default=os.getcwd(), help="Project root (default: cwd)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    args = parser.parse_args()

    project_root = os.path.abspath(args.project)
    dry_run = args.dry_run

    try:
        config = load_config(project_root)
    except FileNotFoundError as e:
        logger.error("%s", e)
        sys.exit(1)

    work_dir = config.work_dir
    pipeline = load_pipeline(config.project_context, config.xorial_core)
    state = ConductorState()
    stop_event = threading.Event()

    bot = TelegramBot(
        config.telegram_bot_token,
        config.telegram_chat_id,
        openai_api_key=config.openai_api_key,
    )
    anthropic_client = _make_anthropic_client(config)
    dispatcher = Dispatcher(anthropic_client, state) if anthropic_client else None

    # ── Message routing ───────────────────────────────────────────────────────

    def _save_human_input(feature: str, answer: str) -> None:
        """Append the user's answer to human-input.md in the feature folder."""
        from datetime import datetime
        path = Path(config.feature_path(feature)) / "human-input.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(path, "a") as f:
            f.write(f"\n## {timestamp}\n\n{answer}\n")
        logger.info("[%s] Human input saved to human-input.md", feature)

    def on_message(text: str) -> None:
        """Route free-form Telegram messages — intake session, human-input, or dispatcher."""
        with state.lock:
            intake = state.active_intake

        # ── Intake mode: all messages go to intake session ────────────────────
        if intake:
            response = intake.send(text)
            bot.send(f"💬 {response}")

            if intake.is_complete():
                with state.lock:
                    state.active_intake = None
                bot.send(
                    f"✅ *Intake complete*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📦 `{intake.feature_name}`\n"
                    f"Orchestrator picks it up automatically.\n\n"
                    f"{_footer(config)}"
                )
                logger.info("Intake complete: %s", intake.feature_name)
            return

        # ── Human-input mode: answer goes to the paused feature ───────────────
        # If any feature is paused waiting for NEEDS_HUMAN_INPUT, treat this
        # message as the answer — save it and auto-resume.
        with state.lock:
            needs_input = [
                f for f in state.paused
                if state.last_status.get(f, {}).get("status") == "NEEDS_HUMAN_INPUT"
            ]

        if needs_input:
            if len(needs_input) == 1:
                feature = needs_input[0]
                _save_human_input(feature, text)
                bot.send(
                    f"✍️ *Answer saved* — `{feature}`\n"
                    f"Continuing automatically…"
                )
                on_resume(feature)
                return
            else:
                # Multiple features waiting — let dispatcher pick the right one,
                # but enrich the message so it knows what's happening
                text = f"[Answering a NEEDS_HUMAN_INPUT question. Paused features: {', '.join(needs_input)}]\n\n{text}"

        # ── Free mode: dispatcher understands natural language ────────────────
        if not dispatcher:
            bot.send("Dispatcher unavailable (install `anthropic` package).")
            return

        action = dispatcher.process(text)
        _execute_action(action)

    def _answer_question(feature: str, question: str) -> None:
        """Answer a user question about a feature, maintaining conversation history."""
        from qa_session import QASession

        if not anthropic_client:
            bot.send("Q&A unavailable — `anthropic` package not installed.")
            return

        feature_path = config.feature_path(feature)
        if not Path(feature_path).exists():
            bot.send(f"Feature `{feature}` not found.")
            return

        with state.lock:
            session = state.active_qa.get(feature)
            if session is None:
                session = QASession(feature, feature_path, anthropic_client)
                state.active_qa[feature] = session

        logger.info("[%s] Q&A question: %s", feature, question[:120])
        answer = session.ask(question)
        logger.info("[%s] Q&A answer sent (%d chars)", feature, len(answer))
        bot.send(f"💡 *{feature}*\n━━━━━━━━━━━━━━━\n{answer}")

    def _execute_action(action: dict) -> None:
        a = action.get("action")

        if a == "resume":
            on_resume(action.get("feature"))

        elif a == "new":
            ftype = action.get("type", "")
            fname = action.get("name", "")
            if ftype and fname:
                on_new(f"{ftype} {fname}")
            else:
                bot.send(action.get("text", "Need type and name."))

        elif a == "status":
            bot.send(format_status(config, state))

        elif a == "artifacts":
            feature = action.get("feature", "")
            if not feature:
                bot.send("Which feature?")
            else:
                files = collect_artifacts(config.feature_path(feature))
                if files:
                    bot.send(
                        f"📎 *Artifacts* — `{feature}`\n"
                        f"Sending {len(files)} file(s)…",
                        attachments=files,
                    )
                else:
                    bot.send(f"No artifacts found for `{feature}`.")

        elif a == "qa":
            feature = action.get("feature", "")
            question = action.get("question", "")
            if feature and question:
                threading.Thread(
                    target=_answer_question,
                    args=(feature, question),
                    daemon=True,
                ).start()
            else:
                bot.send("Which feature and what question?")

        elif a == "reply":
            bot.send(action.get("text", "?"))

        else:
            logger.warning("Unknown dispatcher action: %s", action)

    # ── Command handlers ──────────────────────────────────────────────────────

    def on_new(tail: str) -> None:
        """Handle /new <type> <name> — start intake session."""
        parts = tail.strip().split()
        if len(parts) < 2:
            bot.send(
                f"Usage: `/new <type> <name>`\n"
                f"Types: {', '.join(sorted(VALID_TYPES))}\n"
                f"Example: `/new feat age-verification`"
            )
            return

        ftype, fname = parts[0].lower(), parts[1].lower()
        if ftype not in VALID_TYPES:
            bot.send(f"Unknown type `{ftype}`. Valid: {', '.join(sorted(VALID_TYPES))}")
            return

        # Block new intake if one is already active
        with state.lock:
            if state.active_intake:
                bot.send(
                    f"Intake already active for `{state.active_intake.feature_name}`.\n"
                    f"Finish it first or say 'cancel intake'."
                )
                return

        feature_id = f"{ftype}/{fname}"
        feature_path = config.feature_path(feature_id)

        if os.path.exists(feature_path):
            bot.send(f"Folder `{feature_id}` already exists.")
            return

        if not anthropic_client:
            bot.send("Cannot start intake — `anthropic` package not installed.")
            return

        os.makedirs(feature_path, exist_ok=True)

        session = IntakeSession(feature_id, config, anthropic_client)
        with state.lock:
            state.active_intake = session

        bot.send(
            f"💬 *Intake started*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 `{feature_id}`\n"
            f"Your messages go to the intake agent until it's done.\n"
            f"No other notifications will interrupt you."
        )

        # Get opening question from intake agent
        opening = session.start()
        bot.send(f"💬 {opening}")
        logger.info("Intake session started: %s", feature_id)

    def on_resume(feature: str | None) -> None:
        if feature:
            if state.resume(feature):
                state.reset_iterations(feature)
                logger.info("Resuming: %s", feature)
                bot.send(f"▶️ Resuming `{feature}`…")
            else:
                bot.send(f"`{feature}` is not paused.")
        else:
            resumed = state.resume_any()
            if resumed:
                for f in resumed:
                    state.reset_iterations(f)
                bot.send(f"▶️ Resuming: {', '.join(f'`{f}`' for f in resumed)}")
            else:
                bot.send("Nothing is currently paused.")

    # ── Watcher callback ──────────────────────────────────────────────────────

    def _check_dependents(completed: str) -> None:
        """Trigger any features whose depends_on points to the just-completed feature."""
        for fname, s in state.get_all_statuses().items():
            if s.get("depends_on") == completed:
                logger.info("[%s] depends_on '%s' is now DONE — triggering", fname, completed)
                on_status_change(fname, s)

    def _apply_pipeline(status: dict) -> dict:
        """Substitute owner with effective owner after applying pipeline skip rules.
        Per-feature skip: roles listed in status.json 'skip' field are skipped
        in addition to the global pipeline skip.
        """
        owner = status.get("owner", "")
        feature_skip = set(status.get("roles_skip") or [])
        feature_force = set(status.get("roles_force") or [])
        effective = pipeline.effective_owner(owner, extra_skip=feature_skip, force=feature_force)
        if effective != owner:
            logger.info(
                "Pipeline: skipping '%s' → routing to '%s'%s%s",
                owner, effective,
                f" (feature roles_skip: {feature_skip})" if feature_skip else "",
                f" (feature roles_force: {feature_force})" if feature_force else "",
            )
            return {**status, "owner": effective}
        return status

    def _get_route(status: dict):
        """
        Resolve route for status, checking pipeline custom_agents before built-ins.
        Applies config.agents overrides (model/type/reasoning) after resolution.
        Returns (route, needs_human).
        """
        owner = status.get("owner", "")
        custom_route = pipeline.get_route(owner)
        if custom_route is not None:
            route = apply_agent_config(custom_route, owner, config.agents)
            return route, False  # custom agents never trigger human pause
        route, needs_human = resolve(status)
        if route is not None:
            route = apply_agent_config(route, owner, config.agents)
        return route, needs_human

    def on_status_change(feature: str, status: dict) -> None:
        """Called by watcher when any feature's status.json changes."""

        # Rebuild kanban and canvas map on every status change
        if config.project_context:
            all_st = state.get_all_statuses()
            rebuild_kanban(config.project_context, all_st)
            rebuild_canvas(config.project_context, all_st)

        # Ignore intake folders — handled by IntakeSession directly
        if status.get("stage") == "intake":
            return

        # Ignore IN_PROGRESS — conductor wrote this itself when spawning an agent.
        # Re-queuing here would cause a double-spawn when the agent finishes.
        if status.get("status") == "IN_PROGRESS":
            return

        # BLOCKED = agent failed after retries. Do not auto-requeue — wait for
        # human to fix the issue and /resume.
        if status.get("status") == "BLOCKED":
            if not state.is_paused(feature):
                resume_event = state.pause(feature)

                owner = status.get("owner", "?")
                stage = status.get("stage", "?")
                reason = status.get("blocked_reason", "")
                msg_lines = [
                    f"🔴 *Blocked* — `{feature}`",
                    "━━━━━━━━━━━━━━━",
                    f"👤 `{owner}` · {stage}",
                ]
                if reason:
                    msg_lines.append(f"\n_{reason[:300]}_")
                msg_lines.append(f"\nSend `/resume {feature}` to retry.\n\n{_footer(config)}")
                bot.send("\n".join(msg_lines))

                def _wait_after_block(feat=feature, evt=resume_event):
                    bot.wait_for_resume(feat, evt)
                    logger.info("[%s] Resumed after BLOCKED — requeueing", feat)
                    from watcher import load_status
                    fresh = load_status(config.feature_path(feat))
                    if fresh:
                        fresh = _apply_pipeline(fresh)
                        state.update_status(feat, fresh)
                        r, h = _get_route(fresh)
                        if r and r.agent_type != AgentType.DONE and not h:
                            state.queue.put(feat)
                        elif h:
                            on_status_change(feat, fresh)

                threading.Thread(target=_wait_after_block, daemon=True).start()
            return

        status = _apply_pipeline(status)
        route, needs_human = _get_route(status)

        if route and route.agent_type == AgentType.DONE:
            bot.send(
                f"✅ *Feature complete*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📦 `{feature}`\n\n"
                f"{_footer(config)}"
            )
            _check_dependents(feature)
            return

        if needs_human:
            if state.is_paused(feature):
                # Feature got a fresh agent handoff while already paused (e.g.
                # auto-iteration limit fired just as reviewer finished). Clear the
                # old pause so the resume thread exits cleanly, then fall through
                # to send a new human-review notification and create a fresh pause.
                state.resume(feature)

            current_status = status.get("status", "")
            stage = status.get("stage", "")
            blocked_reason = status.get("blocked_reason", "")

            msg_lines = [
                f"⏸ *Human input needed*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📦 `{feature}`"
            ]
            if current_status == "NEEDS_HUMAN_INPUT":
                msg_lines.append(f"❗ {blocked_reason}")
                msg_lines.append(f"\nJust reply here — your answer will be saved and the agent will continue automatically.\n\n{_footer(config)}")
            else:
                msg_lines.append(f"🏷 Stage: `{stage}` — awaiting your review")
                msg_lines.append(f"\nReply naturally or `/resume {feature}`\n\n{_footer(config)}")

            artifacts = collect_artifacts(config.feature_path(feature)) \
                if current_status in ("FAIL", "BLOCKED") else []

            resume_event = state.pause(feature)
            bot.send("\n".join(msg_lines), attachments=artifacts)

            def wait_and_requeue():
                bot.wait_for_resume(feature, resume_event)
                logger.info("[%s] Resumed — requeueing", feature)
                from watcher import load_status
                fresh = load_status(config.feature_path(feature))
                if fresh:
                    fresh = _apply_pipeline(fresh)
                    state.update_status(feature, fresh)
                    route2, human2 = _get_route(fresh)
                    if route2 and route2.agent_type != AgentType.DONE and not human2:
                        state.queue.put(feature)
                    elif human2:
                        # Status is still needs_human after resume — re-trigger
                        # notification so the user knows they need to act again.
                        on_status_change(feature, fresh)

            threading.Thread(target=wait_and_requeue, daemon=True).start()
            return

        if route is None:
            logger.warning("[%s] No route for owner=%s", feature, status.get("owner"))
            return

        depends_on = status.get("depends_on", "")
        if depends_on:
            parent = state.get_all_statuses().get(depends_on)
            if not parent or parent.get("stage") != "done":
                logger.info("[%s] Waiting on depends_on: %s — not queuing", feature, depends_on)
                return

        state.queue.put(feature)

    # ── Start threads ─────────────────────────────────────────────────────────

    # ── Kill any agent orphaned by a previous conductor crash ────────────────
    kill_stale_agent(config)
    stale = reset_stale_in_progress(config.work_dir, pid_file_path(config))
    if stale:
        logger.warning("Reset stale IN_PROGRESS features: %s", ", ".join(stale))

    # ── Send startup message FIRST, then start threads ───────────────────────
    # (watcher fires immediately and may send BLOCKED notifications — startup
    #  message must arrive in Telegram before those)

    mode_line = "🧪 *DRY RUN — no agents will be executed*" if dry_run else "⚡ *LIVE*"
    bot.send(
        f"🚀 *Conductor started*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📁 `{config.instance_name}`\n"
        f"{mode_line}\n\n"
        f"/status · /resume · /new\n"
        f"Or just write naturally"
    )
    logger.info("Conductor started — watching %s", work_dir)

    threading.Thread(
        target=bot.poll_commands,
        kwargs={
            "on_resume": on_resume,
            "on_status": lambda: format_status(config, state),
            "on_new": on_new,
            "on_message": on_message,
            "stop_event": stop_event,
        },
        daemon=True,
        name="telegram-poller",
    ).start()

    threading.Thread(
        target=watch_all,
        kwargs={
            "work_dir": work_dir,
            "state": state,
            "on_change": on_status_change,
            "poll_interval": 10.0,
            "stop_event": stop_event,
            "context_dir": config.project_context,
        },
        daemon=True,
        name="watcher",
    ).start()

    # ── Signal handling — clean Ctrl+C with no traceback ─────────────────────

    def _on_signal(sig, frame):
        kill_current_agent()
        stop_event.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # ── Main loop: process agent queue sequentially ───────────────────────────

    try:
        while not stop_event.is_set():
            try:
                feature = state.queue.get(timeout=0.5)
            except _queue_module.Empty:
                continue

            with state.lock:
                state.running = feature

            status = state.get_all_statuses().get(feature)
            if not status:
                logger.warning("[%s] No status — skipping", feature)
                state.queue.task_done()
                continue

            route, needs_human = _get_route(status)
            if needs_human or route is None or route.agent_type == AgentType.DONE:
                state.queue.task_done()
                continue

            owner = status.get("owner", "?")
            stage = status.get("stage", "?")
            current_status = status.get("status", "?")

            # ── Auto-iteration limit check ────────────────────────────────────
            max_iters = config.max_auto_iterations
            if max_iters > 0:
                iters = state.get_iterations(feature)
                if iters >= max_iters:
                    logger.warning("[%s] Auto-iteration limit reached (%d/%d) — forcing human review", feature, iters, max_iters)
                    resume_event = state.pause(feature)
                    bot.send(
                        f"⚠️ *Auto-iteration limit reached* — `{feature}`\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"🔁 {iters} agents ran without human review (limit: {max_iters})\n"
                        f"👤 `{owner}` · {stage}\n\n"
                        f"Check the logs and send `/resume {feature}` to continue.\n\n"
                        f"{_footer(config)}"
                    )

                    def _wait_iter_limit(feat=feature, evt=resume_event):
                        evt.wait()
                        state.reset_iterations(feat)
                        logger.info("[%s] Resumed after iteration limit — requeueing", feat)
                        from watcher import load_status
                        fresh = load_status(config.feature_path(feat))
                        if fresh:
                            fresh = _apply_pipeline(fresh)
                            state.update_status(feat, fresh)
                            r, h = _get_route(fresh)
                            if r and r.agent_type != AgentType.DONE and not h:
                                state.queue.put(feat)
                            elif h:
                                on_status_change(feat, fresh)

                    threading.Thread(target=_wait_iter_limit, daemon=True).start()
                    with state.lock:
                        state.running = None
                    state.queue.task_done()
                    continue

            if current_status == "BLOCKED":
                status_line = "📊 Was: `BLOCKED` → 🔄 retrying"
            else:
                status_line = f"📊 Was: `{current_status}`"

            bot.send(
                f"▶️ *Agent running* — `{feature}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 Role: `{owner}`\n"
                f"🏷 Stage: `{stage}`\n"
                f"{status_line}\n"
                f"⏳ Working…\n\n"
                f"{_footer(config)}"
            )

            prompt = build_prompt(config, route, feature, pipeline=pipeline)
            logger.info("[%s] Spawning %s (%s)", feature, route.agent_type.value, route.role_file)

            set_in_progress(config.feature_path(feature), owner)
            set_current_feature(config, feature)
            success, failure_reason = spawn_agent(config, route, prompt, dry_run=dry_run)

            # Increment auto-iteration counter (only on actual agent spawn)
            state.increment_iterations(feature)

            if not success:
                logger.error("[%s] %s", feature, failure_reason)
                set_blocked(config.feature_path(feature), failure_reason)
                artifacts = collect_artifacts(config.feature_path(feature))

                retry_seconds = _seconds_until_retry(failure_reason)
                if retry_seconds is not None:
                    retry_mins = int(retry_seconds / 60) + 1
                    auto_note = f"\n⏰ Auto-resuming in ~{retry_mins} min (after limit resets)."
                else:
                    auto_note = f"\nSend `/resume {feature}` after fixing."

                bot.send(
                    f"❌ *Agent failed* — `{feature}`\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{failure_reason}\n"
                    f"{auto_note}\n\n"
                    f"{_footer(config)}",
                    attachments=artifacts,
                )

                if retry_seconds is not None:
                    def _auto_resume_after_limit(feat=feature, secs=retry_seconds):
                        # Extra 2-minute buffer to let the quota actually reset
                        time.sleep(secs + 120)
                        logger.info("[%s] Auto-resuming after usage limit reset", feat)
                        bot.send(f"⏰ *Auto-resuming* `{feat}` — usage limit should have reset.")
                        on_resume(feat)
                    threading.Thread(target=_auto_resume_after_limit, daemon=True).start()

            # After a successful run, re-check status.json.
            # Agents sometimes leave status=IN_PROGRESS while changing owner
            # (handoff without setting a terminal status). The watcher skips
            # IN_PROGRESS, so the next agent would never be queued.
            # If the owner changed, force-queue the feature now.
            if success:
                from watcher import load_status
                fresh = load_status(config.feature_path(feature))
                if fresh:
                    fresh_owner = fresh.get("owner", "")
                    fresh_status = fresh.get("status", "")
                    if fresh_status == "IN_PROGRESS" and fresh_owner != owner:
                        logger.warning(
                            "[%s] Agent left IN_PROGRESS with new owner=%s — force-queuing",
                            feature, fresh_owner,
                        )
                        fresh = _apply_pipeline(fresh)
                        state.update_status(feature, fresh)
                        r, h = _get_route(fresh)
                        if r and r.agent_type != AgentType.DONE and not h:
                            state.queue.put(feature)

            with state.lock:
                state.running = None

            state.queue.task_done()

    finally:
        print()  # newline — clears the ^C character in terminal
        logger.info("Shutting down...")
        stop_event.set()
        bot.send(f"🛑 *Conductor stopped*\n_`{config.instance_name}`_")
        sys.exit(0)


if __name__ == "__main__":
    main()
