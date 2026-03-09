from __future__ import annotations

from datetime import datetime

from textual.widgets import Static

from monitorator.models import MergedSession, SessionStatus

_ACTIVE_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
}

# ── Half-block pixel art logo (2-line chunky retro font) ──
_ART_L1 = "█▄█▄█ ▄▀▀▄ █▄ █ █ ▀█▀ ▄▀▀▄ █▀▄ ▄▀▀▄ ▀█▀ ▄▀▀▄ █▀▄"
_ART_L2 = "█ ▀ █ ▀▄▄▀ █ ▀█ █  █  ▀▄▄▀ █▀▄ █▀▀█  █  ▀▄▄▀ █▀▄"

# ── Box-drawing characters ─────────────────────────────────
_TL = "\u2554"  # ╔
_TR = "\u2557"  # ╗
_BL = "\u255a"  # ╚
_BR = "\u255d"  # ╝
_H = "\u2550"   # ═
_V = "\u2551"   # ║

_BOX_WIDTH = 92


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
    """Bordered header banner with block logo, stats, and timestamp."""

    def __init__(self) -> None:
        super().__init__("")
        self._stats_text = ""
        self._do_render()

    # CRITICAL: never define _render_content — it shadows Textual 8 internals.

    def _do_render(self) -> None:
        """Rebuild the Rich markup and push it into the Static widget."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self._stats_text:
            stats_parts = self._stats_text.split("\n", 1)
            stats_l1 = stats_parts[0] if len(stats_parts) > 0 else ""
            stats_l2 = stats_parts[1] if len(stats_parts) > 1 else ""
        else:
            stats_l1 = "[#666666]waiting for sessions\u2026[/]"
            stats_l2 = ""

        top = f"[#333300]{_TL}{_H * (_BOX_WIDTH - 2)}{_TR}[/]"

        # Line 1: pixel art top + stats + timestamp
        line1 = (
            f"[#333300]{_V}[/]  "
            f"[bold #ffcc00]{_ART_L1}[/]"
            f"     {stats_l1}"
            f"  [#666666]{timestamp}[/]"
            f"  [#333300]{_V}[/]"
        )

        # Line 2: pixel art bottom + idle stats
        line2 = (
            f"[#333300]{_V}[/]  "
            f"[bold #ffcc00]{_ART_L2}[/]"
            f"     {stats_l2}"
            f"    [#333300]{_V}[/]"
        )

        bottom = f"[#333300]{_BL}{_H * (_BOX_WIDTH - 2)}{_BR}[/]"

        self.update(f"{top}\n{line1}\n{line2}\n{bottom}")

    def update_counts(self, sessions: list[MergedSession]) -> None:
        """Recompute stats from live session list and re-render."""
        counts = count_sessions(sessions)

        # ── Line 1 right: total + active + waiting ──────────
        parts_l1: list[str] = []
        parts_l1.append(
            f"[bold #ffcc00]\u25c6 {counts['total']}[/] [#999999]sessions[/]"
        )
        if counts["active"]:
            parts_l1.append(
                f"[bold #00ff66 blink]\u25cf[/] [bold #00ff66]{counts['active']}[/] [#999999]active[/]"
            )
        if counts["waiting"]:
            parts_l1.append(
                f"[bold #ff3333 blink]\u26a0 {counts['waiting']}[/]"
            )

        # ── Line 2 right: idle ──────────────────────────────
        parts_l2: list[str] = []
        if counts["idle"]:
            parts_l2.append(
                f"[#666666]\u25cb {counts['idle']} idle[/]"
            )

        self._stats_text = (
            "  ".join(parts_l1)
            + "\n"
            + "  ".join(parts_l2)
        )
        self._do_render()
