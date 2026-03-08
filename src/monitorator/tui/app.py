from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.binding import Binding

from monitorator.models import MergedSession
from monitorator.merger import SessionMerger
from monitorator.scanner import ProcessScanner
from monitorator.state_store import StateStore
from monitorator.notifier import Notifier
from monitorator.terminal_opener import open_terminal_for_pid
from monitorator.tui.header_banner import HeaderBanner
from monitorator.tui.column_header import ColumnHeader
from monitorator.tui.session_row import SessionRow
from monitorator.tui.detail_panel import DetailPanel

CSS_PATH = Path(__file__).parent / "styles.tcss"
SESSIONS_DIR = Path.home() / ".monitorator" / "sessions"
POLL_INTERVAL = 2.0


class MonitoratorApp(App[None]):
    TITLE = "Monitorator"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("o", "open_terminal", "Open Terminal"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_session", "Select"),
    ]

    def __init__(self, sessions_dir: Path | None = None) -> None:
        super().__init__()
        self._store = StateStore(sessions_dir or SESSIONS_DIR)
        self._scanner = ProcessScanner()
        self._merger = SessionMerger()
        self._notifier = Notifier()
        self._previous: dict[str, MergedSession] = {}
        self._cards: dict[str, SessionRow] = {}
        self._focused_session_id: str | None = None

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
        merged.sort(key=lambda m: m.last_interaction_time, reverse=True)

        current = {m.session_id: m for m in merged}
        self._notifier.check_transitions(self._previous, current)
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

        # Update detail panel for focused session
        if self._focused_session_id and self._focused_session_id in current:
            panel = self.query_one(DetailPanel)
            panel.show_session(current[self._focused_session_id])

    def action_refresh(self) -> None:
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

    def _show_detail(self, session_id: str) -> None:
        self._focused_session_id = session_id
        session = self._previous.get(session_id)
        panel = self.query_one(DetailPanel)
        if session:
            panel.show_session(session)
        else:
            panel.clear_session()
