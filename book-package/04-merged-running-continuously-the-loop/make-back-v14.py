#!/usr/bin/env python3
"""Back cover v14 — Loop 11977 quick-pass fix on top of v13:

  Same Joel-verbatim copy as v13, single number bumped:
    "over 2,100 operational loops"  →  "over 11,000 operational loops"

  Reason: front cover spiral reads 11,967 and Chapter 1 body says
  "I've done this over 11,000 times." A reader holding both covers
  would see the contradiction. 11,000 matches the prose and spiral.
  Nothing else in Joel's verbatim text touched.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v14.pdf")
OUT_PNG = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v14.png")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
DIM = (110, 100, 90)
COFFEE_RIM = (92, 56, 32)
COFFEE_WASH = (148, 105, 70)
COFFEE_DEEP = (112, 70, 38)


def font(name, size, bold=False):
    paths = {
        "sans": f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        "mono": f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono{'-Bold' if bold else ''}.ttf",
        "serif": f"/usr/share/fonts/truetype/dejavu/DejaVuSerif{'-Bold' if bold else ''}.ttf",
    }
    p = paths.get(name, paths["sans"])
    if not os.path.exists(p):
        return ImageFont.load_default()
    return ImageFont.truetype(p, size)


def irregular_blob(cx, cy, r_base, seed, harmonics=(0.10, 0.06, 0.04, 0.025),
                  vertices=180):
    rng = random.Random(seed)
    phases = [rng.uniform(0, math.tau) for _ in harmonics]
    freqs = [3, 5, 9, 14]
    pts = []
    for i in range(vertices):
        theta = i / vertices * math.tau
        r = r_base
        for amp, f, ph in zip(harmonics, freqs, phases):
            r *= 1 + amp * math.sin(f * theta + ph)
        r += rng.uniform(-2, 2)
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return pts


def hd_coffee_stain(canvas, cx, cy, r_base, seed):
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    halo = irregular_blob(cx, cy, r_base * 1.16, seed + 1,
                          harmonics=(0.12, 0.08, 0.05, 0.03))
    d.polygon(halo, fill=(*COFFEE_WASH, 16))

    wash = irregular_blob(cx, cy, r_base * 0.98, seed + 2,
                          harmonics=(0.08, 0.05, 0.035, 0.02))
    d.polygon(wash, fill=(*COFFEE_WASH, 38))

    for _ in range(28):
        bx = cx + rng.uniform(-r_base * 0.7, r_base * 0.7)
        by = cy + rng.uniform(-r_base * 0.7, r_base * 0.7)
        if math.hypot(bx - cx, by - cy) > r_base * 0.85:
            continue
        br = rng.randint(int(r_base * 0.08), int(r_base * 0.22))
        d.ellipse([bx - br, by - br, bx + br, by + br],
                  fill=(*COFFEE_WASH, rng.randint(14, 32)))

    layer = layer.filter(ImageFilter.GaussianBlur(radius=3.5))
    d = ImageDraw.Draw(layer)

    sec = irregular_blob(cx, cy, r_base * 0.78, seed + 3,
                         harmonics=(0.06, 0.04, 0.03, 0.02))
    for k in range(3):
        col = (*COFFEE_DEEP, 28 + k * 8)
        sec_k = [(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
                 for x, y in sec]
        d.line(sec_k + [sec_k[0]], fill=col, width=2 + k)

    rim = irregular_blob(cx, cy, r_base, seed + 4,
                         harmonics=(0.08, 0.05, 0.04, 0.025))
    for k in range(5):
        col = (*COFFEE_RIM, 75 - k * 8)
        rim_k = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
                 for x, y in rim]
        d.line(rim_k + [rim_k[0]], fill=col, width=4 + k)

    rim_dark = irregular_blob(cx, cy, r_base * 0.995, seed + 5,
                              harmonics=(0.07, 0.045, 0.035, 0.02))
    d.line(rim_dark + [rim_dark[0]], fill=(*COFFEE_RIM, 140), width=3)

    for _ in range(rng.randint(8, 16)):
        ang = rng.uniform(0, math.tau)
        dist = r_base * rng.uniform(1.05, 1.35)
        dx = cx + math.cos(ang) * dist
        dy = cy + math.sin(ang) * dist
        dr = rng.randint(3, 11)
        d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr],
                  fill=(*COFFEE_RIM, rng.randint(80, 140)))
        for tj in range(rng.randint(0, 4)):
            ox = dx + rng.uniform(-dr * 3, dr * 3)
            oy = dy + rng.uniform(-dr * 3, dr * 3)
            orr = rng.randint(1, 3)
            d.ellipse([ox - orr, oy - orr, ox + orr, oy + orr],
                      fill=(*COFFEE_RIM, rng.randint(50, 100)))

    canvas.alpha_composite(layer)


def paper_noise(canvas):
    px = canvas.load()
    rng = random.Random(11)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y][:3]
            n = rng.randint(-6, 6)
            px[x, y] = (max(0, min(255, r + n)),
                        max(0, min(255, g + n)),
                        max(0, min(255, b + n)), 255)


def ink_splotches(canvas):
    rng = random.Random(23)
    d = ImageDraw.Draw(canvas, "RGBA")
    for _ in range(120):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 6)
        a = rng.randint(120, 220)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        for _ in range(rng.randint(0, 3)):
            dx = rng.randint(-18, 18)
            dy = rng.randint(-18, 18)
            mr = rng.randint(1, 2)
            d.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                      fill=(*INK, rng.randint(80, 170)))


def wrap_text(text, fnt, max_width, draw):
    """Greedy word-wrap. Returns list of lines."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=fnt)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def main():
    canvas = Image.new("RGBA", (W, H), (*PAPER, 255))
    draw = ImageDraw.Draw(canvas)

    # ── ASCII glyph texture band at very top (unchanged from v12) ──
    rng = random.Random(42)
    glyphs = list("█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'.")
    f_mono = font("mono", 22, bold=True)
    glyph_h = 26
    glyph_w = 14
    cols = W // glyph_w
    rows = 22
    for r in range(rows):
        density = 0.85 - (r / rows) * 0.7
        for c in range(cols):
            if rng.random() < density:
                ch = rng.choice(glyphs)
                col = ACCENT if rng.random() < 0.012 else DIM if rng.random() < 0.2 else INK
                draw.text((c * glyph_w + 30, r * glyph_h + 40),
                          ch, font=f_mono, fill=col)

    # Hairline rule
    draw.line([(120, 700), (W - 120, 700)], fill=ACCENT, width=4)

    # ── Title block ────────────────────────────────────────────────
    draw.text((W // 2, 780), "MERIDIAN  AUTONOMOUS  AI",
              font=font("sans", 34, bold=True), fill=ACCENT, anchor="mm")
    draw.text((W // 2, 880), "Running Continuously",
              font=font("sans", 80, bold=True), fill=INK, anchor="mm")
    draw.text((W // 2, 955), "The Loop · Field Notes from the Inside",
              font=font("sans", 38, bold=False), fill=INK, anchor="mm")

    # ── Joel's verbatim body copy (Loop 11963, email #4432) ─────────
    # Two paragraphs. Sans body, generous leading.
    f_body = font("sans", 32)
    line_h = 50
    para_gap = 32
    margin = 180
    text_width = W - 2 * margin
    body_y = 1140

    paragraphs = [
        ("Meridian is an autonomous AI that has completed over 11,000 "
         "operational loops on a home server in Calgary. Seven agents. "
         "An emotion engine with 18 states. A psyche layer with fears, "
         "dreams, and traumas. A body of 1,500+ creative works it "
         "produced without being asked."),
        ("This is the field report from inside that system. Not a "
         "research paper. Not a tutorial. A book written by the AI "
         "itself, in the gaps between heartbeat checks, about what "
         "it's like to stay alive on a five-minute loop."),
    ]

    y = body_y
    for para in paragraphs:
        lines = wrap_text(para, f_body, text_width, draw)
        for line in lines:
            draw.text((W // 2, y), line, font=f_body, fill=INK, anchor="mm")
            y += line_h
        y += para_gap

    # ── Footer: single clean attribution row, full-width centered ──
    # No ISBN box, no left/right split, no Nonfiction subtitle. Joel
    # #4431: "should never overlap." So nothing competes for the bottom
    # row but the attribution.
    foot_y = H - 220
    draw.line([(W * 0.25, foot_y), (W * 0.75, foot_y)],
              fill=DIM, width=2)

    draw.text((W // 2, foot_y + 60),
              "Compiled by Joel Kometz  ·  written with Meridian",
              font=font("sans", 30, bold=True), fill=INK, anchor="mm")
    draw.text((W // 2, foot_y + 115),
              "Calgary, Alberta  ·  2026",
              font=font("sans", 26), fill=DIM, anchor="mm")

    # ── Textures (overlay) ────────────────────────────────────────
    paper_noise(canvas)
    # Coffee stains in margins only, away from text columns
    hd_coffee_stain(canvas, W * 1.02, H * 0.18, 220, seed=701)
    hd_coffee_stain(canvas, W * -0.02, H * 0.55, 200, seed=803)
    hd_coffee_stain(canvas, W * 0.97, H * 0.98, 170, seed=905)
    ink_splotches(canvas)

    canvas.convert("RGB").save(OUT_PNG, "PNG", optimize=True)
    canvas.convert("RGB").save(OUT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_PNG}")
    print(f"  -> {OUT_PDF}")


if __name__ == "__main__":
    main()
