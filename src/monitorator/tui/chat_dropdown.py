from __future__ import annotations

from rich.markup import escape

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from monitorator.models import MergedSession
from monitorator.session_prompt import find_newest_jsonl_for_cwd, get_session_history
from monitorator.tui.theme_colors import colors


class ChatMessage(Static):
    """A single chat message in the dropdown."""

    pass


class ChatDropdown(VerticalScroll):
    """Scrollable dropdown showing recent chat history for a session."""

    def __init__(
        self, session: MergedSession, initial_scroll_y: float | None = None
    ) -> None:
        super().__init__()
        self.session_id = session.session_id
        self._initial_scroll_y = initial_scroll_y
        self._messages = self._load_messages(session)

    @staticmethod
    def _load_messages(session: MergedSession) -> list[tuple[str, str]]:
        # Try process_info first (has live UUID from lsof)
        if session.process_info and session.process_info.session_uuid and session.process_info.cwd:
            return get_session_history(
                session.process_info.cwd,
                session.process_info.session_uuid,
            )
        # Fall back to hook_state (session_id is the UUID)
        if session.hook_state and session.hook_state.cwd:
            return get_session_history(
                session.hook_state.cwd,
                session.hook_state.session_id,
            )
        # Last resort: scan project dir for newest JSONL (hookless sessions)
        cwd = session.process_info.cwd if session.process_info else None
        if cwd:
            _path, uuid = find_newest_jsonl_for_cwd(cwd)
            if uuid:
                return get_session_history(cwd, uuid)
        return []

    def compose(self) -> ComposeResult:
        if not self._messages:
            yield ChatMessage(
                f"  [dim {colors.text_dim}]No conversation history available[/]",
                markup=True,
            )
            return

        prev_role = None
        for role, text in self._messages:
            safe = escape(text)

            if role == "user":
                cls = "user-msg turn-start" if prev_role is not None else "user-msg"
                safe_oneline = safe.replace("\n", " ").strip()
                if len(safe_oneline) > 80:
                    safe_oneline = safe_oneline[:79] + "\u2026"
                content = f"  [bold {colors.chat_user}]you:[/] [{colors.text_bright}]{safe_oneline}[/]"
                yield ChatMessage(content, markup=True, classes=cls)

            elif role == "assistant":
                safe_oneline = safe.replace("\n", " ").strip()
                if len(safe_oneline) > 80:
                    safe_oneline = safe_oneline[:79] + "\u2026"
                content = f"  [bold {colors.chat_assistant}]claude:[/] [{colors.text_body}]{safe_oneline}[/]"
                yield ChatMessage(content, markup=True, classes="assistant-msg")

            elif role == "tool":
                content = f"    [{colors.text_dim}]● {safe}[/]"
                yield ChatMessage(content, markup=True, classes="tool-msg")

            prev_role = role

    def on_mount(self) -> None:
        self.call_after_refresh(self._restore_scroll)

    def _restore_scroll(self) -> None:
        if self._initial_scroll_y is not None:
            self.scroll_to(y=self._initial_scroll_y, animate=False)
        else:
            self.scroll_end(animate=False)
