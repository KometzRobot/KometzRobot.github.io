#!/usr/bin/env python3
# Cinderize CC0 creature sprites: quantize to GB DMG palette, add outline,
# burn in a type-mark (1-2px corner glyph) so all 56 creatures read as one
# unified Cinder bestiary instead of generic CC0 mons.
#
# In:  cc0-creatures-16/creature_NN.png   (16x16 RGBA, ~169 colors)
# Out: plugins/cinder-creatures/sprites/creature_NN.png  (16x16 indexed, GB DMG)
#
# Joel directive Loop 9800: "All creatures need to look visually altered from
# the originals to allow a more cinder consistent look".

import json
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "cc0-creatures-16")
DATA_FILE = os.path.join(ROOT, "plugins", "cinder-creatures", "data", "creatures.json")
# Hand-drawn overrides (Joel directive Loop 9951): any id with a file in this
# directory shadows the cinderized CC0 sprite. Built by build-custom-creatures.py.
CUSTOM_DIR = os.path.join(ROOT, "custom-creatures")

# Write the cinderized sprite to every place GB Studio might load it from.
# Tuples are (target_dir, filename_template) — template gets a 2-digit id.
# Until v0.24 only the plugin dirs were updated, so the game was still
# loading raw CC0 sprites from assets/. v0.25 fixes that by syncing all
# four locations on every run.
DST_TARGETS = [
    (os.path.join(ROOT, "plugins", "cinder-creatures", "sprites"),
     "creature_{:02d}.png"),
    (os.path.join(ROOT, "cinder-starter", "plugins", "cinder-creatures", "sprites"),
     "creature_{:02d}.png"),
    (os.path.join(ROOT, "cinder-starter", "assets", "sprites"),
     "creature_{:02d}.png"),
    (os.path.join(ROOT, "assets", "sprites"),
     "cinder_{:02d}.png"),
]

# GB Studio DMG palette (lightest -> darkest)
DMG = [(224, 248, 208), (136, 192, 112), (52, 104, 86), (8, 24, 32)]

# Type-mark: which palette index to stamp where (col,row), per type.
# Subtle: 2-3 pixels in lower-right quadrant. Reads as a "rune" the player
# starts to recognize after a few encounters — that's the Cinder thumbprint.
TYPE_MARK = {
    "DATA":  [(14, 14), (14, 12)],            # two stacked dots = bits
    "LOGIC": [(13, 14), (14, 14), (14, 13)],  # corner bracket
    "MEM":   [(13, 13), (14, 13), (13, 14), (14, 14)],  # 2x2 block
    "PROC":  [(12, 14), (13, 14), (14, 14), (14, 13)],  # arrow tail
    "CORE":  [(13, 13), (14, 14)],            # diagonal nucleus
}


def to_dmg(im: Image.Image) -> Image.Image:
    """Quantize to the 4 DMG shades by closest-luminance match."""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    out = Image.new("RGB", (w, h), DMG[0])
    px = rgba.load()
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 96:
                op[x, y] = DMG[0]  # transparent -> lightest (background)
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > 200:   op[x, y] = DMG[0]
            elif lum > 130: op[x, y] = DMG[1]
            elif lum > 60:  op[x, y] = DMG[2]
            else:           op[x, y] = DMG[3]
    return out


def add_outline(im: Image.Image) -> Image.Image:
    """1-pixel dark outline around any non-background pixel.
    Pushes the silhouette forward — the Cinder unifying treatment."""
    w, h = im.size
    out = im.copy()
    src = im.load()
    op = out.load()
    bg = DMG[0]
    dark = DMG[3]
    for y in range(h):
        for x in range(w):
            if src[x, y] != bg:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny] not in (bg, dark):
                    op[x, y] = dark
                    break
    return out


def stamp_type_mark(im: Image.Image, ctype: str) -> Image.Image:
    """Burn the type rune into lower-right corner using darkest shade.
    Skips pixels that would clobber the silhouette (only writes onto bg)."""
    pixels = TYPE_MARK.get(ctype, [])
    if not pixels:
        return im
    out = im.copy()
    op = out.load()
    src = im.load()
    bg = DMG[0]
    dark = DMG[3]
    for x, y in pixels:
        if src[x, y] == bg:
            op[x, y] = dark
    return out


def cinderize(src_path: str, dst_path: str, ctype: str) -> None:
    im = Image.open(src_path)
    im = to_dmg(im)
    im = add_outline(im)
    im = stamp_type_mark(im, ctype)
    # Re-encode as indexed PNG so GB Studio is happy.
    pal = []
    for c in DMG:
        pal.extend(c)
    pal.extend([0] * (768 - len(pal)))
    indexed = Image.new("P", im.size)
    indexed.putpalette(pal)
    rgb = im.load()
    ip = indexed.load()
    lookup = {DMG[i]: i for i in range(4)}
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            ip[x, y] = lookup[rgb[x, y]]
    indexed.save(dst_path, optimize=True)


def main() -> int:
    with open(DATA_FILE) as f:
        data = json.load(f)
    by_id = {s["id"]: s for s in data["species"]}

    if not os.path.isdir(SRC_DIR):
        print(f"missing src: {SRC_DIR}", file=sys.stderr)
        return 1
    for dst_dir, _ in DST_TARGETS:
        os.makedirs(dst_dir, exist_ok=True)

    custom_ids = set()
    if os.path.isdir(CUSTOM_DIR):
        for fn in os.listdir(CUSTOM_DIR):
            if fn[:2].isdigit():
                custom_ids.add(int(fn[:2]))

    n = 0
    skipped = 0
    for fn in sorted(os.listdir(SRC_DIR)):
        if not fn.startswith("creature_") or not fn.endswith(".png"):
            continue
        cid = int(fn[9:11])
        if cid in custom_ids:
            skipped += 1
            continue
        species = by_id.get(cid)
        ctype = species["type"] if species else "CORE"
        src_path = os.path.join(SRC_DIR, fn)
        for dst_dir, name_tmpl in DST_TARGETS:
            cinderize(src_path, os.path.join(dst_dir, name_tmpl.format(cid)), ctype)
        n += 1
    print(f"cinderized {n} creatures -> {len(DST_TARGETS)} target dirs"
          f" (skipped {skipped} custom)" if skipped else
          f"cinderized {n} creatures -> {len(DST_TARGETS)} target dirs")
    for dst_dir, _ in DST_TARGETS:
        print(f"  {os.path.relpath(dst_dir, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
