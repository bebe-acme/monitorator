from __future__ import annotations

import os
import time

from monitorator.models import MergedSession, SessionStatus
from monitorator.tui.theme_colors import get_status_color


STATUS_ICONS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "\u25cf",           # ●
    SessionStatus.EXECUTING: "\u25b6",          # ▶
    SessionStatus.WAITING_PERMISSION: "\u26a0",  # ⚠
    SessionStatus.IDLE: "\u23ce",               # ⏎
    SessionStatus.SUBAGENT_RUNNING: "\u25c6",   # ◆
    SessionStatus.TERMINATED: "\u00d7",         # ×
    SessionStatus.UNKNOWN: "?",
}

class _StatusColorMap:
    """Dict-like mapping that reads from the active theme."""

    def get(self, status: SessionStatus, default: str = "#666666") -> str:
        return get_status_color(status)

    def __getitem__(self, status: SessionStatus) -> str:
        return get_status_color(status)

    def __contains__(self, status: object) -> bool:
        return isinstance(status, SessionStatus)


STATUS_COLORS: _StatusColorMap = _StatusColorMap()

STATUS_LABELS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "THINK",
    SessionStatus.EXECUTING: "EXEC",
    SessionStatus.WAITING_PERMISSION: "PERM!",
    SessionStatus.IDLE: "WAIT",
    SessionStatus.SUBAGENT_RUNNING: "SUBAG",
    SessionStatus.TERMINATED: "TERM",
    SessionStatus.UNKNOWN: "???",
}

_TOOL_DISPLAY: dict[str, str] = {
    "Edit": "Editing",
    "Write": "Writing",
    "Read": "Reading",
}

_MAX_PATH_LEN = 50



def _get_desc(session: MergedSession) -> str | None:
    """Extract session prompt or project description for process-only sessions.

    Priority: session prompt > project description.
    """
    from monitorator.project_metadata import get_project_description
    from monitorator.session_prompt import get_session_prompt

    cwd = session.process_info.cwd if session.process_info else None
    if not cwd:
        return None

    # 1. Session prompt (if we have a UUID)
    uuid = session.process_info.session_uuid if session.process_info else None
    if uuid:
        prompt = get_session_prompt(cwd, uuid)
        if prompt:
            return prompt[:60]

    # 2. Project description
    return get_project_description(cwd)


def shorten_path(path: str) -> str:
    """Replace home dir with ~ and collapse middle segments if too long."""
    if not path:
        return ""

    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]

    if len(path) <= _MAX_PATH_LEN:
        return path

    parts = path.split("/")
    if len(parts) <= 2:
        return path[:_MAX_PATH_LEN - 3] + "..."

    head = parts[0]
    tail = parts[-1]

    ellipsis = "/.../"
    budget = _MAX_PATH_LEN - len(head) - len(tail) - len(ellipsis)
    middle = ""
    for part in parts[1:-1]:
        candidate = f"{middle}/{part}" if middle else part
        if len(candidate) > budget:
            break
        middle = candidate

    if middle:
        result = f"{head}/{middle}{ellipsis}{tail}"
    else:
        result = f"{head}{ellipsis}{tail}"

    if len(result) > _MAX_PATH_LEN:
        return result[:_MAX_PATH_LEN - 3] + "..."
    return result


def format_memory(mb: float) -> str:
    """Format memory in MB to human-readable string (MB or GB)."""
    if mb >= 1024:
        return f"{mb / 1024:.1f}GB"
    return f"{mb:.0f}MB"


def format_elapsed(seconds: int) -> str:
    """Format elapsed seconds into human-readable string."""
    if seconds >= 3600:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins:02d}m"
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}m {secs:02d}s"


def extract_value(summary: str, key: str) -> str:
    """Extract a value from 'key: value' style summary."""
    prefix = f"{key}: "
    if summary.startswith(prefix):
        return summary[len(prefix):]
    return summary


def format_activity(session: MergedSession) -> str:
    """Transform raw hook data into human-readable activity text.

    NEVER returns empty string — every status gets a meaningful description.
    """
    status = session.effective_status
    hs = session.hook_state
    tool = hs.last_tool if hs else None
    summary = hs.last_tool_input_summary if hs else None

    # Permission warnings take priority
    if status == SessionStatus.WAITING_PERMISSION:
        if tool and summary:
            cmd_text = extract_value(summary, "command")
            return f"!! Permission: {tool} {cmd_text}"
        return "Awaiting permission"

    # Idle states — prompt is shown on its own line, so activity shows elapsed time
    if status == SessionStatus.IDLE:
        if hs and hs.updated_at:
            ago = int(time.time() - hs.updated_at)
            if ago < 60:
                return f"Idle ({ago}s ago)"
            return f"Idle ({ago // 60}m ago)"
        if not hs:
            desc = _get_desc(session)
            return desc or "Process detected \u2014 no hooks"
        return "Awaiting input"

    # Subagent states
    if status == SessionStatus.SUBAGENT_RUNNING:
        if tool and summary:
            # Still show tool activity if available
            return _format_tool(tool, summary)
        count = hs.subagent_count if hs else 0
        if count > 0:
            return f"Subagent active ({count} running)"
        return "Subagent active"

    # Terminated / Unknown
    if status == SessionStatus.TERMINATED:
        return "Session ended"
    if status == SessionStatus.UNKNOWN:
        return "Unknown state"

    # Tool-based descriptions
    if tool and summary:
        return _format_tool(tool, summary)
    if tool:
        return tool

    # Status-based fallbacks (THINKING, EXECUTING)
    if status == SessionStatus.THINKING:
        if not hs:
            desc = _get_desc(session)
            if desc:
                return desc
        return "Thinking..."
    if status == SessionStatus.EXECUTING:
        return "Executing..."

    return "Unknown state"


def _format_tool(tool: str, summary: str) -> str:
    """Format tool + summary into description text."""
    if tool in _TOOL_DISPLAY:
        file_path = extract_value(summary, "file_path")
        return f"{_TOOL_DISPLAY[tool]} {file_path}"
    if tool == "Bash":
        cmd = extract_value(summary, "command")
        return f"Running: {cmd}"
    if tool == "Grep":
        pattern = extract_value(summary, "pattern")
        return f"Searching: {pattern}"
    if tool == "Glob":
        pattern = extract_value(summary, "pattern")
        return f"Finding: {pattern}"
    if tool == "Task":
        return "Spawning subagent"
    return tool
