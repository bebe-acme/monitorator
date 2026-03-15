#!/usr/bin/env python3
"""
Monitorator hook for Claude Code.
Reads event JSON from stdin, writes session state to ~/.monitorator/sessions/.

STDLIB ONLY - no third-party imports. Must complete <100ms.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def get_sessions_dir() -> Path:
    override = os.environ.get("MONITORATOR_SESSIONS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".monitorator" / "sessions"


def read_existing(sessions_dir: Path, session_id: str) -> dict[str, object]:
    path = sessions_dir / f"{session_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _is_system_message(text: str) -> bool:
    """Check if text looks like a system/internal message (starts with XML tag)."""
    stripped = text.strip()
    if not stripped:
        return False
    return bool(re.match(r'^\s*<[a-zA-Z][\w-]*[ >/]', stripped))


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def summarize_tool_input(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return str(tool_input)[:200]
    parts: list[str] = []
    for key, val in tool_input.items():
        val_str = str(val)
        if len(val_str) > 80:
            val_str = val_str[:80] + "..."
        parts.append(f"{key}: {val_str}")
    return truncate(", ".join(parts))


def detect_worktree_info(cwd: str) -> tuple[str, str | None]:
    """Detect if cwd is inside a worktree directory.

    Checks for:
    - /.claude/worktrees/<name>  (built-in Claude Code worktrees)
    - /.worktrees/<name>         (Superpowers plugin / user convention)

    Returns (project_name, worktree_name) where worktree_name is None if not a worktree.
    """
    if not cwd:
        return ("unknown", None)
    cleaned = cwd.rstrip("/")
    for marker in ("/.claude/worktrees/", "/.worktrees/"):
        idx = cleaned.find(marker)
        if idx != -1:
            project = cleaned[:idx].rsplit("/", 1)[-1] or "unknown"
            worktree = cleaned[idx + len(marker):].split("/", 1)[0]
            return (project, worktree if worktree else None)
    return (cleaned.rsplit("/", 1)[-1] or "unknown", None)



def detect_git_branch(cwd: str) -> str | None:
    """Detect the current git branch for a directory. Returns None if not a git repo."""
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch else None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def atomic_write(sessions_dir: Path, session_id: str, data: dict[str, object]) -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    target = sessions_dir / f"{session_id}.json"
    fd, tmp_path = tempfile.mkstemp(dir=sessions_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return

    event_type: str = event.get("hook_event_name", "") or event.get("type", "")
    session_id: str = event.get("session_id", "")
    cwd: str = event.get("cwd", "")

    if not session_id:
        return

    sessions_dir = get_sessions_dir()
    now = time.time()

    existing = read_existing(sessions_dir, session_id)

    effective_cwd_val = cwd or str(existing.get("cwd", ""))
    wt_project, wt_name = detect_worktree_info(effective_cwd_val)

    state: dict[str, object] = {
        "session_id": session_id,
        "cwd": effective_cwd_val,
        "project_name": wt_project,
        "status": existing.get("status", "unknown"),
        "last_event": event_type,
        "timestamp": existing.get("timestamp", now),
        "updated_at": now,
        "git_branch": existing.get("git_branch"),
        "last_tool": existing.get("last_tool"),
        "last_tool_input_summary": existing.get("last_tool_input_summary"),
        "last_prompt_summary": existing.get("last_prompt_summary"),
        "subagent_count": int(existing.get("subagent_count", 0)),
        "permission_mode": existing.get("permission_mode"),
        "is_worktree": wt_name is not None,
        "worktree_name": wt_name,
    }

    # Detect git branch on every event
    if effective_cwd_val:
        branch = detect_git_branch(effective_cwd_val)
        if branch:
            state["git_branch"] = branch

    if event_type == "SessionStart":
        state["status"] = "idle"
        state["timestamp"] = now

    elif event_type == "UserPromptSubmit":
        state["status"] = "thinking"
        prompt = str(event.get("prompt", ""))
        if prompt and not _is_system_message(prompt):
            state["last_prompt_summary"] = truncate(prompt)

    elif event_type == "PreToolUse":
        state["status"] = "executing"
        tool_name = event.get("tool_name", "")
        state["last_tool"] = tool_name
        tool_input = event.get("tool_input")
        if tool_input:
            state["last_tool_input_summary"] = summarize_tool_input(tool_input)

    elif event_type == "PostToolUse":
        state["status"] = "thinking"

    elif event_type == "Stop":
        state["status"] = "idle"

    elif event_type == "SessionEnd":
        state["status"] = "terminated"

    elif event_type == "Notification":
        notification_type = event.get("notification_type", "")
        message = str(event.get("message", ""))
        if notification_type == "permission_prompt" or "permission" in message.lower():
            state["status"] = "waiting_permission"

    elif event_type == "SubagentStart":
        count = int(state.get("subagent_count", 0)) + 1
        state["subagent_count"] = count
        state["status"] = "subagent_running"

    elif event_type == "SubagentStop":
        count = max(0, int(state.get("subagent_count", 0)) - 1)
        state["subagent_count"] = count
        if count > 0:
            state["status"] = "subagent_running"
        else:
            state["status"] = "thinking"

    atomic_write(sessions_dir, session_id, state)


if __name__ == "__main__":
    main()
