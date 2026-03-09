from __future__ import annotations

import json
import os

import pytest


class TestMangleCwd:
    def test_basic_path(self) -> None:
        from monitorator.session_prompt import mangle_cwd

        assert mangle_cwd("/Users/testuser/playground_testuser") == "-Users-testuser-playground-testuser"

    def test_underscores_replaced(self) -> None:
        from monitorator.session_prompt import mangle_cwd

        assert mangle_cwd("/Users/testuser/my_project") == "-Users-testuser-my-project"

    def test_no_leading_slash_doubled(self) -> None:
        from monitorator.session_prompt import mangle_cwd

        result = mangle_cwd("/tmp/proj")
        assert result == "-tmp-proj"
        assert not result.startswith("--")


class TestFindSessionJsonl:
    def test_finds_existing_jsonl(self, tmp_path: object) -> None:
        from monitorator.session_prompt import find_session_jsonl

        p = tmp_path  # type: ignore[assignment]
        mangled = "-Users-testuser-projects-agentator"
        proj_dir = p / "projects" / mangled
        proj_dir.mkdir(parents=True)
        uuid = "abc12345-dead-beef-cafe-123456789abc"
        (proj_dir / f"{uuid}.jsonl").write_text("{}\n")

        result = find_session_jsonl("/Users/testuser/projects/agentator", uuid, claude_dir=str(p))
        assert result is not None
        assert result.endswith(f"{uuid}.jsonl")

    def test_returns_none_when_missing(self, tmp_path: object) -> None:
        from monitorator.session_prompt import find_session_jsonl

        result = find_session_jsonl("/tmp/proj", "nonexistent-uuid-1234-5678-9abc-def0", claude_dir=str(tmp_path))
        assert result is None


class TestReadLastUserPrompt:
    def _make_jsonl(self, tmp_path: object, lines: list[dict[str, object]]) -> str:
        p = tmp_path  # type: ignore[assignment]
        path = str(p / "session.jsonl")
        with open(path, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return path

    def test_finds_last_user_text_prompt(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "First prompt"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Response"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "Second prompt"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Another response"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Second prompt"

    def test_skips_tool_result(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Real prompt"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "result data"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Real prompt"

    def test_skips_local_command_tag(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Real prompt"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "<local-command>something</local-command>"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Real prompt"

    def test_skips_command_name_tag(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Real prompt"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "<command-name>commit</command-name>"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Real prompt"

    def test_skips_task_notification_tag(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Fix the login bug"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "<task-notification>\n<task-id>ae19cf2</task-id>\n</task-notification>"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Fix the login bug"

    def test_skips_system_reminder_tag(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Build the dashboard"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "<system-reminder>Some reminder text</system-reminder>"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Build the dashboard"

    def test_skips_any_xml_tag_message(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "user", "message": {"content": [{"type": "text", "text": "Real user prompt"}]}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "<some-internal-tag>data</some-internal-tag>"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result == "Real user prompt"

    def test_returns_none_for_no_user_messages(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        lines = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}},
        ]
        path = self._make_jsonl(tmp_path, lines)
        result = read_last_user_prompt(path)
        assert result is None

    def test_returns_none_for_missing_file(self) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        result = read_last_user_prompt("/nonexistent/path.jsonl")
        assert result is None

    def test_handles_malformed_json_lines(self, tmp_path: object) -> None:
        from monitorator.session_prompt import read_last_user_prompt

        p = tmp_path  # type: ignore[assignment]
        path = str(p / "session.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "Good prompt"}]}}) + "\n")
            f.write("not valid json\n")
        result = read_last_user_prompt(path)
        assert result == "Good prompt"


class TestGetSessionPrompt:
    def test_returns_cached_result(self, tmp_path: object) -> None:
        from monitorator.session_prompt import _CACHE, find_session_jsonl, get_session_prompt

        _CACHE.clear()
        p = tmp_path  # type: ignore[assignment]
        mangled = "-tmp-proj"
        proj_dir = p / "projects" / mangled
        proj_dir.mkdir(parents=True)
        uuid = "abc12345-dead-beef-cafe-123456789abc"
        jsonl = proj_dir / f"{uuid}.jsonl"
        jsonl.write_text(
            json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "Hello world"}]}}) + "\n"
        )

        result1 = get_session_prompt("/tmp/proj", uuid, claude_dir=str(p))
        assert result1 == "Hello world"

        # Second call should use cache (even if file is gone)
        jsonl.unlink()
        result2 = get_session_prompt("/tmp/proj", uuid, claude_dir=str(p))
        assert result2 == "Hello world"

        _CACHE.clear()

    def test_returns_none_when_no_jsonl(self, tmp_path: object) -> None:
        from monitorator.session_prompt import _CACHE, get_session_prompt

        _CACHE.clear()
        result = get_session_prompt("/tmp/proj", "no-such-uuid-1234-5678-9abc-def0", claude_dir=str(tmp_path))
        assert result is None
        _CACHE.clear()
