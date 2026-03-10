from __future__ import annotations

import subprocess
import time

from monitorator.models import MergedSession, SessionStatus

ACTIVE_STATUSES = {SessionStatus.THINKING, SessionStatus.EXECUTING, SessionStatus.SUBAGENT_RUNNING}


class Notifier:
    def __init__(self, debounce_seconds: float = 30.0) -> None:
        self._debounce_seconds = debounce_seconds
        self._last_sent: dict[tuple[str, str], float] = {}

    def _osascript(self, message: str, sound: str | None = None) -> None:
        script = f'display notification "{message}" with title "Monitorator"'
        if sound:
            script += f' sound name "{sound}"'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )

    _SOUNDS: dict[str, str] = {
        "permission": "Glass",
        "session_finished": "Hero",
    }

    def notify(self, message: str, trigger: str, session_id: str) -> None:
        key = (session_id, trigger)
        now = time.time()

        if trigger != "permission":
            last = self._last_sent.get(key)
            if last is not None and (now - last) < self._debounce_seconds:
                return

        self._last_sent[key] = now
        try:
            self._osascript(message, sound=self._SOUNDS.get(trigger))
        except (OSError, subprocess.TimeoutExpired):
            pass

    def check_transitions(
        self,
        previous: dict[str, MergedSession],
        current: dict[str, MergedSession],
    ) -> None:
        for session_id, curr in current.items():
            prev = previous.get(session_id)
            project = curr.project_name

            # Session finished
            if curr.effective_status == SessionStatus.TERMINATED:
                if prev is None or prev.effective_status != SessionStatus.TERMINATED:
                    self.notify(f"Session finished: {project}", "session_finished", session_id)
                continue

            # Permission needed
            if curr.effective_status == SessionStatus.WAITING_PERMISSION:
                if prev is None or prev.effective_status != SessionStatus.WAITING_PERMISSION:
                    self.notify(f"Permission needed: {project}", "permission", session_id)
                continue

            # Session went idle after being active
            if curr.effective_status == SessionStatus.IDLE:
                if prev is not None and prev.effective_status in ACTIVE_STATUSES:
                    self.notify(f"Session idle: {project}", "idle", session_id)
