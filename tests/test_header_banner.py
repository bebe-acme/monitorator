from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from monitorator.models import MergedSession, SessionState, SessionStatus
from monitorator.tui.header_banner import HeaderBanner, count_sessions, RefreshRequested


def make_merged(
    session_id: str = "test-1",
    status: SessionStatus = SessionStatus.THINKING,
    stale: bool = False,
) -> MergedSession:
    return MergedSession(
        session_id=session_id,
        hook_state=SessionState(
            session_id=session_id,
            cwd="/tmp/test",
            project_name="Test",
            status=status,
            updated_at=time.time(),
        ),
        process_info=None,
        effective_status=status,
        is_stale=stale,
    )


# ── count_sessions() ────────────────────────────────────────────


class TestCountSessions:
    def test_empty(self) -> None:
        result = count_sessions([])
        assert result == {"total": 0, "active": 0, "idle": 0, "waiting": 0}

    def test_all_thinking(self) -> None:
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.THINKING),
        ]
        result = count_sessions(sessions)
        assert result == {"total": 2, "active": 2, "idle": 0, "waiting": 0}

    def test_mixed_statuses(self) -> None:
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.EXECUTING),
            make_merged("s3", SessionStatus.IDLE),
            make_merged("s4", SessionStatus.WAITING_PERMISSION),
            make_merged("s5", SessionStatus.SUBAGENT_RUNNING),
        ]
        result = count_sessions(sessions)
        assert result["total"] == 5
        assert result["active"] == 3
        assert result["idle"] == 1
        assert result["waiting"] == 1

    def test_executing_counts_as_active(self) -> None:
        sessions = [make_merged("s1", SessionStatus.EXECUTING)]
        result = count_sessions(sessions)
        assert result["active"] == 1

    def test_subagent_counts_as_active(self) -> None:
        sessions = [make_merged("s1", SessionStatus.SUBAGENT_RUNNING)]
        result = count_sessions(sessions)
        assert result["active"] == 1

    def test_terminated_not_counted(self) -> None:
        sessions = [make_merged("s1", SessionStatus.TERMINATED)]
        result = count_sessions(sessions)
        assert result["total"] == 1
        assert result["active"] == 0
        assert result["idle"] == 0
        assert result["waiting"] == 0

    def test_unknown_not_counted(self) -> None:
        sessions = [make_merged("s1", SessionStatus.UNKNOWN)]
        result = count_sessions(sessions)
        assert result["total"] == 1
        assert result["active"] == 0
        assert result["idle"] == 0
        assert result["waiting"] == 0


# ── HeaderBanner widget ─────────────────────────────────────────


class TestHeaderBanner:
    def test_banner_instantiates(self) -> None:
        banner = HeaderBanner()
        assert isinstance(banner, HeaderBanner)

    def test_initial_stats_text_empty(self) -> None:
        banner = HeaderBanner()
        assert banner._stats_text == ""

    def test_do_render_initial_shows_waiting_message(self) -> None:
        banner = HeaderBanner()
        content = banner.content
        assert "waiting for sessions" in content
        # Initial message should be on line 3 (index 2)
        lines = content.strip().split("\n")
        assert "waiting for sessions" in lines[2]

    def test_update_counts_sets_stats_text(self) -> None:
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
        ]
        banner.update_counts(sessions)
        assert banner._stats_text != ""

    def test_update_counts_does_not_crash_empty(self) -> None:
        banner = HeaderBanner()
        banner.update_counts([])
        # No assertion needed -- just verifying it doesn't raise.

    def test_update_counts_with_waiting(self) -> None:
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
            make_merged("s3", SessionStatus.WAITING_PERMISSION),
        ]
        banner.update_counts(sessions)
        has_color = "ff3333" in banner._stats_text
        has_symbol = "\u26a0" in banner._stats_text
        assert has_color or has_symbol

    def test_active_count_in_green(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.EXECUTING)]
        banner.update_counts(sessions)
        assert "#00ff66" in banner._stats_text

    def test_idle_count_in_gray(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.IDLE)]
        banner.update_counts(sessions)
        # Idle count uses text_dimmer color from the active theme
        from monitorator.tui.theme_colors import colors
        assert colors.text_dimmer in banner._stats_text

    def test_no_render_content_override(self) -> None:
        """CRITICAL: HeaderBanner must NOT define _render_content."""
        assert "_render_content" not in HeaderBanner.__dict__

    def test_has_on_click_handler(self) -> None:
        """HeaderBanner should have an on_click handler for refresh."""
        assert hasattr(HeaderBanner, "on_click")

    def test_refresh_requested_message_exists(self) -> None:
        """RefreshRequested message class should exist for click-to-refresh."""
        assert issubclass(RefreshRequested, object)


# ── Banner layout tests ────────────────────────────────────────


class TestBannerLayout:
    def test_has_five_lines(self) -> None:
        """Content: 5 lines (ghost sprite height, no border lines in markup)."""
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.THINKING)]
        banner.update_counts(sessions)
        content = banner.content
        lines = content.strip().split("\n")
        assert len(lines) == 5

    def test_no_box_drawing_in_markup(self) -> None:
        """Box-drawing chars should not appear in markup (CSS handles borders)."""
        banner = HeaderBanner()
        content = banner.content
        for ch in "\u2554\u2550\u2557\u2551\u255a\u255d":  # ╔═╗║╚╝
            assert ch not in content

    def test_has_ghost_sprite_in_yellow(self) -> None:
        """Ghost should use #ffcc00 yellow body color with half-block chars."""
        banner = HeaderBanner()
        content = banner.content
        assert "#ffcc00" in content
        has_half_blocks = any(ch in content for ch in "\u2580\u2584\u2588")
        assert has_half_blocks

    def test_ghost_uses_render_sprite(self) -> None:
        """The header should use render_sprite() from the sprites module."""
        with patch("monitorator.tui.header_banner.render_sprite") as mock_render:
            mock_render.return_value = ("l1", "l2", "l3", "l4", "l5")
            banner = HeaderBanner()
            mock_render.assert_called_once()

    def test_no_timestamp(self) -> None:
        """Banner should NOT contain a timestamp — date was removed."""
        banner = HeaderBanner()
        content = banner.content
        import re

        assert not re.search(r"\d{4}-\d{2}-\d{2}", content)

    def test_has_monitorator_text(self) -> None:
        """Banner should contain MONITORATOR on line 4 (next to ghost bottom)."""
        banner = HeaderBanner()
        content = banner.content
        assert "MONITORATOR" in content
        lines = content.strip().split("\n")
        assert "MONITORATOR" in lines[3]

    def test_uses_yellow_for_title(self) -> None:
        banner = HeaderBanner()
        content = banner.content
        assert "bold #ffcc00" in content

    def test_stats_on_line3(self) -> None:
        """Stats should appear on line 3 (index 2)."""
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
            make_merged("s3", SessionStatus.EXECUTING),
        ]
        banner.update_counts(sessions)
        content = banner.content
        lines = content.strip().split("\n")
        assert "3" in lines[2]
        assert "sessions" in lines[2]

    def test_idle_on_line3(self) -> None:
        """Idle count should be on line 3 alongside total."""
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.IDLE),
            make_merged("s2", SessionStatus.IDLE),
        ]
        banner.update_counts(sessions)
        content = banner.content
        lines = content.strip().split("\n")
        assert "idle" in lines[2]

    def test_waiting_shows_warning_symbol(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.WAITING_PERMISSION)]
        banner.update_counts(sessions)
        content = banner.content
        assert "\u26a0" in content

    def test_no_monitor_icon(self) -> None:
        """Old monitor icon (▄██▄/█▀▀█) should not appear — replaced by ghost."""
        banner = HeaderBanner()
        content = banner.content
        assert "\u2584\u2588\u2588\u2584" not in content  # ▄██▄
        assert "\u2588\u2580\u2580\u2588" not in content  # █▀▀█

    def test_lines_short_enough_for_narrow_terminal(self) -> None:
        """No visible line should exceed 80 chars to avoid wrapping in narrow terminals."""
        import re

        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
            make_merged("s3", SessionStatus.WAITING_PERMISSION),
        ]
        banner.update_counts(sessions)
        content = banner.content
        for i, line in enumerate(content.strip().split("\n")):
            plain = re.sub(r"\[/?[^\]]*\]", "", line)
            assert len(plain) <= 80, (
                f"Line {i} has {len(plain)} visible chars (max 80): {plain!r}"
            )
