#!/usr/bin/env python3
"""
Generate a native 32x32 pixel-art creature atlas with Gameboy palette.

Produces 56 deterministic creature sprites in a 8x7 grid (256x224 atlas).
Each sprite is hand-coded pixel art with clear silhouettes, no anti-aliasing,
designed to look like Pokemon Gen 1/2 monster sprites.

Output: sprites/cinder-creatures/atlas.png
"""

import os
import random
from PIL import Image, ImageDraw

# GB palette (lightest -> darkest), alpha-aware for transparent bg
PAL = [
    (155, 188, 15),   # 0 lightest (background — used as transparent)
    (139, 172, 15),   # 1 light
    (48, 98, 48),     # 2 mid (body)
    (15, 56, 15),     # 3 darkest (outline / detail)
]
TRANSPARENT = (0, 0, 0, 0)
ATLAS_COLS, ATLAS_ROWS = 8, 7
CELL = 32
ATLAS_W, ATLAS_H = ATLAS_COLS * CELL, ATLAS_ROWS * CELL

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprites", "cinder-creatures")
os.makedirs(OUT_DIR, exist_ok=True)


def color(p):
    if p == 0:
        return TRANSPARENT
    return PAL[p] + (255,)


def rect(canvas, x0, y0, x1, y1, p):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= x < CELL and 0 <= y < CELL:
                canvas[y][x] = p


def px(canvas, x, y, p):
    if 0 <= x < CELL and 0 <= y < CELL:
        canvas[y][x] = p


def mirror(canvas):
    """Mirror left half onto right half for symmetric body."""
    for y in range(CELL):
        for x in range(CELL // 2):
            canvas[y][CELL - 1 - x] = canvas[y][x]


def outline(canvas):
    """Add dark outline around body pixels (any non-zero adjacent to zero)."""
    new = [row[:] for row in canvas]
    for y in range(CELL):
        for x in range(CELL):
            if canvas[y][x] == 0:
                # if any neighbor is body (1 or 2), make this an outline pixel
                neighbors = [
                    (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)
                ]
                for nx, ny in neighbors:
                    if 0 <= nx < CELL and 0 <= ny < CELL and canvas[ny][nx] in (1, 2):
                        new[y][x] = 3
                        break
    for y in range(CELL):
        for x in range(CELL):
            canvas[y][x] = new[y][x]


def shadow(img, draw):
    """Soft shadow under sprite (4-color, single dark blob)."""
    for x in range(8, 24):
        img.putpixel((x, 28), (15, 56, 15, 90))
    for x in range(10, 22):
        img.putpixel((x, 29), (15, 56, 15, 90))


def build_blob(canvas):
    """Round blob — slime/ghost archetype."""
    rect(canvas, 10, 12, 15, 25, 2)
    rect(canvas, 8, 14, 15, 24, 2)
    rect(canvas, 7, 16, 15, 22, 2)
    rect(canvas, 6, 18, 15, 21, 2)
    # belly
    rect(canvas, 11, 18, 15, 22, 1)
    # eye
    px(canvas, 11, 16, 3)
    px(canvas, 11, 17, 3)
    # mouth hint
    px(canvas, 13, 21, 3)


def build_bug(canvas):
    """Insect — bytefly archetype."""
    rect(canvas, 10, 14, 15, 21, 2)
    rect(canvas, 8, 15, 15, 20, 2)
    # head
    rect(canvas, 11, 11, 15, 14, 2)
    # antennae
    px(canvas, 13, 9, 3); px(canvas, 13, 10, 3)
    px(canvas, 14, 8, 3); px(canvas, 11, 9, 3)
    # wings
    rect(canvas, 7, 16, 9, 19, 1)
    px(canvas, 6, 17, 3); px(canvas, 6, 18, 3)
    # eye
    px(canvas, 13, 12, 3); px(canvas, 14, 12, 3)
    # legs
    px(canvas, 11, 22, 3); px(canvas, 11, 23, 3)
    px(canvas, 13, 22, 3); px(canvas, 13, 23, 3); px(canvas, 13, 24, 3)
    px(canvas, 15, 22, 3); px(canvas, 15, 23, 3)


def build_snake(canvas):
    """Snake/serpent — recurse archetype."""
    # winding body
    pts = [(8, 22), (10, 21), (12, 22), (14, 21), (15, 19), (14, 17), (12, 16), (11, 14), (12, 12), (14, 11)]
    for x, y in pts:
        rect(canvas, x - 1, y - 1, x + 1, y + 1, 2)
    # head at top
    rect(canvas, 13, 9, 15, 12, 2)
    px(canvas, 14, 10, 1)  # eye highlight
    px(canvas, 14, 11, 3)  # eye
    # tongue
    px(canvas, 15, 10, 3)


def build_crystal(canvas):
    """Crystal/rock — kernite archetype."""
    # main crystal cluster
    rect(canvas, 11, 14, 15, 24, 2)
    rect(canvas, 9, 17, 15, 23, 2)
    # spikes
    px(canvas, 13, 11, 2); px(canvas, 13, 12, 2); px(canvas, 13, 13, 2)
    px(canvas, 11, 13, 2); px(canvas, 12, 13, 2)
    px(canvas, 14, 13, 2); px(canvas, 15, 13, 2)
    # facets (light)
    rect(canvas, 12, 18, 14, 21, 1)
    # eye (dark spot)
    px(canvas, 13, 19, 3)
    px(canvas, 14, 19, 3)


def build_quad(canvas):
    """Four-legged beast — allocroc archetype."""
    # body (horizontal capsule)
    rect(canvas, 7, 17, 15, 22, 2)
    rect(canvas, 8, 16, 15, 23, 2)
    # head (right side)
    rect(canvas, 13, 14, 15, 18, 2)
    # legs
    rect(canvas, 9, 23, 10, 26, 3)
    rect(canvas, 13, 23, 14, 26, 3)
    # tail
    px(canvas, 6, 18, 2); px(canvas, 6, 19, 2); px(canvas, 5, 18, 3)
    # eye
    px(canvas, 14, 15, 3)
    # belly stripe
    rect(canvas, 9, 20, 13, 21, 1)


def build_bird(canvas):
    """Bird/owl — semafox-flying archetype."""
    # body
    rect(canvas, 10, 13, 15, 22, 2)
    rect(canvas, 8, 15, 15, 21, 2)
    # head
    rect(canvas, 11, 10, 15, 14, 2)
    # beak
    px(canvas, 15, 13, 3); px(canvas, 14, 13, 3)
    # eye
    px(canvas, 13, 12, 3); px(canvas, 14, 11, 3)
    # wing
    rect(canvas, 8, 17, 11, 21, 1)
    px(canvas, 7, 18, 3); px(canvas, 7, 19, 3); px(canvas, 7, 20, 3)
    # feet
    px(canvas, 11, 23, 3); px(canvas, 12, 23, 3); px(canvas, 13, 23, 3)
    px(canvas, 11, 24, 3); px(canvas, 13, 24, 3)


def build_ghost(canvas):
    """Ghost/null archetype — daemonet."""
    # wisp body
    rect(canvas, 10, 12, 15, 24, 2)
    rect(canvas, 8, 14, 15, 24, 2)
    # tattered bottom
    px(canvas, 8, 24, 0); px(canvas, 8, 25, 2)
    px(canvas, 11, 25, 2); px(canvas, 14, 25, 2)
    px(canvas, 9, 26, 2); px(canvas, 13, 26, 2)
    # hollow eye
    rect(canvas, 11, 16, 12, 18, 3)
    px(canvas, 11, 16, 0)  # eye light
    # arm wisps
    px(canvas, 7, 18, 2); px(canvas, 6, 19, 2)


def build_orb(canvas):
    """Floating orb — cachebit/mutexel."""
    # core
    rect(canvas, 10, 13, 15, 22, 2)
    rect(canvas, 8, 15, 15, 20, 2)
    rect(canvas, 9, 14, 15, 21, 2)
    rect(canvas, 11, 16, 14, 19, 1)  # bright core
    # surrounding particles
    px(canvas, 7, 12, 2); px(canvas, 16, 12, 2)
    px(canvas, 6, 18, 1); px(canvas, 17, 18, 1)
    px(canvas, 8, 24, 1); px(canvas, 16, 23, 1)
    # eye
    px(canvas, 13, 17, 3)
    px(canvas, 14, 17, 3)


ARCHETYPES = [build_blob, build_bug, build_snake, build_crystal,
              build_quad, build_bird, build_ghost, build_orb]


def variation(canvas, rng, idx):
    """Apply per-sprite variation: tweak shading, accent pixels, ear/horn."""
    style = idx % 4
    if style == 0:
        # add horn/ear
        horn_y = 9 + rng.randint(0, 2)
        horn_x = 11 + rng.randint(0, 2)
        rect(canvas, horn_x, horn_y, horn_x + 1, horn_y + 2, 2)
        px(canvas, horn_x, horn_y - 1, 3)
    elif style == 1:
        # add dark spots
        for _ in range(3):
            sx = 9 + rng.randint(0, 5)
            sy = 18 + rng.randint(0, 4)
            if 0 <= sx < CELL and 0 <= sy < CELL and canvas[sy][sx] == 2:
                canvas[sy][sx] = 3
    elif style == 2:
        # bright belly stripe
        for y in range(20, 23):
            for x in range(10, 14):
                if canvas[y][x] == 2:
                    canvas[y][x] = 1
    else:
        # extra appendage on side
        rect(canvas, 7, 19, 8, 21, 2)
        px(canvas, 7, 19, 3); px(canvas, 8, 21, 3)


def render_creature(idx):
    """Render one 32x32 creature with given index."""
    canvas = [[0 for _ in range(CELL)] for _ in range(CELL)]
    rng = random.Random(idx * 1009 + 17)

    arch = ARCHETYPES[idx % len(ARCHETYPES)]
    arch(canvas)
    variation(canvas, rng, idx)
    mirror(canvas)
    outline(canvas)

    img = Image.new("RGBA", (CELL, CELL), TRANSPARENT)
    for y in range(CELL):
        for x in range(CELL):
            p = canvas[y][x]
            if p > 0:
                img.putpixel((x, y), color(p))
    return img


def render_cinder():
    """Index 55 = Cinder boss. Distinctive — flame silhouette + face."""
    canvas = [[0 for _ in range(CELL)] for _ in range(CELL)]
    # flame body (taller, wavy)
    rect(canvas, 10, 8, 15, 26, 2)
    rect(canvas, 8, 12, 15, 25, 2)
    rect(canvas, 7, 14, 15, 24, 2)
    rect(canvas, 6, 17, 15, 23, 2)
    # flame tip
    rect(canvas, 13, 6, 15, 9, 2)
    px(canvas, 14, 5, 2)
    # bright core
    rect(canvas, 11, 18, 15, 22, 1)
    rect(canvas, 13, 19, 15, 21, 0)  # hollow center won't mirror — we re-mirror below
    # eyes (two of them, glowing dark)
    px(canvas, 11, 14, 3); px(canvas, 11, 15, 3)
    px(canvas, 13, 13, 3); px(canvas, 13, 14, 3)
    # horns / spikes
    px(canvas, 8, 13, 3); px(canvas, 9, 11, 3)
    px(canvas, 11, 9, 3); px(canvas, 13, 8, 3)
    mirror(canvas)
    outline(canvas)
    img = Image.new("RGBA", (CELL, CELL), TRANSPARENT)
    for y in range(CELL):
        for x in range(CELL):
            p = canvas[y][x]
            if p > 0:
                img.putpixel((x, y), color(p))
    return img


def render_spark():
    """Index 0 = SPARK starter. A plucky chunky bug."""
    canvas = [[0 for _ in range(CELL)] for _ in range(CELL)]
    # body
    rect(canvas, 9, 14, 15, 22, 2)
    rect(canvas, 8, 16, 15, 21, 2)
    # head
    rect(canvas, 11, 10, 15, 15, 2)
    # antennae with sparks
    px(canvas, 13, 8, 3); px(canvas, 13, 9, 3)
    px(canvas, 14, 7, 1); px(canvas, 12, 7, 1)
    # belly highlight
    rect(canvas, 10, 18, 14, 21, 1)
    # eye (cute, big)
    px(canvas, 13, 12, 3); px(canvas, 14, 12, 3)
    px(canvas, 13, 13, 3); px(canvas, 14, 13, 3)
    px(canvas, 14, 12, 0)  # glint
    # legs
    px(canvas, 10, 22, 3); px(canvas, 10, 23, 3)
    px(canvas, 12, 22, 3); px(canvas, 12, 23, 3)
    px(canvas, 14, 22, 3); px(canvas, 14, 23, 3)
    mirror(canvas)
    outline(canvas)
    img = Image.new("RGBA", (CELL, CELL), TRANSPARENT)
    for y in range(CELL):
        for x in range(CELL):
            p = canvas[y][x]
            if p > 0:
                img.putpixel((x, y), color(p))
    return img


def main():
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), TRANSPARENT)
    for idx in range(ATLAS_COLS * ATLAS_ROWS):
        if idx == 0:
            sprite = render_spark()
        elif idx == 55:
            sprite = render_cinder()
        else:
            sprite = render_creature(idx)
        col = idx % ATLAS_COLS
        row = idx // ATLAS_COLS
        atlas.paste(sprite, (col * CELL, row * CELL))

    out_atlas = os.path.join(OUT_DIR, "atlas.png")
    atlas.save(out_atlas, "PNG")
    print(f"Atlas saved: {out_atlas} ({ATLAS_W}x{ATLAS_H})")

    # Also save individual sprites for inspection
    for idx in range(ATLAS_COLS * ATLAS_ROWS):
        col = idx % ATLAS_COLS
        row = idx // ATLAS_COLS
        sprite = atlas.crop((col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL))
        sprite.save(os.path.join(OUT_DIR, f"creature_{idx + 1:02d}.png"), "PNG")
    print(f"56 individual sprites saved.")


if __name__ == "__main__":
    main()
