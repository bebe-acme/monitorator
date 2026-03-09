from __future__ import annotations

import json
import os
import re

_CACHE: dict[str, tuple[float, str | None]] = {}  # uuid → (mtime, prompt)

_CHUNK_SIZE = 256 * 1024  # 256KB
_MAX_READ = 1024 * 1024  # 1MB

# Matches messages that start with an XML-style tag like <tag-name>
_XML_TAG_RE = re.compile(r"^\s*<[a-zA-Z][\w-]*[ >/]")


def mangle_cwd(cwd: str) -> str:
    """Mangle a cwd path to match Claude's project directory naming.

    "/Users/alice/playground" → "-Users-alice-playground"
    """
    return "-" + cwd.lstrip("/").replace("/", "-").replace("_", "-")


def find_session_jsonl(
    cwd: str, uuid: str, claude_dir: str | None = None
) -> str | None:
    """Locate ~/.claude/projects/<mangled>/<uuid>.jsonl."""
    if claude_dir is None:
        claude_dir = os.path.expanduser("~/.claude")

    mangled = mangle_cwd(cwd)
    path = os.path.join(claude_dir, "projects", mangled, f"{uuid}.jsonl")
    if os.path.isfile(path):
        return path
    return None


def read_last_user_prompt(jsonl_path: str) -> str | None:
    """Read from end of file in chunks. Find last type=user message with
    content[].type=text. Skip tool_results, <local-command>, <command-name>."""
    try:
        file_size = os.path.getsize(jsonl_path)
    except OSError:
        return None

    if file_size == 0:
        return None

    read_size = min(file_size, _MAX_READ)

    try:
        with open(jsonl_path, "rb") as f:
            f.seek(max(0, file_size - read_size))
            data = f.read(read_size)
    except OSError:
        return None

    text = data.decode("utf-8", errors="replace")
    lines = text.strip().split("\n")

    # Walk lines in reverse to find last valid user text prompt
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if entry.get("type") != "user":
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        content = message.get("content")
        if not isinstance(content, list):
            continue

        # Find text content, skip tool_results
        user_text: str | None = None
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                user_text = None
                break
            if block.get("type") == "text":
                t = block.get("text", "")
                if isinstance(t, str) and t:
                    user_text = t

        if user_text is None:
            continue

        # Skip messages that start with XML-like tags (system/internal messages)
        if _XML_TAG_RE.match(user_text.strip()):
            continue

        return user_text

    return None


def get_session_prompt(
    cwd: str, uuid: str, claude_dir: str | None = None
) -> str | None:
    """Cached by uuid + file mtime. Re-reads when mtime changes."""
    jsonl_path = find_session_jsonl(cwd, uuid, claude_dir=claude_dir)
    if jsonl_path is None:
        # If cached, return cached value even if file disappeared
        if uuid in _CACHE:
            return _CACHE[uuid][1]
        return None

    try:
        mtime = os.path.getmtime(jsonl_path)
    except OSError:
        if uuid in _CACHE:
            return _CACHE[uuid][1]
        return None

    if uuid in _CACHE and _CACHE[uuid][0] >= mtime:
        return _CACHE[uuid][1]

    prompt = read_last_user_prompt(jsonl_path)
    _CACHE[uuid] = (mtime, prompt)
    return prompt
