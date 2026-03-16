from __future__ import annotations

from textual.widgets import Static

from monitorator.tui.session_row import get_layout_config
from monitorator.tui.theme_colors import colors


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
        show_branch: bool = layout["show_branch"]  # type: ignore[assignment]

        # Build header labels — widths match session_row columns
        # sprite(12) + space(1) + badge(7) + pad(2) = 22 chars before PROJECT
        # But badge uses 7 visual chars with left-pad of 5 → "STATUS" at offset 14
        parts = f"{'':>14s}{'STATUS':<9s}{'PROJECT':<{proj_w + 2}s}"
        if show_branch:
            parts += f"{'BRANCH':<12s}"

        header = f"[{colors.text_muted}]{parts}[/]"

        # Separator line — match total width
        sep_w = 14 + 9 + proj_w + 2
        if show_branch:
            sep_w += 12

        separator = f"[{colors.text_muted}]{'\u2500' * sep_w}[/]"
        return f"{header}\n{separator}"
