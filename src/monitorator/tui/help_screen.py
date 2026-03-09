from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Vertical
from textual.binding import Binding


class HelpScreen(ModalScreen[None]):
    """Modal help overlay showing keybindings."""

    BINDINGS = [
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close"),
    ]

    def compose(self):
        help_text = (
            "[bold #ffcc00]MONITORATOR \u2014 Keyboard Shortcuts[/]\n"
            "\n"
            "[#ffcc00]q[/]       Quit\n"
            "[#ffcc00]r[/]       Refresh\n"
            "[#ffcc00]R[/]       Force Refresh (aggressive cleanup)\n"
            "[#ffcc00]o[/]       Open Terminal for session\n"
            "[#ffcc00]j/k[/]     Navigate up/down\n"
            "[#ffcc00]Enter[/]   Select session (show details)\n"
            "[#ffcc00]s[/]       Cycle sort mode\n"
            "[#ffcc00]f[/]       Cycle filter mode\n"
            "[#ffcc00]v[/]       Toggle compact view\n"
            "[#ffcc00]c[/]       Copy CWD to clipboard\n"
            "[#ffcc00]?[/]       This help screen\n"
            "\n"
            "[#666666]Press ? or Esc to close[/]"
        )
        with Vertical(id="help-container"):
            yield Static(help_text, markup=True, id="help-text")

    CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-container {
        width: 50;
        height: auto;
        max-height: 20;
        background: #111111;
        border: double #ffcc00;
        padding: 1 2;
    }
    """
