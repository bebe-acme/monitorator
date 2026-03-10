from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from monitorator.labels import get_label, set_label, remove_label


@pytest.fixture
def labels_path(tmp_path: Path):
    """Redirect labels to a temp file."""
    p = tmp_path / "labels.json"
    with patch("monitorator.labels._LABELS_PATH", p):
        yield p


class TestGetLabel:
    def test_returns_none_when_no_file(self, labels_path: Path) -> None:
        assert get_label("session-1") is None

    def test_returns_none_when_not_found(self, labels_path: Path) -> None:
        labels_path.write_text('{"other": "label"}')
        assert get_label("session-1") is None

    def test_returns_label(self, labels_path: Path) -> None:
        labels_path.write_text('{"session-1": "login feature"}')
        assert get_label("session-1") == "login feature"

    def test_handles_corrupt_json(self, labels_path: Path) -> None:
        labels_path.write_text("not json")
        assert get_label("session-1") is None

    def test_handles_non_dict_json(self, labels_path: Path) -> None:
        labels_path.write_text('["a", "b"]')
        assert get_label("session-1") is None


class TestSetLabel:
    def test_creates_file_and_sets_label(self, labels_path: Path) -> None:
        set_label("session-1", "my feature")
        data = json.loads(labels_path.read_text())
        assert data["session-1"] == "my feature"

    def test_overwrites_existing_label(self, labels_path: Path) -> None:
        set_label("session-1", "old")
        set_label("session-1", "new")
        data = json.loads(labels_path.read_text())
        assert data["session-1"] == "new"

    def test_empty_string_removes_label(self, labels_path: Path) -> None:
        set_label("session-1", "something")
        set_label("session-1", "")
        data = json.loads(labels_path.read_text())
        assert "session-1" not in data

    def test_whitespace_only_removes_label(self, labels_path: Path) -> None:
        set_label("session-1", "something")
        set_label("session-1", "   ")
        data = json.loads(labels_path.read_text())
        assert "session-1" not in data

    def test_preserves_other_labels(self, labels_path: Path) -> None:
        set_label("session-1", "first")
        set_label("session-2", "second")
        data = json.loads(labels_path.read_text())
        assert data["session-1"] == "first"
        assert data["session-2"] == "second"

    def test_strips_whitespace(self, labels_path: Path) -> None:
        set_label("session-1", "  padded  ")
        data = json.loads(labels_path.read_text())
        assert data["session-1"] == "padded"


class TestRemoveLabel:
    def test_removes_existing_label(self, labels_path: Path) -> None:
        set_label("session-1", "to remove")
        remove_label("session-1")
        assert get_label("session-1") is None

    def test_noop_when_not_found(self, labels_path: Path) -> None:
        # Should not raise
        remove_label("nonexistent")
        assert get_label("nonexistent") is None

    def test_preserves_other_labels(self, labels_path: Path) -> None:
        set_label("session-1", "keep")
        set_label("session-2", "remove")
        remove_label("session-2")
        assert get_label("session-1") == "keep"
        assert get_label("session-2") is None
