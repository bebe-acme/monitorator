from __future__ import annotations

import os
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


def _get_cwd_for_tty(tty: str) -> str | None:
    """Get the working directory of the process running on the given TTY."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,tty,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, OSError):
        return None

    # Find a PID on the target TTY
    target_pid: int | None = None
    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            proc_tty = parts[1]
        except (ValueError, IndexError):
            continue
        if proc_tty == tty:
            target_pid = pid
            break

    if target_pid is None:
        return None

    # Get cwd via lsof
    try:
        lsof_result = subprocess.run(
            ["lsof", "-p", str(target_pid), "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        in_cwd = False
        for line in lsof_result.stdout.strip().split("\n"):
            if line == "fcwd":
                in_cwd = True
                continue
            if in_cwd and line.startswith("n/"):
                return line[1:]
            if line.startswith("f"):
                in_cwd = False
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def _find_terminal_app_for_tty(tty: str) -> str | None:
    """Identify which terminal app owns a TTY by checking parent processes.

    Returns the app name ("Ghostty", "iTerm2", "Terminal") or None.
    """
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,tty,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, OSError):
        return None

    pid_to_ppid: dict[int, int] = {}
    pid_to_command: dict[int, str] = {}
    tty_pids: list[int] = []

    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            proc_tty = parts[2]
            command = parts[3]
        except (ValueError, IndexError):
            continue
        pid_to_ppid[pid] = ppid
        pid_to_command[pid] = command
        if proc_tty == tty:
            tty_pids.append(pid)

    for start_pid in tty_pids:
        current = start_pid
        for _ in range(10):
            parent = pid_to_ppid.get(current)
            if parent is None or parent <= 1:
                break
            cmd = pid_to_command.get(parent, "").lower()
            if "ghostty" in cmd:
                return "Ghostty"
            if "iterm2" in cmd or "iterm" in cmd:
                return "iTerm2"
            if "terminal.app" in cmd:
                return "Terminal"
            current = parent

    return None


def _activate_ghostty_tab(tty: str) -> bool:
    """Switch to the Ghostty tab containing the given TTY.

    Uses Ghostty's Window menu which lists all tabs by name (derived from
    the working directory). We match the tab name by finding the cwd for the
    target TTY and looking for a menu item containing that directory name.
    """
    # Get the cwd for this TTY to derive the tab name
    cwd = _get_cwd_for_tty(tty)
    if not cwd:
        return False
    dirname = os.path.basename(cwd.rstrip("/"))
    if not dirname:
        return False

    # Get all Window menu items from Ghostty
    try:
        menu_result = subprocess.run(
            ["osascript", "-e", '''
            tell application "System Events"
                tell process "Ghostty"
                    get name of every menu item of menu "Window" of menu bar 1
                end tell
            end tell
            '''],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if menu_result.returncode != 0:
            return False
    except (subprocess.TimeoutExpired, OSError):
        return False

    # Find the menu item that contains our directory name
    menu_items = [item.strip() for item in menu_result.stdout.strip().split(", ")]
    target_item: str | None = None
    for item in menu_items:
        # Tab names look like "🟡 [ dirname ]" or similar with emoji + brackets
        if dirname.lower() in item.lower():
            target_item = item
            break

    if target_item is None:
        return False

    # Escape quotes in the menu item name for AppleScript
    escaped_item = target_item.replace('"', '\\"')
    script = f'''
    tell application "System Events"
        tell process "Ghostty"
            click menu item "{escaped_item}" of menu "Window" of menu bar 1
        end tell
    end tell
    '''
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


def _activate_iterm2_tab(tty: str) -> bool:
    """Switch to the iTerm2 session containing the given TTY."""
    dev_tty = f"/dev/tty{tty}"
    script = f'''
    tell application "iTerm2"
        repeat with aWindow in windows
            repeat with aTab in tabs of aWindow
                repeat with aSession in sessions of aTab
                    if tty of aSession is "{dev_tty}" then
                        select aSession
                        set index of aWindow to 1
                        activate
                        return true
                    end if
                end repeat
            end repeat
        end repeat
    end tell
    return false
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.strip().lower()
    except (subprocess.TimeoutExpired, OSError):
        return False


def _activate_terminal_app_tab(tty: str) -> bool:
    """Switch to the Terminal.app tab containing the given TTY."""
    dev_tty = f"/dev/tty{tty}"
    script = f'''
    tell application "Terminal"
        repeat with aWindow in windows
            repeat with aTab in tabs of aWindow
                if tty of aTab is "{dev_tty}" then
                    set selected tab of aWindow to aTab
                    set index of aWindow to 1
                    activate
                    return true
                end if
            end repeat
        end repeat
    end tell
    return false
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.strip().lower()
    except (subprocess.TimeoutExpired, OSError):
        return False


def activate_terminal_for_tty(tty: str) -> bool:
    """Activate the terminal window/tab containing the given TTY.

    Detects which terminal app owns the TTY and uses app-specific tab
    switching: Ghostty via Window menu click, iTerm2 and Terminal.app
    via AppleScript session/tab matching by TTY path.
    """
    app = _find_terminal_app_for_tty(tty)

    if app == "Ghostty":
        return _activate_ghostty_tab(tty)
    if app == "iTerm2":
        return _activate_iterm2_tab(tty)
    if app == "Terminal":
        return _activate_terminal_app_tab(tty)

    # Unknown app: try each in order (best effort)
    if _activate_ghostty_tab(tty):
        return True
    if _activate_iterm2_tab(tty):
        return True
    if _activate_terminal_app_tab(tty):
        return True
    return False


def open_terminal_for_pid(pid: int) -> bool:
    """Find and activate the terminal window/tab for a Claude Code process."""
    tty = get_tty_for_pid(pid)
    if tty is None:
        return False
    return activate_terminal_for_tty(tty)
