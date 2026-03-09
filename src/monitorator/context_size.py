from __future__ import annotations

from pathlib import Path

# Rough heuristic: 1 token ~ 4 bytes of JSONL content
_BYTES_PER_TOKEN = 4

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


def get_context_estimate(cwd: str, session_uuid: str, claude_dir: Path | None = None) -> str | None:
    """Estimate context token usage from JSONL file size.

    Returns formatted string like "45k", "156k", "1.2M" or None if no file found.
    """
    if not cwd or not session_uuid:
        return None

    base = claude_dir or (Path.home() / ".claude")
    mangled = mangle_cwd(cwd)
    jsonl_path = base / "projects" / mangled / f"{session_uuid}.jsonl"

    if not jsonl_path.exists():
        return None

    try:
        stat = jsonl_path.stat()
        mtime = stat.st_mtime

        # Check cache
        if session_uuid in _CACHE and _CACHE[session_uuid][0] == mtime:
            return _CACHE[session_uuid][1]

        file_size = stat.st_size
        estimated_tokens = file_size // _BYTES_PER_TOKEN
        result = _format_tokens(estimated_tokens)

        _CACHE[session_uuid] = (mtime, result)
        return result
    except OSError:
        return None
