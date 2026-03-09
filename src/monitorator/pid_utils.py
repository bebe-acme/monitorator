from __future__ import annotations

import os


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running.

    Uses os.kill(pid, 0) which doesn't actually send a signal
    but checks if the process exists and we have permission.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission -- it's alive
        return True
    except OSError:
        return False
