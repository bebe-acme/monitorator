from __future__ import annotations

from textual.message import Message
from textual.widgets import Static

from monitorator.context_size import _format_tokens
from monitorator.models import MergedSession, SessionStatus
from monitorator.tui.sprites import SPRITE_TEMPLATES, render_sprite
from monitorator.tui.theme_colors import colors

_ACTIVE_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# ── Ghost sprite (palette adapts to theme) ──
_GHOST_GRID = SPRITE_TEMPLATES[1]


def _ghost_palette() -> dict[int, str]:
    return {2: colors.accent, 3: colors.text_bright, 4: colors.bg_base}

# Pupil row variants for eye animation (row index 4 of the ghost grid).
# Each eye is 2px wide (cols 3-4 and 7-8). Pupil (value 4) shifts left↔right.
_PUPIL_DOWN_LEFT = [0, 2, 2, 4, 3, 2, 2, 4, 3, 2, 2, 0]
_PUPIL_DOWN_RIGHT = [0, 2, 2, 3, 4, 2, 2, 3, 4, 2, 2, 0]  # default
_EYE_FRAMES = [_PUPIL_DOWN_RIGHT, _PUPIL_DOWN_LEFT]
_EYE_TICKS_PER_FRAME = 5  # change eye position every ~1.5s (5 * 0.3s)

_GAP = "  "


class RefreshRequested(Message):
    """Posted when the user clicks the header banner to request a refresh."""


def count_sessions(sessions: list[MergedSession]) -> dict[str, int]:
    """Count sessions by status category."""
    total = len(sessions)
    active = sum(1 for s in sessions if s.effective_status in _ACTIVE_STATUSES)
    idle = sum(1 for s in sessions if s.effective_status == SessionStatus.IDLE)
    waiting = sum(
        1 for s in sessions if s.effective_status == SessionStatus.WAITING_PERMISSION
    )
    return {"total": total, "active": active, "idle": idle, "waiting": waiting}


class HeaderBanner(Static):
    """Header banner with ghost logo, title, and stats.

    Uses CSS border for framing -- no manual box-drawing characters.
    Content is 5 lines tall (matching the ghost sprite height).

    Layout (each line starts with one ghost sprite line + 2-space gap):
      Line 1: ghost (top)
      Line 2: ghost
      Line 3: ghost + session stats (total + active + idle + waiting)
      Line 4: ghost + MONITORATOR title
      Line 5: ghost (bottom)
    """

    def __init__(self) -> None:
        super().__init__("")
        self._stats_text = ""
        self._eye_tick: int = 0
        self._eye_frame: int = 0
        self._do_render()

    # CRITICAL: never define _render_content -- it shadows Textual 8 internals.

    def tick_eyes(self) -> None:
        """Advance the eye animation by one tick (called from app's _tick_sprites)."""
        self._eye_tick += 1
        if self._eye_tick % _EYE_TICKS_PER_FRAME == 0:
            self._eye_frame = (self._eye_frame + 1) % len(_EYE_FRAMES)
            self._do_render()

    def _do_render(self) -> None:
        """Rebuild the Rich markup and push it into the Static widget."""
        grid = list(_GHOST_GRID)
        grid[4] = _EYE_FRAMES[self._eye_frame]
        ghost = render_sprite(grid, _ghost_palette())

        if self._stats_text:
            stats_line = self._stats_text
        else:
            stats_line = f"[{colors.text_dimmer}]waiting for sessions\u2026[/]"

        title = f"[bold {colors.accent}]MONITORATOR[/]"

        line1 = f"{ghost[0]}"
        line2 = f"{ghost[1]}"
        line3 = f"{ghost[2]}{_GAP}{stats_line}"
        line4 = f"{ghost[3]}{_GAP}{title}"
        line5 = f"{ghost[4]}"

        self.update(f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}")

    def on_click(self) -> None:
        """Click anywhere on the header to trigger a refresh."""
        self.post_message(RefreshRequested())

    def update_counts(
        self,
        sessions: list[MergedSession],
        sort_mode: str = "time",
        filter_mode: str = "all",
        tokens_used: int = 0,
        theme_name: str = "dark",
    ) -> None:
        """Recompute stats from live session list and re-render."""
        counts = count_sessions(sessions)

        parts: list[str] = []
        parts.append(
            f"[bold {colors.accent}]\u25c6 {counts['total']}[/] [{colors.text_muted}]sessions[/]"
        )
        if counts["active"]:
            parts.append(
                f"[bold {colors.status_thinking}]\u25cf {counts['active']}[/] [{colors.text_muted}]active[/]"
            )
        if counts["idle"]:
            parts.append(
                f"[{colors.text_dimmer}]\u25cb {counts['idle']} idle[/]"
            )
        if counts["waiting"]:
            parts.append(
                f"[bold {colors.status_permission}]\u26a0 {counts['waiting']}[/]"
            )

        # Token usage since TUI start
        parts.append(
            f"[{colors.status_subagent}]\u2261 {_format_tokens(tokens_used)} tokens[/]"
        )

        # Sort/filter/theme indicators (only show non-defaults)
        if sort_mode != "time":
            parts.append(f"[{colors.text_muted}]\u2195 {sort_mode}[/]")
        if filter_mode != "all":
            parts.append(f"[{colors.status_idle}]\u25b6 {filter_mode}[/]")
        parts.append(f"[{colors.text_muted}]\u25d0 {theme_name}[/]")

        self._stats_text = "  ".join(parts)
        self._do_render()
