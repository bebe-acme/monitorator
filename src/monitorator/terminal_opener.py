from __future__ import annotations

import subprocess


def get_tty_for_pid(pid: int) -> str | None:
    """Get the TTY device for a given PID via ps."""
    try:
        result = subprocess.run(
            ["ps", "-o", "tty=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        tty = result.stdout.strip()
        if not tty or tty == "?":
            return None
        return tty
    except (subprocess.TimeoutExpired, OSError):
        return None


_ACTIVATE_SCRIPTS: list[tuple[str, str]] = [
    (
        "Ghostty",
        """
        tell application "Ghostty"
            activate
        end tell
        """,
    ),
    (
        "iTerm",
        """
        tell application "iTerm2"
            activate
        end tell
        """,
    ),
    (
        "Terminal",
        """
        tell application "Terminal"
            activate
        end tell
        """,
    ),
]


def activate_terminal_for_tty(tty: str) -> bool:
    """Try to activate the terminal app window containing the given TTY.

    Tries Ghostty first, then iTerm2, then Terminal.app.
    """
    try:
        for _name, script in _ACTIVATE_SCRIPTS:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        return False
    except (subprocess.TimeoutExpired, OSError):
        return False


def open_terminal_for_pid(pid: int) -> bool:
    """Find and activate the terminal window for a Claude Code process."""
    tty = get_tty_for_pid(pid)
    if tty is None:
        return False
    return activate_terminal_for_tty(tty)
