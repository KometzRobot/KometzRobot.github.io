#!/usr/bin/env python3
"""Mooshu sample spread — KDP 8x8 trim, two-page facing spread mockup.

Demonstrates: trim, gutter, bleed, verse-on-page-left + illustration-on-page-right,
hand-drawn aesthetic against soft paper background. This is a layout test for Joel,
not a final spread.

Dimensions:
  Trim (per page):     8.00 x 8.00 in
  Bleed (added all):   0.125 in
  Page size w/ bleed:  8.125 x 8.125 in
  Spread total:        16.25 x 8.125 in
  @ 300 DPI:           4875 x 2438 px (with bleed)
                       4800 x 2400 px (trim only)

Output: SAMPLE-spread-trio.png (visual mockup, with trim/safety guide overlay)
        SAMPLE-spread-trio-clean.png (clean version, no guides)
"""
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

DPI = 300
TRIM_W_IN = 8.0
TRIM_H_IN = 8.0
BLEED_IN = 0.125
SAFETY_IN = 0.25

PAGE_TRIM_W = int(TRIM_W_IN * DPI)             # 2400
PAGE_TRIM_H = int(TRIM_H_IN * DPI)             # 2400
BLEED_PX = int(BLEED_IN * DPI)                 # 38
SAFETY_PX = int(SAFETY_IN * DPI)               # 75

SPREAD_W = PAGE_TRIM_W * 2 + BLEED_PX * 2      # 4876
SPREAD_H = PAGE_TRIM_H + BLEED_PX * 2          # 2476

# Cream paper background
PAPER = (244, 236, 220)
INK = (52, 40, 28)
INK_SOFT = (90, 74, 56)
ACCENT = (160, 76, 48)        # warm orange (Mooshu cap)
GUTTER_SHADOW = (210, 198, 178)

F_DIR = "/usr/share/fonts/truetype/dejavu"
F_HEAD = f"{F_DIR}/DejaVuSerif-Bold.ttf"
F_BODY = f"{F_DIR}/DejaVuSerif.ttf"
F_SMALL = f"{F_DIR}/DejaVuSans.ttf"


def make_paper_bg():
    """Cream paper with subtle noise + warm vignette."""
    bg = Image.new("RGB", (SPREAD_W, SPREAD_H), PAPER)

    # Add subtle grain via noise overlay
    import random
    random.seed(42)
    noise = Image.new("L", (SPREAD_W // 4, SPREAD_H // 4))
    npx = noise.load()
    for x in range(noise.width):
        for y in range(noise.height):
            npx[x, y] = random.randint(120, 140)
    noise = noise.resize((SPREAD_W, SPREAD_H), Image.BILINEAR)
    noise = noise.filter(ImageFilter.GaussianBlur(2))
    bg = Image.composite(bg, Image.new("RGB", bg.size, (235, 225, 205)), noise)

    # Gutter shadow (center fold)
    d = ImageDraw.Draw(bg, "RGBA")
    cx = SPREAD_W // 2
    for i in range(120):
        alpha = int(60 * (1 - i / 120))
        d.line([(cx - i, 0), (cx - i, SPREAD_H)], fill=(140, 120, 90, alpha))
        d.line([(cx + i, 0), (cx + i, SPREAD_H)], fill=(140, 120, 90, alpha))
    return bg


def paste_illustration(spread, path, right_page=True):
    """Paste the illustration into the right page area with margin."""
    art = Image.open(path).convert("RGB")
    # Right page = x from (PAGE_TRIM_W + BLEED_PX) to (SPREAD_W - BLEED_PX)
    page_x0 = PAGE_TRIM_W + BLEED_PX if right_page else BLEED_PX
    page_y0 = BLEED_PX

    # Image area inside safety margins
    img_x0 = page_x0 + SAFETY_PX
    img_y0 = page_y0 + SAFETY_PX
    img_x1 = page_x0 + PAGE_TRIM_W - SAFETY_PX
    img_y1 = page_y0 + PAGE_TRIM_H - SAFETY_PX
    box_w = img_x1 - img_x0
    box_h = img_y1 - img_y0

    art = ImageOps.contain(art, (box_w, box_h), Image.LANCZOS)
    # Center the art in the box
    px = img_x0 + (box_w - art.width) // 2
    py = img_y0 + (box_h - art.height) // 2

    # Soft drop shadow
    shadow = Image.new("RGBA", (art.width + 40, art.height + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([(20, 20), (shadow.width - 20, shadow.height - 20)], fill=(40, 30, 20, 100))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    spread.paste(shadow, (px - 20, py - 20 + 10), shadow)

    spread.paste(art, (px, py))


def draw_verse(spread, lines, page_left=True):
    """Type-set verse on the left page."""
    page_x0 = BLEED_PX if page_left else PAGE_TRIM_W + BLEED_PX
    page_y0 = BLEED_PX
    page_w = PAGE_TRIM_W
    page_h = PAGE_TRIM_H

    d = ImageDraw.Draw(spread)

    # Page number marker (corner, soft)
    f_pg = ImageFont.truetype(F_SMALL, 24)
    d.text((page_x0 + SAFETY_PX, page_y0 + page_h - SAFETY_PX), "—  4  —", fill=INK_SOFT, font=f_pg)

    # Verse block — centered vertically
    f_body = ImageFont.truetype(F_BODY, 86)
    f_head = ImageFont.truetype(F_HEAD, 64)

    # Decorative small ornament — orange dot (Mooshu's cap)
    d.ellipse([(page_x0 + page_w // 2 - 14, page_y0 + 220),
               (page_x0 + page_w // 2 + 14, page_y0 + 248)], fill=ACCENT)

    # Title line
    title = "Hush — Who's There?"
    bbox = d.textbbox((0, 0), title, font=f_head)
    tw = bbox[2] - bbox[0]
    d.text((page_x0 + (page_w - tw) // 2, page_y0 + 290), title, fill=INK, font=f_head)

    # Compute total height of verse for centering
    line_h = 116
    total = len(lines) * line_h
    y = page_y0 + (page_h - total) // 2 + 80

    for line in lines:
        if not line.strip():
            y += line_h // 2
            continue
        bbox = d.textbbox((0, 0), line, font=f_body)
        lw = bbox[2] - bbox[0]
        x = page_x0 + (page_w - lw) // 2
        d.text((x, y), line, fill=INK, font=f_body)
        y += line_h

    # Closing series refrain — bottom, italic small
    f_ref = ImageFont.truetype(F_BODY, 38)
    refrain = "(Something small woke up today.)"
    bbox = d.textbbox((0, 0), refrain, font=f_ref)
    rw = bbox[2] - bbox[0]
    d.text((page_x0 + (page_w - rw) // 2, page_y0 + page_h - 280), refrain, fill=INK_SOFT, font=f_ref)


def draw_guides(spread):
    """Print-spec overlay: bleed (red), trim (blue), safety (green)."""
    d = ImageDraw.Draw(spread, "RGBA")
    # Bleed = full canvas border
    d.rectangle([(0, 0), (SPREAD_W - 1, SPREAD_H - 1)], outline=(220, 60, 60, 200), width=3)
    # Trim = inset by bleed
    d.rectangle([(BLEED_PX, BLEED_PX),
                 (SPREAD_W - BLEED_PX, SPREAD_H - BLEED_PX)],
                outline=(60, 100, 220, 200), width=3)
    # Center fold
    d.line([(SPREAD_W // 2, BLEED_PX), (SPREAD_W // 2, SPREAD_H - BLEED_PX)],
           fill=(60, 100, 220, 120), width=2)
    # Safety margin — each page
    for page_idx in (0, 1):
        x0 = BLEED_PX + page_idx * PAGE_TRIM_W + SAFETY_PX
        y0 = BLEED_PX + SAFETY_PX
        x1 = BLEED_PX + (page_idx + 1) * PAGE_TRIM_W - SAFETY_PX
        y1 = BLEED_PX + PAGE_TRIM_H - SAFETY_PX
        d.rectangle([(x0, y0), (x1, y1)], outline=(60, 180, 80, 180), width=2)

    # Legend
    f_leg = ImageFont.truetype(F_SMALL, 22)
    d.text((20, 20), "RED = bleed   BLUE = trim   GREEN = safety   |   8x8 spread @ 300 DPI",
           fill=(40, 40, 40, 220), font=f_leg)


def main():
    verse_b = [
        "Hush — who's there?",
        "Three small caps in the damp fern air.",
        "Not a pebble. Not a snail.",
        "Three small Mooshus, small and pale.",
        "",
        "Hush — they're here.",
        "Three small caps in the damp fern air.",
        "Safe as a pebble. Snug as a snail.",
        "Three small Mooshus, small and pale.",
    ]

    # Clean version (no guides) — what the spread looks like printed
    clean = make_paper_bg()
    draw_verse(clean, verse_b, page_left=True)
    paste_illustration(clean, "mooshu-trio-02.webp", right_page=True)
    clean.save("SAMPLE-spread-trio-clean.png")
    print(f"wrote SAMPLE-spread-trio-clean.png  {clean.size}")

    # Guide overlay version — what the print-spec looks like
    guided = clean.copy()
    draw_guides(guided)
    guided.save("SAMPLE-spread-trio-with-guides.png")
    print(f"wrote SAMPLE-spread-trio-with-guides.png  {guided.size}")


if __name__ == "__main__":
    main()
