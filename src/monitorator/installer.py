from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HOOK_SCRIPT_PY = Path(__file__).parent.parent.parent / "hooks" / "emit_event.py"
HOOK_BINARY_ZIG = Path(__file__).parent.parent.parent / "hooks" / "zig" / "zig-out" / "bin" / "emit_event"
MARKER = "emit_event"

_GLOBAL_BIN_DIR = Path.home() / ".monitorator" / "bin"
_GLOBAL_BINARY = _GLOBAL_BIN_DIR / "emit_event"

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
    """Always point at the global installed binary in ~/.monitorator/bin/."""
    return str(_GLOBAL_BINARY)


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

    @staticmethod
    def _install_binary() -> None:
        """Copy the repo's hook binary (or script) to ~/.monitorator/bin/."""
        source = HOOK_BINARY_ZIG if HOOK_BINARY_ZIG.exists() else HOOK_SCRIPT_PY
        if not source.exists():
            return
        _GLOBAL_BIN_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, _GLOBAL_BINARY)
        _GLOBAL_BINARY.chmod(0o755)

    def install(self) -> None:
        # Copy binary to global location
        self._install_binary()

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

    def _get_installed_command(self) -> str | None:
        """Return the hook command currently in settings.json, or None."""
        settings = self._read_settings()
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            return None
        for event_hooks in hooks.values():
            if not isinstance(event_hooks, list):
                continue
            for entry in event_hooks:
                if not isinstance(entry, dict):
                    continue
                inner = entry.get("hooks")
                if isinstance(inner, list):
                    for h in inner:
                        if isinstance(h, dict) and MARKER in h.get("command", ""):
                            return h["command"]
        return None

    @staticmethod
    def _hash_file(path: Path) -> str | None:
        """SHA-256 of a file, or None if it doesn't exist."""
        if not path.exists():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def ensure_up_to_date(self) -> bool:
        """Check if hooks need updating and re-install if so.

        Compares the repo's source binary against the installed global copy.
        Also re-installs if the hook command in settings.json is stale or
        hooks are missing. Returns True if hooks were updated.
        """
        source = HOOK_BINARY_ZIG if HOOK_BINARY_ZIG.exists() else HOOK_SCRIPT_PY
        source_hash = self._hash_file(source)
        if source_hash is None:
            return False

        installed_hash = self._hash_file(_GLOBAL_BINARY)
        installed_cmd = self._get_installed_command()
        needs_update = (
            source_hash != installed_hash
            or installed_cmd != self._hook_command
            or not self.is_installed()
        )

        if needs_update:
            self.install()
            return True

        return False
