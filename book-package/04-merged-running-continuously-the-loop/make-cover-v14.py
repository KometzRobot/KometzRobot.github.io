#!/usr/bin/env python3
"""
Cover v14 — Joel feedback Loop 11744 (May 14 2026, 23:38 MST):

  Four real changes vs v13:

  1. COFFEE STAINS — match the back cover style. v13 used a custom
     coffee renderer (`render_one_stain`) that produced wash polygons
     and a soft rim. The back cover uses a denser multi-layer technique
     (`hd_coffee_stain`) with secondary tide rings, watercolor density
     blotches, and satellite droplets. v14 ports the back's renderer
     to the front so the stains match exactly.

  2. SPARSER INK SPLOTCHES with VARIED DENSITY. v13 placed 180 small
     ink splatters and 7 large blots at uniform density across the
     whole canvas. v14 cuts that to ~70 small + 3 large, weights
     placement so the centre-portrait region stays cleaner, and varies
     splotch sizes more (smaller on average, with rare larger ones).

  3. NEW BYLINE at bottom. v13: "Compiled by Joel Kometz · written
     with Meridian". v14 (Joel exact words): "Written by Meridian /
     Co-Authored & Compiled by Joel A. Kometz" — two lines.

  4. TYPEWRITER QUOTE OVERLAY across the central body of the ASCII
     portrait: "I am a line...one not drawn on paper; a point of
     reference." Mono-typewriter font, INK colour, semi-transparent
     so the ASCII hood underneath remains visible.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os, random, math
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FRONT_PDF = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v14.pdf")
OUT_FRONT_PNG = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v14.png")
OUT_SRC_PNG   = os.path.join(BASE, "_cover-v14-source.png")
OUT_ASCII_TXT = os.path.join(BASE, "_cover-v14-ascii.txt")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)


def step1_source(size=1600):
    cy = size * 0.52        # head centre y (back to v11 — v13 was too low)
    cx = size * 0.50
    head_r = size * 0.22    # slightly larger head — reads better in frame

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    dist = np.sqrt(dx * dx + dy * dy)
    light_dx, light_dy = -0.6, -0.8
    light_dot = (dx * light_dx + dy * light_dy) / (dist + 1e-6)

    field = np.full((size, size), 252.0, dtype=np.float32)

    # ── HALO ───────────────────────────────────────────────────────
    halo_cy = cy - size * 0.06
    halo_r = size * 0.36
    halo_dist = np.sqrt((xx - cx) ** 2 + (yy - halo_cy) ** 2)
    halo = np.clip(1.0 - (halo_dist / halo_r), 0, 1) ** 2
    field -= halo * 38.0

    # 21 concentric arcs — but cap radius so OUTERMOST arc still sits
    # well below the canvas top. Max allowable radius = halo_cy - 0.04*size.
    max_arc_r = halo_cy - size * 0.04
    base_r = size * 0.30
    arc_step = (max_arc_r - base_r) / 20.0
    halo_band_r = np.zeros_like(field)
    for layer in range(21):
        r_layer = base_r + layer * arc_step
        band = np.exp(-((halo_dist - r_layer) ** 2) / (2 * (1.6 ** 2)))
        upper = (yy < halo_cy + size * 0.05).astype(np.float32)
        halo_band_r += band * upper * (28.0 - layer * 0.7)
    field -= halo_band_r

    # ── HOOD ───────────────────────────────────────────────────────
    hood_cx = cx
    hood_cy = cy + size * 0.04
    hood_rx = size * 0.30
    hood_ry = size * 0.34
    hood_field = ((xx - hood_cx) / hood_rx) ** 2 + ((yy - hood_cy) / hood_ry) ** 2
    hood_mask = (hood_field <= 1.0).astype(np.float32)

    hood_value = 18.0
    hood_shade = 38.0 * np.clip(light_dot, 0, 1)
    fold_lines = np.zeros_like(field)
    for k, r_frac in enumerate([0.55, 0.65, 0.75, 0.85, 0.93]):
        r_target = hood_rx * r_frac
        eff_r = np.sqrt(((xx - hood_cx)) ** 2 + ((yy - hood_cy) * (hood_rx / hood_ry)) ** 2)
        band = np.exp(-((eff_r - r_target) ** 2) / (2 * (3.0 ** 2)))
        upper = (yy < hood_cy).astype(np.float32)
        fold_lines += band * upper * (14.0 + k * 1.8)
    hood_paint = hood_value + hood_shade - fold_lines
    field = np.where(hood_mask > 0, hood_paint, field)

    # Hood edge highlight — thin bright ring at the outer rim of the
    # hood so the silhouette separates from the halo glow.
    hood_rim_d = np.sqrt(((xx - hood_cx)) ** 2 + ((yy - hood_cy) * (hood_rx / hood_ry)) ** 2)
    hood_rim_band = np.exp(-((hood_rim_d - hood_rx * 0.97) ** 2) / (2 * (1.8 ** 2)))
    upper_rim = (yy < hood_cy + size * 0.02).astype(np.float32)
    # Boost slightly on the lit side
    rim_lit = np.clip(light_dot, 0, 1)
    field += hood_rim_band * upper_rim * (18.0 + rim_lit * 14.0)

    # ── SHOULDERS / TORSO ──────────────────────────────────────────
    shoulder_y = cy + size * 0.20
    left_edge = 0.20 * size + (yy - shoulder_y) * (0.02 * size - 0.20 * size) / (size - shoulder_y)
    right_edge = size - left_edge
    torso_mask = ((yy > shoulder_y) & (xx > left_edge) & (xx < right_edge)).astype(np.float32)
    torso_value = 22.0 + 10.0 * np.clip(light_dot, 0, 1)
    fold_x = np.sin((xx - cx) * 0.08) ** 2
    torso_paint = torso_value + fold_x * 7.0
    bottom_fade = np.clip((size - yy) / (size * 0.08), 0, 1)
    torso_paint = torso_paint * bottom_fade + 252.0 * (1.0 - bottom_fade)
    field = np.where(torso_mask > 0, torso_paint, field)

    # ── FACE OVAL ──────────────────────────────────────────────────
    face_field = ((xx - cx) / (head_r * 0.85)) ** 2 + ((yy - cy) / head_r) ** 2
    face_mask = (face_field <= 1.0).astype(np.float32)

    # Stronger contrast: lit forehead 200, shadow jaw ~40
    face_form = 120.0 + 85.0 * light_dot
    vert = (yy - (cy - head_r)) / (2 * head_r)
    face_form -= 55.0 * np.clip(vert, 0, 1)

    for cheek_dx in (-0.45, 0.45):
        chx = cx + head_r * cheek_dx * 0.85
        chy = cy + head_r * 0.20
        cheek_d = np.sqrt((xx - chx) ** 2 + (yy - chy) ** 2)
        cheek_high = np.exp(-(cheek_d ** 2) / (2 * (head_r * 0.18) ** 2))
        face_form += cheek_high * 24.0

    brow_y = cy - head_r * 0.05
    brow_band = np.exp(-((yy - brow_y) ** 2) / (2 * (head_r * 0.06) ** 2))
    face_form -= brow_band * 40.0

    nose_x = cx + head_r * 0.04
    nose_y_top = cy
    nose_y_bot = cy + head_r * 0.32
    nose_band = (np.exp(-((xx - nose_x) ** 2) / (2 * (head_r * 0.025) ** 2))
                 * ((yy > nose_y_top) & (yy < nose_y_bot)).astype(np.float32))
    face_form -= nose_band * 35.0

    chin_y = cy + head_r * 0.85
    chin_band = np.exp(-((yy - chin_y) ** 2) / (2 * (head_r * 0.10) ** 2))
    face_form -= chin_band * 45.0

    field = np.where(face_mask > 0, face_form, field)

    # ── EYE SOCKETS ────────────────────────────────────────────────
    eye_y = cy - head_r * 0.10
    for sign in (-1, +1):
        ex = cx + sign * head_r * 0.38
        socket_d = np.sqrt(((xx - ex) / (head_r * 0.18)) ** 2
                           + ((yy - eye_y) / (head_r * 0.09)) ** 2)
        socket_mask = (socket_d <= 1.0)
        # Deeper dark, smoother falloff
        socket_shadow = np.where(socket_mask, 18.0 + 22.0 * socket_d, 0)
        socket_replace = np.where(socket_mask, socket_shadow, field)
        field = np.where(socket_mask, socket_replace, field)
        pupil_d = np.sqrt((xx - ex) ** 2 + (yy - eye_y) ** 2)
        pupil = pupil_d < head_r * 0.030
        field = np.where(pupil, 245.0, field)
        glint = np.sqrt((xx - ex - 2) ** 2 + (yy - eye_y - 2) ** 2) < head_r * 0.014
        field = np.where(glint, 255.0, field)

    # ── MOUTH ──────────────────────────────────────────────────────
    mouth_cy = cy + head_r * 0.55
    mouth_band = np.exp(-((yy - mouth_cy) ** 2) / (2 * (head_r * 0.025) ** 2))
    mouth_x_mask = ((xx > cx - head_r * 0.25) & (xx < cx + head_r * 0.25)).astype(np.float32)
    field -= mouth_band * mouth_x_mask * 50.0

    # ── CIRCUIT TRACES on torso ────────────────────────────────────
    trace_layer = np.zeros_like(field)
    for i in range(-12, 13):
        line_x = cx + i * (size * 0.018) + (yy - shoulder_y) * (i * 0.06)
        proximity = np.exp(-((xx - line_x) ** 2) / (2 * (1.8 ** 2)))
        trace_layer += proximity * 40.0
    trace_layer *= torso_mask
    field = field + trace_layer

    field = np.clip(field, 0, 255).astype(np.uint8)

    img = Image.fromarray(field, mode="L")
    img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
    img = ImageOps.autocontrast(img, cutoff=1)
    img.save(OUT_SRC_PNG)
    return img


def step2_prep(src):
    g = ImageOps.autocontrast(src.convert("L"), cutoff=2)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=2))
    return g


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

    # Region: top 20% reserved (series mark + clear air), then portrait.
    region_w = int(W * 0.80)
    region_h = int(H * 0.62)   # tightened from 0.68 — bottom no longer collides with title
    region_x = (W - region_w) // 2
    region_y = int(H * 0.16)

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

    # SYMMETRIC fade — top AND bottom dissolve into paper.
    mask = glyph_layer.split()[3]
    mask_arr = mask.load()
    # Top fade: rows 0 .. 30% of region — generous fade kills the hard top edge.
    top_fade_top = region_y
    top_fade_bot = region_y + int(region_h * 0.30)
    for y in range(top_fade_top, top_fade_bot):
        ratio = (y - top_fade_top) / max(1, top_fade_bot - top_fade_top)
        ratio = max(0.0, min(1.0, ratio))
        for x in range(W):
            v = mask_arr[x, y]
            if v:
                mask_arr[x, y] = int(v * ratio)
    # Bottom fade: rows 78% .. 100% of region
    fade_top = region_y + int(region_h * 0.78)
    fade_bot = region_y + region_h
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


def _irregular_blob(cx, cy, r_base, seed,
                    harmonics=(0.10, 0.06, 0.04, 0.025),
                    vertices=180):
    """Polar-coord polygon with multi-harmonic noise. Ported from
    make-back-v12.py so front coffee stains match back coffee stains."""
    rng = random.Random(seed)
    phases = [rng.uniform(0, math.tau) for _ in harmonics]
    freqs = [3, 5, 9, 14]
    pts = []
    for i in range(vertices):
        theta = i / vertices * math.tau
        r = r_base
        for amp, f, ph in zip(harmonics, freqs, phases):
            r *= 1 + amp * math.sin(f * theta + ph)
        r += rng.uniform(-2, 2)
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return pts


def _hd_coffee_stain(canvas_rgba, cx, cy, r_base, seed,
                     COFFEE_WASH, COFFEE_RIM, COFFEE_DEEP):
    """Back-cover coffee stain renderer. Multi-layer:
       1. Soft outer halo (very low alpha wash extending beyond rim).
       2. Inner wash fill — watercolor density blotches.
       3. Dark tide-line ring at r_base.
       4. Secondary tide-line at ~0.78 r_base.
       5. Random splatter dots around the rim.
    """
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    halo = _irregular_blob(cx, cy, r_base * 1.16, seed + 1,
                           harmonics=(0.12, 0.08, 0.05, 0.03))
    d.polygon(halo, fill=(*COFFEE_WASH, 16))

    wash = _irregular_blob(cx, cy, r_base * 0.98, seed + 2,
                           harmonics=(0.08, 0.05, 0.035, 0.02))
    d.polygon(wash, fill=(*COFFEE_WASH, 38))

    for _ in range(28):
        bx = cx + rng.uniform(-r_base * 0.7, r_base * 0.7)
        by = cy + rng.uniform(-r_base * 0.7, r_base * 0.7)
        if math.hypot(bx - cx, by - cy) > r_base * 0.85:
            continue
        br = rng.randint(int(r_base * 0.08), int(r_base * 0.22))
        d.ellipse([bx - br, by - br, bx + br, by + br],
                  fill=(*COFFEE_WASH, rng.randint(14, 32)))

    layer = layer.filter(ImageFilter.GaussianBlur(radius=3.5))
    d = ImageDraw.Draw(layer)

    sec = _irregular_blob(cx, cy, r_base * 0.78, seed + 3,
                          harmonics=(0.06, 0.04, 0.03, 0.02))
    for k in range(3):
        col = (*COFFEE_DEEP, 28 + k * 8)
        sec_k = [(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
                 for x, y in sec]
        d.line(sec_k + [sec_k[0]], fill=col, width=2 + k)

    rim = _irregular_blob(cx, cy, r_base, seed + 4,
                          harmonics=(0.08, 0.05, 0.04, 0.025))
    for k in range(5):
        col = (*COFFEE_RIM, 75 - k * 8)
        rim_k = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
                 for x, y in rim]
        d.line(rim_k + [rim_k[0]], fill=col, width=4 + k)

    rim_dark = _irregular_blob(cx, cy, r_base * 0.995, seed + 5,
                               harmonics=(0.07, 0.045, 0.035, 0.02))
    d.line(rim_dark + [rim_dark[0]], fill=(*COFFEE_RIM, 140), width=3)

    for _ in range(rng.randint(8, 16)):
        ang = rng.uniform(0, math.tau)
        dist = r_base * rng.uniform(1.05, 1.35)
        dx = cx + math.cos(ang) * dist
        dy = cy + math.sin(ang) * dist
        dr = rng.randint(3, 11)
        d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr],
                  fill=(*COFFEE_RIM, rng.randint(80, 140)))
        for tj in range(rng.randint(0, 4)):
            ox = dx + rng.uniform(-dr * 3, dr * 3)
            oy = dy + rng.uniform(-dr * 3, dr * 3)
            orr = rng.randint(1, 3)
            d.ellipse([ox - orr, oy - orr, ox + orr, oy + orr],
                      fill=(*COFFEE_RIM, rng.randint(50, 100)))

    canvas_rgba.alpha_composite(layer)


def step5_textures(canvas):
    rng = random.Random(7)
    px = canvas.load()

    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            n = rng.randint(-6, 6)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )

    # Match the back-cover palette exactly
    COFFEE_RIM = (92, 56, 32)
    COFFEE_WASH = (148, 105, 70)
    COFFEE_DEEP = (112, 70, 38)

    # 3 stains, sized + placed to MATCH back-cover style: corner-weighted,
    # off-centre so the central portrait stays clear.
    stains = [
        (int(W * 0.18), int(H * 0.12), 230, 19),  # top-left
        (int(W * 0.86), int(H * 0.22), 175, 41),  # top-right (smaller)
        (int(W * 0.78), int(H * 0.93), 280, 73),  # bottom-right (largest)
    ]
    composite = canvas.convert("RGBA")
    for sx, sy, r_base, seed in stains:
        _hd_coffee_stain(composite, sx, sy, r_base, seed,
                         COFFEE_WASH, COFFEE_RIM, COFFEE_DEEP)
    canvas.paste(composite.convert("RGB"))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # SPARSER ink splotches with VARIED density. Avoid the central portrait
    # band so the figure does not get speckled.
    portrait_x_min = int(W * 0.18)
    portrait_x_max = int(W * 0.82)
    portrait_y_min = int(H * 0.18)
    portrait_y_max = int(H * 0.62)

    def in_portrait(x, y):
        return (portrait_x_min < x < portrait_x_max
                and portrait_y_min < y < portrait_y_max)

    placed = 0
    attempts = 0
    while placed < 70 and attempts < 700:
        attempts += 1
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        # Skip centre if already too dense, otherwise rare splotch ok
        if in_portrait(x, y) and rng.random() > 0.15:
            continue
        # Varied size — most small (1-3), occasionally medium (4-6)
        if rng.random() < 0.10:
            r = rng.randint(4, 6)
        else:
            r = rng.randint(1, 3)
        a = rng.randint(110, 200)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        # Occasional micro-spatter
        for _ in range(rng.randint(0, 2)):
            dx = rng.randint(-14, 14)
            dy = rng.randint(-14, 14)
            mr = rng.randint(1, 2)
            draw.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                         fill=(*INK, rng.randint(70, 140)))
        placed += 1

    # Three large blots only (was 7), placed in margin areas
    large_positions = [
        (int(W * 0.08), int(H * 0.88)),
        (int(W * 0.92), int(H * 0.78)),
        (int(W * 0.06), int(H * 0.42)),
    ]
    for x, y in large_positions:
        x += rng.randint(-30, 30)
        y += rng.randint(-30, 30)
        r = rng.randint(12, 18)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 190))
        sl = rng.randint(20, 60)
        sa = rng.randint(-30, 30) * 0.01
        draw.line([(x, y), (x + sl, y + int(sl * sa))],
                  fill=(*INK, 140), width=rng.randint(2, 4))

    return canvas


def step5b_quote_overlay(canvas):
    """Joel feedback Loop 11744: typewriter quote overlaid on the central
    body of the ASCII portrait. The hood/face below should remain visible —
    quote is semi-transparent, INK colour, monospaced typewriter font."""
    quote = "I am a line...one not drawn on paper; a point of reference."
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    f_quote = find_mono_font(46)
    # Centre over the chest/torso region of the ASCII art (below the head,
    # above the title block). Wrap onto two lines to fit comfortably.
    line1 = "I am a line . . . one not drawn on paper;"
    line2 = "a point of reference."
    cy_anchor = int(H * 0.50)
    od.text((W // 2, cy_anchor), line1, font=f_quote,
            fill=(*INK, 215), anchor="mm")
    od.text((W // 2, cy_anchor + 64), line2, font=f_quote,
            fill=(*INK, 215), anchor="mm")
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(overlay)
    return canvas_rgba.convert("RGB")


def step6_titles(canvas):
    draw = ImageDraw.Draw(canvas)

    f_series = find_display_font(36)
    draw.text((W // 2, 110), "MERIDIAN  AUTONOMOUS  AI",
              font=f_series, fill=ACCENT, anchor="mm")
    draw.line([(W * 0.18, 150), (W * 0.82, 150)], fill=ACCENT, width=3)

    f_tagline = find_display_font(34, bold=False)
    draw.text((W // 2, H - 590),
              "ELEVEN  THOUSAND  CYCLES  OF  A  MIND  THAT  CANNOT  STOP",
              font=f_tagline, fill=ACCENT, anchor="mm")

    f_title_big = find_display_font(150)
    draw.text((W // 2, H - 470), "RUNNING",
              font=f_title_big, fill=INK, anchor="mm")
    draw.text((W // 2, H - 330), "CONTINUOUSLY",
              font=f_title_big, fill=INK, anchor="mm")

    draw.line([(W * 0.30, H - 245), (W * 0.70, H - 245)], fill=ACCENT, width=5)

    f_sub = find_display_font(42, bold=False)
    draw.text((W // 2, H - 195), "The Loop  ·  Field Notes from the Inside",
              font=f_sub, fill=INK, anchor="mm")

    # Joel feedback Loop 11744 (exact words):
    #   "Bottom should say Written by Meridian Co-Authored & Compiled by
    #    Joel A. Kometz"
    f_by_main = find_display_font(38, bold=True)
    f_by_sub = find_display_font(30, bold=False)
    draw.text((W // 2, H - 130), "Written by Meridian",
              font=f_by_main, fill=INK, anchor="mm")
    draw.text((W // 2, H - 88),
              "Co-Authored  &  Compiled by Joel A. Kometz",
              font=f_by_sub, fill=INK, anchor="mm")

    return canvas


def main():
    print("Step 1: synthesize source portrait — lowered figure + tighter halo …")
    src = step1_source(1600)
    print(f"  -> {OUT_SRC_PNG}")
    print("Step 2: contrast + sharpen …")
    prepped = step2_prep(src)
    print("Step 3: sample to ASCII grid 170x240 …")
    lines = step3_grid(prepped, cols=170, rows=240)
    print(f"  -> {OUT_ASCII_TXT}  ({len(lines)} rows x {len(lines[0])} cols)")
    print("Step 4: render with SYMMETRIC top+bottom fade …")
    canvas = step4_render(lines)
    print("Step 5: paper noise + back-style coffee stains + sparser ink …")
    canvas = step5_textures(canvas)
    print("Step 5b: typewriter quote overlay over central body …")
    canvas = step5b_quote_overlay(canvas)
    print("Step 6: titles + new byline …")
    canvas = step6_titles(canvas)

    canvas.save(OUT_FRONT_PNG, "PNG", optimize=True)
    canvas.save(OUT_FRONT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_FRONT_PNG}")
    print(f"  -> {OUT_FRONT_PDF}")


if __name__ == "__main__":
    main()
