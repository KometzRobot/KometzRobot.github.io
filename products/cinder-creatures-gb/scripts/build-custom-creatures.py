#!/usr/bin/env python3
"""Hand-drawn custom creature sprites — Joel directive Loop 9951:
'Create custom assets as long as they match in style.'

Each creature is described as a 16x16 pixel grid in DMG palette.
This script writes out PNGs to:
  - products/cinder-creatures-gb/custom-creatures/<id>_<NAME>.png  (source of truth)
  - products/cinder-creatures-gb/cinder-starter/assets/sprites/creature_<id>.png  (deployed)

Override semantics: any species id present here SHADOWS the cinderize-creatures.py
output. cinderize will skip ids that already have a custom file. See cinderize-creatures.py.

Palette glyphs:
  '.' lightest (224,248,208) — background
  '-' light    (136,192,112)
  '+' dark     ( 52,104, 86)
  '#' darkest  (  8, 24, 32)
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CUSTOM_DIR = ROOT / "custom-creatures"
CUSTOM_DIR.mkdir(exist_ok=True)

# Mirror cinderize-creatures.py DST_TARGETS so GB Studio loads the custom
# sprite from every path it might read from.
DEPLOY_TARGETS = [
    (ROOT / "plugins/cinder-creatures/sprites",                 "creature_{:02d}.png"),
    (ROOT / "cinder-starter/plugins/cinder-creatures/sprites",  "creature_{:02d}.png"),
    (ROOT / "cinder-starter/assets/sprites",                    "creature_{:02d}.png"),
    (ROOT / "assets/sprites",                                   "cinder_{:02d}.png"),
]

DMG = {
    '.': (224, 248, 208),
    '-': (136, 192, 112),
    '+': ( 52, 104,  86),
    '#': (  8,  24,  32),
}

# species id -> (NAME, 16-row grid)
CUSTOM = {}

# id 8 — REGEXEL (DATA type, gym leader Carrier Wick's signature).
# Pattern-matcher: anchor caret eyes, slash bands across the body, $-tail.
CUSTOM[8] = ("REGEXEL", [
    "................",
    "......####......",
    ".....#----#.....",
    "....#-#--#-#....",
    "...#--####--#...",
    "..#-+-#--#-+-#..",
    "..#----##----#..",
    "..#-+-####-+-#..",
    "..#----##----#..",
    "..#-+-#--#-+-#..",
    "...#--####--#...",
    "....#-+##+-#....",
    ".....#----#.....",
    "......#--#......",
    ".....##..##.....",
    "................",
])

# id 36 — INTGAR (DATA, leader team). Squat round body, tally-stripe back,
# always-rounds-down so the bottom edge is a hard floor.
CUSTOM[36] = ("INTGAR", [
    "................",
    "................",
    "......####......",
    ".....#-##-#.....",
    "....#-####-#....",
    "...#--+--+--#...",
    "...#-+-++-+-#...",
    "...#--+--+--#...",
    "...#-+----+-#...",
    "...#--+--+--#...",
    "...#-++--++-#...",
    "...#--####--#...",
    "....##----##....",
    "....##++++##....",
    "....########....",
    "................",
])

# id 38 — STRTERM (DATA, leader team). Stringy/wiry body, ends in null (\0).
# Tail ends with a pixel zero glyph.
CUSTOM[38] = ("STRTERM", [
    "................",
    "....##....##....",
    "...#--#..#--#...",
    "...#-+-##-+-#...",
    "...#--####--#...",
    "....#------#....",
    "....#-+--+-#....",
    "....#------#....",
    "....#--##--#....",
    ".....#----#.....",
    ".....#-++-#.....",
    ".....#----#.....",
    "......#--#......",
    "......#--#......",
    ".....#-##-#.....",
    "......####......",
])

# Starter trio — Loop 9953. These are the FIRST creatures the player sees in
# Professor Cinder's lab; first impression of the entire bestiary depends on
# these three reading distinctly at 16x16 in DMG palette.

# id 3 — KERNITE (CORE/tank). Squat pebble with a hard diamond nucleus.
# Tank role: compact, low silhouette, no protrusions, reads as solid/heavy.
CUSTOM[3] = ("KERNITE", [
    "................",
    "................",
    "......####......",
    ".....#----#.....",
    "....##----##....",
    "...##--##--##...",
    "..##---++---##..",
    "..#---+##+---#..",
    "..#---+##+---#..",
    "..##---++---##..",
    "...##--##--##...",
    "....##----##....",
    ".....##--##.....",
    "....##....##....",
    "....##....##....",
    "................",
])

# id 4 — RECURSE (LOGIC/glass cannon). Nested concentric rings — recursion
# made literal. Three frames, a paired core inside, no limbs (it IS the call).
CUSTOM[4] = ("RECURSE", [
    "................",
    ".....######.....",
    "....#------#....",
    "...#-######-#...",
    "..#-#------#-#..",
    "..#-#-####-#-#..",
    "..#-#-#--#-#-#..",
    "..#-#-#++#-#-#..",
    "..#-#-#--#-#-#..",
    "..#-#-####-#-#..",
    "..#-#------#-#..",
    "...#-######-#...",
    "....#------#....",
    ".....######.....",
    "......####......",
    "................",
])

# id 6 — BYTEFLY (DATA/swarm). Small body, wings out, motion dots on the
# extreme edges — speed reads at a glance even in 4 shades.
CUSTOM[6] = ("BYTEFLY", [
    "................",
    "................",
    "....##....##....",
    "...#--#..#--#...",
    "....##-##-##....",
    "...##-####-##...",
    "..##--####--##..",
    ".+#---####---#+.",
    ".+#---####---#+.",
    "..##--####--##..",
    "...##-####-##...",
    "....##-##-##....",
    ".....##++##.....",
    "......####......",
    ".......##.......",
    "................",
])


def render(grid: list[str]) -> Image.Image:
    img = Image.new("RGB", (16, 16), DMG['.'])
    pixels = img.load()
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            pixels[x, y] = DMG.get(ch, DMG['.'])
    # quantize to 4-color palette to match other sprites (mode P)
    pal = Image.new("P", (1, 1))
    pal_bytes = []
    for c in [DMG['.'], DMG['-'], DMG['+'], DMG['#']]:
        pal_bytes += list(c)
    pal_bytes += [0] * (768 - len(pal_bytes))
    pal.putpalette(pal_bytes)
    return img.quantize(palette=pal, dither=Image.Dither.NONE)


def main() -> int:
    for sid, (name, grid) in CUSTOM.items():
        assert len(grid) == 16 and all(len(r) == 16 for r in grid), f"{name} not 16x16"
        sprite = render(grid)
        src_path = CUSTOM_DIR / f"{sid:02d}_{name}.png"
        sprite.save(src_path)
        for dst_dir, name_tmpl in DEPLOY_TARGETS:
            dst_dir.mkdir(parents=True, exist_ok=True)
            sprite.save(dst_dir / name_tmpl.format(sid))
        print(f"  custom {sid:02d} {name}")
    print(f"wrote {len(CUSTOM)} custom creature sprites -> {len(DEPLOY_TARGETS)} target dirs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
