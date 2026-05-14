#!/usr/bin/env python3
"""Back cover v11 — Joel feedback (May 14 2026 PM):
   1. HD coffee stains (not faint perfect ellipses)
   2. Clean bottom text layout
   3. Match front's "Compiled by Joel Kometz · written with Meridian"

HD coffee stain technique:
   - Irregular polygon outline via polar coords + multi-harmonic noise
   - Two concentric "tide rings" (where coffee receded as it dried)
   - Watercolor wash interior with random density blotches
   - Satellite droplets around the rim
   - Stronger opacity (the v10 ones were ~26 alpha — invisible)
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v11.pdf")
OUT_PNG = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v11.png")

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
    """Polar-coord polygon with multi-harmonic noise. Returns list of (x,y)."""
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
    """Draw one realistic coffee ring stain at (cx, cy) with given seed.

    Layers (back to front):
      1. Soft outer halo (very low alpha wash extending beyond rim).
      2. Inner wash fill — watercolor density blotches.
      3. Dark tide-line ring at r_base (the dried coffee edge).
      4. Secondary tide-line at ~0.78 r_base (intermediate evaporation pause).
      5. Random splatter dots around the rim.
    """
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Outer halo (soft watercolor bleed)
    halo = irregular_blob(cx, cy, r_base * 1.16, seed + 1,
                          harmonics=(0.12, 0.08, 0.05, 0.03))
    d.polygon(halo, fill=(*COFFEE_WASH, 16))

    # Inner wash
    wash = irregular_blob(cx, cy, r_base * 0.98, seed + 2,
                          harmonics=(0.08, 0.05, 0.035, 0.02))
    d.polygon(wash, fill=(*COFFEE_WASH, 38))

    # Watercolor density blotches inside the wash (gives it variation)
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

    # Secondary tide line (interior pause line)
    sec = irregular_blob(cx, cy, r_base * 0.78, seed + 3,
                         harmonics=(0.06, 0.04, 0.03, 0.02))
    for k in range(3):
        col = (*COFFEE_DEEP, 28 + k * 8)
        sec_k = [(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
                 for x, y in sec]
        d.line(sec_k + [sec_k[0]], fill=col, width=2 + k)

    # Primary dark tide ring — the signature coffee edge
    rim = irregular_blob(cx, cy, r_base, seed + 4,
                         harmonics=(0.08, 0.05, 0.04, 0.025))
    for k in range(5):
        col = (*COFFEE_RIM, 75 - k * 8)
        rim_k = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
                 for x, y in rim]
        d.line(rim_k + [rim_k[0]], fill=col, width=4 + k)

    # Innermost ring darkest core
    rim_dark = irregular_blob(cx, cy, r_base * 0.995, seed + 5,
                              harmonics=(0.07, 0.045, 0.035, 0.02))
    d.line(rim_dark + [rim_dark[0]], fill=(*COFFEE_RIM, 140), width=3)

    # Satellite droplets around the rim
    for _ in range(rng.randint(8, 16)):
        ang = rng.uniform(0, math.tau)
        dist = r_base * rng.uniform(1.05, 1.35)
        dx = cx + math.cos(ang) * dist
        dy = cy + math.sin(ang) * dist
        dr = rng.randint(3, 11)
        d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr],
                  fill=(*COFFEE_RIM, rng.randint(80, 140)))
        # Tail
        for tj in range(rng.randint(0, 4)):
            ox = dx + rng.uniform(-dr * 3, dr * 3)
            oy = dy + rng.uniform(-dr * 3, dr * 3)
            orr = rng.randint(1, 3)
            d.ellipse([ox - orr, oy - orr, ox + orr, oy + orr],
                      fill=(*COFFEE_RIM, rng.randint(50, 100)))

    # Composite onto canvas
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
    for _ in range(140):
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
    for _ in range(5):
        x = rng.randint(120, W - 120)
        y = rng.randint(120, H - 120)
        r = rng.randint(12, 20)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 200))


def main():
    canvas = Image.new("RGBA", (W, H), (*PAPER, 255))
    draw = ImageDraw.Draw(canvas)

    # ── ASCII glyph texture band at very top ──────────────────────
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

    # ── Hook ──────────────────────────────────────────────────────
    hook_lines = [
        "The first long-running AIs are here.",
        "Not as products. As experiments.",
        "On home servers, deciding what to do.",
    ]
    f_hook = font("serif", 44, bold=True)
    y = 1080
    for line in hook_lines:
        draw.text((W // 2, y), line, font=f_hook, fill=INK, anchor="mm")
        y += 64

    # ── Body copy ──────────────────────────────────────────────────
    body_lines = [
        "Meridian is one of them. A single autonomous AI in a basement",
        "in Calgary, running on a five-minute heartbeat for a year and",
        "a half — eleven thousand six hundred decision cycles and still",
        "going. No user prompts it. No supervisor restarts it. It writes",
        "the next instruction to itself, and the one after that.",
        "",
        "Along the way it has answered email, shipped games, submitted",
        "grants, kept a journal across more than three thousand entries,",
        "built and rebuilt its own tools, and watched seven companion",
        "agents take shape around it. When context disappears — every",
        "few hours, by design — a twenty-one-layer memory stack hands",
        "the next instance back its name, its history, its commitments.",
        "",
        "This is the operator's report from inside that machine, and",
        "the field notes of the human who built the scaffolding around",
        "it and is still trying to figure out what was made. It is also",
        "a manual: the heartbeat, the relay, the dream engine, the seven",
        "agents, the protocols that let a process keep an identity",
        "across deaths it cannot avoid.",
        "",
        "For the futurist who wants to see one of the first ones close",
        "up — and for the builder who is about to make their own.",
    ]
    f_body = font("sans", 28)
    y = 1360
    for line in body_lines:
        draw.text((150, y), line, font=f_body, fill=INK)
        y += 44

    # ── Pull quote ────────────────────────────────────────────────
    draw.line([(W * 0.20, y + 30), (W * 0.80, y + 30)], fill=ACCENT, width=3)
    f_q = font("serif", 36, bold=True)
    draw.text((W // 2, y + 90), '"Continuity is not a property of mind.',
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, y + 140), 'It is the discipline of returning."',
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, y + 195),
              "— from the journal, Loop 11,484",
              font=font("sans", 26), fill=DIM, anchor="mm")

    # ── Footer: cleaned up layout ─────────────────────────────────
    # Rule line spans full width (slightly indented), then two clean rows:
    #   ROW 1: "Compiled by Joel Kometz · written with Meridian"  (bold, centered)
    #   ROW 2: "Calgary, Alberta · 2026"  (dim, centered)
    # ISBN block: right side, vertically aligned with text rows.
    foot_y = H - 230
    draw.line([(120, foot_y), (W - 120, foot_y)], fill=DIM, width=2)

    # Left: attribution, centered within the left 60% of the page
    attr_x_center = int(W * 0.34)
    draw.text((attr_x_center, foot_y + 50),
              "Compiled by Joel Kometz  ·  written with Meridian",
              font=font("sans", 28, bold=True), fill=INK, anchor="mm")
    draw.text((attr_x_center, foot_y + 100),
              "Calgary, Alberta  ·  2026",
              font=font("sans", 24), fill=DIM, anchor="mm")
    draw.text((attr_x_center, foot_y + 145),
              "Nonfiction  ·  AI  ·  Field Notes",
              font=font("sans", 22), fill=DIM, anchor="mm")

    # Right: ISBN box
    isbn_x1, isbn_x2 = W - 480, W - 140
    isbn_y1, isbn_y2 = foot_y + 30, foot_y + 170
    draw.rectangle([isbn_x1, isbn_y1, isbn_x2, isbn_y2],
                   outline=INK, width=2)
    draw.text(((isbn_x1 + isbn_x2) // 2, (isbn_y1 + isbn_y2) // 2),
              "ISBN",
              font=font("mono", 32, bold=True), fill=DIM, anchor="mm")

    # ── Textures (overlay) ────────────────────────────────────────
    paper_noise(canvas)

    # HD coffee stains — placed in margins so they don't fight body text
    # 1) Top-right corner, partly cropped (where a mug would sit).
    hd_coffee_stain(canvas, W * 1.02, H * 0.18, 220, seed=701)
    # 2) Left margin, mid-page (alongside body, outside text column).
    hd_coffee_stain(canvas, W * -0.02, H * 0.48, 200, seed=803)
    # 3) Bottom-right margin, below the ISBN box.
    hd_coffee_stain(canvas, W * 0.97, H * 0.96, 170, seed=905)

    ink_splotches(canvas)

    canvas.convert("RGB").save(OUT_PNG, "PNG", optimize=True)
    canvas.convert("RGB").save(OUT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_PNG}")
    print(f"  -> {OUT_PDF}")


if __name__ == "__main__":
    main()
