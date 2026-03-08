from __future__ import annotations

import json
from pathlib import Path

import pytest

from monitorator.installer import HookInstaller


class TestHookInstaller:
    def test_install_creates_hooks_in_empty_settings(self, tmp_settings_file: Path) -> None:
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        settings = json.loads(tmp_settings_file.read_text())
        assert "hooks" in settings
        hook_events = set(settings["hooks"].keys())
        expected_events = {
            "PreToolUse", "PostToolUse", "Notification",
            "SubagentStart", "SubagentStop", "Stop",
        }
        assert expected_events.issubset(hook_events)

    def test_install_preserves_existing_settings(self, tmp_settings_file: Path) -> None:
        tmp_settings_file.write_text(json.dumps({
            "permissions": {"allow": ["Bash"]},
            "hooks": {
                "PreToolUse": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "existing-hook"}]},
                ],
            },
        }))
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        settings = json.loads(tmp_settings_file.read_text())
        assert settings["permissions"] == {"allow": ["Bash"]}
        # Existing hook preserved + our hook added
        pre_hooks = settings["hooks"]["PreToolUse"]
        assert len(pre_hooks) == 2
        assert pre_hooks[0]["hooks"][0]["command"] == "existing-hook"
        assert any(
            "emit_event.py" in h["command"]
            for entry in pre_hooks
            for h in entry.get("hooks", [])
        )

    def test_install_creates_backup(self, tmp_settings_file: Path) -> None:
        tmp_settings_file.write_text(json.dumps({"original": True}))
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        backup = tmp_settings_file.with_suffix(".json.monitorator-backup")
        assert backup.exists()
        assert json.loads(backup.read_text()) == {"original": True}

    def test_install_idempotent(self, tmp_settings_file: Path) -> None:
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        first = json.loads(tmp_settings_file.read_text())
        installer.install()
        second = json.loads(tmp_settings_file.read_text())
        # Should not duplicate hooks
        for event_hooks in second.get("hooks", {}).values():
            monitorator_hooks = [h for h in event_hooks if "emit_event.py" in h.get("command", "")]
            assert len(monitorator_hooks) <= 1

    def test_uninstall_removes_hooks(self, tmp_settings_file: Path) -> None:
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        installer.uninstall()
        settings = json.loads(tmp_settings_file.read_text())
        for event_hooks in settings.get("hooks", {}).values():
            for h in event_hooks:
                assert "emit_event.py" not in h.get("command", "")

    def test_uninstall_preserves_other_hooks(self, tmp_settings_file: Path) -> None:
        tmp_settings_file.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "other-tool"}]},
                ],
            },
        }))
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        installer.uninstall()
        settings = json.loads(tmp_settings_file.read_text())
        pre_hooks = settings["hooks"]["PreToolUse"]
        assert len(pre_hooks) == 1
        assert pre_hooks[0]["hooks"][0]["command"] == "other-tool"

    def test_is_installed(self, tmp_settings_file: Path) -> None:
        installer = HookInstaller(tmp_settings_file)
        assert not installer.is_installed()
        installer.install()
        assert installer.is_installed()
        installer.uninstall()
        assert not installer.is_installed()

    def test_install_creates_settings_if_missing(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "newdir" / "settings.json"
        installer = HookInstaller(settings_file)
        installer.install()
        assert settings_file.exists()
        settings = json.loads(settings_file.read_text())
        assert "hooks" in settings

    def test_hook_command_uses_absolute_path(self, tmp_settings_file: Path) -> None:
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        settings = json.loads(tmp_settings_file.read_text())
        some_hooks = list(settings["hooks"].values())[0]
        # New format: hooks are nested under matcher objects
        inner_hooks = some_hooks[0]["hooks"]
        monitorator_hook = [h for h in inner_hooks if "emit_event.py" in h.get("command", "")][0]
        assert monitorator_hook["command"].startswith("python3 /")

    def test_install_uses_matcher_format(self, tmp_settings_file: Path) -> None:
        """Hooks must use the new matcher-based format required by Claude Code."""
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        settings = json.loads(tmp_settings_file.read_text())
        for event, entries in settings["hooks"].items():
            assert isinstance(entries, list), f"{event}: not a list"
            for entry in entries:
                assert "matcher" in entry, f"{event}: missing matcher field"
                assert isinstance(entry["matcher"], str), f"{event}: matcher must be a string, not {type(entry['matcher'])}"
                assert "hooks" in entry, f"{event}: missing hooks field"
                assert isinstance(entry["hooks"], list), f"{event}: hooks not a list"
                for hook in entry["hooks"]:
                    assert "type" in hook, f"{event}: hook missing type"
                    assert "command" in hook, f"{event}: hook missing command"

    def test_install_preserves_existing_matcher_hooks(self, tmp_settings_file: Path) -> None:
        """Existing hooks in the new matcher format should be preserved."""
        tmp_settings_file.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo done"}],
                    }
                ],
            },
        }))
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        settings = json.loads(tmp_settings_file.read_text())
        pre_hooks = settings["hooks"]["PreToolUse"]
        # Should have the existing matcher hook + our new one
        assert len(pre_hooks) == 2
        # Existing one preserved
        assert pre_hooks[0]["matcher"] == "Bash"
        assert pre_hooks[0]["hooks"][0]["command"] == "echo done"
        # Ours added
        assert any(
            "emit_event.py" in h["command"]
            for entry in pre_hooks
            for h in entry.get("hooks", [])
        )

    def test_uninstall_removes_matcher_format_hooks(self, tmp_settings_file: Path) -> None:
        """Uninstall should remove hooks in the new matcher format."""
        installer = HookInstaller(tmp_settings_file)
        installer.install()
        installer.uninstall()
        settings = json.loads(tmp_settings_file.read_text())
        for event_entries in settings.get("hooks", {}).values():
            for entry in event_entries:
                for h in entry.get("hooks", []):
                    assert "emit_event.py" not in h.get("command", "")

    def test_is_installed_detects_matcher_format(self, tmp_settings_file: Path) -> None:
        """is_installed should detect hooks in the new matcher format."""
        installer = HookInstaller(tmp_settings_file)
        assert not installer.is_installed()
        installer.install()
        assert installer.is_installed()
        installer.uninstall()
        assert not installer.is_installed()
