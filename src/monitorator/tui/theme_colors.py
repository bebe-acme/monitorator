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
    text_dim="#555555",
    text_dimmer="#444444",
    accent="#ffcc00",
    accent_bg="#1a1a00",
    status_thinking="#00ff66",
    status_executing="#3399ff",
    status_permission="#ff3333",
    status_idle="#ffaa00",
    status_subagent="#cc66ff",
    status_terminated="#444444",
    info_color="#3399ff",
    branch_color="#3399ff",
    activity_color="#777777",
    chat_user="#6366f1",
    chat_assistant="#ffcc00",
    scrollbar_idle="#333300",
    scrollbar_active="#ffcc00",
)

LIGHT = ThemeColors(
    bg_base="#f5f5f0",
    bg_raised="#ffffff",
    bg_panel="#eaeaea",
    bg_hover="#e8e8e8",
    bg_focused="#fff8e0",
    bg_permission="#fff0f0",
    border_accent="#b8860b",
    border_dim="#cccccc",
    separator="#dddddd",
    text_body="#333333",
    text_bright="#111111",
    text_muted="#777777",
    text_dim="#999999",
    text_dimmer="#aaaaaa",
    accent="#b8860b",
    accent_bg="#fff8e0",
    status_thinking="#0a8f3a",
    status_executing="#1a6fd4",
    status_permission="#cc2222",
    status_idle="#b8860b",
    status_subagent="#8833cc",
    status_terminated="#aaaaaa",
    info_color="#1a6fd4",
    branch_color="#1a6fd4",
    activity_color="#888888",
    chat_user="#4338ca",
    chat_assistant="#b8860b",
    scrollbar_idle="#cccccc",
    scrollbar_active="#b8860b",
)

BOKEH = ThemeColors(
    bg_base="#1b2838",
    bg_raised="#243447",
    bg_panel="#1e3044",
    bg_hover="#2a4055",
    bg_focused="#2f4a3a",
    bg_permission="#3a2030",
    border_accent="#e5ae38",
    border_dim="#2f5070",
    separator="#2a3e52",
    text_body="#c8d6e5",
    text_bright="#ffffff",
    text_muted="#7f9bb5",
    text_dim="#5a7a95",
    text_dimmer="#4a6a80",
    accent="#e5ae38",
    accent_bg="#2a3520",
    status_thinking="#2ca02c",
    status_executing="#3b8bba",
    status_permission="#d62728",
    status_idle="#e5ae38",
    status_subagent="#9467bd",
    status_terminated="#4a6a80",
    info_color="#3b8bba",
    branch_color="#3b8bba",
    activity_color="#6a8faa",
    chat_user="#5b7fbf",
    chat_assistant="#e5ae38",
    scrollbar_idle="#2f5070",
    scrollbar_active="#e5ae38",
)

THEMES: dict[str, ThemeColors] = {
    "dark": DARK,
    "light": LIGHT,
    "bokeh": BOKEH,
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
