from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from monitorator.models import MergedSession, ProcessInfo, SessionState, SessionStatus

# All session_row tests run at wide terminal width (200 cols) by default
# so all columns are visible. Responsive-specific tests override this.
_WIDE_PATCH = patch("monitorator.tui.session_row._get_term_width", return_value=200)


@pytest.fixture(autouse=True)
def _wide_terminal():
    """Ensure all session_row tests run with wide terminal (all columns visible)."""
    with _WIDE_PATCH:
        yield


@pytest.fixture(autouse=True)
def _no_labels():
    """Disable label loading during tests (unless explicitly patched)."""
    with patch("monitorator.tui.session_row.get_label", return_value=None):
        yield


def make_merged(
    session_id: str = "test-1",
    project: str = "TestProj",
    status: SessionStatus = SessionStatus.THINKING,
    branch: str = "main",
    tool: str | None = "Edit",
    tool_summary: str | None = "file_path: src/app.py",
    prompt: str | None = "Build the monitor",
    cpu: float = 20.0,
    elapsed: int = 300,
    stale: bool = False,
    subagent_count: int = 0,
    updated_at: float | None = None,
    hook_state: bool = True,
    cwd: str | None = None,
    session_uuid: str | None = None,
) -> MergedSession:
    effective_cwd = cwd or f"/tmp/{project.lower()}"
    hs = (
        SessionState(
            session_id=session_id,
            cwd=effective_cwd,
            project_name=project,
            status=status,
            git_branch=branch,
            last_tool=tool,
            last_tool_input_summary=tool_summary,
            last_prompt_summary=prompt,
            updated_at=updated_at or time.time(),
            subagent_count=subagent_count,
        )
        if hook_state
        else None
    )
    return MergedSession(
        session_id=session_id,
        hook_state=hs,
        process_info=ProcessInfo(
            pid=12345,
            cpu_percent=cpu,
            elapsed_seconds=elapsed,
            cwd=effective_cwd,
            command="claude",
            session_uuid=session_uuid,
        ),
        effective_status=status,
        is_stale=stale,
    )


class TestSessionRowContent:
    def test_row_always_has_five_lines(self) -> None:
        """SessionRow always renders 5 lines (sprite 5-line layout)."""
        from monitorator.tui.session_row import SessionRow

        # With prompt
        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5

        # Without prompt — still 5 lines
        session_no_prompt = make_merged(prompt=None, tool=None, tool_summary=None)
        row2 = SessionRow(session_no_prompt)
        content2 = row2._build_content()
        lines2 = content2.strip().split("\n")
        assert len(lines2) == 5

    def test_contains_project_name(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="agentator")
        row = SessionRow(session)
        content = row._build_content()
        assert "AGENTATOR" in content

    def test_project_name_is_uppercase(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="my-cool-project")
        row = SessionRow(session)
        content = row._build_content()
        assert "MY-COOL-PROJECT" in content
        assert "my-cool-project" not in content

    def test_project_name_has_pixel_badge(self) -> None:
        """Project name rendered as pixel badge: ▐ NAME ▌ with colored bg."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="bbmedia")
        row = SessionRow(session)
        content = row._build_content()
        # Half-block pixel edges
        assert "\u2590" in content  # ▐ left edge
        assert "\u258c" in content  # ▌ right edge
        # Dark text on colored background
        assert "on " in content  # Rich "on" syntax for bg color
        assert "BBMEDIA" in content

    def test_contains_branch(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(branch="feat/ui")
        row = SessionRow(session)
        content = row._build_content()
        assert "feat/ui" in content

    def test_contains_status_icon(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        content = row._build_content()
        assert "\u25cf" in content  # ● thinking icon

    def test_contains_status_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        content = row._build_content()
        assert "THINK" in content

    def test_contains_cpu_on_line4(self) -> None:
        """CPU appears on line 4 (index 3)."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(cpu=45.0)
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert "45%" in lines[3]  # line 4 (index 3)
        assert "45%" not in lines[0]  # NOT on line 1

    def test_contains_elapsed_on_line4(self) -> None:
        """Elapsed time appears on line 4 (index 3)."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(elapsed=323)
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert "5m 23s" in lines[3]  # line 4 (index 3)
        assert "5m 23s" not in lines[0]  # NOT on line 1

    def test_description_never_empty(self) -> None:
        """Row must always produce non-empty content for every status."""
        from monitorator.tui.session_row import SessionRow

        for status in SessionStatus:
            session = make_merged(
                status=status,
                tool=None,
                tool_summary=None,
                prompt=None,
            )
            row = SessionRow(session)
            content = row._build_content()
            assert content.strip() != ""

    def test_no_branch_shows_dash(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(branch=None)  # type: ignore[arg-type]
        row = SessionRow(session)
        content = row._build_content()
        assert "\u2014" in content  # em-dash

    def test_no_process_info_shows_dash_for_cpu(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = MergedSession(
            session_id="test",
            hook_state=SessionState(
                session_id="test",
                cwd="/tmp/test",
                project_name="Test",
                status=SessionStatus.THINKING,
                updated_at=time.time(),
            ),
            process_info=None,
            effective_status=SessionStatus.THINKING,
            is_stale=False,
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "-" in content


class TestSessionRowIndex:
    def test_update_index(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged()
        row = SessionRow(session)
        row.update_index(3)
        assert row._row_index == 3


class TestSessionRowWidget:
    @pytest.mark.asyncio
    async def test_row_is_focusable(self) -> None:
        from monitorator.tui.session_row import SessionRow

        row = SessionRow(make_merged())
        assert row.can_focus is True

    @pytest.mark.asyncio
    async def test_row_stores_session_id(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(session_id="abc-123")
        row = SessionRow(session)
        assert row.session_id == "abc-123"

    @pytest.mark.asyncio
    async def test_update_session(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session1 = make_merged(session_id="abc", project="Old")
        row = SessionRow(session1)
        session2 = make_merged(session_id="abc", project="New")
        row.update_session(session2)
        assert row.session.project_name == "New"

    @pytest.mark.asyncio
    async def test_selected_message_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        msg = SessionRow.Selected("test-id")
        assert msg.session_id == "test-id"


class TestSessionRowColors:
    def test_same_session_same_sprite_regardless_of_index(self) -> None:
        """Same session_id should get same sprite/color even at different row positions."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(session_id="stable-test", project="ProjA", status=SessionStatus.IDLE, prompt=None)
        row1 = SessionRow(session)
        row1.update_index(1)
        row2 = SessionRow(session)
        row2.update_index(5)

        # Sprite index should be the same (from session_id, not row position)
        assert row1._sprite_idx == row2._sprite_idx

    def test_different_sessions_can_get_different_sprites(self) -> None:
        """Different session_ids should generally produce different sprites."""
        from monitorator.tui.session_row import SessionRow

        sprites = set()
        for i in range(20):
            session = make_merged(session_id=f"session-{i}", project="Proj", status=SessionStatus.IDLE, prompt=None)
            row = SessionRow(session)
            sprites.add(row._sprite_idx)
        assert len(sprites) >= 3, "Expected variety across 20 sessions"

    def test_session_colors_palette_has_at_least_6(self) -> None:
        """There should be at least 6 unique sprite primary colors."""
        from monitorator.tui.sprites import get_sprite_color

        colors = {get_sprite_color(i) for i in range(1, 23)}
        assert len(colors) >= 6


class TestSessionRowPromptLine:
    def test_shows_session_prompt_on_line_2(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            hook_state=False,
            project="MyProj",
        )
        session.process_info.session_uuid = "abc12345-dead-beef-cafe-123456789abc"  # type: ignore[union-attr]

        with patch("monitorator.tui.session_row.get_session_prompt", return_value="Implement auth flow"):
            row = SessionRow(session)
            content = row._build_content()

        assert "Implement auth flow" in content
        lines = content.strip().split("\n")
        assert len(lines) == 5

    def test_no_prompt_still_has_five_lines(self) -> None:
        """Even without prompt, row always has 5 lines (sprite)."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="Simple", prompt=None, tool=None, tool_summary=None)
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5


class TestSessionRowPermission:
    def test_waiting_permission_shows_warning(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            status=SessionStatus.WAITING_PERMISSION,
            tool="Bash",
            tool_summary="command: rm -rf dist",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "PERM!" in content

    def test_executing_shows_exec_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING)
        row = SessionRow(session)
        content = row._build_content()
        assert "EXEC" in content


class TestSessionRowSprite:
    def test_active_session_has_sprite(self) -> None:
        """THINKING session has half-block content in sprite area."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        row._anim_frame = 0
        content = row._build_content()
        block_chars = set("\u2580\u2584\u2588")
        assert any(ch in block_chars for ch in content)

    def test_different_sessions_get_different_sprites(self) -> None:
        """Different session_ids produce different sprite content."""
        from monitorator.tui.session_row import SessionRow

        session_a = make_merged(session_id="alpha-111", status=SessionStatus.IDLE, prompt=None)
        session_b = make_merged(session_id="beta-222", status=SessionStatus.IDLE, prompt=None)
        row1 = SessionRow(session_a)
        row1._anim_frame = 0
        content1 = row1._build_content()

        row2 = SessionRow(session_b)
        row2._anim_frame = 0
        content2 = row2._build_content()

        assert content1 != content2

    def test_idle_session_has_static_sprite(self) -> None:
        """IDLE frames don't change across anim_frame values."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        row._anim_frame = 0
        content0 = row._build_content()
        row._anim_frame = 1
        content1 = row._build_content()
        assert content0 == content1

    def test_permission_session_has_jump(self) -> None:
        """PERMISSION uses jump animation (standing vs peak differ)."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION, prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        row._anim_frame = 0
        content0 = row._build_content()
        row._anim_frame = 3
        content3 = row._build_content()
        assert content0 != content3

    def test_sprite_uses_fixed_palette(self) -> None:
        """Sprite uses a fixed palette color based on session_id, not row position."""
        from monitorator.tui.session_row import SessionRow
        from monitorator.tui.sprites import get_sprite_color, sprite_index_for_session

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        content = row._build_content()
        sprite_color = get_sprite_color(sprite_idx=sprite_index_for_session(session.session_id))
        assert sprite_color in content

    def test_sprite_stable_across_row_swaps(self) -> None:
        """Simulates app._refresh: two sessions swap positions, sprites stay the same."""
        from monitorator.tui.session_row import SessionRow
        from monitorator.tui.sprites import get_sprite_frame, sprite_index_for_session

        session_a = make_merged(session_id="alpha-111", project="Alpha", status=SessionStatus.IDLE, prompt=None)
        session_b = make_merged(session_id="beta-222", project="Beta", status=SessionStatus.IDLE, prompt=None)

        row_a = SessionRow(session_a)
        row_b = SessionRow(session_b)

        # Initial positions
        row_a._anim_frame = 0
        row_b._anim_frame = 0
        row_a.update_index(1)
        row_b.update_index(2)

        sprite_a_before = row_a._sprite_idx
        sprite_b_before = row_b._sprite_idx

        # Swap positions (like app sorting would do)
        row_a._anim_frame = 0
        row_b._anim_frame = 0
        row_a.update_index(2)
        row_b.update_index(1)

        sprite_a_after = row_a._sprite_idx
        sprite_b_after = row_b._sprite_idx

        # Sprite index must NOT change
        assert sprite_a_after == sprite_a_before, "Session A sprite changed after swap!"
        assert sprite_b_after == sprite_b_before, "Session B sprite changed after swap!"

        # The sprite frames (excluding row index number) should use the same template
        frame_a = get_sprite_frame(sprite_idx=sprite_a_after, status=SessionStatus.IDLE, anim_frame=0)
        frame_b = get_sprite_frame(sprite_idx=sprite_b_after, status=SessionStatus.IDLE, anim_frame=0)
        assert frame_a != frame_b, "Two different sessions should have different sprites"

    def test_thinking_sprite_animates(self) -> None:
        """THINKING produces different frames at different anim_frame values."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        row._anim_frame = 0
        content0 = row._build_content()
        row._anim_frame = 1
        content1 = row._build_content()
        assert content0 != content1

    def test_row_has_five_lines_always(self) -> None:
        """Every status produces exactly 5 lines."""
        from monitorator.tui.session_row import SessionRow

        for status in SessionStatus:
            session = make_merged(status=status, prompt=None)
            row = SessionRow(session)
            row.update_index(1)
            content = row._build_content()
            lines = content.strip().split("\n")
            assert len(lines) == 5, f"Status {status.name} produced {len(lines)} lines, expected 5"


class TestSessionRowFullRowBlink:
    """Active sessions (THINKING/EXECUTING/SUBAGENT) blink the ENTIRE row."""

    def test_thinking_has_full_row_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content

    def test_executing_has_full_row_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content

    def test_idle_has_no_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" not in content

    def test_permission_has_blink(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        content = row._build_content()
        assert "blink" in content


class TestSessionRowTerminatedDim:
    """TERMINATED sessions should have dim styling."""

    def test_terminated_has_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.TERMINATED, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" in content

    def test_thinking_not_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" not in content

    def test_idle_not_dim(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "dim" not in content


class TestSessionRowPaletteColoring:
    """ALL statuses use sprite palette color for project name."""

    @pytest.mark.parametrize("status", list(SessionStatus))
    def test_all_statuses_use_palette_color_for_project(self, status: SessionStatus) -> None:
        from monitorator.tui.session_row import SessionRow
        from monitorator.tui.sprites import get_sprite_color, sprite_index_for_session

        session = make_merged(status=status, project="MyProject", prompt=None)
        row = SessionRow(session)
        row.update_index(1)
        content = row._build_content()
        expected_color = get_sprite_color(sprite_idx=sprite_index_for_session(session.session_id))
        # Pixel badge: dark text on sprite-colored background
        assert f"on {expected_color}" in content
        assert "MYPROJECT" in content


class TestSessionRowIdleAmber:
    """IDLE sessions should use amber color and return symbol icon."""

    def test_idle_row_contains_amber_color_and_return_icon(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "#ffaa00" in content
        assert "\u23ce" in content  # ⏎ return symbol

    def test_idle_row_contains_wait_label(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert "WAIT" in content


class TestSessionRowPromptSanitization:
    def test_xml_tags_filtered_from_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            prompt="<task-notification><task-id>abc</task-id></task-notification>",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "<task-notification>" not in content

    def test_system_reminder_filtered(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            prompt="<system-reminder>You must do X</system-reminder>",
        )
        row = SessionRow(session)
        content = row._build_content()
        assert "<system-reminder>" not in content

    def test_newlines_stripped_from_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Line one\nLine two\nLine three")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5  # 5 lines (sprite), not more

    def test_empty_after_sanitization_hides_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="<system-reminder>internal only</system-reminder>")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5  # still 5 lines, no prompt text

    def test_sanitize_prompt_truncates_to_120_chars(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        long_text = "A" * 200
        result = _sanitize_prompt(long_text)
        assert result is not None
        assert len(result) <= 120

    def test_sanitize_prompt_none_input(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        assert _sanitize_prompt(None) is None

    def test_sanitize_prompt_whitespace_only_returns_none(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        assert _sanitize_prompt("   \n  \n  ") is None

    def test_sanitize_prompt_preserves_normal_text(self) -> None:
        from monitorator.tui.session_row import _sanitize_prompt

        result = _sanitize_prompt("Fix the login bug")
        assert result == "Fix the login bug"

    def test_command_name_tag_filtered(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="<command-name>review</command-name>")
        row = SessionRow(session)
        content = row._build_content()
        assert "<command-name>" not in content


class TestSessionRowContext:
    def test_context_shown_in_row(self) -> None:
        from unittest.mock import patch

        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            project="CtxProj",
            session_uuid="ctx-uuid-1234-5678-abcdef012345",
            cwd="/tmp/ctxproj",
        )

        with patch("monitorator.tui.session_row.get_context_estimate", return_value="45k"):
            row = SessionRow(session)
            content = row._build_content()

        assert "45k" in content

    def test_context_dash_when_no_uuid(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(project="NoUuid", prompt=None)
        row = SessionRow(session)
        content = row._build_content()
        assert content.count("-") >= 1


class TestSessionRowCompact:
    def test_compact_hides_prompt_but_keeps_five_lines(self) -> None:
        """In compact mode, row is still 5 lines but no prompt text."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(True)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5
        assert "Build the monitor" not in content

    def test_non_compact_shows_prompt(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(False)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert len(lines) == 5
        assert "Build the monitor" in content

    def test_compact_default_is_false(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        assert row._compact is False

    def test_set_compact_updates_flag(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        row = SessionRow(session)
        row.set_compact(True)
        assert row._compact is True


# ── Responsive layout tests ────────────────────────────────────────────


class TestSessionRowResponsive:
    """Test that session rows adapt to terminal width."""

    def test_wide_shows_all_columns(self) -> None:
        from monitorator.tui.session_row import SessionRow

        # autouse fixture already sets wide (200)
        session = make_merged(branch="main")
        row = SessionRow(session)
        row.update_index(1)
        content = row._build_content()
        assert "main" in content  # branch visible

    def test_narrow_hides_branch(self) -> None:
        from monitorator.tui.session_row import SessionRow

        with patch("monitorator.tui.session_row._get_term_width", return_value=80):
            session = make_merged(branch="feat/ui")
            row = SessionRow(session)
            row.update_index(1)
            content = row._build_content()
            assert "feat/ui" not in content

    def test_medium_shows_branch_hides_ctx(self) -> None:
        from monitorator.tui.session_row import SessionRow

        with patch("monitorator.tui.session_row._get_term_width", return_value=120):
            session = make_merged(branch="develop")
            row = SessionRow(session)
            row.update_index(1)
            content = row._build_content()
            assert "develop" in content  # branch visible at 120

    def test_get_layout_config_wide(self) -> None:
        from monitorator.tui.session_row import get_layout_config

        cfg = get_layout_config(200)
        assert cfg["show_branch"] is True
        assert cfg["show_ctx"] is True
        assert cfg["proj_w"] == 22

    def test_get_layout_config_narrow(self) -> None:
        from monitorator.tui.session_row import get_layout_config

        cfg = get_layout_config(80)
        assert cfg["show_branch"] is False
        assert cfg["show_ctx"] is False
        assert cfg["proj_w"] == 14

    def test_get_layout_config_medium(self) -> None:
        from monitorator.tui.session_row import get_layout_config

        cfg = get_layout_config(120)
        assert cfg["show_branch"] is True
        assert cfg["show_ctx"] is False

    def test_row_always_five_lines_at_any_width(self) -> None:
        from monitorator.tui.session_row import SessionRow

        for width in [60, 80, 100, 120, 200]:
            with patch("monitorator.tui.session_row._get_term_width", return_value=width):
                session = make_merged(prompt="hello world")
                row = SessionRow(session)
                row.update_index(1)
                content = row._build_content()
                lines = content.strip().split("\n")
                assert len(lines) == 5, f"Width {width} produced {len(lines)} lines"


class TestSessionRowStatusBar:
    """Status bar: left border indicator based on session status."""

    def test_thinking_has_status_active_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        assert row.has_class("status-active")

    def test_executing_has_status_active_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING)
        row = SessionRow(session)
        assert row.has_class("status-active")

    def test_subagent_has_status_active_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.SUBAGENT_RUNNING)
        row = SessionRow(session)
        assert row.has_class("status-active")

    def test_permission_has_status_permission_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        assert row.has_class("status-permission")

    def test_idle_has_status_idle_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE)
        row = SessionRow(session)
        assert row.has_class("status-idle")

    def test_active_does_not_have_idle_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING)
        row = SessionRow(session)
        assert not row.has_class("status-idle")
        assert not row.has_class("status-permission")

    def test_status_class_updates_on_session_change(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session1 = make_merged(session_id="abc", status=SessionStatus.THINKING)
        row = SessionRow(session1)
        assert row.has_class("status-active")

        session2 = make_merged(session_id="abc", status=SessionStatus.IDLE)
        row.update_session(session2)
        assert row.has_class("status-idle")
        assert not row.has_class("status-active")

    def test_terminated_has_no_status_bar_class(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.TERMINATED)
        row = SessionRow(session)
        assert not row.has_class("status-active")
        assert not row.has_class("status-permission")
        assert not row.has_class("status-idle")


class TestSessionRowPermissionRedBar:
    """WAITING_PERMISSION: red blinking bar + 'NEEDS HUMAN INTERVENTION' banner."""

    def test_permission_has_red_bar_class(self) -> None:
        """WAITING_PERMISSION should use status-permission class (red border via CSS)."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        assert row.has_class("status-permission")

    def test_permission_content_has_human_intervention_text(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        content = row._build_content()
        assert "NEEDS HUMAN INTERVENTION" in content

    def test_human_intervention_text_blinks(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION)
        row = SessionRow(session)
        content = row._build_content()
        # The intervention text should have blink markup
        assert "blink" in content
        assert "NEEDS HUMAN INTERVENTION" in content

    def test_non_permission_has_no_intervention_text(self) -> None:
        from monitorator.tui.session_row import SessionRow

        for status in [SessionStatus.THINKING, SessionStatus.IDLE, SessionStatus.EXECUTING]:
            session = make_merged(status=status, prompt=None)
            row = SessionRow(session)
            content = row._build_content()
            assert "NEEDS HUMAN INTERVENTION" not in content


class TestSessionRowLabels:
    """User labels appear on line 1 (right side); prompt always visible on line 2."""

    def test_user_label_shown_on_line_1(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="some prompt")
        with patch("monitorator.tui.session_row.get_label", return_value="login feature expansion"):
            row = SessionRow(session)
            content = row._build_content()
        assert "login feature expansion" in content
        lines = content.strip().split("\n")
        assert "login feature expansion" in lines[0]  # line 1

    def test_label_does_not_replace_prompt(self) -> None:
        """Both label (line 1) and prompt (line 2) should be visible."""
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="Build the monitor")
        with patch("monitorator.tui.session_row.get_label", return_value="my custom label"):
            row = SessionRow(session)
            content = row._build_content()
        lines = content.strip().split("\n")
        assert "my custom label" in lines[0]  # label on line 1
        assert "Build the monitor" in lines[1]  # prompt still on line 2

    def test_user_label_uses_label_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(prompt="something")
        with patch("monitorator.tui.session_row.get_label", return_value="my label"):
            row = SessionRow(session)
            content = row._build_content()
        assert "#aaaaff" in content  # label color

    def test_label_capped_at_30_chars(self) -> None:
        from monitorator.tui.session_row import SessionRow

        long_label = "A" * 50
        session = make_merged(prompt="test")
        with patch("monitorator.tui.session_row.get_label", return_value=long_label):
            row = SessionRow(session)
            content = row._build_content()
        # Should be truncated with ellipsis, not full 50 chars
        assert long_label not in content
        assert "A" * 29 in content  # 29 chars + ellipsis

    def test_no_label_shows_prompt_with_status_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt="Build things")
        # _no_labels fixture already patches get_label to return None
        row = SessionRow(session)
        content = row._build_content()
        assert "Build things" in content
        assert "#00ff66" in content  # thinking bright color for prompt text


class TestSessionRowActivityLine:
    """Line 3 shows latest activity from format_activity()."""

    def test_activity_shown_on_line_3(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(tool="Edit", tool_summary="file_path: src/app.py")
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert "Editing src/app.py" in lines[2]  # line 3

    def test_activity_uses_status_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            status=SessionStatus.EXECUTING,
            tool="Bash",
            tool_summary="command: npm test",
        )
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert "Running: npm test" in lines[2]
        assert "#777777" in lines[2]  # uniform grey for activity

    def test_compact_hides_activity(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(tool="Edit", tool_summary="file_path: src/app.py")
        row = SessionRow(session)
        row.set_compact(True)
        content = row._build_content()
        assert "Editing src/app.py" not in content

    def test_thinking_no_tool_shows_thinking_on_line_3(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(
            status=SessionStatus.THINKING,
            tool=None,
            tool_summary=None,
        )
        row = SessionRow(session)
        content = row._build_content()
        lines = content.strip().split("\n")
        assert "Thinking..." in lines[2]


class TestSessionRowStatusColors:
    """Status-specific colors should be present in the row content."""

    def test_thinking_has_green_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.THINKING, prompt="test")
        row = SessionRow(session)
        content = row._build_content()
        assert "#00ff66" in content

    def test_executing_has_blue_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.EXECUTING, prompt="test")
        row = SessionRow(session)
        content = row._build_content()
        assert "#3399ff" in content  # STATUS_COLORS for executing

    def test_idle_has_amber_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.IDLE, prompt="test")
        row = SessionRow(session)
        content = row._build_content()
        assert "#ffaa00" in content

    def test_permission_has_red_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.WAITING_PERMISSION, prompt="test")
        row = SessionRow(session)
        content = row._build_content()
        assert "#ff3333" in content

    def test_subagent_has_purple_color(self) -> None:
        from monitorator.tui.session_row import SessionRow

        session = make_merged(status=SessionStatus.SUBAGENT_RUNNING, prompt="test")
        row = SessionRow(session)
        content = row._build_content()
        assert "#cc66ff" in content
