from __future__ import annotations

import re
import shutil

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
from monitorator.tui.sprites import get_sprite_color, get_sprite_frame, sprite_index_for_session, assign_sprites

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

# Active statuses: entire row blinks
_ACTIVE_BLINK_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# Activity text color per status
_ACTIVITY_COLORS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "#00ff66",
    SessionStatus.EXECUTING: "#33aaff",
    SessionStatus.SUBAGENT_RUNNING: "#cc66ff",
    SessionStatus.WAITING_PERMISSION: "#ff3333",
    SessionStatus.IDLE: "#cc8800",
    SessionStatus.TERMINATED: "#444444",
    SessionStatus.UNKNOWN: "#444444",
}


def _get_term_width() -> int:
    """Return the current terminal width in columns."""
    return shutil.get_terminal_size()[0]


def get_layout_config(term_width: int | None = None) -> dict[str, object]:
    """Return responsive layout configuration based on terminal width.

    Breakpoints (usable = term_width - 4 for padding/border):
      Wide (≥130): all columns
      Medium (≥112): drop ctx
      Compact (≥94): drop ctx + branch
      Narrow (<94): drop ctx + branch + pid, shrink project/activity
    """
    tw = term_width if term_width is not None else _get_term_width()
    usable = tw - 4  # padding + border margin

    if usable >= 134:
        return {"proj_w": 20, "act_w": 36, "show_branch": True, "show_pid": True, "show_ctx": True}
    if usable >= 116:
        return {"proj_w": 18, "act_w": 30, "show_branch": True, "show_pid": True, "show_ctx": False}
    if usable >= 98:
        return {"proj_w": 16, "act_w": 26, "show_branch": False, "show_pid": True, "show_ctx": False}
    return {"proj_w": 14, "act_w": 20, "show_branch": False, "show_pid": False, "show_ctx": False}


class SessionRow(Static, can_focus=True):
    """Session row with sprite character and rich status-based coloring.

    Line 1: sprite_l1 | idx | icon label | project | branch | activity | cpu | elapsed
    Line 2: sprite_l2 | prompt (or just padding)
    Line 3: sprite_l3 | padding
    Line 4: sprite_l4 | padding
    Line 5: sprite_l5 | padding
    """

    class Selected(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    def __init__(self, session: MergedSession) -> None:
        self.session = session
        self.session_id = session.session_id
        self._row_index: int = 0
        self._sprite_idx: int = sprite_index_for_session(session.session_id)
        self._anim_frame: int = 0
        self._compact: bool = False
        super().__init__(self._build_content(), markup=True)
        self._sync_needs_input()

    def _build_content(self) -> str:
        s = self.session
        status = s.effective_status
        icon = STATUS_ICONS.get(status, "?")
        label = STATUS_LABELS.get(status, "???")

        # Responsive layout
        layout = get_layout_config()
        proj_w: int = layout["proj_w"]  # type: ignore[assignment]
        act_w: int = layout["act_w"]  # type: ignore[assignment]
        show_branch: bool = layout["show_branch"]  # type: ignore[assignment]
        show_pid: bool = layout["show_pid"]  # type: ignore[assignment]
        show_ctx: bool = layout["show_ctx"]  # type: ignore[assignment]

        project = s.project_name[:proj_w - 1] + "\u2026" if len(s.project_name) > proj_w else s.project_name
        branch_raw = (
            s.hook_state.git_branch
            if s.hook_state and s.hook_state.git_branch
            else None
        )
        branch = (branch_raw[:9] + "\u2026") if branch_raw and len(branch_raw) > 10 else (branch_raw or "\u2014")
        activity_raw = format_activity(s)
        activity = (activity_raw[:act_w - 1] + "\u2026") if len(activity_raw) > act_w else activity_raw
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

        # Context estimate — try process_info UUID first, fall back to hook_state session_id
        ctx = "-"
        if show_ctx:
            ctx_uuid = None
            ctx_cwd = None
            if s.process_info and s.process_info.session_uuid and s.process_info.cwd:
                ctx_uuid = s.process_info.session_uuid
                ctx_cwd = s.process_info.cwd
            elif s.hook_state and s.hook_state.session_id and s.hook_state.cwd:
                ctx_uuid = s.hook_state.session_id
                ctx_cwd = s.hook_state.cwd
            if ctx_uuid and ctx_cwd:
                estimate = get_context_estimate(ctx_cwd, ctx_uuid)
                if estimate:
                    ctx = estimate

        idx = self._row_index
        color = STATUS_COLORS.get(status, "#666666")
        # Sprite index is stable per session_id (not row position)
        proj_color = get_sprite_color(sprite_idx=self._sprite_idx)
        activity_color = _ACTIVITY_COLORS.get(status, "#666666")

        pid = str(s.process_info.pid) if s.process_info else "-"

        # Sprite for this session — 5-line character (10x12 grid -> 5 half-block lines)
        sp1, sp2, sp3, sp4, sp5 = get_sprite_frame(
            status=status, anim_frame=self._anim_frame, sprite_idx=self._sprite_idx,
        )

        # Build icon+label
        icon_label = f"{icon} {label:<5s}"

        # Blink icon for permission + active statuses; blink activity only for permission
        if status == SessionStatus.WAITING_PERMISSION:
            icon_markup = f"[{color} blink]{icon_label}[/]"
            activity_markup = f"[{activity_color} blink]{activity:<{act_w}s} \u26a0\u26a0[/]"
        elif status in _ACTIVE_BLINK_STATUSES:
            icon_markup = f"[{color} blink]{icon_label}[/]"
            activity_markup = f"[{activity_color}]{activity:<{act_w}s}[/]"
        else:
            icon_markup = f"[{color}]{icon_label}[/]"
            activity_markup = f"[{activity_color}]{activity:<{act_w}s}[/]"

        # Build columns responsively
        columns = f" {sp1}[{color}]{idx:>2}[/]  {icon_markup}  [bold {proj_color}]{project:<{proj_w}s}[/]  "
        if show_branch:
            columns += f"[#3399ff]{branch:<10s}[/]  "
        if show_pid:
            columns += f"[#666666]{pid:>6s}[/]  "
        columns += f"{activity_markup}"
        if show_ctx:
            columns += f"  [#888888]{ctx:>6s}[/]"

        # Dim terminated rows (active blink moved to icon-only above)
        if status == SessionStatus.TERMINATED:
            line1 = f"[dim]{columns}[/]"
        else:
            line1 = columns

        # Adaptive prompt length
        tw = _get_term_width()
        prompt_max = max(20, tw - 24)  # sprite(12) + pads + └─ + margin

        # Line 2: sprite line 2 + optional prompt
        prompt = None if self._compact else _sanitize_prompt(self._get_prompt())
        if prompt:
            truncated = (prompt[:prompt_max - 1] + "\u2026") if len(prompt) > prompt_max else prompt
            line2 = f" {sp2}    [#555555]\u2514\u2500[/] [italic #777777]{truncated}[/]"
        else:
            line2 = f" {sp2}[#0a0a0a].[/]"

        # Line 3: sprite + cpu/time + session ID (first 8 chars)
        sid_short = s.session_id[:8]
        line3 = f" {sp3}    [#555555]{cpu:>5s}[/]  [#444444]{elapsed}[/]  [#333333]{sid_short}[/]"
        line4 = f" {sp4}[#0a0a0a].[/]"
        line5 = f" {sp5}[#0a0a0a].[/]"

        return f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}"

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

    def set_sprite_idx(self, idx: int) -> None:
        """Override the sprite index (used by anti-collision assignment)."""
        if self._sprite_idx != idx:
            self._sprite_idx = idx
            self.refresh_content()

    def refresh_content(self) -> None:
        self._anim_frame += 1
        self.update(self._build_content())

    def _sync_needs_input(self) -> None:
        """Add or remove the needs-input CSS class based on session status."""
        if self.session.effective_status == SessionStatus.WAITING_PERMISSION:
            self.add_class("needs-input")
        else:
            self.remove_class("needs-input")

    def update_session(self, session: MergedSession) -> None:
        """Update row with new session data without recreating widget."""
        self.session = session
        self._sync_needs_input()
        self.refresh_content()

    def on_click(self) -> None:
        self.post_message(self.Selected(self.session_id))

    def action_select(self) -> None:
        self.post_message(self.Selected(self.session_id))
