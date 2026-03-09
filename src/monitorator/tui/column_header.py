from __future__ import annotations

from textual.widgets import Static


class ColumnHeader(Static, can_focus=False):
    """Static column header row with separator — DexScreener table aesthetic."""

    def __init__(self) -> None:
        super().__init__(self._build_content(), markup=True)

    def _build_content(self) -> str:
        header = (
            "[#888888]"
            "   #  STATUS      PROJECT             BRANCH       PID  "
            "DESCRIPTION                          CPU    TIME       CTX"
            "[/]"
        )
        separator = (
            "[#888888]"
            "  \u2500\u2500\u2500 "
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500  "
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500  "
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500  "
            "\u2500\u2500\u2500\u2500\u2500\u2500 "
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 "
            "\u2500\u2500\u2500\u2500\u2500\u2500 "
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500  "
            "\u2500\u2500\u2500\u2500\u2500\u2500"
            "[/]"
        )
        return f"{header}\n{separator}"
