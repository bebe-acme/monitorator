from __future__ import annotations

import os
import re
import subprocess

# Known terminal keywords (in command path, lowercase) → AppleScript app name.
# Checked against the full command string so paths like
# "/Applications/Warp.app/Contents/MacOS/stable" match via "warp".
_TERMINAL_APPS: dict[str, str] = {
    "ghostty": "Ghostty",
    "iterm2": "iTerm2",
    "iterm": "iTerm2",
    "/terminal.app/": "Terminal",
    "warp": "Warp",
    "kitty": "kitty",
    "alacritty": "Alacritty",
    "wezterm": "WezTerm",
    "hyper": "Hyper",
    "tabby": "Tabby",
    "rio": "Rio",
}

# Pattern to extract app name from a macOS .app bundle path.
# e.g. "/Applications/Foo Bar.app/Contents/MacOS/bin" → "Foo Bar"
_APP_BUNDLE_RE = re.compile(r"/([^/]+)\.app/", re.IGNORECASE)


def _find_terminal_app_for_pid(pid: int) -> str | None:
    """Walk up the process tree from PID to find the owning terminal app.

    First checks against known terminal names. If none match, falls back to
    extracting the app name from any macOS .app bundle path in an ancestor's
    command — this handles terminals we don't explicitly list.
    """
    current = pid
    ancestors: list[str] = []  # collected for fallback

    for _ in range(10):
        try:
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(current)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            ppid_str = result.stdout.strip()
            if not ppid_str:
                break
            ppid = int(ppid_str)
            if ppid <= 1:
                break

            result = subprocess.run(
                ["ps", "-o", "command=", "-p", str(ppid)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            command = result.stdout.strip()
            command_lower = command.lower()
            ancestors.append(command)

            # Check known terminals
            for key, app_name in _TERMINAL_APPS.items():
                if key in command_lower:
                    return app_name

            current = ppid
        except (ValueError, subprocess.TimeoutExpired, OSError):
            break

    # Fallback: find any .app bundle in ancestor commands
    for cmd in ancestors:
        match = _APP_BUNDLE_RE.search(cmd)
        if match:
            return match.group(1)

    return None


def _activate_iterm2_tab(tty: str) -> bool:
    """Focus the specific iTerm2 tab containing the given TTY."""
    script = f'''
        tell application "iTerm2"
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        if tty of s is "/dev/{tty}" then
                            select t
                            set index of w to 1
                            activate
                            return true
                        end if
                    end repeat
                end repeat
            end repeat
            activate
        end tell
    '''
    return _run_osascript(script)


def _activate_terminal_tab(tty: str) -> bool:
    """Focus the specific Terminal.app tab containing the given TTY."""
    script = f'''
        tell application "Terminal"
            repeat with w in windows
                repeat with t in tabs of w
                    if tty of t is "/dev/{tty}" then
                        set selected tab of w to t
                        set index of w to 1
                        activate
                        return true
                    end if
                end repeat
            end repeat
            activate
        end tell
    '''
    return _run_osascript(script)


def _activate_warp_tab(tab_title: str) -> bool:
    """Switch to a Warp tab by cycling through Cmd+1..9 and matching window title.

    Warp doesn't expose tabs via accessibility, but Cmd+number switches tabs
    and the window title reflects the active tab's OSC-set title. We cycle
    through tabs until the window title contains the target name.
    """
    # Escape double quotes for AppleScript string
    safe_title = tab_title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
        tell application "Warp" to activate
        delay 0.1
        tell application "System Events"
            tell process "stable"
                set origTitle to name of window 1
                repeat with i from 1 to 9
                    keystroke (i as text) using command down
                    delay 0.1
                    set curTitle to name of window 1
                    if curTitle contains "{safe_title}" then
                        return true
                    end if
                end repeat
            end tell
        end tell
    '''
    return _run_osascript(script)


def _badge_and_activate(app_name: str, tty: str | None) -> bool:
    """Ring the bell on the TTY to badge the tab, then activate the app.

    Fallback for terminals that don't expose tab-level APIs (Ghostty,
    kitty, etc.). The bell causes most terminals to highlight/badge the
    tab so the user can find it.
    """
    if tty:
        try:
            fd = os.open(f"/dev/{tty}", os.O_WRONLY | os.O_NOCTTY)
            try:
                os.write(fd, b"\a")
            finally:
                os.close(fd)
        except OSError:
            pass
    return _run_osascript(f'tell application "{app_name}" to activate')


def _run_osascript(script: str) -> bool:
    """Run an AppleScript and return whether it succeeded."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def open_terminal_for_pid(
    pid: int,
    tty: str | None = None,
    tab_title: str | None = None,
) -> bool:
    """Find and activate the terminal window for a Claude Code process.

    Walks the process tree to detect the actual terminal app, then activates
    it. For iTerm2 and Terminal.app, focuses the specific tab by TTY. For
    Warp, cycles through tabs matching by window title.
    """
    app = _find_terminal_app_for_pid(pid)
    if app is None:
        return False

    # Terminals that support tab-level focusing
    if tty:
        if app == "iTerm2":
            return _activate_iterm2_tab(tty)
        if app == "Terminal":
            return _activate_terminal_tab(tty)
    if app == "Warp" and tab_title:
        return _activate_warp_tab(tab_title)

    # Fallback: bell to badge the tab + activate
    return _badge_and_activate(app, tty)
