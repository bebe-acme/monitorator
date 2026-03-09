from __future__ import annotations

from unittest.mock import patch

import pytest


def _patch_wide():
    """Patch terminal width to 200 (shows all columns)."""
    return patch("monitorator.tui.session_row._get_term_width", return_value=200)


def _patch_narrow():
    """Patch terminal width to 80 (hides branch, pid, ctx)."""
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
        assert "DESCRIPTION" in content

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

    def test_renders_pid_column_wide(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "PID" in content
        branch_pos = content.find("BRANCH")
        pid_pos = content.find("PID")
        desc_pos = content.find("DESCRIPTION")
        assert branch_pos < pid_pos < desc_pos

    def test_gray_color_in_markup(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "#888888" in content

    def test_renders_ctx_column_wide(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "CTX" in content
        desc_pos = content.find("DESCRIPTION")
        ctx_pos = content.find("CTX")
        assert desc_pos < ctx_pos

    def test_narrow_hides_branch(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "BRANCH" not in content

    def test_narrow_hides_pid(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "PID" not in content

    def test_narrow_hides_ctx(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "CTX" not in content

    def test_narrow_still_has_core_columns(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_narrow():
            widget = ColumnHeader()
            content = widget._build_content()
        assert "STATUS" in content
        assert "PROJECT" in content
        assert "DESCRIPTION" in content

    def test_rebuild_updates_content(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        with _patch_wide():
            widget = ColumnHeader()
            assert "BRANCH" in widget._build_content()

        with _patch_narrow():
            widget.rebuild()
            assert "BRANCH" not in widget._build_content()
