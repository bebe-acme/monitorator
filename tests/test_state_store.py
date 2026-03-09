from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from monitorator.models import SessionState, SessionStatus
from monitorator.state_store import StateStore


class TestStateStore:
    def test_write_and_read(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        state = SessionState(
            session_id="abc-123",
            cwd="/tmp/project",
            status=SessionStatus.THINKING,
            project_name="TestProj",
        )
        store.write(state)
        result = store.read("abc-123")
        assert result is not None
        assert result.session_id == "abc-123"
        assert result.status == SessionStatus.THINKING
        assert result.project_name == "TestProj"

    def test_read_nonexistent(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        assert store.read("nonexistent") is None

    def test_list_all(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        store.write(SessionState(session_id="a", cwd="/a"))
        store.write(SessionState(session_id="b", cwd="/b"))
        store.write(SessionState(session_id="c", cwd="/c"))
        sessions = store.list_all()
        assert len(sessions) == 3
        ids = {s.session_id for s in sessions}
        assert ids == {"a", "b", "c"}

    def test_list_all_empty(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        assert store.list_all() == []

    def test_delete(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        store.write(SessionState(session_id="del-me", cwd="/tmp"))
        assert store.read("del-me") is not None
        store.delete("del-me")
        assert store.read("del-me") is None

    def test_delete_nonexistent_no_error(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        store.delete("nope")  # should not raise

    def test_cleanup_stale(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        old_state = SessionState(
            session_id="old",
            cwd="/tmp",
            updated_at=time.time() - 7200,  # 2 hours ago
        )
        new_state = SessionState(
            session_id="new",
            cwd="/tmp",
            updated_at=time.time(),
        )
        store.write(old_state)
        store.write(new_state)
        removed = store.cleanup_stale(max_age_seconds=3600)
        assert removed == ["old"]
        assert store.read("old") is None
        assert store.read("new") is not None

    def test_write_creates_dir_if_missing(self, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "nonexistent" / "sessions"
        store = StateStore(sessions_dir)
        store.write(SessionState(session_id="auto", cwd="/tmp"))
        assert store.read("auto") is not None

    def test_write_is_atomic(self, tmp_sessions_dir: Path) -> None:
        """Verify no .tmp files left behind after write."""
        store = StateStore(tmp_sessions_dir)
        store.write(SessionState(session_id="atomic", cwd="/tmp"))
        tmp_files = list(tmp_sessions_dir.glob("*.tmp"))
        assert len(tmp_files) == 0
        json_files = list(tmp_sessions_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_handles_corrupt_json(self, tmp_sessions_dir: Path) -> None:
        bad_file = tmp_sessions_dir / "corrupt.json"
        bad_file.write_text("{not valid json")
        store = StateStore(tmp_sessions_dir)
        assert store.read("corrupt") is None

    def test_list_all_skips_corrupt(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        store.write(SessionState(session_id="good", cwd="/tmp"))
        bad = tmp_sessions_dir / "bad.json"
        bad.write_text("nope")
        sessions = store.list_all()
        assert len(sessions) == 1
        assert sessions[0].session_id == "good"

    def test_cleanup_stale_exempts_active_cwds(self, tmp_sessions_dir: Path) -> None:
        store = StateStore(tmp_sessions_dir)
        active = SessionState(
            session_id="active",
            cwd="/projects/monitorator",
            updated_at=time.time() - 7200,
        )
        inactive = SessionState(
            session_id="inactive",
            cwd="/projects/old-thing",
            updated_at=time.time() - 7200,
        )
        store.write(active)
        store.write(inactive)
        removed = store.cleanup_stale(
            max_age_seconds=3600,
            active_cwds={"/projects/monitorator"},
        )
        assert removed == ["inactive"]
        assert store.read("active") is not None
        assert store.read("inactive") is None

    def test_cleanup_stale_does_not_exempt_terminated_with_active_cwd(
        self, tmp_sessions_dir: Path
    ) -> None:
        """TERMINATED sessions should be cleaned up even if cwd is active."""
        store = StateStore(tmp_sessions_dir)
        terminated = SessionState(
            session_id="old-terminated",
            cwd="/projects/monitorator",
            status=SessionStatus.TERMINATED,
            updated_at=time.time() - 7200,
        )
        store.write(terminated)
        removed = store.cleanup_stale(
            max_age_seconds=3600,
            active_cwds={"/projects/monitorator"},
        )
        assert "old-terminated" in removed
        assert store.read("old-terminated") is None

    def test_cleanup_stale_still_exempts_non_terminated_with_active_cwd(
        self, tmp_sessions_dir: Path
    ) -> None:
        """Non-terminated sessions with active cwd should still be exempted."""
        store = StateStore(tmp_sessions_dir)
        thinking = SessionState(
            session_id="active-thinking",
            cwd="/projects/monitorator",
            status=SessionStatus.THINKING,
            updated_at=time.time() - 7200,
        )
        store.write(thinking)
        removed = store.cleanup_stale(
            max_age_seconds=3600,
            active_cwds={"/projects/monitorator"},
        )
        assert removed == []
        assert store.read("active-thinking") is not None


class TestMarkDeadPidsTerminated:
    def test_marks_stuck_thinking_session(self, tmp_sessions_dir: Path) -> None:
        """Session stuck in THINKING for >5 min should be marked TERMINATED."""
        store = StateStore(tmp_sessions_dir)
        old_thinking = SessionState(
            session_id="stuck",
            cwd="/tmp/stuck",
            status=SessionStatus.THINKING,
            updated_at=time.time() - 600,  # 10 min ago
        )
        store.write(old_thinking)
        marked = store.mark_dead_pids_terminated(set())
        assert "stuck" in marked
        result = store.read("stuck")
        assert result is not None
        assert result.status == SessionStatus.TERMINATED

    def test_marks_stuck_executing_session(self, tmp_sessions_dir: Path) -> None:
        """Session stuck in EXECUTING for >5 min should be marked TERMINATED."""
        store = StateStore(tmp_sessions_dir)
        old_exec = SessionState(
            session_id="exec-stuck",
            cwd="/tmp/exec",
            status=SessionStatus.EXECUTING,
            updated_at=time.time() - 600,
        )
        store.write(old_exec)
        marked = store.mark_dead_pids_terminated(set())
        assert "exec-stuck" in marked
        result = store.read("exec-stuck")
        assert result is not None
        assert result.status == SessionStatus.TERMINATED

    def test_marks_stuck_subagent_session(self, tmp_sessions_dir: Path) -> None:
        """Session stuck in SUBAGENT_RUNNING for >5 min should be marked TERMINATED."""
        store = StateStore(tmp_sessions_dir)
        old_sub = SessionState(
            session_id="sub-stuck",
            cwd="/tmp/sub",
            status=SessionStatus.SUBAGENT_RUNNING,
            updated_at=time.time() - 600,
        )
        store.write(old_sub)
        marked = store.mark_dead_pids_terminated(set())
        assert "sub-stuck" in marked

    def test_marks_stuck_waiting_permission_session(self, tmp_sessions_dir: Path) -> None:
        """Session stuck in WAITING_PERMISSION for >5 min should be marked TERMINATED."""
        store = StateStore(tmp_sessions_dir)
        old_perm = SessionState(
            session_id="perm-stuck",
            cwd="/tmp/perm",
            status=SessionStatus.WAITING_PERMISSION,
            updated_at=time.time() - 600,
        )
        store.write(old_perm)
        marked = store.mark_dead_pids_terminated(set())
        assert "perm-stuck" in marked

    def test_ignores_recently_updated(self, tmp_sessions_dir: Path) -> None:
        """Sessions updated < 5 min ago should NOT be marked TERMINATED."""
        store = StateStore(tmp_sessions_dir)
        recent = SessionState(
            session_id="active",
            cwd="/tmp/active",
            status=SessionStatus.THINKING,
            updated_at=time.time() - 60,  # 1 min ago — still fresh
        )
        store.write(recent)
        marked = store.mark_dead_pids_terminated(set())
        assert marked == []
        result = store.read("active")
        assert result is not None
        assert result.status == SessionStatus.THINKING

    def test_ignores_idle(self, tmp_sessions_dir: Path) -> None:
        """IDLE sessions should NOT be marked TERMINATED regardless of age."""
        store = StateStore(tmp_sessions_dir)
        idle = SessionState(
            session_id="idle-one",
            cwd="/tmp/idle",
            status=SessionStatus.IDLE,
            updated_at=time.time() - 600,
        )
        store.write(idle)
        marked = store.mark_dead_pids_terminated(set())
        assert marked == []

    def test_ignores_already_terminated(self, tmp_sessions_dir: Path) -> None:
        """TERMINATED sessions should NOT be re-marked."""
        store = StateStore(tmp_sessions_dir)
        term = SessionState(
            session_id="already-done",
            cwd="/tmp/done",
            status=SessionStatus.TERMINATED,
            updated_at=time.time() - 600,
        )
        store.write(term)
        marked = store.mark_dead_pids_terminated(set())
        assert marked == []

    def test_uses_timestamp_if_no_updated_at(self, tmp_sessions_dir: Path) -> None:
        """Should fall back to timestamp if updated_at is None."""
        store = StateStore(tmp_sessions_dir)
        old = SessionState(
            session_id="old-ts",
            cwd="/tmp/old",
            status=SessionStatus.THINKING,
            timestamp=time.time() - 600,
            updated_at=None,
        )
        store.write(old)
        marked = store.mark_dead_pids_terminated(set())
        assert "old-ts" in marked
