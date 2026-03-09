from __future__ import annotations

import os

import pytest

from monitorator.pid_utils import is_pid_alive


class TestIsPidAlive:
    def test_current_process_is_alive(self) -> None:
        assert is_pid_alive(os.getpid()) is True

    def test_pid_1_is_alive(self) -> None:
        # PID 1 (init/launchd) should always exist
        # On macOS it may raise PermissionError, which means it's alive
        assert is_pid_alive(1) is True

    def test_nonexistent_pid_is_not_alive(self) -> None:
        # Use a very high PID that's unlikely to exist
        assert is_pid_alive(99999999) is False

    def test_zero_pid_is_not_alive(self) -> None:
        assert is_pid_alive(0) is False

    def test_negative_pid_is_not_alive(self) -> None:
        assert is_pid_alive(-1) is False
