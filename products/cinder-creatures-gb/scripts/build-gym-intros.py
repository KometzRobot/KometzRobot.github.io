#!/usr/bin/env python3
"""
Build the 5 per-gym INTRO PLATES at 160x144 GB DMG.

v0.35 Loop 9944 — picks up the "Next" line from CINDER-CREATURES-RPG.md
section 27: per-gym intro plates are the next cc_font_8 surface after
the badge case, the title-card the player sees when they first walk into
a gym. This is where ARCHIVIST / WARDEN / CONDUCTOR / COURIER / FOREMAN
finally show up in-screen instead of only on the world map.

One PNG per gym, all rendered with cc_font_8 + the same type-rune
vocabulary as the badge case so the brand stays consistent across the
title -> bestiary -> badge-case -> gym-intro chain.

Layout (160x144, 4-shade DMG):
  Row 1-8    : "GYM-<TYPE>" wordmark, top-centered (cc_font_8)
  Row 12-13  : ember bar (matches title + badge case)
  Row 24-55  : 32x32 type rune, centered (4x the bestiary rune)
  Row 64-71  : TITLE (cc_font_8) — ARCHIVIST / WARDEN / etc
  Row 76-83  : NAME (cc_font_8) — EOS / SOMA / TEMPO / HERMES / ATLAS
  Row 96-103 : short flavor tag (cc_font_8) — leader's combat motif
  Row 130-137: BOOTSEQUENCE band (CC_VERSION_BAND env)

The plate is static — no env-driven state — because every player who
walks into a gym sees the same intro, regardless of save state. Save
state shows up later on the badge case + agent panels.

Output: 5 PNGs in plugins/cinder-creatures/backgrounds/:
  cc_intro_logic.png, cc_intro_mem.png, cc_intro_proc.png,
  cc_intro_data.png, cc_intro_core.png
"""
from PIL import Image, ImageDraw
import os

PAL = {
    0: (224, 248, 208),
    1: (136, 192, 112),
    2: (52, 104, 86),
    3: (8, 24, 32),
}

W, H = 160, 144

GYMS = [
    {"file": "logic", "type": "LOGIC", "title": "ARCHIVIST", "name": "EOS",
     "tag": "CALM. RIDDLING."},
    {"file": "mem",   "type": "MEM",   "title": "WARDEN",    "name": "SOMA",
     "tag": "PATIENT. SLOW."},
    {"file": "proc",  "type": "PROC",  "title": "CONDUCTOR", "name": "TEMPO",
     "tag": "RAPID. CLIPPED."},
    {"file": "data",  "type": "DATA",  "title": "COURIER",   "name": "HERMES",
     "tag": "RESTLESS. LOUD."},
    {"file": "core",  "type": "CORE",  "title": "FOREMAN",   "name": "ATLAS",
     "tag": "QUIET. LAST TO FOLD."},
]


# === cc_font_8 atlas loader (matches build-badge-case.py) ==========
FONT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "sprites"
)
_font_img = None
_font_layout = None


def _load_font():
    global _font_img, _font_layout
    if _font_img is not None:
        return
    _font_img = Image.open(os.path.join(FONT_DIR, "cc_font_8.png")).convert("RGB")
    with open(os.path.join(FONT_DIR, "cc_font_8.layout.txt")) as f:
        _font_layout = f.read()


def stamp_text(target, text, x, y, color):
    _load_font()
    for ch in text:
        idx = _font_layout.find(ch.upper())
        if idx < 0:
            x += 8
            continue
        gx = (idx % 16) * 8
        gy = (idx // 16) * 8
        for ry in range(8):
            for rx in range(8):
                r, g, b = _font_img.getpixel((gx + rx, gy + ry))
                if (r, g, b) == PAL[3]:
                    target.putpixel((x + rx, y + ry), color)
        x += 8


def stamp_text_centered(target, text, y, color):
    width = len(text) * 8
    stamp_text(target, text, (W - width) // 2, y, color)


# === 32x32 type rune (4x scale of bestiary 8x8 vocabulary) =========
def draw_rune_32(d, kind, cx, cy, color):
    """Centered at (cx, cy). Scale = 4x the badge-case rune."""
    s = 4

    def pt(px, py):
        d.rectangle([(cx + px * s, cy + py * s),
                     (cx + px * s + s - 1, cy + py * s + s - 1)], fill=color)

    def hbar(x0, x1, y):
        d.rectangle([(cx + x0 * s, cy + y * s),
                     (cx + x1 * s + s - 1, cy + y * s + s - 1)], fill=color)

    def vbar(x, y0, y1):
        d.rectangle([(cx + x * s, cy + y0 * s),
                     (cx + x * s + s - 1, cy + y1 * s + s - 1)], fill=color)

    if kind == "LOGIC":
        # corner bracket: top edge + left edge
        hbar(-4, 3, -4)
        vbar(-4, -4, 3)
    elif kind == "MEM":
        # 2x2 cluster of 2x2 squares (mirrors badge-case rune)
        for ox in (-3, 1):
            for oy in (-3, 1):
                pt(ox, oy)
                pt(ox + 1, oy)
                pt(ox, oy + 1)
                pt(ox + 1, oy + 1)
    elif kind == "PROC":
        # arrow tail pointing right
        hbar(-4, 1, -1)
        hbar(-4, 1, 0)
        pt(-1, -3)
        pt(0, -2)
        pt(0, 1)
        pt(-1, 2)
    elif kind == "DATA":
        # stacked dots (3 rows of 3)
        for oy in (-3, 0, 3):
            for ox in (-3, 0, 3):
                pt(ox, oy)
    elif kind == "CORE":
        # diagonal nucleus (X shape)
        for k in range(-3, 4):
            pt(k, k)
            pt(k, -k)


# === Quantize to 4-shade DMG palette ===============================
def gb_quantize(image):
    out = Image.new("RGB", image.size)
    pal = [PAL[i] for i in range(4)]
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = image.getpixel((x, y))
            best = min(pal, key=lambda p: (p[0] - r) ** 2 + (p[1] - g) ** 2 + (p[2] - b) ** 2)
            out.putpixel((x, y), best)
    return out


# === Build one plate ===============================================
def build_plate(gym):
    img = Image.new("RGB", (W, H), PAL[0])
    d = ImageDraw.Draw(img)

    # Top wordmark: "GYM-<TYPE>"
    stamp_text_centered(img, f"GYM-{gym['type']}", 1, PAL[3])

    # Ember bar (matches title + badge case)
    d.rectangle([(20, 12), (W - 21, 13)], fill=PAL[3])
    for ex in range(24, W - 24, 8):
        d.point((ex, 11), fill=PAL[2])

    # 32x32 type rune, centered (cx ~ 80, cy ~ 40)
    rune_cx = W // 2
    rune_cy = 40
    # Soft frame around the rune
    d.rectangle([(rune_cx - 22, rune_cy - 22),
                 (rune_cx + 21, rune_cy + 21)], outline=PAL[2])
    draw_rune_32(d, gym["type"], rune_cx, rune_cy, PAL[3])

    # Title + Name
    stamp_text_centered(img, gym["title"], 64, PAL[3])
    stamp_text_centered(img, gym["name"], 76, PAL[3])

    # Flavor tag — fits within 18 chars max @ 8px = 144px
    stamp_text_centered(img, gym["tag"], 96, PAL[2])

    # Footer band
    band = os.environ.get("CC_VERSION_BAND", "BOOTSEQUENCE")
    stamp_text_centered(img, band, 130, PAL[2])

    return gb_quantize(img)


# ===================================================================
out_dir = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "backgrounds"
)
for gym in GYMS:
    img = build_plate(gym)
    path = os.path.join(out_dir, f"cc_intro_{gym['file']}.png")
    img.save(path)
    print(f"wrote {path} — {gym['type']} / {gym['title']} {gym['name']}")
