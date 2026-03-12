from __future__ import annotations

import time

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus
from monitorator.tui.formatting import (
    format_elapsed,
    format_activity,
    STATUS_ICONS,
    STATUS_COLORS,
    shorten_path,
)
from monitorator.tui.session_row import SessionRow


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
) -> MergedSession:
    return MergedSession(
        session_id=session_id,
        hook_state=SessionState(
            session_id=session_id,
            cwd=f"/tmp/{project.lower()}",
            project_name=project,
            status=status,
            git_branch=branch,
            last_tool=tool,
            last_tool_input_summary=tool_summary,
            last_prompt_summary=prompt,
            updated_at=updated_at or time.time(),
            subagent_count=subagent_count,
        ),
        process_info=ProcessInfo(
            pid=12345,
            cpu_percent=cpu,
            elapsed_seconds=elapsed,
            cwd=f"/tmp/{project.lower()}",
            command="claude",
        ),
        effective_status=status,
        is_stale=stale,
    )


class TestFormatElapsed:
    def test_seconds(self) -> None:
        assert format_elapsed(45) == "0m 45s"

    def test_minutes(self) -> None:
        assert format_elapsed(872) == "14m 32s"

    def test_hours(self) -> None:
        assert format_elapsed(3661) == "1h 01m"

    def test_zero(self) -> None:
        assert format_elapsed(0) == "0m 00s"


class TestFormatActivity:
    def test_edit_tool(self) -> None:
        session = make_merged(tool="Edit", tool_summary="file_path: src/app.py")
        result = format_activity(session)
        assert result == "Editing src/app.py"

    def test_bash_tool(self) -> None:
        session = make_merged(tool="Bash", tool_summary="command: npm test")
        result = format_activity(session)
        assert result == "Running: npm test"

    def test_write_tool(self) -> None:
        session = make_merged(tool="Write", tool_summary="file_path: config.ts")
        result = format_activity(session)
        assert result == "Writing config.ts"

    def test_read_tool(self) -> None:
        session = make_merged(tool="Read", tool_summary="file_path: CLAUDE.md")
        result = format_activity(session)
        assert result == "Reading CLAUDE.md"

    def test_grep_tool(self) -> None:
        session = make_merged(tool="Grep", tool_summary="pattern: TODO")
        result = format_activity(session)
        assert result == "Searching: TODO"

    def test_glob_tool(self) -> None:
        session = make_merged(tool="Glob", tool_summary="pattern: **/*.ts")
        result = format_activity(session)
        assert result == "Finding: **/*.ts"

    def test_task_tool(self) -> None:
        session = make_merged(tool="Task", tool_summary="prompt: do stuff")
        result = format_activity(session)
        assert result == "Spawning subagent"

    def test_waiting_permission(self) -> None:
        session = make_merged(
            status=SessionStatus.WAITING_PERMISSION,
            tool="Bash",
            tool_summary="command: rm -rf dist",
        )
        result = format_activity(session)
        assert result == "!! Permission: Bash rm -rf dist"

    def test_idle(self) -> None:
        session = make_merged(
            status=SessionStatus.IDLE,
            tool=None,
            tool_summary=None,
            prompt=None,
            updated_at=time.time() - 180,
        )
        result = format_activity(session)
        assert result == "Idle (3m ago)"

    def test_thinking_no_tool(self) -> None:
        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
        )
        result = format_activity(session)
        assert result == "Thinking..."

    def test_unknown_tool_fallback(self) -> None:
        session = make_merged(tool="WebSearch", tool_summary="query: test")
        result = format_activity(session)
        assert result == "WebSearch"


class TestStatusIcons:
    def test_thinking_icon(self) -> None:
        assert STATUS_ICONS[SessionStatus.THINKING] == "\u25cf"

    def test_executing_icon(self) -> None:
        assert STATUS_ICONS[SessionStatus.EXECUTING] == "\u25b6"

    def test_waiting_icon(self) -> None:
        assert STATUS_ICONS[SessionStatus.WAITING_PERMISSION] == "\u26a0"

    def test_idle_icon(self) -> None:
        assert STATUS_ICONS[SessionStatus.IDLE] == "\u23ce"

    def test_subagent_icon(self) -> None:
        assert STATUS_ICONS[SessionStatus.SUBAGENT_RUNNING] == "\u25c6"


class TestShortenPath:
    def test_replaces_home_with_tilde(self) -> None:
        import os
        home = os.path.expanduser("~")
        result = shorten_path(f"{home}/projects/myapp")
        assert result == "~/projects/myapp"

    def test_short_path_unchanged(self) -> None:
        result = shorten_path("~/projects/myapp")
        assert result == "~/projects/myapp"

    def test_long_path_collapsed(self) -> None:
        long_path = "~/very/deeply/nested/directory/structure/that/is/way/too/long/project"
        result = shorten_path(long_path)
        assert len(result) <= 50
        assert result.startswith("~/")
        assert result.endswith("project")
        assert "..." in result

    def test_empty_path(self) -> None:
        result = shorten_path("")
        assert result == ""

    def test_path_exactly_at_limit(self) -> None:
        filler = "a" * 48
        path = f"~/{filler}"
        assert len(path) == 50
        result = shorten_path(path)
        assert result == path

    def test_non_home_path_stays_as_is_when_short(self) -> None:
        result = shorten_path("/tmp/myproject")
        assert result == "/tmp/myproject"


class TestSessionRowRendering:
    def test_process_only_shows_project_and_status(self) -> None:
        """Process-only session should show project name and status badge."""
        session = MergedSession(
            session_id="proc-999",
            hook_state=None,
            process_info=ProcessInfo(
                pid=999, cpu_percent=2.0, elapsed_seconds=60,
                cwd="/tmp/myproject", command="claude",
            ),
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "MYPROJECT" in content
        assert "WAIT" in content


class TestSessionRowWidget:
    @pytest.mark.asyncio
    async def test_row_is_focusable(self) -> None:
        row = SessionRow(make_merged())
        assert row.can_focus is True

    @pytest.mark.asyncio
    async def test_row_stores_session_id(self) -> None:
        session = make_merged(session_id="abc-123")
        row = SessionRow(session)
        assert row.session_id == "abc-123"

    @pytest.mark.asyncio
    async def test_update_session(self) -> None:
        session1 = make_merged(session_id="abc", project="Old")
        row = SessionRow(session1)
        session2 = make_merged(session_id="abc", project="New")
        row.update_session(session2)
        assert row.session.project_name == "New"
