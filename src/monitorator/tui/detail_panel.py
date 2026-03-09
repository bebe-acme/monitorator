from __future__ import annotations

import os

from textual.widgets import Static

from monitorator.models import MergedSession
from monitorator.project_metadata import get_project_description
from monitorator.session_prompt import get_session_prompt
from monitorator.tui.formatting import STATUS_ICONS, STATUS_COLORS, format_elapsed


def _shorten_path(path: str, max_length: int = 55) -> str:
    """Replace home dir with ~ and collapse middle segments if too long."""
    if not path:
        return ""
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    if len(path) <= max_length:
        return path
    # Keep first segment (~/...) and last segment, collapse middle
    parts = path.split("/")
    if len(parts) <= 2:
        return path[:max_length]
    first = parts[0]
    last = parts[-1]
    # Build collapsed path: first/.../last
    collapsed = f"{first}/.../{last}"
    if len(collapsed) > max_length:
        return collapsed[:max_length]
    return collapsed


# Box-drawing characters
_TL = "\u2554"  # ╔
_TR = "\u2557"  # ╗
_BL = "\u255a"  # ╚
_BR = "\u255d"  # ╝
_H = "\u2550"   # ═
_V = "\u2551"   # ║

_BOX_WIDTH = 78
_INNER_WIDTH = _BOX_WIDTH - 4  # space inside ║  ...  ║


def _box_top(project: str) -> str:
    """Build the top border with project name embedded."""
    label = f" {project} "
    prefix = f"{_TL}{_H}{_H}"
    remaining = _BOX_WIDTH - len(prefix) - len(label) - 1  # -1 for closing ╗
    if remaining < 1:
        remaining = 1
    return f"[#333300]{prefix}[/][bold #ffcc00]{label}[/][#333300]{_H * remaining}{_TR}[/]"


def _box_bottom() -> str:
    """Build the bottom border."""
    inner = _H * (_BOX_WIDTH - 2)
    return f"[#333300]{_BL}{inner}{_BR}[/]"


def _box_row(content: str) -> str:
    """Wrap content in box side borders."""
    return f"[#333300]{_V}[/]  {content}"


class DetailPanel(Static):
    """Detail view for the selected session — hacker terminal aesthetic."""

    def __init__(self) -> None:
        super().__init__("[#555555]select a session to inspect[/]")

    def show_session(self, session: MergedSession) -> None:
        s = session
        status = s.effective_status
        icon = STATUS_ICONS.get(status, "?")
        color = STATUS_COLORS.get(status, "#666666")

        project = s.project_name
        pid = str(s.process_info.pid) if s.process_info else "-"
        cpu = f"{s.process_info.cpu_percent:.0f}%" if s.process_info else "-"
        elapsed = format_elapsed(s.process_info.elapsed_seconds) if s.process_info else "-"
        branch = s.hook_state.git_branch if s.hook_state and s.hook_state.git_branch else "-"
        cwd_raw = s.hook_state.cwd if s.hook_state else (s.process_info.cwd if s.process_info else "-")
        cwd = _shorten_path(cwd_raw)
        last_tool = s.hook_state.last_tool if s.hook_state and s.hook_state.last_tool else None
        prompt = s.hook_state.last_prompt_summary if s.hook_state and s.hook_state.last_prompt_summary else ""
        subagents = s.hook_state.subagent_count if s.hook_state else 0

        # Row 1: status icon + status label, PID, CPU, elapsed timer
        from monitorator.models import SessionStatus as SS
        _active = {SS.THINKING, SS.EXECUTING, SS.SUBAGENT_RUNNING}
        status_label = status.value.upper().replace("_", " ")
        if status == SS.WAITING_PERMISSION:
            status_markup = f"[bold #ff3333 blink]{icon} {status_label} \u26a0\u26a0\u26a0[/]"
        elif status in _active:
            status_markup = f"[{color} blink]{icon}[/] [{color}]{status_label}[/]"
        else:
            status_markup = f"[{color}]{icon} {status_label}[/]"
        row1 = (
            f"{status_markup}"
            f"          "
            f"[#555555]PID [/][#cccccc]{pid}[/]"
            f"       "
            f"[#555555]CPU [/][#cccccc]{cpu}[/]"
            f"       "
            f"[#555555]\u23f1 [/][#cccccc]{elapsed}[/]"
        )

        # Row 2: branch + cwd
        row2 = (
            f"[#555555]branch [/][#3399ff]{branch}[/]"
            f"         "
            f"[#555555]cwd [/][#cccccc]{cwd}[/]"
        )

        # Row 2b: project description (if available from filesystem)
        desc_text = get_project_description(cwd_raw) if cwd_raw and cwd_raw != "-" else None
        row_desc = f"[#555555]desc   [/][#ffcc00]{desc_text}[/]" if desc_text else ""

        # Row 3: tool (only if active)
        row3 = ""
        if last_tool:
            row3 = f"[#555555]tool   [/][{color}]{last_tool[:65]}[/]"

        # Row 4: prompt (only if available)
        row4 = ""
        if prompt:
            truncated = prompt[:60]
            row4 = f'[#555555]prompt [/][italic #cccccc]{truncated}[/]'
        elif not s.hook_state and s.process_info and s.process_info.session_uuid:
            session_prompt = get_session_prompt(
                s.process_info.cwd, s.process_info.session_uuid
            )
            if session_prompt:
                row4 = f'[#555555]prompt [/][italic #cccccc]{session_prompt[:60]}[/]'

        # Row 5: subagents (only if > 0)
        row5 = ""
        if subagents > 0:
            row5 = f"[#555555]subagents [/][#cc66ff]{subagents}[/]"

        # Assemble the box
        lines = [
            _box_top(project),
            _box_row(row1),
            _box_row(row2),
        ]
        if row_desc:
            lines.append(_box_row(row_desc))
        if row3:
            lines.append(_box_row(row3))
        if row4:
            lines.append(_box_row(row4))
        if row5:
            lines.append(_box_row(row5))
        lines.append(_box_bottom())

        self.update("\n".join(lines))

    def clear_session(self) -> None:
        self.update("[#555555]select a session to inspect[/]")
