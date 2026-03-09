from __future__ import annotations

import json
import shutil
from pathlib import Path

HOOK_SCRIPT_PY = Path(__file__).parent.parent.parent / "hooks" / "emit_event.py"
HOOK_BINARY_ZIG = Path(__file__).parent.parent.parent / "hooks" / "zig" / "zig-out" / "bin" / "emit_event"
MARKER = "emit_event"

HOOK_EVENTS = [
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "SubagentStart",
    "SubagentStop",
    "Stop",
    "UserPromptSubmit",
]


def _resolve_hook_command() -> str:
    """Prefer compiled Zig binary; fall back to Python script."""
    if HOOK_BINARY_ZIG.exists():
        return str(HOOK_BINARY_ZIG.resolve())
    return f"python3 {HOOK_SCRIPT_PY.resolve()}"


class HookInstaller:
    def __init__(self, settings_path: Path | None = None) -> None:
        if settings_path is None:
            settings_path = Path.home() / ".claude" / "settings.json"
        self._path = settings_path
        self._hook_command = _resolve_hook_command()

    def _read_settings(self) -> dict[str, object]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _write_settings(self, settings: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(settings, indent=2) + "\n")

    def _make_hook_entry(self) -> dict[str, object]:
        """Create a matcher-based hook entry (new Claude Code format)."""
        return {
            "matcher": "",
            "hooks": [{"type": "command", "command": self._hook_command}],
        }

    @staticmethod
    def _entry_has_marker(entry: object) -> bool:
        """Check if a hook entry (old or new format) contains our marker."""
        if not isinstance(entry, dict):
            return False
        # New format: {"matcher": {}, "hooks": [{"type": "command", "command": "..."}]}
        inner_hooks = entry.get("hooks")
        if isinstance(inner_hooks, list):
            for h in inner_hooks:
                if isinstance(h, dict) and MARKER in h.get("command", ""):
                    return True
        # Old format: {"type": "command", "command": "..."}
        if MARKER in entry.get("command", ""):
            return True
        return False

    def install(self) -> None:
        settings = self._read_settings()

        # Backup
        if self._path.exists():
            backup = self._path.with_suffix(".json.monitorator-backup")
            shutil.copy2(self._path, backup)

        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
            settings["hooks"] = hooks

        entry = self._make_hook_entry()

        for event in HOOK_EVENTS:
            event_hooks = hooks.get(event)
            if not isinstance(event_hooks, list):
                event_hooks = []
                hooks[event] = event_hooks

            # Remove existing monitorator hooks — both old and new format (idempotent)
            event_hooks[:] = [h for h in event_hooks if not self._entry_has_marker(h)]
            event_hooks.append(entry)

        self._write_settings(settings)

    def uninstall(self) -> None:
        settings = self._read_settings()
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            return

        for event in list(hooks.keys()):
            event_hooks = hooks[event]
            if isinstance(event_hooks, list):
                event_hooks[:] = [h for h in event_hooks if not self._entry_has_marker(h)]

        self._write_settings(settings)

    def is_installed(self) -> bool:
        settings = self._read_settings()
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            return False
        for event_hooks in hooks.values():
            if isinstance(event_hooks, list):
                for entry in event_hooks:
                    if self._entry_has_marker(entry):
                        return True
        return False
