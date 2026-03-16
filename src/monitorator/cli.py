from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from monitorator.installer import HookInstaller
from monitorator.merger import SessionMerger
from monitorator.models import SessionStatus
from monitorator.scanner import ProcessScanner
from monitorator.state_store import StateStore
from monitorator.tui.theme_colors import THEMES

SESSIONS_DIR = Path.home() / ".monitorator" / "sessions"


def cmd_run(args: argparse.Namespace) -> None:
    from monitorator.tui.app import MonitoratorApp
    theme = getattr(args, "theme", None)
    app = MonitoratorApp(theme_name=theme)
    app.run()


def cmd_install(args: argparse.Namespace) -> None:
    installer = HookInstaller()
    if installer.is_installed():
        print("Monitorator hooks already installed.")
        return
    installer.install()
    print("Monitorator hooks installed in ~/.claude/settings.json")
    print("Backup saved as settings.json.monitorator-backup")


def cmd_uninstall(args: argparse.Namespace) -> None:
    installer = HookInstaller()
    if not installer.is_installed():
        print("Monitorator hooks not found.")
        return
    installer.uninstall()
    print("Monitorator hooks removed from ~/.claude/settings.json")
    if args.clean:
        import shutil
        sessions_dir = SESSIONS_DIR
        if sessions_dir.exists():
            shutil.rmtree(sessions_dir)
            print(f"Removed {sessions_dir}")


def cmd_status(args: argparse.Namespace) -> None:
    store = StateStore(SESSIONS_DIR)
    scanner = ProcessScanner()
    merger = SessionMerger()

    hook_states = store.list_all()
    processes = scanner.scan()
    merged = merger.merge(hook_states, processes)

    if not merged:
        print("No active Claude Code sessions found.")
        return

    installer = HookInstaller()
    hooks_status = "installed" if installer.is_installed() else "not installed"
    print(f"Hooks: {hooks_status}")
    print(f"Sessions: {len(merged)}")
    print()
    print(f"{'Project':<20} {'Status':<18} {'CPU%':<8} {'Activity'}")
    print("-" * 70)
    for m in merged:
        project = m.project_name[:19]
        status = m.effective_status.value
        if m.is_stale:
            status = "stale"
        cpu = f"{m.process_info.cpu_percent:.0f}%" if m.process_info else "-"
        activity = ""
        if m.hook_state and m.hook_state.last_tool:
            activity = m.hook_state.last_tool
            if m.hook_state.last_tool_input_summary:
                activity += f": {m.hook_state.last_tool_input_summary[:30]}"
        elif m.hook_state and m.hook_state.updated_at:
            ago = int(time.time() - m.hook_state.updated_at)
            activity = f"{ago}s ago" if ago < 60 else f"{ago // 60}m ago"
        print(f"{project:<20} {status:<18} {cpu:<8} {activity}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="monitorator",
        description="Monitor all active Claude Code sessions",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Launch TUI dashboard")
    run_parser.add_argument(
        "--theme", choices=list(THEMES.keys()), default=None,
        help="Color theme (overrides saved preference)",
    )

    # Also add --theme to the top-level parser for `monitorator --theme bokeh`
    parser.add_argument(
        "--theme", choices=list(THEMES.keys()), default=None,
        help="Color theme (overrides saved preference)",
    )

    subparsers.add_parser("install", help="Install global hooks")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove hooks")
    uninstall_parser.add_argument("--clean", action="store_true", help="Also remove session data")

    subparsers.add_parser("status", help="Quick status summary")

    args = parser.parse_args(argv)

    if args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        # Default: launch TUI
        cmd_run(args)
