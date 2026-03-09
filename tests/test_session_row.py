from __future__ import annotations

import time

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus


def make_merged(
    session_id: str = "test-1",
    project: str = "TestProj",
    status: SessionStatus = SessionStatus.THINKING,
    branch: str = "main",
    tool: str | None = "Edit",
    tool_summary: str | None = "file_path: src/app.py",
    prompt: str | None = "Build the monitor",
    cpu: float = 20.0,
    elapsed: int = 300,
    stale: bool = False,
    subagent_count: int = 0,
    updated_at: float | None = None,
    hook_state: bool = True,
    cwd: str | None = None,
    session_uuid: str | None = None,
) -> MergedSession:
    effective_cwd = cwd or f"/tmp/{project.lower()}"
    hs = (
        SessionState(
            session_id=session_id,
            cwd=effective_cwd,
            project_name=project,
            status=status,
            git_branch=branch,
            last_tool=tool,
            last_tool_input_summary=tool_summary,
            last_prompt_summary=prompt,
            updated_at=updated_at or time.time(),
            subagent_count=subagent_count,
        )
        if hook_state
        else None
    )
    return MergedSession(
        session_id=session_id,
        hook_state=hs,
        process_info=ProcessInfo(
            pid=12345,
            cpu_percent=cpu,
            elapsed_seconds=elapsed,
            cwd=effective_cwd,
            command="claude",
            session_uuid=session_uuid,
        ),
        effective_status=status,
        is_stale=stale,
    )


class TestSessionRowContent:
    def test_content_lines(self) -> None:
        """SessionRow renders 1 line without prompt, 2 lines with prompt."""
        from monitorator.tui.session_row import SessionRow

        # With hook prompt → 2 lines
        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 2

        # Without prompt → 1 line
        session_no_prompt = make_merged(prompt=None, tool=None, tool_summary=None)
        row2 = SessionRow(session_no_prompt)
        content2 = row2._build_content()
        lines2 = content2.strip().split("\n")
        assert len(lines2) == 1

    def test_contains_project_name(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="agentator")
        row = SessionRow(session)
        content = row._build_content()
        assert "agentator" in content

    def test_contains_branch(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(branch="feat/ui")
        row = SessionRow(session)
        content = row._build_content()
        assert "feat/ui" in content

    def test_contains_status_icon(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        content = row._build_content()
        assert "\u25cf" in content  # ● thinking icon

    def test_contains_status_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        content = row._build_content()
        assert "THINK" in content

    def test_contains_cpu(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(cpu=45.0)
        row = SessionRow(session)
        content = row._build_content()
        assert "45%" in content

    def test_contains_elapsed(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(elapsed=323)
        row = SessionRow(session)
        content = row._build_content()
        assert "5m 23s" in content

    def test_description_never_empty(self) -> None:
        """Description column must always have text."""
        from monitorator.tui.session_row import SessionRow

        for status in SessionStatus:
            session = make_merged(
                status=status,
                tool=None,
                tool_summary=None,
                prompt=None,
            )
            row = SessionRow(session)
            content = row._build_content()
            # The content should contain some meaningful activity text
            assert content.strip() != ""

    def test_no_branch_shows_dash(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(branch=None)  # type: ignore[arg-type]
        row = SessionRow(session)
        content = row._build_content()
        assert "\u2014" in content  # em-dash

    def test_no_process_info_shows_dash_for_cpu(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = MergedSession(
            session_id="test",
            hook_state=SessionState(
                session_id="test",
                cwd="/tmp/test",
                project_name="Test",
                status=SessionStatus.THINKING,
                updated_at=time.time(),
            ),
            process_info=None,
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )
        row = SessionRow(session)
        content = row._build_content()
        # Should have dash for cpu/time when no process info
        assert "-" in content


class TestSessionRowIndex:
    def test_update_index(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged()
        row = SessionRow(session)
        row.update_index(3)
        assert row._row_index == 3

    def test_index_in_content(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged()
        row = SessionRow(session)
        row.update_index(5)
        content = row._build_content()
        assert "5" in content


class TestSessionRowWidget:
    @pytest.mark.asyncio
    async def test_row_is_focusable(self) -> None:
        from monitorator.tui.session_row import SessionRow

        row = SessionRow(make_merged())
        assert row.can_focus is True

    @pytest.mark.asyncio
    async def test_row_stores_session_id(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(session_id="abc-123")
        row = SessionRow(session)
        assert row.session_id == "abc-123"

    @pytest.mark.asyncio
    async def test_update_session(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session1 = make_merged(session_id="abc", project="Old")
        row = SessionRow(session1)
        session2 = make_merged(session_id="abc", project="New")
        row.update_session(session2)
        assert row.session.project_name == "New"

    @pytest.mark.asyncio
    async def test_selected_message_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        msg = SessionRow.Selected("test-id")
        assert msg.session_id == "test-id"


class TestSessionRowColors:
    def test_different_indexes_get_different_project_colors(self) -> None:
        from monitorator.tui.session_row import SessionRow, SESSION_COLORS

        # Use IDLE status — palette colors only apply to non-full-row statuses
        session = make_merged(project="ProjA", status=SessionStatus.IDLE, prompt=None)
        row1 = SessionRow(session)
        row1.update_index(1)
        row2 = SessionRow(session)
        row2.update_index(2)

        content1 = row1._build_content()
        content2 = row2._build_content()

        # Each row should use a different color from the palette
        color1 = SESSION_COLORS[(1 - 1) % len(SESSION_COLORS)]
        color2 = SESSION_COLORS[(2 - 1) % len(SESSION_COLORS)]
        assert color1 in content1
        assert color2 in content2
        assert color1 != color2

    def test_session_colors_palette_has_at_least_6(self) -> None:
        from monitorator.tui.session_row import SESSION_COLORS

        assert len(SESSION_COLORS) >= 6


class TestSessionRowPromptLine:
    def test_shows_session_prompt_on_second_line(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            hook_state=False,
            project="MyProj",
        )
        session.process_info.session_uuid = "abc12345-dead-beef-cafe-123456789abc"  # type: ignore[union-attr]

        with patch("monitorator.tui.session_row.get_session_prompt", return_value="Implement auth flow"):
            row = SessionRow(session)
            content = row._build_content()

        assert "Implement auth flow" in content
        lines = content.strip().split("\n")
        assert len(lines) == 2

    def test_no_prompt_stays_single_line(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="Simple", prompt=None, tool=None, tool_summary=None)
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 1


class TestSessionRowPermission:
    def test_waiting_permission_shows_warning(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            status=SessionStatus.WAITING_PERMISSION,
            tool="Bash",
            tool_summary="command: rm -rf dist",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "PERM!" in content
        assert "Permission" in content

    def test_executing_shows_exec_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING)
        row = SessionRow(session)
        content = row._build_content()
        assert "EXEC" in content


class TestSessionRowPid:
    def test_pid_shown_in_row(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="PidProj")
        row = SessionRow(session)
        content = row._build_content()
        assert "12345" in content

    def test_pid_dash_when_no_process(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = MergedSession(
            session_id="test",
            hook_state=SessionState(
                session_id="test",
                cwd="/tmp/test",
                project_name="Test",
                status=SessionStatus.THINKING,
                updated_at=time.time(),
            ),
            process_info=None,
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )
        row = SessionRow(session)
        content = row._build_content()
        # PID column should show "-" when no process
        # Count occurrences — should have at least one "-" for PID
        assert "[#666666]" in content
        # The PID area should contain a dash
        assert "     -" in content or "    -" in content


class TestSessionRowSpinner:
    def test_active_session_has_spinner(self) -> None:
        from monitorator.tui.session_row import SessionRow, _ANIM_THINKING

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        row._anim_frame = 0
        content = row._build_content()
        assert _ANIM_THINKING[0] in content

    def test_spinner_cycles_on_refresh(self) -> None:
        from monitorator.tui.session_row import SessionRow, _ANIM_THINKING

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        row._anim_frame = 0
        content0 = row._build_content()
        row._anim_frame = 1
        content1 = row._build_content()
        assert _ANIM_THINKING[0] in content0
        assert _ANIM_THINKING[1] in content1
        assert _ANIM_THINKING[0] != _ANIM_THINKING[1]

    def test_idle_session_has_no_spinner(self) -> None:
        from monitorator.tui.session_row import (
            SessionRow,
            _ANIM_THINKING,
            _ANIM_EXECUTING,
            _ANIM_SUBAGENT,
            _ANIM_PERMISSION,
        )

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        all_frames = _ANIM_THINKING + _ANIM_EXECUTING + _ANIM_SUBAGENT + _ANIM_PERMISSION
        for frame in all_frames:
            assert frame not in content

    def test_terminated_session_has_no_spinner(self) -> None:
        from monitorator.tui.session_row import (
            SessionRow,
            _ANIM_THINKING,
            _ANIM_EXECUTING,
            _ANIM_SUBAGENT,
            _ANIM_PERMISSION,
        )

        session = make_merged(status=SessionStatus.TERMINATED, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        all_frames = _ANIM_THINKING + _ANIM_EXECUTING + _ANIM_SUBAGENT + _ANIM_PERMISSION
        for frame in all_frames:
            assert frame not in content

    def test_spinner_frames_has_at_least_8_frames(self) -> None:
        from monitorator.tui.session_row import (
            _ANIM_THINKING,
            _ANIM_EXECUTING,
            _ANIM_SUBAGENT,
            _ANIM_PERMISSION,
        )

        assert len(_ANIM_THINKING) >= 8
        assert len(_ANIM_EXECUTING) >= 8
        assert len(_ANIM_SUBAGENT) >= 8
        assert len(_ANIM_PERMISSION) >= 8

    def test_spinner_frames_are_multi_char(self) -> None:
        """Each spinner frame should be 5 chars wide for all animation sets."""
        from monitorator.tui.session_row import (
            _ANIM_THINKING,
            _ANIM_EXECUTING,
            _ANIM_SUBAGENT,
            _ANIM_PERMISSION,
        )

        for name, frames in [
            ("THINKING", _ANIM_THINKING),
            ("EXECUTING", _ANIM_EXECUTING),
            ("SUBAGENT", _ANIM_SUBAGENT),
            ("PERMISSION", _ANIM_PERMISSION),
        ]:
            for i, frame in enumerate(frames):
                assert len(frame) == 5, (
                    f"{name} frame {i} is {len(frame)} chars, expected 5: {frame!r}"
                )

    def test_spinner_uses_block_elements(self) -> None:
        """All animation sets should use lower block Unicode chars."""
        from monitorator.tui.session_row import (
            _ANIM_THINKING,
            _ANIM_EXECUTING,
            _ANIM_SUBAGENT,
            _ANIM_PERMISSION,
        )

        block_chars = set("\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588\u2591\u2593")
        for name, frames in [
            ("THINKING", _ANIM_THINKING),
            ("EXECUTING", _ANIM_EXECUTING),
            ("SUBAGENT", _ANIM_SUBAGENT),
            ("PERMISSION", _ANIM_PERMISSION),
        ]:
            for frame in frames:
                assert any(ch in block_chars for ch in frame), (
                    f"{name} frame {frame!r} has no block elements"
                )

    def test_thinking_and_executing_have_different_animations(self) -> None:
        """THINKING and EXECUTING should produce different spinner text at same frame."""
        from monitorator.tui.session_row import SessionRow, _ANIM_THINKING, _ANIM_EXECUTING

        thinking_session = make_merged(status=SessionStatus.THINKING, prompt=None)
        thinking_row = SessionRow(thinking_session)
        thinking_row._anim_frame = 0
        thinking_content = thinking_row._build_content()

        executing_session = make_merged(status=SessionStatus.EXECUTING, prompt=None)
        executing_row = SessionRow(executing_session)
        executing_row._anim_frame = 0
        executing_content = executing_row._build_content()

        assert _ANIM_THINKING[0] in thinking_content
        assert _ANIM_EXECUTING[0] in executing_content
        assert _ANIM_THINKING[0] != _ANIM_EXECUTING[0]

    def test_subagent_has_unique_animation(self) -> None:
        """SUBAGENT_RUNNING gets its own animation different from THINKING."""
        from monitorator.tui.session_row import SessionRow, _ANIM_THINKING, _ANIM_SUBAGENT

        subagent_session = make_merged(status=SessionStatus.SUBAGENT_RUNNING, prompt=None)
        subagent_row = SessionRow(subagent_session)
        subagent_row._anim_frame = 0
        subagent_content = subagent_row._build_content()

        assert _ANIM_SUBAGENT[0] in subagent_content
        assert _ANIM_SUBAGENT[0] != _ANIM_THINKING[0]

    def test_permission_has_strobe_animation(self) -> None:
        """WAITING_PERMISSION gets animation (not just blank)."""
        from monitorator.tui.session_row import SessionRow, _ANIM_PERMISSION

        permission_session = make_merged(status=SessionStatus.WAITING_PERMISSION, prompt=None)
        permission_row = SessionRow(permission_session)
        permission_row._anim_frame = 0
        content = permission_row._build_content()

        assert _ANIM_PERMISSION[0] in content

    def test_spinner_color_varies_by_status(self) -> None:
        """Each status should use its own spinner color."""
        from monitorator.tui.session_row import SessionRow, _SPINNER_COLORS

        test_cases = [
            (SessionStatus.THINKING, "#00ff66"),
            (SessionStatus.EXECUTING, "#00ccff"),
            (SessionStatus.SUBAGENT_RUNNING, "#cc66ff"),
            (SessionStatus.WAITING_PERMISSION, "#ff3333"),
        ]
        for status, expected_color in test_cases:
            assert _SPINNER_COLORS[status] == expected_color
            session = make_merged(status=status, prompt=None)
            row = SessionRow(session)
            row._anim_frame = 0
            content = row._build_content()
            assert expected_color in content, (
                f"Status {status.name} should use color {expected_color}"
            )

    def test_status_animations_map_has_all_active_statuses(self) -> None:
        """_STATUS_ANIMATIONS should map THINKING, EXECUTING, SUBAGENT_RUNNING, WAITING_PERMISSION."""
        from monitorator.tui.session_row import _STATUS_ANIMATIONS

        assert SessionStatus.THINKING in _STATUS_ANIMATIONS
        assert SessionStatus.EXECUTING in _STATUS_ANIMATIONS
        assert SessionStatus.SUBAGENT_RUNNING in _STATUS_ANIMATIONS
        assert SessionStatus.WAITING_PERMISSION in _STATUS_ANIMATIONS


class TestSessionRowFullRowBlink:
    """Active sessions (THINKING/EXECUTING/SUBAGENT) blink the ENTIRE row."""

    def test_thinking_has_full_row_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content
        # The blink should wrap more than just the icon
        assert content.count("blink") >= 1

    def test_executing_has_full_row_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content

    def test_idle_has_no_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" not in content

    def test_permission_has_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content
        assert "\u26a0\u26a0" in content


class TestSessionRowTerminatedDim:
    """TERMINATED sessions should have dim styling."""

    def test_terminated_has_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.TERMINATED, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" in content

    def test_thinking_not_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" not in content

    def test_idle_not_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" not in content


class TestSessionRowPaletteColoring:
    """ALL statuses use palette color for project name."""

    @pytest.mark.parametrize("status", list(SessionStatus))
    def test_all_statuses_use_palette_color_for_project(self, status: SessionStatus) -> None:
        from monitorator.tui.session_row import SessionRow, SESSION_COLORS

        session = make_merged(status=status, project="MyProject", prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        content = row._build_content()
        expected_color = SESSION_COLORS[0]
        assert f"bold {expected_color}" in content
        assert "MyProject" in content


class TestSessionRowPidPosition:
    """PID should appear between BRANCH and DESCRIPTION columns."""

    def test_pid_after_branch_before_activity(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="TestProj", branch="main")
        row = SessionRow(session)
        row.update_index(1)
        content = row._build_content()
        # PID (12345) should come after branch (main) and before activity text
        main_pos = content.find("main")
        pid_pos = content.find("12345")
        activity_pos = content.find("Editing")  # format_activity result for Edit tool
        assert main_pos < pid_pos < activity_pos, (
            f"Column order wrong: main@{main_pos}, pid@{pid_pos}, activity@{activity_pos}"
        )


class TestSessionRowIdleAmber:
    """IDLE sessions should use amber color and return symbol icon."""

    def test_idle_row_contains_amber_color_and_return_icon(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "#ffaa00" in content
        assert "\u23ce" in content  # ⏎ return symbol

    def test_idle_row_contains_wait_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "WAIT" in content


class TestSessionRowPromptSanitization:
    def test_xml_tags_filtered_from_prompt(self) -> None:
        """Prompts starting with XML tags should not appear."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            prompt="<task-notification><task-id>abc</task-id></task-notification>",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "<task-notification>" not in content

    def test_system_reminder_filtered(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            prompt="<system-reminder>You must do X</system-reminder>",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "<system-reminder>" not in content

    def test_newlines_stripped_from_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Line one\nLine two\nLine three")
        row = SessionRow(session)
        content = row._build_content()
        # Should be single prompt line, no extra newlines from prompt text
        lines = content.strip().split("\n")
        assert len(lines) == 2  # main line + prompt line only

    def test_empty_after_sanitization_hides_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="<system-reminder>internal only</system-reminder>")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # no prompt line

    def test_sanitize_prompt_truncates_to_120_chars(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        long_text = "A" * 200
        result = _sanitize_prompt(long_text)
        assert result is not None
        assert len(result) <= 120

    def test_sanitize_prompt_none_input(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        assert _sanitize_prompt(None) is None

    def test_sanitize_prompt_whitespace_only_returns_none(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        assert _sanitize_prompt("   \n  \n  ") is None

    def test_sanitize_prompt_preserves_normal_text(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        result = _sanitize_prompt("Fix the login bug")
        assert result == "Fix the login bug"

    def test_command_name_tag_filtered(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="<command-name>review</command-name>")
        row = SessionRow(session)
        content = row._build_content()
        assert "<command-name>" not in content


class TestSessionRowContext:
    def test_context_shown_in_row(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            project="CtxProj",
            session_uuid="ctx-uuid-1234-5678-abcdef012345",
            cwd="/tmp/ctxproj",
        )

        with patch("monitorator.tui.session_row.get_context_estimate", return_value="45k"):
            row = SessionRow(session)
            content = row._build_content()

        assert "45k" in content

    def test_context_dash_when_no_uuid(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="NoUuid", prompt=None)
        # session_uuid defaults to None in make_merged
        row = SessionRow(session)
        content = row._build_content()
        # Should show "-" for context when no uuid
        # The content should contain the dash in the context column
        assert content.count("-") >= 1  # at least one dash for context


class TestSessionRowCompact:
    def test_compact_hides_prompt_line(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(True)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # No prompt line

    def test_non_compact_shows_prompt_line(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(False)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # Main + prompt line

    def test_compact_default_is_false(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        assert row._compact is False

    def test_set_compact_updates_flag(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(True)
        assert row._compact is True
