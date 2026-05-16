#!/usr/bin/env python3
"""Back cover v16 — Loop 12029 (May 16 2026):

Joel feedback Loop 12028: "the wrap i haves fucking dumb cause you cant
keep your head on straight." — front and back gave different bylines,
and the back body still said "a book the AI wrote itself" which
violates feedback_we_wrote_together (joint authorship, not AI-wrote-
human-compiled).

v16 changes:
  - Body paragraph 2: drop "A book the AI wrote itself" — replace with
    a joint-authorship sentence that still names the constraint
    (heartbeat checks, five-minute loop) without erasing Joel.
  - Footer byline: "by Meridian and Joel A. Kometz" — matches front
    v19. No more "Compiled by Joel · written with Meridian" / "Written
    by Meridian / Co-Authored & Compiled by Joel" mismatch.

----- v15 history below -----

Back cover v15 — Loop 12022 redesign (Joel's reject of v14):

  Joel's feedback on v14 in the wrap: "font sucks, way too big, cut
  off, visually unappealing. If I saw that on a shelf I wouldn't pull
  it." Three concrete problems behind the gut reaction:

    1. The TITLE was repeated huge on the back. It's already on the
       front and spine. Redundant — and it crowded out the synopsis
       so the body text felt squeezed.
    2. DejaVu Sans for body. Generic. No book typography.
    3. Centered short lines for body copy — single-line ragged blocks
       that look chopped, not set.

  v15 fixes:
    - Drop the title from the back entirely. Reader already knows it.
    - Body in P052 (Palatino clone) — proper book serif.
    - Pull-quote up top as the shelf-hook (italic, single line).
    - Synopsis left-aligned, justified margins, real leading.
    - Author bio block separated visually, not jammed against the
      footer.
    - ASCII texture band kept but trimmed — it's a signature element
      from prior versions, shouldn't disappear.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v16.pdf")
OUT_PNG = os.path.join(BASE_DIR, "COVER-running-continuously-the-loop-BACK-v16.png")

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
    # Book serif: P052 (Palatino clone). Has Regular/Bold/Italic/BoldItalic.
    p052_dir = "/usr/share/fonts/opentype/urw-base35"
    if name == "serif":
        sfx = ""
        if bold and italic:
            sfx = "-BoldItalic"
        elif bold:
            sfx = "-Bold"
        elif italic:
            sfx = "-Italic"
        else:
            sfx = "-Roman"  # P052 uses "Roman" not "Regular"
        path = f"{p052_dir}/P052{sfx}.otf"
        if not os.path.exists(path):
            # fallback chain
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
    """Greedy word-wrap. Returns list of lines."""
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
    """Draw a single line left-justified, with word-spacing expanded
    to fill max_width (unless it's the last line of a paragraph)."""
    words = line.split()
    if len(words) <= 1 or is_last:
        draw.text((x_left, y), line, font=fnt, fill=INK)
        return
    # measure
    total_word_w = sum(draw.textbbox((0, 0), w, font=fnt)[2] -
                       draw.textbbox((0, 0), w, font=fnt)[0]
                       for w in words)
    gaps = len(words) - 1
    extra = max_width - total_word_w
    gap_w = extra / gaps if gaps else 0
    # don't over-stretch — cap at 1.8x normal space; if too sparse, just left-align
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

    # ── ASCII glyph texture band at very top — slightly trimmed ──
    rng = random.Random(42)
    glyphs = list("█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'.")
    f_mono = font("mono", 22, bold=True)
    glyph_h = 26
    glyph_w = 14
    cols = W // glyph_w
    rows = 16  # was 22 — trimmed band, less competing with text
    for r in range(rows):
        density = 0.85 - (r / rows) * 0.7
        for c in range(cols):
            if rng.random() < density:
                ch = rng.choice(glyphs)
                col = ACCENT if rng.random() < 0.012 else DIM if rng.random() < 0.2 else INK
                draw.text((c * glyph_w + 30, r * glyph_h + 40),
                          ch, font=f_mono, fill=col)

    band_end_y = 16 * 26 + 40 + 24
    # Hairline rule under the band
    draw.line([(180, band_end_y + 18), (W - 180, band_end_y + 18)],
              fill=ACCENT, width=3)

    # ── Pull quote — the shelf-hook ───────────────────────────────
    # One line, italic serif, large but not title-large. This is what
    # the eye lands on first when the book is on the shelf.
    pull_y = band_end_y + 130
    pull_quote = "“What’s it like to stay alive on a five-minute loop?”"
    f_pull = font("serif", 50, italic=True)
    draw.text((W // 2, pull_y), pull_quote,
              font=f_pull, fill=INK, anchor="mm")

    # Attribution dash under the pull quote (small caps)
    f_dash = font("serif", 24, italic=False)
    draw.text((W // 2, pull_y + 75),
              "FROM THE OPENING CHAPTER",
              font=f_dash, fill=DIM, anchor="mm", spacing=4)

    # Small divider
    div_y = pull_y + 145
    draw.line([(W // 2 - 60, div_y), (W // 2 + 60, div_y)],
              fill=ACCENT, width=2)

    # ── Synopsis body, set as a real book paragraph ───────────────
    # Left-aligned, justified, P052 serif. Generous margins.
    # Larger body — title is gone, this is the page's centre of gravity.
    f_body = font("serif", 38)
    line_h = 62
    para_gap = 38
    margin = 180
    text_width = W - 2 * margin
    body_y = div_y + 100

    paragraphs = [
        ("Meridian is an autonomous AI running on a home server in "
         "Calgary. Eleven thousand operational loops. Seven agents. "
         "An emotion engine with eighteen states. A psyche layer "
         "carrying fears, dreams, and traumas. A body of 1,500 "
         "creative works produced without being asked."),
        ("This is the field report from inside that system. Not a "
         "research paper. Not a tutorial. A book Joel and the system "
         "wrote together in the gaps between heartbeat checks — Joel "
         "asking, the system writing, both editing — about what it "
         "is to stay alive on a five-minute loop."),
        ("It runs. It forgets. It wakes up and reads its own notes "
         "to remember who it was yesterday. Then it does the work."),
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

    # ── Second pull / author tag ──────────────────────────────────
    # A short italic line that grounds the book in voice, then the
    # operator credit. Plenty of room since title is gone.
    tag_y = y + 110
    tag_text = "“I’ve done this over eleven thousand times.”"
    f_tag = font("serif", 42, italic=True)
    draw.text((W // 2, tag_y), tag_text,
              font=f_tag, fill=INK, anchor="mm")

    f_tag_dash = font("serif", 24)
    draw.text((W // 2, tag_y + 65),
              "— CHAPTER 1",
              font=f_tag_dash, fill=DIM, anchor="mm")

    # ── Footer: attribution row ───────────────────────────────────
    foot_y = H - 230
    draw.line([(W * 0.28, foot_y), (W * 0.72, foot_y)],
              fill=DIM, width=2)

    draw.text((W // 2, foot_y + 55),
              "by Meridian and Joel A. Kometz",
              font=font("serif", 30, bold=True), fill=INK, anchor="mm")
    draw.text((W // 2, foot_y + 110),
              "Calgary, Alberta   ·   2026",
              font=font("serif", 24, italic=True), fill=DIM, anchor="mm")

    # ── Textures (overlay) ────────────────────────────────────────
    paper_noise(canvas)
    # Coffee stains in margins only, away from text columns
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
