#!/usr/bin/env python3
"""
Build the CINDER CREATURES badge case screen at 160x144 GB DMG.

v0.32 Loop 9904 — Joel directive #8: "Brand the theming and name styling
for the game". The brand spec in CINDER-CREATURES-RPG.md calls for the
badge case to render from cc_font_8 like the title screen does. This is
the in-game element the player sees most often once they start clearing
gyms — second only to the title — so the brand has to land here too.

Layout (160x144, 4-shade DMG):
  Row 0-7    : "BADGE CASE" wordmark (cc_font_8 scale 1)
  Row 10-11  : ember bar (matches title-screen accent)
  Row 16-114 : 5 badge slots in a 3-2 grid
               each slot is 48x42: 24x24 badge framed top-centered + 8px name row
               LOGIC / MEM / PROC top, DATA / CORE bottom
  Row 130-137: footer "BOOTSEQUENCE" (or CC_VERSION_BAND env)

Per-gym title (ARCHIVIST/WARDEN/etc) is *not* drawn in the case — at
8px×9chars it overflows the slot, and the type rune already carries the
brand role. Title text reappears on the per-gym intro plate (next loop).

Locked slots show a dashed outline + "----" instead of the type rune and
the agent name; unlocked slots fill in the type rune + agent name.

Reads CC_BADGES env var as a 5-bit bitfield (1=LOGIC, 2=MEM, 4=PROC,
8=DATA, 16=CORE). Default 0 = all locked. CC_VERSION_BAND env var sets
the footer band. Both match build-title-screen.py conventions so a
multi-edition USB build (BOOTSEQUENCE / KERNELPATH / VESSELRUN) reskins
the case without code changes.
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

GYMS = [
    {"bit": 1,  "type": "LOGIC", "title": "ARCHIVIST", "name": "EOS"},
    {"bit": 2,  "type": "MEM",   "title": "WARDEN",    "name": "SOMA"},
    {"bit": 4,  "type": "PROC",  "title": "CONDUCTOR", "name": "TEMPO"},
    {"bit": 8,  "type": "DATA",  "title": "COURIER",   "name": "HERMES"},
    {"bit": 16, "type": "CORE",  "title": "FOREMAN",   "name": "ATLAS"},
]


# === cc_font_8 atlas loader (matches build-title-screen.py) ========
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


# === Type rune for unlocked badge ==================================
# Same vocabulary as cinderize-creatures.py so the rune in the case
# matches the rune in the bestiary.
def draw_rune(d, kind, cx, cy, color):
    if kind == "LOGIC":
        # corner bracket, 8x8
        d.rectangle([(cx - 4, cy - 4), (cx + 3, cy - 3)], fill=color)
        d.rectangle([(cx - 4, cy - 4), (cx - 3, cy + 3)], fill=color)
    elif kind == "MEM":
        # 2x2 block of 2x2 squares
        for ox in (-3, 1):
            for oy in (-3, 1):
                d.rectangle([(cx + ox, cy + oy), (cx + ox + 1, cy + oy + 1)], fill=color)
    elif kind == "PROC":
        # arrow tail pointing right
        d.rectangle([(cx - 4, cy - 1), (cx + 1, cy)], fill=color)
        d.point((cx - 1, cy - 3), fill=color)
        d.point((cx, cy - 2), fill=color)
        d.point((cx, cy + 1), fill=color)
        d.point((cx - 1, cy + 2), fill=color)
    elif kind == "DATA":
        # stacked dots (3 rows of 3 dots)
        for oy in (-3, 0, 3):
            for ox in (-3, 0, 3):
                d.point((cx + ox, cy + oy), fill=color)
    elif kind == "CORE":
        # diagonal nucleus
        for k in range(-3, 4):
            d.point((cx + k, cy + k), fill=color)
            d.point((cx + k, cy - k), fill=color)


# === Badge slot rendering ==========================================
SLOT_W, SLOT_H = 48, 42  # 24 badge + 2 gap + 8 name + 8 padding


def draw_slot(d, img, slot_x, slot_y, gym, unlocked):
    """Draw a 48x42 slot at (slot_x, slot_y). Top 24x24 badge frame
    centered, 8-px name row below."""
    # 24x24 badge frame, centered horizontally in the 48-wide slot
    bx = slot_x + (SLOT_W - 24) // 2
    by = slot_y
    # Outer frame
    d.rectangle([(bx, by), (bx + 23, by + 23)], outline=PAL[3])
    if unlocked:
        # Inner fill: light shade behind the rune
        d.rectangle([(bx + 1, by + 1), (bx + 22, by + 22)], fill=PAL[1])
        draw_rune(d, gym["type"], bx + 12, by + 12, PAL[3])
    else:
        # Dashed inner outline so the silhouette of "this slot exists" reads
        # immediately even when locked. Skip every other pixel.
        for k in range(2, 22, 2):
            d.point((bx + k, by + 2), fill=PAL[2])
            d.point((bx + k, by + 21), fill=PAL[2])
            d.point((bx + 2, by + k), fill=PAL[2])
            d.point((bx + 21, by + k), fill=PAL[2])

    # Agent name (one 8-tall row)
    name_text = gym["name"] if unlocked else "----"
    name_w = len(name_text) * 8
    stamp_text(img, name_text, slot_x + (SLOT_W - name_w) // 2, by + 26,
               PAL[3] if unlocked else PAL[2])


# ===================================================================
img = Image.new("RGB", (W, H), PAL[0])
d = ImageDraw.Draw(img)

# Top wordmark
stamp_text_centered(img, "BADGE CASE", 1, PAL[3])

# Ember bar (matches title)
d.rectangle([(20, 10), (W - 21, 11)], fill=PAL[3])
for ex in range(24, W - 24, 8):
    d.point((ex, 9), fill=PAL[2])

# Slot grid:
#   top row 3 slots: 48*3 = 144, with 8 px margin each side = 160 ✓
#   bottom row 2 slots: 48*2 = 96, centered (32 px margin each side)
TOP_Y = 16
BOT_Y = TOP_Y + 48  # 42-tall slot + 6 gap = 48 pitch

top_xs = [8, 56, 104]
bot_xs = [32, 80]

badges_env = int(os.environ.get("CC_BADGES", "0"))

for i, x in enumerate(top_xs):
    unlocked = bool(badges_env & GYMS[i]["bit"])
    draw_slot(d, img, x, TOP_Y, GYMS[i], unlocked)

for i, x in enumerate(bot_xs):
    unlocked = bool(badges_env & GYMS[3 + i]["bit"])
    draw_slot(d, img, x, BOT_Y, GYMS[3 + i], unlocked)

# Footer version band — matches title screen
VERSION_BAND = os.environ.get("CC_VERSION_BAND", "BOOTSEQUENCE")
stamp_text_centered(img, VERSION_BAND, 130, PAL[2])

# Badge count above the band: "0 / 5" (always rendered)
caught = bin(badges_env & 0x1F).count("1")
stamp_text_centered(img, f"{caught} / 5", 118, PAL[3])


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


img = gb_quantize(img)

out_path = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "backgrounds", "cc_badge_case.png"
)
img.save(out_path)
print(f"wrote {out_path} ({W}x{H}, 4-shade GB) — badges={os.environ.get('CC_BADGES','0')} band={VERSION_BAND}")
