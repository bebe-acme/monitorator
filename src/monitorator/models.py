from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_PERMISSION = "waiting_permission"
    SUBAGENT_RUNNING = "subagent_running"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


@dataclass
class SessionState:
    session_id: str
    cwd: str
    project_name: Optional[str] = None
    status: SessionStatus = SessionStatus.UNKNOWN
    last_event: Optional[str] = None
    timestamp: Optional[float] = None
    updated_at: Optional[float] = None
    git_branch: Optional[str] = None
    last_tool: Optional[str] = None
    last_tool_input_summary: Optional[str] = None
    last_prompt_summary: Optional[str] = None
    subagent_count: int = 0
    permission_mode: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "cwd": self.cwd,
            "project_name": self.project_name,
            "status": self.status.value,
            "last_event": self.last_event,
            "timestamp": self.timestamp,
            "updated_at": self.updated_at,
            "git_branch": self.git_branch,
            "last_tool": self.last_tool,
            "last_tool_input_summary": self.last_tool_input_summary,
            "last_prompt_summary": self.last_prompt_summary,
            "subagent_count": self.subagent_count,
            "permission_mode": self.permission_mode,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> SessionState:
        status_str = d.get("status", "unknown")
        try:
            status = SessionStatus(str(status_str))
        except ValueError:
            status = SessionStatus.UNKNOWN

        return cls(
            session_id=str(d["session_id"]),
            cwd=str(d["cwd"]),
            project_name=d.get("project_name") if d.get("project_name") is not None else None,  # type: ignore[arg-type]
            status=status,
            last_event=d.get("last_event") if d.get("last_event") is not None else None,  # type: ignore[arg-type]
            timestamp=float(d["timestamp"]) if d.get("timestamp") is not None else None,
            updated_at=float(d["updated_at"]) if d.get("updated_at") is not None else None,
            git_branch=d.get("git_branch") if d.get("git_branch") is not None else None,  # type: ignore[arg-type]
            last_tool=d.get("last_tool") if d.get("last_tool") is not None else None,  # type: ignore[arg-type]
            last_tool_input_summary=d.get("last_tool_input_summary") if d.get("last_tool_input_summary") is not None else None,  # type: ignore[arg-type]
            last_prompt_summary=d.get("last_prompt_summary") if d.get("last_prompt_summary") is not None else None,  # type: ignore[arg-type]
            subagent_count=int(d.get("subagent_count", 0)),  # type: ignore[arg-type]
            permission_mode=d.get("permission_mode") if d.get("permission_mode") is not None else None,  # type: ignore[arg-type]
        )


@dataclass
class ProcessInfo:
    pid: int
    cpu_percent: float
    elapsed_seconds: int
    cwd: str
    command: str
    session_uuid: Optional[str] = None


@dataclass
class MergedSession:
    session_id: str
    hook_state: Optional[SessionState]
    process_info: Optional[ProcessInfo]
    effective_status: SessionStatus
    is_stale: bool

    @property
    def last_interaction_time(self) -> float:
        """Unix timestamp of last interaction. Higher = more recent."""
        if self.hook_state:
            if self.hook_state.updated_at:
                return self.hook_state.updated_at
            if self.hook_state.timestamp:
                return self.hook_state.timestamp
        if self.process_info:
            return time.time() - self.process_info.elapsed_seconds
        return 0.0

    @property
    def project_name(self) -> str:
        if self.hook_state and self.hook_state.project_name:
            return self.hook_state.project_name
        cwd = None
        if self.hook_state:
            cwd = self.hook_state.cwd
        elif self.process_info:
            cwd = self.process_info.cwd
        if cwd:
            return cwd.rstrip("/").rsplit("/", 1)[-1]
        return "unknown"
