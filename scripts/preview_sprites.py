"""Preview sprite rendering in the terminal using Rich markup and half-block characters.

Renders:
  1. The 16x16 rabbit sprite (3 animation frames) side by side
  2. Downscaled versions of the rabbit at 12x10, 10x8, and 8x6
  3. All 10 existing monitorator sprites for comparison

Usage:
    uv run python scripts/preview_sprites.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the src directory is on the path so we can import monitorator
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rich.console import Console

# ---------------------------------------------------------------------------
# Rabbit palette and frames
# ---------------------------------------------------------------------------

RABBIT_PALETTE: dict[int, str | None] = {
    0: None,        # transparent
    1: "#000000",   # outline black
    2: "#F8F8F8",   # body white
    3: "#FC7878",   # inner ear pink
    4: "#FFFFFF",   # eye highlight
    5: "#BCBCBC",   # whiskers gray
    6: "#E8E0D8",   # belly cream
}

RABBIT_FRAME_1: list[list[int]] = [
    [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 0, 1, 2, 1, 1, 1, 1, 2, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0],
    [0, 0, 1, 2, 4, 1, 2, 2, 2, 2, 1, 4, 2, 1, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 1, 0, 0],
    [0, 0, 1, 5, 2, 2, 3, 2, 2, 3, 2, 2, 5, 1, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 1, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 6, 6, 6, 6, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 6, 1, 0],
    [0, 0, 0, 0, 1, 2, 1, 0, 0, 1, 2, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0],
]

RABBIT_FRAME_2: list[list[int]] = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 0, 1, 2, 1, 1, 1, 1, 2, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0],
    [0, 0, 1, 2, 4, 1, 2, 2, 2, 2, 1, 4, 2, 1, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 1, 0, 0],
    [0, 0, 1, 5, 2, 2, 3, 2, 2, 3, 2, 2, 5, 1, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 1, 1, 0, 0, 0],
    [0, 0, 1, 2, 2, 6, 6, 6, 6, 6, 6, 2, 2, 1, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 6, 1],
    [0, 0, 0, 1, 2, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0],
]

RABBIT_FRAME_3: list[list[int]] = [
    [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 3, 1, 0, 0, 1, 3, 2, 1, 0, 0, 0],
    [0, 0, 0, 0, 1, 2, 1, 1, 1, 1, 2, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],
    [0, 0, 1, 2, 4, 1, 2, 2, 2, 2, 1, 4, 2, 1, 0, 0],
    [0, 0, 1, 2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 1, 0, 0],
    [0, 0, 0, 1, 2, 2, 3, 2, 2, 3, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 6, 6, 6, 6, 2, 2, 1, 0, 0, 0],
    [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 6, 1, 0],
    [0, 0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]

RABBIT_FRAMES: list[tuple[str, list[list[int]]]] = [
    ("Standing", RABBIT_FRAME_1),
    ("Crouched", RABBIT_FRAME_2),
    ("Jumping", RABBIT_FRAME_3),
]


# ---------------------------------------------------------------------------
# Generic half-block renderer for arbitrary-sized grids
# ---------------------------------------------------------------------------


def render_halfblock_lines(
    grid: list[list[int]],
    palette: dict[int, str | None],
) -> list[str]:
    """Render an NxM pixel grid into Rich markup lines using half-block characters.

    Pairs rows (0,1), (2,3), ... into output lines. If the grid has an odd
    number of rows, the last row is paired with a transparent row.

    Returns a list of Rich-markup strings (one per row pair).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    # Pad to even number of rows
    if rows % 2 != 0:
        padded = grid + [[0] * cols]
    else:
        padded = grid

    lines: list[str] = []
    for pair_idx in range(len(padded) // 2):
        top_row = padded[pair_idx * 2]
        bot_row = padded[pair_idx * 2 + 1]
        chars: list[str] = []
        for col in range(cols):
            tp = top_row[col]
            bp = bot_row[col]
            tc = palette.get(tp)
            bc = palette.get(bp)
            if tc is None and bc is None:
                chars.append(" ")
            elif tc is not None and bc is None:
                chars.append(f"[{tc}]\u2580[/]")
            elif tc is None and bc is not None:
                chars.append(f"[{bc}]\u2584[/]")
            elif tc == bc:
                chars.append(f"[{tc}]\u2588[/]")
            else:
                chars.append(f"[{tc} on {bc}]\u2580[/]")
        lines.append("".join(chars))
    return lines


# ---------------------------------------------------------------------------
# Nearest-neighbor downscaler
# ---------------------------------------------------------------------------


def downscale_nearest(
    grid: list[list[int]],
    target_width: int,
    target_height: int,
) -> list[list[int]]:
    """Downscale a pixel grid using nearest-neighbor sampling."""
    src_height = len(grid)
    src_width = len(grid[0]) if src_height > 0 else 0
    result: list[list[int]] = []
    for y in range(target_height):
        src_y = int(y * src_height / target_height)
        src_y = min(src_y, src_height - 1)
        row: list[int] = []
        for x in range(target_width):
            src_x = int(x * src_width / target_width)
            src_x = min(src_x, src_width - 1)
            row.append(grid[src_y][src_x])
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    console = Console()

    # ======================================================================
    # Section 1: Rabbit frames at full 16x16 resolution
    # ======================================================================
    console.print()
    console.print(
        "[bold yellow]===  Rabbit Sprite  ===  16x16 pixels  ===  "
        "8 output lines  ===[/]"
    )
    console.print()

    # Render each frame into lines
    all_frame_lines: list[list[str]] = []
    for label, frame in RABBIT_FRAMES:
        lines = render_halfblock_lines(frame, RABBIT_PALETTE)
        all_frame_lines.append(lines)

    # Print labels
    labels = [f"  {label:<18}" for label, _ in RABBIT_FRAMES]
    console.print("".join(labels))
    console.print()

    # Print frames side by side
    num_output_lines = len(all_frame_lines[0])
    for line_idx in range(num_output_lines):
        parts: list[str] = []
        for frame_lines in all_frame_lines:
            parts.append(f"  {frame_lines[line_idx]}  ")
        console.print("".join(parts))

    # ======================================================================
    # Section 2: Downscaled rabbit variants
    # ======================================================================
    console.print()
    console.print(
        "[bold yellow]===  Downscaled Versions (nearest-neighbor)  ===[/]"
    )
    console.print()

    target_sizes: list[tuple[int, int]] = [
        (12, 10),
        (10, 8),
        (8, 6),
    ]

    # Use frame 1 (standing) for downscale demos
    base_frame = RABBIT_FRAME_1

    scaled_renders: list[tuple[str, list[str]]] = []
    for tw, th in target_sizes:
        scaled = downscale_nearest(base_frame, tw, th)
        lines = render_halfblock_lines(scaled, RABBIT_PALETTE)
        label = f"{tw}x{th} ({tw}w x {th // 2}h)"
        scaled_renders.append((label, lines))

    # Also include the original for reference
    orig_lines = render_halfblock_lines(base_frame, RABBIT_PALETTE)
    all_renders = [("16x16 (original)", orig_lines)] + scaled_renders

    # Print labels
    max_output_lines = max(len(lines) for _, lines in all_renders)
    label_parts: list[str] = []
    for label, lines in all_renders:
        # Width = number of pixel columns + padding
        width = 16 + 4  # max visual width + padding
        label_parts.append(f"  {label:<{width}}")
    console.print("".join(label_parts))
    console.print()

    # Print side by side, padded to the tallest
    for line_idx in range(max_output_lines):
        parts = []
        for _, lines in all_renders:
            if line_idx < len(lines):
                rendered = lines[line_idx]
            else:
                rendered = ""
            parts.append(f"  {rendered}    ")
        console.print("".join(parts))

    # ======================================================================
    # Section 3: Existing monitorator sprites
    # ======================================================================
    console.print()
    console.print(
        "[bold yellow]===  Monitorator Sprites (6x8, from sprites.py)  ===[/]"
    )
    console.print()

    from monitorator.tui.sprites import (
        SPRITE_NAMES,
        SPRITE_PALETTES,
        SPRITE_TEMPLATES,
        render_sprite,
    )

    # Render each sprite
    sprite_renders: list[tuple[str, tuple[str, str, str]]] = []
    for idx, (name, grid, palette) in enumerate(
        zip(SPRITE_NAMES, SPRITE_TEMPLATES, SPRITE_PALETTES)
    ):
        line0, line1, line2 = render_sprite(grid, palette)
        sprite_renders.append((name, (line0, line1, line2)))

    # Print in rows of 5
    sprites_per_row = 5
    col_width = 14  # visual width for labels

    for row_start in range(0, len(sprite_renders), sprites_per_row):
        row_slice = sprite_renders[row_start : row_start + sprites_per_row]

        # Labels
        label_line = ""
        for name, _ in row_slice:
            label_line += f"  {name:<{col_width}}"
        console.print(label_line)
        console.print()

        # Sprite lines (3 lines each)
        for line_idx in range(3):
            parts = []
            for _, lines in row_slice:
                parts.append(f"  {lines[line_idx]}      ")
            console.print("".join(parts))

        console.print()

    # ======================================================================
    # Section 4: Side-by-side comparison -- rabbit downscaled to 8x6
    #            next to existing monitorator sprites
    # ======================================================================
    console.print()
    console.print(
        "[bold yellow]===  Comparison: Rabbit at 8x6 vs Monitorator Sprites  ===[/]"
    )
    console.print()

    rabbit_8x6 = downscale_nearest(base_frame, 8, 6)
    rabbit_lines = render_halfblock_lines(rabbit_8x6, RABBIT_PALETTE)

    # Pick a few sprites to compare against
    compare_indices = [0, 1, 4, 5, 9]  # Plumber, Ghost, Robot, Frog, Monkey
    compare_items: list[tuple[str, tuple[str, ...]]] = [
        ("Rabbit 8x6", tuple(rabbit_lines)),
    ]
    for idx in compare_indices:
        line0, line1, line2 = render_sprite(
            SPRITE_TEMPLATES[idx], SPRITE_PALETTES[idx]
        )
        compare_items.append((SPRITE_NAMES[idx], (line0, line1, line2)))

    # Labels
    label_line = ""
    for name, _ in compare_items:
        label_line += f"  {name:<{col_width}}"
    console.print(label_line)
    console.print()

    # Lines (3 lines each)
    max_lines = max(len(lines) for _, lines in compare_items)
    for line_idx in range(max_lines):
        parts = []
        for _, lines in compare_items:
            if line_idx < len(lines):
                parts.append(f"  {lines[line_idx]}      ")
            else:
                parts.append(f"  {'':8}      ")
        console.print("".join(parts))

    console.print()


if __name__ == "__main__":
    main()
