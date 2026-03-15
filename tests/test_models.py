from __future__ import annotations

import time
from dataclasses import asdict

import pytest

from monitorator.models import (
    MergedSession,
    ProcessInfo,
    SessionState,
    SessionStatus,
)


class TestSessionStatus:
    def test_all_statuses_exist(self) -> None:
        expected = {
            "idle",
            "thinking",
            "executing",
            "waiting_permission",
            "subagent_running",
            "terminated",
            "unknown",
        }
        assert {s.value for s in SessionStatus} == expected

    def test_status_from_string(self) -> None:
        assert SessionStatus("thinking") == SessionStatus.THINKING
        assert SessionStatus("idle") == SessionStatus.IDLE

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError):
            SessionStatus("nonexistent")


class TestSessionState:
    def test_create_minimal(self) -> None:
        state = SessionState(
            session_id="abc-123",
            cwd="/tmp/project",
        )
        assert state.session_id == "abc-123"
        assert state.cwd == "/tmp/project"
        assert state.status == SessionStatus.UNKNOWN
        assert state.project_name is None
        assert state.last_event is None

    def test_create_full(self) -> None:
        now = time.time()
        state = SessionState(
            session_id="abc-123",
            cwd="/tmp/project",
            project_name="Agentator",
            status=SessionStatus.THINKING,
            last_event="UserPromptSubmit",
            timestamp=now,
            updated_at=now,
            git_branch="main",
            last_tool="Edit",
            last_tool_input_summary="file_path: src/app.py",
            last_prompt_summary="Build the session monitor",
            subagent_count=2,
            permission_mode="default",
        )
        assert state.project_name == "Agentator"
        assert state.status == SessionStatus.THINKING
        assert state.subagent_count == 2

    def test_to_dict(self) -> None:
        state = SessionState(session_id="x", cwd="/tmp")
        d = state.to_dict()
        assert d["session_id"] == "x"
        assert d["status"] == "unknown"
        assert isinstance(d, dict)

    def test_from_dict(self) -> None:
        d = {
            "session_id": "abc",
            "cwd": "/tmp",
            "status": "thinking",
            "project_name": "Test",
            "last_event": "PreToolUse",
            "timestamp": 1000.0,
            "updated_at": 1000.1,
            "git_branch": "dev",
            "last_tool": "Bash",
            "last_tool_input_summary": "cmd: ls",
            "last_prompt_summary": "list files",
            "subagent_count": 1,
            "permission_mode": "plan",
        }
        state = SessionState.from_dict(d)
        assert state.session_id == "abc"
        assert state.status == SessionStatus.THINKING
        assert state.project_name == "Test"

    def test_from_dict_missing_optional_fields(self) -> None:
        d = {"session_id": "abc", "cwd": "/tmp"}
        state = SessionState.from_dict(d)
        assert state.status == SessionStatus.UNKNOWN
        assert state.project_name is None

    def test_from_dict_invalid_status_defaults_unknown(self) -> None:
        d = {"session_id": "abc", "cwd": "/tmp", "status": "garbage"}
        state = SessionState.from_dict(d)
        assert state.status == SessionStatus.UNKNOWN

    def test_roundtrip(self) -> None:
        original = SessionState(
            session_id="rt-1",
            cwd="/projects/test",
            project_name="RoundTrip",
            status=SessionStatus.EXECUTING,
            last_event="PostToolUse",
            git_branch="feat/x",
        )
        restored = SessionState.from_dict(original.to_dict())
        assert restored.session_id == original.session_id
        assert restored.status == original.status
        assert restored.project_name == original.project_name


class TestProcessInfo:
    def test_create(self) -> None:
        info = ProcessInfo(
            pid=12345,
            cpu_percent=21.5,
            elapsed_seconds=300,
            cwd="/tmp/project",
            command="claude",
        )
        assert info.pid == 12345
        assert info.cpu_percent == 21.5
        assert info.elapsed_seconds == 300

    def test_session_uuid_default_none(self) -> None:
        info = ProcessInfo(
            pid=1, cpu_percent=0.0, elapsed_seconds=0, cwd="/tmp", command="claude",
        )
        assert info.session_uuid is None

    def test_session_uuid_set(self) -> None:
        info = ProcessInfo(
            pid=1, cpu_percent=0.0, elapsed_seconds=0, cwd="/tmp", command="claude",
            session_uuid="abc-def-123",
        )
        assert info.session_uuid == "abc-def-123"


class TestMergedSession:
    def test_create_with_both(self) -> None:
        state = SessionState(session_id="m-1", cwd="/tmp", status=SessionStatus.IDLE)
        proc = ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="/tmp", command="claude")
        merged = MergedSession(
            session_id="m-1",
            hook_state=state,
            process_info=proc,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.session_id == "m-1"
        assert merged.hook_state is not None
        assert merged.process_info is not None
        assert merged.effective_status == SessionStatus.IDLE
        assert not merged.is_stale

    def test_create_hook_only(self) -> None:
        state = SessionState(session_id="h-1", cwd="/tmp")
        merged = MergedSession(
            session_id="h-1",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.UNKNOWN,
            is_stale=True,
        )
        assert merged.process_info is None
        assert merged.is_stale

    def test_create_process_only(self) -> None:
        proc = ProcessInfo(pid=200, cpu_percent=50.0, elapsed_seconds=120, cwd="/tmp", command="claude")
        merged = MergedSession(
            session_id="p-1",
            hook_state=None,
            process_info=proc,
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )
        assert merged.hook_state is None
        assert merged.effective_status == SessionStatus.THINKING

    def test_project_name_from_hook(self) -> None:
        state = SessionState(session_id="pn-1", cwd="/tmp/myproj", project_name="MyProj")
        merged = MergedSession(
            session_id="pn-1",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.project_name == "MyProj"

    def test_project_name_from_cwd_fallback(self) -> None:
        proc = ProcessInfo(pid=300, cpu_percent=0.0, elapsed_seconds=10, cwd="/tmp/fallback-proj", command="claude")
        merged = MergedSession(
            session_id="fb-1",
            hook_state=None,
            process_info=proc,
            effective_status=SessionStatus.UNKNOWN,
            is_stale=False,
        )
        assert merged.project_name == "fallback-proj"

    def test_project_name_unknown_when_no_data(self) -> None:
        merged = MergedSession(
            session_id="none-1",
            hook_state=None,
            process_info=None,
            effective_status=SessionStatus.UNKNOWN,
            is_stale=True,
        )
        assert merged.project_name == "unknown"


class TestSessionStateWorktreeFields:
    def test_defaults(self) -> None:
        state = SessionState(session_id="wt-1", cwd="/tmp")
        assert state.is_worktree is False
        assert state.worktree_name is None

    def test_worktree_roundtrip(self) -> None:
        state = SessionState(
            session_id="wt-2",
            cwd="/Users/nico/dev/proj/.claude/worktrees/FOO-BAR-BAZ",
            project_name="proj",
            is_worktree=True,
            worktree_name="FOO-BAR-BAZ",
        )
        d = state.to_dict()
        assert d["is_worktree"] is True
        assert d["worktree_name"] == "FOO-BAR-BAZ"

        restored = SessionState.from_dict(d)
        assert restored.is_worktree is True
        assert restored.worktree_name == "FOO-BAR-BAZ"
        assert restored.project_name == "proj"

    def test_from_dict_missing_worktree_fields(self) -> None:
        d = {"session_id": "wt-3", "cwd": "/tmp"}
        state = SessionState.from_dict(d)
        assert state.is_worktree is False
        assert state.worktree_name is None


class TestMergedSessionWorktreeProperties:
    def test_worktree_session(self) -> None:
        state = SessionState(
            session_id="mwt-1",
            cwd="/dev/proj/.claude/worktrees/ABC",
            project_name="proj",
            is_worktree=True,
            worktree_name="ABC",
        )
        merged = MergedSession(
            session_id="mwt-1",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.is_worktree is True
        assert merged.worktree_name == "ABC"
        assert merged.project_name == "proj"

    def test_non_worktree_session(self) -> None:
        state = SessionState(session_id="mwt-2", cwd="/dev/proj", project_name="proj")
        merged = MergedSession(
            session_id="mwt-2",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.is_worktree is False
        assert merged.worktree_name is None

    def test_no_hook_state(self) -> None:
        merged = MergedSession(
            session_id="mwt-3",
            hook_state=None,
            process_info=None,
            effective_status=SessionStatus.UNKNOWN,
            is_stale=True,
        )
        assert merged.is_worktree is False
        assert merged.worktree_name is None


class TestMergedSessionLastInteractionTime:
    def test_uses_hook_updated_at(self) -> None:
        state = SessionState(session_id="t1", cwd="/tmp", updated_at=5000.0)
        merged = MergedSession(
            session_id="t1",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.last_interaction_time == 5000.0

    def test_falls_back_to_hook_timestamp(self) -> None:
        state = SessionState(session_id="t2", cwd="/tmp", timestamp=3000.0)
        merged = MergedSession(
            session_id="t2",
            hook_state=state,
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        assert merged.last_interaction_time == 3000.0

    def test_hookless_uses_process_elapsed(self) -> None:
        proc = ProcessInfo(pid=1, cpu_percent=0.0, elapsed_seconds=600, cwd="/tmp", command="claude")
        merged = MergedSession(
            session_id="t3",
            hook_state=None,
            process_info=proc,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        # Should be approximately now - 600
        now = time.time()
        assert abs(merged.last_interaction_time - (now - 600)) < 2.0

    def test_no_data_returns_zero(self) -> None:
        merged = MergedSession(
            session_id="t4",
            hook_state=None,
            process_info=None,
            effective_status=SessionStatus.UNKNOWN,
            is_stale=True,
        )
        assert merged.last_interaction_time == 0.0

    def test_sort_by_last_interaction_time(self) -> None:
        """Sessions sorted by last_interaction_time descending = most recent first."""
        old = MergedSession(
            session_id="old",
            hook_state=SessionState(session_id="old", cwd="/tmp", updated_at=1000.0),
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        new = MergedSession(
            session_id="new",
            hook_state=SessionState(session_id="new", cwd="/tmp", updated_at=5000.0),
            process_info=None,
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )
        mid = MergedSession(
            session_id="mid",
            hook_state=SessionState(session_id="mid", cwd="/tmp", updated_at=3000.0),
            process_info=None,
            effective_status=SessionStatus.IDLE,
            is_stale=False,
        )
        sessions = [old, mid, new]
        sessions.sort(key=lambda m: m.last_interaction_time, reverse=True)
        assert [s.session_id for s in sessions] == ["new", "mid", "old"]
