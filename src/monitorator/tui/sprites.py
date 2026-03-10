from __future__ import annotations

import hashlib

from monitorator.models import SessionStatus

# ============================================================================
# NES-style 8-bit sprite system for the Monitorator TUI
#
# Each sprite is a 10-row x 12-column pixel grid with values 0-6.
# 0 = transparent, 1-6 = palette color indices.
# Each character has a fixed 6-color palette using actual NES hex values.
#
# Rendered via half-block characters: each text line = 2 pixel rows,
# so 10 rows -> 5 rendered lines, each 12 chars wide.
#
# Palette slot convention:
#   1 = outline (usually black)
#   2 = primary body color
#   3 = secondary / accent color
#   4 = detail color (eyes, highlights)
#   5 = skin / face / special
#   6 = shadow / extra detail
# ============================================================================


# -- Color Utility -----------------------------------------------------------


def darken(hex_color: str, factor: float) -> str:
    """Darken a hex color by a factor (0.0 = black, 1.0 = unchanged)."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def brighten(hex_color: str, factor: float) -> str:
    """Brighten a hex color by a factor (0.0 = unchanged, 1.0 = white)."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = max(0, min(255, r + int((255 - r) * factor)))
    g = max(0, min(255, g + int((255 - g) * factor)))
    b = max(0, min(255, b + int((255 - b) * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


# -- 10 Sprite Templates (10 rows x 12 columns, values 0-6) -----------------
#
# High-resolution sprites with recognizable arcade character shapes.
# 12 pixels wide x 10 pixels tall -> 12 chars x 5 rendered lines.

SPRITE_TEMPLATES: list[list[list[int]]] = [
    # -- 0: Plumber -----------------------------------------------------------
    # Red cap, skin face, cream mustache, red shirt + cream overalls, dark boots
    [
        [0, 0, 0, 0, 1, 2, 2, 2, 1, 0, 0, 0],  # cap top
        [0, 0, 0, 1, 2, 2, 2, 2, 2, 1, 0, 0],  # cap wider
        [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],  # cap brim
        [0, 0, 1, 5, 5, 4, 5, 4, 5, 5, 1, 0],  # face: skin + eyes
        [0, 0, 1, 5, 3, 3, 3, 3, 3, 5, 1, 0],  # mustache
        [0, 0, 0, 1, 5, 5, 5, 5, 5, 1, 0, 0],  # chin
        [0, 0, 1, 2, 2, 3, 3, 3, 2, 2, 1, 0],  # shirt + overalls
        [0, 0, 1, 2, 3, 3, 3, 3, 3, 2, 1, 0],  # overalls wider
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # legs
        [0, 0, 1, 6, 6, 0, 0, 6, 6, 1, 0, 0],  # dark boots
    ],
    # -- 1: Ghost -------------------------------------------------------------
    # Round dome, big white eyes with blue pupils, wavy bottom edge
    [
        [0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0],  # dome top
        [0, 0, 0, 2, 2, 2, 2, 2, 2, 0, 0, 0],  # dome wider
        [0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0],  # dome widest
        [0, 2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 0],  # white eyes
        [0, 2, 2, 3, 4, 2, 2, 3, 4, 2, 2, 0],  # blue pupils
        [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0],  # body
        [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0],  # body
        [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0],  # body lower
        [0, 2, 0, 2, 2, 0, 0, 2, 2, 0, 2, 0],  # wavy bottom
        [0, 2, 0, 0, 2, 0, 0, 2, 0, 0, 2, 0],  # wavy tips
    ],
    # -- 2: Knight ------------------------------------------------------------
    # Helmet plume on top, visor slit, blue armor, dark boots
    [
        [0, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 0],  # plume top
        [0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0],  # plume wider
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # helmet top
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # helmet wider
        [0, 0, 1, 1, 4, 1, 1, 4, 1, 1, 0, 0],  # visor slit
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # helmet bottom
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # chest plate
        [0, 1, 6, 1, 2, 4, 4, 2, 1, 6, 1, 0],  # arms + buttons
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # legs
        [0, 0, 1, 6, 6, 0, 0, 6, 6, 1, 0, 0],  # dark boots
    ],
    # -- 3: Ninja -------------------------------------------------------------
    # Masked face with visible eyes, headband accent, slim purple body
    [
        [0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0],  # head top
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # head wider
        [0, 0, 1, 2, 3, 3, 3, 3, 2, 1, 0, 0],  # headband
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # mask top
        [0, 0, 1, 5, 4, 1, 1, 4, 5, 1, 0, 0],  # eyes through mask
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # mask bottom
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # torso
        [0, 3, 1, 2, 2, 3, 3, 2, 2, 1, 3, 0],  # sash + stars
        [0, 0, 1, 2, 2, 0, 0, 2, 2, 1, 0, 0],  # legs
        [0, 0, 0, 6, 6, 0, 0, 6, 6, 0, 0, 0],  # tabi boots
    ],
    # -- 4: Robot -------------------------------------------------------------
    # Red antenna LED, boxy silver head, red LED eyes, metallic body
    [
        [0, 0, 0, 0, 0, 4, 4, 0, 0, 0, 0, 0],  # antenna tip
        [0, 0, 0, 0, 1, 4, 4, 1, 0, 0, 0, 0],  # antenna base
        [0, 0, 0, 1, 3, 3, 3, 3, 1, 0, 0, 0],  # head top
        [0, 0, 1, 3, 3, 3, 3, 3, 3, 1, 0, 0],  # head wider
        [0, 0, 1, 3, 4, 5, 5, 4, 3, 1, 0, 0],  # eyes + mouth
        [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0],  # neck
        [0, 0, 1, 5, 2, 2, 2, 2, 5, 1, 0, 0],  # torso + arms
        [0, 0, 1, 2, 2, 4, 4, 2, 2, 1, 0, 0],  # chest panel
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # legs
        [0, 0, 1, 6, 6, 0, 0, 6, 6, 1, 0, 0],  # dark feet
    ],
    # -- 5: Frog --------------------------------------------------------------
    # Big bulging eyes on top, wide body, green, splayed yellow feet
    [
        [0, 1, 4, 1, 0, 0, 0, 0, 1, 4, 1, 0],  # eye stalks
        [0, 1, 4, 1, 0, 0, 0, 0, 1, 4, 1, 0],  # eye pupils
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # head top
        [0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0],  # head wider
        [0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0],  # head
        [0, 1, 2, 3, 3, 3, 3, 3, 3, 2, 1, 0],  # mouth
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # body
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # body
        [0, 5, 5, 1, 2, 2, 2, 2, 1, 5, 5, 0],  # feet spread
        [5, 5, 0, 0, 1, 1, 1, 1, 0, 0, 5, 5],  # toe tips
    ],
    # -- 6: Astronaut ---------------------------------------------------------
    # Fishbowl helmet, face visible through visor, white suit
    [
        [0, 0, 0, 1, 4, 4, 4, 4, 1, 0, 0, 0],  # helmet dome
        [0, 0, 1, 4, 4, 4, 4, 4, 4, 1, 0, 0],  # helmet wider
        [0, 1, 4, 4, 5, 5, 5, 5, 4, 4, 1, 0],  # visor (face)
        [0, 1, 4, 4, 5, 1, 1, 5, 4, 4, 1, 0],  # visor + eyes
        [0, 0, 1, 4, 4, 4, 4, 4, 4, 1, 0, 0],  # helmet bottom
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # suit top
        [0, 1, 2, 2, 3, 3, 3, 3, 2, 2, 1, 0],  # suit + panel
        [0, 1, 6, 1, 2, 2, 2, 2, 1, 6, 1, 0],  # gloves
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # legs
        [0, 0, 1, 6, 6, 0, 0, 6, 6, 1, 0, 0],  # boots
    ],
    # -- 7: Slime -------------------------------------------------------------
    # Dome blob, shiny highlight, eyes, drippy bottom edge
    [
        [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],  # tip
        [0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0],  # dome top
        [0, 0, 0, 1, 2, 3, 3, 2, 1, 0, 0, 0],  # dome + highlight
        [0, 0, 1, 2, 2, 3, 3, 2, 2, 1, 0, 0],  # body wider
        [0, 1, 2, 2, 4, 2, 2, 4, 2, 2, 1, 0],  # eyes
        [0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0],  # body
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],  # widest body
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],  # base
        [0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0],  # drippy bottom
        [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],  # drip tips
    ],
    # -- 8: Bat ---------------------------------------------------------------
    # Pointy ears, small head, wings spread wide, dark coloring
    [
        [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],  # ear tips
        [0, 0, 0, 1, 2, 0, 0, 2, 1, 0, 0, 0],  # ears
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # head
        [0, 0, 0, 1, 4, 2, 2, 4, 1, 0, 0, 0],  # eyes
        [0, 0, 1, 2, 2, 3, 3, 2, 2, 1, 0, 0],  # face + mouth
        [0, 1, 6, 2, 2, 2, 2, 2, 2, 6, 1, 0],  # body + wings
        [1, 6, 6, 2, 2, 2, 2, 2, 2, 6, 6, 1],  # wings spread
        [1, 6, 6, 6, 1, 2, 2, 1, 6, 6, 6, 1],  # wings widest
        [0, 1, 6, 6, 0, 1, 1, 0, 6, 6, 1, 0],  # wing tips
        [0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0],  # wingtips
    ],
    # -- 9: Monkey ------------------------------------------------------------
    # Round face, prominent ears, face marking, curled tail
    [
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # head top
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # head wider
        [1, 3, 1, 2, 2, 2, 2, 2, 2, 1, 3, 1],  # big ears
        [1, 3, 1, 3, 4, 3, 3, 4, 3, 1, 3, 1],  # face + eyes
        [0, 1, 1, 3, 3, 3, 3, 3, 3, 1, 1, 0],  # face
        [0, 0, 1, 3, 3, 5, 5, 3, 3, 1, 0, 0],  # nose/mouth
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # body
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 1, 6, 0],  # body + tail
        [0, 0, 1, 2, 2, 0, 0, 2, 2, 1, 0, 6],  # legs + tail
        [0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 6, 0],  # feet + tail curl
    ],
    # -- 10: Turtle -----------------------------------------------------------
    # Shell with checkerboard pattern, head poking out, little feet
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
        [0, 0, 0, 0, 1, 2, 2, 3, 2, 1, 0, 0],
        [0, 0, 0, 1, 2, 3, 3, 2, 3, 2, 1, 0],
        [0, 0, 1, 3, 2, 3, 3, 2, 3, 2, 1, 0],
        [1, 4, 1, 6, 6, 6, 6, 6, 6, 6, 6, 5],
        [1, 2, 2, 6, 6, 6, 6, 6, 6, 6, 1, 1],
        [0, 0, 0, 1, 5, 1, 0, 1, 5, 0, 0, 0],
        [0, 0, 0, 5, 5, 1, 1, 5, 5, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ],
    # -- 11: Duck -------------------------------------------------------------
    # Round body, flat beak, tail feather, webbed feet
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 2, 2, 2, 2, 1, 0, 0, 0, 0],
        [1, 1, 1, 2, 4, 1, 2, 1, 0, 0, 0, 0],
        [0, 1, 1, 2, 2, 2, 2, 1, 1, 0, 0, 0],
        [0, 0, 0, 2, 2, 3, 2, 2, 2, 2, 1, 0],
        [0, 0, 0, 2, 3, 3, 3, 2, 2, 2, 1, 0],
        [0, 0, 0, 1, 2, 2, 2, 2, 2, 0, 6, 1],
        [0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0],
        [0, 0, 0, 1, 5, 5, 1, 5, 5, 0, 0, 0],
    ],
    # -- 12: Bird -------------------------------------------------------------
    # Small songbird with beak, breast patch, tail feathers
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 2, 2, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 2, 2, 4, 2, 1, 0, 0, 0, 0],
        [1, 5, 5, 2, 2, 2, 2, 2, 2, 0, 0, 0],
        [0, 0, 1, 3, 3, 3, 2, 2, 2, 2, 1, 0],
        [0, 0, 1, 2, 3, 3, 2, 2, 2, 1, 6, 1],
        [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1],
        [0, 0, 0, 0, 1, 5, 1, 5, 0, 0, 0, 0],
        [0, 0, 0, 1, 5, 5, 5, 5, 1, 0, 0, 0],
    ],
    # -- 13: Pirate -----------------------------------------------------------
    # Bandana, eyepatch, stubble, coat, peg leg
    [
        [0, 0, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0],  # bandana top
        [0, 0, 1, 2, 2, 3, 3, 2, 2, 1, 0, 0],  # bandana + knot
        [0, 0, 1, 5, 5, 5, 5, 5, 5, 1, 0, 0],  # face
        [0, 0, 1, 1, 4, 5, 5, 4, 5, 1, 0, 0],  # eyepatch + eye
        [0, 0, 1, 5, 5, 6, 6, 5, 5, 1, 0, 0],  # stubble/mouth
        [0, 0, 0, 1, 5, 5, 5, 5, 1, 0, 0, 0],  # chin
        [0, 0, 1, 2, 2, 3, 3, 2, 2, 1, 0, 0],  # coat + belt
        [0, 1, 6, 1, 2, 2, 2, 2, 1, 6, 1, 0],  # arms + hooks
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # legs
        [0, 0, 1, 6, 6, 0, 0, 6, 6, 1, 0, 0],  # boots
    ],
    # -- 14: Spider -----------------------------------------------------------
    # Eight legs radiating from round body, multiple eyes
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 2, 4, 4, 4, 2, 0, 0, 0],
        [0, 0, 0, 1, 2, 1, 4, 1, 2, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 1, 0, 1, 2, 2, 3, 2, 2, 1, 0, 1],
        [0, 0, 1, 1, 2, 3, 6, 3, 2, 0, 1, 0],
        [1, 0, 1, 0, 1, 2, 2, 2, 1, 0, 1, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ],
    # -- 15: Skeleton ---------------------------------------------------------
    # Skull with eye sockets, rib cage, bony limbs
    [
        [0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
        [0, 0, 0, 1, 2, 2, 2, 2, 2, 0, 0, 0],
        [0, 0, 0, 2, 3, 3, 2, 3, 3, 1, 0, 0],
        [0, 0, 0, 2, 3, 3, 2, 3, 3, 1, 0, 0],
        [0, 0, 0, 1, 4, 4, 4, 4, 4, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 2, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 2, 2, 2, 1, 1, 0, 0],
        [0, 1, 0, 0, 1, 2, 5, 2, 1, 0, 0, 1],
        [0, 1, 0, 0, 0, 1, 2, 1, 0, 0, 0, 1],
        [0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0],
    ],
    # -- 16: Zombie -----------------------------------------------------------
    # Tattered clothes, outstretched arms, shambling pose
    [
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 2, 2, 2, 1, 0, 0, 0],
        [0, 0, 0, 1, 3, 4, 2, 3, 4, 0, 0, 0],
        [0, 0, 0, 1, 2, 2, 2, 2, 2, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
        [0, 1, 1, 1, 1, 6, 6, 6, 1, 1, 1, 1],
        [1, 2, 2, 1, 6, 6, 2, 6, 6, 2, 2, 2],
        [0, 0, 1, 0, 0, 1, 2, 1, 0, 0, 1, 0],
        [0, 0, 0, 0, 1, 6, 6, 6, 1, 0, 0, 0],
        [0, 0, 0, 0, 1, 2, 1, 2, 1, 0, 0, 0],
    ],
    # -- 17: Wizard -----------------------------------------------------------
    # Pointy hat with star, long beard, robe, staff
    [
        [0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0],  # hat tip
        [0, 0, 0, 0, 1, 2, 1, 0, 0, 0, 0, 0],  # hat top
        [0, 0, 0, 1, 2, 4, 2, 1, 0, 0, 0, 0],  # hat + star
        [0, 0, 1, 2, 2, 2, 2, 2, 1, 0, 0, 0],  # hat brim
        [0, 0, 1, 5, 4, 5, 5, 4, 5, 1, 0, 0],  # face + eyes
        [0, 0, 1, 5, 3, 3, 3, 3, 5, 1, 0, 0],  # beard
        [0, 0, 0, 1, 3, 3, 3, 3, 1, 0, 0, 0],  # beard lower
        [0, 3, 1, 2, 2, 2, 2, 2, 2, 1, 0, 0],  # robe + staff
        [0, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0],  # robe bottom
        [0, 0, 0, 6, 6, 0, 0, 6, 6, 0, 0, 0],  # sandals
    ],
    # -- 18: Rabbit -----------------------------------------------------------
    # Long ears, round body, fluffy tail
    [
        [0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0],
        [0, 0, 0, 2, 3, 1, 0, 1, 3, 1, 0, 0],
        [0, 0, 0, 2, 3, 1, 0, 1, 3, 1, 0, 0],
        [0, 0, 0, 1, 2, 1, 1, 1, 2, 0, 0, 0],
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 1, 0],
        [0, 0, 1, 2, 2, 2, 3, 2, 2, 2, 1, 0],
        [0, 0, 1, 2, 2, 3, 2, 3, 2, 5, 1, 0],
        [0, 0, 0, 1, 1, 2, 2, 2, 1, 0, 0, 0],
        [0, 0, 0, 2, 2, 6, 6, 6, 2, 1, 0, 0],
        [0, 0, 0, 1, 2, 1, 0, 1, 2, 0, 0, 0],
    ],
    # -- 19: Mushroom ---------------------------------------------------------
    # Spotted cap, thick stem
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 2, 2, 2, 2, 2, 0, 0, 0],
        [0, 0, 0, 2, 2, 3, 2, 2, 2, 1, 0, 0],
        [0, 0, 1, 2, 3, 4, 3, 2, 3, 2, 1, 0],
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 5, 1, 0],
        [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0],
        [0, 0, 0, 0, 1, 3, 1, 3, 1, 0, 0, 0],
        [0, 0, 0, 0, 1, 3, 3, 3, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
    ],
    # -- 20: Heart ------------------------------------------------------------
    # Classic heart shape with highlight and shadow
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0],
        [0, 0, 1, 3, 3, 1, 0, 1, 3, 2, 1, 0],
        [0, 1, 3, 2, 2, 2, 2, 2, 2, 5, 5, 1],
        [0, 0, 1, 2, 2, 2, 2, 2, 2, 5, 1, 0],
        [0, 0, 0, 2, 2, 2, 2, 2, 2, 1, 0, 0],
        [0, 0, 0, 0, 1, 2, 2, 5, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 6, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ],
    # -- 21: Star -------------------------------------------------------------
    # Five-pointed star with faceted shading
    [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 2, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 3, 2, 2, 1, 0, 0, 0],
        [0, 0, 1, 3, 3, 3, 2, 2, 2, 5, 1, 0],
        [0, 0, 0, 1, 3, 2, 2, 2, 5, 0, 0, 0],
        [0, 0, 0, 3, 3, 2, 2, 2, 5, 1, 0, 0],
        [0, 1, 3, 5, 1, 0, 0, 0, 1, 6, 6, 1],
        [0, 1, 2, 1, 0, 0, 0, 0, 0, 5, 6, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ],
]


# -- 22 Sprite Palettes (NES hex colors) ------------------------------------

SPRITE_PALETTES: list[dict[int, str]] = [
    # 0: Plumber -- hero_red
    {
        1: "#000000",
        2: "#F83800",  # red cap/shirt
        3: "#FCE4A0",  # cream mustache/overalls
        4: "#FFFFFF",  # white eyes
        5: "#FCA044",  # skin
        6: "#A80000",  # dark red boots
    },
    # 1: Ghost -- ghost_pink
    {
        1: "#FCB4FC",  # outline = body (ghosts)
        2: "#FCB4FC",  # body: pink
        3: "#FFFFFF",  # eye whites
        4: "#0000FC",  # pupils: blue
        5: "#FCD8FC",  # highlight
        6: "#A87CA8",  # shadow
    },
    # 2: Knight -- hero_blue
    {
        1: "#000000",
        2: "#0078F8",  # blue armor
        3: "#FCE4A0",  # cream plume
        4: "#FFFFFF",  # white highlights
        5: "#FCA044",  # skin
        6: "#0058A8",  # dark blue boots
    },
    # 3: Ninja -- hero_purple
    {
        1: "#000000",
        2: "#A800A8",  # purple
        3: "#FCE4A0",  # cream headband
        4: "#FFFFFF",  # white eyes
        5: "#FCA044",  # skin (through mask)
        6: "#580058",  # dark purple boots
    },
    # 4: Robot -- robot_silver
    {
        1: "#000000",
        2: "#BCBCBC",  # silver body
        3: "#F8F8F8",  # bright silver head
        4: "#FC0000",  # red LEDs
        5: "#787878",  # gray panels
        6: "#383838",  # dark gray
    },
    # 5: Frog -- lime_green (distinct from other greens)
    {
        1: "#000000",
        2: "#58F858",  # lime green body
        3: "#A8FCA8",  # light lime belly
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow feet
        6: "#28A828",  # dark lime
    },
    # 6: Astronaut -- hero_white
    {
        1: "#000000",
        2: "#F8F8F8",  # white suit
        3: "#BCBCBC",  # gray panels
        4: "#FFFFFF",  # bright helmet glass
        5: "#FCA044",  # skin (through visor)
        6: "#787878",  # dark gloves/boots
    },
    # 7: Slime -- emerald (distinct green)
    {
        1: "#000000",
        2: "#00D868",  # emerald body
        3: "#58F8A8",  # bright emerald highlight
        4: "#FFFFFF",  # white eyes
        5: "#656565",  # mouth
        6: "#008840",  # dark emerald
    },
    # 8: Bat -- animal_gray
    {
        1: "#000000",
        2: "#787878",  # gray body
        3: "#BCBCBC",  # light gray belly
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow fangs
        6: "#383838",  # dark wing membrane
    },
    # 9: Monkey -- animal_brown
    {
        1: "#000000",
        2: "#884400",  # brown fur
        3: "#FCA044",  # orange face
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow nose
        6: "#442200",  # dark brown tail
    },
    # 10: Turtle -- teal (blue-green)
    {
        1: "#000000",
        2: "#00B8A8",  # teal shell
        3: "#58F8E8",  # light teal pattern
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow feet
        6: "#007868",  # dark teal
    },
    # 11: Duck -- animal_orange
    {
        1: "#000000",
        2: "#F87800",  # orange body
        3: "#FCB800",  # yellow breast
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow feet
        6: "#A84800",  # dark orange tail
    },
    # 12: Bird -- sky_blue (lighter blue)
    {
        1: "#000000",
        2: "#58C8F8",  # sky blue body
        3: "#A8E8FC",  # light sky breast
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow beak/feet
        6: "#2898C8",  # dark sky tail
    },
    # 13: Pirate -- chartreuse (yellow-green coat)
    {
        1: "#000000",
        2: "#A8D800",  # chartreuse coat
        3: "#D8F858",  # belt/accent
        4: "#FFFFFF",  # white eye
        5: "#FCA044",  # skin
        6: "#688800",  # dark boots/hooks
    },
    # 14: Spider -- tan (light brown)
    {
        1: "#000000",
        2: "#D8A060",  # tan body
        3: "#F8D098",  # light tan markings
        4: "#FFFFFF",  # white eyes
        5: "#F8D878",  # yellow details
        6: "#986830",  # dark tan legs
    },
    # 15: Skeleton -- bone (warm white)
    {
        1: "#000000",
        2: "#E8D8C0",  # bone white
        3: "#C8B8A0",  # gray-bone shadows
        4: "#FFFFFF",  # bright highlights
        5: "#FCA044",  # orange details
        6: "#A89878",  # dark bone
    },
    # 16: Zombie -- olive (yellow-brown-green)
    {
        1: "#000000",
        2: "#688800",  # olive skin
        3: "#98B800",  # light olive highlights
        4: "#FFFFFF",  # white eyes
        5: "#656565",  # gray details
        6: "#405800",  # dark olive
    },
    # 17: Wizard -- indigo (deep blue robe)
    {
        1: "#000000",
        2: "#3850E0",  # indigo robe
        3: "#C8C0B0",  # beard (warm gray)
        4: "#F8D878",  # star/eyes (gold)
        5: "#FCA044",  # skin
        6: "#2038A0",  # dark sandals
    },
    # 18: Rabbit -- cream (warm off-white)
    {
        1: "#000000",
        2: "#F0E0C0",  # cream fur
        3: "#FC7878",  # pink inner ears
        4: "#FFFFFF",  # bright highlights
        5: "#C8B898",  # warm gray tail
        6: "#D8C8A8",  # darker cream feet
    },
    # 19: Mushroom -- coral (pink-red)
    {
        1: "#A83030",  # dark coral outline
        2: "#F87070",  # coral cap
        3: "#FCA8A8",  # light coral spots
        4: "#FFFFFF",  # white spots
        5: "#FCA044",  # orange stem
        6: "#983838",  # dark coral
    },
    # 20: Heart -- hot_pink
    {
        1: "#A82060",  # dark pink outline
        2: "#F850A8",  # hot pink body
        3: "#FC98D0",  # light pink highlight
        4: "#FFFFFF",  # white sparkle
        5: "#FCA044",  # orange shadow
        6: "#882050",  # dark hot pink
    },
    # 21: Star -- item_gold
    {
        1: "#A87800",  # dark gold outline
        2: "#F8B800",  # gold body
        3: "#FCF878",  # bright yellow highlight
        4: "#FFFFFF",  # white sparkle
        5: "#F8D878",  # light gold
        6: "#785800",  # dark gold shadow
    },
]


# -- Sprite Names ------------------------------------------------------------

SPRITE_NAMES: list[str] = [
    "Plumber",
    "Ghost",
    "Knight",
    "Ninja",
    "Robot",
    "Frog",
    "Astronaut",
    "Slime",
    "Bat",
    "Monkey",
    "Turtle",
    "Duck",
    "Bird",
    "Pirate",
    "Spider",
    "Skeleton",
    "Zombie",
    "Wizard",
    "Rabbit",
    "Mushroom",
    "Heart",
    "Star",
]

_GRID_ROWS = 10
_GRID_COLS = 12
_BLANK_ROW: list[int] = [0] * _GRID_COLS


# -- Renderer ----------------------------------------------------------------


def render_sprite(
    grid: list[list[int]], palette: dict[int, str]
) -> tuple[str, str, str, str, str]:
    """Render a 10-row x 12-col pixel grid into 5 lines of Rich markup.

    Each output line combines two grid rows using half-block characters:
      Row pairs (0,1), (2,3), (4,5), (6,7), (8,9) produce lines 0-4.

    Half-block encoding per column:
      (0, 0) -> " "                          (both transparent)
      (c, 0) -> [fg_color]▀[/]              (top pixel only)
      (0, c) -> [fg_color]▄[/]              (bottom pixel only)
      (c, c) -> [fg_color]█[/]              (same color both)
      (c1,c2) -> [c1_color on c2_color]▀[/] (different colors)

    Returns a 5-tuple of Rich-markup strings, each 12 characters visual width.
    """
    lines: list[str] = []
    for pair_idx in range(5):
        top_row = grid[pair_idx * 2]
        bot_row = grid[pair_idx * 2 + 1]
        chars: list[str] = []
        for col in range(_GRID_COLS):
            tp = top_row[col]
            bp = bot_row[col]
            if tp == 0 and bp == 0:
                chars.append(" ")
            elif tp != 0 and bp == 0:
                chars.append(f"[{palette[tp]}]\u2580[/]")
            elif tp == 0 and bp != 0:
                chars.append(f"[{palette[bp]}]\u2584[/]")
            elif tp == bp:
                chars.append(f"[{palette[tp]}]\u2588[/]")
            else:
                chars.append(
                    f"[{palette[tp]} on {palette[bp]}]\u2580[/]"
                )
        lines.append("".join(chars))
    return lines[0], lines[1], lines[2], lines[3], lines[4]


# -- Grid Transforms (for animations) ---------------------------------------


def _translate_grid(grid: list[list[int]], dx: int, dy: int) -> list[list[int]]:
    """Translate entire sprite grid by (dx, dy) pixels, filling gaps with transparent."""
    result = [row[:] for row in grid]
    if dx < 0:
        n = min(-dx, _GRID_COLS)
        result = [row[n:] + [0] * n for row in result]
    elif dx > 0:
        n = min(dx, _GRID_COLS)
        result = [[0] * n + row[:-n] for row in result]
    if dy < 0:
        n = min(-dy, _GRID_ROWS)
        result = result[n:] + [[0] * _GRID_COLS for _ in range(n)]
    elif dy > 0:
        n = min(dy, _GRID_ROWS)
        result = [[0] * _GRID_COLS for _ in range(n)] + result[:-n]
    return result


def _shift_grid_left(grid: list[list[int]]) -> list[list[int]]:
    """Shift pixel grid left by 1 column; rightmost column becomes transparent."""
    return [row[1:] + [0] for row in grid]


def _shift_grid_right(grid: list[list[int]]) -> list[list[int]]:
    """Shift pixel grid right by 1 column; leftmost column becomes transparent."""
    return [[0] + row[:-1] for row in grid]


def _walk_frame(grid: list[list[int]], phase: int) -> list[list[int]]:
    """Generate a walk-cycle frame by modifying the bottom 2 rows.

    4 leg positions cycled through:
      0 = base (standing)
      1 = legs apart (spread outward)
      2 = together (centered)
      3 = legs apart mirrored (swap of phase 1)
    """
    result = [row[:] for row in grid]
    row_a = result[_GRID_ROWS - 2][:]
    row_b = result[_GRID_ROWS - 1][:]

    if phase == 1:
        # Shift bottom rows left by 1 (step left)
        result[_GRID_ROWS - 2] = row_a[1:] + [0]
        result[_GRID_ROWS - 1] = row_b[1:] + [0]
    elif phase == 2:
        # Compress legs inward (feet together)
        result[_GRID_ROWS - 1] = list(_BLANK_ROW)
        for c in range(_GRID_COLS):
            if row_b[c] != 0:
                target = max(0, min(_GRID_COLS - 1, (c + _GRID_COLS // 2) // 2))
                result[_GRID_ROWS - 1][target] = row_b[c]
    elif phase == 3:
        # Shift bottom rows right by 1 (step right)
        result[_GRID_ROWS - 2] = [0] + row_a[:-1]
        result[_GRID_ROWS - 1] = [0] + row_b[:-1]

    return result


def _jump_frame(grid: list[list[int]], offset: int) -> list[list[int]]:
    """Shift entire grid UP by |offset| rows, fill bottom with transparent.

    offset is negative (e.g. -2 = shift up 2 rows).
    """
    if offset >= 0:
        return grid
    shift = -offset
    result: list[list[int]] = []
    for r in range(len(grid)):
        src = r + shift
        if src < len(grid):
            result.append(grid[src][:])
        else:
            result.append([0] * _GRID_COLS)
    return result


def _apply_palette_brightness(
    palette: dict[int, str], factor: float
) -> dict[int, str]:
    """Create a new palette with all colors brightened by factor.

    factor > 0 brightens, factor < 0 darkens.
    """
    result: dict[int, str] = {}
    for key, color in palette.items():
        if factor >= 0:
            result[key] = brighten(color, factor)
        else:
            result[key] = darken(color, 1.0 + factor)
    return result


# -- Animation Frame Generator -----------------------------------------------

_BLANK_FRAME: tuple[str, str, str, str, str] = (
    " " * _GRID_COLS,
    " " * _GRID_COLS,
    " " * _GRID_COLS,
    " " * _GRID_COLS,
    " " * _GRID_COLS,
)

# THINKING walk cycle (8 frames): 4 positions cycled twice
_THINKING_PHASES: list[int] = [0, 1, 2, 3, 0, 1, 2, 3]

# Full-body walk sequences (dx, dy) per frame
_THINKING_WALK: list[tuple[int, int]] = [
    (0, 0), (-2, 0), (0, -1), (2, 0), (0, 0), (-2, 0), (0, -1), (2, 0),
]
_EXECUTING_WALK: list[tuple[int, int]] = [
    (0, 0), (-2, -1), (0, 0), (2, -1), (0, 0), (-2, -1), (0, 0), (2, -1),
]

# EXECUTING fast walk cycle (8 frames): double-speed walk
_EXECUTING_PHASES: list[int] = [0, 2, 0, 2, 1, 3, 1, 3]

# SUBAGENT_RUNNING pulse brightness (8 frames):
# base, bright, brighter, brightest, bright, base, dim, base
_PULSE_FACTORS: list[float] = [0.0, 0.15, 0.35, 0.55, 0.35, 0.0, -0.3, 0.0]

# WAITING_PERMISSION jump offsets (8 frames):
# standing, standing, jump up 1, peak (up 2), peak, descending (up 1), landed, landed
_JUMP_OFFSETS: list[int] = [0, 0, -1, -2, -2, -1, 0, 0]


def get_sprite_frame(
    row_index: int = 0,
    status: SessionStatus = SessionStatus.IDLE,
    anim_frame: int = 0,
    *,
    sprite_idx: int | None = None,
) -> tuple[str, str, str, str, str]:
    """Get 5-line Rich markup for an animated sprite.

    Args:
        row_index: Legacy 1-based row position (used if sprite_idx is None).
        status: Current session status (drives animation type).
        anim_frame: Current animation frame counter (0-7).
        sprite_idx: Direct sprite template index (0-based). Overrides row_index.

    Returns:
        5-tuple of Rich-markup strings, each 12 characters visual width.
    """
    if sprite_idx is None:
        sprite_idx = max(0, row_index - 1) % len(SPRITE_TEMPLATES)
    base_grid = SPRITE_TEMPLATES[sprite_idx]
    palette = SPRITE_PALETTES[sprite_idx]
    frame = anim_frame % 8

    # -- IDLE / UNKNOWN: static base frame --
    if status in (SessionStatus.IDLE, SessionStatus.UNKNOWN):
        return render_sprite(base_grid, palette)

    # -- TERMINATED: static, dimmed --
    if status == SessionStatus.TERMINATED:
        lines = render_sprite(base_grid, palette)
        return tuple(f"[dim]{line}[/]" for line in lines)  # type: ignore[return-value]

    # -- THINKING: full-body walk --
    if status == SessionStatus.THINKING:
        dx, dy = _THINKING_WALK[frame]
        if dx == 0 and dy == 0:
            grid = base_grid
        else:
            grid = _translate_grid(base_grid, dx, dy)
        return render_sprite(grid, palette)

    # -- EXECUTING: full-body bouncy walk --
    if status == SessionStatus.EXECUTING:
        dx, dy = _EXECUTING_WALK[frame]
        if dx == 0 and dy == 0:
            grid = base_grid
        else:
            grid = _translate_grid(base_grid, dx, dy)
        return render_sprite(grid, palette)

    # -- SUBAGENT_RUNNING: brightness pulse --
    if status == SessionStatus.SUBAGENT_RUNNING:
        factor = _PULSE_FACTORS[frame]
        if factor == 0.0:
            return render_sprite(base_grid, palette)
        adjusted = _apply_palette_brightness(palette, factor)
        return render_sprite(base_grid, adjusted)

    # -- WAITING_PERMISSION: jump --
    if status == SessionStatus.WAITING_PERMISSION:
        offset = _JUMP_OFFSETS[frame]
        if offset == 0:
            return render_sprite(base_grid, palette)
        grid = _jump_frame(base_grid, offset)
        return render_sprite(grid, palette)

    # -- Fallback --
    return render_sprite(base_grid, palette)


# -- Color Accessor ----------------------------------------------------------


def get_sprite_color(row_index: int = 0, *, sprite_idx: int | None = None) -> str:
    """Return the primary body color (palette slot 2) for a sprite.

    Args:
        row_index: Legacy 1-based row position (used if sprite_idx is None).
        sprite_idx: Direct sprite template index (0-based). Overrides row_index.
    """
    if sprite_idx is None:
        sprite_idx = max(0, row_index - 1) % len(SPRITE_PALETTES)
    return SPRITE_PALETTES[sprite_idx][2]


# -- Session → Sprite Mapping ------------------------------------------------

# Index 1 (Ghost) is reserved for the header logo.
_GHOST_INDEX = 1
_SESSION_POOL = [i for i in range(len(SPRITE_TEMPLATES)) if i != _GHOST_INDEX]


def sprite_index_for_session(session_id: str) -> int:
    """Return a stable sprite index for a session_id.

    Uses a deterministic hash (MD5) of the session_id to pick from the pool
    of available sprites, excluding index 1 (Ghost) which is reserved for
    the header logo. Stable across process restarts (unlike Python's hash()).
    """
    h = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)
    return _SESSION_POOL[h % len(_SESSION_POOL)]


def assign_sprites(session_ids: list[str]) -> dict[str, int]:
    """Assign unique sprite indices to sessions, avoiding collisions.

    Uses hash-based assignment with linear probing fallback to guarantee
    unique sprites when possible (up to len(_SESSION_POOL) sessions).
    """
    pool = list(_SESSION_POOL)
    sorted_ids = sorted(session_ids)
    assignments: dict[str, int] = {}
    used: set[int] = set()
    for sid in sorted_ids:
        h = int(hashlib.md5(sid.encode()).hexdigest()[:8], 16)
        base_pos = h % len(pool)
        assigned = None
        for offset in range(len(pool)):
            candidate = pool[(base_pos + offset) % len(pool)]
            if candidate not in used:
                assigned = candidate
                break
        if assigned is None:
            assigned = pool[base_pos % len(pool)]
        assignments[sid] = assigned
        used.add(assigned)
    return assignments
