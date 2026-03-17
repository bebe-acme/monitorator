# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Monitorator

A TUI dashboard (built with Textual) that monitors all active Claude Code sessions in real time. It works by installing Claude Code hooks that write session state to `~/.monitorator/sessions/` as JSON files, then merging that hook data with live process scanning (`ps` + `lsof`) to produce a unified view.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run the TUI
uv run monitorator            # default: launches TUI
uv run monitorator run        # explicit

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_scanner.py

# Run a single test by name
uv run pytest tests/test_scanner.py -k "test_name"

# Install/uninstall hooks into ~/.claude/settings.json
uv run monitorator install
uv run monitorator uninstall --clean

# Quick CLI status (no TUI)
uv run monitorator status

# Run with a specific theme
uv run monitorator --theme solarized-dark
```

## Architecture

### Data Pipeline

1. **Hook (`hooks/emit_event.py`)** — Standalone stdlib-only script registered in `~/.claude/settings.json`. Reads Claude Code event JSON from stdin, writes/updates `~/.monitorator/sessions/<session_id>.json`. Must stay stdlib-only and complete <100ms.

2. **ProcessScanner (`scanner.py`)** — Finds running Claude Code processes via `ps`, resolves their cwd and session UUID via `lsof`, then maps UUIDs to `~/.claude/projects/<mangled>/<uuid>.jsonl` files by newest mtime.

3. **StateStore (`state_store.py`)** — Reads/writes/cleans the JSON session files in `~/.monitorator/sessions/`.

4. **SessionMerger (`merger.py`)** — Joins hook states with process info by matching `cwd`. Produces `MergedSession` objects with `effective_status` (can override idle→thinking if CPU > 10%). Unmatched processes become hookless sessions (`proc-{pid}`). Sessions with no matching process and no update for 5 min are marked stale.

5. **Notifier (`notifier.py`)** — macOS notifications via `osascript`. Fires on status transitions (permission needed, session finished, active→idle). Permission notifications bypass debounce; others have 30s debounce.

### TUI Layer (`tui/`)

- **`app.py`** — `MonitoratorApp(App)`: composes HeaderBanner + ColumnHeader + scrollable SessionRow list + DetailPanel. Polls every 2s via `_refresh()` which does diff-based row updates (add/remove/update).
- **`session_row.py`** — Single-line focusable row per session. Shows status icon, project name (color-rotated), branch, activity description, CPU%, elapsed time. Optionally shows a second line with the last user prompt.
- **`detail_panel.py`** — Bottom panel showing expanded info for the selected session (status, PID, CPU, elapsed, branch, cwd, tool, prompt, subagent count). Uses box-drawing characters.
- **`formatting.py`** — Status icons/colors/labels maps, `format_activity()` which transforms raw hook data into human-readable descriptions (tool-specific formatting for Bash/Edit/Write/Read/Grep/Glob/Task).
- **`header_banner.py`** — Top banner with block logo, session counts (total/active/idle/waiting), timestamp.
- **`theme_colors.py`** — Six color themes (dark, light, bokeh, high-contrast, solarized-dark, solarized-light). All WCAG AA contrast-verified. `ThemeColors` dataclass with 30 semantic tokens, `_ActiveColors` proxy for runtime switching, `get_status_color()` helper.
- **`theme_screen.py`** — Modal theme picker (keys 1-6). Shows current selection and descriptions.
- **`styles.tcss`** — Theme-aware Textual CSS using `$variable` references that map to active theme colors.

### Supporting Modules

- **`session_prompt.py`** — Reads the last user prompt from Claude's JSONL transcript files. Reads from end of file in chunks (max 1MB), caches by UUID+mtime.
- **`project_metadata.py`** — Extracts project description from CLAUDE.md headings, pyproject.toml, package.json, or README.md. Cached per cwd.
- **`terminal_opener.py`** — macOS-specific: finds TTY for a PID, activates the terminal app (tries Ghostty → iTerm2 → Terminal.app).
- **`installer.py`** — Installs/uninstalls the `emit_event.py` hook into `~/.claude/settings.json` for all relevant event types (PreToolUse, PostToolUse, Notification, SubagentStart/Stop, Stop, UserPromptSubmit).
- **`preferences.py`** — Persists user settings (theme choice) to `~/.monitorator/preferences.json`.

### Models (`models.py`)

Three core dataclasses: `SessionState` (hook data), `ProcessInfo` (ps/lsof data), `MergedSession` (joined view with `effective_status` and `is_stale`). `SessionStatus` enum: IDLE, THINKING, EXECUTING, WAITING_PERMISSION, SUBAGENT_RUNNING, TERMINATED, UNKNOWN.

## Key Conventions

- Python 3.11+, uses `uv` for dependency management
- `from __future__ import annotations` in every module
- Textual framework for TUI — widgets are `Static` subclasses with Rich markup
- `hooks/emit_event.py` must remain stdlib-only (no third-party imports)
- Tests use `pytest` with `pytest-asyncio` (asyncio_mode = "auto")
- Session data path: `~/.monitorator/sessions/`
- Claude project path mangling: `/Users/alice/foo_bar` → `-Users-alice-foo-bar`
