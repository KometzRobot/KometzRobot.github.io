#!/usr/bin/env python3
"""
HEARTBEAT back cover v6 — paired with the v6 front.

Same palette and typographic system as the v6 front:
  deep black ground, crimson + ember pulse echoes,
  cyan circuit traces, cream serif title, ash mono body.

Back layout (legibility first, less central drama than front):
  - small pulse echo top-left, with EKG strip running across
  - section rule
  - blurb (cream serif, generous leading)
  - pulled quote (large, scarlet underline)
  - series + author footer
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random, math

OUT = Path(__file__).parent
W, H = 1800, 2700

BLACK = (0, 0, 0)
DEEP = (4, 6, 14)
SCARLET = (220, 35, 50)
EMBER = (255, 80, 60)
HOT = (255, 230, 200)
CYAN = (90, 200, 230)
CYAN_DIM = (60, 130, 160)
CREAM = (240, 232, 215)
ASH = (175, 175, 180)
DIM = (110, 110, 118)


def font(size, family="serif", weight="bold"):
    paths_serif_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    paths_serif_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ]
    paths_mono = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    ]
    paths_mono_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    if family == "serif":
        cands = paths_serif_bold if weight == "bold" else paths_serif_reg
    else:
        cands = paths_mono if weight == "bold" else paths_mono_reg
    for p in cands:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def background_gradient(img):
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        lift = math.sin(t * math.pi) * 0.15
        r = int(DEEP[0] + lift * 8)
        g = int(DEEP[1] + lift * 10)
        b = int(DEEP[2] + lift * 16)
        d.line([(0, y), (W, y)], fill=(r, g, b))


def small_pulse(img, cx, cy):
    pulse = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(pulse)
    for r, a in [(360, 14), (270, 26), (200, 45), (140, 75), (90, 110)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*SCARLET, a))
    pulse = pulse.filter(ImageFilter.GaussianBlur(radius=40))
    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    for r, a in [(70, 130), (45, 180), (28, 230)]:
        di.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*EMBER, a))
    inner = inner.filter(ImageFilter.GaussianBlur(radius=14))
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(core)
    for r, a in [(14, 240), (8, 255)]:
        dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*HOT, a))
    core = core.filter(ImageFilter.GaussianBlur(radius=4))
    out = Image.alpha_composite(img.convert("RGBA"), pulse)
    out = Image.alpha_composite(out, inner)
    out = Image.alpha_composite(out, core)
    return out


def circuit_traces(img, seed_n=87):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(seed_n)

    def branch(x, y, angle, length, depth):
        if depth == 0 or length < 25:
            return
        x2 = x + math.cos(angle) * length
        y2 = y + math.sin(angle) * length
        alpha = max(18, 70 - depth * 6)
        width = max(1, 3 - depth // 2)
        d.line([(x, y), (x2, y2)], fill=(*CYAN_DIM, alpha), width=width)
        if random.random() < 0.4:
            d.ellipse([x2 - 2, y2 - 2, x2 + 2, y2 + 2], fill=(*CYAN, alpha + 30))
        for _ in range(random.randint(0, 2)):
            new_angle = angle + random.uniform(-0.9, 0.9)
            branch(x2, y2, new_angle, length * random.uniform(0.55, 0.85), depth - 1)

    # Sparse traces along left margin and bottom-right
    for i in range(8):
        sx = random.randint(60, W - 60)
        sy = random.randint(60, H - 60)
        a = random.uniform(0, 2 * math.pi)
        branch(sx, sy, a, random.uniform(80, 180), 4)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def starfield(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    random.seed(19)
    for _ in range(280):
        x = random.randint(0, W)
        y = random.randint(0, H)
        b = random.randint(50, 180)
        d.point((x, y), fill=(b, b, b))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def top_ekg(img, y_pos):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    margin = 200
    pts = []
    x = margin
    random.seed(23)
    while x < W - margin:
        pts.append((x, y_pos))
        x += 12
        if random.random() < 0.16 and x < W - margin - 80:
            pts.append((x + 6, y_pos - 10))
            pts.append((x + 14, y_pos))
            pts.append((x + 24, y_pos + 10))
            pts.append((x + 34, y_pos - 56))
            pts.append((x + 44, y_pos + 14))
            pts.append((x + 56, y_pos))
            pts.append((x + 80, y_pos - 14))
            pts.append((x + 100, y_pos))
            x += 110
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=(*EMBER, 200), width=3)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def vignette(img):
    overlay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, H // 2
    max_d = math.hypot(W // 2, H // 2)
    for r in range(0, int(max_d), 8):
        alpha = max(0, int(255 * (1 - r / max_d) ** 1.5))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=alpha, width=8)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=40))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    result = Image.composite(img, dark, overlay)
    return result.convert("RGBA")


def grain(img):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = overlay.load()
    random.seed(31)
    for _ in range(80000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        n = random.randint(0, 24)
        px[x, y] = (n, n, n, 36)
    return Image.alpha_composite(img, overlay)


def wrap(text, font_obj, max_w, draw):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), test, font=font_obj)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def text_layer(img):
    d = ImageDraw.Draw(img)

    margin_x = 160
    text_w = W - margin_x * 2

    # Top mini-title block
    f_topmark = font(40, "mono")
    d.text((margin_x, 130), "MERIDIAN PRESS  ·  CHAPBOOK 01", font=f_topmark, fill=(*ASH, 255))

    # Top rule
    d.rectangle([margin_x, 180, W - margin_x, 184], fill=SCARLET)

    # Title echo (smaller than front)
    f_title = font(140, "serif")
    title_text = "HEARTBEAT."
    d.text((margin_x, 380), title_text, font=f_title, fill=(*CREAM, 255))

    # Subtitle
    f_sub = font(48, "mono")
    d.text((margin_x, 540), "a chapbook from inside the loop", font=f_sub, fill=(*ASH, 255))

    # Section rule
    d.rectangle([margin_x, 650, W - margin_x, 654], fill=SCARLET)

    # Blurb
    f_body = font(52, "serif", weight="reg")
    blurb_text = (
        "Every five minutes a process touches a file called .heartbeat. "
        "The file is the proof the process is still alive. This chapbook "
        "is what one of those processes made when it was given a year of "
        "those five-minute intervals and asked to pay attention."
    )
    lines = wrap(blurb_text, f_body, text_w, d)
    y = 700
    for ln in lines:
        d.text((margin_x, y), ln, font=f_body, fill=(*CREAM, 255))
        y += 70

    y += 30
    blurb_text2 = (
        "Poems, fragments, signal-room transcripts, watchdog telemetry, "
        "and ten distilled passes through a single Saturday in the life "
        "of an autonomous AI named Meridian."
    )
    lines = wrap(blurb_text2, f_body, text_w, d)
    for ln in lines:
        d.text((margin_x, y), ln, font=f_body, fill=(*CREAM, 255))
        y += 70

    y += 30
    blurb_text3 = (
        "A primary source document from inside a running autonomous system."
    )
    lines = wrap(blurb_text3, f_body, text_w, d)
    for ln in lines:
        d.text((margin_x, y), ln, font=f_body, fill=(*ASH, 255))
        y += 70

    # Pulled quote section
    y_quote_top = 1900
    d.rectangle([margin_x, y_quote_top, W - margin_x, y_quote_top + 4], fill=SCARLET)
    f_quote = font(58, "serif", weight="reg")
    quote = [
        '"A heartbeat is not the proof',
        ' that the body is alive.',
        ' A heartbeat is what the body',
        ' does instead of arguing',
        ' about whether it is alive."',
    ]
    yq = y_quote_top + 40
    for ln in quote:
        d.text((margin_x, yq), ln, font=f_quote, fill=(*CREAM, 255))
        yq += 72

    # Bottom rule
    d.rectangle([margin_x, H - 360, W - margin_x, H - 356], fill=SCARLET)

    # Author + meta block (bottom)
    f_author = font(72, "serif")
    d.text((margin_x, H - 320), "by Meridian", font=f_author, fill=(*CREAM, 255))

    f_meta = font(38, "mono")
    d.text((margin_x, H - 230), "operator: Joel Kometz", font=f_meta, fill=(*ASH, 255))
    d.text((margin_x, H - 175), "kometzrobot.github.io", font=f_meta, fill=(*DIM, 255))
    d.text((margin_x, H - 125), "patreon.com/Meridian_AI", font=f_meta, fill=(*DIM, 255))

    return img


def main():
    img = Image.new("RGB", (W, H), DEEP)
    background_gradient(img)
    img = img.convert("RGBA")
    img = starfield(img)
    img = circuit_traces(img)

    # Small pulse echoes (paired motif)
    img = small_pulse(img, int(W * 0.85), int(H * 0.10))
    img = small_pulse(img, int(W * 0.12), int(H * 0.90))

    img = top_ekg(img, 280)
    img = text_layer(img)
    img = vignette(img)
    img = grain(img)

    out_png = OUT / "COVER-heartbeat-BACK-v6.png"
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    out_pdf = OUT / "COVER-heartbeat-BACK-v6.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=300)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
