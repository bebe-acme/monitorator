from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus
from monitorator.tui.app import MonitoratorApp, _STALE_ACTIVE_STATUSES, STALE_HOOK_THRESHOLD, ANIM_INTERVAL
from monitorator.tui.header_banner import HeaderBanner
from monitorator.tui.column_header import ColumnHeader
from monitorator.tui.session_row import SessionRow
from monitorator.tui.detail_panel import DetailPanel, _box_row


def make_merged(
    session_id: str = "test-1",
    project: str = "TestProj",
    status: SessionStatus = SessionStatus.THINKING,
    branch: str = "main",
    tool: str | None = "Edit",
    cpu: float = 20.0,
    stale: bool = False,
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
            last_tool_input_summary="file_path: src/app.py",
            last_prompt_summary="Build the monitor",
            updated_at=time.time(),
        ),
        process_info=ProcessInfo(
            pid=12345,
            cpu_percent=cpu,
            memory_mb=0.0,
            elapsed_seconds=300,
            cwd=f"/tmp/{project.lower()}",
            command="claude",
        ),
        effective_status=status,
        is_stale=stale,
    )


class TestMonitoratorApp:
    @pytest.mark.asyncio
    async def test_app_composes(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            assert pilot.app.query_one(HeaderBanner) is not None
            assert pilot.app.query_one(ColumnHeader) is not None
            assert pilot.app.query_one(DetailPanel) is not None

    @pytest.mark.asyncio
    async def test_app_has_keybindings(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            bindings = {b.key for b in pilot.app.BINDINGS}
            assert "q" in bindings
            assert "r" in bindings
            assert "o" in bindings
            assert "j" in bindings
            assert "k" in bindings


class TestHeaderBannerWidget:
    @pytest.mark.asyncio
    async def test_banner_renders(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            banner = pilot.app.query_one(HeaderBanner)
            assert banner is not None

    @pytest.mark.asyncio
    async def test_banner_update_counts(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            banner = pilot.app.query_one(HeaderBanner)
            sessions = [
                make_merged("s1", status=SessionStatus.THINKING),
                make_merged("s2", status=SessionStatus.IDLE),
                make_merged("s3", status=SessionStatus.WAITING_PERMISSION),
            ]
            banner.update_counts(sessions)


class TestColumnHeaderWidget:
    @pytest.mark.asyncio
    async def test_column_header_renders(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            ch = pilot.app.query_one(ColumnHeader)
            assert ch is not None


class TestMonitoratorAppForceRefresh:
    def test_force_refresh_binding_exists(self) -> None:
        app = MonitoratorApp()
        binding_keys = [b.key for b in app.BINDINGS]
        assert "R" in binding_keys


class TestDetailPanelToolLabel:
    def _get_content(self, session: MergedSession) -> str:
        """Build the detail panel content string."""
        panel = DetailPanel()
        captured: list[str] = []
        original_update = panel.update
        def capture_update(content: str, **kwargs: object) -> None:
            captured.append(content)
        panel.update = capture_update  # type: ignore[assignment]
        panel.show_session(session)
        return captured[0] if captured else ""

    def test_tool_row_shows_actual_tool_name(self) -> None:
        session = make_merged("d1", "Agentator", SessionStatus.EXECUTING, tool="Bash")
        content = self._get_content(session)
        for line in content.split("\n"):
            if "tool" in line and "tool " in line:
                assert "Bash" in line, f"Tool row should contain 'Bash': {line}"
                return
        pytest.fail("No tool row found in detail panel output")

    def test_tool_row_hidden_when_no_tool(self) -> None:
        session = make_merged("d2", "Agentator", SessionStatus.IDLE, tool=None)
        content = self._get_content(session)
        for line in content.split("\n"):
            if "tool " in line and "tool" in line.lower():
                pytest.fail(f"Tool row should be hidden when no tool: {line}")

    def test_tool_row_does_not_show_idle(self) -> None:
        session = make_merged("d3", "Agentator", SessionStatus.IDLE, tool=None)
        content = self._get_content(session)
        for line in content.split("\n"):
            assert "Idle" not in line or "IDLE" in line, f"Should not show 'Idle' in tool context: {line}"


class TestDetailPanelWidget:
    @pytest.mark.asyncio
    async def test_detail_shows_session(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            panel = pilot.app.query_one(DetailPanel)
            session = make_merged("d1", "Agentator", SessionStatus.THINKING)
            panel.show_session(session)

    @pytest.mark.asyncio
    async def test_detail_clear(self) -> None:
        async with MonitoratorApp().run_test(size=(120, 30)) as pilot:
            panel = pilot.app.query_one(DetailPanel)
            panel.clear_session()


class TestRefreshStaleOverride:
    """Tests for the stale active session override logic in _refresh()."""

    def test_refresh_does_not_call_mark_dead_pids(self) -> None:
        """_refresh() should NOT call mark_dead_pids_terminated (only force_refresh does)."""
        app = MonitoratorApp()
        app._store = MagicMock()
        app._store.list_all.return_value = []
        app._scanner = MagicMock()
        app._scanner.scan.return_value = []
        app._merger = MagicMock()
        app._merger.merge.return_value = []
        app._notifier = MagicMock()
        # Stub out TUI queries so _refresh doesn't fail on widget lookups
        app.query_one = MagicMock()
        app.query = MagicMock(return_value=[])

        app._refresh()

        app._store.mark_dead_pids_terminated.assert_not_called()

    @patch("monitorator.tui.app.is_pid_alive", return_value=True)
    def test_stale_active_session_with_alive_pid_becomes_idle(
        self, mock_pid_alive: MagicMock
    ) -> None:
        """A THINKING session with alive PID and stale hooks (>5 min) should become IDLE."""
        stale_time = time.time() - STALE_HOOK_THRESHOLD - 60  # 6 min ago
        session = MergedSession(
            session_id="stale-1",
            hook_state=SessionState(
                session_id="stale-1",
                cwd="/tmp/proj",
                status=SessionStatus.THINKING,
                updated_at=stale_time,
            ),
            process_info=ProcessInfo(
                pid=99999,
                cpu_percent=5.0,
                memory_mb=0.0,
                elapsed_seconds=600,
                cwd="/tmp/proj",
                command="claude",
            ),
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )

        app = MonitoratorApp()
        app._store = MagicMock()
        app._store.list_all.return_value = []
        app._scanner = MagicMock()
        app._scanner.scan.return_value = []
        app._merger = MagicMock()
        app._merger.merge.return_value = [session]
        app._notifier = MagicMock()
        app.query_one = MagicMock()
        app.query = MagicMock(return_value=[])

        app._refresh()

        assert session.effective_status == SessionStatus.IDLE

    @patch("monitorator.tui.app.is_pid_alive", return_value=True)
    def test_recent_active_session_stays_active(
        self, mock_pid_alive: MagicMock
    ) -> None:
        """A THINKING session with alive PID and recent hooks (<5 min) should stay THINKING."""
        recent_time = time.time() - 60  # 1 min ago
        session = MergedSession(
            session_id="recent-1",
            hook_state=SessionState(
                session_id="recent-1",
                cwd="/tmp/proj",
                status=SessionStatus.THINKING,
                updated_at=recent_time,
            ),
            process_info=ProcessInfo(
                pid=99998,
                cpu_percent=50.0,
                memory_mb=0.0,
                elapsed_seconds=120,
                cwd="/tmp/proj",
                command="claude",
            ),
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )

        app = MonitoratorApp()
        app._store = MagicMock()
        app._store.list_all.return_value = []
        app._scanner = MagicMock()
        app._scanner.scan.return_value = []
        app._merger = MagicMock()
        app._merger.merge.return_value = [session]
        app._notifier = MagicMock()
        app.query_one = MagicMock()
        app.query = MagicMock(return_value=[])

        app._refresh()

        assert session.effective_status == SessionStatus.THINKING

    @patch("monitorator.tui.app.is_pid_alive", return_value=True)
    def test_stale_permission_session_with_alive_pid_becomes_idle(
        self, mock_pid_alive: MagicMock
    ) -> None:
        """A WAITING_PERMISSION session with alive PID and stale hooks (>5 min) should become IDLE."""
        stale_time = time.time() - STALE_HOOK_THRESHOLD - 60  # 6 min ago
        session = MergedSession(
            session_id="perm-stale-1",
            hook_state=SessionState(
                session_id="perm-stale-1",
                cwd="/tmp/proj",
                status=SessionStatus.WAITING_PERMISSION,
                updated_at=stale_time,
            ),
            process_info=ProcessInfo(
                pid=99997,
                cpu_percent=5.0,
                memory_mb=0.0,
                elapsed_seconds=600,
                cwd="/tmp/proj",
                command="claude",
            ),
            effective_status=SessionStatus.WAITING_PERMISSION,
            is_stale=False,
        )

        app = MonitoratorApp()
        app._store = MagicMock()
        app._store.list_all.return_value = []
        app._scanner = MagicMock()
        app._scanner.scan.return_value = []
        app._merger = MagicMock()
        app._merger.merge.return_value = [session]
        app._notifier = MagicMock()
        app.query_one = MagicMock()
        app.query = MagicMock(return_value=[])
        # Pre-populate _previous so auto-focus doesn't trigger for "new" permission
        app._previous = {"perm-stale-1": session}

        app._refresh()

        assert session.effective_status == SessionStatus.IDLE


class TestHelpOverlay:
    def test_help_binding_exists(self) -> None:
        app = MonitoratorApp()
        keys = [b.key for b in app.BINDINGS]
        assert "question_mark" in keys


class TestSortToggle:
    def test_sort_binding_exists(self) -> None:
        app = MonitoratorApp()
        keys = [b.key for b in app.BINDINGS]
        assert "s" in keys

    def test_sort_modes_defined(self) -> None:
        app = MonitoratorApp()
        assert hasattr(app, '_SORT_MODES')
        assert len(app._SORT_MODES) >= 3

    def test_cycle_sort_increments(self) -> None:
        app = MonitoratorApp()
        assert app._sort_mode == 0
        with patch.object(app, "_refresh"):
            app.action_cycle_sort()
        assert app._sort_mode == 1

    def test_cycle_sort_wraps_around(self) -> None:
        app = MonitoratorApp()
        with patch.object(app, "_refresh"):
            for _ in range(len(app._SORT_MODES)):
                app.action_cycle_sort()
        assert app._sort_mode == 0


class TestFilterToggle:
    def test_filter_binding_exists(self) -> None:
        app = MonitoratorApp()
        keys = [b.key for b in app.BINDINGS]
        assert "f" in keys

    def test_filter_modes_defined(self) -> None:
        app = MonitoratorApp()
        assert hasattr(app, '_FILTER_MODES')
        assert len(app._FILTER_MODES) >= 3

    def test_cycle_filter_increments(self) -> None:
        app = MonitoratorApp()
        assert app._filter_mode == 0
        with patch.object(app, "_refresh"):
            app.action_cycle_filter()
        assert app._filter_mode == 1

    def test_cycle_filter_wraps_around(self) -> None:
        app = MonitoratorApp()
        with patch.object(app, "_refresh"):
            for _ in range(len(app._FILTER_MODES)):
                app.action_cycle_filter()
        assert app._filter_mode == 0


class TestCompactToggle:
    def test_compact_binding_exists(self) -> None:
        app = MonitoratorApp()
        keys = [b.key for b in app.BINDINGS]
        assert "v" in keys

    def test_compact_default_false(self) -> None:
        app = MonitoratorApp()
        assert app._compact is False

    def test_toggle_compact_flips_value(self) -> None:
        app = MonitoratorApp()
        assert app._compact is False
        app.action_toggle_compact()
        assert app._compact is True
        app.action_toggle_compact()
        assert app._compact is False


class TestAnimationTimer:
    def test_anim_interval_is_fast(self) -> None:
        """Animation interval should be much faster than data poll interval."""
        assert ANIM_INTERVAL < 1.0
        assert ANIM_INTERVAL > 0.1

    def test_tick_sprites_method_exists(self) -> None:
        app = MonitoratorApp()
        assert hasattr(app, "_tick_sprites")
        assert callable(app._tick_sprites)

    def test_tick_sprites_increments_frames_on_cards(self) -> None:
        """_tick_sprites() should call refresh_content() on each card."""
        app = MonitoratorApp()
        mock_card = MagicMock()
        app._cards = {"s1": mock_card, "s2": MagicMock()}
        app._tick_sprites()
        mock_card.refresh_content.assert_called_once()
        app._cards["s2"].refresh_content.assert_called_once()

    def test_tick_sprites_no_cards_no_error(self) -> None:
        app = MonitoratorApp()
        app._cards = {}
        app._tick_sprites()  # should not raise


class TestCopyCwd:
    def test_copy_binding_exists(self) -> None:
        app = MonitoratorApp()
        keys = [b.key for b in app.BINDINGS]
        assert "c" in keys
