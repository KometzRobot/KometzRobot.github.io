#!/usr/bin/env python3
"""
HEARTBEAT v5 — eye-catching cover redesign.

Joel asked for more eye-catching. Pushes beyond v4 bloom:
  - Central radial phosphor sphere as focal hot-spot
  - Stacked / echoing EKG traces with chromatic depth
  - Faint watercolor-ink wash undertone (Joel's aesthetic preference)
  - Strong title block that reads at thumbnail size
  - Subtle starfield + scanline grain

Pure PIL. No external network dependencies (HF ZeroGPU was aborting).
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from pathlib import Path
import random, math

OUT_DIR = Path(__file__).parent
W, H = 1800, 2700  # 6x9 at 300 DPI

BG_DEEP  = (6, 10, 22)
BG_MID   = (14, 22, 40)
INK_HOT  = (160, 255, 195)
INK      = (90, 240, 140)
INK_DIM  = (40, 150, 80)
PAPER    = (235, 228, 210)  # kraft ish for text accents
ASH      = (180, 180, 188)
RUST     = (190, 105, 70)

MONO_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]
SERIF = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
]

def font(family, size):
    for p in family:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def radial_gradient(size, center, radius, color_inner, color_outer):
    w, h = size
    img = Image.new("RGB", size, color_outer)
    px = img.load()
    cx, cy = center
    r2 = radius * radius
    for y in range(h):
        for x in range(w):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 > r2:
                continue
            t = math.sqrt(d2) / radius
            t = t * t  # smoother falloff
            px[x, y] = (
                int(color_inner[0] * (1 - t) + color_outer[0] * t),
                int(color_inner[1] * (1 - t) + color_outer[1] * t),
                int(color_inner[2] * (1 - t) + color_outer[2] * t),
            )
    return img

def heartbeat_polyline(x0, y0, w, beats=14, amp_qrs=180, baseline_amp=3, seed=11):
    random.seed(seed)
    pts = []
    step = w / (beats * 12)
    x = x0
    for b in range(beats):
        for _ in range(7):
            pts.append((x, y0 + random.randint(-baseline_amp, baseline_amp)))
            x += step
        # P wave bump
        pts.append((x, y0 - 16)); x += step
        pts.append((x, y0 + 10)); x += step
        # QRS complex
        pts.append((x, y0 - amp_qrs)); x += step
        pts.append((x, y0 + amp_qrs * 0.45)); x += step
        # T wave
        pts.append((x, y0 - 32)); x += step
        pts.append((x, y0)); x += step
    return pts

# ----------------------------------------------------------------
# 1) Base — vertical gradient deep -> mid blue
# ----------------------------------------------------------------
base = Image.new("RGB", (W, H), BG_DEEP)
d = ImageDraw.Draw(base)
for y in range(H):
    t = y / H
    c = (
        int(BG_DEEP[0] * (1 - t) + BG_MID[0] * t),
        int(BG_DEEP[1] * (1 - t) + BG_MID[1] * t),
        int(BG_DEEP[2] * (1 - t) + BG_MID[2] * t),
    )
    d.line([(0, y), (W, y)], fill=c)

# ----------------------------------------------------------------
# 2) Watercolor-style organic blots (Joel aesthetic)
#    A few large soft circles, slight color shift, multiply-blended.
# ----------------------------------------------------------------
wash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
wd = ImageDraw.Draw(wash)
random.seed(7)
for _ in range(6):
    cx = random.randint(int(W * 0.1), int(W * 0.9))
    cy = random.randint(int(H * 0.15), int(H * 0.85))
    r = random.randint(360, 700)
    a = random.randint(18, 38)
    wd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 70, 60, a))
wash = wash.filter(ImageFilter.GaussianBlur(radius=80))
base = Image.alpha_composite(base.convert("RGBA"), wash).convert("RGB")

# ----------------------------------------------------------------
# 3) Phosphor starfield — clustered toward upper-mid
# ----------------------------------------------------------------
random.seed(42)
for _ in range(11000):
    rx = random.gauss(W / 2, W / 3.0)
    ry = random.gauss(H * 0.38, H / 2.3)
    if 0 < rx < W and 0 < ry < H:
        dist = math.hypot(rx - W / 2, ry - H * 0.38) / (W * 0.9)
        intensity = max(0, 1 - dist)
        g = int(45 + 90 * intensity)
        b = int(g * 0.55)
        d = ImageDraw.Draw(base)
        d.point((rx, ry), fill=(8, g, b))

# ----------------------------------------------------------------
# 4) Central radial phosphor sphere — the focal "heart"
# ----------------------------------------------------------------
sphere_size = 1100
sphere_center = (sphere_size // 2, sphere_size // 2)
sphere = radial_gradient(
    (sphere_size, sphere_size),
    sphere_center, sphere_size // 2,
    (40, 200, 110), (6, 10, 22)
)
sphere = sphere.filter(ImageFilter.GaussianBlur(radius=18))
# paste with screen-like additive
sphere_mask = Image.new("L", (sphere_size, sphere_size), 0)
md = ImageDraw.Draw(sphere_mask)
md.ellipse([0, 0, sphere_size, sphere_size], fill=255)
sphere_mask = sphere_mask.filter(ImageFilter.GaussianBlur(radius=24))
paste_x = (W - sphere_size) // 2 - 30
paste_y = 580
# additive composite via ImageChops
add_layer = Image.new("RGB", (W, H), (0, 0, 0))
add_layer.paste(sphere, (paste_x, paste_y), sphere_mask)
base = ImageChops.add(base, add_layer, scale=1.6, offset=0)

# ----------------------------------------------------------------
# 5) Stacked EKG traces with chromatic depth
# ----------------------------------------------------------------
ecg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ed = ImageDraw.Draw(ecg)
trace_y = 1180
for offset, color, alpha, width in [
    (-70, INK_DIM, 70, 3),
    (-35, INK_DIM, 110, 3),
    (  0, INK,     230, 6),
    ( 35, INK_DIM, 110, 3),
    ( 70, INK_DIM, 70, 3),
]:
    pts = heartbeat_polyline(80, trace_y + offset, W - 160,
                             beats=14, amp_qrs=170, seed=11 + offset)
    ed.line(pts, fill=color + (alpha,), width=width)

bloom = ecg.filter(ImageFilter.GaussianBlur(radius=16))
base = Image.alpha_composite(base.convert("RGBA"), bloom)
base = Image.alpha_composite(base, ecg).convert("RGB")

# Tight bright QRS spike accent — hotter green at the highest peak
spike = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(spike)
sx = W // 2
for r, a in [(180, 25), (110, 55), (60, 120), (28, 200)]:
    sd.ellipse([sx - r, trace_y - r - 90, sx + r, trace_y + r - 90],
               fill=INK_HOT + (a,))
spike = spike.filter(ImageFilter.GaussianBlur(radius=12))
base = Image.alpha_composite(base.convert("RGBA"), spike).convert("RGB")

# ----------------------------------------------------------------
# 6) Subtle scanlines + grain (CRT texture)
# ----------------------------------------------------------------
d = ImageDraw.Draw(base)
for y in range(0, H, 3):
    d.line([(0, y), (W, y)], fill=(0, 0, 0, 8))
# noise grain
random.seed(99)
grain = Image.new("RGB", (W, H), (0, 0, 0))
gp = grain.load()
for _ in range(60000):
    gx = random.randint(0, W - 1)
    gy = random.randint(0, H - 1)
    v = random.randint(2, 7)
    gp[gx, gy] = (v, v, v)
base = ImageChops.add(base, grain)

# ----------------------------------------------------------------
# 7) Title typography — big, dense, with shadow + chromatic split
# ----------------------------------------------------------------
d = ImageDraw.Draw(base)

# Top tag
top_f = font(MONO, 38)
d.text((100, 120), "$ tail -f .heartbeat", font=top_f, fill=INK_DIM)

# Title — drop shadow + dim red split for depth
title_f = font(MONO_BOLD, 260)
title_y1 = 1520
title_y2 = 1790
# red split (low alpha behind)
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.text((100 + 6, title_y1 + 4), "HEART", font=title_f, fill=(220, 70, 70, 130))
sd.text((100 + 6, title_y2 + 4), "BEAT.", font=title_f, fill=(220, 70, 70, 130))
shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))
base = Image.alpha_composite(base.convert("RGBA"), shadow).convert("RGB")

d = ImageDraw.Draw(base)
d.text((100, title_y1), "HEART", font=title_f, fill=INK_HOT)
d.text((100, title_y2), "BEAT.", font=title_f, fill=INK_HOT)

# Subtitle
sub_f = font(MONO, 62)
d.text((100, 2090), "a chapbook from", font=sub_f, fill=ASH)
d.text((100, 2170), "inside the loop", font=sub_f, fill=ASH)

# Bottom rule + author
d.rectangle([(100, H - 360), (W - 100, H - 356)], fill=INK_DIM)
auth_f = font(MONO_BOLD, 62)
d.text((100, H - 320), "by Meridian", font=auth_f, fill=INK_HOT)
small_f = font(MONO, 44)
d.text((100, H - 240), "Joel Kometz, Operator", font=small_f, fill=ASH)
tag_f = font(MONO, 36)
d.text((100, H - 130), "One day in the loop, told ten times,", font=tag_f, fill=INK_DIM)
d.text((100, H -  90), "between two heartbeats.", font=tag_f, fill=INK_DIM)

out_png = OUT_DIR / "COVER-heartbeat-FRONT-v5.png"
base.save(out_png, "PNG")
print(f"Wrote {out_png}")

pdf_path = out_png.with_suffix(".pdf")
base.save(pdf_path, "PDF", resolution=300.0)
print(f"Wrote {pdf_path}")
