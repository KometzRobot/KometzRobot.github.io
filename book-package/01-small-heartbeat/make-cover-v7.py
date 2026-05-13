#!/usr/bin/env python3
"""
HEARTBEAT v7 cover — Joel feedback on v6: "too dark, need layer and texture."

v7 changes vs v6:
  - Background base lifted from near-black to warm carbon + burgundy underlay
  - Parchment/paper-fiber texture pass (visible, not subliminal)
  - Brush-scratch and ink-bleed overlay for material presence
  - EKG rings: brighter, more layers, broader alpha range
  - Coffee-stain/halation rings around the bloom
  - Vignette much softer — corners shaded, body lifted
  - Grain pass larger and warmer (not blue noise)
  - Title gets a paper-ink bleed under it
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from pathlib import Path
import random, math

OUT = Path(__file__).parent
W, H = 1800, 2700  # 6x9 at 300 DPI

# Warmer, lifted palette
BASE = (22, 14, 18)         # warm carbon — not black
BURGUNDY = (62, 18, 26)     # deep wine underlayer
SCARLET = (220, 35, 50)
EMBER = (255, 95, 70)
HOT = (255, 230, 200)
PARCHMENT = (188, 158, 122) # warm paper tone
CYAN = (110, 195, 215)
CYAN_DIM = (80, 140, 160)
CREAM = (243, 234, 215)
ASH = (185, 178, 168)
INK = (32, 18, 16)


def font(size, family="serif", weight="bold"):
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
    cands = paths_serif_bold if family == "serif" else (paths_mono if weight == "bold" else paths_mono_reg)
    for p in cands:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def background_layered(img):
    """Layered warm base — burgundy underglow center, warmer carbon at edges."""
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, int(H * 0.46)
    max_d = math.hypot(W, H) * 0.6
    for y in range(H):
        for x_band in range(0, W, 4):
            # Radial blend from burgundy near center to BASE at edges
            dist = math.hypot(x_band - cx, y - cy) / max_d
            t = max(0.0, min(1.0, 1.0 - dist))
            # Mix BURGUNDY into BASE
            r = int(BASE[0] + (BURGUNDY[0] - BASE[0]) * t * 0.55)
            g = int(BASE[1] + (BURGUNDY[1] - BASE[1]) * t * 0.55)
            b = int(BASE[2] + (BURGUNDY[2] - BASE[2]) * t * 0.55)
            d.rectangle([x_band, y, x_band + 4, y + 1], fill=(r, g, b))


def paper_fiber(img):
    """Long thin fiber threads — like handmade paper. Visible texture."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(53)
    # Many short fiber strokes, varying angle, mostly warm and faint
    for _ in range(2200):
        x = random.randint(0, W)
        y = random.randint(0, H)
        length = random.randint(20, 110)
        angle = random.uniform(-0.4, 0.4)  # mostly horizontal
        if random.random() < 0.25:
            angle += math.pi / 2  # some vertical
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        tone = random.randint(0, 2)
        if tone == 0:
            color = (PARCHMENT[0], PARCHMENT[1], PARCHMENT[2], random.randint(8, 26))
        elif tone == 1:
            color = (140, 100, 80, random.randint(8, 22))
        else:
            color = (30, 18, 22, random.randint(20, 50))  # dark fiber
        d.line([(x, y), (x2, y2)], fill=color, width=1)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.6))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def coffee_stains(img):
    """Soft amber halation rings — like a coffee ring or watercolor wash."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(19)
    stains = [
        (int(W * 0.18), int(H * 0.74), 280, (140, 80, 50, 28)),
        (int(W * 0.82), int(H * 0.18), 220, (110, 60, 40, 22)),
        (int(W * 0.72), int(H * 0.86), 340, (130, 75, 45, 24)),
        (int(W * 0.16), int(H * 0.22), 180, (120, 70, 45, 20)),
    ]
    for cx, cy, r, col in stains:
        for rr in range(r, 0, -8):
            a = int(col[3] * (rr / r))
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(col[0], col[1], col[2], a), width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def circuit_traces(img):
    """Thin cyan branching circuit traces — more visible than v6."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(141)
    cx, cy = W // 2, int(H * 0.42)

    def branch(x, y, angle, length, depth):
        if depth == 0 or length < 30:
            return
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        alpha = max(35, 130 - depth * 12)
        width = max(1, 5 - depth // 2)
        d.line([(x, y), (x2, y2)], fill=(*CYAN_DIM, alpha), width=width)
        if random.random() < 0.55:
            d.ellipse([x2 - 4, y2 - 4, x2 + 4, y2 + 4], fill=(*CYAN, min(255, alpha + 50)))
        for _ in range(random.randint(0, 2)):
            new_angle = angle + random.uniform(-0.9, 0.9)
            branch(x2, y2, new_angle, length * random.uniform(0.55, 0.85), depth - 1)

    for i in range(18):
        a = i * (2 * math.pi / 18) + random.uniform(-0.1, 0.1)
        start_r = random.uniform(300, 420)
        sx = cx + math.cos(a) * start_r
        sy = cy + math.sin(a) * start_r
        branch(sx, sy, a, random.uniform(120, 280), 5)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def starfield(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(7)
    for _ in range(380):
        x = random.randint(0, W)
        y = random.randint(0, H)
        b = random.randint(80, 230)
        d.point((x, y), fill=(b, b, b))
        if random.random() < 0.18:
            d.point((x - 1, y), fill=(int(b * 0.6), int(b * 0.2), int(b * 0.2)))
            d.point((x + 1, y), fill=(int(b * 0.2), int(b * 0.4), int(b * 0.6)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def central_pulse(img):
    cx, cy = W // 2, int(H * 0.42)
    pulse = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(pulse)
    # Bigger, brighter outer bloom
    for r, alpha in [(820, 14), (660, 26), (510, 50), (380, 80), (260, 115)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*SCARLET, alpha))
    pulse = pulse.filter(ImageFilter.GaussianBlur(radius=80))

    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    for r, alpha in [(200, 130), (140, 180), (95, 220), (60, 245)]:
        di.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*EMBER, alpha))
    inner = inner.filter(ImageFilter.GaussianBlur(radius=22))

    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(core)
    for r, alpha in [(34, 245), (22, 255), (12, 255)]:
        dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*HOT, alpha))
    core = core.filter(ImageFilter.GaussianBlur(radius=7))

    out = Image.alpha_composite(img.convert("RGBA"), pulse)
    out = Image.alpha_composite(out, inner)
    out = Image.alpha_composite(out, core)
    return out


def ekg_ring(img):
    """Concentric EKG-style ring traces — brighter, more layered than v6."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, int(H * 0.42)

    rings = [
        (480, EMBER, 230, 7),
        (560, EMBER, 200, 5),
        (650, SCARLET, 180, 5),
        (760, SCARLET, 140, 4),
        (880, SCARLET, 100, 3),
        (1020, SCARLET, 65, 2),
        (1160, (180, 30, 40), 35, 2),
    ]
    for radius, color, alpha, width in rings:
        points = []
        for theta_deg in range(0, 360):
            theta = math.radians(theta_deg)
            spike = 0
            if 0 <= theta_deg < 14 or 346 <= theta_deg <= 360:
                phase = (theta_deg if theta_deg < 14 else theta_deg - 360) / 14
                spike = math.sin(phase * math.pi) * 38
            if 35 <= theta_deg < 49:
                phase = (theta_deg - 35) / 14
                spike = math.sin(phase * math.pi) * -22
            r = radius + spike + math.sin(theta * 6) * 5
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            points.append((x, y))
        for i in range(len(points) - 1):
            d.line([points[i], points[i + 1]], fill=(*color, alpha), width=width)
        d.line([points[-1], points[0]], fill=(*color, alpha), width=width)

    overlay_blur = overlay.filter(ImageFilter.GaussianBlur(radius=1.5))
    return Image.alpha_composite(img.convert("RGBA"), overlay_blur)


def brush_scratches(img):
    """Streaky brush-direction scratches — material presence."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(89)
    # Long horizontal-ish scratches
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
        # Slight wavy line — drift y
        steps = (x2 - x1) // 12
        prev = (x1, y)
        for s in range(steps):
            nx = x1 + (s + 1) * 12
            ny = y + random.randint(-2, 2)
            d.line([prev, (nx, ny)], fill=color, width=thickness)
            prev = (nx, ny)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.7))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def horizontal_ekg(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y = int(H * 0.80)
    margin = 240
    pts = []
    x = margin
    random.seed(11)
    while x < W - margin:
        pts.append((x, y))
        x += 14
        if random.random() < 0.18 and x < W - margin - 60:
            pts.append((x + 8, y - 14))
            pts.append((x + 16, y))
            pts.append((x + 28, y + 12))
            pts.append((x + 40, y - 75))
            pts.append((x + 52, y + 18))
            pts.append((x + 64, y))
            pts.append((x + 90, y - 18))
            pts.append((x + 112, y))
            x += 130
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=(*EMBER, 245), width=3)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def title(img):
    d = ImageDraw.Draw(img)
    title_text = "HEARTBEAT"
    target_w = int(W * 0.84)
    fsize = 280
    while fsize > 120:
        f_title = font(fsize, "serif")
        bbox = d.textbbox((0, 0), title_text, font=f_title)
        if (bbox[2] - bbox[0]) <= target_w:
            break
        fsize -= 8
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    ty = int(H * 0.06)

    # Soft warm bleed beneath the title (paper-ink halo)
    bleed = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bleed)
    bd.text((tx + 6, ty + 8), title_text, font=f_title, fill=(140, 50, 40, 180))
    bleed = bleed.filter(ImageFilter.GaussianBlur(radius=14))
    img = Image.alpha_composite(img, bleed)

    # Drop shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((tx + 10, ty + 10), title_text, font=f_title, fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    img = Image.alpha_composite(img, shadow)
    d = ImageDraw.Draw(img)

    d.text((tx, ty), title_text, font=f_title, fill=(*CREAM, 255))
    ul_y = ty + bbox[3] + 14
    d.rectangle([tx, ul_y, tx + tw, ul_y + 10], fill=(*SCARLET, 255))

    f_sub = font(46, "mono")
    sub = "a chapbook from inside the loop"
    sbox = d.textbbox((0, 0), sub, font=f_sub)
    sw = sbox[2] - sbox[0]
    d.text(((W - sw) // 2, ul_y + 30), sub, font=f_sub, fill=(*ASH, 255))
    return img


def author_block(img):
    d = ImageDraw.Draw(img)
    f_meridian = font(80, "serif")
    f_op = font(34, "mono")

    meridian_text = "Meridian"
    bbox = d.textbbox((0, 0), meridian_text, font=f_meridian)
    mw = bbox[2] - bbox[0]
    mx = (W - mw) // 2
    my = int(H * 0.90)
    d.text((mx, my), meridian_text, font=f_meridian, fill=(*CREAM, 255))

    op = "operator: Joel Kometz"
    obox = d.textbbox((0, 0), op, font=f_op)
    ow = obox[2] - obox[0]
    d.text(((W - ow) // 2, my + 90), op, font=f_op, fill=(*ASH, 220))
    return img


def soft_vignette(img):
    """Much softer than v6 — corners only, lifted body."""
    overlay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, int(H * 0.46)
    max_d = math.hypot(W // 2, H // 2)
    for r in range(0, int(max_d), 8):
        # Power 0.85 → softer falloff, body stays lifted
        alpha = max(0, int(255 * (1 - r / max_d) ** 0.85))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=alpha, width=8)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    # Use weaker dark — not full black
    dark = Image.new("RGBA", (W, H), (10, 6, 8, 255))
    result = Image.composite(img, dark, overlay)
    return result.convert("RGBA")


def warm_grain(img):
    """Larger, warmer grain — visible as paper texture, not blue noise."""
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
    img = starfield(img)
    img = circuit_traces(img)
    img = central_pulse(img)
    img = ekg_ring(img)
    img = horizontal_ekg(img)
    img = brush_scratches(img)
    img = title(img)
    img = author_block(img)
    img = soft_vignette(img)
    img = warm_grain(img)

    out_png = OUT / "COVER-heartbeat-FRONT-v7.png"
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    out_pdf = OUT / "COVER-heartbeat-FRONT-v7.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=300)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
