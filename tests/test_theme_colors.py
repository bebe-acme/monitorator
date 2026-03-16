from __future__ import annotations

import pytest

from monitorator.tui.theme_colors import (
    ThemeColors,
    DARK,
    LIGHT,
    BOKEH,
    THEMES,
    colors,
    get_theme,
    set_theme,
    get_status_color,
)
from monitorator.models import SessionStatus


class TestThemeColorsDataclass:
    """All three theme instances have all required tokens."""

    @pytest.mark.parametrize("theme", [DARK, LIGHT, BOKEH])
    def test_all_tokens_are_strings(self, theme: ThemeColors) -> None:
        import dataclasses
        for f in dataclasses.fields(theme):
            value = getattr(theme, f.name)
            assert isinstance(value, str), f"{f.name} should be a str, got {type(value)}"

    @pytest.mark.parametrize("theme", [DARK, LIGHT, BOKEH])
    def test_all_tokens_are_hex_colors(self, theme: ThemeColors) -> None:
        import dataclasses
        import re
        for f in dataclasses.fields(theme):
            value = getattr(theme, f.name)
            assert re.match(r"^#[0-9a-fA-F]{6}$", value), (
                f"{f.name}={value!r} is not a valid hex color"
            )

    def test_dark_bg_base(self) -> None:
        assert DARK.bg_base == "#0a0a0a"

    def test_light_bg_base(self) -> None:
        assert LIGHT.bg_base == "#f5f5f0"

    def test_bokeh_bg_base(self) -> None:
        assert BOKEH.bg_base == "#1b2838"


class TestThemeSwitching:
    def setup_method(self) -> None:
        set_theme("dark")

    def test_default_is_dark(self) -> None:
        assert get_theme() == "dark"

    def test_set_and_get_roundtrip(self) -> None:
        set_theme("light")
        assert get_theme() == "light"
        set_theme("bokeh")
        assert get_theme() == "bokeh"
        set_theme("dark")
        assert get_theme() == "dark"

    def test_colors_object_reflects_theme(self) -> None:
        set_theme("dark")
        assert colors.bg_base == "#0a0a0a"
        set_theme("light")
        assert colors.bg_base == "#f5f5f0"
        set_theme("bokeh")
        assert colors.bg_base == "#1b2838"

    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ValueError):
            set_theme("neon")

    def test_themes_dict_has_three_entries(self) -> None:
        assert set(THEMES.keys()) == {"dark", "light", "bokeh"}


class TestGetStatusColor:
    def setup_method(self) -> None:
        set_theme("dark")

    def test_thinking_color(self) -> None:
        assert get_status_color(SessionStatus.THINKING) == "#00ff66"

    def test_executing_color(self) -> None:
        assert get_status_color(SessionStatus.EXECUTING) == "#3399ff"

    def test_permission_color(self) -> None:
        assert get_status_color(SessionStatus.WAITING_PERMISSION) == "#ff3333"

    def test_idle_color(self) -> None:
        assert get_status_color(SessionStatus.IDLE) == "#ffaa00"

    def test_subagent_color(self) -> None:
        assert get_status_color(SessionStatus.SUBAGENT_RUNNING) == "#cc66ff"

    def test_terminated_color(self) -> None:
        assert get_status_color(SessionStatus.TERMINATED) == "#444444"

    def test_unknown_color(self) -> None:
        assert get_status_color(SessionStatus.UNKNOWN) == "#444444"

    def test_colors_change_with_theme(self) -> None:
        set_theme("light")
        assert get_status_color(SessionStatus.THINKING) == "#0a8f3a"
        set_theme("bokeh")
        assert get_status_color(SessionStatus.THINKING) == "#2ca02c"
