from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from monitorator.terminal_opener import (
    get_tty_for_pid,
    activate_terminal_for_tty,
    open_terminal_for_pid,
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
    def test_tries_ghostty_first(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "osascript"
            assert "Ghostty" in call_args[0][0][2]

    def test_falls_back_to_iterm(self) -> None:
        with patch("subprocess.run") as mock_run:
            # First call (Ghostty) fails, second (iTerm) succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1),
                MagicMock(returncode=0),
            ]
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            assert mock_run.call_count == 2

    def test_falls_back_to_terminal_app(self) -> None:
        with patch("subprocess.run") as mock_run:
            # Ghostty and iTerm fail, Terminal.app succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1),
                MagicMock(returncode=1),
                MagicMock(returncode=0),
            ]
            result = activate_terminal_for_tty("ttys003")
            assert result is True
            assert mock_run.call_count == 3

    def test_returns_false_when_all_fail(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = activate_terminal_for_tty("ttys003")
            assert result is False

    def test_returns_false_on_exception(self) -> None:
        with patch("subprocess.run", side_effect=OSError("no osascript")):
            result = activate_terminal_for_tty("ttys003")
            assert result is False


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
