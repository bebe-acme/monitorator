from __future__ import annotations

import pytest


class TestColumnHeader:
    def test_renders_column_names(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "#" in content
        assert "STATUS" in content
        assert "PROJECT" in content
        assert "BRANCH" in content
        assert "DESCRIPTION" in content
        assert "CPU" in content
        assert "TIME" in content

    def test_renders_separator_line(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "\u2500" in content  # ─ horizontal line char

    def test_has_two_lines(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 2

    def test_not_focusable(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        assert widget.can_focus is False

    def test_renders_pid_column(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "PID" in content
        # PID should come after BRANCH
        branch_pos = content.find("BRANCH")
        pid_pos = content.find("PID")
        desc_pos = content.find("DESCRIPTION")
        assert branch_pos < pid_pos < desc_pos

    def test_gray_color_in_markup(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "#666666" in content or "#888888" in content

    def test_renders_ctx_column(self) -> None:
        from monitorator.tui.column_header import ColumnHeader

        widget = ColumnHeader()
        content = widget._build_content()
        assert "CTX" in content
        # CTX should come after TIME
        time_pos = content.find("TIME")
        ctx_pos = content.find("CTX")
        assert time_pos < ctx_pos
