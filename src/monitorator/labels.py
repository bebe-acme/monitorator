from __future__ import annotations

import json
from pathlib import Path

_LABELS_PATH = Path.home() / ".monitorator" / "labels.json"


def _load_labels() -> dict[str, str]:
    """Load all session labels from disk."""
    if not _LABELS_PATH.exists():
        return {}
    try:
        data = json.loads(_LABELS_PATH.read_text())
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def get_label(session_id: str) -> str | None:
    """Get label for a session, or None if not set."""
    labels = _load_labels()
    return labels.get(session_id)


def set_label(session_id: str, label: str) -> None:
    """Set or clear a session label. Empty string removes the label."""
    labels = _load_labels()
    label = label.strip()
    if label:
        labels[session_id] = label
    else:
        labels.pop(session_id, None)
    _LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n")


def remove_label(session_id: str) -> None:
    """Remove a session label if it exists."""
    labels = _load_labels()
    if session_id in labels:
        del labels[session_id]
        _LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n")
