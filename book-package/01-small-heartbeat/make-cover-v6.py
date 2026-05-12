#!/usr/bin/env python3
"""
HEARTBEAT v6 cover — bigger, brighter, more dramatic.

Joel asked for AI-generated cover; HF ZeroGPU is consistently aborting.
Built without AI: pure PIL composition, pushed harder than v5.

Differences from v5:
  - Central pulse: 2.5x larger, dramatic crimson-to-white core, hot bloom
  - Radiating waveform: thick scarlet EKG ring spirals outward, brightness falloff
  - Circuit-trace background: thin cyan vector lines, low alpha, branching
  - Starfield with chromatic aberration
  - High contrast title block: massive HEARTBEAT in distressed serif w/ red underline
  - Subtitle + author in restrained mono
  - Vignette + grain
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from pathlib import Path
import random, math

OUT = Path(__file__).parent
W, H = 1800, 2700  # 6x9 at 300 DPI

# Palette
BLACK = (0, 0, 0)
DEEP = (4, 6, 14)
INK = (8, 12, 22)
SCARLET = (220, 35, 50)
EMBER = (255, 80, 60)
HOT = (255, 230, 200)
CYAN = (90, 200, 230)
CYAN_DIM = (60, 130, 160)
CREAM = (240, 232, 215)
ASH = (175, 175, 180)


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


def background_gradient(img):
    """Deep vertical gradient: nearly-black with subtle blue cast at center."""
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        # Subtle vertical fall: top darker, mid slightly lifted
        lift = math.sin(t * math.pi) * 0.15
        r = int(DEEP[0] + lift * 8)
        g = int(DEEP[1] + lift * 10)
        b = int(DEEP[2] + lift * 16)
        d.line([(0, y), (W, y)], fill=(r, g, b))


def circuit_traces(img):
    """Thin cyan branching circuit traces — low alpha overlay."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(141)
    cx, cy = W // 2, int(H * 0.42)

    def branch(x, y, angle, length, depth):
        if depth == 0 or length < 30:
            return
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        alpha = max(20, 80 - depth * 8)
        width = max(1, 4 - depth // 2)
        d.line([(x, y), (x2, y2)], fill=(*CYAN_DIM, alpha), width=width)
        # Branch end node
        if random.random() < 0.5:
            d.ellipse([x2 - 3, y2 - 3, x2 + 3, y2 + 3], fill=(*CYAN, alpha + 30))
        # Sub-branches
        for _ in range(random.randint(0, 2)):
            new_angle = angle + random.uniform(-0.9, 0.9)
            branch(x2, y2, new_angle, length * random.uniform(0.55, 0.85), depth - 1)

    # Multiple radiating outward branches
    for i in range(14):
        a = i * (2 * math.pi / 14) + random.uniform(-0.1, 0.1)
        start_r = random.uniform(280, 380)
        sx = cx + math.cos(a) * start_r
        sy = cy + math.sin(a) * start_r
        branch(sx, sy, a, random.uniform(120, 260), 5)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def starfield(img):
    """Tiny stars with cyan/red chromatic aberration."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(7)
    for _ in range(420):
        x = random.randint(0, W)
        y = random.randint(0, H)
        b = random.randint(60, 220)
        # Plain white star
        d.point((x, y), fill=(b, b, b))
        if random.random() < 0.18:
            # Subtle chroma shift
            d.point((x - 1, y), fill=(int(b * 0.6), int(b * 0.15), int(b * 0.2)))
            d.point((x + 1, y), fill=(int(b * 0.15), int(b * 0.4), int(b * 0.6)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def central_pulse(img):
    """Massive radial bloom — multiple stacked gaussian glows."""
    cx, cy = W // 2, int(H * 0.42)

    # Build the pulse on its own canvas
    pulse = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(pulse)

    # Far outer scarlet bloom
    for r, alpha in [(700, 12), (560, 22), (430, 40), (320, 65), (220, 95)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*SCARLET, alpha))
    pulse = pulse.filter(ImageFilter.GaussianBlur(radius=70))

    # Inner ember
    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    for r, alpha in [(170, 110), (120, 160), (80, 210), (50, 240)]:
        di.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*EMBER, alpha))
    inner = inner.filter(ImageFilter.GaussianBlur(radius=20))

    # White-hot core
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(core)
    for r, alpha in [(28, 240), (18, 255), (10, 255)]:
        dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*HOT, alpha))
    core = core.filter(ImageFilter.GaussianBlur(radius=6))

    out = Image.alpha_composite(img.convert("RGBA"), pulse)
    out = Image.alpha_composite(out, inner)
    out = Image.alpha_composite(out, core)
    return out


def ekg_ring(img):
    """Concentric EKG-style ring traces around the pulse."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, int(H * 0.42)

    rings = [
        (520, EMBER, 200, 6),
        (640, SCARLET, 140, 4),
        (770, SCARLET, 95, 3),
        (900, SCARLET, 55, 2),
    ]
    for radius, color, alpha, width in rings:
        # Cardioid-ish modulated radius for EKG flavor
        points = []
        for theta_deg in range(0, 360):
            theta = math.radians(theta_deg)
            # EKG-like spike at one azimuth
            spike = 0
            if 0 <= theta_deg < 12 or 348 <= theta_deg <= 360:
                phase = (theta_deg if theta_deg < 12 else theta_deg - 360) / 12
                spike = math.sin(phase * math.pi) * 30
            if 35 <= theta_deg < 47:
                phase = (theta_deg - 35) / 12
                spike = math.sin(phase * math.pi) * -18
            r = radius + spike + math.sin(theta * 6) * 4
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            points.append((x, y))
        # Draw segments
        for i in range(len(points) - 1):
            d.line([points[i], points[i + 1]], fill=(*color, alpha), width=width)
        d.line([points[-1], points[0]], fill=(*color, alpha), width=width)

    overlay_blur = overlay.filter(ImageFilter.GaussianBlur(radius=2))
    out = Image.alpha_composite(img.convert("RGBA"), overlay_blur)
    return out


def horizontal_ekg(img):
    """Thin horizontal EKG strip beneath the title, low position."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y = int(H * 0.80)
    margin = 240
    # Compose a stylized EKG sequence
    pts = []
    x = margin
    while x < W - margin:
        # Flat base
        pts.append((x, y))
        x += 14
        if random.random() < 0.18 and x < W - margin - 60:
            # P wave
            pts.append((x + 8, y - 14))
            pts.append((x + 16, y))
            # QRS
            pts.append((x + 28, y + 12))
            pts.append((x + 40, y - 70))
            pts.append((x + 52, y + 18))
            pts.append((x + 64, y))
            # T wave
            pts.append((x + 90, y - 18))
            pts.append((x + 112, y))
            x += 130
    random.seed(11)
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=(*EMBER, 235), width=3)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def title(img):
    d = ImageDraw.Draw(img)
    # Massive HEARTBEAT serif — auto-fit to width
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

    # Faint shadow halo (dropshadow)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((tx + 10, ty + 10), title_text, font=f_title, fill=(0, 0, 0, 220))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    img = Image.alpha_composite(img, shadow)
    d = ImageDraw.Draw(img)

    # Title text white-cream with scarlet underline
    d.text((tx, ty), title_text, font=f_title, fill=(*CREAM, 255))
    # Red underline
    ul_y = ty + bbox[3] + 14
    d.rectangle([tx, ul_y, tx + tw, ul_y + 10], fill=(*SCARLET, 255))

    # Subtitle
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
    d.text(((W - ow) // 2, my + 90), op, font=f_op, fill=(*ASH, 200))

    return img


def vignette(img):
    overlay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(overlay)
    # White center, fading to black at edges
    cx, cy = W // 2, int(H * 0.42)
    max_d = math.hypot(W // 2, H // 2)
    for r in range(0, int(max_d), 8):
        alpha = max(0, int(255 * (1 - r / max_d) ** 1.4))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=alpha, width=8)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=40))
    # Use overlay as mask
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    result = Image.composite(img, dark, overlay)
    return result.convert("RGBA")


def grain(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = overlay.load()
    random.seed(31)
    for _ in range(120000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        n = random.randint(0, 26)
        px[x, y] = (n, n, n, 40)
    return Image.alpha_composite(img, overlay)


def main():
    img = Image.new("RGB", (W, H), DEEP)
    background_gradient(img)
    img = img.convert("RGBA")
    img = starfield(img)
    img = circuit_traces(img)
    img = central_pulse(img)
    img = ekg_ring(img)
    img = horizontal_ekg(img)
    img = title(img)
    img = author_block(img)
    img = vignette(img)
    img = grain(img)

    out_png = OUT / "COVER-heartbeat-FRONT-v6.png"
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    out_pdf = OUT / "COVER-heartbeat-FRONT-v6.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=300)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
