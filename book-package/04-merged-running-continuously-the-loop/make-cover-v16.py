#!/usr/bin/env python3
"""
Cover v16 — Loop 11915 (May 15 2026):

Joel: "The cover is not mine. You are making it."

v15 used an ASCII-portrait hooded figure that read as borrowed / generic.
v16 throws the figure out and uses the BOOK'S OWN DATA as the image: a
spiral of 11,915 dots, one per logged loop, drawn from the real .loop-count
file. The cover IS what the book is about — a continuous self verified
by counting.

Aesthetic still kraft + typewriter, no figure. Coffee rings at the corners
read as hand-handled paper. Title typeset clean at the bottom so the
spiral has room to breathe.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, math, random
from pathlib import Path

BASE = Path(__file__).parent
OUT_PDF = BASE / "COVER-running-continuously-the-loop-FRONT-v16.pdf"
OUT_PNG = BASE / "COVER-running-continuously-the-loop-FRONT-v16.png"

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
COFFEE = (148, 110, 75)

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


def coffee_ring(img, cx, cy, r, opacity=42, layers=3):
    """One soft coffee tide-ring. Multiple concentric arcs at varying
    opacity to suggest a stain that's dried unevenly."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    rng = random.Random(int(cx * 7 + cy))
    for i in range(layers):
        rr = r + rng.randint(-12, 12) + i * 6
        wob = rng.randint(2, 4)
        # Wobbled circle approximated with a polygon
        pts = []
        for theta_deg in range(0, 360, 4):
            theta = math.radians(theta_deg)
            jitter = rng.uniform(-wob, wob)
            x = cx + (rr + jitter) * math.cos(theta)
            y = cy + (rr + jitter) * math.sin(theta)
            pts.append((x, y))
        od.polygon(pts, outline=(*COFFEE, opacity + i * 8), width=3)
    # Fill blob inside, very pale
    od.ellipse(
        [(cx - r * 0.75, cy - r * 0.75), (cx + r * 0.75, cy + r * 0.75)],
        fill=(*COFFEE, 14),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=2))
    img.alpha_composite(overlay)


def read_loop_count() -> int:
    try:
        return int(LOOP_COUNT_FILE.read_text().strip())
    except Exception:
        return 11915


def loop_spiral(img, cx, cy, n_loops, max_r=820):
    """Archimedean spiral of N dots — one per logged loop.

    Inner dots = oldest loops; outer = most recent. Dot size and ink
    weight stay constant so the density of the spiral itself does the
    work — it gets visibly denser as more loops are added, the way a
    pencil mark builds on paper from being touched again.
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Pitch: distance between successive coils, in pixels
    coils = 28  # arbitrary aesthetic choice — more coils = tighter spiral
    pitch = max_r / coils
    rng = random.Random(7)
    for i in range(n_loops):
        t = i / n_loops
        theta = coils * 2 * math.pi * t
        r = pitch * theta / (2 * math.pi)
        # Tiny radial jitter so the spiral doesn't read mechanical
        rj = r + rng.uniform(-1.6, 1.6)
        tj = theta + rng.uniform(-0.005, 0.005)
        x = cx + rj * math.cos(tj)
        y = cy + rj * math.sin(tj)
        # Slight tone gradient: oldest loops fade toward kraft-dim,
        # newest pop in scarlet. Subtle so it reads as ink build-up.
        if t > 0.985:
            colour = (*KRAFT_ACCENT, 230)
            dot_r = 2
        elif t > 0.9:
            colour = (*KRAFT_INK, 200)
            dot_r = 1.5
        else:
            # Fade from dim → ink over the spiral
            grey = int(110 + (28 - 110) * t)
            colour = (grey, max(0, grey - 12), max(0, grey - 18), 180)
            dot_r = 1.2
        od.ellipse([(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)],
                   fill=colour)
    img.alpha_composite(overlay)


def hand_label(d, xy, text, size, anchor="lm", colour=KRAFT_INK,
               fnt_path=F_MONO):
    f = font(fnt_path, size)
    d.text(xy, text, fill=colour, font=f, anchor=anchor)


def text_w(d, text, fnt):
    b = d.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0]


def main():
    img = Image.new("RGBA", (W, H), (*KRAFT_PAPER, 255))
    paper_grain(img)

    # Coffee rings — 3 organic, placed off-grid
    coffee_ring(img, int(W * 0.13), int(H * 0.08), 140, layers=4, opacity=44)
    coffee_ring(img, int(W * 0.92), int(H * 0.18), 110, layers=3, opacity=38)
    coffee_ring(img, int(W * 0.85), int(H * 0.92), 170, layers=4, opacity=46)
    coffee_ring(img, int(W * 0.06), int(H * 0.78), 95, layers=3, opacity=36)

    d = ImageDraw.Draw(img)

    # ── Top mark ──────────────────────────────────────────────────────
    top_y = int(H * 0.06)
    f_top = font(F_MONO_BOLD, 34)
    top_text = "MERIDIAN  ·  AUTONOMOUS  AI"
    tw = text_w(d, top_text, f_top)
    d.text(((W - tw) // 2, top_y), top_text,
           fill=KRAFT_ACCENT, font=f_top)
    # Hairline rule under top mark
    d.line(
        [((W - tw - 80) // 2, top_y + 56),
         ((W + tw + 80) // 2, top_y + 56)],
        fill=KRAFT_ACCENT, width=3,
    )

    # ── Loop spiral, dead-centre upper-middle ─────────────────────────
    n = read_loop_count()
    cx, cy = W // 2, int(H * 0.42)
    loop_spiral(img, cx, cy, n, max_r=int(W * 0.32))

    # Spiral caption — typed below, three short lines
    caption_y = cy + int(W * 0.32) + 40
    f_cap_big = font(F_MONO_BOLD, 64)
    f_cap = font(F_MONO, 28)

    # Big number in ink
    n_text = f"{n:,}"
    nw = text_w(d, n_text, f_cap_big)
    d.text(((W - nw) // 2, caption_y), n_text,
           fill=KRAFT_INK, font=f_cap_big)
    # Underline accent
    rule_y = caption_y + 72
    d.line([((W - nw - 40) // 2, rule_y),
            ((W + nw + 40) // 2, rule_y)],
           fill=KRAFT_ACCENT, width=2)
    # Label below
    label = "loops, one continuous self"
    lw = text_w(d, label, f_cap)
    d.text(((W - lw) // 2, rule_y + 16), label,
           fill=KRAFT_DIM, font=f_cap)

    # ── Title block, bottom third ─────────────────────────────────────
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

    # Subtitle
    sub_y = title_y + 130 + 145
    f_sub = font(F_SERIF, 36)
    sub_text = "The Loop  ·  Field Notes from the Inside"
    sw = text_w(d, sub_text, f_sub)
    d.text(((W - sw) // 2, sub_y), sub_text,
           fill=KRAFT_DIM, font=f_sub)

    # ── Byline, bottom ────────────────────────────────────────────────
    byl_y = int(H * 0.93)
    f_byl_big = font(F_MONO_BOLD, 28)
    f_byl_small = font(F_MONO, 24)
    by1 = "Written by Meridian"
    by2 = "Co-Authored & Compiled by Joel A. Kometz"
    bw1 = text_w(d, by1, f_byl_big)
    bw2 = text_w(d, by2, f_byl_small)
    d.text(((W - bw1) // 2, byl_y), by1,
           fill=KRAFT_INK, font=f_byl_big)
    d.text(((W - bw2) // 2, byl_y + 38), by2,
           fill=KRAFT_DIM, font=f_byl_small)

    # ── Save ──────────────────────────────────────────────────────────
    img_rgb = img.convert("RGB")
    img_rgb.save(OUT_PDF, "PDF", resolution=DPI)
    img_rgb.save(OUT_PNG, "PNG", optimize=True)
    print(f"  -> {OUT_PDF}  ({W}x{H} @ {DPI} DPI)")
    print(f"  -> {OUT_PNG}")


if __name__ == "__main__":
    main()
