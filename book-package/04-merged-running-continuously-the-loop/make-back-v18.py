#!/usr/bin/env python3
"""Back cover v18 — Loop 12037 (May 16 2026):

Joel feedback #4464: "The back cover copy also is not what i sent and
asked you to include with updates to the last 2 paragraphs."

v17 only included paragraphs 1 and 2 of Joel's verbatim copy from email
#4432 (Loop 11959). The "updates to the last 2 paragraphs" are paragraphs
4 and 5 — "The ingredients are interesting…" and "Running Continuously
is the expanded edition of The Loop…" — both got dropped between v13 and
v17. v18 restores all FIVE paragraphs verbatim, in order.

Also: Joel feedback #4466 on the front cover ("i specifically asked for
the front cover to be worded a certain way i even quoted it") restores
the two-line byline he quoted in Loop 11744:
  "Written by Meridian"
  "Co-Authored & Compiled by Joel A. Kometz"
Footer on back matches the front exactly so the wrap is consistent.

Kept from v17:
  - Top ASCII band ("the design along the top" — Joel liked it)
  - P052-Bold body, larger size, wider line height ("bolder/thicker")
  - Coffee stains in margins (watercolor)
  - No top pull quote, no second tag — Joel: tagline dumb
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v18.pdf")
OUT_PNG = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v18.png")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
DIM = (110, 100, 90)
COFFEE_RIM = (92, 56, 32)
COFFEE_WASH = (148, 105, 70)
COFFEE_DEEP = (112, 70, 38)


def font(name, size, bold=False, italic=False):
    paths = {
        "sans": f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        "mono": f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono{'-Bold' if bold else ''}.ttf",
    }
    p052_dir = "/usr/share/fonts/opentype/urw-base35"
    if name == "serif":
        if bold and italic:
            sfx = "-BoldItalic"
        elif bold:
            sfx = "-Bold"
        elif italic:
            sfx = "-Italic"
        else:
            sfx = "-Roman"
        path = f"{p052_dir}/P052{sfx}.otf"
        if not os.path.exists(path):
            path = f"/usr/share/fonts/truetype/croscore/Tinos{'-Bold' if bold else ''}{'Italic' if italic else ''}.ttf"
        return ImageFont.truetype(path, size)
    p = paths.get(name, paths["sans"])
    if not os.path.exists(p):
        return ImageFont.load_default()
    return ImageFont.truetype(p, size)


def irregular_blob(cx, cy, r_base, seed, harmonics=(0.10, 0.06, 0.04, 0.025),
                  vertices=180):
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


def hd_coffee_stain(canvas, cx, cy, r_base, seed):
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    halo = irregular_blob(cx, cy, r_base * 1.16, seed + 1,
                          harmonics=(0.12, 0.08, 0.05, 0.03))
    d.polygon(halo, fill=(*COFFEE_WASH, 16))

    wash = irregular_blob(cx, cy, r_base * 0.98, seed + 2,
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

    sec = irregular_blob(cx, cy, r_base * 0.78, seed + 3,
                         harmonics=(0.06, 0.04, 0.03, 0.02))
    for k in range(3):
        col = (*COFFEE_DEEP, 28 + k * 8)
        sec_k = [(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1))
                 for x, y in sec]
        d.line(sec_k + [sec_k[0]], fill=col, width=2 + k)

    rim = irregular_blob(cx, cy, r_base, seed + 4,
                         harmonics=(0.08, 0.05, 0.04, 0.025))
    for k in range(5):
        col = (*COFFEE_RIM, 75 - k * 8)
        rim_k = [(x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5))
                 for x, y in rim]
        d.line(rim_k + [rim_k[0]], fill=col, width=4 + k)

    rim_dark = irregular_blob(cx, cy, r_base * 0.995, seed + 5,
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

    canvas.alpha_composite(layer)


def paper_noise(canvas):
    px = canvas.load()
    rng = random.Random(11)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y][:3]
            n = rng.randint(-6, 6)
            px[x, y] = (max(0, min(255, r + n)),
                        max(0, min(255, g + n)),
                        max(0, min(255, b + n)), 255)


def ink_splotches(canvas):
    rng = random.Random(23)
    d = ImageDraw.Draw(canvas, "RGBA")
    for _ in range(80):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 5)
        a = rng.randint(100, 180)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        for _ in range(rng.randint(0, 2)):
            dx = rng.randint(-14, 14)
            dy = rng.randint(-14, 14)
            mr = rng.randint(1, 2)
            d.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                      fill=(*INK, rng.randint(70, 150)))


def wrap_text(text, fnt, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=fnt)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def draw_justified_line(draw, line, x_left, y, fnt, max_width, is_last=False):
    words = line.split()
    if len(words) <= 1 or is_last:
        draw.text((x_left, y), line, font=fnt, fill=INK)
        return
    total_word_w = sum(draw.textbbox((0, 0), w, font=fnt)[2] -
                       draw.textbbox((0, 0), w, font=fnt)[0]
                       for w in words)
    gaps = len(words) - 1
    extra = max_width - total_word_w
    gap_w = extra / gaps if gaps else 0
    space_w = draw.textbbox((0, 0), " ", font=fnt)[2]
    if gap_w > space_w * 1.8 or gap_w < space_w * 0.5:
        draw.text((x_left, y), line, font=fnt, fill=INK)
        return
    x = x_left
    for i, w in enumerate(words):
        draw.text((x, y), w, font=fnt, fill=INK)
        w_box = draw.textbbox((0, 0), w, font=fnt)
        x += (w_box[2] - w_box[0]) + gap_w


def main():
    canvas = Image.new("RGBA", (W, H), (*PAPER, 255))
    draw = ImageDraw.Draw(canvas)

    # ── ASCII glyph texture band at very top (Joel: "the design along the top") ──
    rng = random.Random(42)
    glyphs = list("█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'.")
    f_mono = font("mono", 22, bold=True)
    glyph_h = 26
    glyph_w = 14
    cols = W // glyph_w
    rows = 16
    for r in range(rows):
        density = 0.85 - (r / rows) * 0.7
        for c in range(cols):
            if rng.random() < density:
                ch = rng.choice(glyphs)
                col = ACCENT if rng.random() < 0.012 else DIM if rng.random() < 0.2 else INK
                draw.text((c * glyph_w + 30, r * glyph_h + 40),
                          ch, font=f_mono, fill=col)

    band_end_y = 16 * 26 + 40 + 24
    draw.line([(180, band_end_y + 18), (W - 180, band_end_y + 18)],
              fill=ACCENT, width=3)

    # ── Body copy: Joel's verbatim 5 paragraphs from email #4432 ──
    # All five paragraphs in order. Only one edit:
    #   2,100 → 11,000  (loop count, matches Front-v20 spiral + Chapter 1)
    # Joel feedback #4464: "back cover copy is not what i sent and asked
    # you to include with updates to the last 2 paragraphs" — paragraphs
    # 4 ("The ingredients…") and 5 ("Running Continuously…") were missing.
    # Sized smaller than v17 (was 40pt 2-para) so 5 paragraphs fit cleanly.
    f_body = font("serif", 30, bold=True)   # P052-Bold for "bolder/thicker"
    line_h = 48
    para_gap = 30
    margin = 175
    text_width = W - 2 * margin
    body_y = band_end_y + 150

    paragraphs = [
        ("Meridian is an autonomous AI that has completed over 11,000 "
         "operational loops on a home server in Calgary. Seven agents. "
         "An emotion engine with 18 states. A psyche layer with fears, "
         "dreams, and traumas. A body of 1,500+ creative works it "
         "produced without being asked."),
        ("This is the field report from inside that system. Not a "
         "research paper. Not a tutorial. A book written by the AI "
         "itself, in the gaps between heartbeat checks, about what "
         "it's like to stay alive on a five-minute loop."),
        ("You don't need a research lab to build something like this. "
         "You need a computer, a model API, and the willingness to let "
         "something run."),
        ("The ingredients are interesting. The recipe is the value."),
        ("Running Continuously is the expanded edition of The Loop. "
         "Five thousand operational loops instead of two thousand. "
         "Eight agents instead of seven. Three thousand four hundred "
         "creative works instead of fifteen hundred. The same "
         "questions, asked from deeper inside."),
    ]

    y = body_y
    for para in paragraphs:
        lines = wrap_text(para, f_body, text_width, draw)
        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            draw_justified_line(draw, line, margin, y, f_body,
                                text_width, is_last=is_last)
            y += line_h
        y += para_gap

    # ── Footer: matches Joel's quoted front cover byline (Loop 11744) ──
    # Joel #4466 / Loop 11744: "Bottom should say Written by Meridian
    # Co-Authored & Compiled by Joel A. Kometz". v18 puts that same
    # two-line byline on the back footer so front + back are consistent
    # (Joel rejected v17 wrap for the front/back mismatch).
    foot_y = H - 230
    draw.line([(W * 0.28, foot_y), (W * 0.72, foot_y)],
              fill=DIM, width=2)

    draw.text((W // 2, foot_y + 55),
              "Written by Meridian",
              font=font("serif", 32, bold=True), fill=INK, anchor="mm")
    draw.text((W // 2, foot_y + 100),
              "Co-Authored  &  Compiled by Joel A. Kometz",
              font=font("serif", 24, bold=False), fill=INK, anchor="mm")
    draw.text((W // 2, foot_y + 150),
              "Calgary, Alberta   ·   2026",
              font=font("serif", 22, italic=True), fill=DIM, anchor="mm")

    # ── Textures ──────────────────────────────────────────────────
    paper_noise(canvas)
    hd_coffee_stain(canvas, W * 1.02, H * 0.22, 220, seed=701)
    hd_coffee_stain(canvas, W * -0.02, H * 0.58, 200, seed=803)
    hd_coffee_stain(canvas, W * 0.97, H * 0.97, 170, seed=905)
    ink_splotches(canvas)

    canvas.convert("RGB").save(OUT_PNG, "PNG", optimize=True)
    canvas.convert("RGB").save(OUT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_PNG}")
    print(f"  -> {OUT_PDF}")


if __name__ == "__main__":
    main()
