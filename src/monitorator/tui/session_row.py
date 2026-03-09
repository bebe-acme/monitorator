from __future__ import annotations

import re

from textual.widgets import Static
from textual.message import Message

from monitorator.context_size import get_context_estimate
from monitorator.models import MergedSession, SessionStatus
from monitorator.session_prompt import get_session_prompt
from monitorator.tui.formatting import (
    STATUS_ICONS,
    STATUS_COLORS,
    STATUS_LABELS,
    format_activity,
    format_elapsed,
)

# Matches text that starts with an XML-style tag (system/internal messages)
_XML_TAG_RE = re.compile(r"^\s*<[a-zA-Z][\w-]*[ >/]")

_PROMPT_MAX_LEN = 120


def _sanitize_prompt(prompt: str | None) -> str | None:
    """Sanitize prompt text for display in session rows.

    - Returns None if input is None
    - Strips newlines (replace with space)
    - Returns None if prompt starts with XML tag (system/internal message)
    - Returns None if result is empty/whitespace-only
    - Truncates to _PROMPT_MAX_LEN characters
    """
    if prompt is None:
        return None

    # Replace newlines with spaces
    cleaned = prompt.replace("\n", " ")

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Check if starts with XML tag — system/internal message
    if _XML_TAG_RE.match(cleaned):
        return None

    # Empty after cleaning?
    if not cleaned:
        return None

    # Truncate
    if len(cleaned) > _PROMPT_MAX_LEN:
        cleaned = cleaned[:_PROMPT_MAX_LEN]

    return cleaned

# Rotating color palette for project names — each session gets a unique color
SESSION_COLORS: tuple[str, ...] = (
    "#ffcc00",  # yellow (original)
    "#00ccff",  # cyan
    "#ff6699",  # pink
    "#66ff66",  # lime
    "#ff9933",  # orange
    "#cc99ff",  # lavender
    "#33ffcc",  # mint
    "#ff6666",  # coral
    "#99ccff",  # sky blue
    "#ffff66",  # light yellow
)

# Per-status animations — 5 chars wide, 8 frames each
# THINKING: Gentle breathing pulse — symmetric wave rises and falls (calm, contemplative)
_ANIM_THINKING = (
    "\u2581\u2583\u2585\u2583\u2581",  # ▁▃▅▃▁
    "\u2582\u2584\u2586\u2584\u2582",  # ▂▄▆▄▂
    "\u2583\u2585\u2587\u2585\u2583",  # ▃▅▇▅▃
    "\u2584\u2586\u2588\u2586\u2584",  # ▄▆█▆▄
    "\u2583\u2585\u2587\u2585\u2583",  # ▃▅▇▅▃
    "\u2582\u2584\u2586\u2584\u2582",  # ▂▄▆▄▂
    "\u2581\u2583\u2585\u2583\u2581",  # ▁▃▅▃▁
    "\u2581\u2582\u2584\u2582\u2581",  # ▁▂▄▂▁
)

# EXECUTING: Scanner bar with trail — bright block moves left to right (purposeful work)
_ANIM_EXECUTING = (
    "\u2588\u2593\u2591\u2591\u2591",  # █▓░░░
    "\u2591\u2588\u2593\u2591\u2591",  # ░█▓░░
    "\u2591\u2591\u2588\u2593\u2591",  # ░░█▓░
    "\u2591\u2591\u2591\u2588\u2593",  # ░░░█▓
    "\u2591\u2591\u2591\u2591\u2588",  # ░░░░█
    "\u2591\u2591\u2591\u2588\u2593",  # ░░░█▓
    "\u2591\u2591\u2588\u2593\u2591",  # ░░█▓░
    "\u2591\u2588\u2593\u2591\u2591",  # ░█▓░░
)

# SUBAGENT: Fork from center — pulse splits outward and reconverges (branching processes)
_ANIM_SUBAGENT = (
    "\u2581\u2581\u2588\u2581\u2581",  # ▁▁█▁▁
    "\u2581\u2584\u2588\u2584\u2581",  # ▁▄█▄▁
    "\u2583\u2586\u2588\u2586\u2583",  # ▃▆█▆▃
    "\u2586\u2588\u2582\u2588\u2586",  # ▆█▂█▆
    "\u2588\u2585\u2581\u2585\u2588",  # █▅▁▅█
    "\u2586\u2583\u2581\u2583\u2586",  # ▆▃▁▃▆
    "\u2583\u2581\u2581\u2581\u2583",  # ▃▁▁▁▃
    "\u2581\u2581\u2583\u2581\u2581",  # ▁▁▃▁▁
)

# PERMISSION: Strobe alert — checkerboard flash + solid blink (urgent attention)
_ANIM_PERMISSION = (
    "\u2588\u2591\u2588\u2591\u2588",  # █░█░█
    "\u2591\u2588\u2591\u2588\u2591",  # ░█░█░
    "\u2588\u2591\u2588\u2591\u2588",  # █░█░█
    "\u2591\u2588\u2591\u2588\u2591",  # ░█░█░
    "\u2588\u2588\u2588\u2588\u2588",  # █████
    "\u2591\u2591\u2591\u2591\u2591",  # ░░░░░
    "\u2588\u2588\u2588\u2588\u2588",  # █████
    "\u2591\u2591\u2591\u2591\u2591",  # ░░░░░
)

# Map status → animation frames
_STATUS_ANIMATIONS: dict[SessionStatus, tuple[str, ...]] = {
    SessionStatus.THINKING: _ANIM_THINKING,
    SessionStatus.EXECUTING: _ANIM_EXECUTING,
    SessionStatus.SUBAGENT_RUNNING: _ANIM_SUBAGENT,
    SessionStatus.WAITING_PERMISSION: _ANIM_PERMISSION,
}

# Per-status spinner colors
_SPINNER_COLORS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "#00ff66",
    SessionStatus.EXECUTING: "#00ccff",
    SessionStatus.SUBAGENT_RUNNING: "#cc66ff",
    SessionStatus.WAITING_PERMISSION: "#ff3333",
}

# Active statuses: entire row blinks
_ACTIVE_BLINK_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# Activity text color per status
_ACTIVITY_COLORS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "#00ff66",
    SessionStatus.EXECUTING: "#00ff66",
    SessionStatus.SUBAGENT_RUNNING: "#cc66ff",
    SessionStatus.WAITING_PERMISSION: "#ff3333",
    SessionStatus.IDLE: "#cc8800",
    SessionStatus.TERMINATED: "#444444",
    SessionStatus.UNKNOWN: "#444444",
}


class SessionRow(Static, can_focus=True):
    """Session row with rich status-based coloring.

    Line 1: idx | icon label | project | branch | activity | cpu | elapsed
    Line 2: (optional) last user prompt
    """

    class Selected(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    def __init__(self, session: MergedSession) -> None:
        self.session = session
        self.session_id = session.session_id
        self._row_index: int = 0
        self._anim_frame: int = 0
        self._compact: bool = False
        super().__init__(self._build_content(), markup=True)

    def _build_content(self) -> str:
        s = self.session
        status = s.effective_status
        icon = STATUS_ICONS.get(status, "?")
        label = STATUS_LABELS.get(status, "???")

        project = s.project_name[:20]
        branch_raw = (
            s.hook_state.git_branch
            if s.hook_state and s.hook_state.git_branch
            else None
        )
        branch = branch_raw[:10] if branch_raw else "\u2014"
        activity = format_activity(s)[:36]
        cpu = (
            f"{s.process_info.cpu_percent:.0f}%"
            if s.process_info
            else "-"
        )
        elapsed = (
            format_elapsed(s.process_info.elapsed_seconds)
            if s.process_info
            else "-"
        )

        # Context estimate
        ctx = "-"
        if s.process_info and s.process_info.session_uuid and s.process_info.cwd:
            estimate = get_context_estimate(s.process_info.cwd, s.process_info.session_uuid)
            if estimate:
                ctx = estimate

        idx = self._row_index
        color = STATUS_COLORS.get(status, "#666666")
        proj_color = SESSION_COLORS[(idx - 1) % len(SESSION_COLORS)] if idx > 0 else SESSION_COLORS[0]
        activity_color = _ACTIVITY_COLORS.get(status, "#666666")

        pid = str(s.process_info.pid) if s.process_info else "-"

        # Spinner for active sessions — cycles every refresh
        anim_frames = _STATUS_ANIMATIONS.get(status)
        if anim_frames:
            spinner = anim_frames[self._anim_frame % len(anim_frames)]
            spin_color = _SPINNER_COLORS.get(status, "#00ff66")
            spinner_markup = f"[bold {spin_color}]{spinner}[/]"
        else:
            spinner_markup = "     "  # 5-space placeholder for alignment

        # Build icon+label
        icon_label = f"{icon} {label:<5s}"

        # Permission: blink on icon+label and activity with warning suffix
        if status == SessionStatus.WAITING_PERMISSION:
            icon_markup = f"[{color} blink]{icon_label}[/]"
            activity_markup = f"[{activity_color} blink]{activity:<36s} \u26a0\u26a0[/]"
        else:
            icon_markup = f"[{color}]{icon_label}[/]"
            activity_markup = f"[{activity_color}]{activity:<36s}[/]"

        # Core columns (shared across all status branches)
        columns = (
            f" {spinner_markup}[{color}]{idx:>2}[/]  "
            f"{icon_markup}  "
            f"[bold {proj_color}]{project:<20s}[/]  "
            f"[#3399ff]{branch:<10s}[/]  "
            f"[#666666]{pid:>6s}[/]  "
            f"{activity_markup}  "
            f"[#999999]{cpu:>5s}[/]  "
            f"[#666666]{elapsed:>7s}[/]  "
            f"[#888888]{ctx:>6s}[/]"
        )

        # Wrap entire row for active (blink) or terminated (dim)
        if status in _ACTIVE_BLINK_STATUSES:
            line1 = f"[blink]{columns}[/]"
        elif status == SessionStatus.TERMINATED:
            line1 = f"[dim]{columns}[/]"
        else:
            line1 = columns

        # Line 2: session prompt (if available and not in compact mode)
        prompt = None if self._compact else _sanitize_prompt(self._get_prompt())
        if prompt:
            truncated = prompt[:70]
            line2 = f"       [#555555]\u2514\u2500[/] [italic #777777]{truncated}[/]"
            return f"{line1}\n{line2}"

        return line1

    def _get_prompt(self) -> str | None:
        """Get session prompt — tries hook data first, then JSONL transcript."""
        s = self.session
        # Hook-based prompt
        if s.hook_state and s.hook_state.last_prompt_summary:
            return s.hook_state.last_prompt_summary
        # JSONL-based prompt (works for both hooked and hookless sessions)
        if s.process_info and s.process_info.session_uuid and s.process_info.cwd:
            return get_session_prompt(s.process_info.cwd, s.process_info.session_uuid)
        return None

    def set_compact(self, compact: bool) -> None:
        """Set compact mode (hides prompt line) and refresh display."""
        self._compact = compact
        self.refresh_content()

    def update_index(self, index: int) -> None:
        """Set the row index and refresh display."""
        self._row_index = index
        self.refresh_content()

    def refresh_content(self) -> None:
        self._anim_frame += 1
        self.update(self._build_content())

    def update_session(self, session: MergedSession) -> None:
        """Update row with new session data without recreating widget."""
        self.session = session
        self.refresh_content()

    def on_click(self) -> None:
        self.post_message(self.Selected(self.session_id))

    def action_select(self) -> None:
        self.post_message(self.Selected(self.session_id))
