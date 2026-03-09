from __future__ import annotations

import os

import pytest


class TestFormatTokens:
    def test_format_tokens_small(self) -> None:
        """Values < 1000 return raw number string."""
        from monitorator.context_size import _format_tokens

        assert _format_tokens(0) == "0"
        assert _format_tokens(500) == "500"
        assert _format_tokens(999) == "999"

    def test_format_tokens_thousands(self) -> None:
        """Values in thousands return Nk format."""
        from monitorator.context_size import _format_tokens

        assert _format_tokens(5000) == "5k"
        assert _format_tokens(45000) == "45k"
        assert _format_tokens(999999) == "999k"

    def test_format_tokens_millions(self) -> None:
        """Values >= 1M return N.NM format."""
        from monitorator.context_size import _format_tokens

        assert _format_tokens(1500000) == "1.5M"
        assert _format_tokens(1000000) == "1.0M"
        assert _format_tokens(2300000) == "2.3M"


class TestMangleCwd:
    def test_mangle_cwd(self) -> None:
        from monitorator.context_size import mangle_cwd

        assert mangle_cwd("/Users/beib/project") == "-Users-beib-project"

    def test_mangle_cwd_with_underscores(self) -> None:
        from monitorator.context_size import mangle_cwd

        assert mangle_cwd("/Users/beib/foo_bar") == "-Users-beib-foo-bar"


class TestGetContextEstimate:
    def test_get_context_estimate_returns_estimate(self, tmp_path: object) -> None:
        """Create a tmp JSONL file and verify estimate is returned."""
        from monitorator.context_size import get_context_estimate

        p = tmp_path  # type: ignore[assignment]
        # Create directory structure: projects/<mangled>/<uuid>.jsonl
        cwd = "/Users/beib/myproject"
        uuid = "abc12345-dead-beef-cafe-123456789abc"
        mangled = "-Users-beib-myproject"
        project_dir = p / "projects" / mangled
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / f"{uuid}.jsonl"
        # Write 20000 bytes = 5000 tokens at 4 bytes/token = "5k"
        jsonl_file.write_text("x" * 20000)

        result = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result == "5k"

    def test_get_context_estimate_no_file(self, tmp_path: object) -> None:
        """Nonexistent file returns None."""
        from monitorator.context_size import get_context_estimate

        p = tmp_path  # type: ignore[assignment]
        result = get_context_estimate("/nonexistent/path", "no-such-uuid", claude_dir=p)
        assert result is None

    def test_get_context_estimate_caches(self, tmp_path: object) -> None:
        """Second call with same mtime uses cache."""
        from monitorator.context_size import _CACHE, get_context_estimate

        _CACHE.clear()

        p = tmp_path  # type: ignore[assignment]
        cwd = "/Users/beib/cached"
        uuid = "cached-uuid-1234-5678-abcdef012345"
        mangled = "-Users-beib-cached"
        project_dir = p / "projects" / mangled
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / f"{uuid}.jsonl"
        jsonl_file.write_text("x" * 8000)  # 2000 tokens = "2k"

        # First call populates cache
        result1 = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result1 == "2k"
        assert uuid in _CACHE

        # Second call should use cache (same mtime)
        result2 = get_context_estimate(cwd, uuid, claude_dir=p)
        assert result2 == "2k"

        _CACHE.clear()

    def test_get_context_estimate_empty_cwd_returns_none(self) -> None:
        from monitorator.context_size import get_context_estimate

        assert get_context_estimate("", "some-uuid") is None

    def test_get_context_estimate_empty_uuid_returns_none(self) -> None:
        from monitorator.context_size import get_context_estimate

        assert get_context_estimate("/some/path", "") is None
