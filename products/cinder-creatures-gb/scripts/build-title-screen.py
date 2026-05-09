#!/usr/bin/env python3
"""
Build a Pokemon-Red/Blue-style title screen for CINDER CREATURES at 160x144.

Pokemon RBY title layout:
  Top 80px   : Mascot (CISCOTL — legendary CORE)
  88-104     : "CINDER  CREATURES" wordmark
  108-120    : "BOOTSEQUENCE" subtitle
  124-138    : copyright + press start

GB Studio expects a 160x144 PNG using the 4-shade GB palette so the engine
keeps it as one big background image (the engine handles the GB tile decomp).
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Authentic Game Boy DMG palette (greenscale)
PAL = {
    0: (224, 248, 208),   # lightest (off-white)
    1: (136, 192, 112),   # light
    2: (52, 104, 86),     # dark
    3: (8, 24, 32),       # darkest (near-black)
}

W, H = 160, 144
img = Image.new("RGB", (W, H), PAL[0])
d = ImageDraw.Draw(img)

# === Mascot frame (scaled-up CISCOTL silhouette) ===
# Read the 16x16 sprite, find dark pixels, scale 4x to 64x64, center top.
mascot_path = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "sprites", "creature_21.png"
)
mascot = Image.open(mascot_path).convert("RGB")
# Convert greenscale -> 4-shade GB palette by luminance
mw, mh = mascot.size
mq = Image.new("RGB", (mw, mh), PAL[0])
for y in range(mh):
    for x in range(mw):
        r, g, b = mascot.getpixel((x, y))
        lum = (r * 0.299 + g * 0.587 + b * 0.114)
        if lum < 40:
            shade = PAL[3]
        elif lum < 90:
            shade = PAL[2]
        elif lum < 160:
            shade = PAL[1]
        else:
            shade = PAL[0]
        mq.putpixel((x, y), shade)
# Scale up 4x with nearest-neighbor for crisp pixel art
mq = mq.resize((mw * 4, mh * 4), Image.NEAREST)
# Place at x=48 (centered horizontally), y=8
img.paste(mq, ((W - mq.width) // 2, 8))

# === Wordmark "CINDER CREATURES" in chunky pixel font ===
# Hand-rolled 8x8 letter glyphs (subset). Each glyph is 5 wide x 7 tall + 1 spacing.
# To stay reliable, use PIL default font scaled. Then re-quantize to GB palette.
try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 8)
except Exception:
    FONT = ImageFont.load_default()

def render_text(text, scale=2, color=PAL[3]):
    """Render text to a fresh transparent-bg image, return image."""
    bbox = FONT.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tmp = Image.new("RGB", (tw + 2, th + 2), PAL[0])
    td = ImageDraw.Draw(tmp)
    td.text((1 - bbox[0], 1 - bbox[1]), text, fill=color, font=FONT)
    if scale != 1:
        tmp = tmp.resize((tmp.width * scale, tmp.height * scale), Image.NEAREST)
    return tmp

def paste_centered(text, y, scale=2, color=PAL[3]):
    t = render_text(text, scale=scale, color=color)
    img.paste(t, ((W - t.width) // 2, y))

# Title wordmark (two lines)
paste_centered("CINDER",    78, scale=2)
paste_centered("CREATURES", 92, scale=2)

# Subtitle band
d.rectangle([(28, 108), (W - 28, 118)], fill=PAL[1], outline=PAL[3])
paste_centered("BOOTSEQUENCE", 109, scale=1, color=PAL[3])

# Footer
paste_centered("(c) MERIDIAN 2026", 124, scale=1, color=PAL[2])
paste_centered("PRESS START",       134, scale=1, color=PAL[3])

# Quantize the entire image strictly to 4 GB shades (some font edges may have intermediate values)
def gb_quantize(image):
    out = Image.new("RGB", image.size)
    palette_rgb = [PAL[i] for i in range(4)]
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = image.getpixel((x, y))
            best = min(palette_rgb, key=lambda p: (p[0]-r)**2 + (p[1]-g)**2 + (p[2]-b)**2)
            out.putpixel((x, y), best)
    return out

img = gb_quantize(img)

out_path = os.path.join(
    os.path.dirname(__file__), "..", "plugins", "cinder-creatures", "backgrounds", "cc_title_screen.png"
)
img.save(out_path)
print(f"wrote {out_path} ({W}x{H}, 4-shade GB)")
