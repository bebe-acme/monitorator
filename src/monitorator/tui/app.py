from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.binding import Binding
from textual.widgets import Footer

from monitorator.models import MergedSession, SessionStatus
from monitorator.merger import SessionMerger
from monitorator.pid_utils import is_pid_alive
from monitorator.scanner import ProcessScanner
from monitorator.state_store import StateStore
from monitorator.context_size import _format_tokens
from monitorator.installer import HookInstaller
from monitorator.notifier import Notifier
from monitorator.tab_renamer import rename_tabs
from monitorator.terminal_opener import open_terminal_for_pid
from monitorator.tui.header_banner import HeaderBanner, RefreshRequested
from monitorator.tui.column_header import ColumnHeader
from monitorator.tui.help_screen import HelpScreen
from monitorator.tui.session_row import SessionRow
from monitorator.tui.sprites import assign_sprites
from monitorator.tui.chat_dropdown import ChatDropdown
from monitorator.tui.detail_panel import DetailPanel
from monitorator.tui.label_screen import LabelScreen

CSS_PATH = Path(__file__).parent / "styles.tcss"
SESSIONS_DIR = Path.home() / ".monitorator" / "sessions"
POLL_INTERVAL = 2.0
ANIM_INTERVAL = 0.3  # sprite animation refresh (visual-only, no I/O)

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
        Binding("up", "cursor_up", "Up", show=False, priority=True),
        Binding("down", "cursor_down", "Down", show=False, priority=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_session", "Select"),
        Binding("question_mark", "help", "Help"),
        Binding("s", "cycle_sort", "Sort", show=False),
        Binding("f", "cycle_filter", "Filter", show=False),
        Binding("v", "toggle_compact", "Compact", show=False),
        Binding("c", "copy_cwd", "Copy CWD", show=False),
        Binding("l", "set_label", "Label", show=False),
        Binding("x", "kill_session", "Kill Session", show=False),
        Binding("X", "kill_stale", "Kill Stale", show=False),
        Binding("escape", "close_dropdown", "Close", show=False),
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
        self._dropdowns: dict[str, ChatDropdown] = {}
        self._dropdown_scroll_cache: dict[str, float] = {}
        self._stable_order: list[str] = []  # session IDs in display order (newest first)
        self._sort_mode: int = 0
        self._filter_mode: int = 0
        self._compact: bool = False
        # Token tracking: accumulates forever (survives session kills/removals)
        # Maps (cwd, uuid) -> cumulative output_tokens for that session
        self._token_snapshots: dict[tuple[str, str], int] = {}

    def compose(self) -> ComposeResult:
        yield HeaderBanner()
        yield ColumnHeader()
        yield VerticalScroll(id="session-list")
        yield DetailPanel()
        yield Footer()

    def on_mount(self) -> None:
        # Auto-update hooks if binary has changed (e.g. after git pull)
        installer = HookInstaller()
        if installer.ensure_up_to_date():
            self.notify("Hooks updated to latest version")
        elif not installer.is_installed():
            installer.install()
            self.notify("Hooks installed")

        self._refresh()
        self.set_interval(POLL_INTERVAL, self._refresh)
        self.set_interval(ANIM_INTERVAL, self._tick_sprites)

    def _refresh(self) -> None:
        processes = self._scanner.scan()
        active_cwds = {p.cwd for p in processes if p.cwd}
        self._store.cleanup_stale(active_cwds=active_cwds)
        hook_states = self._store.list_all()
        merged = self._merger.merge(hook_states, processes)

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

        # Rename terminal tabs (uses exact CWD matching, not merger's loose match)
        rename_tabs(processes, merged)

        # Check transitions on ALL sessions (including terminated) for notifications
        all_current = {m.session_id: m for m in merged}
        previous = self._previous
        self._notifier.check_transitions(previous, all_current)
        self._previous = all_current

        # Hide terminated sessions from display
        merged = [m for m in merged if m.effective_status != SessionStatus.TERMINATED]

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

        current = {m.session_id: m for m in merged}

        # Stable ordering: keep existing positions, append new sessions at top
        # sorted by newest-first.  Remove gone sessions.
        current_ids = set(current.keys())
        new_ids = current_ids - set(self._stable_order)
        if new_ids:
            new_sorted = sorted(
                new_ids,
                key=lambda sid: current[sid].last_interaction_time,
                reverse=True,
            )
            self._stable_order = new_sorted + self._stable_order
        self._stable_order = [sid for sid in self._stable_order if sid in current_ids]

        # Track token usage across all sessions (including terminated/filtered)
        tokens_since_start = self._update_token_tracking(list(all_current.values()))

        # Update header + column header for responsive layout
        banner = self.query_one(HeaderBanner)
        sort_mode = self._SORT_MODES[self._sort_mode % len(self._SORT_MODES)]
        banner.update_counts(
            merged, sort_mode=sort_mode, filter_mode=filter_mode,
            tokens_used=tokens_since_start,
        )
        col_header = self.query_one(ColumnHeader)
        col_header.rebuild()

        # Diff-based row update
        container = self.query_one("#session-list", VerticalScroll)
        current_ids = set(current.keys())
        existing_ids = set(self._cards.keys())

        # Remove gone sessions
        for sid in existing_ids - current_ids:
            card = self._cards.pop(sid)
            card.remove()
            if sid in self._dropdowns:
                self._dropdowns.pop(sid).remove()
                self._dropdown_scroll_cache.pop(sid, None)

        # Update existing rows
        for sid in existing_ids & current_ids:
            self._cards[sid].update_session(current[sid])

        # Add new rows
        for sid in current_ids - existing_ids:
            row = SessionRow(current[sid])
            self._cards[sid] = row
            container.mount(row)

        # Reorder rows to match stable order (newest first, positions don't shift)
        for i, sid in enumerate(self._stable_order):
            if sid in self._cards:
                container.move_child(self._cards[sid], before=i)

        # Rebuild _cards in stable order for consistent indexing
        self._cards = {sid: self._cards[sid] for sid in self._stable_order if sid in self._cards}

        # Reposition all open dropdowns after their associated rows
        for sid, dropdown in list(self._dropdowns.items()):
            if sid in self._cards:
                row = self._cards[sid]
                children = list(container.children)
                row_pos = children.index(row)
                container.move_child(dropdown, before=row_pos + 1)
            else:
                dropdown.remove()
                self._dropdowns.pop(sid)
                self._dropdown_scroll_cache.pop(sid, None)

        # Re-index all rows
        for i, sid in enumerate(self._cards, start=1):
            self._cards[sid].update_index(i)

        # Anti-collision: assign unique sprites to all visible sessions
        sprite_map = assign_sprites(list(self._cards.keys()))
        for sid, sprite_idx in sprite_map.items():
            if sid in self._cards:
                self._cards[sid].set_sprite_idx(sprite_idx)

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

    def _update_token_tracking(self, sessions: list[MergedSession]) -> int:
        """Update token tracking for all sessions. Returns total context tokens.

        Sums context size (input tokens) across all sessions — same metric as the row.
        Accumulates forever — killed/removed sessions keep their last snapshot.
        """
        from monitorator.context_size import _extract_usage_from_tail, _resolve_jsonl

        for s in sessions:
            cwd = None
            uuid = None
            if s.process_info and s.process_info.session_uuid and s.process_info.cwd:
                cwd = s.process_info.cwd
                uuid = s.process_info.session_uuid
            elif s.hook_state and s.hook_state.session_id and s.hook_state.cwd:
                cwd = s.hook_state.cwd
                uuid = s.hook_state.session_id
            if not cwd or not uuid:
                continue

            jsonl_path = _resolve_jsonl(cwd, uuid)
            if jsonl_path is None:
                continue
            ctx = _extract_usage_from_tail(jsonl_path)
            if ctx and ctx > 0:
                self._token_snapshots[(cwd, uuid)] = ctx

        return sum(self._token_snapshots.values())

    def _tick_sprites(self) -> None:
        """Fast visual-only refresh: update sprite animation frames + status bar blink."""
        try:
            self.query_one(HeaderBanner).tick_eyes()
        except Exception:
            pass  # widget not yet mounted (e.g. in unit tests)
        for card in self._cards.values():
            card.refresh_content()
            # Toggle bar-off class for active + permission rows (blink)
            if card.has_class("status-active") or card.has_class("status-permission"):
                card.toggle_class("bar-off")

    def on_refresh_requested(self, message: RefreshRequested) -> None:
        """Handle click-to-refresh from HeaderBanner."""
        self._refresh()

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
        self._focus_adjacent_row(direction=1)

    def action_cursor_up(self) -> None:
        self._focus_adjacent_row(direction=-1)

    def _focus_adjacent_row(self, direction: int) -> None:
        """Focus next/previous SessionRow, skipping ChatDropdown widgets."""
        order = list(self._cards.keys())
        if not order:
            return

        focused = self.focused
        current_sid = None
        if isinstance(focused, SessionRow):
            current_sid = focused.session_id

        if current_sid is None or current_sid not in order:
            # Nothing focused or unknown — focus first/last row
            target = order[0] if direction == 1 else order[-1]
        else:
            idx = order.index(current_sid)
            new_idx = idx + direction
            if new_idx < 0 or new_idx >= len(order):
                return  # at boundary
            target = order[new_idx]

        if target in self._cards:
            self._cards[target].focus()

    def action_select_session(self) -> None:
        focused = self.focused
        if isinstance(focused, SessionRow):
            self._show_detail(focused.session_id, focus_dropdown=True)

    def on_session_row_selected(self, event: SessionRow.Selected) -> None:
        self._show_detail(event.session_id)

    def action_close_dropdown(self) -> None:
        """Close the dropdown for the currently focused session row."""
        focused = self.focused
        if isinstance(focused, SessionRow):
            sid = focused.session_id
            if sid in self._dropdowns:
                dropdown = self._dropdowns.pop(sid)
                self._dropdown_scroll_cache[sid] = dropdown.scroll_y
                dropdown.remove()

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

    def action_set_label(self) -> None:
        """Open label editor for focused session."""
        focused = self.focused
        if isinstance(focused, SessionRow):
            from monitorator.labels import get_label
            current = get_label(focused.session_id) or ""
            self.push_screen(LabelScreen(focused.session_id, current))

    def _kill_pid(self, pid: int) -> bool:
        """Send SIGTERM to a process. Returns True if signal was sent."""
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def action_kill_session(self) -> None:
        """Kill the focused session's process."""
        focused = self.focused
        if not isinstance(focused, SessionRow):
            return
        session = focused.session
        if not session.process_info:
            self.notify("No process to kill", severity="warning")
            return
        pid = session.process_info.pid
        if self._kill_pid(pid):
            self.notify(f"Killed PID {pid} ({session.project_name})")
            self._refresh()
        else:
            self.notify(f"Failed to kill PID {pid}", severity="error")

    def action_kill_stale(self) -> None:
        """Kill all stale sessions (IDLE + 0% CPU + running > 30 min)."""
        killed = []
        for sid, session in self._previous.items():
            if (
                session.effective_status == SessionStatus.IDLE
                and session.process_info
                and session.process_info.cpu_percent < 1.0
                and session.process_info.elapsed_seconds > 1800  # 30 min
            ):
                pid = session.process_info.pid
                if self._kill_pid(pid):
                    killed.append(f"{session.project_name} (PID {pid})")
        if killed:
            self.notify(f"Killed {len(killed)} stale: {', '.join(killed)}")
            self._refresh()
        else:
            self.notify("No stale sessions to kill")

    def _toggle_dropdown(self, session_id: str, focus: bool = False) -> None:
        """Toggle the chat history dropdown for a session row."""
        container = self.query_one("#session-list", VerticalScroll)

        # If already open for this session, close it (save scroll position)
        if session_id in self._dropdowns:
            dropdown = self._dropdowns.pop(session_id)
            self._dropdown_scroll_cache[session_id] = dropdown.scroll_y
            dropdown.remove()
            return

        # Open new dropdown after the row
        session = self._previous.get(session_id)
        if session and session_id in self._cards:
            saved_scroll = self._dropdown_scroll_cache.get(session_id)
            dropdown = ChatDropdown(session, initial_scroll_y=saved_scroll)
            container.mount(dropdown, after=self._cards[session_id])
            self._dropdowns[session_id] = dropdown
            if focus:
                dropdown.focus()

    def _show_detail(self, session_id: str, focus_dropdown: bool = False) -> None:
        self._focused_session_id = session_id
        session = self._previous.get(session_id)
        panel = self.query_one(DetailPanel)
        if session:
            panel.show_session(session)
        else:
            panel.clear_session()
        self._toggle_dropdown(session_id, focus=focus_dropdown)
