from __future__ import annotations

from unittest.mock import patch

import pytest


def _patch_wide():
    """Patch terminal width to 200 (shows all columns)."""
    return patch("monitorator.tui.session_row._get_term_width", return_value=200)


def _patch_narrow():
    """Patch terminal width to 80 (hides branch)."""
    return patch("monitorator.tui.session_row._get_term_width", return_value=80)


class TestColumnHeader:
    def test_renders_column_names_wide(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "STATUS" in content
        assert "PROJECT" in content
        assert "BRANCH" in content

    def test_renders_separator_line(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "\u2500" in content  # ─ horizontal line char

    def test_has_two_lines(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            content = widget._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 2

    def test_not_focusable(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        assert widget.can_focus is False

    def test_gray_color_in_markup(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "#888888" in content

    def test_narrow_hides_branch(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "BRANCH" not in content

    def test_narrow_still_has_core_columns(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "STATUS" in content
        assert "PROJECT" in content

    def test_rebuild_updates_content(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            assert "BRANCH" in widget._build_content()

        with _patch_narrow():
            widget.rebuild()
            assert "BRANCH" not in widget._build_content()
