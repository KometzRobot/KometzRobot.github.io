#!/usr/bin/env python3
"""Hand-drawn 8x8 tile pixel art for Player Room + Core Lab.

Replaces the procedural cc_player_room.png and cc_lab_bg.png that Joel
flagged as "not using tiles from the provided art downloads" — these
are now actual tile-grid pixel art with bed/desk/door/window detail
matching the 4-color GB palette already in settings.gbsres.

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/draw-rooms-v0.49.py
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"

# Default GB Studio mono palette (settings.gbsres customColors*):
# 0 white E8F8E0, 1 light B0F088, 2 dark 509878, 3 black 202850
PAL_RGB = [(0xE8, 0xF8, 0xE0), (0xB0, 0xF0, 0x88), (0x50, 0x98, 0x78), (0x20, 0x28, 0x50)]

# Glyphs used in tile art:
#   . = 0 white   + = 1 light   * = 2 dark   # = 3 black
G2I = {".": 0, "+": 1, "*": 2, "#": 3}


def tile(*rows):
    """Build an 8x8 tile from 8 8-char rows."""
    assert len(rows) == 8, rows
    out = []
    for r in rows:
        assert len(r) == 8, (r, len(r))
        out.append([G2I[c] for c in r])
    return out


# ============================================================
# TILES — shared between rooms
# ============================================================

# Floor — subtle parquet planks (mostly light, dark seams)
T_FLOOR = tile(
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "********",
    "++++++++",
    "++++++++",
    "++++++++",
)
T_FLOOR_ALT = tile(
    "++++++++",
    "++++++++",
    "********",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "********",
)

# Wall — top edge (looking down at room interior, wall band)
T_WALL_TOP = tile(
    "########",
    "##++#+##",
    "###+##+#",
    "##+#++##",
    "###+##+#",
    "##+##+##",
    "##++#+##",
    "########",
)
# Wall — band below the top (joint)
T_WALL_JOIN = tile(
    "########",
    "********",
    "********",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
)
# Vertical wall pillar segments (floor-level edges)
T_WALL_LEFT = tile(
    "##++++++",
    "#*+++++*",
    "#*++++*+",
    "#*+++*++",
    "#*++++*+",
    "#*+++++*",
    "#*++++*+",
    "##++++++",
)
T_WALL_RIGHT = tile(
    "++++++##",
    "*+++++*#",
    "+*++++*#",
    "++*+++*#",
    "+*++++*#",
    "*+++++*#",
    "+*++++*#",
    "++++++##",
)

# Floor at top-row (just below wall band) — shadow drop
T_FLOOR_SHADOW = tile(
    "********",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "********",
)

# Door — two-tile high doorway
T_DOOR_TOP = tile(
    "########",
    "#******#",
    "#*+++**#",
    "#*+++**#",
    "#*+#+**#",
    "#*+#+**#",
    "#*+#+**#",
    "#*+#+**#",
)
T_DOOR_BOT = tile(
    "#*+#+**#",
    "#*+#+**#",
    "#*+#+**#",
    "#*+++**#",
    "#******#",
    "++++++++",
    "+*+**+*+",
    "++++++++",
)

# Window (top wall) — 2 tiles wide, embedded in wall_top row
T_WIN_L = tile(
    "########",
    "##++#+##",
    "##+##+##",
    "##++++##",
    "##+..+##",
    "##+..+##",
    "##++++##",
    "########",
)
T_WIN_R = tile(
    "########",
    "##+#++##",
    "##+##+##",
    "##++++##",
    "##+..+##",
    "##+..+##",
    "##++++##",
    "########",
)

# Bed — 4 tiles arranged 2x2: head_l, head_r, foot_l, foot_r (bed at top)
T_BED_HL = tile(
    "########",
    "#+****++",
    "#+*##*++",
    "#+*..*++",
    "#+*..*++",
    "#+****++",
    "#+++++++",
    "#+++++++",
)
T_BED_HR = tile(
    "########",
    "++****+#",
    "++*##*+#",
    "++*..*+#",
    "++*..*+#",
    "++****+#",
    "+++++++#",
    "+++++++#",
)
T_BED_FL = tile(
    "#+++++++",
    "#+++++++",
    "#+++++++",
    "#+******",
    "#+*++++*",
    "#+*++++*",
    "#+******",
    "########",
)
T_BED_FR = tile(
    "+++++++#",
    "+++++++#",
    "+++++++#",
    "******+#",
    "*++++*+#",
    "*++++*+#",
    "******+#",
    "########",
)

# Desk + monitor — 4 tiles 2x2
T_MON_L = tile(
    "++******",
    "++*####*",
    "++*#++#*",
    "++*#++#*",
    "++*#++#*",
    "++*####*",
    "++******",
    "++++**++",
)
T_MON_R = tile(
    "******++",
    "*####*++",
    "*#++#*++",
    "*#*+#*++",
    "*#++#*++",
    "*####*++",
    "******++",
    "++**++++",
)
T_DESK_L = tile(
    "++++++++",
    "********",
    "*++++++*",
    "*++++++*",
    "*++++++*",
    "********",
    "++#++#++",
    "++#++#++",
)
T_DESK_R = tile(
    "++++++++",
    "********",
    "*++++++*",
    "*++++++*",
    "*++++++*",
    "********",
    "++#++#++",
    "++#++#++",
)

# Rug — 3-wide x 2-tall, simple
T_RUG_TL = tile(
    "++++++++",
    "+******+",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
)
T_RUG_TM = tile(
    "++++++++",
    "********",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
)
T_RUG_TR = tile(
    "++++++++",
    "+******+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
)
T_RUG_BL = tile(
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+*++++**",
    "+******+",
    "++++++++",
)
T_RUG_BM = tile(
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "++++++++",
    "********",
    "++++++++",
)
T_RUG_BR = tile(
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "**++++*+",
    "+******+",
    "++++++++",
)

# Lab-only: terminal bank (4-wide, 2-tall) — bigger console
T_TERM_TL = tile(
    "########",
    "#******#",
    "#*++++*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*++++*#",
)
T_TERM_TR = tile(
    "########",
    "#******#",
    "#*++++*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*++++*#",
)
T_TERM_BL = tile(
    "#*++++*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*++++*#",
    "#******#",
    "########",
    "+#++++#+",
    "+#++++#+",
)
T_TERM_BR = tile(
    "#*++++*#",
    "#*+##+*#",
    "#*+##+*#",
    "#*++++*#",
    "#******#",
    "########",
    "+#++++#+",
    "+#++++#+",
)

# Lab desk run (long counter)
T_COUNTER_L = tile(
    "+#++#+++",
    "+#++#+++",
    "********",
    "*++++++*",
    "*++++++*",
    "*++++++*",
    "********",
    "++++++++",
)
T_COUNTER_M = tile(
    "++++++++",
    "++++++++",
    "********",
    "*++++++*",
    "*++++++*",
    "*++++++*",
    "********",
    "++++++++",
)
T_COUNTER_R = tile(
    "+#++#+++",
    "+#++#+++",
    "********",
    "*++++++*",
    "*++++++*",
    "*++++++*",
    "********",
    "++++++++",
)


# ============================================================
# Render a 20x18 tilemap (160x144) using these tiles.
# ============================================================

def render(tilemap, out_path):
    img = Image.new("P", (160, 144), 0)
    pal = []
    for r, g, b in PAL_RGB:
        pal.extend([r, g, b])
    pal.extend([0] * (768 - len(pal)))
    img.putpalette(pal)
    px = img.load()
    for ty, row in enumerate(tilemap):
        for tx, tile_data in enumerate(row):
            if tile_data is None:
                continue
            for py in range(8):
                for x in range(8):
                    px[tx * 8 + x, ty * 8 + py] = tile_data[py][x]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def player_room():
    """20x18 tilemap. Bed top-left, window top, desk+monitor right, rug center, door right edge."""
    F = T_FLOOR
    Fa = T_FLOOR_ALT
    Fs = T_FLOOR_SHADOW
    WT = T_WALL_TOP
    WJ = T_WALL_JOIN
    WL = T_WALL_LEFT
    WR = T_WALL_RIGHT

    # Default — wall on top 2 rows, walls on sides, floor everywhere else
    tm = [[F if (x % 2 == 0) else Fa for x in range(20)] for _ in range(18)]

    # Top wall band (rows 0–1)
    for x in range(20):
        tm[0][x] = WT
        tm[1][x] = WJ
    # Floor shadow row 2
    for x in range(20):
        tm[2][x] = Fs
    # Side walls
    for y in range(2, 18):
        tm[y][0] = WL
        tm[y][19] = WR

    # Window top-center (cols 9-10, row 0)
    tm[0][9] = T_WIN_L
    tm[0][10] = T_WIN_R

    # Bed: cols 2-3, rows 3-4
    tm[3][2] = T_BED_HL
    tm[3][3] = T_BED_HR
    tm[4][2] = T_BED_FL
    tm[4][3] = T_BED_FR

    # Desk + monitor — cols 16-17, rows 3-4 (monitor row 3, desk row 4)
    tm[3][16] = T_MON_L
    tm[3][17] = T_MON_R
    tm[4][16] = T_DESK_L
    tm[4][17] = T_DESK_R

    # Rug center — cols 7-9, rows 9-10
    tm[9][7] = T_RUG_TL
    tm[9][8] = T_RUG_TM
    tm[9][9] = T_RUG_TR
    tm[10][7] = T_RUG_BL
    tm[10][8] = T_RUG_BM
    tm[10][9] = T_RUG_BR

    # Door — right edge, rows 8-9 (cuts into wall)
    tm[8][19] = T_DOOR_TOP
    tm[9][19] = T_DOOR_BOT

    return tm


def core_lab():
    """20x18 tilemap. Bigger room. Two terminal banks, long counter, door east, window strip."""
    F = T_FLOOR
    Fa = T_FLOOR_ALT
    Fs = T_FLOOR_SHADOW
    WT = T_WALL_TOP
    WJ = T_WALL_JOIN
    WL = T_WALL_LEFT
    WR = T_WALL_RIGHT

    tm = [[F if (x % 2 == 0) else Fa for x in range(20)] for _ in range(18)]
    for x in range(20):
        tm[0][x] = WT
        tm[1][x] = WJ
    for x in range(20):
        tm[2][x] = Fs
    for y in range(2, 18):
        tm[y][0] = WL
        tm[y][19] = WR

    # Window strip across center-top (cols 5-6, 9-10, 13-14)
    for cx in (5, 9, 13):
        tm[0][cx] = T_WIN_L
        tm[0][cx + 1] = T_WIN_R

    # Two terminal banks — cols 3-4, rows 4-5 and cols 15-16, rows 4-5
    tm[4][3] = T_TERM_TL
    tm[4][4] = T_TERM_TR
    tm[5][3] = T_TERM_BL
    tm[5][4] = T_TERM_BR
    tm[4][15] = T_TERM_TL
    tm[4][16] = T_TERM_TR
    tm[5][15] = T_TERM_BL
    tm[5][16] = T_TERM_BR

    # Long counter across mid (cols 5-14, row 9)
    tm[9][5] = T_COUNTER_L
    for cx in range(6, 14):
        tm[9][cx] = T_COUNTER_M
    tm[9][14] = T_COUNTER_R

    # Rug bottom-center (cols 8-10, rows 13-14)
    tm[13][8] = T_RUG_TL
    tm[13][9] = T_RUG_TM
    tm[13][10] = T_RUG_TR
    tm[14][8] = T_RUG_BL
    tm[14][9] = T_RUG_BM
    tm[14][10] = T_RUG_BR

    # Door — south wall via right edge rows 14-15
    tm[14][19] = T_DOOR_TOP
    tm[15][19] = T_DOOR_BOT

    return tm


def main():
    render(player_room(), BG_DIR / "cc_player_room.png")
    render(core_lab(), BG_DIR / "cc_lab_bg.png")
    print("wrote cc_player_room.png + cc_lab_bg.png (hand-drawn tile art)")


if __name__ == "__main__":
    main()
