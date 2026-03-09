from __future__ import annotations

import subprocess
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.binding import Binding

from monitorator.models import MergedSession, SessionStatus
from monitorator.merger import SessionMerger
from monitorator.pid_utils import is_pid_alive
from monitorator.scanner import ProcessScanner
from monitorator.state_store import StateStore
from monitorator.notifier import Notifier
from monitorator.terminal_opener import open_terminal_for_pid
from monitorator.tui.header_banner import HeaderBanner
from monitorator.tui.column_header import ColumnHeader
from monitorator.tui.help_screen import HelpScreen
from monitorator.tui.session_row import SessionRow
from monitorator.tui.detail_panel import DetailPanel

CSS_PATH = Path(__file__).parent / "styles.tcss"
SESSIONS_DIR = Path.home() / ".monitorator" / "sessions"
POLL_INTERVAL = 2.0

_STALE_ACTIVE_STATUSES = {
    SessionStatus.THINKING,
    SessionStatus.EXECUTING,
    SessionStatus.SUBAGENT_RUNNING,
    SessionStatus.WAITING_PERMISSION,
}
STALE_HOOK_THRESHOLD = 300  # 5 minutes


class MonitoratorApp(App[None]):
    TITLE = "Monitorator"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("R", "force_refresh", "Force Refresh"),
        Binding("o", "open_terminal", "Open Terminal"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_session", "Select"),
        Binding("question_mark", "help", "Help"),
        Binding("s", "cycle_sort", "Sort", show=False),
        Binding("f", "cycle_filter", "Filter", show=False),
        Binding("v", "toggle_compact", "Compact", show=False),
        Binding("c", "copy_cwd", "Copy CWD", show=False),
    ]

    _SORT_MODES = ["time", "status", "project"]
    _FILTER_MODES = ["all", "active", "idle", "permission"]

    def __init__(self, sessions_dir: Path | None = None) -> None:
        super().__init__()
        self._store = StateStore(sessions_dir or SESSIONS_DIR)
        self._scanner = ProcessScanner()
        self._merger = SessionMerger()
        self._notifier = Notifier()
        self._previous: dict[str, MergedSession] = {}
        self._cards: dict[str, SessionRow] = {}
        self._focused_session_id: str | None = None
        self._sort_mode: int = 0
        self._filter_mode: int = 0
        self._compact: bool = False

    def compose(self) -> ComposeResult:
        yield HeaderBanner()
        yield ColumnHeader()
        yield VerticalScroll(id="session-list")
        yield DetailPanel()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(POLL_INTERVAL, self._refresh)

    def _refresh(self) -> None:
        processes = self._scanner.scan()
        active_cwds = {p.cwd for p in processes if p.cwd}
        self._store.cleanup_stale(active_cwds=active_cwds)
        hook_states = self._store.list_all()
        merged = [m for m in self._merger.merge(hook_states, processes) if not m.is_stale]

        # Mark sessions with dead PIDs as terminated
        for m in merged:
            if (
                m.process_info
                and not is_pid_alive(m.process_info.pid)
                and m.effective_status != SessionStatus.TERMINATED
            ):
                m.effective_status = SessionStatus.TERMINATED

        # Override stale active status to IDLE when PID is alive
        now = time.time()
        for m in merged:
            if (
                m.effective_status in _STALE_ACTIVE_STATUSES
                and m.process_info
                and is_pid_alive(m.process_info.pid)
            ):
                hook_time = 0.0
                if m.hook_state:
                    hook_time = m.hook_state.updated_at or m.hook_state.timestamp or 0.0
                if hook_time and now - hook_time > STALE_HOOK_THRESHOLD:
                    m.effective_status = SessionStatus.IDLE

        # Filter based on current mode
        filter_mode = self._FILTER_MODES[self._filter_mode % len(self._FILTER_MODES)]
        if filter_mode == "active":
            merged = [m for m in merged if m.effective_status in {
                SessionStatus.THINKING, SessionStatus.EXECUTING, SessionStatus.SUBAGENT_RUNNING,
            }]
        elif filter_mode == "idle":
            merged = [m for m in merged if m.effective_status == SessionStatus.IDLE]
        elif filter_mode == "permission":
            merged = [m for m in merged if m.effective_status == SessionStatus.WAITING_PERMISSION]

        # Sort based on current mode
        _STATUS_PRIORITY = {
            SessionStatus.WAITING_PERMISSION: 0,
            SessionStatus.THINKING: 1,
            SessionStatus.EXECUTING: 2,
            SessionStatus.SUBAGENT_RUNNING: 3,
            SessionStatus.IDLE: 4,
            SessionStatus.UNKNOWN: 5,
            SessionStatus.TERMINATED: 6,
        }
        sort_mode = self._SORT_MODES[self._sort_mode % len(self._SORT_MODES)]
        if sort_mode == "time":
            merged.sort(key=lambda m: m.last_interaction_time, reverse=True)
        elif sort_mode == "status":
            merged.sort(key=lambda m: _STATUS_PRIORITY.get(m.effective_status, 99))
        elif sort_mode == "project":
            merged.sort(key=lambda m: m.project_name.lower())

        current = {m.session_id: m for m in merged}
        previous = self._previous
        self._notifier.check_transitions(previous, current)
        self._previous = current

        # Update header
        banner = self.query_one(HeaderBanner)
        banner.update_counts(merged)

        # Diff-based row update
        container = self.query_one("#session-list", VerticalScroll)
        current_ids = set(current.keys())
        existing_ids = set(self._cards.keys())

        # Remove gone sessions
        for sid in existing_ids - current_ids:
            card = self._cards.pop(sid)
            card.remove()

        # Update existing rows
        for sid in existing_ids & current_ids:
            self._cards[sid].update_session(current[sid])

        # Add new rows
        for sid in current_ids - existing_ids:
            row = SessionRow(current[sid])
            self._cards[sid] = row
            container.mount(row)

        # Reorder rows to match sorted order (most recently interacted first)
        sorted_sids = list(current.keys())
        for i, sid in enumerate(sorted_sids):
            if sid in self._cards:
                container.move_child(self._cards[sid], before=i)

        # Rebuild _cards in sorted order for consistent indexing
        self._cards = {sid: self._cards[sid] for sid in sorted_sids if sid in self._cards}

        # Re-index all rows
        for i, sid in enumerate(self._cards, start=1):
            self._cards[sid].update_index(i)

        # Apply compact mode to new rows
        for sid in current_ids - existing_ids:
            if sid in self._cards:
                self._cards[sid].set_compact(self._compact)

        # Update detail panel for focused session
        if self._focused_session_id and self._focused_session_id in current:
            panel = self.query_one(DetailPanel)
            panel.show_session(current[self._focused_session_id])

        # Auto-focus sessions needing permission
        for sid, session in current.items():
            if (
                session.effective_status == SessionStatus.WAITING_PERMISSION
                and (sid not in previous or previous[sid].effective_status != SessionStatus.WAITING_PERMISSION)
            ):
                # New permission request — auto-focus
                if sid in self._cards:
                    self._cards[sid].focus()
                break

    def action_refresh(self) -> None:
        self._refresh()

    def action_force_refresh(self) -> None:
        """Force refresh with aggressive cleanup of stale sessions."""
        self._store.mark_dead_pids_terminated(set())
        self._store.cleanup_stale(max_age_seconds=300)  # 5 min instead of 1 hour
        self._refresh()

    def action_open_terminal(self) -> None:
        focused = self.focused
        if isinstance(focused, SessionRow):
            session = focused.session
            if session.process_info:
                open_terminal_for_pid(session.process_info.pid)

    def action_cursor_down(self) -> None:
        self.action_focus_next()

    def action_cursor_up(self) -> None:
        self.action_focus_previous()

    def action_select_session(self) -> None:
        focused = self.focused
        if isinstance(focused, SessionRow):
            self._show_detail(focused.session_id)

    def on_session_row_selected(self, event: SessionRow.Selected) -> None:
        self._show_detail(event.session_id)

    def action_help(self) -> None:
        """Show help overlay with keybindings."""
        self.push_screen(HelpScreen())

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes: time -> status -> project."""
        self._sort_mode = (self._sort_mode + 1) % len(self._SORT_MODES)
        self._refresh()

    def action_cycle_filter(self) -> None:
        """Cycle through filter modes: all -> active -> idle -> permission."""
        self._filter_mode = (self._filter_mode + 1) % len(self._FILTER_MODES)
        self._refresh()

    def action_toggle_compact(self) -> None:
        """Toggle compact view (hide/show prompt lines)."""
        self._compact = not self._compact
        for card in self._cards.values():
            card.set_compact(self._compact)

    def action_copy_cwd(self) -> None:
        """Copy focused session's CWD to clipboard."""
        focused = self.focused
        if isinstance(focused, SessionRow):
            session = focused.session
            cwd = None
            if session.hook_state:
                cwd = session.hook_state.cwd
            elif session.process_info:
                cwd = session.process_info.cwd
            if cwd:
                try:
                    subprocess.run(["pbcopy"], input=cwd.encode(), check=True)
                    self.notify(f"Copied: {cwd}")
                except (subprocess.SubprocessError, FileNotFoundError):
                    self.notify("Failed to copy", severity="error")

    def _show_detail(self, session_id: str) -> None:
        self._focused_session_id = session_id
        session = self._previous.get(session_id)
        panel = self.query_one(DetailPanel)
        if session:
            panel.show_session(session)
        else:
            panel.clear_session()
