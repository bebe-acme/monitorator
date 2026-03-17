from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from monitorator.tui.theme_colors import THEMES, colors


_THEME_LABELS: dict[str, str] = {
    "dark": "Dark             Near-black, yellow accent",
    "light": "Light            Warm white, amber accent",
    "bokeh": "Bokeh            Navy + gold, data-viz",
    "high-contrast": "High Contrast    Pure black, max readability",
    "solarized-dark": "Solarized Dark   Teal + blue, terminal classic",
    "solarized-light": "Solarized Light  Cream + blue, terminal classic",
}


class ThemeScreen(ModalScreen[str | None]):
    """Modal dialog for selecting a color theme."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("1", "pick_1", "Dark", show=False),
        Binding("2", "pick_2", "Light", show=False),
        Binding("3", "pick_3", "Bokeh", show=False),
        Binding("4", "pick_4", "High Contrast", show=False),
        Binding("5", "pick_5", "Solarized Dark", show=False),
        Binding("6", "pick_6", "Solarized Light", show=False),
    ]

    def __init__(self, current_theme: str) -> None:
        super().__init__()
        self._current_theme = current_theme

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-dialog"):
            yield Static(
                f"[bold {colors.accent}]Select Theme[/]", markup=True
            )
            for i, name in enumerate(THEMES, start=1):
                label = _THEME_LABELS.get(name, name)
                if name == self._current_theme:
                    line = f"[bold {colors.accent}] {i}  \u25b6 {label}[/]"
                else:
                    line = f"[{colors.text_body}] {i}    {label}[/]"
                yield Static(line, markup=True)
            yield Static(
                f"[{colors.text_dimmer}]Press 1-6 to select \u2022 Esc to cancel[/]",
                markup=True,
            )

    def _pick(self, index: int) -> None:
        names = list(THEMES.keys())
        if 0 <= index < len(names):
            self.dismiss(names[index])

    def action_pick_1(self) -> None:
        self._pick(0)

    def action_pick_2(self) -> None:
        self._pick(1)

    def action_pick_3(self) -> None:
        self._pick(2)

    def action_pick_4(self) -> None:
        self._pick(3)

    def action_pick_5(self) -> None:
        self._pick(4)

    def action_pick_6(self) -> None:
        self._pick(5)

    def action_cancel(self) -> None:
        self.dismiss(None)

    CSS = """
    ThemeScreen {
        align: center middle;
    }
    #theme-dialog {
        width: 60;
        height: auto;
        max-height: 15;
        background: $bg-raised;
        border: round $accent;
        padding: 1 2;
    }
    """
