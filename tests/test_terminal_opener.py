from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from monitorator.terminal_opener import (
    get_tty_for_pid,
    activate_terminal_for_tty,
    open_terminal_for_pid,
    _activate_ghostty_tab,
    _activate_iterm2_tab,
    _activate_terminal_app_tab,
    _find_terminal_app_for_tty,
)


class TestGetTtyForPid:
    def test_returns_tty_string(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ttys003\n"
            )
            result = get_tty_for_pid(12345)
            assert result == "ttys003"
            mock_run.assert_called_once_with(
                ["ps", "-o", "tty=", "-p", "12345"],
                capture_output=True,
                text=True,
                timeout=5,
            )

    def test_returns_none_on_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = get_tty_for_pid(99999)
            assert result is None

    def test_returns_none_on_empty_output(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="  \n")
            result = get_tty_for_pid(12345)
            assert result is None

    def test_returns_none_on_question_mark(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="?\n")
            result = get_tty_for_pid(12345)
            assert result is None

    def test_returns_none_on_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ps", 5)):
            result = get_tty_for_pid(12345)
            assert result is None

    def test_returns_none_on_os_error(self) -> None:
        with patch("subprocess.run", side_effect=OSError("no ps")):
            result = get_tty_for_pid(12345)
            assert result is None


class TestActivateTerminalForTty:
    def test_dispatches_to_ghostty_when_detected(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value="Ghostty"), \
             patch("monitorator.terminal_opener._activate_ghostty_tab", return_value=True) as mock_ghostty:
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            mock_ghostty.assert_called_once_with("ttys003")

    def test_dispatches_to_iterm_when_detected(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value="iTerm2"), \
             patch("monitorator.terminal_opener._activate_iterm2_tab", return_value=True) as mock_iterm:
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            mock_iterm.assert_called_once_with("ttys003")

    def test_dispatches_to_terminal_app_when_detected(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value="Terminal"), \
             patch("monitorator.terminal_opener._activate_terminal_app_tab", return_value=True) as mock_term:
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            mock_term.assert_called_once_with("ttys003")

    def test_falls_back_to_iterm_when_ghostty_fails(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value=None), \
             patch("monitorator.terminal_opener._activate_ghostty_tab", return_value=False), \
             patch("monitorator.terminal_opener._activate_iterm2_tab", return_value=True) as mock_iterm:
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            mock_iterm.assert_called_once_with("ttys003")

    def test_falls_back_to_terminal_app(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value=None), \
             patch("monitorator.terminal_opener._activate_ghostty_tab", return_value=False), \
             patch("monitorator.terminal_opener._activate_iterm2_tab", return_value=False), \
             patch("monitorator.terminal_opener._activate_terminal_app_tab", return_value=True) as mock_term:
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            mock_term.assert_called_once_with("ttys003")

    def test_returns_false_when_all_fail(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", return_value=None), \
             patch("monitorator.terminal_opener._activate_ghostty_tab", return_value=False), \
             patch("monitorator.terminal_opener._activate_iterm2_tab", return_value=False), \
             patch("monitorator.terminal_opener._activate_terminal_app_tab", return_value=False):
            result = activate_terminal_for_tty("ttys003")
            assert result is False

    def test_propagates_exception_from_detection(self) -> None:
        with patch("monitorator.terminal_opener._find_terminal_app_for_tty", side_effect=OSError("no ps")):
            with pytest.raises(OSError):
                activate_terminal_for_tty("ttys003")


class TestOpenTerminalForPid:
    def test_success_path(self) -> None:
        with patch("monitorator.terminal_opener.get_tty_for_pid", return_value="ttys003"), \
             patch("monitorator.terminal_opener.activate_terminal_for_tty", return_value=True):
            result = open_terminal_for_pid(12345)
            assert result is True

    def test_no_tty_returns_false(self) -> None:
        with patch("monitorator.terminal_opener.get_tty_for_pid", return_value=None):
            result = open_terminal_for_pid(12345)
            assert result is False

    def test_activation_fails_returns_false(self) -> None:
        with patch("monitorator.terminal_opener.get_tty_for_pid", return_value="ttys003"), \
             patch("monitorator.terminal_opener.activate_terminal_for_tty", return_value=False):
            result = open_terminal_for_pid(12345)
            assert result is False
