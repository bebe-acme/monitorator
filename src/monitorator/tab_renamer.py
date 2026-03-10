from __future__ import annotations

import os

from monitorator.labels import get_label
from monitorator.models import MergedSession, ProcessInfo, SessionStatus

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


def _cwds_related(a: str, b: str) -> bool:
    """Check if two paths are equal or one is a parent of the other."""
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _match_processes_to_sessions(
    processes: list[ProcessInfo],
    sessions: list[MergedSession],
) -> dict[int, MergedSession]:
    """Match processes to sessions with two-pass CWD matching.

    Pass 1: exact CWD match (most reliable).
    Pass 2: parent/child CWD match for leftovers (handles cases where the
    process CWD is a parent of the hook-reported CWD).

    Each process and session can only match once.
    """
    # Collect sessions with hook CWDs
    available: list[tuple[str, MergedSession]] = []
    for session in sessions:
        cwd = session.hook_state.cwd if session.hook_state else None
        if cwd:
            available.append((cwd.rstrip("/"), session))

    matched: dict[int, MergedSession] = {}
    matched_session_ids: set[str] = set()

    # Pass 1: exact CWD match
    for proc in processes:
        if not proc.tty or not proc.cwd:
            continue
        key = proc.cwd.rstrip("/")
        for cwd, session in available:
            if session.session_id in matched_session_ids:
                continue
            if cwd == key:
                matched[proc.pid] = session
                matched_session_ids.add(session.session_id)
                break

    # Pass 2: parent/child match for remaining processes
    for proc in processes:
        if proc.pid in matched or not proc.tty or not proc.cwd:
            continue
        key = proc.cwd.rstrip("/")
        for cwd, session in available:
            if session.session_id in matched_session_ids:
                continue
            if _cwds_related(key, cwd):
                matched[proc.pid] = session
                matched_session_ids.add(session.session_id)
                break

    return matched


def rename_tabs(
    processes: list[ProcessInfo],
    sessions: list[MergedSession],
) -> None:
    """Rename terminal tabs using two-pass CWD matching.

    Goes process-first: each process's own TTY gets renamed based on its CWD
    matched to the correct session. Exact match first, then parent/child for
    leftovers, so each process gets a distinct session.
    """
    pid_to_session = _match_processes_to_sessions(processes, sessions)

    for proc in processes:
        if not proc.tty or not proc.cwd:
            continue

        session = pid_to_session.get(proc.pid)

        if session:
            label = get_label(session.session_id)
            name = label if label else session.project_name
            status = session.effective_status
        else:
            name = proc.cwd.rstrip("/").rsplit("/", 1)[-1]
            status = SessionStatus.IDLE

        _write_osc_title(proc.tty, _build_title(name, status))
