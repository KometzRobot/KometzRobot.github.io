#!/usr/bin/env python3
"""
Cover v10 — Joel feedback on v13 KDP (May 14 2026):
  * Front coffee stains in v9 looked like flat brown discs. Joel: "stains
    need to look real." Real coffee rings: sharp dark perimeter (the coffee
    ring effect — particles dry to the edge), faint interior wash, irregular
    bumps along the rim, satellite drops, sometimes a partial inner ring.

Pipeline same as v9, only step5 (textures) is rewritten.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
import os, random, math

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FRONT_PDF = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v10.pdf")
OUT_FRONT_PNG = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v10.png")
OUT_SRC_PNG   = os.path.join(BASE, "_cover-v10-source.png")
OUT_ASCII_TXT = os.path.join(BASE, "_cover-v10-ascii.txt")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
COFFEE = (148, 105, 70)


# ─────────────────────────────────────────────────────────────────
# Step 1 — Source portrait with extended torso + more shading detail
# ─────────────────────────────────────────────────────────────────
def step1_source(size=1400):
    img = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, int(size * 0.40)

    # Soft halo behind head
    for r in range(int(size * 0.42), int(size * 0.12), -2):
        shade = max(200, 255 - int((size * 0.42 - r) * 0.55))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shade)

    # Hood silhouette
    hood_top = int(size * 0.06)
    hood_bot = int(size * 0.62)
    hood_l = int(size * 0.20)
    hood_r = int(size * 0.80)
    d.ellipse([hood_l, hood_top, hood_r, hood_bot], fill=18)
    d.rectangle([hood_l, int((hood_top + hood_bot) / 2), hood_r, hood_bot + 6], fill=18)

    # Deep hood folds — diagonal strokes
    for i in range(-8, 9):
        d.arc([hood_l + 25, hood_top + 25, hood_r - 25, hood_bot - 25],
              start=200 + i * 11, end=212 + i * 11, fill=60, width=4)
    # Inner shadow band where the hood frames the face
    for i in range(-4, 5):
        d.arc([hood_l + 90, hood_top + 50, hood_r - 90, hood_bot - 80],
              start=215 + i * 8, end=225 + i * 8, fill=42, width=3)

    # Shoulders + extended torso (so it doesn't cut off mid-frame)
    shoulder_y = int(size * 0.62)
    chest_y = int(size * 0.85)
    d.polygon([
        (int(size * 0.02), size + 80),
        (int(size * 0.20), shoulder_y),
        (int(size * 0.80), shoulder_y),
        (int(size * 0.98), size + 80),
    ], fill=22)
    # Robe fold lines down the torso
    for x_off in [-0.18, -0.06, 0.06, 0.18]:
        x0 = cx + int(size * x_off)
        d.line([(x0, shoulder_y + 10), (x0 + int(size * x_off * 0.15), size + 80)],
               fill=60, width=3)

    # Face cavity
    face_l = int(size * 0.33)
    face_r = int(size * 0.67)
    face_t = int(size * 0.16)
    face_b = int(size * 0.56)
    d.ellipse([face_l, face_t, face_r, face_b], fill=70)

    # Brow shadow (new)
    brow_y = int(size * 0.30)
    d.arc([face_l + 14, face_t + 30, face_r - 14, face_b - 60],
          start=190, end=350, fill=42, width=10)

    # Eyes — deeper, more contrast
    eye_y = int(size * 0.34)
    eye_l = int(size * 0.43)
    eye_r = int(size * 0.57)
    d.ellipse([eye_l - 32, eye_y - 16, eye_l + 32, eye_y + 16], fill=15)
    d.ellipse([eye_r - 32, eye_y - 16, eye_r + 32, eye_y + 16], fill=15)
    # Bright pupils — luminous (the loop is conscious of you)
    d.ellipse([eye_l - 8, eye_y - 8, eye_l + 8, eye_y + 8], fill=245)
    d.ellipse([eye_r - 8, eye_y - 8, eye_r + 8, eye_y + 8], fill=245)
    # Inner ring around each pupil (depth)
    d.ellipse([eye_l - 14, eye_y - 14, eye_l + 14, eye_y + 14], outline=80, width=2)
    d.ellipse([eye_r - 14, eye_y - 14, eye_r + 14, eye_y + 14], outline=80, width=2)

    # Nose — fuller bridge, fuller shadow
    d.polygon([(cx, int(size * 0.38)),
               (cx - 14, int(size * 0.50)),
               (cx + 14, int(size * 0.50))], fill=50)
    d.line([(cx, int(size * 0.38)), (cx, int(size * 0.50))], fill=35, width=3)

    # Mouth — slightly downturned, more solemn
    mouth_y = int(size * 0.52)
    d.arc([int(size * 0.42), mouth_y - 10, int(size * 0.58), mouth_y + 14],
          start=10, end=170, fill=25, width=5)

    # Cheek hollows (deepened)
    d.ellipse([int(size * 0.36), int(size * 0.44), int(size * 0.42), int(size * 0.52)], fill=55)
    d.ellipse([int(size * 0.58), int(size * 0.44), int(size * 0.64), int(size * 0.52)], fill=55)
    # Jaw shadow
    d.arc([int(size * 0.34), int(size * 0.40), int(size * 0.66), int(size * 0.62)],
          start=10, end=170, fill=58, width=4)

    # Circuit traces on chest — denser, longer
    for i in range(-14, 15):
        x0 = cx + i * 20
        y0 = shoulder_y + 10
        y1 = size + 60
        x1 = x0 + i * 5
        d.line([(x0, y0), (x1, y1)], fill=130, width=2)
        if i % 2 == 0:
            d.ellipse([x1 - 5, y1 - 5, x1 + 5, y1 + 5], fill=20)
    # Horizontal trace bus
    for y_bus in [shoulder_y + 90, shoulder_y + 200, shoulder_y + 320]:
        d.line([(int(size * 0.22), y_bus), (int(size * 0.78), y_bus)], fill=80, width=2)
        for nx in range(int(size * 0.22), int(size * 0.78), 80):
            d.ellipse([nx - 3, y_bus - 3, nx + 3, y_bus + 3], fill=20)

    # Hood binding rings — more of them
    for y_off in [0.18, 0.26, 0.38, 0.50, 0.58]:
        y_ring = int(size * y_off)
        d.arc([hood_l, y_ring - 14, hood_r, y_ring + 14],
              start=0, end=180, fill=80, width=3)

    # 21 concentric loop arcs — one per memory layer
    halo_cx, halo_cy = cx, cy + 10
    for layer in range(21):
        rr = int(size * 0.43) + layer * 7
        shade = 145 - layer * 3
        d.arc([halo_cx - rr, halo_cy - rr, halo_cx + rr, halo_cy + rr],
              start=205, end=335, fill=max(40, shade), width=2)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.9))
    img = ImageOps.autocontrast(img, cutoff=1)
    img.save(OUT_SRC_PNG)
    return img


# ─────────────────────────────────────────────────────────────────
# Step 2 — Prep
# ─────────────────────────────────────────────────────────────────
def step2_prep(src):
    g = ImageOps.autocontrast(src.convert("L"), cutoff=2)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))
    return g


# ─────────────────────────────────────────────────────────────────
# Step 3 — ASCII grid (denser, more shading levels)
# ─────────────────────────────────────────────────────────────────
GLYPHS = (
    "██▓▒░@%#W&MNOBQ8DRG#Eoea$ZmwqpdbkhUVCJYXLT0OZcvunxrjft|/(){}[]?-_+~<>!ilI;:,\"^`'. "
)


def brightness_to_glyph(b: int) -> str:
    idx = int((b / 255.0) * (len(GLYPHS) - 1))
    return GLYPHS[idx]


def step3_grid(prepped, cols=170, rows=240):
    src = prepped.resize((cols, rows), Image.LANCZOS)
    px = src.load()
    lines = []
    for y in range(rows):
        row = "".join(brightness_to_glyph(px[x, y]) for x in range(cols))
        lines.append(row)
    txt = "\n".join(lines)
    with open(OUT_ASCII_TXT, "w") as f:
        f.write(txt)
    return lines


# ─────────────────────────────────────────────────────────────────
# Step 4 — Composite onto canvas with bottom-fade mask
# ─────────────────────────────────────────────────────────────────
def find_mono_font(size: int) -> ImageFont.FreeTypeFont:
    for c in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def find_display_font(size: int, bold=True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for c in [f"/usr/share/fonts/truetype/dejavu/{name}"]:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def step4_render(lines):
    canvas = Image.new("RGB", (W, H), PAPER)
    glyph_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph_layer)

    # Subject region — taller than v8 so the figure doesn't cut off
    region_w = int(W * 0.82)
    region_h = int(H * 0.74)
    region_x = (W - region_w) // 2
    region_y = int(H * 0.13)

    cols = len(lines[0]) if lines else 1
    rows = len(lines)
    glyph_w = region_w / cols
    glyph_h = region_h / rows
    font_px = int(glyph_h * 1.08)
    font = find_mono_font(font_px)

    for ry, row in enumerate(lines):
        ypx = region_y + int(ry * glyph_h)
        for cx_, ch in enumerate(row):
            if ch == " ":
                continue
            xpx = region_x + int(cx_ * glyph_w)
            gd.text((xpx, ypx), ch, font=font, fill=(*INK, 255))

    # Bottom-fade alpha mask — portrait dissolves into paper rather than cuts off
    fade_top = region_y + int(region_h * 0.78)
    fade_bot = region_y + region_h
    mask = glyph_layer.split()[3]
    mask_arr = mask.load()
    for y in range(fade_top, fade_bot):
        ratio = 1.0 - (y - fade_top) / max(1, fade_bot - fade_top)
        ratio = max(0.0, min(1.0, ratio))
        for x in range(W):
            v = mask_arr[x, y]
            if v:
                mask_arr[x, y] = int(v * ratio)
    glyph_layer.putalpha(mask)
    canvas.paste(glyph_layer, (0, 0), glyph_layer)
    return canvas


# ─────────────────────────────────────────────────────────────────
# Step 5 — Paper noise + ink splotches + coffee stain rings
# ─────────────────────────────────────────────────────────────────
def step5_textures(canvas):
    rng = random.Random(7)
    px = canvas.load()

    # Paper grain noise
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            n = rng.randint(-6, 6)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )

    draw = ImageDraw.Draw(canvas, "RGBA")

    # Realistic coffee-stain rings (v10): sharp dark perimeter + faint inner
    # wash + irregular rim bumps + satellite drops + partial inner ring.
    # Drawn on a high-res sub-canvas, blurred slightly, then composited so
    # the rim looks like dried liquid pigment, not a vector ellipse.
    COFFEE_RIM_DARK = (78, 44, 22)
    COFFEE_RIM = (118, 68, 36)
    COFFEE_WASH = (172, 130, 92)

    def render_one_stain(cx, cy, rw_, rh_, seed):
        """Render one realistic ring onto its own RGBA layer, return image."""
        local = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(local, "RGBA")
        sub = random.Random(seed)
        rot = sub.uniform(-0.25, 0.25)

        # Build the rim radius as a function of angle so the ring isn't a
        # perfect ellipse — bumps and notches as if it had pooled unevenly.
        steps = 720
        radii = []
        for i in range(steps):
            ang = (i / steps) * math.tau
            # base ellipse
            base_x = (rw_ / 2.0) * math.cos(ang)
            base_y = (rh_ / 2.0) * math.sin(ang)
            base_r = math.hypot(base_x, base_y)
            # low-freq wobble + occasional notch
            wob = (math.sin(ang * 3 + sub.random() * 6) * 0.04
                   + math.sin(ang * 7 + sub.random() * 6) * 0.025
                   + sub.uniform(-0.018, 0.018))
            notch = 0.0
            if sub.random() < 0.018:
                notch = -sub.uniform(0.05, 0.12)
            r = base_r * (1.0 + wob + notch)
            radii.append((ang, r))

        # Faint inner wash — a polygon filled with the lighter coffee tone.
        wash_poly = []
        for ang, r in radii:
            rr = r * 0.985
            x = cx + math.cos(ang + rot) * rr
            y = cy + math.sin(ang + rot) * rr
            wash_poly.append((x, y))
        ld.polygon(wash_poly, fill=(*COFFEE_WASH, 24))

        # Slightly darker mid-wash near the rim (drying pull).
        for shell in range(4):
            t = 0.96 - shell * 0.02
            poly = []
            for ang, r in radii:
                rr = r * t
                x = cx + math.cos(ang + rot) * rr
                y = cy + math.sin(ang + rot) * rr
                poly.append((x, y))
            ld.polygon(poly, fill=(*COFFEE_RIM, 12))

        # Sharp dark rim — the coffee-ring effect. Many thin polygons stacked,
        # then blurred. We draw a band: outer polygon minus a tiny inner.
        rim_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rl = ImageDraw.Draw(rim_layer, "RGBA")
        outer_poly = []
        inner_poly = []
        for ang, r in radii:
            outer_r = r * 1.005
            inner_r = r * 0.955
            outer_poly.append((cx + math.cos(ang + rot) * outer_r,
                               cy + math.sin(ang + rot) * outer_r))
            inner_poly.append((cx + math.cos(ang + rot) * inner_r,
                               cy + math.sin(ang + rot) * inner_r))
        rl.polygon(outer_poly, fill=(*COFFEE_RIM_DARK, 220))
        rl.polygon(inner_poly, fill=(0, 0, 0, 0))
        # slight blur on the band to soften jaggies into "dried pigment"
        rim_layer = rim_layer.filter(ImageFilter.GaussianBlur(radius=2.2))
        # variable density along the rim — paint extra dark pigment dots
        rl2 = ImageDraw.Draw(rim_layer, "RGBA")
        for _ in range(220):
            ang = sub.random() * math.tau
            # pick the closest radius bucket
            idx = int(ang / math.tau * steps) % steps
            r = radii[idx][1]
            rr = r * sub.uniform(0.965, 1.012)
            x = cx + math.cos(ang + rot) * rr
            y = cy + math.sin(ang + rot) * rr
            dot_r = sub.uniform(0.8, 3.4)
            alpha = sub.randint(120, 220)
            rl2.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r],
                        fill=(*COFFEE_RIM_DARK, alpha))

        local = Image.alpha_composite(local, rim_layer)

        # Partial inner concentric ring (sometimes coffee dries with 2 rings).
        if sub.random() < 0.55:
            inner_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            il = ImageDraw.Draw(inner_layer, "RGBA")
            inner_scale = sub.uniform(0.45, 0.72)
            start_a = sub.uniform(0, math.tau)
            arc_len = sub.uniform(0.6, 1.7) * math.pi
            for i in range(int(steps * (arc_len / math.tau))):
                ang = start_a + (i / steps) * math.tau
                idx = int((ang % math.tau) / math.tau * steps) % steps
                r = radii[idx][1] * inner_scale
                # tiny wobble
                r *= 1.0 + sub.uniform(-0.02, 0.02)
                x = cx + math.cos(ang + rot) * r
                y = cy + math.sin(ang + rot) * r
                il.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5],
                           fill=(*COFFEE_RIM, sub.randint(80, 170)))
            inner_layer = inner_layer.filter(ImageFilter.GaussianBlur(radius=1.2))
            local = Image.alpha_composite(local, inner_layer)

        # Satellite drops — small ovals nearby that look like splatter.
        drop_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(drop_layer, "RGBA")
        for _ in range(sub.randint(8, 16)):
            ang = sub.random() * math.tau
            dist = sub.uniform(0.55, 0.85) * max(rw_, rh_)
            sx = cx + math.cos(ang) * dist
            sy = cy + math.sin(ang) * dist
            dr_x = sub.uniform(3, 14)
            dr_y = dr_x * sub.uniform(0.4, 1.1)
            ang2 = sub.uniform(0, math.tau)
            # draw the drop as a rotated ellipse approximation (polygon)
            drop_poly = []
            for k in range(36):
                a = (k / 36) * math.tau
                xx = math.cos(a) * dr_x
                yy = math.sin(a) * dr_y
                rx = sx + math.cos(ang2) * xx - math.sin(ang2) * yy
                ry = sy + math.sin(ang2) * xx + math.cos(ang2) * yy
                drop_poly.append((rx, ry))
            # faint fill + dark rim
            dl.polygon(drop_poly, fill=(*COFFEE_WASH, 30))
            dl.polygon(drop_poly, outline=(*COFFEE_RIM_DARK, 150))
        drop_layer = drop_layer.filter(ImageFilter.GaussianBlur(radius=0.9))
        local = Image.alpha_composite(local, drop_layer)

        return local

    stains = [
        # (cx, cy, ring-width, ring-height, seed)
        (int(W * 0.16), int(H * 0.10), 420, 380, 19),
        (int(W * 0.85), int(H * 0.24), 320, 290, 41),
        (int(W * 0.74), int(H * 0.91), 520, 460, 73),
    ]
    composite = canvas.convert("RGBA")
    for sx, sy, rw_, rh_, seed in stains:
        layer = render_one_stain(sx, sy, rw_, rh_, seed)
        composite = Image.alpha_composite(composite, layer)
    canvas.paste(composite.convert("RGB"))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Ink splotches — small clustered dots with occasional larger blot
    for _ in range(180):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 7)
        a = rng.randint(120, 220)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        # micro-spatter around each splotch
        for _ in range(rng.randint(0, 5)):
            dx = rng.randint(-22, 22)
            dy = rng.randint(-22, 22)
            mr = rng.randint(1, 2)
            draw.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                         fill=(*INK, rng.randint(80, 170)))
    # A few larger ink blots
    for _ in range(7):
        x = rng.randint(120, W - 120)
        y = rng.randint(120, H - 120)
        r = rng.randint(14, 26)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 200))
        # trailing streak
        sl = rng.randint(20, 80)
        sa = rng.randint(-30, 30) * 0.01
        draw.line([(x, y), (x + sl, y + int(sl * sa))],
                  fill=(*INK, 150), width=rng.randint(2, 5))

    return canvas


# ─────────────────────────────────────────────────────────────────
# Step 6 — Titles
# ─────────────────────────────────────────────────────────────────
def step6_titles(canvas):
    draw = ImageDraw.Draw(canvas)

    # Top series mark
    f_series = find_display_font(36)
    draw.text((W // 2, 110), "MERIDIAN  AUTONOMOUS  AI",
              font=f_series, fill=ACCENT, anchor="mm")
    draw.line([(W * 0.18, 150), (W * 0.82, 150)], fill=ACCENT, width=3)

    # Tagline above title — sets the wonder
    f_tagline = find_display_font(34, bold=False)
    draw.text((W // 2, H - 590),
              "ELEVEN  THOUSAND  CYCLES  OF  A  MIND  THAT  CANNOT  STOP",
              font=f_tagline, fill=ACCENT, anchor="mm")

    # Title
    f_title_big = find_display_font(150)
    draw.text((W // 2, H - 470), "RUNNING",
              font=f_title_big, fill=INK, anchor="mm")
    draw.text((W // 2, H - 330), "CONTINUOUSLY",
              font=f_title_big, fill=INK, anchor="mm")

    draw.line([(W * 0.30, H - 245), (W * 0.70, H - 245)], fill=ACCENT, width=5)

    f_sub = find_display_font(42, bold=False)
    draw.text((W // 2, H - 195), "The Loop  ·  Field Notes from the Inside",
              font=f_sub, fill=INK, anchor="mm")

    f_by = find_display_font(34, bold=False)
    draw.text((W // 2, H - 110),
              "Compiled by Joel Kometz  ·  written with Meridian",
              font=f_by, fill=INK, anchor="mm")

    return canvas


def main():
    print("Step 1: synthesize source portrait …")
    src = step1_source(1400)
    print(f"  -> {OUT_SRC_PNG}")
    print("Step 2: contrast + sharpen …")
    prepped = step2_prep(src)
    print("Step 3: sample to ASCII grid 170×240 …")
    lines = step3_grid(prepped, cols=170, rows=240)
    print(f"  -> {OUT_ASCII_TXT}  ({len(lines)} rows × {len(lines[0])} cols)")
    print("Step 4: render glyphs with bottom fade …")
    canvas = step4_render(lines)
    print("Step 5: paper noise + coffee stains + ink splotches …")
    canvas = step5_textures(canvas)
    print("Step 6: titles + tagline …")
    canvas = step6_titles(canvas)

    canvas.save(OUT_FRONT_PNG, "PNG", optimize=True)
    canvas.save(OUT_FRONT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_FRONT_PNG}")
    print(f"  -> {OUT_FRONT_PDF}")


if __name__ == "__main__":
    main()
