from __future__ import annotations

from unittest.mock import patch, MagicMock, call
import subprocess

import pytest

from monitorator.terminal_opener import (
    _find_terminal_app_for_pid,
    _badge_and_activate,
    _APP_BUNDLE_RE,
    open_terminal_for_pid,
)


def _mock_ps_chain(chain: list[tuple[int, str]]):
    """Build side_effect for ps calls that walk up a process tree.

    chain: [(ppid, command), ...] — each entry is one ancestor.
    Two subprocess.run calls per ancestor (ppid lookup, then command lookup).
    """
    effects = []
    for ppid, command in chain:
        effects.append(MagicMock(returncode=0, stdout=f"  {ppid}\n"))
        effects.append(MagicMock(returncode=0, stdout=f"{command}\n"))
    return effects


class TestFindTerminalApp:
    def test_finds_warp_via_app_path(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_ps_chain([
                (100, "/Users/me/.claude/local/claude"),
                (50, "-zsh"),
                (10, "/Applications/Warp.app/Contents/MacOS/stable"),
            ])
            result = _find_terminal_app_for_pid(12345)
            assert result == "Warp"

    def test_finds_ghostty(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_ps_chain([
                (100, "-zsh"),
                (10, "/Applications/Ghostty.app/Contents/MacOS/ghostty"),
            ])
            result = _find_terminal_app_for_pid(12345)
            assert result == "Ghostty"

    def test_finds_iterm2(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_ps_chain([
                (100, "login -fp user"),
                (50, "-zsh"),
                (10, "/Applications/iTerm2.app/Contents/MacOS/iTerm2"),
            ])
            result = _find_terminal_app_for_pid(12345)
            assert result == "iTerm2"

    def test_finds_terminal_app(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_ps_chain([
                (100, "-zsh"),
                (10, "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal"),
            ])
            result = _find_terminal_app_for_pid(12345)
            assert result == "Terminal"

    def test_returns_none_at_pid_1(self) -> None:
        with patch("subprocess.run") as mock_run:
            # Parent is PID 1 (launchd) — no terminal found
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="  1\n"),
            ]
            result = _find_terminal_app_for_pid(12345)
            assert result is None

    def test_returns_none_on_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ps", 2)):
            result = _find_terminal_app_for_pid(12345)
            assert result is None

    def test_returns_none_on_empty_output(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = _find_terminal_app_for_pid(12345)
            assert result is None

    def test_fallback_extracts_app_from_bundle_path(self) -> None:
        """Unknown terminal with .app path should be detected via fallback."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_ps_chain([
                (100, "-zsh"),
                (10, "/Applications/CoolTerminal.app/Contents/MacOS/cool"),
            ]) + [
                # Walk hits PID 1
                MagicMock(returncode=0, stdout="  1\n"),
            ]
            result = _find_terminal_app_for_pid(12345)
            assert result == "CoolTerminal"

    def test_app_bundle_regex(self) -> None:
        assert _APP_BUNDLE_RE.search("/Applications/Foo.app/Contents/MacOS/x")
        assert _APP_BUNDLE_RE.search("/Applications/Foo.app/Contents/MacOS/x").group(1) == "Foo"
        assert _APP_BUNDLE_RE.search("/Applications/Foo Bar.app/Contents/MacOS/x").group(1) == "Foo Bar"
        assert _APP_BUNDLE_RE.search("/usr/bin/python") is None


class TestBadgeAndActivate:
    def test_success(self) -> None:
        with patch("subprocess.run") as mock_run, \
             patch("os.open", side_effect=OSError):
            mock_run.return_value = MagicMock(returncode=0)
            assert _badge_and_activate("Warp", None) is True

    def test_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert _badge_and_activate("Warp", None) is False

    def test_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 5)):
            assert _badge_and_activate("Warp", None) is False

    def test_rings_bell_on_tty(self) -> None:
        with patch("subprocess.run") as mock_run, \
             patch("os.open", return_value=5) as mock_open, \
             patch("os.write") as mock_write, \
             patch("os.close"):
            mock_run.return_value = MagicMock(returncode=0)
            assert _badge_and_activate("Warp", "ttys003") is True
            mock_open.assert_called_once()
            mock_write.assert_called_once_with(5, b"\a")


class TestOpenTerminalForPid:
    def test_opens_warp(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_pid", return_value="Warp"), \
             patch("monitorator.terminal_opener._badge_and_activate", return_value=True) as mock_activate:
            result = open_terminal_for_pid(12345, tty="ttys003")
            assert result is True
            mock_activate.assert_called_once_with("Warp", "ttys003")

    def test_opens_iterm2_with_tab_focus(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_pid", return_value="iTerm2"), \
             patch("monitorator.terminal_opener._activate_iterm2_tab", return_value=True) as mock_tab:
            result = open_terminal_for_pid(12345, tty="ttys003")
            assert result is True
            mock_tab.assert_called_once_with("ttys003")

    def test_opens_terminal_app_with_tab_focus(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_pid", return_value="Terminal"), \
             patch("monitorator.terminal_opener._activate_terminal_tab", return_value=True) as mock_tab:
            result = open_terminal_for_pid(12345, tty="ttys003")
            assert result is True
            mock_tab.assert_called_once_with("ttys003")

    def test_no_terminal_found(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_pid", return_value=None):
            result = open_terminal_for_pid(12345)
            assert result is False

    def test_falls_back_to_badge_when_no_tty(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_pid", return_value="iTerm2"), \
             patch("monitorator.terminal_opener._badge_and_activate", return_value=True) as mock_activate:
            result = open_terminal_for_pid(12345)
            assert result is True
            mock_activate.assert_called_once_with("iTerm2", None)
