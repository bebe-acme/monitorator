from __future__ import annotations

import time

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus
from monitorator.merger import SessionMerger


class TestSessionMerger:
    def test_hook_only_session(self) -> None:
        states = [SessionState(session_id="h1", cwd="/tmp/proj", status=SessionStatus.THINKING, updated_at=time.time())]
        processes: list[ProcessInfo] = []
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 1
        assert merged[0].session_id == "h1"
        assert merged[0].effective_status == SessionStatus.THINKING
        assert merged[0].hook_state is not None
        assert merged[0].process_info is None

    def test_process_only_session(self) -> None:
        states: list[SessionState] = []
        processes = [ProcessInfo(pid=100, cpu_percent=20.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 1
        m = merged[0]
        assert m.hook_state is None
        assert m.process_info is not None
        assert m.effective_status == SessionStatus.THINKING  # high CPU -> thinking

    def test_process_only_low_cpu_is_idle(self) -> None:
        states: list[SessionState] = []
        processes = [ProcessInfo(pid=100, cpu_percent=1.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert merged[0].effective_status == SessionStatus.IDLE

    def test_matched_by_cwd(self) -> None:
        states = [SessionState(session_id="m1", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=time.time())]
        processes = [ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 1
        m = merged[0]
        assert m.hook_state is not None
        assert m.process_info is not None

    def test_cpu_override_idle_to_thinking(self) -> None:
        """If hooks say idle but CPU >10%, override to thinking."""
        states = [SessionState(session_id="ov1", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=time.time())]
        processes = [ProcessInfo(pid=100, cpu_percent=25.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert merged[0].effective_status == SessionStatus.THINKING

    def test_no_cpu_override_for_non_idle(self) -> None:
        """CPU override only applies to idle status."""
        states = [SessionState(
            session_id="no-ov",
            cwd="/tmp/proj",
            status=SessionStatus.WAITING_PERMISSION,
            updated_at=time.time(),
        )]
        processes = [ProcessInfo(pid=100, cpu_percent=25.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert merged[0].effective_status == SessionStatus.WAITING_PERMISSION

    def test_stale_detection_no_process(self) -> None:
        """No update in 5min + no matching process = stale."""
        old_time = time.time() - 400  # >5 min ago
        states = [SessionState(session_id="stale1", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=old_time)]
        processes: list[ProcessInfo] = []
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert merged[0].is_stale

    def test_not_stale_with_process(self) -> None:
        old_time = time.time() - 400
        states = [SessionState(session_id="alive", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=old_time)]
        processes = [ProcessInfo(pid=100, cpu_percent=0.0, elapsed_seconds=600, cwd="/tmp/proj", command="claude")]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert not merged[0].is_stale

    def test_not_stale_when_recent(self) -> None:
        states = [SessionState(session_id="recent", cwd="/tmp/proj", updated_at=time.time())]
        processes: list[ProcessInfo] = []
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert not merged[0].is_stale

    def test_multiple_unmatched_processes_same_cwd_all_kept(self) -> None:
        """Multiple unmatched processes with same cwd should all produce sessions."""
        states: list[SessionState] = []
        processes = [
            ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude"),
            ProcessInfo(pid=101, cpu_percent=25.0, elapsed_seconds=120, cwd="/tmp/proj", command="claude"),
            ProcessInfo(pid=102, cpu_percent=1.0, elapsed_seconds=30, cwd="/tmp/proj", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        # Each process is a real Claude session — all should appear
        assert len(merged) == 3
        pids = {m.process_info.pid for m in merged if m.process_info}
        assert pids == {100, 101, 102}

    def test_dedup_keeps_different_cwds_separate(self) -> None:
        """Unmatched processes with different cwds should remain separate."""
        states: list[SessionState] = []
        processes = [
            ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="/tmp/proj-a", command="claude"),
            ProcessInfo(pid=101, cpu_percent=25.0, elapsed_seconds=60, cwd="/tmp/proj-b", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 2

    def test_dedup_skips_empty_cwd(self) -> None:
        """Unmatched processes with empty cwd should be skipped."""
        states: list[SessionState] = []
        processes = [
            ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 0

    def test_hysteresis_stays_thinking_when_cpu_drops_slightly(self) -> None:
        """Once THINKING due to CPU override, should stay THINKING until CPU drops below 3%."""
        merger = SessionMerger()
        states = [SessionState(session_id="hy1", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=time.time())]

        # First merge: high CPU → THINKING
        procs_high = [ProcessInfo(pid=100, cpu_percent=15.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merged = merger.merge(states, procs_high)
        assert merged[0].effective_status == SessionStatus.THINKING

        # Second merge: CPU dropped to 7% (above drop threshold of 3%) → stays THINKING
        procs_mid = [ProcessInfo(pid=100, cpu_percent=7.0, elapsed_seconds=62, cwd="/tmp/proj", command="claude")]
        merged = merger.merge(states, procs_mid)
        assert merged[0].effective_status == SessionStatus.THINKING

        # Third merge: CPU drops below 3% → back to IDLE
        procs_low = [ProcessInfo(pid=100, cpu_percent=2.0, elapsed_seconds=64, cwd="/tmp/proj", command="claude")]
        merged = merger.merge(states, procs_low)
        assert merged[0].effective_status == SessionStatus.IDLE

    def test_time_hold_prevents_idle_flicker_between_tools(self) -> None:
        """If hook says IDLE but updated_at is recent and prev was THINKING, hold THINKING."""
        merger = SessionMerger()
        states_thinking = [SessionState(
            session_id="th1", cwd="/tmp/proj",
            status=SessionStatus.THINKING,
            updated_at=time.time(),
        )]
        procs = [ProcessInfo(pid=100, cpu_percent=1.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]

        # First merge: THINKING
        merged = merger.merge(states_thinking, procs)
        assert merged[0].effective_status == SessionStatus.THINKING

        # Second merge: hook says IDLE, but updated_at is only 2s later (< 15s threshold)
        states_idle = [SessionState(
            session_id="th1", cwd="/tmp/proj",
            status=SessionStatus.IDLE,
            updated_at=time.time(),
        )]
        merged = merger.merge(states_idle, procs)
        assert merged[0].effective_status == SessionStatus.THINKING, "Should hold THINKING when recently active"

    def test_time_hold_releases_after_threshold(self) -> None:
        """After enough time passes, allow IDLE to show."""
        merger = SessionMerger()
        states_thinking = [SessionState(
            session_id="th2", cwd="/tmp/proj",
            status=SessionStatus.THINKING,
            updated_at=time.time() - 30,
        )]
        procs = [ProcessInfo(pid=100, cpu_percent=1.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]

        # First merge: THINKING (but updated 30s ago)
        merged = merger.merge(states_thinking, procs)
        assert merged[0].effective_status == SessionStatus.THINKING

        # Second merge: hook says IDLE, updated 20s ago (> 15s threshold)
        states_idle = [SessionState(
            session_id="th2", cwd="/tmp/proj",
            status=SessionStatus.IDLE,
            updated_at=time.time() - 20,
        )]
        merged = merger.merge(states_idle, procs)
        assert merged[0].effective_status == SessionStatus.IDLE, "Should release to IDLE after threshold"

    def test_hysteresis_resets_for_new_sessions(self) -> None:
        """Hysteresis should not apply to sessions it hasn't seen before."""
        merger = SessionMerger()
        states = [SessionState(session_id="new1", cwd="/tmp/proj", status=SessionStatus.IDLE, updated_at=time.time())]
        procs = [ProcessInfo(pid=100, cpu_percent=5.0, elapsed_seconds=60, cwd="/tmp/proj", command="claude")]
        merged = merger.merge(states, procs)
        assert merged[0].effective_status == SessionStatus.IDLE

    def test_hookless_process_stale_when_idle_long_time(self) -> None:
        """Hookless process with 0% CPU and >1h uptime should be stale."""
        states: list[SessionState] = []
        processes = [ProcessInfo(
            pid=100, cpu_percent=0.0, elapsed_seconds=3700,  # >1h
            cwd="/tmp/proj", command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert merged[0].is_stale

    def test_hookless_process_not_stale_when_active(self) -> None:
        """Hookless process with high CPU should NOT be stale regardless of uptime."""
        states: list[SessionState] = []
        processes = [ProcessInfo(
            pid=100, cpu_percent=15.0, elapsed_seconds=90000,  # 25h but active
            cwd="/tmp/proj", command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert not merged[0].is_stale

    def test_hookless_process_not_stale_when_young(self) -> None:
        """Hookless process with low CPU but <1h uptime should NOT be stale."""
        states: list[SessionState] = []
        processes = [ProcessInfo(
            pid=100, cpu_percent=0.0, elapsed_seconds=600,  # 10 min
            cwd="/tmp/proj", command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert not merged[0].is_stale

    def test_match_hook_subdirectory_of_process_cwd(self) -> None:
        """Hook cwd that is a subdirectory of process cwd should match."""
        states = [SessionState(
            session_id="sub1",
            cwd="/Users/testuser/projects/bbmedia/projects/podcast",
            status=SessionStatus.EXECUTING,
            updated_at=time.time(),
        )]
        processes = [ProcessInfo(
            pid=100, cpu_percent=15.0, elapsed_seconds=60,
            cwd="/Users/testuser/projects/bbmedia",
            command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 1
        assert merged[0].process_info is not None
        assert merged[0].process_info.pid == 100

    def test_match_process_subdirectory_of_hook_cwd(self) -> None:
        """Process cwd that is a subdirectory of hook cwd should also match."""
        states = [SessionState(
            session_id="sub2",
            cwd="/Users/testuser/projects/bbmedia",
            status=SessionStatus.THINKING,
            updated_at=time.time(),
        )]
        processes = [ProcessInfo(
            pid=200, cpu_percent=10.0, elapsed_seconds=60,
            cwd="/Users/testuser/projects/bbmedia/projects/podcast",
            command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        assert len(merged) == 1
        assert merged[0].process_info is not None

    def test_no_match_unrelated_paths(self) -> None:
        """Unrelated paths should not match even with common prefix."""
        states = [SessionState(
            session_id="unrel",
            cwd="/Users/testuser/projects/foo",
            status=SessionStatus.IDLE,
            updated_at=time.time(),
        )]
        processes = [ProcessInfo(
            pid=300, cpu_percent=5.0, elapsed_seconds=60,
            cwd="/Users/testuser/projects/foobar",
            command="claude",
        )]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        # Should NOT match — foobar is not a parent/child of foo
        assert len(merged) == 2

    def test_multiple_sessions(self) -> None:
        states = [
            SessionState(session_id="s1", cwd="/a", status=SessionStatus.THINKING, updated_at=time.time()),
            SessionState(session_id="s2", cwd="/b", status=SessionStatus.IDLE, updated_at=time.time()),
        ]
        processes = [
            ProcessInfo(pid=1, cpu_percent=20.0, elapsed_seconds=60, cwd="/a", command="claude"),
            ProcessInfo(pid=2, cpu_percent=0.0, elapsed_seconds=60, cwd="/c", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        # s1 matched with proc pid=1, s2 unmatched, proc pid=2 unmatched
        assert len(merged) == 3
        ids = {m.session_id for m in merged}
        assert "s1" in ids
        assert "s2" in ids


class TestSessionMergerDedup:
    """Dedup sessions sharing the same cwd (zombie cleanup)."""

    def test_same_cwd_keeps_most_recent(self) -> None:
        """When two hook states share cwd, the most recently updated wins."""
        now = time.time()
        states = [
            SessionState(session_id="old", cwd="/proj", status=SessionStatus.IDLE, updated_at=now - 60),
            SessionState(session_id="new", cwd="/proj", status=SessionStatus.THINKING, updated_at=now),
        ]
        processes = [
            ProcessInfo(pid=100, cpu_percent=20.0, elapsed_seconds=30, cwd="/proj", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        non_stale = [m for m in merged if not m.is_stale]
        assert len(non_stale) == 1
        assert non_stale[0].session_id == "new"

    def test_same_cwd_no_process_keeps_newest(self) -> None:
        """When two hook states share cwd and neither has process, keep newest."""
        now = time.time()
        states = [
            SessionState(session_id="old", cwd="/proj", status=SessionStatus.IDLE, updated_at=now - 60),
            SessionState(session_id="new", cwd="/proj", status=SessionStatus.THINKING, updated_at=now),
        ]
        processes: list[ProcessInfo] = []
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        non_stale = [m for m in merged if not m.is_stale]
        assert len(non_stale) == 1
        assert non_stale[0].session_id == "new"

    def test_different_cwds_not_deduped(self) -> None:
        """Sessions with different cwds should not be deduped."""
        now = time.time()
        states = [
            SessionState(session_id="s1", cwd="/a", status=SessionStatus.THINKING, updated_at=now),
            SessionState(session_id="s2", cwd="/b", status=SessionStatus.THINKING, updated_at=now),
        ]
        processes: list[ProcessInfo] = []
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        non_stale = [m for m in merged if not m.is_stale]
        assert len(non_stale) == 2

    def test_same_cwd_both_have_processes_keeps_newest(self) -> None:
        """If multiple sessions with same cwd both have processes, keep only the newest."""
        now = time.time()
        states = [
            SessionState(session_id="s1", cwd="/proj", status=SessionStatus.THINKING, updated_at=now),
            SessionState(session_id="s2", cwd="/proj", status=SessionStatus.IDLE, updated_at=now - 10),
        ]
        processes = [
            ProcessInfo(pid=100, cpu_percent=20.0, elapsed_seconds=30, cwd="/proj", command="claude"),
            ProcessInfo(pid=200, cpu_percent=5.0, elapsed_seconds=60, cwd="/proj", command="claude"),
        ]
        merger = SessionMerger()
        merged = merger.merge(states, processes)
        non_stale = [m for m in merged if not m.is_stale]
        # Only the most recent session survives dedup
        assert len(non_stale) == 1
        assert non_stale[0].session_id == "s1"
