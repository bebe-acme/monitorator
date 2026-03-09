from __future__ import annotations

import time
from collections import defaultdict

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus

STALE_THRESHOLD_SECONDS = 300  # 5 minutes
CPU_OVERRIDE_THRESHOLD = 10.0  # percent — CPU must exceed this to go IDLE→THINKING
CPU_DROP_THRESHOLD = 3.0  # percent — CPU must drop below this to go THINKING→IDLE
STATUS_HOLD_SECONDS = 15.0  # seconds — hold active status to prevent flicker
HOOKLESS_STALE_ELAPSED = 3600  # 1 hour — hookless process idle this long = stale
HOOKLESS_STALE_CPU = 1.0  # percent — below this CPU, hookless process considered idle

_ACTIVE_STATUSES = {SessionStatus.THINKING, SessionStatus.EXECUTING, SessionStatus.SUBAGENT_RUNNING}


class SessionMerger:
    def __init__(self) -> None:
        self._prev_status: dict[str, SessionStatus] = {}
        self._prev_active_time: dict[str, float] = {}

    def merge(
        self,
        hook_states: list[SessionState],
        processes: list[ProcessInfo],
    ) -> list[MergedSession]:
        now = time.time()
        results: list[MergedSession] = []
        matched_process_indices: set[int] = set()

        # Sort by recency so active sessions get matched to processes first,
        # preventing zombie sessions from stealing process matches
        sorted_states = sorted(
            hook_states,
            key=lambda s: s.updated_at or s.timestamp or 0,
            reverse=True,
        )

        for state in sorted_states:
            proc = self._find_matching_process(state, processes, matched_process_indices)
            effective_status = state.status
            is_stale = self._check_stale(state, proc, now)

            # Track when session was last in an active state
            if effective_status in _ACTIVE_STATUSES:
                self._prev_active_time[state.session_id] = state.updated_at or now

            if proc is not None and effective_status == SessionStatus.IDLE:
                # Time-based hold: if recently active, keep THINKING to prevent flicker
                last_active = self._prev_active_time.get(state.session_id, 0)
                recently_active = (now - last_active) < STATUS_HOLD_SECONDS
                prev = self._prev_status.get(state.session_id)

                if prev in _ACTIVE_STATUSES and recently_active:
                    effective_status = SessionStatus.THINKING
                elif prev == SessionStatus.THINKING and proc.cpu_percent > CPU_DROP_THRESHOLD:
                    effective_status = SessionStatus.THINKING
                elif proc.cpu_percent > CPU_OVERRIDE_THRESHOLD:
                    effective_status = SessionStatus.THINKING

            self._prev_status[state.session_id] = effective_status
            results.append(MergedSession(
                session_id=state.session_id,
                hook_state=state,
                process_info=proc,
                effective_status=effective_status,
                is_stale=is_stale,
            ))

        # Add unmatched processes — each is a real Claude session
        for i, proc in enumerate(processes):
            if i in matched_process_indices:
                continue
            if not proc.cwd:
                continue
            session_id = f"proc-{proc.pid}"
            prev = self._prev_status.get(session_id)
            if prev == SessionStatus.THINKING and proc.cpu_percent > CPU_DROP_THRESHOLD:
                effective_status = SessionStatus.THINKING
            elif proc.cpu_percent > CPU_OVERRIDE_THRESHOLD:
                effective_status = SessionStatus.THINKING
            else:
                effective_status = SessionStatus.IDLE
            is_stale = (
                proc.cpu_percent < HOOKLESS_STALE_CPU
                and proc.elapsed_seconds > HOOKLESS_STALE_ELAPSED
            )
            self._prev_status[session_id] = effective_status
            results.append(MergedSession(
                session_id=session_id,
                hook_state=None,
                process_info=proc,
                effective_status=effective_status,
                is_stale=is_stale,
            ))

        return self._dedup_same_cwd(results)

    @staticmethod
    def _dedup_same_cwd(results: list[MergedSession]) -> list[MergedSession]:
        """Deduplicate sessions sharing the same cwd.

        When multiple sessions share a cwd (e.g. after permission prompt restart),
        keep only the most recently updated one. All others are marked stale.
        """
        cwd_groups: dict[str, list[MergedSession]] = defaultdict(list)
        no_cwd: list[MergedSession] = []

        for r in results:
            cwd = r.hook_state.cwd if r.hook_state else (r.process_info.cwd if r.process_info else None)
            if cwd:
                cwd_groups[cwd.rstrip("/")].append(r)
            else:
                no_cwd.append(r)

        deduped: list[MergedSession] = list(no_cwd)
        for _cwd, sessions in cwd_groups.items():
            if len(sessions) <= 1:
                deduped.extend(sessions)
                continue

            # Sort by recency — keep only the most recently updated session
            sessions.sort(
                key=lambda s: (s.hook_state.updated_at or 0) if s.hook_state else 0,
                reverse=True,
            )
            deduped.append(sessions[0])
            for s in sessions[1:]:
                s.is_stale = True
                deduped.append(s)

        return deduped

    @staticmethod
    def _cwds_related(cwd_a: str, cwd_b: str) -> bool:
        """Check if two paths are equal or one is a parent of the other."""
        # Normalize trailing slashes
        a = cwd_a.rstrip("/")
        b = cwd_b.rstrip("/")
        if a == b:
            return True
        # Check parent/child relationship (must be a path boundary)
        return a.startswith(b + "/") or b.startswith(a + "/")

    def _find_matching_process(
        self,
        state: SessionState,
        processes: list[ProcessInfo],
        matched: set[int],
    ) -> ProcessInfo | None:
        for i, proc in enumerate(processes):
            if i in matched:
                continue
            if proc.cwd and state.cwd and self._cwds_related(proc.cwd, state.cwd):
                matched.add(i)
                return proc
        return None

    def _check_stale(
        self,
        state: SessionState,
        proc: ProcessInfo | None,
        now: float,
    ) -> bool:
        if proc is not None:
            return False
        updated = state.updated_at or state.timestamp or 0
        return (now - updated) > STALE_THRESHOLD_SECONDS
