from __future__ import annotations

from textual.message import Message
from textual.widgets import Static

from monitorator.context_size import _format_tokens
from monitorator.models import MergedSession, SessionStatus
from monitorator.tui.sprites import SPRITE_TEMPLATES, render_sprite

_ACTIVE_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# ── Ghost sprite (yellow palette for header logo) ──
_GHOST_GRID = SPRITE_TEMPLATES[1]
_GHOST_PALETTE = {2: "#ffcc00", 3: "#ffffff", 4: "#0a0a0a"}

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
        self._do_render()

    # CRITICAL: never define _render_content -- it shadows Textual 8 internals.

    def _do_render(self) -> None:
        """Rebuild the Rich markup and push it into the Static widget."""
        ghost = render_sprite(_GHOST_GRID, _GHOST_PALETTE)

        if self._stats_text:
            stats_line = self._stats_text
        else:
            stats_line = "[#666666]waiting for sessions\u2026[/]"

        title = "[bold #ffcc00]MONITORATOR[/]"

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
    ) -> None:
        """Recompute stats from live session list and re-render."""
        counts = count_sessions(sessions)

        parts: list[str] = []
        parts.append(
            f"[bold #ffcc00]\u25c6 {counts['total']}[/] [#999999]sessions[/]"
        )
        if counts["active"]:
            parts.append(
                f"[bold #00ff66]\u25cf {counts['active']}[/] [#999999]active[/]"
            )
        if counts["idle"]:
            parts.append(
                f"[#666666]\u25cb {counts['idle']} idle[/]"
            )
        if counts["waiting"]:
            parts.append(
                f"[bold #ff3333]\u26a0 {counts['waiting']}[/]"
            )

        # Token usage since TUI start
        parts.append(
            f"[#cc66ff]\u2261 {_format_tokens(tokens_used)} tokens[/]"
        )

        # Sort/filter indicators (only show non-defaults)
        if sort_mode != "time":
            parts.append(f"[#888888]\u2195 {sort_mode}[/]")
        if filter_mode != "all":
            parts.append(f"[#cc8800]\u25b6 {filter_mode}[/]")

        self._stats_text = "  ".join(parts)
        self._do_render()
