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


class TestFormatElapsed:
    def test_seconds(self) -> None:
        from monitorator.tui.formatting import format_elapsed

        assert format_elapsed(45) == "0m 45s"

    def test_minutes(self) -> None:
        from monitorator.tui.formatting import format_elapsed

        assert format_elapsed(872) == "14m 32s"

    def test_hours(self) -> None:
        from monitorator.tui.formatting import format_elapsed

        assert format_elapsed(3661) == "1h 01m"

    def test_zero(self) -> None:
        from monitorator.tui.formatting import format_elapsed

        assert format_elapsed(0) == "0m 00s"


class TestStatusDicts:
    def test_status_icons_has_all_statuses(self) -> None:
        from monitorator.tui.formatting import STATUS_ICONS

        for status in SessionStatus:
            assert status in STATUS_ICONS

    def test_status_colors_has_all_statuses(self) -> None:
        from monitorator.tui.formatting import STATUS_COLORS

        for status in SessionStatus:
            assert status in STATUS_COLORS

    def test_status_labels_has_all_statuses(self) -> None:
        from monitorator.tui.formatting import STATUS_LABELS

        for status in SessionStatus:
            assert status in STATUS_LABELS

    def test_status_labels_values(self) -> None:
        from monitorator.tui.formatting import STATUS_LABELS

        assert STATUS_LABELS[SessionStatus.THINKING] == "THINK"
        assert STATUS_LABELS[SessionStatus.EXECUTING] == "EXEC"
        assert STATUS_LABELS[SessionStatus.WAITING_PERMISSION] == "PERM!"
        assert STATUS_LABELS[SessionStatus.IDLE] == "WAIT"
        assert STATUS_LABELS[SessionStatus.SUBAGENT_RUNNING] == "SUBAG"
        assert STATUS_LABELS[SessionStatus.TERMINATED] == "TERM"
        assert STATUS_LABELS[SessionStatus.UNKNOWN] == "???"

    def test_thinking_icon(self) -> None:
        from monitorator.tui.formatting import STATUS_ICONS

        assert STATUS_ICONS[SessionStatus.THINKING] == "\u25cf"

    def test_executing_icon(self) -> None:
        from monitorator.tui.formatting import STATUS_ICONS

        assert STATUS_ICONS[SessionStatus.EXECUTING] == "\u25b6"

    def test_waiting_icon(self) -> None:
        from monitorator.tui.formatting import STATUS_ICONS

        assert STATUS_ICONS[SessionStatus.WAITING_PERMISSION] == "\u26a0"

    def test_idle_color_is_amber(self) -> None:
        from monitorator.tui.formatting import STATUS_COLORS

        assert STATUS_COLORS[SessionStatus.IDLE] == "#ffaa00"

    def test_idle_icon_is_return_symbol(self) -> None:
        from monitorator.tui.formatting import STATUS_ICONS

        assert STATUS_ICONS[SessionStatus.IDLE] == "\u23ce"

    def test_idle_label_is_wait(self) -> None:
        from monitorator.tui.formatting import STATUS_LABELS

        assert STATUS_LABELS[SessionStatus.IDLE] == "WAIT"


class TestFormatActivityNeverEmpty:
    """format_activity must NEVER return empty string for any status."""

    @pytest.mark.parametrize("status", list(SessionStatus))
    def test_never_empty_with_hook(self, status: SessionStatus) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=status,
            tool=None,
            tool_summary=None,
            prompt=None,
        )
        result = format_activity(session)
        assert result != "", f"format_activity returned empty for {status.value} with hook"

    @pytest.mark.parametrize("status", list(SessionStatus))
    def test_never_empty_without_hook(self, status: SessionStatus) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=status,
            tool=None,
            tool_summary=None,
            prompt=None,
            hook_state=False,
        )
        result = format_activity(session)
        assert result != "", f"format_activity returned empty for {status.value} without hook"


class TestFormatActivitySpecific:
    def test_edit_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Edit", tool_summary="file_path: src/app.py")
        assert format_activity(session) == "Editing src/app.py"

    def test_bash_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Bash", tool_summary="command: npm test")
        assert format_activity(session) == "Running: npm test"

    def test_write_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Write", tool_summary="file_path: config.ts")
        assert format_activity(session) == "Writing config.ts"

    def test_read_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Read", tool_summary="file_path: CLAUDE.md")
        assert format_activity(session) == "Reading CLAUDE.md"

    def test_grep_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Grep", tool_summary="pattern: TODO")
        assert format_activity(session) == "Searching: TODO"

    def test_glob_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Glob", tool_summary="pattern: **/*.ts")
        assert format_activity(session) == "Finding: **/*.ts"

    def test_task_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(tool="Task", tool_summary="prompt: do stuff")
        assert format_activity(session) == "Spawning subagent"

    def test_waiting_permission_with_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.WAITING_PERMISSION,
            tool="Bash",
            tool_summary="command: rm -rf dist",
        )
        assert format_activity(session) == "!! Permission: Bash rm -rf dist"

    def test_waiting_permission_no_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.WAITING_PERMISSION,
            tool=None,
            tool_summary=None,
        )
        assert format_activity(session) == "Awaiting permission"

    def test_idle_with_hook_and_prompt_shows_elapsed(self) -> None:
        """IDLE activity shows elapsed time, not prompt (prompt has its own line)."""
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            prompt="Implement the auth flow for login",
            updated_at=time.time() - 180,
        )
        assert format_activity(session) == "Idle (3m ago)"

    def test_idle_hooked_no_prompt_shows_elapsed(self) -> None:
        """IDLE activity shows elapsed time even without prompt."""
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            prompt=None,
            updated_at=time.time() - 180,
            session_uuid="abc12345-dead-beef-cafe-123456789abc",
        )
        result = format_activity(session)
        assert result == "Idle (3m ago)"

    def test_idle_with_time(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            prompt=None,
            updated_at=time.time() - 180,
        )
        assert format_activity(session) == "Idle (3m ago)"

    def test_idle_no_hook(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
        )
        assert format_activity(session) == "Process detected \u2014 no hooks"

    def test_idle_hook_no_updated_at(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = MergedSession(
            session_id="test",
            hook_state=SessionState(
                session_id="test",
                cwd="/tmp/test",
                project_name="Test",
                status=SessionStatus.IDLE,
                updated_at=None,
            ),
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert format_activity(session) == "Awaiting input"

    def test_subagent_running_with_count(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.SUBAGENT_RUNNING,
            tool=None,
            tool_summary=None,
            subagent_count=2,
        )
        assert format_activity(session) == "Subagent active (2 running)"

    def test_subagent_running_no_count(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.SUBAGENT_RUNNING,
            tool=None,
            tool_summary=None,
            subagent_count=0,
        )
        assert format_activity(session) == "Subagent active"

    def test_terminated(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.TERMINATED,
            tool=None,
            tool_summary=None,
        )
        assert format_activity(session) == "Session ended"

    def test_unknown(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.UNKNOWN,
            tool=None,
            tool_summary=None,
        )
        assert format_activity(session) == "Unknown state"

    def test_thinking_no_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
        )
        assert format_activity(session) == "Thinking..."

    def test_executing_no_tool(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.EXECUTING,
            tool=None,
            tool_summary=None,
        )
        assert format_activity(session) == "Executing..."


class TestShortenPath:
    def test_replaces_home_with_tilde(self) -> None:
        import os

        from monitorator.tui.formatting import shorten_path

        home = os.path.expanduser("~")
        result = shorten_path(f"{home}/projects/myapp")
        assert result == "~/projects/myapp"

    def test_short_path_unchanged(self) -> None:
        from monitorator.tui.formatting import shorten_path

        assert shorten_path("~/projects/myapp") == "~/projects/myapp"

    def test_long_path_collapsed(self) -> None:
        from monitorator.tui.formatting import shorten_path

        long_path = "~/very/deeply/nested/directory/structure/that/is/way/too/long/project"
        result = shorten_path(long_path)
        assert len(result) <= 50
        assert result.startswith("~/")
        assert result.endswith("project")
        assert "..." in result

    def test_empty_path(self) -> None:
        from monitorator.tui.formatting import shorten_path

        assert shorten_path("") == ""

    def test_path_exactly_at_limit(self) -> None:
        from monitorator.tui.formatting import shorten_path

        filler = "a" * 48
        path = f"~/{filler}"
        assert len(path) == 50
        assert shorten_path(path) == path

    def test_non_home_path_stays_as_is_when_short(self) -> None:
        from monitorator.tui.formatting import shorten_path

        assert shorten_path("/tmp/myproject") == "/tmp/myproject"


class TestExtractValue:
    def test_extracts_value(self) -> None:
        from monitorator.tui.formatting import extract_value

        assert extract_value("file_path: src/app.py", "file_path") == "src/app.py"

    def test_no_prefix_returns_summary(self) -> None:
        from monitorator.tui.formatting import extract_value

        assert extract_value("just a string", "file_path") == "just a string"


class TestFormatActivityProjectDescription:
    """format_activity uses project metadata for process-only sessions."""

    @pytest.fixture(autouse=True)
    def _clear_metadata_cache(self) -> None:
        from monitorator.project_metadata import _CACHE
        _CACHE.clear()

    def test_idle_no_hook_shows_project_description(self, tmp_path: object) -> None:
        from monitorator.tui.formatting import format_activity

        p = tmp_path  # type: ignore[assignment]
        (p / "CLAUDE.md").write_text("# BB Media Creative Studio\n")

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd=str(p),
        )
        assert format_activity(session) == "BB Media Creative Studio"

    def test_idle_no_hook_fallback_when_no_metadata(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd="/nonexistent/path/xyz",
        )
        assert format_activity(session) == "Process detected \u2014 no hooks"

    def test_thinking_no_hook_shows_project_description(self, tmp_path: object) -> None:
        from monitorator.tui.formatting import format_activity

        p = tmp_path  # type: ignore[assignment]
        (p / "package.json").write_text('{"description": "My Web App"}')

        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd=str(p),
        )
        assert format_activity(session) == "My Web App"

    def test_thinking_no_hook_fallback_when_no_metadata(self) -> None:
        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd="/nonexistent/path/xyz",
        )
        assert format_activity(session) == "Thinking..."


class TestFormatActivitySessionPrompt:
    """format_activity prefers session prompt over project description."""

    @pytest.fixture(autouse=True)
    def _clear_caches(self) -> None:
        from monitorator.project_metadata import _CACHE as meta_cache
        from monitorator.session_prompt import _CACHE as prompt_cache
        meta_cache.clear()
        prompt_cache.clear()
        yield
        meta_cache.clear()
        prompt_cache.clear()

    def test_idle_no_hook_prefers_session_prompt(self, tmp_path: object) -> None:
        from unittest.mock import patch

        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd="/tmp/proj",
            session_uuid="abc12345-dead-beef-cafe-123456789abc",
        )
        with patch("monitorator.session_prompt.get_session_prompt", return_value="Implement the auth flow"):
            result = format_activity(session)
        assert result == "Implement the auth flow"

    def test_idle_no_hook_falls_back_to_project_desc(self, tmp_path: object) -> None:
        from unittest.mock import patch

        from monitorator.tui.formatting import format_activity

        p = tmp_path  # type: ignore[assignment]
        (p / "CLAUDE.md").write_text("# My Project\n")

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd=str(p),
            session_uuid="abc12345-dead-beef-cafe-123456789abc",
        )
        with patch("monitorator.session_prompt.get_session_prompt", return_value=None):
            result = format_activity(session)
        assert result == "My Project"

    def test_thinking_no_hook_prefers_session_prompt(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.formatting import format_activity

        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd="/tmp/proj",
            session_uuid="abc12345-dead-beef-cafe-123456789abc",
        )
        with patch("monitorator.session_prompt.get_session_prompt", return_value="Fix the login bug"):
            result = format_activity(session)
        assert result == "Fix the login bug"

    def test_truncates_long_session_prompt(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.formatting import format_activity

        long_prompt = "A" * 100
        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd="/tmp/proj",
            session_uuid="abc12345-dead-beef-cafe-123456789abc",
        )
        with patch("monitorator.session_prompt.get_session_prompt", return_value=long_prompt):
            result = format_activity(session)
        assert len(result) == 60

    def test_no_uuid_falls_through_to_project_desc(self, tmp_path: object) -> None:
        from monitorator.tui.formatting import format_activity

        p = tmp_path  # type: ignore[assignment]
        (p / "CLAUDE.md").write_text("# Existing Desc\n")

        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            hook_state=False,
            cwd=str(p),
            session_uuid=None,
        )
        result = format_activity(session)
        assert result == "Existing Desc"
