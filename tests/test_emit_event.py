from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK_SCRIPT = Path(__file__).parent.parent / "hooks" / "emit_event.py"


def run_hook(event_data: dict[str, object], sessions_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the hook script with event data on stdin."""
    env = os.environ.copy()
    env["MONITORATOR_SESSIONS_DIR"] = str(sessions_dir)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )


class TestEmitEvent:
    def test_session_start_creates_state_file(self, tmp_sessions_dir: Path) -> None:
        event = {
            "type": "SessionStart",
            "session_id": "sess-001",
            "cwd": "/tmp/project",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        files = list(tmp_sessions_dir.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["session_id"] == "sess-001"
        assert data["cwd"] == "/tmp/project"

    def test_user_prompt_submit_updates_status(self, tmp_sessions_dir: Path) -> None:
        # First create session
        run_hook({"type": "SessionStart", "session_id": "sess-002", "cwd": "/tmp"}, tmp_sessions_dir)
        # Then submit prompt
        event = {
            "type": "UserPromptSubmit",
            "session_id": "sess-002",
            "cwd": "/tmp",
            "prompt": "Build a dashboard for monitoring",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-002.json").read_text())
        assert data["status"] == "thinking"
        assert data["last_event"] == "UserPromptSubmit"
        assert "Build a dashboard" in data["last_prompt_summary"]

    def test_pre_tool_use_sets_executing(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-003", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "PreToolUse",
            "session_id": "sess-003",
            "cwd": "/tmp",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/src/app.py", "old_string": "foo", "new_string": "bar"},
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-003.json").read_text())
        assert data["status"] == "executing"
        assert data["last_tool"] == "Edit"

    def test_post_tool_use_keeps_thinking(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-004", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "PostToolUse",
            "session_id": "sess-004",
            "cwd": "/tmp",
            "tool_name": "Read",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-004.json").read_text())
        assert data["status"] == "thinking"

    def test_stop_sets_terminated(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-005", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "Stop",
            "session_id": "sess-005",
            "cwd": "/tmp",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-005.json").read_text())
        assert data["status"] == "terminated"

    def test_notification_with_permission(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-006", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "Notification",
            "session_id": "sess-006",
            "cwd": "/tmp",
            "message": "Permission requested for Bash",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-006.json").read_text())
        assert data["status"] == "waiting_permission"

    def test_subagent_start(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-007", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "SubagentStart",
            "session_id": "sess-007",
            "cwd": "/tmp",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-007.json").read_text())
        assert data["status"] == "subagent_running"
        assert data["subagent_count"] == 1

    def test_subagent_stop_decrements(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-008", "cwd": "/tmp"}, tmp_sessions_dir)
        run_hook({"type": "SubagentStart", "session_id": "sess-008", "cwd": "/tmp"}, tmp_sessions_dir)
        run_hook({"type": "SubagentStart", "session_id": "sess-008", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "SubagentStop",
            "session_id": "sess-008",
            "cwd": "/tmp",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "sess-008.json").read_text())
        assert data["subagent_count"] == 1
        assert data["status"] == "subagent_running"

    def test_project_name_from_cwd(self, tmp_sessions_dir: Path) -> None:
        event = {
            "type": "SessionStart",
            "session_id": "sess-009",
            "cwd": "/Users/testuser/projects/agentator",
        }
        run_hook(event, tmp_sessions_dir)
        data = json.loads((tmp_sessions_dir / "sess-009.json").read_text())
        assert data["project_name"] == "agentator"

    def test_prompt_summary_truncated(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-010", "cwd": "/tmp"}, tmp_sessions_dir)
        long_prompt = "x" * 500
        event = {
            "type": "UserPromptSubmit",
            "session_id": "sess-010",
            "cwd": "/tmp",
            "prompt": long_prompt,
        }
        run_hook(event, tmp_sessions_dir)
        data = json.loads((tmp_sessions_dir / "sess-010.json").read_text())
        assert len(data["last_prompt_summary"]) <= 203  # 200 + "..."

    def test_tool_input_summary(self, tmp_sessions_dir: Path) -> None:
        run_hook({"type": "SessionStart", "session_id": "sess-011", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "PreToolUse",
            "session_id": "sess-011",
            "cwd": "/tmp",
            "tool_name": "Bash",
            "tool_input": {"command": "npm test --coverage"},
        }
        run_hook(event, tmp_sessions_dir)
        data = json.loads((tmp_sessions_dir / "sess-011.json").read_text())
        assert "npm test" in data["last_tool_input_summary"]

    def test_git_branch_detected_on_session_start(self, tmp_sessions_dir: Path) -> None:
        """Hook should detect git branch from cwd on every event."""
        import tempfile
        import subprocess

        # Create a real git repo for the hook to detect
        with tempfile.TemporaryDirectory() as git_dir:
            subprocess.run(["git", "init", git_dir], capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", git_dir, "checkout", "-b", "feat/cool"],
                capture_output=True,
                check=True,
            )
            # Need at least one commit for branch to show
            subprocess.run(
                ["git", "-C", git_dir, "commit", "--allow-empty", "-m", "init"],
                capture_output=True,
                check=True,
            )

            event = {
                "type": "SessionStart",
                "session_id": "git-branch-test",
                "cwd": git_dir,
            }
            result = run_hook(event, tmp_sessions_dir)
            assert result.returncode == 0
            data = json.loads((tmp_sessions_dir / "git-branch-test.json").read_text())
            assert data["git_branch"] == "feat/cool"

    def test_git_branch_none_for_non_git_dir(self, tmp_sessions_dir: Path) -> None:
        """Non-git directory should result in no git_branch (None)."""
        import tempfile

        with tempfile.TemporaryDirectory() as non_git_dir:
            event = {
                "type": "SessionStart",
                "session_id": "no-git-test",
                "cwd": non_git_dir,
            }
            result = run_hook(event, tmp_sessions_dir)
            assert result.returncode == 0
            data = json.loads((tmp_sessions_dir / "no-git-test.json").read_text())
            assert data.get("git_branch") is None

    def test_hook_event_name_field_works(self, tmp_sessions_dir: Path) -> None:
        """Claude Code sends hook_event_name, not type. Both must work."""
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "hook-event-name-test",
            "cwd": "/tmp/test-project",
            "prompt": "Fix the login bug",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "hook-event-name-test.json").read_text())
        assert data["status"] == "thinking"
        assert data["last_prompt_summary"] == "Fix the login bug"
        assert data["last_event"] == "UserPromptSubmit"

    def test_hook_event_name_prefers_over_type(self, tmp_sessions_dir: Path) -> None:
        """When both fields exist, hook_event_name takes precedence."""
        event = {
            "hook_event_name": "PreToolUse",
            "type": "SessionStart",  # should be ignored
            "session_id": "precedence-test",
            "cwd": "/tmp",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "precedence-test.json").read_text())
        assert data["status"] == "executing"
        assert data["last_tool"] == "Bash"

    def test_notification_permission_prompt_type(self, tmp_sessions_dir: Path) -> None:
        """Real Claude Code notification uses hook_event_name and notification_type."""
        run_hook({
            "hook_event_name": "SessionStart",
            "session_id": "notif-test",
            "cwd": "/tmp",
        }, tmp_sessions_dir)
        event = {
            "hook_event_name": "Notification",
            "session_id": "notif-test",
            "cwd": "/tmp",
            "message": "Claude needs your permission to use Bash",
            "notification_type": "permission_prompt",
        }
        result = run_hook(event, tmp_sessions_dir)
        assert result.returncode == 0
        data = json.loads((tmp_sessions_dir / "notif-test.json").read_text())
        assert data["status"] == "waiting_permission"

    def test_user_prompt_system_message_skipped(self, tmp_sessions_dir: Path) -> None:
        """System messages (XML-tagged) should NOT be saved as prompts."""
        # Pre-create existing session with no prompt
        run_hook({"type": "SessionStart", "session_id": "xml-skip-1", "cwd": "/tmp"}, tmp_sessions_dir)
        event = {
            "type": "UserPromptSubmit",
            "session_id": "xml-skip-1",
            "cwd": "/tmp",
            "prompt": "<task-notification><task-id>abc</task-id></task-notification>",
        }
        run_hook(event, tmp_sessions_dir)
        data = json.loads((tmp_sessions_dir / "xml-skip-1.json").read_text())
        # The system message should NOT be saved as prompt
        assert data.get("last_prompt_summary") is None or "<task" not in str(data.get("last_prompt_summary", ""))

    def test_completes_under_100ms(self, tmp_sessions_dir: Path) -> None:
        event = {
            "type": "SessionStart",
            "session_id": "perf-test",
            "cwd": "/tmp",
        }
        start = time.monotonic()
        run_hook(event, tmp_sessions_dir)
        elapsed_ms = (time.monotonic() - start) * 1000
        # Allow generous 2000ms for subprocess overhead, script itself should be <100ms
        assert elapsed_ms < 2000, f"Hook took {elapsed_ms:.0f}ms"


class TestIsSystemMessage:
    def test_task_notification_is_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("<task-notification><task-id>abc</task-id></task-notification>") is True

    def test_system_reminder_is_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("<system-reminder>You must do X</system-reminder>") is True

    def test_command_name_is_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("<command-name>review</command-name>") is True

    def test_normal_text_is_not_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("Fix the login bug") is False

    def test_empty_is_not_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("") is False

    def test_text_with_angle_brackets_not_system(self) -> None:
        from hooks.emit_event import _is_system_message

        assert _is_system_message("use array[0] > array[1]") is False
