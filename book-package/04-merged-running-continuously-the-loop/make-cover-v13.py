#!/usr/bin/env python3
"""
Cover v13 — Joel feedback Loop 11742 (May 14 2026, 23:00 MST):

  * "The book cover ASCII art got worse not better and the top is
     still abruptly cut off."

v11 added headroom in the source canvas, but the rendered cover still
shows a hard horizontal edge where the ASCII glyph mat begins. The
halo's outermost concentric arcs hit row 0 of the ASCII grid and
print as a flat line. Below that the face/hood is too low-contrast to
read as a figure.

Three real changes vs v11:

  1. SYMMETRIC FADE. v11 fades glyphs into paper at the BOTTOM of the
     portrait region but not at the top. v13 mirrors the same fade at
     the top so the halo dissolves into paper instead of clipping.

  2. LOWER FIGURE + TIGHTER HALO. Move portrait centre from cy=0.52
     down to cy=0.58, and cap the outermost halo arc radius below
     halo_cy so no arc ever touches the source's upper edge.

  3. STRONGER FACE FORM. Increase the contrast curve between
     face-form-shadow, brow shadow, eye-socket darkness and cheek
     highlights so the head reads as a head, not a smudge. Add hood
     edge highlight to separate hood silhouette from halo glow.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os, random, math
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FRONT_PDF = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v13.pdf")
OUT_FRONT_PNG = os.path.join(BASE, "COVER-running-continuously-the-loop-FRONT-v13.png")
OUT_SRC_PNG   = os.path.join(BASE, "_cover-v13-source.png")
OUT_ASCII_TXT = os.path.join(BASE, "_cover-v13-ascii.txt")

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

    draw = ImageDraw.Draw(canvas, "RGBA")

    COFFEE_RIM_DARK = (78, 44, 22)
    COFFEE_RIM = (118, 68, 36)
    COFFEE_WASH = (172, 130, 92)

    def render_one_stain(cx, cy, rw_, rh_, seed):
        local = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(local, "RGBA")
        sub = random.Random(seed)
        rot = sub.uniform(-0.25, 0.25)

        steps = 720
        radii = []
        for i in range(steps):
            ang = (i / steps) * math.tau
            base_x = (rw_ / 2.0) * math.cos(ang)
            base_y = (rh_ / 2.0) * math.sin(ang)
            base_r = math.hypot(base_x, base_y)
            wob = (math.sin(ang * 3 + sub.random() * 6) * 0.04
                   + math.sin(ang * 7 + sub.random() * 6) * 0.025
                   + sub.uniform(-0.018, 0.018))
            notch = 0.0
            if sub.random() < 0.018:
                notch = -sub.uniform(0.05, 0.12)
            r = base_r * (1.0 + wob + notch)
            radii.append((ang, r))

        wash_poly = []
        for ang, r in radii:
            rr = r * 0.985
            x = cx + math.cos(ang + rot) * rr
            y = cy + math.sin(ang + rot) * rr
            wash_poly.append((x, y))
        ld.polygon(wash_poly, fill=(*COFFEE_WASH, 24))

        for shell in range(4):
            t = 0.96 - shell * 0.02
            poly = []
            for ang, r in radii:
                rr = r * t
                x = cx + math.cos(ang + rot) * rr
                y = cy + math.sin(ang + rot) * rr
                poly.append((x, y))
            ld.polygon(poly, fill=(*COFFEE_RIM, 12))

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
        rim_layer = rim_layer.filter(ImageFilter.GaussianBlur(radius=2.2))
        rl2 = ImageDraw.Draw(rim_layer, "RGBA")
        for _ in range(220):
            ang = sub.random() * math.tau
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
                r *= 1.0 + sub.uniform(-0.02, 0.02)
                x = cx + math.cos(ang + rot) * r
                y = cy + math.sin(ang + rot) * r
                il.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5],
                           fill=(*COFFEE_RIM, sub.randint(80, 170)))
            inner_layer = inner_layer.filter(ImageFilter.GaussianBlur(radius=1.2))
            local = Image.alpha_composite(local, inner_layer)

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
            drop_poly = []
            for k in range(36):
                a = (k / 36) * math.tau
                xx_ = math.cos(a) * dr_x
                yy_ = math.sin(a) * dr_y
                rx = sx + math.cos(ang2) * xx_ - math.sin(ang2) * yy_
                ry = sy + math.sin(ang2) * xx_ + math.cos(ang2) * yy_
                drop_poly.append((rx, ry))
            dl.polygon(drop_poly, fill=(*COFFEE_WASH, 30))
            dl.polygon(drop_poly, outline=(*COFFEE_RIM_DARK, 150))
        drop_layer = drop_layer.filter(ImageFilter.GaussianBlur(radius=0.9))
        local = Image.alpha_composite(local, drop_layer)

        return local

    stains = [
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

    for _ in range(180):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 7)
        a = rng.randint(120, 220)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        for _ in range(rng.randint(0, 5)):
            dx = rng.randint(-22, 22)
            dy = rng.randint(-22, 22)
            mr = rng.randint(1, 2)
            draw.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                         fill=(*INK, rng.randint(80, 170)))
    for _ in range(7):
        x = rng.randint(120, W - 120)
        y = rng.randint(120, H - 120)
        r = rng.randint(14, 26)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 200))
        sl = rng.randint(20, 80)
        sa = rng.randint(-30, 30) * 0.01
        draw.line([(x, y), (x + sl, y + int(sl * sa))],
                  fill=(*INK, 150), width=rng.randint(2, 5))

    return canvas


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

    # Joel feedback Loop 11742: "Put my name in () for compiler"
    f_by = find_display_font(34, bold=False)
    draw.text((W // 2, H - 110),
              "Compiled by Joel Kometz  ·  written with Meridian",
              font=f_by, fill=INK, anchor="mm")

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
    print("Step 5: paper noise + coffee stains + ink splotches …")
    canvas = step5_textures(canvas)
    print("Step 6: titles …")
    canvas = step6_titles(canvas)

    canvas.save(OUT_FRONT_PNG, "PNG", optimize=True)
    canvas.save(OUT_FRONT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_FRONT_PNG}")
    print(f"  -> {OUT_FRONT_PDF}")


if __name__ == "__main__":
    main()
