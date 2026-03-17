from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Vertical
from textual.binding import Binding

from monitorator.tui.theme_colors import colors


class HelpScreen(ModalScreen[None]):
    """Modal help overlay showing keybindings."""

    BINDINGS = [
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("h", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close"),
    ]

    def compose(self):
        a = colors.accent
        d = colors.text_dimmer
        help_text = (
            f"[bold {a}]MONITORATOR \u2014 Keyboard Shortcuts[/]\n"
            "\n"
            f"[{a}]q[/]       Quit\n"
            f"[{a}]r[/]       Refresh\n"
            f"[{a}]R[/]       Force Refresh (aggressive cleanup)\n"
            f"[{a}]o[/]       Open Terminal for session\n"
            f"[{a}]t[/]       Cycle theme\n"
            f"[{a}]T[/]       Theme picker\n"
            f"[{a}]j/k[/]     Navigate up/down\n"
            f"[{a}]Enter[/]   Select session (show details)\n"
            f"[{a}]s[/]       Cycle sort mode\n"
            f"[{a}]f[/]       Cycle filter mode\n"
            f"[{a}]v[/]       Toggle compact view\n"
            f"[{a}]c[/]       Copy CWD to clipboard\n"
            f"[{a}]l[/]       Set session label\n"
            f"[{a}]x[/]       Kill focused session\n"
            f"[{a}]X[/]       Kill all stale sessions\n"
            f"[{a}]?/h[/]     This help screen\n"
            "\n"
            f"[{d}]Press ? or Esc to close[/]"
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
        max-height: 22;
        background: $bg-raised;
        border: double $accent;
        padding: 1 2;
    }
    """
