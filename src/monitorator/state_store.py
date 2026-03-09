from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from monitorator.models import SessionState, SessionStatus


class StateStore:
    def __init__(self, sessions_dir: Path) -> None:
        self._dir = sessions_dir

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def write(self, state: SessionState) -> None:
        self._ensure_dir()
        target = self._path_for(state.session_id)
        fd, tmp_path = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state.to_dict(), f)
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def read(self, session_id: str) -> SessionState | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return SessionState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def list_all(self) -> list[SessionState]:
        if not self._dir.exists():
            return []
        results: list[SessionState] = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                results.append(SessionState.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return results

    def delete(self, session_id: str) -> None:
        path = self._path_for(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def mark_dead_pids_terminated(self, active_pids: set[int]) -> list[str]:
        """Mark sessions as terminated if their activity suggests they're dead.

        Sessions that haven't been updated in > 5 minutes and have an active
        status (THINKING/EXECUTING) are likely from dead processes.
        """
        marked: list[str] = []
        now = time.time()
        active_statuses = {
            SessionStatus.THINKING,
            SessionStatus.EXECUTING,
            SessionStatus.SUBAGENT_RUNNING,
            SessionStatus.WAITING_PERMISSION,
        }

        for state in self.list_all():
            if state.status not in active_statuses:
                continue
            updated = state.updated_at or state.timestamp or 0
            # If no update for > 5 min and status is "active", likely dead
            if now - updated > 300:
                state.status = SessionStatus.TERMINATED
                self.write(state)
                marked.append(state.session_id)

        return marked

    def cleanup_stale(
        self,
        max_age_seconds: int = 3600,
        active_cwds: set[str] | None = None,
    ) -> list[str]:
        now = time.time()
        removed: list[str] = []
        for state in self.list_all():
            if active_cwds and state.cwd in active_cwds and state.status != SessionStatus.TERMINATED:
                continue
            updated = state.updated_at or state.timestamp or 0
            if now - updated > max_age_seconds:
                self.delete(state.session_id)
                removed.append(state.session_id)
        return removed
