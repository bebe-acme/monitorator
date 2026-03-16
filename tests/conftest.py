from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture(autouse=True)
def _reset_theme() -> None:
    """Ensure every test starts with the dark theme to prevent leakage."""
    from monitorator.tui.theme_colors import set_theme
    set_theme("dark")


@pytest.fixture
def tmp_sessions_dir(tmp_path: Path) -> Path:
    """Provide a temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def tmp_settings_file(tmp_path: Path) -> Path:
    """Provide a temporary Claude settings.json file."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({}))
    return settings_file
