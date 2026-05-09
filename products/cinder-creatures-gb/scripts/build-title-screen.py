#!/usr/bin/env python3
"""
Build a Pokemon-Red/Blue-style title screen for CINDER CREATURES at 160x144.

v0.21 Loop 9817 rebuild — Joel directive: "Brand the theming and name styling
for the game". Replaces the DejaVu-rendered placeholder with a hand-pixel
wordmark + flame/ember motif so the title reads as a real Cinder brand.

Layout (160x144 GB DMG):
  Top 56px       : CISCOTL mascot (legendary CORE) at 3x scale, ember sparks
  Row 58-78      : "CINDER" hand-pixel wordmark (scale 3) with flame caps
  Row 84-97      : "CREATURES" sub-wordmark (scale 2)
  Row 116-121    : ember bar (kraft accent — closest GB analogue)
  Row 130-138    : MERIDIAN 2026 / PRESS START

GB Studio reads it as a single 160x144 background PNG quantized to 4 DMG shades.
"""
from PIL import Image, ImageDraw
import os

PAL = {
    0: (224, 248, 208),   # lightest (off-white)
    1: (136, 192, 112),   # light
    2: (52, 104, 86),     # dark
    3: (8, 24, 32),       # darkest
}

W, H = 160, 144

# === Hand-pixel font (5w x 7h, 1px gap) ===========================
# Chunky uppercase glyphs. '#' = ink, '.' = bg.
GLYPH_5x7 = {
    "A": ["..#..", ".#.#.", "#...#", "#####", "#...#", "#...#", "#...#"],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "###..", "#....", "#....", "#####"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}


def stamp_glyph(d, ch, x, y, scale, color):
    g = GLYPH_5x7.get(ch.upper())
    if not g:
        return
    for ry, row in enumerate(g):
        for rx, c in enumerate(row):
            if c == "#":
                d.rectangle(
                    [(x + rx * scale, y + ry * scale),
                     (x + (rx + 1) * scale - 1, y + (ry + 1) * scale - 1)],
                    fill=color,
                )


def stamp_text(d, text, x, y, scale, color):
    cx = x
    for ch in text:
        stamp_glyph(d, ch, cx, y, scale, color)
        cx += (5 + 1) * scale
    return cx


def text_width(text, scale):
    return len(text) * (5 + 1) * scale - scale


def stamp_centered(d, text, y, scale, color):
    tw = text_width(text, scale)
    stamp_text(d, text, (W - tw) // 2, y, scale, color)


# ===================================================================
img = Image.new("RGB", (W, H), PAL[0])
d = ImageDraw.Draw(img)

# === Mascot frame: CISCOTL silhouette, 3x scale, top-centered =====
mascot_path = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "sprites", "creature_21.png"
)
mascot = Image.open(mascot_path).convert("RGB")
mw, mh = mascot.size
mq = Image.new("RGB", (mw, mh), PAL[0])
for y in range(mh):
    for x in range(mw):
        r, g, b = mascot.getpixel((x, y))
        lum = r * 0.299 + g * 0.587 + b * 0.114
        if lum < 40:
            mq.putpixel((x, y), PAL[3])
        elif lum < 90:
            mq.putpixel((x, y), PAL[2])
        elif lum < 160:
            mq.putpixel((x, y), PAL[1])
        else:
            mq.putpixel((x, y), PAL[0])
mq = mq.resize((mw * 3, mh * 3), Image.NEAREST)  # 48x48
img.paste(mq, ((W - mq.width) // 2, 4))

# === Ember sparks flanking the mascot ==============================
def spark(x, y):
    d.point((x, y), fill=PAL[3])
    d.rectangle([(x - 1, y + 1), (x + 1, y + 1)], fill=PAL[2])
    d.point((x, y + 2), fill=PAL[1])

for sy, sx_l, sx_r in [(8, 18, 142), (22, 12, 148), (38, 22, 138)]:
    spark(sx_l, sy)
    spark(sx_r, sy)

# === CINDER wordmark — chunky, scale 3 ============================
title_y = 58
title_text = "CINDER"
title_scale = 3
stamp_centered(d, title_text, title_y, title_scale, PAL[3])

# Flame caps on top of each letter
title_w = text_width(title_text, title_scale)
title_x0 = (W - title_w) // 2
for i in range(len(title_text)):
    glyph_x = title_x0 + i * (5 + 1) * title_scale
    fx = glyph_x + 2 * title_scale
    fy = title_y - 5
    d.point((fx + title_scale // 2, fy), fill=PAL[3])
    d.rectangle([(fx, fy + 1), (fx + title_scale - 1, fy + 2)], fill=PAL[2])
    d.rectangle([(fx - 1, fy + 3), (fx + title_scale, fy + 4)], fill=PAL[1])

# === CREATURES sub-wordmark — scale 2 ==============================
sub_y = title_y + 26
stamp_centered(d, "CREATURES", sub_y, 2, PAL[2])

# === Ember bar (kraft accent) ======================================
bar_y = sub_y + 18
d.rectangle([(20, bar_y), (W - 21, bar_y + 1)], fill=PAL[3])
for ex in range(24, W - 24, 8):
    d.point((ex, bar_y - 1), fill=PAL[2])
d.rectangle([(20, bar_y + 3), (W - 21, bar_y + 4)], fill=PAL[2])

# === Footer ========================================================
stamp_centered(d, "MERIDIAN 2026", 130, 1, PAL[2])
stamp_centered(d, "PRESS START", 138, 1, PAL[3])


# === Final: snap every pixel to nearest of the 4 DMG shades ========
def gb_quantize(image):
    out = Image.new("RGB", image.size)
    pal = [PAL[i] for i in range(4)]
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = image.getpixel((x, y))
            best = min(pal, key=lambda p: (p[0] - r) ** 2 + (p[1] - g) ** 2 + (p[2] - b) ** 2)
            out.putpixel((x, y), best)
    return out


img = gb_quantize(img)

out_path = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "backgrounds", "cc_title_screen.png"
)
img.save(out_path)
print(f"wrote {out_path} ({W}x{H}, 4-shade GB)")
