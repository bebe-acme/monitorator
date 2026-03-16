from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from monitorator.preferences import get_theme_preference, set_theme_preference


@pytest.fixture
def prefs_path(tmp_path: Path):
    """Redirect preferences to a temp file."""
    p = tmp_path / "preferences.json"
    with patch("monitorator.preferences._PREFS_PATH", p):
        yield p


class TestGetThemePreference:
    def test_returns_dark_when_no_file(self, prefs_path: Path) -> None:
        assert get_theme_preference() == "dark"

    def test_returns_saved_theme(self, prefs_path: Path) -> None:
        prefs_path.write_text('{"theme": "bokeh"}')
        assert get_theme_preference() == "bokeh"

    def test_returns_dark_on_corrupt_json(self, prefs_path: Path) -> None:
        prefs_path.write_text("not json")
        assert get_theme_preference() == "dark"

    def test_returns_dark_on_missing_key(self, prefs_path: Path) -> None:
        prefs_path.write_text('{"other": "value"}')
        assert get_theme_preference() == "dark"

    def test_returns_dark_on_invalid_theme(self, prefs_path: Path) -> None:
        prefs_path.write_text('{"theme": "neon"}')
        assert get_theme_preference() == "dark"


class TestSetThemePreference:
    def test_creates_file_and_saves(self, prefs_path: Path) -> None:
        set_theme_preference("light")
        data = json.loads(prefs_path.read_text())
        assert data["theme"] == "light"

    def test_overwrites_existing(self, prefs_path: Path) -> None:
        set_theme_preference("light")
        set_theme_preference("bokeh")
        data = json.loads(prefs_path.read_text())
        assert data["theme"] == "bokeh"

    def test_preserves_other_keys(self, prefs_path: Path) -> None:
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        prefs_path.write_text('{"other": "value"}')
        set_theme_preference("light")
        data = json.loads(prefs_path.read_text())
        assert data["other"] == "value"
        assert data["theme"] == "light"

    def test_roundtrip(self, prefs_path: Path) -> None:
        set_theme_preference("bokeh")
        assert get_theme_preference() == "bokeh"

    def test_rejects_invalid_theme(self, prefs_path: Path) -> None:
        with pytest.raises(ValueError):
            set_theme_preference("neon")
