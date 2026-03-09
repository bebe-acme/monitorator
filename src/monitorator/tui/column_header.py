from __future__ import annotations

from textual.widgets import Static

from monitorator.tui.session_row import get_layout_config


class ColumnHeader(Static, can_focus=False):
    """Responsive column header row with separator — DexScreener table aesthetic."""

    def __init__(self) -> None:
        super().__init__(self._build_content(), markup=True)

    def rebuild(self) -> None:
        """Rebuild header to match current terminal width."""
        self.update(self._build_content())

    def _build_content(self) -> str:
        layout = get_layout_config()
        proj_w: int = layout["proj_w"]  # type: ignore[assignment]
        act_w: int = layout["act_w"]  # type: ignore[assignment]
        show_branch: bool = layout["show_branch"]  # type: ignore[assignment]
        show_pid: bool = layout["show_pid"]  # type: ignore[assignment]
        show_ctx: bool = layout["show_ctx"]  # type: ignore[assignment]

        # Build header labels — widths match session_row columns
        # sprite(12) + space(1) + idx(2) + pad(2) = 17 chars before STATUS
        parts = f"{'':>17s}{'STATUS':<9s}{'PROJECT':<{proj_w + 2}s}"
        if show_branch:
            parts += f"{'BRANCH':<12s}"
        if show_pid:
            parts += f"{'PID':>6s}  "
        parts += f"{'DESCRIPTION':<{act_w + 2}s}"
        if show_ctx:
            parts += f"  {'CTX':>6s}"

        header = f"[#888888]{parts}[/]"

        # Separator line — match total width
        sep_w = 17 + 9 + proj_w + 2
        if show_branch:
            sep_w += 12
        if show_pid:
            sep_w += 8
        sep_w += act_w + 2
        if show_ctx:
            sep_w += 8

        separator = f"[#888888]{'\u2500' * sep_w}[/]"
        return f"{header}\n{separator}"
