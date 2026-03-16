from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Static
from textual.containers import Vertical

from monitorator.labels import set_label
from monitorator.tui.theme_colors import colors


class LabelScreen(ModalScreen[str | None]):
    """Modal dialog for setting a session label."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, session_id: str, current_label: str = "") -> None:
        super().__init__()
        self._session_id = session_id
        self._current_label = current_label

    def compose(self) -> ComposeResult:
        with Vertical(id="label-dialog"):
            yield Static(f"[bold {colors.accent}]Set session label[/]", markup=True)
            yield Input(
                value=self._current_label,
                placeholder="e.g. login feature expansion",
                id="label-input",
            )
            yield Static(
                "[dim]Enter to save \u2022 Escape to cancel \u2022 Empty to clear[/]",
                markup=True,
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        label = event.value.strip()
        set_label(self._session_id, label)
        self.dismiss(label if label else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
