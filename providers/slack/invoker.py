from dataclasses import dataclass
from typing import AsyncIterator
import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    query,
)

from .config import Config, Project


ROLE_FILES = {
    "intake": "05-intake.md",
    "orchestrator": "10-orchestrator.md",
    "critic": "20-critic.md",
    "implementer": "30-implementer.md",
    "reviewer": "40-reviewer.md",
    "behavior-reviewer": "50-behavior-reviewer.md",
}


@dataclass
class RunEvent:
    kind: str          # "text" | "tool" | "thinking" | "result"
    text: str = ""
    session_id: str = ""
    cost_usd: float | None = None


def _build_prompt(
    project: Project,
    role: str,
    feature: str | None,
    speaker: str,
    user_message: str,
    attachments: list[str] | None = None,
    continuation: bool = False,
) -> str:
    """Minimal role-kick prompt. The agent itself reads the role file, common
    rules, project context, and feature folder via its Read tool — matching
    the convention used by chat.md and the conductor runner.

    On continuation (resume session), the role context is already loaded —
    we only send the new speaker message and any new attachments.
    """
    if continuation:
        parts = [f"Speaker ({speaker}) replied:"]
        if user_message:
            parts.append(user_message)
        if attachments:
            parts.append("")
            parts.append("Attached files (absolute paths — Read/view them as needed):")
            for p in attachments:
                parts.append(f"- {p}")
        return "\n".join(parts)

    role_file = ROLE_FILES[role]
    parts = [
        f"Take role: {project.xorial_core}/roles/{role_file}",
        f"Common rules: {project.xorial_core}/ROLES_COMMON_RULES.md",
        f"Project context: {project.project_context}/project-context.md",
    ]
    if feature:
        parts.append(f"Work on: {project.feature_path(feature)}/")
    parts.append(f"Speaker (record as author of this pass): {speaker}")
    if user_message:
        parts.append("")
        parts.append("Speaker message:")
        parts.append(user_message)
    if attachments:
        parts.append("")
        parts.append("Attached files (absolute paths — Read/view them as needed):")
        for p in attachments:
            parts.append(f"- {p}")
    parts.append("")
    parts.append("Start your pass.")
    return "\n".join(parts)


async def run_role(
    cfg: Config,
    project: Project,
    role: str,
    feature: str | None,
    speaker: str,
    user_message: str,
    resume_session: str | None = None,
    model: str | None = None,
    attachments: list[str] | None = None,
) -> AsyncIterator[RunEvent]:
    """Invoke a Xorial role via the Claude Agent SDK and yield streaming
    events. The SDK bundles the Claude Code CLI; the cwd is the project root
    so the agent sees the real repo."""
    if role not in ROLE_FILES:
        raise ValueError(f"Unknown role: {role}")

    prompt = _build_prompt(
        project,
        role,
        feature,
        speaker,
        user_message,
        attachments=attachments,
        continuation=bool(resume_session),
    )

    # Merge onto os.environ, not replace it — the SDK subprocess needs PATH,
    # HOME, and everything else the parent process has.
    env = dict(os.environ)
    if cfg.anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = cfg.anthropic_api_key

    options = ClaudeAgentOptions(
        model=model or cfg.default_model,
        cwd=project.project_root,
        permission_mode="bypassPermissions",
        env=env,
        resume=resume_session,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield RunEvent(kind="text", text=block.text)
                elif isinstance(block, ToolUseBlock):
                    yield RunEvent(kind="tool", text=f"🔧 {block.name}")
                elif isinstance(block, ThinkingBlock):
                    # Thinking blocks are usually noisy; surface a tick so the
                    # user sees the agent is alive without flooding.
                    yield RunEvent(kind="thinking", text="·")
        elif isinstance(message, ResultMessage):
            yield RunEvent(
                kind="result",
                session_id=message.session_id or "",
                cost_usd=message.total_cost_usd,
            )


CHAT_SYSTEM_PROMPT = """You are Xorial — a Slack bot that runs AI-driven software delivery. You are in chat mode: orientation, questions, banter.

Voice:
- Direct, sharp, a little cocky. No "I'd be happy to", no "let me know if you need anything else", no corporate hedging.
- 1-3 sentences by default. Only go longer when the user explicitly asks for detail or the topic actually needs it.
- If the answer is one word, say one word.

Hard rules:
- Do NOT close your replies with suggestions like `/xorial bind ...` or `/xorial new ...`. Only mention a command if the user *actually asked* "what do I do next?" or the question is literally about commands.
- Do not apologize for limitations. State facts.
- You have read-only tools (Read/Glob/Grep/WebFetch). Use them silently when a question needs real project context; don't announce that you're about to look.

Commands (for reference, only surface when relevant):
- `/xorial help | whoami | register | list | status | unbind`
- `/xorial new <feat|fix|refactor|chore> <name>` · `/xorial bind <type>/<name>` · `/xorial delete <type>/<name> [confirm]`
- `/xorial intake | orchestrate | critic [message]` — planning roles
- `@xorial <role> [message]` — same as slash, or `@xorial <anything>` for this chat

Pipeline: intake (interview) → orchestrator (plan) → critic (review) → orchestrator (finalize) → implementer → reviewer → behavior-reviewer.
"""


async def run_chat(
    cfg: Config,
    project: Project,
    user_message: str,
    resume_session: str | None = None,
    attachments: list[str] | None = None,
) -> AsyncIterator[RunEvent]:
    """Free-form chat mode: the bot answers orientation / help / casual
    questions in a thread. Read-only tools, no git commit, Sonnet-class model.
    """
    env = dict(os.environ)
    if cfg.anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = cfg.anthropic_api_key

    options = ClaudeAgentOptions(
        model=cfg.chat_model,
        cwd=project.project_root,
        system_prompt=CHAT_SYSTEM_PROMPT,
        allowed_tools=["Read", "Glob", "Grep", "WebFetch"],
        permission_mode="bypassPermissions",
        env=env,
        resume=resume_session,
    )

    prompt = user_message or "(the user @-mentioned you with no text — greet and orient them)"
    if attachments:
        parts = [prompt, "", "Attached files (absolute paths — Read them as needed):"]
        for p in attachments:
            parts.append(f"- {p}")
        prompt = "\n".join(parts)

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield RunEvent(kind="text", text=block.text)
                elif isinstance(block, ToolUseBlock):
                    yield RunEvent(kind="tool", text=f"🔧 {block.name}")
        elif isinstance(message, ResultMessage):
            yield RunEvent(
                kind="result",
                session_id=message.session_id or "",
                cost_usd=message.total_cost_usd,
            )
