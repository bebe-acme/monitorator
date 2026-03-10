from __future__ import annotations

import json

import pytest


def _make_assistant_line(input_tokens: int = 1, cache_creation: int = 0, cache_read: int = 0) -> str:
    """Create a JSONL line mimicking a Claude assistant message with usage data."""
    return json.dumps({
        "parentUuid": "abc",
        "userType": "external",
        "cwd": "/tmp/test",
        "sessionId": "test-session",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "hello"}],
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "output_tokens": 100,
            },
        },
    })


def _make_user_line() -> str:
    """Create a JSONL line mimicking a user message (no usage)."""
    return json.dumps({
        "parentUuid": "abc",
        "userType": "external",
        "type": "user",
        "message": {"role": "user", "content": "hello"},
    })


class TestFormatTokens:
    def test_format_tokens_small(self) -> None:
        from monitorator.context_size import _format_tokens

        assert _format_tokens(0) == "0"
        assert _format_tokens(500) == "500"
        assert _format_tokens(999) == "999"

    def test_format_tokens_thousands(self) -> None:
        from monitorator.context_size import _format_tokens

        assert _format_tokens(5000) == "5k"
        assert _format_tokens(45000) == "45k"
        assert _format_tokens(999999) == "999k"

    def test_format_tokens_millions(self) -> None:
        from monitorator.context_size import _format_tokens

        assert _format_tokens(1500000) == "1.5M"
        assert _format_tokens(1000000) == "1.0M"
        assert _format_tokens(2300000) == "2.3M"


class TestMangleCwd:
    def test_mangle_cwd(self) -> None:
        from monitorator.context_size import mangle_cwd

        assert mangle_cwd("/Users/testuser/project") == "-Users-testuser-project"

    def test_mangle_cwd_with_underscores(self) -> None:
        from monitorator.context_size import mangle_cwd

        assert mangle_cwd("/Users/testuser/foo_bar") == "-Users-testuser-foo-bar"


class TestExtractUsageFromTail:
    def test_extracts_last_usage(self, tmp_path: object) -> None:
        from monitorator.context_size import _extract_usage_from_tail

        p = tmp_path  # type: ignore[assignment]
        jsonl = p / "test.jsonl"
        lines = [
            _make_assistant_line(input_tokens=1, cache_creation=500, cache_read=10000),
            _make_user_line(),
            _make_assistant_line(input_tokens=1, cache_creation=375, cache_read=106527),
        ]
        jsonl.write_text("\n".join(lines) + "\n")

        result = _extract_usage_from_tail(jsonl)
        assert result == 1 + 375 + 106527  # 106903

    def test_returns_none_for_empty_file(self, tmp_path: object) -> None:
        from monitorator.context_size import _extract_usage_from_tail

        p = tmp_path  # type: ignore[assignment]
        jsonl = p / "empty.jsonl"
        jsonl.write_text("")

        assert _extract_usage_from_tail(jsonl) is None

    def test_returns_none_for_no_usage(self, tmp_path: object) -> None:
        from monitorator.context_size import _extract_usage_from_tail

        p = tmp_path  # type: ignore[assignment]
        jsonl = p / "no_usage.jsonl"
        jsonl.write_text(_make_user_line() + "\n")

        assert _extract_usage_from_tail(jsonl) is None

    def test_skips_invalid_json(self, tmp_path: object) -> None:
        from monitorator.context_size import _extract_usage_from_tail

        p = tmp_path  # type: ignore[assignment]
        jsonl = p / "mixed.jsonl"
        lines = [
            _make_assistant_line(input_tokens=1, cache_creation=100, cache_read=5000),
            "this is not json",
            "{also broken",
        ]
        jsonl.write_text("\n".join(lines) + "\n")

        result = _extract_usage_from_tail(jsonl)
        assert result == 1 + 100 + 5000


class TestGetContextEstimate:
    def test_returns_formatted_estimate(self, tmp_path: object) -> None:
        from monitorator.context_size import get_context_estimate

        p = tmp_path  # type: ignore[assignment]
        cwd = "/Users/testuser/myproject"
        uuid = "abc12345-dead-beef-cafe-123456789abc"
        mangled = "-Users-testuser-myproject"
        project_dir = p / "projects" / mangled
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / f"{uuid}.jsonl"
        jsonl_file.write_text(
            _make_assistant_line(input_tokens=1, cache_creation=2000, cache_read=43000) + "\n"
        )

        result = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result == "45k"  # 1 + 2000 + 43000 = 45001

    def test_no_file_returns_none(self, tmp_path: object) -> None:
        from monitorator.context_size import get_context_estimate

        p = tmp_path  # type: ignore[assignment]
        result = get_context_estimate("/nonexistent/path", "no-such-uuid", claude_dir=p)
        assert result is None

    def test_caches_by_mtime(self, tmp_path: object) -> None:
        from monitorator.context_size import _CACHE, get_context_estimate

        _CACHE.clear()

        p = tmp_path  # type: ignore[assignment]
        cwd = "/Users/testuser/cached"
        uuid = "cached-uuid-1234-5678-abcdef012345"
        mangled = "-Users-testuser-cached"
        project_dir = p / "projects" / mangled
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / f"{uuid}.jsonl"
        jsonl_file.write_text(
            _make_assistant_line(input_tokens=1, cache_creation=100, cache_read=1900) + "\n"
        )

        result1 = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result1 == "2k"  # 2001 tokens
        assert uuid in _CACHE

        result2 = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result2 == "2k"

        _CACHE.clear()

    def test_empty_cwd_returns_none(self) -> None:
        from monitorator.context_size import get_context_estimate

        assert get_context_estimate("", "some-uuid") is None

    def test_empty_uuid_returns_none(self) -> None:
        from monitorator.context_size import get_context_estimate

        assert get_context_estimate("/some/path", "") is None

    def test_no_usage_in_file_returns_none(self, tmp_path: object) -> None:
        from monitorator.context_size import get_context_estimate

        p = tmp_path  # type: ignore[assignment]
        cwd = "/Users/testuser/nousage"
        uuid = "nousage-uuid-1234-5678-abcdef012345"
        mangled = "-Users-testuser-nousage"
        project_dir = p / "projects" / mangled
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / f"{uuid}.jsonl"
        jsonl_file.write_text(_make_user_line() + "\n")

        result = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result is None
