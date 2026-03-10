from __future__ import annotations

import os
import re
import subprocess

from monitorator.models import ProcessInfo

_UUID_RE = re.compile(
    r"\.claude/(?:tasks|projects/[^/]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def parse_elapsed(elapsed_str: str) -> int:
    """Parse ps elapsed time format (MM:SS, HH:MM:SS, D-HH:MM:SS) to seconds."""
    elapsed_str = elapsed_str.strip()
    days = 0
    if "-" in elapsed_str:
        day_part, elapsed_str = elapsed_str.split("-", 1)
        try:
            days = int(day_part)
        except ValueError:
            return 0

    parts = elapsed_str.split(":")
    try:
        int_parts = [int(p) for p in parts]
    except ValueError:
        return 0

    if len(int_parts) == 2:
        return days * 86400 + int_parts[0] * 60 + int_parts[1]
    elif len(int_parts) == 3:
        return days * 86400 + int_parts[0] * 3600 + int_parts[1] * 60 + int_parts[2]
    return 0


def parse_ps_output(output: str) -> list[dict[str, object]]:
    """Parse ps output into structured dicts."""
    lines = output.strip().split("\n")
    if len(lines) <= 1:
        return []

    results: list[dict[str, object]] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            cpu = float(parts[1])
            elapsed_str = parts[2]
            command = " ".join(parts[3:])
            results.append({
                "pid": pid,
                "cpu": cpu,
                "elapsed_str": elapsed_str,
                "command": command,
            })
        except (ValueError, IndexError):
            continue
    return results


class ProcessScanner:
    CLAUDE_PATTERNS = ("claude", "claude-code")

    def _run_ps(self) -> str:
        result = subprocess.run(
            ["ps", "-eo", "pid,%cpu,etime,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout

    def _run_lsof(self, pid: int) -> str:
        try:
            result = subprocess.run(
                ["lsof", "-p", str(pid), "-Fn"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, OSError):
            return ""

    def _parse_lsof_output(self, output: str) -> tuple[str, set[str]]:
        """Parse lsof output → (cwd, set of session UUIDs).

        cwd: the line after 'fcwd' marker starting with 'n/'
        UUIDs: extracted from lines matching ~/.claude/tasks/<uuid>
        """
        cwd = ""
        uuids: set[str] = set()
        in_cwd = False

        for line in output.strip().split("\n"):
            if line == "fcwd":
                in_cwd = True
                continue
            if in_cwd and line.startswith("n/"):
                cwd = line[1:]
                in_cwd = False
                continue
            if line.startswith("f"):
                in_cwd = False
            match = _UUID_RE.search(line)
            if match:
                uuids.add(match.group(1))

        return cwd, uuids

    def _resolve_session_uuid(
        self,
        cwd: str,
        uuids: set[str],
        claude_dir: str | None = None,
    ) -> str | None:
        """Find the UUID whose JSONL file has the newest mtime."""
        if not uuids:
            return None

        if claude_dir is None:
            claude_dir = os.path.expanduser("~/.claude")

        mangled = "-" + cwd.lstrip("/").replace("/", "-").replace("_", "-")
        proj_dir = os.path.join(claude_dir, "projects", mangled)

        best_uuid: str | None = None
        best_mtime: float = -1.0

        for uuid in uuids:
            jsonl_path = os.path.join(proj_dir, f"{uuid}.jsonl")
            try:
                mtime = os.path.getmtime(jsonl_path)
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_uuid = uuid
            except OSError:
                continue

        return best_uuid

    _EXCLUDED_FLAGS = ("--chrome-native-host",)
    _EXCLUDED_PATHS = ("claude.app",)

    def _is_claude_process(self, command: str) -> bool:
        # Exclude helper processes like Chrome extension native host or Claude Desktop app
        cmd_lower = command.lower()
        for flag in self._EXCLUDED_FLAGS:
            if flag in cmd_lower:
                return False
        for path_fragment in self._EXCLUDED_PATHS:
            if path_fragment in cmd_lower:
                return False

        # Check if any token's basename is a Claude binary
        tokens = command.split()
        for token in tokens:
            if token.startswith("-"):
                continue
            basename = token.rsplit("/", 1)[-1].lower()
            if basename in self.CLAUDE_PATTERNS:
                return True
        return False

    def scan(self) -> list[ProcessInfo]:
        try:
            ps_output = self._run_ps()
        except (subprocess.TimeoutExpired, OSError):
            return []

        parsed = parse_ps_output(ps_output)
        results: list[ProcessInfo] = []

        for entry in parsed:
            command = str(entry["command"])
            if not self._is_claude_process(command):
                continue

            pid = int(entry["pid"])  # type: ignore[arg-type]
            lsof_output = self._run_lsof(pid)
            cwd, uuids = self._parse_lsof_output(lsof_output)
            session_uuid = self._resolve_session_uuid(cwd, uuids) if cwd and uuids else None

            results.append(ProcessInfo(
                pid=pid,
                cpu_percent=float(entry["cpu"]),  # type: ignore[arg-type]
                elapsed_seconds=parse_elapsed(str(entry["elapsed_str"])),
                cwd=cwd,
                command=command,
                session_uuid=session_uuid,
            ))

        return results
