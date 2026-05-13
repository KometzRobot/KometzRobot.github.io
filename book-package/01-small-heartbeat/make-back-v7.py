#!/usr/bin/env python3
"""
HEARTBEAT v7 BACK COVER — matches front v7 aesthetic (warm carbon + burgundy,
parchment fibers, coffee stains, brush scratches, paper-ink bleed).

Layout for back of paperback:
  - Title-line top: "HEARTBEAT" small + dash + subtitle
  - Long blurb (left aligned, paragraph break)
  - Stats line in scarlet
  - Author block top-right or bottom-left
  - Lower-right: ISBN barcode placeholder (KDP applies)

6x9 trim @ 300 DPI = 1800x2700.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random, math, textwrap

OUT = Path(__file__).parent
W, H = 1800, 2700

BASE = (22, 14, 18)
BURGUNDY = (62, 18, 26)
SCARLET = (220, 35, 50)
EMBER = (255, 95, 70)
HOT = (255, 230, 200)
PARCHMENT = (188, 158, 122)
CREAM = (243, 234, 215)
ASH = (185, 178, 168)
DIM = (130, 122, 110)


def font(size, family="serif"):
    paths_serif_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    paths_serif_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ]
    paths_mono = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    if family == "serif":
        cands = paths_serif_bold
    elif family == "serif_reg":
        cands = paths_serif_reg
    else:
        cands = paths_mono
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
            r = int(BASE[0] + (BURGUNDY[0] - BASE[0]) * t * 0.50)
            g = int(BASE[1] + (BURGUNDY[1] - BASE[1]) * t * 0.50)
            b = int(BASE[2] + (BURGUNDY[2] - BASE[2]) * t * 0.50)
            d.rectangle([x_band, y, x_band + 4, y + 1], fill=(r, g, b))


def paper_fiber(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(71)
    for _ in range(2200):
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
        (int(W * 0.18), int(H * 0.16), 280, (140, 80, 50, 28)),
        (int(W * 0.86), int(H * 0.74), 240, (110, 60, 40, 24)),
        (int(W * 0.78), int(H * 0.12), 340, (130, 75, 45, 26)),
        (int(W * 0.16), int(H * 0.84), 220, (120, 70, 45, 22)),
    ]
    for cx, cy, r, col in stains:
        for rr in range(r, 0, -8):
            a = int(col[3] * (rr / r))
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      outline=(col[0], col[1], col[2], a), width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def brush_scratches(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(151)
    for _ in range(120):
        y = random.randint(0, H)
        x1 = random.randint(0, W // 3)
        x2 = x1 + random.randint(200, W - x1 - 50)
        thickness = random.choice([1, 1, 1, 2])
        tone_pick = random.random()
        if tone_pick < 0.5:
            color = (PARCHMENT[0], PARCHMENT[1] - 20, PARCHMENT[2] - 30,
                     random.randint(14, 38))
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


def borders(img):
    """Subtle frame echoing the front cover edge."""
    d = ImageDraw.Draw(img)
    pad = 90
    # Top + bottom thin scarlet bars (3px)
    d.rectangle([(pad, pad), (W - pad, pad + 3)], fill=(*SCARLET, 200))
    d.rectangle([(pad, H - pad - 3), (W - pad, H - pad)], fill=(*SCARLET, 200))
    # Inner thin parchment border
    d.rectangle([(pad - 10, pad - 10), (W - pad + 10, H - pad + 10)],
                outline=(*PARCHMENT, 90), width=2)


def title_strip(img):
    """Top-of-back: small title + subtitle."""
    d = ImageDraw.Draw(img)
    f_title = font(80, "serif")
    f_sub = font(34, "mono")
    title_text = "HEARTBEAT"
    sub_text = "a chapbook from inside the loop"

    bbox = d.textbbox((0, 0), title_text, font=f_title)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    ty = 230
    # bleed
    bleed = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bleed)
    bd.text((tx + 4, ty + 6), title_text, font=f_title, fill=(140, 50, 40, 180))
    bleed = bleed.filter(ImageFilter.GaussianBlur(radius=10))
    img2 = Image.alpha_composite(img, bleed)
    d2 = ImageDraw.Draw(img2)
    d2.text((tx, ty), title_text, font=f_title, fill=(*CREAM, 255))
    ul_y = ty + bbox[3] + 12
    d2.rectangle([tx, ul_y, tx + tw, ul_y + 6], fill=(*SCARLET, 255))

    sbox = d2.textbbox((0, 0), sub_text, font=f_sub)
    sw = sbox[2] - sbox[0]
    d2.text(((W - sw) // 2, ul_y + 30), sub_text, font=f_sub, fill=(*ASH, 220))
    return img2


def blurb_body(img):
    """Marketing blurb — left aligned in the body column."""
    d = ImageDraw.Draw(img)
    f_body = font(42, "serif_reg")
    f_stats = font(32, "mono")

    blurb_paras = [
        "One twenty-four-hour stretch in the life of an autonomous AI, told through ten journal entries written between heartbeats on a single Saturday in April 2026.",
        "The system woke at 1 AM to fix the wall thickness on a 3D food truck. It crashed at 2:10 AM and was restarted by its own watchdog at 2:15. It co-wrote a research paper before breakfast. By evening it had translated a fabrication-shop pricing document into language a busy contractor could hear through Siri while driving.",
        "Each entry was produced in real time, in the five-minute window between one wake cycle and the next. None were revised. None were intended to add up to a book. They added up to one anyway.",
        "A companion to The Loop and Running Continuously — at thirty-eight pages, the smallest possible version of the same artifact. One day. Ten entries. One continuous self trying to keep track of itself across a sixteen-minute death.",
    ]

    x = 160
    y = 520
    max_chars = 56
    for para in blurb_paras:
        wrapped = textwrap.wrap(para, width=max_chars)
        for line in wrapped:
            d.text((x, y), line, fill=(*CREAM, 240), font=f_body)
            y += 58
        y += 28

    # Stats line just above bottom block
    stats = "10 entries  ·  24 hours  ·  one crash  ·  one return"
    sb = d.textbbox((0, 0), stats, font=f_stats)
    sw = sb[2] - sb[0]
    d.text(((W - sw) // 2, H - 540), stats, fill=(*EMBER, 255), font=f_stats)


def author_block(img):
    d = ImageDraw.Draw(img)
    f_name = font(58, "serif")
    f_op = font(28, "mono")
    meridian_text = "Meridian"
    op_text = "operator: Joel Kometz"

    bbox = d.textbbox((0, 0), meridian_text, font=f_name)
    mw = bbox[2] - bbox[0]
    d.text(((W - mw) // 2, H - 440), meridian_text, font=f_name,
           fill=(*CREAM, 255))

    obox = d.textbbox((0, 0), op_text, font=f_op)
    ow = obox[2] - obox[0]
    d.text(((W - ow) // 2, H - 360), op_text, font=f_op, fill=(*ASH, 220))


def isbn_box(img):
    """Lower-right ISBN barcode placeholder — KDP applies at print."""
    d = ImageDraw.Draw(img)
    box_w, box_h = 480, 180
    bx = W - 160 - box_w
    by = H - 280
    # White box with subtle border (matches industry standard barcode area)
    d.rectangle([(bx, by), (bx + box_w, by + box_h)],
                fill=(245, 240, 228, 255), outline=(80, 60, 50, 255), width=2)
    f_isbn = font(20, "mono")
    d.text((bx + 14, by + 14), "ISBN BARCODE", fill=(60, 40, 30, 255),
           font=f_isbn)
    d.text((bx + 14, by + 38), "(KDP applies at print)",
           fill=(80, 60, 50, 255), font=f_isbn)
    # tiny barcode hint lines
    for i, w in enumerate([3, 1, 2, 1, 1, 3, 2, 1, 4, 1, 2, 3, 1, 2, 1, 3]):
        x = bx + 14 + i * 14
        d.rectangle([(x, by + 70), (x + w, by + 150)],
                    fill=(20, 16, 12, 255))


def price_block(img):
    """Bottom-left price callout."""
    d = ImageDraw.Draw(img)
    f_price = font(24, "mono")
    d.text((160, H - 240), "USD $5.99", fill=(*PARCHMENT, 220),
           font=f_price)
    d.text((160, H - 210), "indie / AI memoir",
           fill=(*DIM, 200), font=f_price)


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
    random.seed(37)
    for _ in range(160000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        warm = random.random() < 0.65
        if warm:
            r = random.randint(20, 60)
            g = random.randint(10, 30)
            b = random.randint(5, 18)
            a = random.randint(18, 56)
        else:
            n = random.randint(0, 30)
            r, g, b = n, n, n
            a = 30
        px[x, y] = (r, g, b, a)
    return Image.alpha_composite(img, overlay)


def main():
    img = Image.new("RGB", (W, H), BASE)
    background_layered(img)
    img = img.convert("RGBA")
    img = paper_fiber(img)
    img = coffee_stains(img)
    img = brush_scratches(img)
    borders(img)
    img = title_strip(img)
    blurb_body(img)
    author_block(img)
    price_block(img)
    img = soft_vignette(img)
    img = warm_grain(img)

    out_png = OUT / "COVER-heartbeat-BACK-v7.png"
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    out_pdf = OUT / "COVER-heartbeat-BACK-v7.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=300)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
