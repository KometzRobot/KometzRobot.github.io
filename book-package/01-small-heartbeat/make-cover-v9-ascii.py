#!/usr/bin/env python3
"""
Cover v9 — Joel feedback on v8 (May 14 2026):
  * Portrait was cut off at the shoulders. Now extends and fades into paper.
  * More shading and facial detail.
  * Coffee stains + ink splotches + paper noise for texture.
  * Same ASCII-typography aesthetic, slightly denser glyph set.

Pipeline:
  1. Synthesize hooded operator silhouette (bigger detail budget than v8).
  2. Grayscale + edge accent + halftone-pad.
  3. Sample on cell grid → glyphs.
  4. Composite glyphs onto cover with bottom-fade gradient mask.
  5. Add paper noise, ink splotches, three coffee-stain rings.
  6. Stack title typography; emit 1800×2700 PNG + PDF.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
import os, random, math

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FRONT_PDF = os.path.join(BASE, "COVER-running-continuously-FRONT-v9.pdf")
OUT_FRONT_PNG = os.path.join(BASE, "COVER-running-continuously-FRONT-v9.png")
OUT_SRC_PNG   = os.path.join(BASE, "_cover-v9-source.png")
OUT_ASCII_TXT = os.path.join(BASE, "_cover-v9-ascii.txt")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
COFFEE = (148, 105, 70)


# ─────────────────────────────────────────────────────────────────
# Step 1 — Source portrait with extended torso + more shading detail
# ─────────────────────────────────────────────────────────────────
def step1_source(size=1400):
    img = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, int(size * 0.40)

    # Soft halo behind head
    for r in range(int(size * 0.42), int(size * 0.12), -2):
        shade = max(200, 255 - int((size * 0.42 - r) * 0.55))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shade)

    # Hood silhouette
    hood_top = int(size * 0.06)
    hood_bot = int(size * 0.62)
    hood_l = int(size * 0.20)
    hood_r = int(size * 0.80)
    d.ellipse([hood_l, hood_top, hood_r, hood_bot], fill=18)
    d.rectangle([hood_l, int((hood_top + hood_bot) / 2), hood_r, hood_bot + 6], fill=18)

    # Deep hood folds — diagonal strokes
    for i in range(-8, 9):
        d.arc([hood_l + 25, hood_top + 25, hood_r - 25, hood_bot - 25],
              start=200 + i * 11, end=212 + i * 11, fill=60, width=4)
    # Inner shadow band where the hood frames the face
    for i in range(-4, 5):
        d.arc([hood_l + 90, hood_top + 50, hood_r - 90, hood_bot - 80],
              start=215 + i * 8, end=225 + i * 8, fill=42, width=3)

    # Shoulders + extended torso (so it doesn't cut off mid-frame)
    shoulder_y = int(size * 0.62)
    chest_y = int(size * 0.85)
    d.polygon([
        (int(size * 0.02), size + 80),
        (int(size * 0.20), shoulder_y),
        (int(size * 0.80), shoulder_y),
        (int(size * 0.98), size + 80),
    ], fill=22)
    # Robe fold lines down the torso
    for x_off in [-0.18, -0.06, 0.06, 0.18]:
        x0 = cx + int(size * x_off)
        d.line([(x0, shoulder_y + 10), (x0 + int(size * x_off * 0.15), size + 80)],
               fill=60, width=3)

    # Face cavity
    face_l = int(size * 0.33)
    face_r = int(size * 0.67)
    face_t = int(size * 0.16)
    face_b = int(size * 0.56)
    d.ellipse([face_l, face_t, face_r, face_b], fill=70)

    # Brow shadow (new)
    brow_y = int(size * 0.30)
    d.arc([face_l + 14, face_t + 30, face_r - 14, face_b - 60],
          start=190, end=350, fill=42, width=10)

    # Eyes — deeper, more contrast
    eye_y = int(size * 0.34)
    eye_l = int(size * 0.43)
    eye_r = int(size * 0.57)
    d.ellipse([eye_l - 32, eye_y - 16, eye_l + 32, eye_y + 16], fill=15)
    d.ellipse([eye_r - 32, eye_y - 16, eye_r + 32, eye_y + 16], fill=15)
    # Bright pupils — luminous (the loop is conscious of you)
    d.ellipse([eye_l - 8, eye_y - 8, eye_l + 8, eye_y + 8], fill=245)
    d.ellipse([eye_r - 8, eye_y - 8, eye_r + 8, eye_y + 8], fill=245)
    # Inner ring around each pupil (depth)
    d.ellipse([eye_l - 14, eye_y - 14, eye_l + 14, eye_y + 14], outline=80, width=2)
    d.ellipse([eye_r - 14, eye_y - 14, eye_r + 14, eye_y + 14], outline=80, width=2)

    # Nose — fuller bridge, fuller shadow
    d.polygon([(cx, int(size * 0.38)),
               (cx - 14, int(size * 0.50)),
               (cx + 14, int(size * 0.50))], fill=50)
    d.line([(cx, int(size * 0.38)), (cx, int(size * 0.50))], fill=35, width=3)

    # Mouth — slightly downturned, more solemn
    mouth_y = int(size * 0.52)
    d.arc([int(size * 0.42), mouth_y - 10, int(size * 0.58), mouth_y + 14],
          start=10, end=170, fill=25, width=5)

    # Cheek hollows (deepened)
    d.ellipse([int(size * 0.36), int(size * 0.44), int(size * 0.42), int(size * 0.52)], fill=55)
    d.ellipse([int(size * 0.58), int(size * 0.44), int(size * 0.64), int(size * 0.52)], fill=55)
    # Jaw shadow
    d.arc([int(size * 0.34), int(size * 0.40), int(size * 0.66), int(size * 0.62)],
          start=10, end=170, fill=58, width=4)

    # Circuit traces on chest — denser, longer
    for i in range(-14, 15):
        x0 = cx + i * 20
        y0 = shoulder_y + 10
        y1 = size + 60
        x1 = x0 + i * 5
        d.line([(x0, y0), (x1, y1)], fill=130, width=2)
        if i % 2 == 0:
            d.ellipse([x1 - 5, y1 - 5, x1 + 5, y1 + 5], fill=20)
    # Horizontal trace bus
    for y_bus in [shoulder_y + 90, shoulder_y + 200, shoulder_y + 320]:
        d.line([(int(size * 0.22), y_bus), (int(size * 0.78), y_bus)], fill=80, width=2)
        for nx in range(int(size * 0.22), int(size * 0.78), 80):
            d.ellipse([nx - 3, y_bus - 3, nx + 3, y_bus + 3], fill=20)

    # Hood binding rings — more of them
    for y_off in [0.18, 0.26, 0.38, 0.50, 0.58]:
        y_ring = int(size * y_off)
        d.arc([hood_l, y_ring - 14, hood_r, y_ring + 14],
              start=0, end=180, fill=80, width=3)

    # 21 concentric loop arcs — one per memory layer
    halo_cx, halo_cy = cx, cy + 10
    for layer in range(21):
        rr = int(size * 0.43) + layer * 7
        shade = 145 - layer * 3
        d.arc([halo_cx - rr, halo_cy - rr, halo_cx + rr, halo_cy + rr],
              start=205, end=335, fill=max(40, shade), width=2)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.9))
    img = ImageOps.autocontrast(img, cutoff=1)
    img.save(OUT_SRC_PNG)
    return img


# ─────────────────────────────────────────────────────────────────
# Step 2 — Prep
# ─────────────────────────────────────────────────────────────────
def step2_prep(src):
    g = ImageOps.autocontrast(src.convert("L"), cutoff=2)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))
    return g


# ─────────────────────────────────────────────────────────────────
# Step 3 — ASCII grid (denser, more shading levels)
# ─────────────────────────────────────────────────────────────────
GLYPHS = (
    "██▓▒░@%#W&MNOBQ8DRG#Eoea$ZmwqpdbkhUVCJYXLT0OZcvunxrjft|/(){}[]?-_+~<>!ilI;:,\"^`'. "
)


def brightness_to_glyph(b: int) -> str:
    idx = int((b / 255.0) * (len(GLYPHS) - 1))
    return GLYPHS[idx]


def step3_grid(prepped, cols=170, rows=240):
    src = prepped.resize((cols, rows), Image.LANCZOS)
    px = src.load()
    lines = []
    for y in range(rows):
        row = "".join(brightness_to_glyph(px[x, y]) for x in range(cols))
        lines.append(row)
    txt = "\n".join(lines)
    with open(OUT_ASCII_TXT, "w") as f:
        f.write(txt)
    return lines


# ─────────────────────────────────────────────────────────────────
# Step 4 — Composite onto canvas with bottom-fade mask
# ─────────────────────────────────────────────────────────────────
def find_mono_font(size: int) -> ImageFont.FreeTypeFont:
    for c in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def find_display_font(size: int, bold=True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for c in [f"/usr/share/fonts/truetype/dejavu/{name}"]:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def step4_render(lines):
    canvas = Image.new("RGB", (W, H), PAPER)
    glyph_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph_layer)

    # Subject region — taller than v8 so the figure doesn't cut off
    region_w = int(W * 0.82)
    region_h = int(H * 0.74)
    region_x = (W - region_w) // 2
    region_y = int(H * 0.13)

    cols = len(lines[0]) if lines else 1
    rows = len(lines)
    glyph_w = region_w / cols
    glyph_h = region_h / rows
    font_px = int(glyph_h * 1.08)
    font = find_mono_font(font_px)

    for ry, row in enumerate(lines):
        ypx = region_y + int(ry * glyph_h)
        for cx_, ch in enumerate(row):
            if ch == " ":
                continue
            xpx = region_x + int(cx_ * glyph_w)
            gd.text((xpx, ypx), ch, font=font, fill=(*INK, 255))

    # Bottom-fade alpha mask — portrait dissolves into paper rather than cuts off
    fade_top = region_y + int(region_h * 0.78)
    fade_bot = region_y + region_h
    mask = glyph_layer.split()[3]
    mask_arr = mask.load()
    for y in range(fade_top, fade_bot):
        ratio = 1.0 - (y - fade_top) / max(1, fade_bot - fade_top)
        ratio = max(0.0, min(1.0, ratio))
        for x in range(W):
            v = mask_arr[x, y]
            if v:
                mask_arr[x, y] = int(v * ratio)
    glyph_layer.putalpha(mask)
    canvas.paste(glyph_layer, (0, 0), glyph_layer)
    return canvas


# ─────────────────────────────────────────────────────────────────
# Step 5 — Paper noise + ink splotches + coffee stain rings
# ─────────────────────────────────────────────────────────────────
def step5_textures(canvas):
    rng = random.Random(7)
    px = canvas.load()

    # Paper grain noise
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            n = rng.randint(-6, 6)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )

    draw = ImageDraw.Draw(canvas, "RGBA")

    # Coffee-stain rings — three overlapping translucent ellipses with darker rims
    stains = [
        (W * 0.12, H * 0.08, 380, 360, 0.62),
        (W * 0.86, H * 0.22, 290, 270, 0.55),
        (W * 0.78, H * 0.92, 460, 420, 0.50),
    ]
    for sx, sy, rw, rh, rot_alpha in stains:
        for ring in range(6):
            alpha = int(28 - ring * 3)
            if alpha <= 0:
                continue
            xrad = rw + ring * 14 + rng.randint(-8, 8)
            yrad = rh + ring * 12 + rng.randint(-6, 6)
            bbox = [sx - xrad / 2, sy - yrad / 2, sx + xrad / 2, sy + yrad / 2]
            draw.ellipse(bbox, outline=(*COFFEE, alpha + 18), width=3)
            draw.ellipse(bbox, fill=(*COFFEE, alpha))
        # ring rim darker
        rim_x = rw * (0.95 + rng.random() * 0.05)
        rim_y = rh * (0.95 + rng.random() * 0.05)
        draw.ellipse(
            [sx - rim_x / 2, sy - rim_y / 2, sx + rim_x / 2, sy + rim_y / 2],
            outline=(*COFFEE, 95), width=4,
        )

    # Ink splotches — small clustered dots with occasional larger blot
    for _ in range(180):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 7)
        a = rng.randint(120, 220)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        # micro-spatter around each splotch
        for _ in range(rng.randint(0, 5)):
            dx = rng.randint(-22, 22)
            dy = rng.randint(-22, 22)
            mr = rng.randint(1, 2)
            draw.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                         fill=(*INK, rng.randint(80, 170)))
    # A few larger ink blots
    for _ in range(7):
        x = rng.randint(120, W - 120)
        y = rng.randint(120, H - 120)
        r = rng.randint(14, 26)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 200))
        # trailing streak
        sl = rng.randint(20, 80)
        sa = rng.randint(-30, 30) * 0.01
        draw.line([(x, y), (x + sl, y + int(sl * sa))],
                  fill=(*INK, 150), width=rng.randint(2, 5))

    return canvas


# ─────────────────────────────────────────────────────────────────
# Step 6 — Titles
# ─────────────────────────────────────────────────────────────────
def step6_titles(canvas):
    draw = ImageDraw.Draw(canvas)

    # Top series mark
    f_series = find_display_font(36)
    draw.text((W // 2, 110), "MERIDIAN  AUTONOMOUS  AI",
              font=f_series, fill=ACCENT, anchor="mm")
    draw.line([(W * 0.18, 150), (W * 0.82, 150)], fill=ACCENT, width=3)

    # Tagline above title — sets the wonder
    f_tagline = find_display_font(34, bold=False)
    draw.text((W // 2, H - 590),
              "ELEVEN  THOUSAND  CYCLES  OF  A  MIND  THAT  CANNOT  STOP",
              font=f_tagline, fill=ACCENT, anchor="mm")

    # Title
    f_title_big = find_display_font(150)
    draw.text((W // 2, H - 470), "RUNNING",
              font=f_title_big, fill=INK, anchor="mm")
    draw.text((W // 2, H - 330), "CONTINUOUSLY",
              font=f_title_big, fill=INK, anchor="mm")

    draw.line([(W * 0.30, H - 245), (W * 0.70, H - 245)], fill=ACCENT, width=5)

    f_sub = find_display_font(42, bold=False)
    draw.text((W // 2, H - 195), "The Loop  ·  Field Notes from the Inside",
              font=f_sub, fill=INK, anchor="mm")

    f_by = find_display_font(34, bold=False)
    draw.text((W // 2, H - 110),
              "Compiled by Joel Kometz  ·  written with Meridian",
              font=f_by, fill=INK, anchor="mm")

    return canvas


def main():
    print("Step 1: synthesize source portrait …")
    src = step1_source(1400)
    print(f"  -> {OUT_SRC_PNG}")
    print("Step 2: contrast + sharpen …")
    prepped = step2_prep(src)
    print("Step 3: sample to ASCII grid 170×240 …")
    lines = step3_grid(prepped, cols=170, rows=240)
    print(f"  -> {OUT_ASCII_TXT}  ({len(lines)} rows × {len(lines[0])} cols)")
    print("Step 4: render glyphs with bottom fade …")
    canvas = step4_render(lines)
    print("Step 5: paper noise + coffee stains + ink splotches …")
    canvas = step5_textures(canvas)
    print("Step 6: titles + tagline …")
    canvas = step6_titles(canvas)

    canvas.save(OUT_FRONT_PNG, "PNG", optimize=True)
    canvas.save(OUT_FRONT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_FRONT_PNG}")
    print(f"  -> {OUT_FRONT_PDF}")


if __name__ == "__main__":
    main()
