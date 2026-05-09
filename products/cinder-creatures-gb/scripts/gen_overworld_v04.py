#!/usr/bin/env python3
# Generate Pokemon-GB-style overworld backgrounds + tileset for plugin v0.4.
# 4-color DMG palette, 8x8 tile grid, 160x144 BG canvas.
from PIL import Image, ImageDraw
import os, random

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]  # GB green palette
W, H = 160, 144
TS = 8  # tile size
OUT = os.path.join(os.path.dirname(__file__), '..', 'plugins', 'cinder-creatures', 'backgrounds')
TS_OUT = os.path.join(os.path.dirname(__file__), '..', 'plugins', 'cinder-creatures', 'tilesets')
os.makedirs(OUT, exist_ok=True)
os.makedirs(TS_OUT, exist_ok=True)

def new_bg():
    return Image.new('RGB', (W, H), DMG[3])

def put_grass(img, x, y, density=0.25):
    px = img.load()
    for dx in range(TS):
        for dy in range(TS):
            if random.random() < density:
                px[x+dx, y+dy] = DMG[2]

def put_path(img, x, y):
    px = img.load()
    for dx in range(TS):
        for dy in range(TS):
            px[x+dx, y+dy] = DMG[1] if (dx + dy) % 5 == 0 else DMG[3]

def put_tree(img, x, y):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x+TS-1, y+TS-1], fill=DMG[2])
    d.rectangle([x+1, y+1, x+TS-2, y+TS-2], fill=DMG[1])
    d.point([(x+3, y+3), (x+5, y+5), (x+2, y+5)], fill=DMG[0])
    d.rectangle([x+3, y+TS-2, x+4, y+TS-1], fill=DMG[0])  # trunk

def put_water(img, x, y, frame=0):
    px = img.load()
    for dy in range(TS):
        for dx in range(TS):
            if (dx + dy + frame) % 4 == 0:
                px[x+dx, y+dy] = DMG[0]
            elif (dx + dy + frame) % 4 == 1:
                px[x+dx, y+dy] = DMG[1]
            else:
                px[x+dx, y+dy] = DMG[1]

def put_fence(img, x, y):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y+3, x+TS-1, y+4], fill=DMG[0])
    d.rectangle([x, y+5, x+TS-1, y+5], fill=DMG[1])
    d.rectangle([x+2, y, x+3, y+TS-1], fill=DMG[0])
    d.rectangle([x+5, y, x+6, y+TS-1], fill=DMG[0])

def put_sign(img, x, y):
    d = ImageDraw.Draw(img)
    d.rectangle([x+1, y+1, x+TS-2, y+5], fill=DMG[1])
    d.rectangle([x+2, y+2, x+TS-3, y+4], fill=DMG[3])
    d.rectangle([x+3, y+5, x+4, y+TS-1], fill=DMG[0])  # post

def put_house_wall(img, x, y):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x+TS-1, y+TS-1], fill=DMG[1])
    d.point([(x+1, y+1), (x+5, y+5), (x+3, y+3)], fill=DMG[0])

def put_house_roof(img, x, y, side='m'):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x+TS-1, y+TS-1], fill=DMG[0])
    d.line([(x, y+3), (x+TS-1, y+3)], fill=DMG[1])

def put_door(img, x, y):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x+TS-1, y+TS-1], fill=DMG[1])
    d.rectangle([x+1, y+1, x+TS-2, y+TS-1], fill=DMG[0])
    d.point([(x+5, y+4)], fill=DMG[2])  # knob

random.seed(42)

# ── ROUTE 1 (grass + path through middle, trees border, sign) ─────────
img = new_bg()
for ty in range(0, H, TS):
    for tx in range(0, W, TS):
        put_grass(img, tx, ty)
# horizontal path band y=64..96
for ty in range(64, 96, TS):
    for tx in range(0, W, TS):
        put_path(img, tx, ty)
# tree border (top + bottom rows)
for tx in range(0, W, TS):
    if random.random() < 0.6:
        put_tree(img, tx, 0)
    if random.random() < 0.6:
        put_tree(img, tx, H - TS)
# trees scattered in upper grass
for _ in range(8):
    put_tree(img, random.randint(0, 19) * TS, random.randint(1, 6) * TS)
# fence along south path edge
for tx in range(0, W, TS):
    put_fence(img, tx, 96)
# a sign post
put_sign(img, 40, 56)
img.save(os.path.join(OUT, 'cc_route1_bg.png'))

# ── PALLET-ISH TOWN (houses, path, grass plot) ───────────────────────
img = new_bg()
for ty in range(0, H, TS):
    for tx in range(0, W, TS):
        put_grass(img, tx, ty, 0.15)
# a house: 3-tile-wide × 3-tile-tall
def house(img, hx, hy):
    for tx in range(hx, hx + 3*TS, TS):
        put_house_roof(img, tx, hy)
    for ty in range(hy + TS, hy + 3*TS, TS):
        for tx in range(hx, hx + 3*TS, TS):
            put_house_wall(img, tx, ty)
    put_door(img, hx + TS, hy + 2*TS)
house(img, 16, 24)
house(img, 96, 24)
# vertical path connecting them
for ty in range(0, H, TS):
    for tx in range(72, 96, TS):
        put_path(img, tx, ty)
# horizontal path across bottom
for ty in range(112, H, TS):
    for tx in range(0, W, TS):
        put_path(img, tx, ty)
# fence around bottom-right grass plot
for tx in range(120, W, TS):
    put_fence(img, tx, 80)
img.save(os.path.join(OUT, 'cc_town_bg.png'))

# ── PARTY MENU SCREEN (6 slot list + cursor area) ────────────────────
img = Image.new('RGB', (W, H), DMG[3])
d = ImageDraw.Draw(img)
# outer border
d.rectangle([2, 2, W-3, H-3], outline=DMG[0], width=1)
# title bar
d.rectangle([4, 4, W-5, 16], fill=DMG[1])
# 6 slot rows
for i in range(6):
    y = 20 + i*20
    d.rectangle([6, y, W-7, y+18], outline=DMG[1], width=1)
    d.rectangle([8, y+2, 24, y+16], fill=DMG[1])  # sprite slot
img.save(os.path.join(OUT, 'cc_party_bg.png'))

# ── BAG / ITEM SCREEN ────────────────────────────────────────────────
img = Image.new('RGB', (W, H), DMG[3])
d = ImageDraw.Draw(img)
d.rectangle([2, 2, W-3, H-3], outline=DMG[0], width=1)
d.rectangle([4, 4, W-5, 16], fill=DMG[1])
d.text((8, 5), "ITEMS", fill=DMG[3])
for i in range(7):
    y = 22 + i*16
    d.line([(6, y), (W-7, y)], fill=DMG[1])
img.save(os.path.join(OUT, 'cc_bag_bg.png'))

# ── 256x256 OVERWORLD TILESET (32x32 grid of 8x8 tiles) ─────────────
ts = Image.new('RGB', (256, 256), DMG[3])
# row 0: grass variants
for i in range(8):
    put_grass(ts, i*TS, 0, 0.1 + i*0.07)
# row 1: paths
for i in range(8):
    put_path(ts, i*TS, TS)
# row 2: trees + fences
for i in range(4):
    put_tree(ts, i*TS, 2*TS)
for i in range(4):
    put_fence(ts, (4+i)*TS, 2*TS)
# row 3: water frames
for i in range(8):
    put_water(ts, i*TS, 3*TS, frame=i)
# row 4: signs + doors
put_sign(ts, 0, 4*TS)
put_door(ts, TS, 4*TS)
# row 5: house pieces
put_house_wall(ts, 0, 5*TS)
put_house_roof(ts, TS, 5*TS)
ts.save(os.path.join(TS_OUT, 'cc_overworld_tileset.png'))

print("Wrote backgrounds: cc_route1_bg, cc_town_bg, cc_party_bg, cc_bag_bg")
print("Wrote tileset: cc_overworld_tileset.png (256x256, 32x32 tiles)")
