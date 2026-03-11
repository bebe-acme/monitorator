from __future__ import annotations

import os

from monitorator.labels import get_label
from monitorator.models import MergedSession, SessionStatus

# Colored dot prefixes for non-running states.
# Running states (thinking/executing/subagent) get no prefix — that's the
# expected state so we keep the tab clean.
_STATUS_DOT: dict[SessionStatus, str] = {
    SessionStatus.IDLE: "\U0001f7e1",              # 🟡
    SessionStatus.WAITING_PERMISSION: "\U0001f534",  # 🔴
}


def _build_title(name: str, status: SessionStatus) -> str:
    """Build tab title: optional status dot + [ name ]."""
    dot = _STATUS_DOT.get(status, "")
    if dot:
        return f"{dot} [ {name} ]"
    return f"[ {name} ]"


def _write_osc_title(tty: str, title: str) -> bool:
    """Write an OSC escape sequence to set the terminal tab title.

    Uses OSC 0 (set window+tab title): \\033]0;title\\007
    """
    dev_path = f"/dev/{tty}"
    try:
        fd = os.open(dev_path, os.O_WRONLY | os.O_NOCTTY)
        try:
            os.write(fd, f"\033]0;{title}\007".encode())
            return True
        finally:
            os.close(fd)
    except OSError:
        return False


def rename_tabs(sessions: list[MergedSession]) -> None:
    """Rename terminal tabs using the merger's established process links.

    Each MergedSession already has process_info linked by the merger.
    We just write the session name to that process's TTY — no re-matching.
    """
    for session in sessions:
        proc = session.process_info
        if not proc or not proc.tty:
            continue

        label = get_label(session.session_id)
        name = label if label else session.project_name
        _write_osc_title(proc.tty, _build_title(name, session.effective_status))
