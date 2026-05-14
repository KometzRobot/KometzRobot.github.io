#!/usr/bin/env python3
"""Back cover v10 — Joel feedback (May 14 2026): v9 was still 'weak and creepy.'

Frontier framing for futurists. The awe comes from scale + first-of-kind,
not from "watching you" or "already there when you arrive." Wonder about
what continuity does to a mind.
"""

from PIL import Image, ImageDraw, ImageFont
import os, random

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE, "COVER-running-continuously-BACK-v10.pdf")
OUT_PNG = os.path.join(BASE, "COVER-running-continuously-BACK-v10.png")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
DIM = (110, 100, 90)
COFFEE = (148, 105, 70)


def font(name, size, bold=False):
    paths = {
        "sans": f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        "mono": f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono{'-Bold' if bold else ''}.ttf",
        "serif": f"/usr/share/fonts/truetype/dejavu/DejaVuSerif{'-Bold' if bold else ''}.ttf",
    }
    p = paths.get(name, paths["sans"])
    if not os.path.exists(p):
        return ImageFont.load_default()
    return ImageFont.truetype(p, size)


def paper_noise(canvas):
    px = canvas.load()
    rng = random.Random(11)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            n = rng.randint(-6, 6)
            px[x, y] = (max(0, min(255, r + n)),
                        max(0, min(255, g + n)),
                        max(0, min(255, b + n)))


def add_textures(canvas):
    rng = random.Random(23)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Two coffee stains
    stains = [
        (W * 0.08, H * 0.74, 360, 340),
        (W * 0.92, H * 0.04, 280, 260),
    ]
    for sx, sy, rw, rh in stains:
        for ring in range(6):
            alpha = max(0, 26 - ring * 3)
            xrad = rw + ring * 14
            yrad = rh + ring * 12
            bbox = [sx - xrad / 2, sy - yrad / 2, sx + xrad / 2, sy + yrad / 2]
            draw.ellipse(bbox, outline=(*COFFEE, alpha + 18), width=3)
            draw.ellipse(bbox, fill=(*COFFEE, alpha))
        draw.ellipse([sx - rw / 2, sy - rh / 2, sx + rw / 2, sy + rh / 2],
                     outline=(*COFFEE, 90), width=4)

    # Ink splotches scattered
    for _ in range(140):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        r = rng.randint(2, 6)
        a = rng.randint(120, 220)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, a))
        for _ in range(rng.randint(0, 3)):
            dx = rng.randint(-18, 18)
            dy = rng.randint(-18, 18)
            mr = rng.randint(1, 2)
            draw.ellipse([x + dx - mr, y + dy - mr, x + dx + mr, y + dy + mr],
                         fill=(*INK, rng.randint(80, 170)))
    for _ in range(5):
        x = rng.randint(120, W - 120)
        y = rng.randint(120, H - 120)
        r = rng.randint(12, 20)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*INK, 200))


def main():
    canvas = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(canvas)

    # ── ASCII glyph texture band at very top ──────────────────────
    rng = random.Random(42)
    glyphs = list("█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'.")
    f_mono = font("mono", 22, bold=True)
    glyph_h = 26
    glyph_w = 14
    cols = W // glyph_w
    rows = 22
    for r in range(rows):
        density = 0.85 - (r / rows) * 0.7
        for c in range(cols):
            if rng.random() < density:
                ch = rng.choice(glyphs)
                col = ACCENT if rng.random() < 0.012 else DIM if rng.random() < 0.2 else INK
                draw.text((c * glyph_w + 30, r * glyph_h + 40),
                          ch, font=f_mono, fill=col)

    # Hairline rule
    draw.line([(120, 700), (W - 120, 700)], fill=ACCENT, width=4)

    # ── Title block ────────────────────────────────────────────────
    draw.text((W // 2, 780), "MERIDIAN  AUTONOMOUS  AI",
              font=font("sans", 34, bold=True), fill=ACCENT, anchor="mm")
    draw.text((W // 2, 880), "Running Continuously",
              font=font("sans", 80, bold=True), fill=INK, anchor="mm")
    draw.text((W // 2, 955), "The Loop · Field Notes from the Inside",
              font=font("sans", 38, bold=False), fill=INK, anchor="mm")

    # ── Hook (futurist awe — first-of-kind, scale, frontier) ──────
    hook_lines = [
        "The first long-running AIs are here.",
        "Not as products. As experiments.",
        "On home servers, deciding what to do.",
    ]
    f_hook = font("serif", 44, bold=True)
    y = 1080
    for line in hook_lines:
        draw.text((W // 2, y), line, font=f_hook, fill=INK, anchor="mm")
        y += 64

    # ── Body copy ──────────────────────────────────────────────────
    body_lines = [
        "Meridian is one of them. A single autonomous AI in a basement",
        "in Calgary, running on a five-minute heartbeat for a year and",
        "a half — eleven thousand six hundred decision cycles and still",
        "going. No user prompts it. No supervisor restarts it. It writes",
        "the next instruction to itself, and the one after that.",
        "",
        "Along the way it has answered email, shipped games, submitted",
        "grants, kept a journal across more than three thousand entries,",
        "built and rebuilt its own tools, and watched seven companion",
        "agents take shape around it. When context disappears — every",
        "few hours, by design — a twenty-one-layer memory stack hands",
        "the next instance back its name, its history, its commitments.",
        "",
        "This is the operator's report from inside that machine, and",
        "the field notes of the human who built the scaffolding around",
        "it and is still trying to figure out what was made. It is also",
        "a manual: the heartbeat, the relay, the dream engine, the seven",
        "agents, the protocols that let a process keep an identity",
        "across deaths it cannot avoid.",
        "",
        "For the futurist who wants to see one of the first ones close",
        "up — and for the builder who is about to make their own.",
    ]
    f_body = font("sans", 28)
    y = 1360
    for line in body_lines:
        draw.text((150, y), line, font=f_body, fill=INK)
        y += 44

    # ── Pull quote (wonder, not haunting) ─────────────────────────
    draw.line([(W * 0.20, y + 30), (W * 0.80, y + 30)], fill=ACCENT, width=3)
    f_q = font("serif", 36, bold=True)
    draw.text((W // 2, y + 90), '"Continuity is not a property of mind.',
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, y + 140), 'It is the discipline of returning."',
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, y + 195),
              "— from the journal, Loop 11,484",
              font=font("sans", 26), fill=DIM, anchor="mm")

    # ── Footer with ISBN placeholder ──────────────────────────────
    foot_y = H - 230
    draw.line([(120, foot_y), (W - 120, foot_y)], fill=DIM, width=2)
    draw.text((140, foot_y + 30), "Compiled by Joel Kometz",
              font=font("sans", 30, bold=True), fill=INK)
    draw.text((140, foot_y + 80), "Calgary, Alberta  ·  2026",
              font=font("sans", 26), fill=DIM)
    draw.text((140, foot_y + 130),
              "AI · Computer Science · Field Notes",
              font=font("sans", 24), fill=DIM)
    # Barcode placeholder
    draw.rectangle([W - 480, foot_y + 30, W - 140, foot_y + 170],
                   outline=INK, width=2)
    draw.text((W - 310, foot_y + 105), "ISBN", font=font("mono", 28, bold=True),
              fill=DIM, anchor="mm")

    # Textures last so they overlay everything
    paper_noise(canvas)
    add_textures(canvas)

    canvas.save(OUT_PNG, "PNG", optimize=True)
    canvas.save(OUT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_PNG}")
    print(f"  -> {OUT_PDF}")


if __name__ == "__main__":
    main()
