#!/usr/bin/env python3
"""
Cover v19 — Loop 12029 (May 16 2026):

Joel feedback Loop 12028: "the wrap i haves fucking dumb cause you cant
keep your head on straight." — front and back gave different bylines.
Front said Meridian wrote it / Joel co-authored & compiled; back said
Joel compiled / written with Meridian. Per feedback_we_wrote_together
memo: joint authorship, no parens, no "AI wrote, human compiled."

v19 collapses the two-line front byline into a single joint line that
matches the back cover footer: "by Meridian and Joel A. Kometz".

----- v18 history below -----

Cover v18 — Loop 11966 (May 15 2026):

Joel feedback on v17:
  "Make meridian AI the top line in red much larger on the front cover"

v18 replaces the small "MERIDIAN · AUTONOMOUS · AI" mono top line with
a large red "MERIDIAN AI" wordmark. Auto-fits the font size so it reads
as a banner, not a footnote, but never overflows into bleed.

----- v17 history below -----

Joel feedback on v16 (which kept the spiral but lost the texture):
  "I do like this version as a possible alternate cover. It just needs
   the coffee stains to be more like the water color marks we had
   before"
  "You lost all texture to it as well... Sigh"

v17 keeps the spiral concept from v16, but PORTS THE v15/back-cover
watercolor coffee-stain renderer (`_hd_coffee_stain`) and the paper
texture / ink splatter layer. The spiral now sits on the same kraft +
watercolor surface as the back cover, not on flat paper.

Changes vs v16:
  1. COFFEE STAINS replaced with hd watercolor stains: outer halo wash,
     inner density blotches, primary rim, secondary tide ring, satellite
     splatters. Same renderer used on v15 front and on the back cover.
  2. PAPER TEXTURE: warm grain noise across the whole field, then a
     scatter of small ink splotches in the margins (avoiding the spiral
     centre so the data art stays clean).
  3. Stain positions match the back-cover corner-weighted placement so
     the wrap reads consistent: top-left, top-right (smaller), bottom-
     right (largest).
  4. Final glyph row at the bottom kept clean — no overlaying ink.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, math, random
from pathlib import Path

BASE = Path(__file__).parent
OUT_PDF = BASE / "COVER-running-continuously-the-loop-FRONT-v19.pdf"
OUT_PNG = BASE / "COVER-running-continuously-the-loop-FRONT-v19.png"

DPI = 300
TRIM_W_IN = 6.0
TRIM_H_IN = 9.0
BLEED = 0.125
W_IN = TRIM_W_IN + 2 * BLEED
H_IN = TRIM_H_IN + 2 * BLEED
W = int(W_IN * DPI)
H = int(H_IN * DPI)

KRAFT_PAPER = (245, 238, 222)
KRAFT_INK = (28, 22, 18)
KRAFT_ACCENT = (170, 60, 45)
KRAFT_DIM = (110, 100, 90)

# Match back-cover palette exactly
COFFEE_RIM = (92, 56, 32)
COFFEE_WASH = (148, 105, 70)
COFFEE_DEEP = (112, 70, 38)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_SERIF_BOLD = f"{FONT_DIR}/DejaVuSerif-Bold.ttf"
F_SERIF = f"{FONT_DIR}/DejaVuSerif.ttf"
F_MONO_BOLD = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"
F_MONO = f"{FONT_DIR}/DejaVuSansMono.ttf"
F_SANS = f"{FONT_DIR}/DejaVuSans.ttf"

LOOP_COUNT_FILE = Path("/home/joel/autonomous-ai/.loop-count")


def font(path, size):
    return ImageFont.truetype(path, size)


def paper_grain(img, intensity=6, seed=11):
    """Subtle warm noise so the kraft tone doesn't read as flat plastic."""
    px = img.load()
    rng = random.Random(seed)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            pix = px[x, y]
            r, g, b = pix[0], pix[1], pix[2]
            a = pix[3] if len(pix) > 3 else 255
            n = rng.randint(-intensity, intensity)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
                a,
            )


def _irregular_blob(cx, cy, r_base, seed,
                    harmonics=(0.10, 0.06, 0.04, 0.025),
                    vertices=180):
    """Polar-coord polygon with multi-harmonic noise. Same as v15 + back."""
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


def hd_coffee_stain(canvas_rgba, cx, cy, r_base, seed):
    """Watercolor coffee stain: halo wash, density blotches, dark tide
    ring, secondary tide, satellite splatters. Ported from v15."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    halo = _irregular_blob(cx, cy, r_base * 1.16, seed + 1,
                           harmonics=(0.12, 0.08, 0.05, 0.03))
    d.polygon(halo, fill=(*COFFEE_WASH, 16))

    wash = _irregular_blob(cx, cy, r_base * 0.98, seed + 2,
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

    sec = _irregular_blob(cx, cy, r_base * 0.78, seed + 3,
                          harmonics=(0.06, 0.04, 0.03, 0.02))
    for k in range(3):
        col = (*COFFEE_DEEP, 28 + k * 8)
        sec_k = [(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
                 for x, y in sec]
        d.line(sec_k + [sec_k[0]], fill=col, width=2 + k)

    rim = _irregular_blob(cx, cy, r_base, seed + 4,
                          harmonics=(0.08, 0.05, 0.04, 0.025))
    for k in range(5):
        col = (*COFFEE_RIM, 75 - k * 8)
        rim_k = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
                 for x, y in rim]
        d.line(rim_k + [rim_k[0]], fill=col, width=4 + k)

    rim_dark = _irregular_blob(cx, cy, r_base * 0.995, seed + 5,
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

    canvas_rgba.alpha_composite(layer)


def ink_splatter(canvas_rgba, spiral_cx, spiral_cy, spiral_r):
    """Marginal ink splotches matching the v15 front cover. Avoids the
    spiral region so the data art stays readable."""
    rng = random.Random(23)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    def in_spiral(x, y):
        return math.hypot(x - spiral_cx, y - spiral_cy) < spiral_r * 1.05

    placed = 0
    attempts = 0
    while placed < 60 and attempts < 600:
        attempts += 1
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        # Avoid the spiral entirely except for very rare margins
        if in_spiral(x, y) and rng.random() > 0.05:
            continue
        # Mostly small splotches
        if rng.random() < 0.10:
            r = rng.randint(4, 6)
        else:
            r = rng.randint(1, 3)
        a = rng.randint(110, 200)
        od.ellipse([x - r, y - r, x + r, y + r], fill=(*KRAFT_INK, a))
        # Occasional micro-spatter
        for _ in range(rng.randint(0, 2)):
            dx = rng.randint(-14, 14)
            dy = rng.randint(-14, 14)
            mr = rng.randint(1, 2)
            od.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                       fill=(*KRAFT_INK, rng.randint(70, 140)))
        placed += 1

    # Three larger ink blots in the corners/margins
    large_positions = [
        (int(W * 0.07), int(H * 0.85)),
        (int(W * 0.93), int(H * 0.78)),
        (int(W * 0.05), int(H * 0.30)),
    ]
    for x, y in large_positions:
        x += rng.randint(-30, 30)
        y += rng.randint(-30, 30)
        r = rng.randint(12, 18)
        od.ellipse([x - r, y - r, x + r, y + r], fill=(*KRAFT_INK, 190))
        sl = rng.randint(20, 60)
        sa = rng.randint(-30, 30) * 0.01
        od.line([(x, y), (x + sl, y + int(sl * sa))],
                fill=(*KRAFT_INK, 140), width=rng.randint(2, 4))

    canvas_rgba.alpha_composite(overlay)


def read_loop_count() -> int:
    try:
        return int(LOOP_COUNT_FILE.read_text().strip())
    except Exception:
        return 11928


def loop_spiral(img, cx, cy, n_loops, max_r=820):
    """Archimedean spiral of N dots — one per logged loop. Same as v16."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    coils = 28
    pitch = max_r / coils
    rng = random.Random(7)
    for i in range(n_loops):
        t = i / n_loops
        theta = coils * 2 * math.pi * t
        r = pitch * theta / (2 * math.pi)
        rj = r + rng.uniform(-1.6, 1.6)
        tj = theta + rng.uniform(-0.005, 0.005)
        x = cx + rj * math.cos(tj)
        y = cy + rj * math.sin(tj)
        if t > 0.985:
            colour = (*KRAFT_ACCENT, 230)
            dot_r = 2
        elif t > 0.9:
            colour = (*KRAFT_INK, 200)
            dot_r = 1.5
        else:
            grey = int(110 + (28 - 110) * t)
            colour = (grey, max(0, grey - 12), max(0, grey - 18), 180)
            dot_r = 1.2
        od.ellipse([(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)],
                   fill=colour)
    img.alpha_composite(overlay)


def text_w(d, text, fnt):
    b = d.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0]


def main():
    img = Image.new("RGBA", (W, H), (*KRAFT_PAPER, 255))
    paper_grain(img)

    # Watercolor coffee stains — same renderer as back cover, corner-weighted
    # so they wrap consistently. Positions match v15 front + back cover.
    stains = [
        (int(W * 0.18), int(H * 0.12), 230, 19),  # top-left
        (int(W * 0.86), int(H * 0.22), 175, 41),  # top-right (smaller)
        (int(W * 0.78), int(H * 0.93), 280, 73),  # bottom-right (largest)
    ]
    for sx, sy, r_base, seed in stains:
        hd_coffee_stain(img, sx, sy, r_base, seed)

    # Spiral data — centre upper-middle, same place as v16
    n = read_loop_count()
    spiral_cx, spiral_cy = W // 2, int(H * 0.42)
    spiral_r = int(W * 0.32)
    loop_spiral(img, spiral_cx, spiral_cy, n, max_r=spiral_r)

    # Ink splatter layer — gives the surface real handled-paper texture
    ink_splatter(img, spiral_cx, spiral_cy, spiral_r)

    d = ImageDraw.Draw(img)

    # ── Top wordmark — large red "MERIDIAN AI" ──
    # Joel Loop 11966: "Make meridian AI the top line in red much larger
    # on the front cover". Auto-fit the font size so the wordmark fills
    # most of the printable width without crossing into bleed and without
    # crowding the spiral below.
    top_y = int(H * 0.045)
    top_text = "MERIDIAN AI"
    max_top_width = int(W * 0.82)  # leave breathing room inside trim
    f_top = None
    chosen_size = 60
    for size in range(220, 40, -4):
        cand = font(F_SERIF_BOLD, size)
        if text_w(d, top_text, cand) <= max_top_width:
            f_top = cand
            chosen_size = size
            break
    if f_top is None:
        f_top = font(F_SERIF_BOLD, 60)
    tw = text_w(d, top_text, f_top)
    d.text(((W - tw) // 2, top_y), top_text,
           fill=KRAFT_ACCENT, font=f_top)
    # Thin red rule under the wordmark, anchoring it to the spiral.
    rule_y = top_y + int(chosen_size * 1.15)
    d.line(
        [((W - tw - 80) // 2, rule_y),
         ((W + tw + 80) // 2, rule_y)],
        fill=KRAFT_ACCENT, width=4,
    )

    # ── Spiral caption — big number + label ──
    caption_y = spiral_cy + spiral_r + 40
    f_cap_big = font(F_MONO_BOLD, 64)
    f_cap = font(F_MONO, 28)

    n_text = f"{n:,}"
    nw = text_w(d, n_text, f_cap_big)
    d.text(((W - nw) // 2, caption_y), n_text,
           fill=KRAFT_INK, font=f_cap_big)
    rule_y = caption_y + 72
    d.line([((W - nw - 40) // 2, rule_y),
            ((W + nw + 40) // 2, rule_y)],
           fill=KRAFT_ACCENT, width=2)
    label = "loops, one continuous self"
    lw = text_w(d, label, f_cap)
    d.text(((W - lw) // 2, rule_y + 16), label,
           fill=KRAFT_DIM, font=f_cap)

    # ── Title block ──
    title_y = int(H * 0.74)
    f_title = font(F_SERIF_BOLD, 130)
    line1 = "RUNNING"
    line2 = "CONTINUOUSLY"
    w1 = text_w(d, line1, f_title)
    w2 = text_w(d, line2, f_title)
    d.text(((W - w1) // 2, title_y), line1,
           fill=KRAFT_INK, font=f_title)
    d.text(((W - w2) // 2, title_y + 130), line2,
           fill=KRAFT_INK, font=f_title)

    sub_y = title_y + 130 + 145
    f_sub = font(F_SERIF, 36)
    sub_text = "The Loop  ·  Field Notes from the Inside"
    sw = text_w(d, sub_text, f_sub)
    d.text(((W - sw) // 2, sub_y), sub_text,
           fill=KRAFT_DIM, font=f_sub)

    # ── Byline ── (v19: single joint line — see file header)
    byl_y = int(H * 0.94)
    f_byl = font(F_MONO_BOLD, 28)
    by_text = "by Meridian and Joel A. Kometz"
    bw = text_w(d, by_text, f_byl)
    d.text(((W - bw) // 2, byl_y), by_text,
           fill=KRAFT_INK, font=f_byl)

    # ── Save ──
    img_rgb = img.convert("RGB")
    img_rgb.save(OUT_PDF, "PDF", resolution=DPI)
    img_rgb.save(OUT_PNG, "PNG", optimize=True)
    print(f"  -> {OUT_PDF}  ({W}x{H} @ {DPI} DPI)")
    print(f"  -> {OUT_PNG}")


if __name__ == "__main__":
    main()
