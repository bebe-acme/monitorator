from __future__ import annotations

import json
from pathlib import Path

# Read chunk size for scanning from end of file
_READ_CHUNK = 64 * 1024  # 64KB — enough to find the last assistant message

# Cache: uuid -> (mtime, estimate_str)
_CACHE: dict[str, tuple[float, str]] = {}


def _format_tokens(token_count: int) -> str:
    """Format token count as human-readable string."""
    if token_count >= 1_000_000:
        return f"{token_count / 1_000_000:.1f}M"
    if token_count >= 1_000:
        return f"{token_count // 1_000}k"
    return str(token_count)


def mangle_cwd(cwd: str) -> str:
    """Convert cwd to Claude project dir mangled format."""
    return "-" + cwd.lstrip("/").replace("/", "-").replace("_", "-")


def _extract_usage_from_tail(jsonl_path: Path) -> int | None:
    """Read the last assistant message's context size from a JSONL file.

    Returns input_tokens + cache_creation_input_tokens + cache_read_input_tokens.
    """
    usage = _extract_raw_usage(jsonl_path)
    if usage is None:
        return None
    input_tokens = usage.get("input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    total = input_tokens + cache_creation + cache_read
    return total if total > 0 else None


def _extract_raw_usage(jsonl_path: Path) -> dict | None:
    """Read the last assistant message's raw usage dict from a JSONL file."""
    try:
        file_size = jsonl_path.stat().st_size
        if file_size == 0:
            return None

        with open(jsonl_path, "rb") as f:
            offset = max(0, file_size - _READ_CHUNK)
            f.seek(offset)
            tail = f.read().decode("utf-8", errors="replace")

        lines = tail.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            if usage.get("input_tokens", 0) + usage.get("output_tokens", 0) > 0:
                return usage

        return None
    except OSError:
        return None


def _resolve_jsonl(cwd: str, session_uuid: str, claude_dir: Path | None = None) -> Path | None:
    """Resolve a JSONL path for a session. Returns None if file doesn't exist."""
    if not cwd or not session_uuid:
        return None
    base = claude_dir or (Path.home() / ".claude")
    mangled = mangle_cwd(cwd)
    jsonl_path = base / "projects" / mangled / f"{session_uuid}.jsonl"
    return jsonl_path if jsonl_path.exists() else None


def get_session_usage(cwd: str, session_uuid: str, claude_dir: Path | None = None) -> dict[str, int] | None:
    """Get the latest token usage for a session.

    Returns dict with keys: input_tokens, cache_creation_input_tokens,
    cache_read_input_tokens, output_tokens. Or None if unavailable.
    """
    jsonl_path = _resolve_jsonl(cwd, session_uuid, claude_dir)
    if jsonl_path is None:
        return None
    usage = _extract_raw_usage(jsonl_path)
    if usage is None:
        return None
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


# Incremental output token accumulator: uuid -> (file_offset, cumulative_total)
_OUTPUT_STATE: dict[str, tuple[int, int]] = {}


def get_cumulative_output_tokens(cwd: str, session_uuid: str, claude_dir: Path | None = None) -> int:
    """Sum all output_tokens across all assistant messages in a session's JSONL.

    Uses incremental reading: only scans new bytes since last call.
    Returns 0 if file not found or no usage data.
    """
    jsonl_path = _resolve_jsonl(cwd, session_uuid, claude_dir)
    if jsonl_path is None:
        return 0

    try:
        file_size = jsonl_path.stat().st_size
        if file_size == 0:
            return 0

        prev_offset, prev_total = _OUTPUT_STATE.get(session_uuid, (0, 0))

        # Nothing new since last check
        if file_size <= prev_offset:
            return prev_total

        # Read only new bytes
        new_tokens = 0
        with open(jsonl_path, "r", errors="replace") as f:
            f.seek(prev_offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if isinstance(usage, dict):
                    new_tokens += usage.get("output_tokens", 0)

        total = prev_total + new_tokens
        _OUTPUT_STATE[session_uuid] = (file_size, total)
        return total
    except OSError:
        return 0


def get_context_estimate(cwd: str, session_uuid: str, claude_dir: Path | None = None) -> str | None:
    """Get context token usage from the last assistant message's usage data.

    Returns formatted string like "45k", "156k", "1.2M" or None if no file found.
    """
    jsonl_path = _resolve_jsonl(cwd, session_uuid, claude_dir)
    if jsonl_path is None:
        return None

    try:
        mtime = jsonl_path.stat().st_mtime

        # Check cache
        if session_uuid in _CACHE and _CACHE[session_uuid][0] == mtime:
            return _CACHE[session_uuid][1]

        total = _extract_usage_from_tail(jsonl_path)
        if total is None:
            return None

        result = _format_tokens(total)
        _CACHE[session_uuid] = (mtime, result)
        return result
    except OSError:
        return None
