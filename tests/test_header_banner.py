from __future__ import annotations

import time

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus
from monitorator.tui.header_banner import HeaderBanner, count_sessions


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

    def test_terminated_not_counted_in_categories(self) -> None:
        sessions = [make_merged("s1", SessionStatus.TERMINATED)]
        result = count_sessions(sessions)
        assert result["total"] == 1
        assert result["active"] == 0
        assert result["idle"] == 0
        assert result["waiting"] == 0

    def test_unknown_not_counted_in_categories(self) -> None:
        sessions = [make_merged("s1", SessionStatus.UNKNOWN)]
        result = count_sessions(sessions)
        assert result["total"] == 1
        assert result["active"] == 0
        assert result["idle"] == 0
        assert result["waiting"] == 0


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
        assert "\u2588\u2584\u2588\u2584\u2588" in content  # █▄█▄█ (M top in half-block art)

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

    def test_update_counts_with_waiting(self) -> None:
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
            make_merged("s3", SessionStatus.WAITING_PERMISSION),
        ]
        banner.update_counts(sessions)
        assert "ff3333" in banner._stats_text or "WAIT" in banner._stats_text

    def test_active_count_in_green(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.EXECUTING)]
        banner.update_counts(sessions)
        assert "#00ff66" in banner._stats_text

    def test_idle_count_in_gray(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.IDLE)]
        banner.update_counts(sessions)
        assert "#666666" in banner._stats_text

    def test_no_render_content_override(self) -> None:
        """CRITICAL: HeaderBanner must NOT define _render_content."""
        assert "_render_content" not in HeaderBanner.__dict__

    # ── Box border tests ──

    def test_has_top_border(self) -> None:
        """Content should have ╔═══╗ top border."""
        banner = HeaderBanner()
        content = banner.content
        assert "\u2554" in content  # ╔
        assert "\u2557" in content  # ╗
        assert "\u2550" in content  # ═

    def test_has_bottom_border(self) -> None:
        """Content should have ╚═══╝ bottom border."""
        banner = HeaderBanner()
        content = banner.content
        assert "\u255a" in content  # ╚
        assert "\u255d" in content  # ╝

    def test_has_four_lines(self) -> None:
        """Bordered layout: top border + 2 art lines + bottom border."""
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.THINKING)]
        banner.update_counts(sessions)
        content = banner.content
        lines = content.strip().split("\n")
        assert len(lines) == 4

    def test_has_timestamp(self) -> None:
        """Line 1 (inside border) should contain a timestamp."""
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.THINKING)]
        banner.update_counts(sessions)
        content = banner.content
        # Timestamp format includes colons (HH:MM:SS)
        assert ":" in content

    def test_line1_has_ascii_art_and_color(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.THINKING)]
        banner.update_counts(sessions)
        content = banner.content
        assert "\u2588\u2584\u2588\u2584\u2588" in content  # █▄█▄█ (M top in half-block art)
        assert "bold #ffcc00" in content

    def test_line1_stats_include_total_sessions(self) -> None:
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.THINKING),
            make_merged("s2", SessionStatus.IDLE),
            make_merged("s3", SessionStatus.EXECUTING),
        ]
        banner.update_counts(sessions)
        content = banner.content
        assert "3" in content
        assert "sessions" in content

    def test_line2_idle_on_right(self) -> None:
        banner = HeaderBanner()
        sessions = [
            make_merged("s1", SessionStatus.IDLE),
            make_merged("s2", SessionStatus.IDLE),
        ]
        banner.update_counts(sessions)
        content = banner.content
        assert "2" in content
        assert "idle" in content

    def test_waiting_shows_warning_symbol(self) -> None:
        banner = HeaderBanner()
        sessions = [make_merged("s1", SessionStatus.WAITING_PERMISSION)]
        banner.update_counts(sessions)
        content = banner.content
        assert "\u26a0" in content

    def test_half_block_art_in_content(self) -> None:
        """Verify the half-block pixel art MONITORATOR lines appear in rendered content."""
        banner = HeaderBanner()
        content = banner.content
        # Line 1: M starts with █▄█▄█, O starts with ▄▀▀▄
        assert "\u2588\u2584\u2588\u2584\u2588" in content  # █▄█▄█ (M top)
        assert "\u2584\u2580\u2580\u2584" in content  # ▄▀▀▄ (O top)
        # Line 2: M bottom is █ ▀ █, O bottom is ▀▄▄▀
        assert "\u2588 \u2580 \u2588" in content  # █ ▀ █ (M bottom)
        assert "\u2580\u2584\u2584\u2580" in content  # ▀▄▄▀ (O bottom)

    def test_art_uses_half_block_chars(self) -> None:
        """Verify half-block characters are used in the pixel art."""
        banner = HeaderBanner()
        content = banner.content
        # Art should contain full block, upper half, and lower half characters
        assert "\u2588" in content  # █ (full block)
        assert "\u2580" in content  # ▀ (upper half block)
        assert "\u2584" in content  # ▄ (lower half block)
        # Art should NOT contain old box-drawing art characters (borders still use them)
        # The art-specific sequences from the old version should be gone
        assert "\u2560\u2566\u255d" not in content  # ╠╦╝ no longer in art
        assert "\u2560\u2550\u2563" not in content  # ╠═╣ no longer in art
