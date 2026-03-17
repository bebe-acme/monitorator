from __future__ import annotations

from dataclasses import dataclass

from monitorator.models import SessionStatus


@dataclass(frozen=True)
class ThemeColors:
    """Semantic color tokens for Rich markup in Python code."""

    bg_base: str
    bg_raised: str
    bg_panel: str
    bg_hover: str
    bg_focused: str
    bg_permission: str
    border_accent: str
    border_dim: str
    separator: str
    text_body: str
    text_bright: str
    text_muted: str
    text_dim: str
    text_dimmer: str
    accent: str
    accent_bg: str
    status_thinking: str
    status_executing: str
    status_permission: str
    status_idle: str
    status_subagent: str
    status_terminated: str
    info_color: str
    branch_color: str
    activity_color: str
    chat_user: str
    chat_assistant: str
    scrollbar_idle: str
    scrollbar_active: str


DARK = ThemeColors(
    bg_base="#0a0a0a",
    bg_raised="#111111",
    bg_panel="#0e0e0e",
    bg_hover="#151515",
    bg_focused="#1a1a00",
    bg_permission="#1a0505",
    border_accent="#ffcc00",
    border_dim="#333300",
    separator="#1a1a1a",
    text_body="#cccccc",
    text_bright="#ffffff",
    text_muted="#888888",
    text_dim="#818181",
    text_dimmer="#666666",
    accent="#ffcc00",
    accent_bg="#1a1a00",
    status_thinking="#00ff66",
    status_executing="#3399ff",
    status_permission="#ff3333",
    status_idle="#ffaa00",
    status_subagent="#cc66ff",
    status_terminated="#666666",
    info_color="#3399ff",
    branch_color="#3399ff",
    activity_color="#777777",
    chat_user="#676af5",
    chat_assistant="#ffcc00",
    scrollbar_idle="#333300",
    scrollbar_active="#ffcc00",
)

LIGHT = ThemeColors(
    bg_base="#f5f5f0",
    bg_raised="#ffffff",
    bg_panel="#e8e8e3",
    bg_hover="#edede8",
    bg_focused="#fff8e0",
    bg_permission="#fff0f0",
    border_accent="#866104",
    border_dim="#cccccc",
    separator="#dddddd",
    text_body="#333333",
    text_bright="#111111",
    text_muted="#656565",
    text_dim="#686868",
    text_dimmer="#858585",
    accent="#866104",
    accent_bg="#fff8e0",
    status_thinking="#07752f",
    status_executing="#1065ca",
    status_permission="#cc2222",
    status_idle="#866104",
    status_subagent="#8833cc",
    status_terminated="#858585",
    info_color="#1065ca",
    branch_color="#1065ca",
    activity_color="#878787",
    chat_user="#4338ca",
    chat_assistant="#866104",
    scrollbar_idle="#cccccc",
    scrollbar_active="#866104",
)

BOKEH = ThemeColors(
    bg_base="#1b2838",
    bg_raised="#243447",
    bg_panel="#1e3044",
    bg_hover="#243a4d",
    bg_focused="#253d2d",
    bg_permission="#3a2030",
    border_accent="#e5ae38",
    border_dim="#2f5070",
    separator="#2a3e52",
    text_body="#c8d6e5",
    text_bright="#ffffff",
    text_muted="#8ba7c1",
    text_dim="#85a5c0",
    text_dimmer="#5f8da6",
    accent="#e5ae38",
    accent_bg="#2a3520",
    status_thinking="#2ca02c",
    status_executing="#3b8bba",
    status_permission="#f55a5a",
    status_idle="#e5ae38",
    status_subagent="#9c6fc5",
    status_terminated="#5f8da6",
    info_color="#59a9d8",
    branch_color="#59a9d8",
    activity_color="#6a8faa",
    chat_user="#7397d7",
    chat_assistant="#e5ae38",
    scrollbar_idle="#2f5070",
    scrollbar_active="#e5ae38",
)

HIGH_CONTRAST = ThemeColors(
    bg_base="#000000",
    bg_raised="#0a0a0a",
    bg_panel="#050505",
    bg_hover="#1a1a1a",
    bg_focused="#1a1a00",
    bg_permission="#200000",
    border_accent="#ffffff",
    border_dim="#555555",
    separator="#333333",
    text_body="#e0e0e0",
    text_bright="#ffffff",
    text_muted="#aaaaaa",
    text_dim="#999999",
    text_dimmer="#777777",
    accent="#ffffff",
    accent_bg="#1a1a1a",
    status_thinking="#00e050",
    status_executing="#40aaff",
    status_permission="#ff3030",
    status_idle="#ffcc00",
    status_subagent="#cc77ff",
    status_terminated="#777777",
    info_color="#40aaff",
    branch_color="#40aaff",
    activity_color="#999999",
    chat_user="#8888ff",
    chat_assistant="#ffffff",
    scrollbar_idle="#555555",
    scrollbar_active="#ffffff",
)

SOLARIZED_DARK = ThemeColors(
    bg_base="#002b36",
    bg_raised="#073642",
    bg_panel="#04313c",
    bg_hover="#0a3540",
    bg_focused="#083028",
    bg_permission="#200a15",
    border_accent="#3a9fe6",
    border_dim="#586e75",
    separator="#0a3642",
    text_body="#8a9b9d",
    text_bright="#93a1a1",
    text_muted="#899fa7",
    text_dim="#869ca4",
    text_dimmer="#697f86",
    accent="#3a9fe6",
    accent_bg="#073642",
    status_thinking="#859900",
    status_executing="#3a9fe6",
    status_permission="#e23835",
    status_idle="#b58900",
    status_subagent="#6d72c5",
    status_terminated="#697f86",
    info_color="#31a89f",
    branch_color="#31a89f",
    activity_color="#6d838a",
    chat_user="#878cdf",
    chat_assistant="#3a9fe6",
    scrollbar_idle="#586e75",
    scrollbar_active="#3a9fe6",
)

SOLARIZED_LIGHT = ThemeColors(
    bg_base="#fdf6e3",
    bg_raised="#f2ecda",
    bg_panel="#f5efdd",
    bg_hover="#f3eddb",
    bg_focused="#f7f1df",
    bg_permission="#fce8e6",
    border_accent="#096eb5",
    border_dim="#93a1a1",
    separator="#d6cdb5",
    text_body="#586e76",
    text_bright="#586e75",
    text_muted="#5b6c6e",
    text_dim="#5d6e70",
    text_dimmer="#7c8a8a",
    accent="#096eb5",
    accent_bg="#f2ecda",
    status_thinking="#7d9100",
    status_executing="#096eb5",
    status_permission="#dc322f",
    status_idle="#ad8100",
    status_subagent="#6c71c4",
    status_terminated="#7c8a8a",
    info_color="#01786f",
    branch_color="#01786f",
    activity_color="#6d7e80",
    chat_user="#5c61b4",
    chat_assistant="#096eb5",
    scrollbar_idle="#93a1a1",
    scrollbar_active="#096eb5",
)

THEMES: dict[str, ThemeColors] = {
    "dark": DARK,
    "light": LIGHT,
    "bokeh": BOKEH,
    "high-contrast": HIGH_CONTRAST,
    "solarized-dark": SOLARIZED_DARK,
    "solarized-light": SOLARIZED_LIGHT,
}

_STATUS_MAP = {
    SessionStatus.THINKING: "status_thinking",
    SessionStatus.EXECUTING: "status_executing",
    SessionStatus.WAITING_PERMISSION: "status_permission",
    SessionStatus.IDLE: "status_idle",
    SessionStatus.SUBAGENT_RUNNING: "status_subagent",
    SessionStatus.TERMINATED: "status_terminated",
    SessionStatus.UNKNOWN: "status_terminated",
}


class _ActiveColors:
    """Proxy that always reads from the current theme."""

    def __getattr__(self, name: str) -> str:
        return getattr(THEMES[_current_theme], name)


_current_theme: str = "dark"
colors = _ActiveColors()


def get_theme() -> str:
    return _current_theme


def set_theme(name: str) -> None:
    global _current_theme
    if name not in THEMES:
        raise ValueError(f"Unknown theme: {name!r}. Choose from {list(THEMES)}")
    _current_theme = name


def get_status_color(status: SessionStatus) -> str:
    attr = _STATUS_MAP.get(status, "status_terminated")
    return getattr(colors, attr)
