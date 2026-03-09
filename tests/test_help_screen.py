from __future__ import annotations


class TestHelpScreen:
    def test_help_screen_has_keybindings_text(self) -> None:
        from monitorator.tui.help_screen import HelpScreen

        screen = HelpScreen()
        # Should be importable and instantiable
        assert screen is not None

    def test_help_screen_has_dismiss_binding(self) -> None:
        from monitorator.tui.help_screen import HelpScreen

        keys = [b.key for b in HelpScreen.BINDINGS]
        assert "escape" in keys

    def test_help_screen_has_question_mark_dismiss(self) -> None:
        from monitorator.tui.help_screen import HelpScreen

        keys = [b.key for b in HelpScreen.BINDINGS]
        assert "question_mark" in keys
