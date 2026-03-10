from __future__ import annotations

from unittest.mock import patch

import pytest

from monitorator.models import ProcessInfo
from monitorator.scanner import ProcessScanner, parse_ps_output, parse_elapsed


class TestParseElapsed:
    def test_minutes_seconds(self) -> None:
        assert parse_elapsed("05:30") == 330

    def test_hours_minutes_seconds(self) -> None:
        assert parse_elapsed("01:05:30") == 3930

    def test_days_hours(self) -> None:
        # ps format: "2-03:15:00"
        assert parse_elapsed("2-03:15:00") == 2 * 86400 + 3 * 3600 + 15 * 60

    def test_seconds_only(self) -> None:
        assert parse_elapsed("00:45") == 45

    def test_invalid(self) -> None:
        assert parse_elapsed("garbage") == 0


class TestParsePsOutput:
    def test_typical_output(self) -> None:
        output = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "12345  21.3     05:30 node /path/to/claude\n"
            "12346   0.5     10:00 node /path/to/claude\n"
        )
        results = parse_ps_output(output)
        assert len(results) == 2
        assert results[0]["pid"] == 12345
        assert results[0]["cpu"] == 21.3
        assert results[0]["elapsed_str"] == "05:30"

    def test_empty_output(self) -> None:
        assert parse_ps_output("") == []
        assert parse_ps_output("  PID  %CPU   ELAPSED COMMAND\n") == []

    def test_malformed_line_skipped(self) -> None:
        output = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "not a valid line\n"
            "12345  21.3     05:30 node claude\n"
        )
        results = parse_ps_output(output)
        assert len(results) == 1


class TestProcessScanner:
    def test_scan_returns_process_info_list(self) -> None:
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "12345  21.3     05:30 node /Users/testuser/.claude/local/claude\n"
        )
        mock_lsof = "p12345\nf4\nn/Users/testuser/projects/agentator\n"

        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=mock_lsof),
        ):
            results = scanner.scan()

        assert len(results) == 1
        info = results[0]
        assert isinstance(info, ProcessInfo)
        assert info.pid == 12345
        assert info.cpu_percent == 21.3
        assert info.elapsed_seconds == 330

    def test_scan_empty_when_no_processes(self) -> None:
        scanner = ProcessScanner()
        with patch.object(scanner, "_run_ps", return_value="  PID  %CPU   ELAPSED COMMAND\n"):
            results = scanner.scan()
        assert results == []

    def test_scan_handles_ps_failure(self) -> None:
        scanner = ProcessScanner()
        with patch.object(scanner, "_run_ps", side_effect=OSError("no ps")):
            results = scanner.scan()
        assert results == []

    def test_excludes_chrome_native_host(self) -> None:
        """Chrome extension native host should not be detected as Claude."""
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "55555  0.1     10:00 /Users/testuser/.claude/local/claude --chrome-native-host\n"
        )
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=""),
        ):
            results = scanner.scan()
        assert len(results) == 0

    def test_includes_real_claude_process(self) -> None:
        """Real Claude Code process should be detected."""
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "12345  21.3     05:30 /Users/testuser/.claude/local/claude\n"
        )
        mock_lsof = "p12345\nn/Users/testuser/projects/agentator\n"
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=mock_lsof),
        ):
            results = scanner.scan()
        assert len(results) == 1

    def test_includes_claude_code_binary(self) -> None:
        """Binary named claude-code should be detected."""
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "12345  5.0     02:00 /usr/local/bin/claude-code --some-flag\n"
        )
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=""),
        ):
            results = scanner.scan()
        assert len(results) == 1

    def test_excludes_claude_desktop_app(self) -> None:
        """Claude Desktop app processes should not be detected as Claude CLI."""
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "44444  0.0  4-02:15:00 /Applications/Claude.app/Contents/MacOS/Claude\n"
            "44445  0.0  4-02:15:00 /Applications/Claude.app/Contents/Frameworks/Claude Helper (GPU).app/Contents/MacOS/Claude Helper (GPU) --type=gpu-process\n"
            "44446  0.0  4-02:15:00 /Applications/Claude.app/Contents/Frameworks/Claude Helper (Renderer).app/Contents/MacOS/Claude Helper (Renderer) --type=renderer\n"
        )
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=""),
        ):
            results = scanner.scan()
        assert len(results) == 0

    def test_excludes_unrelated_claude_substring(self) -> None:
        """A process that merely contains 'claude' in path but isn't Claude binary."""
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "99999  1.0     01:00 /usr/bin/python /home/claude-user/scripts/server.py\n"
        )
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=""),
        ):
            results = scanner.scan()
        assert len(results) == 0

    def test_cwd_fallback_when_lsof_fails(self) -> None:
        mock_ps = (
            "  PID  %CPU   ELAPSED COMMAND\n"
            "99999  5.0     01:00 node /path/claude\n"
        )
        scanner = ProcessScanner()
        with (
            patch.object(scanner, "_run_ps", return_value=mock_ps),
            patch.object(scanner, "_run_lsof", return_value=""),
        ):
            results = scanner.scan()
        assert len(results) == 1
        assert results[0].cwd == ""


class TestParseLsofOutput:
    def test_extracts_cwd_and_uuids(self) -> None:
        output = (
            "p12345\n"
            "fcwd\n"
            "n/Users/testuser/projects/agentator\n"
            "f5\n"
            "n/Users/testuser/.claude/tasks/abc12345-dead-beef-cafe-123456789abc\n"
            "f6\n"
            "n/Users/testuser/.claude/tasks/def67890-1234-5678-9abc-def012345678\n"
        )
        scanner = ProcessScanner()
        cwd, uuids = scanner._parse_lsof_output(output)
        assert cwd == "/Users/testuser/projects/agentator"
        assert uuids == {
            "abc12345-dead-beef-cafe-123456789abc",
            "def67890-1234-5678-9abc-def012345678",
        }

    def test_cwd_only_no_uuids(self) -> None:
        output = "p12345\nfcwd\nn/Users/testuser/projects/agentator\n"
        scanner = ProcessScanner()
        cwd, uuids = scanner._parse_lsof_output(output)
        assert cwd == "/Users/testuser/projects/agentator"
        assert uuids == set()

    def test_empty_output(self) -> None:
        scanner = ProcessScanner()
        cwd, uuids = scanner._parse_lsof_output("")
        assert cwd == ""
        assert uuids == set()

    def test_uuids_but_no_cwd(self) -> None:
        output = (
            "p12345\n"
            "f5\n"
            "n/Users/testuser/.claude/tasks/abc12345-dead-beef-cafe-123456789abc\n"
        )
        scanner = ProcessScanner()
        cwd, uuids = scanner._parse_lsof_output(output)
        assert cwd == ""
        assert uuids == {"abc12345-dead-beef-cafe-123456789abc"}

    def test_extracts_uuid_from_jsonl_path(self) -> None:
        """UUIDs from .claude/projects/<mangled>/<uuid>.jsonl should be extracted."""
        output = (
            "p12345\n"
            "fcwd\n"
            "n/Users/testuser/projects/monitorator\n"
            "f7\n"
            "n/Users/testuser/.claude/projects/-Users-testuser-projects-monitorator/"
            "f6890b8c-1486-4835-8c1f-d72fc598354c.jsonl\n"
        )
        scanner = ProcessScanner()
        cwd, uuids = scanner._parse_lsof_output(output)
        assert cwd == "/Users/testuser/projects/monitorator"
        assert uuids == {"f6890b8c-1486-4835-8c1f-d72fc598354c"}


class TestResolveSessionUuid:
    def test_resolves_newest_jsonl(self, tmp_path: object) -> None:
        import os
        import time

        p = tmp_path  # type: ignore[assignment]
        # Simulate ~/.claude/projects/<mangled>/
        mangled = "-Users-testuser-projects-agentator"
        proj_dir = p / "projects" / mangled
        proj_dir.mkdir(parents=True)

        uuid1 = "abc12345-dead-beef-cafe-123456789abc"
        uuid2 = "def67890-1234-5678-9abc-def012345678"

        (proj_dir / f"{uuid1}.jsonl").write_text("{}\n")
        time.sleep(0.05)
        (proj_dir / f"{uuid2}.jsonl").write_text("{}\n")

        scanner = ProcessScanner()
        result = scanner._resolve_session_uuid(
            "/Users/testuser/projects/agentator",
            {uuid1, uuid2},
            claude_dir=str(p),
        )
        assert result == uuid2

    def test_returns_none_when_no_jsonl_exists(self, tmp_path: object) -> None:
        p = tmp_path  # type: ignore[assignment]
        scanner = ProcessScanner()
        result = scanner._resolve_session_uuid(
            "/Users/testuser/projects/agentator",
            {"nonexistent-uuid-1234-5678-9abc-def012345678"},
            claude_dir=str(p),
        )
        assert result is None

    def test_returns_none_when_no_uuids(self) -> None:
        scanner = ProcessScanner()
        result = scanner._resolve_session_uuid("/tmp/proj", set())
        assert result is None
