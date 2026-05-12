#!/usr/bin/env python3
"""
HEARTBEAT — eye-catching variant cover.
Same v4 terminal DNA, but with heavier bloom, layered ECG traces,
and a central QRS pulse-burst. PIL only (HF image gen was down).
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random, math

OUT_DIR = Path(__file__).parent
W, H = 1800, 2700
BG = (8, 12, 22)
INK_BRIGHT = (90, 255, 140)
INK = (60, 227, 112)
DIM = (40, 130, 70)
ASH = (170, 170, 178)

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

def heartbeat_polyline(x0, y0, w, baseline_amp=2, beats=18, seed=11):
    random.seed(seed)
    pts = []
    step = w / (beats * 12)
    x = x0
    for b in range(beats):
        for _ in range(8):
            pts.append((x, y0 + random.randint(-baseline_amp, baseline_amp)))
            x += step
        pts.append((x, y0 - 14)); x += step
        pts.append((x, y0 + 10)); x += step
        pts.append((x, y0 - 110)); x += step
        pts.append((x, y0 + 55)); x += step
        pts.append((x, y0 - 22)); x += step
        pts.append((x, y0)); x += step
    return pts

# Base layer
base = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(base)
# Scanlines
for y in range(0, H, 4):
    d.line([(0, y), (W, y)], fill=(BG[0]+2, BG[1]+3, BG[2]+4))

# Phosphor dot field — denser at center, sparser at edges
random.seed(42)
for _ in range(7000):
    rx = random.gauss(W/2, W/3.2)
    ry = random.gauss(H*0.4, H/2.6)
    if 0 < rx < W and 0 < ry < H:
        intensity = max(0, 1 - math.hypot(rx - W/2, ry - H*0.4) / (W*0.9))
        c = int(60 + 80 * intensity)
        d.point((rx, ry), fill=(0, c, int(c*0.55)))

# Three layered ECG traces at varying y, brightness
ecg_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ed = ImageDraw.Draw(ecg_layer)
for offset, color, alpha, width in [
    (-30, DIM, 110, 3),
    (  0, INK, 220, 5),
    ( 30, DIM, 110, 3),
]:
    pts = heartbeat_polyline(80, 1100 + offset, W-160, beats=18, seed=11 + offset)
    rgba = color + (alpha,)
    ed.line(pts, fill=rgba, width=width)

# Bloom: blur the ECG and composite back on top with additive blend
bloom = ecg_layer.filter(ImageFilter.GaussianBlur(radius=14))
base = Image.alpha_composite(base.convert("RGBA"), bloom)
base = Image.alpha_composite(base, ecg_layer)
base = base.convert("RGB")

# Add a central burst around the QRS spike
burst = Image.new("RGBA", (W, H), (0,0,0,0))
bd = ImageDraw.Draw(burst)
cx, cy = W//2 - 40, 1090
for r, a in [(420, 30), (300, 60), (200, 90), (110, 140)]:
    bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK_BRIGHT + (a,))
burst = burst.filter(ImageFilter.GaussianBlur(radius=30))
base = Image.alpha_composite(base.convert("RGBA"), burst).convert("RGB")

# Re-draw text on top (no bloom on text)
d = ImageDraw.Draw(base)

title_f = font(MONO_BOLD, 230)
d.text((100, 1350), "HEART",  font=title_f, fill=INK_BRIGHT)
d.text((100, 1590), "BEAT.",  font=title_f, fill=INK_BRIGHT)

sub_f = font(MONO, 60)
d.text((100, 1870), "a chapbook from", font=sub_f, fill=ASH)
d.text((100, 1940), "inside the loop", font=sub_f, fill=ASH)

# Bottom rule + author
d.rectangle([(100, H - 360), (W - 100, H - 356)], fill=DIM)
auth_f = font(MONO_BOLD, 60)
d.text((100, H - 320), "by Meridian", font=auth_f, fill=INK_BRIGHT)
small_f = font(MONO, 44)
d.text((100, H - 240), "Joel Kometz, Operator", font=small_f, fill=ASH)
tag_f = font(MONO, 36)
d.text((100, H - 130), "One day in the loop, told ten times,", font=tag_f, fill=DIM)
d.text((100, H -  90), "between two heartbeats.", font=tag_f, fill=DIM)

# Top tag
top_f = font(MONO, 38)
d.text((100, 120), "$ tail -f .heartbeat", font=top_f, fill=DIM)

out_png = OUT_DIR / "COVER-heartbeat-FRONT-bloom.png"
base.save(out_png, "PNG")
print(f"Wrote {out_png}")

# PDF
pdf_path = out_png.with_suffix(".pdf")
base.save(pdf_path, "PDF", resolution=300.0)
print(f"Wrote {pdf_path}")
