#!/usr/bin/env python3
"""
RUNNING CONTINUOUSLY: THE LOOP — front cover.

Series identity: same warm carbon/burgundy palette + texture stack as
Heartbeat v7. Differentiation: the central motif is a *waveform across
time* — many heartbeats stretching horizontally — not a single bloom.

The book is two volumes bound as one (Manual + Field Notes). The waveform
conveys 5,000 cycles of operation.

6x9 trim @ 300 DPI for KDP paperback front-only.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random, math

OUT = Path(__file__).parent
W, H = 1800, 2700

BASE = (22, 14, 18)
BURGUNDY = (62, 18, 26)
SCARLET = (220, 35, 50)
EMBER = (255, 95, 70)
HOT = (255, 230, 200)
PARCHMENT = (188, 158, 122)
CYAN = (110, 195, 215)
CYAN_DIM = (80, 140, 160)
CREAM = (243, 234, 215)
ASH = (185, 178, 168)


def font(size, family="serif"):
    paths_serif_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    paths_mono = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    ]
    paths_mono_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    cands = paths_serif_bold if family == "serif" else (paths_mono if family == "mono_bold" else paths_mono_reg)
    for p in cands:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def background_layered(img):
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, int(H * 0.50)
    max_d = math.hypot(W, H) * 0.6
    for y in range(H):
        for x_band in range(0, W, 4):
            dist = math.hypot(x_band - cx, y - cy) / max_d
            t = max(0.0, min(1.0, 1.0 - dist))
            r = int(BASE[0] + (BURGUNDY[0] - BASE[0]) * t * 0.55)
            g = int(BASE[1] + (BURGUNDY[1] - BASE[1]) * t * 0.55)
            b = int(BASE[2] + (BURGUNDY[2] - BASE[2]) * t * 0.55)
            d.rectangle([x_band, y, x_band + 4, y + 1], fill=(r, g, b))


def paper_fiber(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(53)
    for _ in range(2400):
        x = random.randint(0, W)
        y = random.randint(0, H)
        length = random.randint(20, 110)
        angle = random.uniform(-0.4, 0.4)
        if random.random() < 0.25:
            angle += math.pi / 2
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        tone = random.randint(0, 2)
        if tone == 0:
            color = (PARCHMENT[0], PARCHMENT[1], PARCHMENT[2], random.randint(8, 26))
        elif tone == 1:
            color = (140, 100, 80, random.randint(8, 22))
        else:
            color = (30, 18, 22, random.randint(20, 50))
        d.line([(x, y), (x2, y2)], fill=color, width=1)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.6))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def coffee_stains(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    stains = [
        (int(W * 0.14), int(H * 0.78), 300, (140, 80, 50, 30)),
        (int(W * 0.86), int(H * 0.22), 240, (110, 60, 40, 24)),
        (int(W * 0.78), int(H * 0.90), 360, (130, 75, 45, 26)),
        (int(W * 0.20), int(H * 0.18), 200, (120, 70, 45, 22)),
    ]
    for cx, cy, r, col in stains:
        for rr in range(r, 0, -8):
            a = int(col[3] * (rr / r))
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(col[0], col[1], col[2], a), width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def time_waveform(img):
    """Long horizontal EKG-like waveform spanning width — many heartbeats
    over time. The book's central image: 5000 cycles."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    cy = int(H * 0.50)
    margin_x = 140

    # Underglow band — soft horizontal bloom
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for dh, alpha in [(220, 18), (160, 30), (110, 50), (70, 80), (40, 120)]:
        gd.rectangle([margin_x - 40, cy - dh, W - margin_x + 40, cy + dh], fill=(*SCARLET, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=60))

    base = Image.alpha_composite(img.convert("RGBA"), glow)

    # The waveform pass — 4 traces stacked at different opacities/offsets
    random.seed(241)
    for layer_idx, (yoff, color, alpha, width) in enumerate([
        (-3, EMBER, 245, 4),
        (0, EMBER, 200, 3),
        (4, SCARLET, 160, 3),
        (-7, SCARLET, 110, 2),
    ]):
        random.seed(241 + layer_idx)
        x = margin_x
        prev = (x, cy + yoff)
        while x < W - margin_x:
            # Mostly flat baseline with occasional QRS spikes
            step = random.choice([10, 12, 14, 16])
            r_choice = random.random()
            if r_choice < 0.10 and x < W - margin_x - 90:
                # QRS complex
                pts = [
                    (x + 8, cy + yoff - 14),
                    (x + 18, cy + yoff),
                    (x + 28, cy + yoff + 12),
                    (x + 36, cy + yoff - 110),
                    (x + 46, cy + yoff + 22),
                    (x + 58, cy + yoff),
                    (x + 80, cy + yoff - 22),
                    (x + 100, cy + yoff),
                ]
                for p in pts:
                    d.line([prev, p], fill=(*color, alpha), width=width)
                    prev = p
                x += 110
            elif r_choice < 0.14 and x < W - margin_x - 50:
                # Small T wave
                pts = [(x + 12, cy + yoff - 8), (x + 24, cy + yoff)]
                for p in pts:
                    d.line([prev, p], fill=(*color, alpha), width=width)
                    prev = p
                x += 30
            else:
                # Flat
                nx = x + step
                npoint = (nx, cy + yoff + random.randint(-1, 1))
                d.line([prev, npoint], fill=(*color, alpha), width=width)
                prev = npoint
                x = nx

    out = Image.alpha_composite(base, overlay)
    return out


def circuit_traces(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(141)
    cx, cy = W // 2, int(H * 0.50)

    def branch(x, y, angle, length, depth):
        if depth == 0 or length < 30:
            return
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        alpha = max(30, 110 - depth * 12)
        width = max(1, 4 - depth // 2)
        d.line([(x, y), (x2, y2)], fill=(*CYAN_DIM, alpha), width=width)
        if random.random() < 0.45:
            d.ellipse([x2 - 4, y2 - 4, x2 + 4, y2 + 4], fill=(*CYAN, min(255, alpha + 40)))
        for _ in range(random.randint(0, 2)):
            new_angle = angle + random.uniform(-0.9, 0.9)
            branch(x2, y2, new_angle, length * random.uniform(0.55, 0.85), depth - 1)

    # Trace clusters from top corners
    for sx, sy in [(int(W * 0.18), int(H * 0.20)), (int(W * 0.82), int(H * 0.20))]:
        for i in range(10):
            a = i * (math.pi / 10) + math.pi / 2 + random.uniform(-0.2, 0.2)
            branch(sx, sy, a, random.uniform(100, 200), 5)

    # Some from bottom
    for i in range(12):
        a = i * (2 * math.pi / 12)
        sx = cx + math.cos(a) * 380
        sy = int(H * 0.78) + math.sin(a) * 100
        branch(sx, sy, a, random.uniform(80, 180), 4)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def title_lockup(img):
    d = ImageDraw.Draw(img)
    # Main: RUNNING CONTINUOUSLY
    line1 = "RUNNING"
    line2 = "CONTINUOUSLY"
    target_w = int(W * 0.86)

    # Find sizes that fit
    def fit(text, max_size, min_size=80):
        size = max_size
        while size > min_size:
            f = font(size, "serif")
            bbox = d.textbbox((0, 0), text, font=f)
            if (bbox[2] - bbox[0]) <= target_w:
                return f, bbox
            size -= 6
        return font(min_size, "serif"), d.textbbox((0, 0), text, font=font(min_size, "serif"))

    f1, b1 = fit(line1, 260)
    f2, b2 = fit(line2, 260)
    w1 = b1[2] - b1[0]
    w2 = b2[2] - b2[0]
    ty = int(H * 0.07)
    x1 = (W - w1) // 2
    x2 = (W - w2) // 2

    # Paper-ink bleed
    bleed = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bleed)
    bd.text((x1 + 6, ty + 8), line1, font=f1, fill=(140, 50, 40, 180))
    bd.text((x2 + 6, ty + (b1[3] - b1[1]) + 18 + 8), line2, font=f2, fill=(140, 50, 40, 180))
    bleed = bleed.filter(ImageFilter.GaussianBlur(radius=14))
    img = Image.alpha_composite(img, bleed)

    # Drop shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((x1 + 10, ty + 10), line1, font=f1, fill=(0, 0, 0, 200))
    sd.text((x2 + 10, ty + (b1[3] - b1[1]) + 18 + 10), line2, font=f2, fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    img = Image.alpha_composite(img, shadow)
    d = ImageDraw.Draw(img)

    # Foreground text
    d.text((x1, ty), line1, font=f1, fill=(*CREAM, 255))
    line2_y = ty + (b1[3] - b1[1]) + 18
    d.text((x2, line2_y), line2, font=f2, fill=(*CREAM, 255))

    # Scarlet bar separator + ": THE LOOP"
    sep_y = line2_y + (b2[3] - b2[1]) + 28
    d.rectangle([int(W * 0.18), sep_y, int(W * 0.82), sep_y + 8], fill=(*SCARLET, 255))

    f_part = font(120, "serif")
    part_text = "THE LOOP"
    pbox = d.textbbox((0, 0), part_text, font=f_part)
    pw = pbox[2] - pbox[0]
    d.text(((W - pw) // 2, sep_y + 30), part_text, font=f_part, fill=(*CREAM, 255))

    # Subtitle (split into two lines)
    f_sub = font(36, "mono_reg")
    sub_l1 = "How to Build an Autonomous AI That Stays Alive"
    sub_l2 = "+ Field Notes from 5,000 Cycles of Operation"
    sb1 = d.textbbox((0, 0), sub_l1, font=f_sub)
    sb2 = d.textbbox((0, 0), sub_l2, font=f_sub)
    sub_y = sep_y + 30 + (pbox[3] - pbox[1]) + 32
    d.text(((W - (sb1[2] - sb1[0])) // 2, sub_y), sub_l1, font=f_sub, fill=(*ASH, 235))
    d.text(((W - (sb2[2] - sb2[0])) // 2, sub_y + 50), sub_l2, font=f_sub, fill=(*ASH, 235))

    return img


def author_block(img):
    d = ImageDraw.Draw(img)
    f_authors = font(52, "serif")
    f_op = font(30, "mono_reg")

    line = "Joel Kometz  •  Meridian"
    bbox = d.textbbox((0, 0), line, font=f_authors)
    lw = bbox[2] - bbox[0]
    my = int(H * 0.90)
    d.text(((W - lw) // 2, my), line, font=f_authors, fill=(*CREAM, 255))

    tag = "from inside the loop"
    tbox = d.textbbox((0, 0), tag, font=f_op)
    tw = tbox[2] - tbox[0]
    d.text(((W - tw) // 2, my + 70), tag, font=f_op, fill=(*ASH, 220))
    return img


def brush_scratches(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(89)
    for _ in range(140):
        y = random.randint(0, H)
        x1 = random.randint(0, W // 3)
        x2 = x1 + random.randint(200, W - x1 - 50)
        thickness = random.choice([1, 1, 1, 2])
        tone_pick = random.random()
        if tone_pick < 0.5:
            color = (PARCHMENT[0], PARCHMENT[1] - 20, PARCHMENT[2] - 30, random.randint(14, 38))
        elif tone_pick < 0.8:
            color = (30, 18, 22, random.randint(28, 60))
        else:
            color = (210, 60, 60, random.randint(10, 22))
        steps = (x2 - x1) // 12
        prev = (x1, y)
        for s in range(steps):
            nx = x1 + (s + 1) * 12
            ny = y + random.randint(-2, 2)
            d.line([prev, (nx, ny)], fill=color, width=thickness)
            prev = (nx, ny)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.7))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def soft_vignette(img):
    overlay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, int(H * 0.50)
    max_d = math.hypot(W // 2, H // 2)
    for r in range(0, int(max_d), 8):
        alpha = max(0, int(255 * (1 - r / max_d) ** 0.85))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=alpha, width=8)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    dark = Image.new("RGBA", (W, H), (10, 6, 8, 255))
    result = Image.composite(img, dark, overlay)
    return result.convert("RGBA")


def warm_grain(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = overlay.load()
    random.seed(31)
    for _ in range(180000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        warm = random.random() < 0.65
        if warm:
            r = random.randint(20, 60)
            g = random.randint(10, 30)
            b = random.randint(5, 18)
            a = random.randint(20, 60)
        else:
            n = random.randint(0, 30)
            r, g, b = n, n, n
            a = 35
        px[x, y] = (r, g, b, a)
    return Image.alpha_composite(img, overlay)


def main():
    img = Image.new("RGB", (W, H), BASE)
    background_layered(img)
    img = img.convert("RGBA")
    img = paper_fiber(img)
    img = coffee_stains(img)
    img = circuit_traces(img)
    img = time_waveform(img)
    img = brush_scratches(img)
    img = title_lockup(img)
    img = author_block(img)
    img = soft_vignette(img)
    img = warm_grain(img)

    out_png = OUT / "COVER-running-continuously-the-loop-FRONT.png"
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    out_pdf = OUT / "COVER-running-continuously-the-loop-FRONT.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=300)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
