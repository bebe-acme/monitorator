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
    """Locate ~/.claude/projects/<mangled>/<uuid>.jsonl.

    Claude Code stores sessions under the git root's mangled path, which may
    be a parent of the hook's cwd.  Try the exact cwd first, then walk up
    parent directories until we find the JSONL or hit the filesystem root.
    """
    if claude_dir is None:
        claude_dir = os.path.expanduser("~/.claude")

    projects_dir = os.path.join(claude_dir, "projects")
    current = cwd
    while current and current != "/":
        mangled = mangle_cwd(current)
        path = os.path.join(projects_dir, mangled, f"{uuid}.jsonl")
        if os.path.isfile(path):
            return path
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
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


def _extract_user_text(content: list[object]) -> str | None:
    """Extract user prompt text from content blocks.

    Handles two JSONL formats:
    - Dict blocks: [{"type": "text", "text": "hello"}]
    - Raw char strings: ["h", "e", "l", "l", "o"]  (streamed input)
    Returns None for tool_result messages and system messages.
    """
    has_tool_result = any(
        isinstance(b, dict) and b.get("type") == "tool_result"
        for b in content
    )
    if has_tool_result:
        return None

    # Try dict-style blocks first
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text", "")
            if isinstance(t, str) and t.strip():
                return t.strip()

    # Try raw string concatenation (streamed char-by-char input)
    if content and all(isinstance(b, str) for b in content):
        joined = "".join(content).strip()  # type: ignore[arg-type]
        if joined:
            return joined

    return None


def _summarize_tool_use(block: dict[str, object]) -> str:
    """Create a compact one-line summary of a tool_use block."""
    name = str(block.get("name", ""))
    inp = block.get("input", {})
    if not isinstance(inp, dict):
        return name

    if name in ("Read", "Edit", "Write"):
        path = str(inp.get("file_path", ""))
        if path:
            parts = path.rsplit("/", 2)
            short = "/".join(parts[-2:]) if len(parts) > 2 else path
            return f"{name} {short}"
        return name

    if name == "Bash":
        cmd = str(inp.get("command", ""))
        if len(cmd) > 60:
            cmd = cmd[:60] + "\u2026"
        return f"$ {cmd}" if cmd else "Bash"

    if name == "Grep":
        pattern = str(inp.get("pattern", ""))
        return f'Search "{pattern}"' if pattern else "Grep"

    if name == "Glob":
        pattern = str(inp.get("pattern", ""))
        return f'Find "{pattern}"' if pattern else "Glob"

    if name in ("Agent", "Task", "TaskCreate"):
        desc = str(inp.get("description", inp.get("prompt", "")))
        if desc:
            if len(desc) > 50:
                desc = desc[:50] + "\u2026"
            return f"Agent: {desc}"
        return name

    return name


def read_recent_messages(
    jsonl_path: str,
    max_messages: int = 1000,
    max_msg_len: int = 300,
) -> list[tuple[str, str]]:
    """Read recent user/assistant messages + tool uses from a JSONL transcript.

    Returns list of (role, text) tuples in chronological order.
    Roles: "user", "assistant", "tool".
    Filters out tool_result user messages and system/XML messages.
    """
    try:
        file_size = os.path.getsize(jsonl_path)
    except OSError:
        return []

    if file_size == 0:
        return []

    read_size = min(file_size, 10 * 1024 * 1024)

    try:
        with open(jsonl_path, "rb") as f:
            f.seek(max(0, file_size - read_size))
            data = f.read(read_size)
    except OSError:
        return []

    text = data.decode("utf-8", errors="replace")
    lines = text.strip().split("\n")
    messages: list[tuple[str, str]] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        role = entry.get("type")
        if role not in ("user", "assistant"):
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        content = message.get("content")

        if role == "user":
            # content can be a plain string (direct user input)
            if isinstance(content, str):
                user_text = content.strip() or None
            elif isinstance(content, list):
                user_text = _extract_user_text(content)
            else:
                continue
            if not user_text or _XML_TAG_RE.match(user_text):
                continue
            # Skip interruption markers
            if user_text.startswith("[Request interrupted"):
                continue
            if len(user_text) > max_msg_len:
                user_text = user_text[:max_msg_len] + "\u2026"
            messages.append(("user", user_text))

        else:  # assistant
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    t = block.get("text", "")
                    if isinstance(t, str) and t.strip():
                        cleaned = t.strip()
                        if _XML_TAG_RE.match(cleaned):
                            continue
                        if len(cleaned) > max_msg_len:
                            cleaned = cleaned[:max_msg_len] + "\u2026"
                        messages.append(("assistant", cleaned))
                elif block.get("type") == "tool_use":
                    summary = _summarize_tool_use(block)
                    if summary:
                        messages.append(("tool", summary))

    # Collapse consecutive tool entries to keep more conversation visible.
    # Keep up to 3 tools per assistant turn, replace the rest with a count.
    collapsed: list[tuple[str, str]] = []
    consecutive_tools = 0
    for role, text in messages:
        if role == "tool":
            consecutive_tools += 1
            if consecutive_tools <= 3:
                collapsed.append((role, text))
            elif consecutive_tools == 4:
                collapsed.append(("tool", "\u2026"))
            # else: skip
        else:
            consecutive_tools = 0
            collapsed.append((role, text))

    return collapsed[-max_messages:]


_HISTORY_CACHE: dict[str, tuple[float, list[tuple[str, str]]]] = {}


def get_session_history(
    cwd: str,
    uuid: str,
    max_messages: int = 1000,
    claude_dir: str | None = None,
) -> list[tuple[str, str]]:
    """Return recent chat messages for a session, cached by uuid + file mtime."""
    jsonl_path = find_session_jsonl(cwd, uuid, claude_dir=claude_dir)
    if jsonl_path is None:
        if uuid in _HISTORY_CACHE:
            return _HISTORY_CACHE[uuid][1]
        return []

    try:
        mtime = os.path.getmtime(jsonl_path)
    except OSError:
        if uuid in _HISTORY_CACHE:
            return _HISTORY_CACHE[uuid][1]
        return []

    if uuid in _HISTORY_CACHE and _HISTORY_CACHE[uuid][0] >= mtime:
        return _HISTORY_CACHE[uuid][1]

    messages = read_recent_messages(jsonl_path, max_messages=max_messages)
    _HISTORY_CACHE[uuid] = (mtime, messages)
    return messages


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
