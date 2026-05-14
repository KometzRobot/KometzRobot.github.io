#!/usr/bin/env python3
"""
Cover v8 — ASCII-typography portrait (Joel direction May 14 2026).

Pipeline (multi-step, like Joel asked):
  1. Source portrait: stylized AI "operator" silhouette synthesized with PIL primitives.
  2. Grayscale + edge accent + halftone-pad it to amplify detail.
  3. Sample on a cell grid; map cell brightness -> printable glyph density string.
  4. Composite glyph layer back onto cover canvas in a monospace font.
  5. Stack title typography over it; emit KDP-ready 1800x2700 PDF + PNG preview.

Targets the merged book "Running Continuously: The Loop".
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FRONT_PDF = os.path.join(BASE, "COVER-running-continuously-FRONT-v8.pdf")
OUT_FRONT_PNG = os.path.join(BASE, "COVER-running-continuously-FRONT-v8.png")
OUT_SRC_PNG   = os.path.join(BASE, "_cover-v8-source.png")
OUT_ASCII_TXT = os.path.join(BASE, "_cover-v8-ascii.txt")

# KDP 6x9 paperback @ 300 DPI = 1800 x 2700
W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)          # near-black warm
PAPER = (245, 238, 222)     # cream paper
ACCENT = (170, 60, 45)      # rust red — matches earlier covers


# ──────────────────────────────────────────────────────────────────
# Step 1 — synthesize a source portrait: hooded operator silhouette
#          looking at a glowing screen, with circuit traces.
# ──────────────────────────────────────────────────────────────────
def step1_source(size=1200):
    """High-contrast hooded operator silhouette with a luminous loop halo."""
    img = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, int(size * 0.46)

    # Halo — soft glow disc behind the head, becomes white in negative
    for r in range(int(size * 0.40), int(size * 0.15), -2):
        shade = max(200, 255 - int((size * 0.40 - r) * 0.6))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shade)

    # Hood silhouette — DARK
    hood_top = int(size * 0.12)
    hood_bot = int(size * 0.66)
    hood_l = int(size * 0.22)
    hood_r = int(size * 0.78)
    d.ellipse([hood_l, hood_top, hood_r, hood_bot], fill=18)
    d.rectangle([hood_l, int((hood_top + hood_bot) / 2), hood_r, hood_bot + 6], fill=18)

    # Hood folds (lighter strokes for texture)
    for i in range(-5, 6):
        d.arc([hood_l + 30, hood_top + 30, hood_r - 30, hood_bot - 30],
              start=200 + i * 14, end=210 + i * 14, fill=60, width=4)

    # Shoulders — wide, sloped
    shoulder_y = int(size * 0.66)
    d.polygon([
        (int(size * 0.05), size),
        (int(size * 0.22), shoulder_y),
        (int(size * 0.78), shoulder_y),
        (int(size * 0.95), size),
    ], fill=22)

    # Face cavity — dark recess but with face emerging
    face_l = int(size * 0.32)
    face_r = int(size * 0.68)
    face_t = int(size * 0.22)
    face_b = int(size * 0.60)
    d.ellipse([face_l, face_t, face_r, face_b], fill=70)

    # Face features — mid-tone with high local contrast
    # Eyes: deep dark recessed sockets
    eye_y = int(size * 0.38)
    eye_l = int(size * 0.42)
    eye_r = int(size * 0.58)
    d.ellipse([eye_l - 28, eye_y - 14, eye_l + 28, eye_y + 14], fill=15)
    d.ellipse([eye_r - 28, eye_y - 14, eye_r + 28, eye_y + 14], fill=15)
    # Bright pupils — luminous dot
    d.ellipse([eye_l - 6, eye_y - 6, eye_l + 6, eye_y + 6], fill=240)
    d.ellipse([eye_r - 6, eye_y - 6, eye_r + 6, eye_y + 6], fill=240)
    # Nose ridge
    d.polygon([(cx, int(size * 0.42)), (cx - 8, int(size * 0.52)),
               (cx + 8, int(size * 0.52))], fill=50)
    # Mouth — flat solemn line
    mouth_y = int(size * 0.55)
    d.rectangle([int(size * 0.44), mouth_y - 3, int(size * 0.56), mouth_y + 3], fill=25)
    # Cheek hollows
    d.ellipse([int(size * 0.36), int(size * 0.46), int(size * 0.42), int(size * 0.54)], fill=55)
    d.ellipse([int(size * 0.58), int(size * 0.46), int(size * 0.64), int(size * 0.54)], fill=55)

    # Circuit traces over chest — diagonal grid (signal flow)
    for i in range(-10, 11):
        x0 = cx + i * 22
        y0 = shoulder_y + 10
        y1 = int(size * 0.96)
        x1 = x0 + i * 4
        d.line([(x0, y0), (x1, y1)], fill=130, width=2)
        if i % 2 == 0:
            d.ellipse([x1 - 5, y1 - 5, x1 + 5, y1 + 5], fill=20)

    # Horizontal binding rings on hood (more typographic detail)
    for y_off in [0.20, 0.30, 0.50, 0.60]:
        y_ring = int(size * y_off)
        d.arc([hood_l, y_ring - 12, hood_r, y_ring + 12],
              start=0, end=180, fill=80, width=3)

    # Concentric loop halo (the THE LOOP motif)
    for r_off in range(0, 110, 18):
        rr = int(size * 0.42) + r_off
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr],
              start=200, end=340, fill=140 - r_off, width=3)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    img = ImageOps.autocontrast(img, cutoff=1)
    img.save(OUT_SRC_PNG)
    return img


# ──────────────────────────────────────────────────────────────────
# Step 2 — prep grayscale with stretched contrast + slight sharpen
# ──────────────────────────────────────────────────────────────────
def step2_prep(src):
    g = ImageOps.autocontrast(src.convert("L"), cutoff=2)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2))
    return g


# ──────────────────────────────────────────────────────────────────
# Step 3 — sample to glyph grid
# ──────────────────────────────────────────────────────────────────
GLYPHS = "█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'. "


def brightness_to_glyph(b: int) -> str:
    # b: 0..255  dark=dense glyph
    idx = int((b / 255.0) * (len(GLYPHS) - 1))
    return GLYPHS[idx]


def step3_grid(prepped, cols=160, rows=210):
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


# ──────────────────────────────────────────────────────────────────
# Step 4 — render glyph grid onto cover canvas
# ──────────────────────────────────────────────────────────────────
def find_mono_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def find_display_font(size: int, bold=True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/{name}",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def step4_render(lines):
    canvas = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(canvas)

    # Subject region (centered, roughly middle 70% of canvas)
    region_w = int(W * 0.78)
    region_h = int(H * 0.62)
    region_x = (W - region_w) // 2
    region_y = int(H * 0.18)

    cols = len(lines[0]) if lines else 1
    rows = len(lines)

    glyph_w = region_w / cols
    glyph_h = region_h / rows
    font_px = int(glyph_h * 1.05)
    font = find_mono_font(font_px)

    for ry, row in enumerate(lines):
        ypx = region_y + int(ry * glyph_h)
        for cx_, ch in enumerate(row):
            if ch == " ":
                continue
            xpx = region_x + int(cx_ * glyph_w)
            draw.text((xpx, ypx), ch, font=font, fill=INK)

    return canvas


# ──────────────────────────────────────────────────────────────────
# Step 5 — title typography
# ──────────────────────────────────────────────────────────────────
def step5_titles(canvas):
    draw = ImageDraw.Draw(canvas)

    # Top: tiny series mark
    f_series = find_display_font(36)
    draw.text((W // 2, 110), "MERIDIAN  AUTONOMOUS  AI",
              font=f_series, fill=ACCENT, anchor="mm")
    # Hairline
    draw.line([(W * 0.18, 150), (W * 0.82, 150)], fill=ACCENT, width=3)

    # Main title — two-line, serif-strong sans
    f_title_big = find_display_font(150)
    f_title_med = find_display_font(120)
    # Place title at bottom over the cream paper margin
    draw.text((W // 2, H - 470), "RUNNING",
              font=f_title_big, fill=INK, anchor="mm")
    draw.text((W // 2, H - 330), "CONTINUOUSLY",
              font=f_title_big, fill=INK, anchor="mm")

    # Accent rule
    draw.line([(W * 0.30, H - 245), (W * 0.70, H - 245)], fill=ACCENT, width=5)

    # Subtitle
    f_sub = find_display_font(42, bold=False)
    draw.text((W // 2, H - 195), "The Loop  ·  Field Notes From 11,000 Cycles",
              font=f_sub, fill=INK, anchor="mm")

    # Byline
    f_by = find_display_font(34, bold=False)
    draw.text((W // 2, H - 110),
              "Compiled by Joel Kometz  ·  with Meridian",
              font=f_by, fill=INK, anchor="mm")

    return canvas


def main():
    print("Step 1: synthesize source portrait …")
    src = step1_source(1200)
    print(f"  -> {OUT_SRC_PNG}")
    print("Step 2: contrast + sharpen …")
    prepped = step2_prep(src)
    print("Step 3: sample to ASCII grid 160x210 …")
    lines = step3_grid(prepped, cols=160, rows=210)
    print(f"  -> {OUT_ASCII_TXT}  ({len(lines)} rows × {len(lines[0])} cols)")
    print("Step 4: render glyphs onto KDP canvas …")
    canvas = step4_render(lines)
    print("Step 5: title typography …")
    canvas = step5_titles(canvas)

    canvas.save(OUT_FRONT_PNG, "PNG", optimize=True)
    canvas.save(OUT_FRONT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_FRONT_PNG}")
    print(f"  -> {OUT_FRONT_PDF}")


if __name__ == "__main__":
    main()
