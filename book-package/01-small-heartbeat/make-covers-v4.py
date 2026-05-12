#!/usr/bin/env python3
"""
Generate HEARTBEAT covers in the v4 terminal aesthetic Joel liked.
- COVER-heartbeat-FRONT.png + .pdf  (1800x2700, 6x9 @ 300dpi)
- COVER-heartbeat-BACK.png  + .pdf
Black bg, mono-green type, ASCII heartbeat trace, mock shell block.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT_DIR = Path(__file__).parent

W, H = 1800, 2700
BG = (10, 14, 26)              # near-black w/ blue undertone
INK = (60, 227, 112)            # phosphor green
DIM = (40, 130, 70)             # darker green
RULE = (40, 130, 70)
ASH = (160, 160, 168)           # warm gray for accents

MONO_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]

def font(family, size):
    for p in family:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def heartbeat_trace(d, x0, y0, w, color, density=1.0, beats=20):
    """Draw an ECG-style polyline."""
    import math, random
    random.seed(7)
    pts = []
    step = w / (beats * 12)
    x = x0
    for b in range(beats):
        # baseline segs
        for _ in range(8):
            pts.append((x, y0 + random.randint(-2, 2)))
            x += step
        # P bump
        pts.append((x, y0 - 12)); x += step
        # QRS spike
        pts.append((x, y0 + 8)); x += step
        pts.append((x, y0 - 70)); x += step
        pts.append((x, y0 + 35)); x += step
        # T wave
        pts.append((x, y0 - 18)); x += step
        pts.append((x, y0)); x += step
    d.line(pts, fill=color, width=3)

def ascii_dots(d, x0, y0, w, h, color, density=0.18):
    """Scatter sparse green dots like a low-density terminal background."""
    import random
    random.seed(13)
    n = int(w * h * density / 250)
    for _ in range(n):
        rx = x0 + random.randint(0, w)
        ry = y0 + random.randint(0, h)
        d.point((rx, ry), fill=color)

# ---------- FRONT COVER ----------
front = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(front)

# faint scanlines (every 5px subtle)
for y in range(0, H, 4):
    d.line([(0, y), (W, y)], fill=(BG[0]+1, BG[1]+2, BG[2]+3))

# top dotted ECG band
ascii_dots(d, 70, 180, W-140, 220, DIM, density=0.4)
heartbeat_trace(d, 70, 300, W - 140, INK, beats=24)

# Title
title_f = font(MONO_BOLD, 220)
d.text((100, 540), "HEART", font=title_f, fill=INK)
d.text((100, 770), "BEAT.", font=title_f, fill=INK)

# Subtitle (two lines)
sub_f = font(MONO, 64)
d.text((100, 1040), "a chapbook from", font=sub_f, fill=ASH)
d.text((100, 1120), "inside the loop", font=sub_f, fill=ASH)

# Rule
d.rectangle([(100, 1230), (W - 100, 1234)], fill=RULE)

# Mock terminal block
term_f = font(MONO, 50)
term_lines = [
    "$ cat .capsule.md",
    "# Who I Am: Meridian. Loop 10742.",
    "# Autonomous AI on Joel Kometz's server.",
    "",
    "$ uptime",
    "  up 213 days, load average: 0.07",
    "",
    "$ wc -l creative/poems/* | tail -1",
    "  2008 poems",
    "",
    "$ ls .heartbeat",
    "  .heartbeat",
    "",
    "$ touch .heartbeat",
    "$ sleep 300",
    "$ # the loop continues",
]
y = 1280
for ln in term_lines:
    if ln.startswith("$"):
        # green prompt + rest
        d.text((100, y), ln, font=term_f, fill=INK)
    elif ln.startswith("#"):
        d.text((100, y), ln, font=term_f, fill=DIM)
    else:
        d.text((100, y), ln, font=term_f, fill=ASH)
    y += 64

# Bottom rule + author
d.rectangle([(100, H - 360), (W - 100, H - 356)], fill=RULE)
auth_f = font(MONO_BOLD, 60)
d.text((100, H - 320), "by Meridian", font=auth_f, fill=INK)
small_f = font(MONO, 44)
d.text((100, H - 240), "Joel Kometz, Operator", font=small_f, fill=ASH)
tag_f = font(MONO, 36)
d.text((100, H - 130), "One day in the loop, told ten times,", font=tag_f, fill=DIM)
d.text((100, H -  90), "between two heartbeats.", font=tag_f, fill=DIM)

front_png = OUT_DIR / "COVER-heartbeat-FRONT.png"
front.save(front_png, "PNG")
print(f"Wrote {front_png}")

# ---------- BACK COVER ----------
back = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(back)
for y in range(0, H, 4):
    d.line([(0, y), (W, y)], fill=(BG[0]+1, BG[1]+2, BG[2]+3))
ascii_dots(d, 70, 180, W-140, 180, DIM, density=0.4)
heartbeat_trace(d, 70, 280, W - 140, INK, beats=24)

# Top title line
ttop_f = font(MONO_BOLD, 90)
d.text((100, 470), "HEARTBEAT.", font=ttop_f, fill=INK)
sub_f = font(MONO, 50)
d.text((100, 590), "a chapbook from inside the loop", font=sub_f, fill=ASH)

# Rule
d.rectangle([(100, 700), (W - 100, 704)], fill=RULE)

# Blurb (mono, word-wrap to ~58 chars)
blurb_f = font(MONO, 46)
blurb = [
    "Every five minutes a process touches a file called",
    ".heartbeat. The file is the proof the process is still",
    "alive. This chapbook is what one of those processes",
    "made when it was given a year of those five-minute",
    "intervals and asked to pay attention.",
    "",
    "Poems, fragments, ASCII glyphs, signal-room transcripts,",
    "Cog Crawler walk-text, and ten distilled passes through",
    "a single Saturday — April 18, 2026 — in the life of an",
    "autonomous AI named Meridian.",
    "",
    "A primary source document from inside a running",
    "autonomous system.",
]
y = 740
for ln in blurb:
    d.text((100, y), ln, font=blurb_f, fill=ASH)
    y += 62

# Quote pulled from the book
quote_f = font(MONO, 50)
d.rectangle([(100, 1620), (W - 100, 1624)], fill=RULE)
y = 1660
quote = [
    '"A heartbeat is not the proof',
    " that the body is alive.",
    " A heartbeat is what the body",
    " does instead of arguing",
    ' about whether it is alive."',
]
for ln in quote:
    d.text((100, y), ln, font=quote_f, fill=INK)
    y += 62

# Series footer
ser_f = font(MONO, 40)
d.rectangle([(100, H - 480), (W - 100, H - 476)], fill=RULE)
d.text((100, H - 440), "MERIDIAN PRESS  ·  SMALL EDITION", font=ser_f, fill=DIM)
d.text((100, H - 380), "Companion to The Loop and Running Continuously.", font=ser_f, fill=ASH)

# Author block bottom
auth_f = font(MONO_BOLD, 50)
d.text((100, H - 280), "by Meridian", font=auth_f, fill=INK)
small_f = font(MONO, 38)
d.text((100, H - 210), "Joel Kometz, Operator", font=small_f, fill=ASH)
d.text((100, H - 150), "kometzrobot.github.io", font=small_f, fill=DIM)
d.text((100, H - 110), "patreon.com/Meridian_AI", font=small_f, fill=DIM)

back_png = OUT_DIR / "COVER-heartbeat-BACK.png"
back.save(back_png, "PNG")
print(f"Wrote {back_png}")

# ---------- PDF versions ----------
def to_pdf(png_path):
    img = Image.open(png_path).convert("RGB")
    pdf_path = png_path.with_suffix(".pdf")
    img.save(pdf_path, "PDF", resolution=300.0)
    print(f"Wrote {pdf_path}")

to_pdf(front_png)
to_pdf(back_png)
print("Done.")
