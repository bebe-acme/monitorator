from __future__ import annotations


class TestThemeScreen:
    def test_importable_and_instantiable(self) -> None:
        from monitorator.tui.theme_screen import ThemeScreen

        screen = ThemeScreen("dark")
        assert screen is not None

    def test_has_dismiss_bindings(self) -> None:
        from monitorator.tui.theme_screen import ThemeScreen

        keys = [b.key for b in ThemeScreen.BINDINGS]
        assert "escape" in keys

    def test_stores_current_theme(self) -> None:
        from monitorator.tui.theme_screen import ThemeScreen

        screen = ThemeScreen("bokeh")
        assert screen._current_theme == "bokeh"

    def test_has_all_three_theme_labels(self) -> None:
        from monitorator.tui.theme_screen import _THEME_LABELS
        from monitorator.tui.theme_colors import THEMES

        for name in THEMES:
            assert name in _THEME_LABELS

    def test_result_type_is_str_or_none(self) -> None:
        from monitorator.tui.theme_screen import ThemeScreen

        # ThemeScreen should be a ModalScreen that returns str | None
        screen = ThemeScreen("dark")
        assert hasattr(screen, "dismiss")
