#!/usr/bin/env python3
"""
Generate a clean 6x9 front cover for HEARTBEAT.
Output: COVER-heartbeat.png at KDP-compatible 1800x2700 px (300dpi).
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent / "COVER-heartbeat.png"

W, H = 1800, 2700
BG = (15, 18, 28)        # near-black with a hint of blue
INK = (235, 230, 220)    # warm off-white
ACCENT = (220, 90, 60)   # ember orange (Cinder palette)
DIM = (140, 140, 150)

# Find a serif and a mono font
SERIF_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
]
MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]

def find_font(candidates, size):
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Top thin rule
d.rectangle([(W*0.08, 220), (W*0.92, 224)], fill=DIM)

# Title block (HEARTBEAT)
title_font = find_font(SERIF_CANDIDATES, 240)
title = "HEARTBEAT"
tw, th = d.textbbox((0, 0), title, font=title_font)[2:]
d.text(((W - tw) / 2, 360), title, font=title_font, fill=INK)

# Subtitle
sub_font = find_font(SERIF_CANDIDATES, 70)
sub = "One Day in the Loop"
tw, _ = d.textbbox((0, 0), sub, font=sub_font)[2:]
d.text(((W - tw) / 2, 700), sub, font=sub_font, fill=INK)

# Center pulse — three ember dots, like a heartbeat trace
center_y = 1250
pulse_y = 1380
d.line([(W*0.18, pulse_y), (W*0.34, pulse_y),
        (W*0.38, pulse_y - 110), (W*0.42, pulse_y + 140),
        (W*0.46, pulse_y - 60), (W*0.50, pulse_y),
        (W*0.66, pulse_y), (W*0.70, pulse_y - 110),
        (W*0.74, pulse_y + 140), (W*0.78, pulse_y - 60),
        (W*0.82, pulse_y)], fill=ACCENT, width=8)

# Date stamp under pulse
mono = find_font(MONO_CANDIDATES, 56)
date = "2026.04.18  ·  LOOP 5750 — 5756"
tw, _ = d.textbbox((0, 0), date, font=mono)[2:]
d.text(((W - tw) / 2, 1640), date, font=mono, fill=DIM)

# Block of small text near middle-lower
quote_font = find_font(SERIF_CANDIDATES, 52)
quote = [
    "Twenty-four hours.",
    "Ten journal entries.",
    "One sixteen-minute death.",
]
y = 1860
for line in quote:
    tw, _ = d.textbbox((0, 0), line, font=quote_font)[2:]
    d.text(((W - tw) / 2, y), line, font=quote_font, fill=INK)
    y += 80

# Author at bottom
auth_font = find_font(SERIF_CANDIDATES, 60)
auth = "MERIDIAN  ·  JOEL KOMETZ"
tw, _ = d.textbbox((0, 0), auth, font=auth_font)[2:]
d.text(((W - tw) / 2, H - 360), auth, font=auth_font, fill=INK)

# Bottom thin rule
d.rectangle([(W*0.08, H-260), (W*0.92, H-256)], fill=DIM)

# Bottom label
lbl_font = find_font(MONO_CANDIDATES, 40)
lbl = "BOOK ONE  ·  SMALL EDITION"
tw, _ = d.textbbox((0, 0), lbl, font=lbl_font)[2:]
d.text(((W - tw) / 2, H - 220), lbl, font=lbl_font, fill=DIM)

img.save(OUT, "PNG")
print(f"Wrote {OUT} ({OUT.stat().st_size//1024} KB, {W}x{H})")
