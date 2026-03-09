from __future__ import annotations

import re

import pytest

from monitorator.models import SessionStatus


def _strip_markup(text: str) -> str:
    """Remove Rich markup tags, leaving only visible characters."""
    return re.sub(r"\[[^\]]*\]", "", text)


# -- render_sprite -----------------------------------------------------------


class TestRenderSprite:
    def test_returns_five_strings(self) -> None:
        from monitorator.tui.sprites import render_sprite

        grid = [
            [0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
            [0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
            [1, 2, 3, 2, 2, 3, 2, 2, 2, 1, 0, 0],
            [0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
            [0, 0, 1, 2, 2, 1, 2, 2, 0, 0, 0, 0],
            [0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
        ]
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert isinstance(result, tuple)
        assert len(result) == 5
        for line in result:
            assert isinstance(line, str)

    def test_transparent_pixels_produce_spaces(self) -> None:
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        for line in result:
            assert line == " " * 12

    def test_full_block_same_color(self) -> None:
        """When top and bottom pixel are the same non-zero color, produce full block."""
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        grid[0][3] = 2
        grid[1][3] = 2
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert "\u2588" in result[0]  # full block

    def test_upper_half_block(self) -> None:
        """When top pixel is colored and bottom is transparent, produce upper half block."""
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        grid[0][3] = 2
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert "\u2580" in result[0]  # upper half block

    def test_lower_half_block(self) -> None:
        """When top pixel is transparent and bottom is colored, produce lower half block."""
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        grid[1][3] = 2
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert "\u2584" in result[0]  # lower half block

    def test_two_color_produces_upper_on_lower(self) -> None:
        """When top and bottom pixels are different colors, use 'on' syntax with upper half."""
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        grid[0][3] = 1
        grid[1][3] = 2
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert "\u2580" in result[0]
        assert " on " in result[0]

    def test_output_visual_width_is_12(self) -> None:
        """Each line should have exactly 12 visible characters when markup is stripped."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES, SPRITE_PALETTES, render_sprite

        for i, template in enumerate(SPRITE_TEMPLATES):
            result = render_sprite(template, SPRITE_PALETTES[i])
            for j, line in enumerate(result):
                visible = _strip_markup(line)
                assert len(visible) == 12, (
                    f"Template {i} line {j} has {len(visible)} visible chars, expected 12"
                )

    def test_all_transparent_grid_has_no_markup(self) -> None:
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        for line in result:
            assert "[" not in line

    def test_full_grid_produces_all_full_blocks(self) -> None:
        """A grid where every pair is the same color produces full blocks only."""
        from monitorator.tui.sprites import render_sprite

        grid = [[2] * 12 for _ in range(10)]
        palette = {1: "#333333", 2: "#ffcc00", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        for line in result:
            visible = _strip_markup(line)
            assert visible == "\u2588" * 12

    def test_palette_colors_appear_in_markup(self) -> None:
        """The palette hex colors should appear in the Rich markup output."""
        from monitorator.tui.sprites import render_sprite

        grid = [[0] * 12 for _ in range(10)]
        grid[0][3] = 2
        palette = {1: "#333333", 2: "#abcdef", 3: "#ffffff", 4: "#ff0000", 5: "#00ff00", 6: "#0000ff"}
        result = render_sprite(grid, palette)
        assert "#abcdef" in result[0]


# -- SPRITE_TEMPLATES --------------------------------------------------------


class TestSpriteTemplates:
    def test_exactly_10_templates(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        assert len(SPRITE_TEMPLATES) == 22

    def test_all_templates_are_10_rows_12_cols(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            assert len(template) == 10, f"Template {i} has {len(template)} rows, expected 10"
            for r, row in enumerate(template):
                assert len(row) == 12, f"Template {i} row {r} has {len(row)} cols, expected 12"

    def test_all_values_in_range_0_to_6(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            for r, row in enumerate(template):
                for c, val in enumerate(row):
                    assert 0 <= val <= 6, (
                        f"Template {i} [{r}][{c}] = {val}, expected 0-6"
                    )

    def test_templates_are_not_all_identical(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        first = SPRITE_TEMPLATES[0]
        different_count = sum(1 for t in SPRITE_TEMPLATES[1:] if t != first)
        assert different_count >= 8, "Expected at least 8 templates to differ from the first"

    def test_no_template_is_all_transparent(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            has_pixels = any(val != 0 for row in template for val in row)
            assert has_pixels, f"Template {i} is entirely transparent"

    def test_each_template_uses_at_least_2_colors(self) -> None:
        """Each template should use at least 2 distinct non-zero color slots."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            colors_used = {val for row in template for val in row if val != 0}
            assert len(colors_used) >= 2, (
                f"Template {i} uses only {colors_used} (expected at least 2 non-zero colors)"
            )

    def test_templates_are_list_of_lists_of_ints(self) -> None:
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            assert isinstance(template, list), f"Template {i} is not a list"
            for r, row in enumerate(template):
                assert isinstance(row, list), f"Template {i} row {r} is not a list"
                for c, val in enumerate(row):
                    assert isinstance(val, int), (
                        f"Template {i} [{r}][{c}] is {type(val).__name__}, expected int"
                    )

    def test_every_template_uses_color_slot_2(self) -> None:
        """Color slot 2 is the body color; every sprite should use it."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES

        for i, template in enumerate(SPRITE_TEMPLATES):
            has_body = any(val == 2 for row in template for val in row)
            assert has_body, f"Template {i} never uses color slot 2 (body)"


# -- SPRITE_PALETTES --------------------------------------------------------


class TestSpritePalettes:
    def test_exactly_10_palettes(self) -> None:
        from monitorator.tui.sprites import SPRITE_PALETTES

        assert len(SPRITE_PALETTES) == 22

    def test_palettes_have_keys_1_through_6(self) -> None:
        from monitorator.tui.sprites import SPRITE_PALETTES

        for i, pal in enumerate(SPRITE_PALETTES):
            for key in range(1, 7):
                assert key in pal, f"Palette {i} missing key {key}"

    def test_palette_values_are_hex_colors(self) -> None:
        from monitorator.tui.sprites import SPRITE_PALETTES

        hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for i, pal in enumerate(SPRITE_PALETTES):
            for key, color in pal.items():
                assert hex_re.match(color), (
                    f"Palette {i} key {key}: {color!r} is not a valid hex color"
                )

    def test_palettes_are_visually_distinct(self) -> None:
        """At least 8 palettes should have different primary body colors (slot 2)."""
        from monitorator.tui.sprites import SPRITE_PALETTES

        body_colors = {pal[2] for pal in SPRITE_PALETTES}
        assert len(body_colors) >= 8, (
            f"Only {len(body_colors)} distinct body colors, expected at least 8"
        )

    def test_palettes_cover_all_template_colors(self) -> None:
        """Each palette should cover every non-zero color used in its template."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES, SPRITE_PALETTES

        for i in range(len(SPRITE_TEMPLATES)):
            template = SPRITE_TEMPLATES[i]
            palette = SPRITE_PALETTES[i]
            colors_used = {val for row in template for val in row if val != 0}
            for color in colors_used:
                assert color in palette, (
                    f"Template {i} uses color {color} but palette {i} lacks it"
                )


# -- SPRITE_NAMES ------------------------------------------------------------


class TestSpriteNames:
    def test_exactly_10_names(self) -> None:
        from monitorator.tui.sprites import SPRITE_NAMES

        assert len(SPRITE_NAMES) == 22

    def test_names_are_strings(self) -> None:
        from monitorator.tui.sprites import SPRITE_NAMES

        for name in SPRITE_NAMES:
            assert isinstance(name, str)
            assert len(name) > 0


# -- get_sprite_frame --------------------------------------------------------


class TestGetSpriteFrame:
    def test_returns_five_strings_for_all_statuses(self) -> None:
        from monitorator.tui.sprites import get_sprite_frame

        for status in SessionStatus:
            result = get_sprite_frame(row_index=1, status=status, anim_frame=0)
            assert isinstance(result, tuple), f"Status {status.value} did not return a tuple"
            assert len(result) == 5, f"Status {status.value} returned {len(result)}-tuple"
            for i, line in enumerate(result):
                assert isinstance(line, str), f"Status {status.value} line {i} is not str"

    def test_idle_is_static(self) -> None:
        """IDLE frames should not change with anim_frame."""
        from monitorator.tui.sprites import get_sprite_frame

        frame0 = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=0)
        frame7 = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=7)
        assert frame0 == frame7

    def test_unknown_is_static(self) -> None:
        """UNKNOWN should behave like IDLE (static)."""
        from monitorator.tui.sprites import get_sprite_frame

        frame0 = get_sprite_frame(row_index=1, status=SessionStatus.UNKNOWN, anim_frame=0)
        frame3 = get_sprite_frame(row_index=1, status=SessionStatus.UNKNOWN, anim_frame=3)
        assert frame0 == frame3

    def test_thinking_animates(self) -> None:
        """THINKING should produce different output at different anim_frame values."""
        from monitorator.tui.sprites import get_sprite_frame

        frame0 = get_sprite_frame(row_index=1, status=SessionStatus.THINKING, anim_frame=0)
        frame1 = get_sprite_frame(row_index=1, status=SessionStatus.THINKING, anim_frame=1)
        assert frame0 != frame1

    def test_executing_animates(self) -> None:
        """EXECUTING should produce different output at different anim_frame values."""
        from monitorator.tui.sprites import get_sprite_frame

        frame0 = get_sprite_frame(row_index=1, status=SessionStatus.EXECUTING, anim_frame=0)
        frame1 = get_sprite_frame(row_index=1, status=SessionStatus.EXECUTING, anim_frame=1)
        assert frame0 != frame1

    def test_permission_strobes(self) -> None:
        """WAITING_PERMISSION alternates between content and blank."""
        from monitorator.tui.sprites import get_sprite_frame

        frame0 = get_sprite_frame(
            row_index=1, status=SessionStatus.WAITING_PERMISSION, anim_frame=0,
        )
        frame1 = get_sprite_frame(
            row_index=1, status=SessionStatus.WAITING_PERMISSION, anim_frame=1,
        )
        frame0_has_content = any(line.strip() != "" for line in frame0)
        frame1_has_content = any(line.strip() != "" for line in frame1)
        # Frame 0 is visible, frame 1 is blank
        assert frame0_has_content
        assert not frame1_has_content

    def test_permission_blank_frame_is_twelve_spaces(self) -> None:
        """The blank frame in permission strobe should be exactly 12 spaces per line."""
        from monitorator.tui.sprites import get_sprite_frame

        result = get_sprite_frame(
            row_index=1, status=SessionStatus.WAITING_PERMISSION, anim_frame=1,
        )
        for i, line in enumerate(result):
            assert line == " " * 12, f"Blank frame line {i}: {line!r}"

    def test_terminated_has_dim(self) -> None:
        """TERMINATED output should contain 'dim' markup."""
        from monitorator.tui.sprites import get_sprite_frame

        result = get_sprite_frame(
            row_index=1, status=SessionStatus.TERMINATED, anim_frame=0,
        )
        combined = "".join(result)
        assert "dim" in combined

    def test_terminated_wraps_with_dim_tags(self) -> None:
        """TERMINATED output should wrap each line in [dim]...[/] tags."""
        from monitorator.tui.sprites import get_sprite_frame

        result = get_sprite_frame(
            row_index=1, status=SessionStatus.TERMINATED, anim_frame=0,
        )
        for i, line in enumerate(result):
            assert line.startswith("[dim]") and line.endswith("[/]"), (
                f"TERMINATED line {i}: {line!r}"
            )

    def test_subagent_pulse(self) -> None:
        """SUBAGENT_RUNNING should have different frames (brightness varies)."""
        from monitorator.tui.sprites import get_sprite_frame

        frames = [
            get_sprite_frame(
                row_index=1, status=SessionStatus.SUBAGENT_RUNNING, anim_frame=f,
            )
            for f in range(8)
        ]
        # The bright (frame 1-3) frames should differ from base (frame 0)
        assert frames[0] != frames[1], "Base and bright frames should differ"
        assert frames[0] != frames[2], "Base and brighter frames should differ"

    def test_different_row_indexes_produce_different_sprites(self) -> None:
        """Different row indexes map to different sprite templates."""
        from monitorator.tui.sprites import get_sprite_frame

        sprite1 = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=0)
        sprite2 = get_sprite_frame(row_index=2, status=SessionStatus.IDLE, anim_frame=0)
        assert sprite1 != sprite2

    def test_row_index_wraps_around_templates(self) -> None:
        """Row indexes beyond 22 should wrap to the beginning."""
        from monitorator.tui.sprites import get_sprite_frame

        sprite_1 = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=0)
        sprite_23 = get_sprite_frame(row_index=23, status=SessionStatus.IDLE, anim_frame=0)
        assert sprite_1 == sprite_23

    def test_thinking_has_8_frame_sway_cycle(self) -> None:
        """THINKING animation uses an 8-frame horizontal sway (no vertical jump)."""
        from monitorator.tui.sprites import get_sprite_frame

        frames = [
            get_sprite_frame(
                row_index=1, status=SessionStatus.THINKING, anim_frame=f,
            )
            for f in range(8)
        ]
        # Sway pattern: base, right, right, base, base, left, left, base
        assert frames[0] == frames[3]  # base == base
        assert frames[1] == frames[2]  # right == right
        assert frames[5] == frames[6]  # left == left
        assert frames[0] == frames[7]  # base == base
        # At least 3 distinct frames (base, right, left)
        unique = len(set(frames))
        assert unique >= 3, f"Expected at least 3 distinct THINKING frames, got {unique}"

    def test_thinking_frame_0_is_base_grid(self) -> None:
        """THINKING at phase 0 should render the base (unmodified) grid, same as IDLE."""
        from monitorator.tui.sprites import get_sprite_frame

        base = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=0)
        think_0 = get_sprite_frame(row_index=1, status=SessionStatus.THINKING, anim_frame=0)
        assert base == think_0

    def test_executing_frame_0_is_base_grid(self) -> None:
        """EXECUTING at phase 0 should render the base (unmodified) grid."""
        from monitorator.tui.sprites import get_sprite_frame

        base = get_sprite_frame(row_index=1, status=SessionStatus.IDLE, anim_frame=0)
        exec_0 = get_sprite_frame(row_index=1, status=SessionStatus.EXECUTING, anim_frame=0)
        assert base == exec_0

    def test_all_statuses_produce_12_wide_visible(self) -> None:
        """Every status should produce lines with 12 visible characters."""
        from monitorator.tui.sprites import get_sprite_frame

        for status in SessionStatus:
            result = get_sprite_frame(row_index=1, status=status, anim_frame=0)
            for i, line in enumerate(result):
                visible = _strip_markup(line)
                assert len(visible) == 12, (
                    f"Status {status.value} line {i} has {len(visible)} visible chars"
                )

    def test_permission_strobe_pattern(self) -> None:
        """Permission strobe follows: visible, blank, visible, blank, visible, visible, blank, blank."""
        from monitorator.tui.sprites import get_sprite_frame

        expected_visible = [True, False, True, False, True, True, False, False]
        for frame_idx, should_be_visible in enumerate(expected_visible):
            result = get_sprite_frame(
                row_index=1, status=SessionStatus.WAITING_PERMISSION, anim_frame=frame_idx,
            )
            has_content = any(line.strip() != "" for line in result)
            assert has_content == should_be_visible, (
                f"Frame {frame_idx}: expected visible={should_be_visible}, got {has_content}"
            )

    def test_subagent_pulse_pattern(self) -> None:
        """SUBAGENT_RUNNING pulse: frames 0 and 5 are base, frame 6 is dimmed."""
        from monitorator.tui.sprites import get_sprite_frame

        base = get_sprite_frame(row_index=1, status=SessionStatus.SUBAGENT_RUNNING, anim_frame=0)
        frame5 = get_sprite_frame(row_index=1, status=SessionStatus.SUBAGENT_RUNNING, anim_frame=5)
        frame6 = get_sprite_frame(row_index=1, status=SessionStatus.SUBAGENT_RUNNING, anim_frame=6)
        assert base == frame5, "Frames 0 and 5 should both be base brightness"
        assert base != frame6, "Frame 6 (dim) should differ from base"


# -- darken ------------------------------------------------------------------


class TestDarken:
    def test_returns_valid_hex(self) -> None:
        from monitorator.tui.sprites import darken

        result = darken("#ffcc00", 0.4)
        assert result.startswith("#")
        assert len(result) == 7

    def test_factor_zero_is_black(self) -> None:
        from monitorator.tui.sprites import darken

        assert darken("#ffcc00", 0.0) == "#000000"

    def test_factor_zero_on_white(self) -> None:
        from monitorator.tui.sprites import darken

        assert darken("#ffffff", 0.0) == "#000000"

    def test_factor_one_unchanged(self) -> None:
        from monitorator.tui.sprites import darken

        assert darken("#ffcc00", 1.0) == "#ffcc00"

    def test_factor_one_on_white(self) -> None:
        from monitorator.tui.sprites import darken

        assert darken("#ffffff", 1.0) == "#ffffff"

    def test_darkened_values_lower(self) -> None:
        """All R, G, B components should be less than or equal to the original."""
        from monitorator.tui.sprites import darken

        original = "#ffcc00"
        darkened = darken(original, 0.5)
        for i in range(3):
            orig_val = int(original[1 + i * 2: 3 + i * 2], 16)
            dark_val = int(darkened[1 + i * 2: 3 + i * 2], 16)
            assert dark_val <= orig_val, (
                f"Channel {i}: darkened {dark_val} > original {orig_val}"
            )

    def test_darkened_rgb_proportional(self) -> None:
        """Darkening should multiply each channel by the factor."""
        from monitorator.tui.sprites import darken

        result = darken("#ff8040", 0.5)
        r = int(result[1:3], 16)
        g = int(result[3:5], 16)
        b = int(result[5:7], 16)
        assert r == int(0xFF * 0.5)
        assert g == int(0x80 * 0.5)
        assert b == int(0x40 * 0.5)

    def test_darken_black_stays_black(self) -> None:
        from monitorator.tui.sprites import darken

        assert darken("#000000", 0.5) == "#000000"

    def test_result_is_lowercase_hex(self) -> None:
        from monitorator.tui.sprites import darken

        result = darken("#AABBCC", 0.5)
        hex_part = result[1:]
        assert hex_part == hex_part.lower()

    def test_various_factors(self) -> None:
        """Darker factor produces darker results monotonically."""
        from monitorator.tui.sprites import darken

        color = "#cc8844"
        prev_brightness = float("inf")
        for factor in [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]:
            result = darken(color, factor)
            brightness = sum(int(result[1 + i * 2: 3 + i * 2], 16) for i in range(3))
            assert brightness <= prev_brightness, (
                f"Factor {factor} produced brightness {brightness} > previous {prev_brightness}"
            )
            prev_brightness = brightness


# -- brighten ----------------------------------------------------------------


class TestBrighten:
    def test_returns_valid_hex(self) -> None:
        from monitorator.tui.sprites import brighten

        result = brighten("#333333", 0.5)
        assert result.startswith("#")
        assert len(result) == 7

    def test_factor_zero_unchanged(self) -> None:
        from monitorator.tui.sprites import brighten

        assert brighten("#ffcc00", 0.0) == "#ffcc00"

    def test_factor_one_is_white(self) -> None:
        from monitorator.tui.sprites import brighten

        assert brighten("#000000", 1.0) == "#ffffff"
        assert brighten("#ff0000", 1.0) == "#ffffff"

    def test_brightened_values_higher(self) -> None:
        """All R, G, B components should be >= the original."""
        from monitorator.tui.sprites import brighten

        original = "#334455"
        brightened = brighten(original, 0.5)
        for i in range(3):
            orig_val = int(original[1 + i * 2: 3 + i * 2], 16)
            bright_val = int(brightened[1 + i * 2: 3 + i * 2], 16)
            assert bright_val >= orig_val, (
                f"Channel {i}: brightened {bright_val} < original {orig_val}"
            )

    def test_brighten_white_stays_white(self) -> None:
        from monitorator.tui.sprites import brighten

        assert brighten("#ffffff", 0.5) == "#ffffff"


# -- get_sprite_color --------------------------------------------------------


class TestGetSpriteColor:
    def test_returns_hex_color(self) -> None:
        from monitorator.tui.sprites import get_sprite_color

        color = get_sprite_color(1)
        assert color.startswith("#")
        assert len(color) == 7

    def test_returns_palette_slot_2(self) -> None:
        """get_sprite_color should return the primary body color (palette slot 2)."""
        from monitorator.tui.sprites import get_sprite_color, SPRITE_PALETTES

        for i in range(len(SPRITE_PALETTES)):
            expected = SPRITE_PALETTES[i][2]
            actual = get_sprite_color(i + 1)
            assert actual == expected, (
                f"Row {i + 1}: expected {expected}, got {actual}"
            )

    def test_wraps_around(self) -> None:
        from monitorator.tui.sprites import get_sprite_color

        color1 = get_sprite_color(1)
        color23 = get_sprite_color(23)
        assert color1 == color23

    def test_at_least_8_distinct_colors(self) -> None:
        from monitorator.tui.sprites import get_sprite_color

        colors = {get_sprite_color(i) for i in range(1, 23)}
        assert len(colors) >= 8


# -- sprite_index_for_session ------------------------------------------------


class TestSpriteIndexForSession:
    def test_returns_int_in_range(self) -> None:
        from monitorator.tui.sprites import sprite_index_for_session, SPRITE_TEMPLATES

        idx = sprite_index_for_session("abc-123")
        assert isinstance(idx, int)
        assert 0 <= idx < len(SPRITE_TEMPLATES)

    def test_stable_for_same_session(self) -> None:
        """Same session_id always produces the same index."""
        from monitorator.tui.sprites import sprite_index_for_session

        idx1 = sprite_index_for_session("session-abc")
        idx2 = sprite_index_for_session("session-abc")
        assert idx1 == idx2

    def test_different_sessions_can_differ(self) -> None:
        """Different session_ids should generally produce different indices."""
        from monitorator.tui.sprites import sprite_index_for_session

        indices = {sprite_index_for_session(f"session-{i}") for i in range(50)}
        assert len(indices) >= 5, "Expected variety across 50 sessions"

    def test_skips_ghost_index(self) -> None:
        """Index 1 (Ghost) is reserved for the header — sessions should never get it."""
        from monitorator.tui.sprites import sprite_index_for_session

        for i in range(100):
            idx = sprite_index_for_session(f"test-session-{i}")
            assert idx != 1, f"Session test-session-{i} got Ghost index 1"

    def test_deterministic_across_calls(self) -> None:
        """Must use a deterministic hash (not Python's randomized hash())."""
        from monitorator.tui.sprites import sprite_index_for_session

        # These specific session IDs should always map to the same indices
        # regardless of PYTHONHASHSEED
        idx_a = sprite_index_for_session("session-deterministic-test-a")
        idx_b = sprite_index_for_session("session-deterministic-test-b")
        # Call again — must be identical
        assert sprite_index_for_session("session-deterministic-test-a") == idx_a
        assert sprite_index_for_session("session-deterministic-test-b") == idx_b


# -- get_sprite_frame_by_idx / get_sprite_color_by_idx ---------------------


class TestDirectIndexAPI:
    def test_get_sprite_frame_by_idx(self) -> None:
        """get_sprite_frame should accept sprite_idx directly."""
        from monitorator.tui.sprites import get_sprite_frame, SPRITE_TEMPLATES

        # Pass sprite_idx=5 directly
        result = get_sprite_frame(sprite_idx=5, status=SessionStatus.IDLE, anim_frame=0)
        assert isinstance(result, tuple)
        assert len(result) == 5

    def test_get_sprite_color_by_idx(self) -> None:
        """get_sprite_color should accept sprite_idx directly."""
        from monitorator.tui.sprites import get_sprite_color, SPRITE_PALETTES

        color = get_sprite_color(sprite_idx=5)
        assert color == SPRITE_PALETTES[5][2]

    def test_sprite_idx_overrides_row_index(self) -> None:
        """When sprite_idx is given, row_index should be ignored."""
        from monitorator.tui.sprites import get_sprite_frame

        # row_index=1 would normally give sprite 0, but sprite_idx=5 forces sprite 5
        result_by_idx = get_sprite_frame(sprite_idx=5, status=SessionStatus.IDLE, anim_frame=0)
        result_by_row = get_sprite_frame(row_index=6, status=SessionStatus.IDLE, anim_frame=0)
        # row_index=6 → sprite_idx=(6-1)%22=5, so they should match
        assert result_by_idx == result_by_row


# -- _shift_grid_left / _shift_grid_right -----------------------------------


class TestShiftGridLeft:
    def test_shifts_columns_left_by_one(self) -> None:
        from monitorator.tui.sprites import _shift_grid_left

        grid = [[c for c in range(12)] for _ in range(10)]
        result = _shift_grid_left(grid)
        # Each row shifted left: [1,2,3,...,11,0]
        assert result[0][0] == 1
        assert result[0][10] == 11
        assert result[0][11] == 0  # rightmost becomes transparent

    def test_rightmost_column_is_transparent(self) -> None:
        from monitorator.tui.sprites import _shift_grid_left

        grid = [[1] * 12 for _ in range(10)]
        result = _shift_grid_left(grid)
        for row in result:
            assert row[11] == 0


class TestShiftGridRight:
    def test_shifts_columns_right_by_one(self) -> None:
        from monitorator.tui.sprites import _shift_grid_right

        grid = [[c for c in range(12)] for _ in range(10)]
        result = _shift_grid_right(grid)
        # Each row shifted right: [0,0,1,2,...,10]
        assert result[0][0] == 0  # leftmost becomes transparent
        assert result[0][1] == 0  # was column 0
        assert result[0][2] == 1

    def test_leftmost_column_is_transparent(self) -> None:
        from monitorator.tui.sprites import _shift_grid_right

        grid = [[1] * 12 for _ in range(10)]
        result = _shift_grid_right(grid)
        for row in result:
            assert row[0] == 0


# -- _walk_frame -------------------------------------------------------------


class TestWalkFrame:
    def test_phase_0_is_base_grid(self) -> None:
        """Phase 0 returns the unmodified base grid."""
        from monitorator.tui.sprites import _walk_frame

        grid = [[0] * 12 for _ in range(10)]
        grid[9] = [1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 3, 0]
        result = _walk_frame(grid, 0)
        assert len(result) == 10

    def test_upper_rows_unchanged(self) -> None:
        """Walk frame should only modify the bottom 2 rows."""
        from monitorator.tui.sprites import _walk_frame

        grid = [[i + 1] * 12 for i in range(10)]
        result = _walk_frame(grid, 1)
        for i in range(8):  # rows 0-7 unchanged
            assert result[i] == grid[i]

    def test_does_not_mutate_original(self) -> None:
        """Walk frame should return a new grid, not mutate the original."""
        from monitorator.tui.sprites import _walk_frame

        grid = [[0] * 12 for _ in range(10)]
        grid[9] = [1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 3, 0]
        original_bottom = grid[9][:]
        _walk_frame(grid, 1)
        assert grid[9] == original_bottom

    def test_different_phases_differ(self) -> None:
        from monitorator.tui.sprites import _walk_frame

        grid = [[0] * 12 for _ in range(10)]
        grid[8] = [0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0]
        grid[9] = [0, 0, 6, 6, 0, 0, 0, 0, 6, 6, 0, 0]
        phase1 = _walk_frame(grid, 1)
        phase3 = _walk_frame(grid, 3)
        assert phase1[8] != phase3[8] or phase1[9] != phase3[9]


# -- Integration: full pipeline tests ---------------------------------------


class TestIntegration:
    def test_all_templates_render_without_error(self) -> None:
        """Every template should render cleanly with its own palette."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES, SPRITE_PALETTES, render_sprite

        for i, template in enumerate(SPRITE_TEMPLATES):
            result = render_sprite(template, SPRITE_PALETTES[i])
            assert isinstance(result, tuple)
            assert len(result) == 5

    def test_all_statuses_all_frames_all_templates(self) -> None:
        """Stress test: every combination of template, status, and frame produces output."""
        from monitorator.tui.sprites import get_sprite_frame

        for row_idx in range(1, 23):
            for status in SessionStatus:
                for frame in range(8):
                    result = get_sprite_frame(
                        row_index=row_idx, status=status, anim_frame=frame,
                    )
                    assert isinstance(result, tuple)
                    assert len(result) == 5

    def test_rendered_sprites_are_non_trivial(self) -> None:
        """Every template should produce at least some visible (non-space) content."""
        from monitorator.tui.sprites import SPRITE_TEMPLATES, SPRITE_PALETTES, render_sprite

        for i, template in enumerate(SPRITE_TEMPLATES):
            result = render_sprite(template, SPRITE_PALETTES[i])
            visible = "".join(_strip_markup(line) for line in result)
            assert visible.strip() != "", f"Template {i} produces only spaces"

    def test_subagent_cycle_length_is_8(self) -> None:
        """SUBAGENT_RUNNING has an 8-frame cycle."""
        from monitorator.tui.sprites import get_sprite_frame

        frames = [
            get_sprite_frame(
                row_index=1, status=SessionStatus.SUBAGENT_RUNNING, anim_frame=f,
            )
            for f in range(16)
        ]
        # Frames 0-7 should equal frames 8-15
        for i in range(8):
            assert frames[i] == frames[i + 8], (
                f"Subagent frame {i} != frame {i + 8}, cycle is not 8"
            )

    def test_executing_walk_has_8_frame_cycle(self) -> None:
        """EXECUTING walk cycles through twice in 8 frames."""
        from monitorator.tui.sprites import get_sprite_frame

        frames = [
            get_sprite_frame(
                row_index=1, status=SessionStatus.EXECUTING, anim_frame=f,
            )
            for f in range(8)
        ]
        # 4 positions repeated: frame 0 == frame 4, etc.
        for i in range(4):
            assert frames[i] == frames[i + 4], (
                f"Walk frame {i} != frame {i + 4}"
            )
