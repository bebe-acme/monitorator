from __future__ import annotations

import json
from pathlib import Path

from monitorator.tui.theme_colors import THEMES

_PREFS_PATH = Path.home() / ".monitorator" / "preferences.json"


def _load_prefs() -> dict:
    if not _PREFS_PATH.exists():
        return {}
    try:
        data = json.loads(_PREFS_PATH.read_text())
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def get_theme_preference() -> str:
    prefs = _load_prefs()
    theme = prefs.get("theme", "dark")
    if theme not in THEMES:
        return "dark"
    return theme


def set_theme_preference(name: str) -> None:
    if name not in THEMES:
        raise ValueError(f"Unknown theme: {name!r}. Choose from {list(THEMES)}")
    prefs = _load_prefs()
    prefs["theme"] = name
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(json.dumps(prefs, indent=2) + "\n")
