from __future__ import annotations

import re
import shutil

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.message import Message

from monitorator.context_size import get_context_estimate
from monitorator.labels import get_label
from monitorator.models import MergedSession, SessionStatus
from monitorator.session_prompt import get_session_prompt
from monitorator.tui.formatting import (
    STATUS_ICONS,
    STATUS_COLORS,
    STATUS_LABELS,
    format_activity,
    format_elapsed,
    format_memory,
)
from monitorator.tui.sprites import get_sprite_color, get_sprite_frame, sprite_index_for_session

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


# Active statuses: entire row blinks + green status bar
_ACTIVE_BLINK_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# Status bar CSS classes
_STATUS_BAR_CLASSES = ("status-active", "status-permission", "status-idle")

_STATUS_TO_BAR_CLASS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "status-active",
    SessionStatus.EXECUTING: "status-active",
    SessionStatus.SUBAGENT_RUNNING: "status-active",
    SessionStatus.WAITING_PERMISSION: "status-permission",
    SessionStatus.IDLE: "status-idle",
}

# Bright status colors for human prompt line (line 2)
_PROMPT_COLORS: dict[SessionStatus, str] = {
    SessionStatus.THINKING: "#00ff66",
    SessionStatus.EXECUTING: "#33aaff",
    SessionStatus.SUBAGENT_RUNNING: "#cc66ff",
    SessionStatus.WAITING_PERMISSION: "#ff3333",
    SessionStatus.IDLE: "#cc8800",
    SessionStatus.TERMINATED: "#444444",
    SessionStatus.UNKNOWN: "#444444",
}

# Uniform grey for system activity line (line 3) — calm, non-distracting
_ACTIVITY_COLOR = "#777777"


def _get_term_width() -> int:
    """Return the current terminal width in columns."""
    return shutil.get_terminal_size()[0]


def get_layout_config(term_width: int | None = None) -> dict[str, object]:
    """Return responsive layout configuration based on terminal width.

    Breakpoints (usable = term_width - 4 for padding/border):
      Wide (>=120): all columns including ctx
      Medium (>=90): drop ctx
      Narrow (<90): drop branch + ctx
    """
    tw = term_width if term_width is not None else _get_term_width()
    usable = tw - 4  # padding + border margin

    if usable >= 120:
        return {"proj_w": 22, "show_branch": True, "show_ctx": True}
    if usable >= 90:
        return {"proj_w": 18, "show_branch": True, "show_ctx": False}
    return {"proj_w": 14, "show_branch": False, "show_ctx": False}


_LABEL_MAX = 30


class SessionSprite(Static):
    """Fixed-width sprite display for session rows.

    Isolated widget so text content can never overflow into the sprite area.
    """


class SessionText(Static):
    """Session info text content — fills remaining width next to sprite."""


class SessionRow(Widget, can_focus=True):
    """Session row with sprite character and rich status-based coloring.

    Horizontal layout: fixed-width SessionSprite + flexible SessionText.
    The sprite is its own component so text overflow cannot bleed into it.

    SessionSprite (line 1-5): animated character
    SessionText:
      Line 1: status_badge | PROJECT | branch | [label]
      Line 2: last prompt
      Line 3: latest activity / agent response
      Line 4: cpu | elapsed | ctx  (or NEEDS HUMAN INTERVENTION)
      Line 5: (empty)
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
        super().__init__()
        self._sync_status_classes()

    def compose(self) -> ComposeResult:
        yield SessionSprite(self._build_sprite(), markup=True)
        yield SessionText(self._build_text(), markup=True)

    # ── Width helpers ──

    def _get_text_width(self) -> int:
        """Return available character width for the text content widget."""
        try:
            w = self.query_one(SessionText).content_size.width
            if w > 0:
                return w
        except Exception:
            pass
        # Fallback before mount: terminal width minus sprite and chrome
        return max(40, _get_term_width() - 22)

    # ── Content builders ──

    def _build_sprite(self) -> str:
        """Build the 5-line sprite column."""
        sp1, sp2, sp3, sp4, sp5 = get_sprite_frame(
            status=self.session.effective_status,
            anim_frame=self._anim_frame,
            sprite_idx=self._sprite_idx,
        )
        return f"{sp1}\n{sp2}\n{sp3}\n{sp4}\n{sp5}"

    def _build_text(self) -> str:
        """Build the 5-line text content adjacent to the sprite."""
        s = self.session
        status = s.effective_status
        icon = STATUS_ICONS.get(status, "?")
        label_text = STATUS_LABELS.get(status, "???")

        # Responsive layout
        layout = get_layout_config()
        proj_w: int = layout["proj_w"]  # type: ignore[assignment]
        show_branch: bool = layout["show_branch"]  # type: ignore[assignment]
        show_ctx: bool = layout["show_ctx"]  # type: ignore[assignment]

        project_upper = s.project_name.upper()
        project = project_upper[:proj_w - 1] + "\u2026" if len(project_upper) > proj_w else project_upper
        branch_raw = (
            s.hook_state.git_branch
            if s.hook_state and s.hook_state.git_branch
            else None
        )
        branch = (branch_raw[:9] + "\u2026") if branch_raw and len(branch_raw) > 10 else (branch_raw or "\u2014")
        cpu = (
            f"{s.process_info.cpu_percent:.0f}%"
            if s.process_info
            else "-"
        )
        ram = (
            format_memory(s.process_info.memory_mb)
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

        color = STATUS_COLORS.get(status, "#666666")
        proj_color = get_sprite_color(sprite_idx=self._sprite_idx)

        # Status badge (icon + label)
        status_badge = f"{icon} {label_text:<5s}"
        if status == SessionStatus.WAITING_PERMISSION:
            badge_markup = f"[{color} blink]{status_badge}[/]"
        elif status in _ACTIVE_BLINK_STATUSES:
            badge_markup = f"[{color} blink]{status_badge}[/]"
        else:
            badge_markup = f"[{color}]{status_badge}[/]"

        # Line 1: status badge + project pixel badge + branch + label
        proj_badge = (
            f"[{proj_color}]\u2590[/]"
            f"[bold #0a0a0a on {proj_color}] {project} [/]"
            f"[{proj_color}]\u258c[/]"
        )
        line1_parts = f"{badge_markup}  {proj_badge}"
        # Pad to keep alignment (badge has 2 extra chars from ▐▌ + spaces)
        pad_needed = max(0, proj_w - len(project) - 2)
        line1_parts += " " * pad_needed
        # Worktree indicator
        if s.is_worktree and s.worktree_name:
            wt_name = s.worktree_name.lower()
            if len(wt_name) > 20:
                wt_name = wt_name[:19] + "\u2026"
            line1_parts += f"  [dim #8a8a8a]\U0001f33f {wt_name}[/]"
        if show_branch:
            line1_parts += f"  [#3399ff]{branch:<10s}[/]"

        # User label — capped, appended on the right of line 1
        user_label = get_label(s.session_id)
        if user_label:
            capped = (user_label[:_LABEL_MAX - 1] + "\u2026") if len(user_label) > _LABEL_MAX else user_label
            line1_parts += f"  [#aaaaff]{capped}[/]"

        # Dim terminated rows
        if status == SessionStatus.TERMINATED:
            line1 = f"[dim]{line1_parts}[/]"
        else:
            line1 = line1_parts

        # Adaptive text length for lines 2-3
        text_w = self._get_text_width()
        desc_max = max(20, text_w - 7)  # 7 = "    └─ " prefix

        # Line 2: last prompt (always shown unless compact)
        prompt_text: str | None = None
        if not self._compact:
            prompt_text = _sanitize_prompt(self._get_prompt())

        if prompt_text:
            truncated = (prompt_text[:desc_max - 1] + "\u2026") if len(prompt_text) > desc_max else prompt_text
            text_color = _PROMPT_COLORS.get(status, "#555555")
            line2 = f"    [#555555]\u2514\u2500[/] [italic {text_color}]{truncated}[/]"
        else:
            line2 = "[#0a0a0a].[/]"

        # Line 3: latest activity / agent response
        activity_text: str | None = None
        if not self._compact:
            activity_raw = format_activity(s)
            activity_text = (activity_raw[:desc_max - 1] + "\u2026") if len(activity_raw) > desc_max else activity_raw

        if activity_text:
            line3 = f"    [#555555]\u2514\u2500[/] [{_ACTIVITY_COLOR}]{activity_text}[/]"
        else:
            line3 = "[#0a0a0a].[/]"

        # Line 4: cpu/elapsed/ctx  (or NEEDS HUMAN INTERVENTION)
        if status == SessionStatus.WAITING_PERMISSION:
            line4 = f"    [bold #ff3333 blink]\u26a0 NEEDS HUMAN INTERVENTION[/]"
        else:
            line4 = f"    [#555555]{cpu:>5s}[/]  [#555555]{ram:>6s}[/]  [#444444]{elapsed}[/]"
            if show_ctx:
                line4 += f"  [#888888]{ctx:>6s}[/]"

        line5 = "[#0a0a0a].[/]"

        return f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}"

    def _build_content(self) -> str:
        """Combined sprite + text content (backward-compatible for tests)."""
        sprite_lines = self._build_sprite().split("\n")
        text_lines = self._build_text().split("\n")
        return "\n".join(f" {s} {t}" for s, t in zip(sprite_lines, text_lines))

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
        try:
            self.query_one(SessionSprite).update(self._build_sprite())
            self.query_one(SessionText).update(self._build_text())
        except Exception:
            pass  # Not yet composed (e.g. in unit tests)

    def _sync_status_classes(self) -> None:
        """Sync CSS classes based on session status (needs-input + status bar)."""
        status = self.session.effective_status
        if status == SessionStatus.WAITING_PERMISSION:
            self.add_class("needs-input")
        else:
            self.remove_class("needs-input")

        # Status bar class
        target_class = _STATUS_TO_BAR_CLASS.get(status)
        for cls in _STATUS_BAR_CLASSES:
            if cls == target_class:
                self.add_class(cls)
            else:
                self.remove_class(cls)

    def update_session(self, session: MergedSession) -> None:
        """Update row with new session data without recreating widget."""
        self.session = session
        self._sync_status_classes()
        self.refresh_content()

    def on_click(self) -> None:
        self.post_message(self.Selected(self.session_id))

    def action_select(self) -> None:
        self.post_message(self.Selected(self.session_id))
