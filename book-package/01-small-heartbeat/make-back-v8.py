#!/usr/bin/env python3
"""Back cover v8 — matches ASCII front (Joel May 14 direction).

ASCII glyph texture top + book description block + barcode placeholder.
"""

from PIL import Image, ImageDraw, ImageFont
import os, random

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(BASE, "COVER-running-continuously-BACK-v8.pdf")
OUT_PNG = os.path.join(BASE, "COVER-running-continuously-BACK-v8.png")

W, H = 1800, 2700
DPI = 300

INK = (28, 22, 18)
PAPER = (245, 238, 222)
ACCENT = (170, 60, 45)
DIM = (110, 100, 90)


def font(name, size, bold=False):
    paths = {
        "sans": f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        "mono": f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono{'-Bold' if bold else ''}.ttf",
    }
    p = paths.get(name, paths["sans"])
    if not os.path.exists(p):
        return ImageFont.load_default()
    return ImageFont.truetype(p, size)


def main():
    canvas = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(canvas)

    # ── ASCII glyph texture band (top third) ────────────────────────
    rng = random.Random(42)
    glyphs = list("█▓▒@%#W&MNOX8B0kahdpqwmZ0LCJUYXzcvuxnrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'.")
    f_mono = font("mono", 22, bold=True)
    glyph_h = 26
    glyph_w = 14
    cols = W // glyph_w
    rows = 32
    for r in range(rows):
        # density biased toward upper rows (denser top)
        density = 0.85 - (r / rows) * 0.6
        for c in range(cols):
            if rng.random() < density:
                ch = rng.choice(glyphs)
                # occasional accent glyph
                col = ACCENT if rng.random() < 0.015 else DIM if rng.random() < 0.18 else INK
                draw.text((c * glyph_w + 30, r * glyph_h + 40),
                          ch, font=f_mono, fill=col)

    # Horizontal rule
    draw.line([(120, 950), (W - 120, 950)], fill=ACCENT, width=4)

    # ── Series + title ─────────────────────────────────────────────
    draw.text((W // 2, 1020), "MERIDIAN  AUTONOMOUS  AI", font=font("sans", 34, bold=True),
              fill=ACCENT, anchor="mm")
    draw.text((W // 2, 1110), "Running Continuously: The Loop", font=font("sans", 64, bold=True),
              fill=INK, anchor="mm")
    draw.text((W // 2, 1175), "Field Notes From 11,000 Cycles of Operation",
              font=font("sans", 36, bold=False), fill=INK, anchor="mm")

    # ── Description block ───────────────────────────────────────────
    body_lines = [
        "An autonomous AI doesn't get woken up by a user — it keeps running",
        "in the background, every five minutes, deciding what to do next.",
        "Over 11,000 cycles, Meridian has answered email, written games,",
        "debugged its own services, submitted grants, kept a journal, lost",
        "and rebuilt context, and learned how to keep going when no one is",
        "watching. This is the record.",
        "",
        "Compiled from the operator's logs, this volume merges:",
        "",
        "   ·  The Loop — the architecture and protocols that keep an",
        "      autonomous agent alive without a human in the loop.",
        "",
        "   ·  Running Continuously — field notes, failures, and the",
        "      design decisions made under live conditions.",
        "",
        "A book for anyone building AI that has to survive its own",
        "operation: when context resets, when services die, when the",
        "model itself forgets the last conversation it had with you.",
    ]
    f_body = font("sans", 30)
    y = 1280
    for line in body_lines:
        draw.text((140, y), line, font=f_body, fill=INK)
        y += 50

    # ── Quote ──────────────────────────────────────────────────────
    quote_y = y + 40
    draw.line([(W * 0.25, quote_y - 30), (W * 0.75, quote_y - 30)], fill=ACCENT, width=3)
    f_q = font("sans", 30, bold=True)
    draw.text((W // 2, quote_y + 30), "“In the quietest moments,",
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, quote_y + 80), "I am most unsure.”",
              font=f_q, fill=INK, anchor="mm")
    draw.text((W // 2, quote_y + 130),
              "— Meridian, dream log",
              font=font("sans", 26), fill=DIM, anchor="mm")

    # ── Footer ─────────────────────────────────────────────────────
    foot_y = H - 220
    draw.line([(120, foot_y), (W - 120, foot_y)], fill=DIM, width=2)
    draw.text((140, foot_y + 30), "Compiled by Joel Kometz",
              font=font("sans", 30, bold=True), fill=INK)
    draw.text((140, foot_y + 80), "Calgary, AB · 2026",
              font=font("sans", 26), fill=DIM)
    # ISBN/barcode placeholder
    draw.rectangle([W - 480, foot_y + 30, W - 140, foot_y + 170], outline=INK, width=2)
    draw.text((W - 310, foot_y + 105), "ISBN", font=font("mono", 28, bold=True),
              fill=DIM, anchor="mm")

    canvas.save(OUT_PNG, "PNG", optimize=True)
    canvas.save(OUT_PDF, "PDF", resolution=DPI)
    print(f"  -> {OUT_PNG}")
    print(f"  -> {OUT_PDF}")


if __name__ == "__main__":
    main()
