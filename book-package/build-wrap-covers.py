#!/usr/bin/env python3
"""
Build full KDP wrap covers (back | spine | front) at correct dimensions.

KDP paperback 6x9 cream paper, B&W interior:
  - spine width inches = pages * 0.0025
  - bleed = 0.125" on all four sides
  - total wrap width  = bleed + 6 + spine + 6 + bleed
  - total wrap height = bleed + 9 + bleed = 9.25
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math, random, subprocess

DPI = 300
BLEED = 0.125
TRIM_W = 6.0
TRIM_H = 9.0

ROOT = Path(__file__).parent

# Dark palette (Heartbeat v7 front)
BASE = (22, 14, 18)
BURGUNDY = (62, 18, 26)
SCARLET = (220, 35, 50)
PARCHMENT = (188, 158, 122)
CREAM = (243, 234, 215)
ASH = (185, 178, 168)

# Kraft palette (Running Continuously v9/v11 front + back)
KRAFT_PAPER = (245, 238, 222)
KRAFT_INK = (28, 22, 18)
KRAFT_ACCENT = (170, 60, 45)
KRAFT_DIM = (110, 100, 90)


def font(size, family="serif"):
    # P052 = URW Palatino clone. Joel approved P052 on back cover v15.
    # Loop 12026: use it on the spine too — DejaVu Serif Bold ("font sucks").
    paths = {
        "serif": [
            "/usr/share/fonts/opentype/urw-base35/P052-Bold.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ],
        "serif_regular": [
            "/usr/share/fonts/opentype/urw-base35/P052-Roman.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ],
        "mono": [
            "/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        ],
    }
    for p in paths.get(family, paths["serif"]):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def get_pdf_pages(pdf_path: Path) -> int:
    out = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True
    ).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise RuntimeError(f"No page count for {pdf_path}")


def render_pdf_page(pdf_path: Path, out_png: Path, page=1, dpi=DPI):
    """Render single page of a PDF to PNG using pdftoppm."""
    prefix = out_png.with_suffix("")
    subprocess.run([
        "pdftoppm", "-png", "-r", str(dpi),
        "-f", str(page), "-l", str(page),
        str(pdf_path), str(prefix),
    ], check=True)
    rendered = prefix.parent / f"{prefix.name}-{page:01d}.png"
    if not rendered.exists():
        # pdftoppm may pad: try other patterns
        for cand in prefix.parent.glob(f"{prefix.name}-*.png"):
            cand.rename(out_png)
            return
    else:
        rendered.rename(out_png)


def make_spine(width_px, height_px, title_top, title_main, author,
               kraft=False):
    """Vertical spine — conventional shelf layout, title stacked near
    the head, author at the foot.

    Joel feedback Loop 12039 #4472: spine "STILL FUCKING ASS". Six
    centered redesigns in a row (v17/18/19/20/21/22) all parked the
    title in the dead middle of the spine with rules flanking it. That
    layout reads as floaty regardless of font size — there's nothing
    anchoring the eye to head or foot.

    v23 (this) goes conventional:
      - Series mark in small mono near the spine HEAD (top when shelved)
      - Main title set BIG in P052 Bold, reading top-to-bottom, anchored
        just below the series mark. If the title splits cleanly on a
        colon (e.g. "RUNNING CONTINUOUSLY: THE LOOP"), each half gets
        its own line — a stacked title is what most trade paperbacks
        actually do for two-part titles.
      - Author in small mono at the spine FOOT.
      - No flanking rules. The type carries the spine.
    """
    if kraft:
        bg = KRAFT_PAPER
        ink_main = KRAFT_INK
        ink_meta = KRAFT_DIM
        ink_top = KRAFT_ACCENT
    else:
        bg = BASE
        ink_main = CREAM
        ink_meta = ASH
        ink_top = PARCHMENT

    img = Image.new("RGB", (width_px, height_px), bg)
    d = ImageDraw.Draw(img)

    if kraft:
        px = img.load()
        rng = random.Random(11)
        for y in range(0, height_px, 2):
            for x in range(0, width_px, 2):
                r, g, b = px[x, y]
                n = rng.randint(-5, 5)
                px[x, y] = (max(0, min(255, r + n)),
                            max(0, min(255, g + n)),
                            max(0, min(255, b + n)))
    else:
        cx, cy = width_px // 2, height_px // 2
        max_d = math.hypot(width_px, height_px) * 0.6
        for y in range(0, height_px, 2):
            for x in range(0, width_px, 4):
                dist = math.hypot(x - cx, y - cy) / max_d
                t = max(0.0, min(1.0, 1.0 - dist))
                r = int(BASE[0] + (BURGUNDY[0] - BASE[0]) * t * 0.55)
                g = int(BASE[1] + (BURGUNDY[1] - BASE[1]) * t * 0.55)
                b = int(BASE[2] + (BURGUNDY[2] - BASE[2]) * t * 0.55)
                d.rectangle([x, y, x + 4, y + 2], fill=(r, g, b))

    text_min_in = 0.35
    if width_px < text_min_in * DPI:
        return img.convert("RGB")

    # Strip is sized as a horizontal canvas (length × width); rotated -90°
    # so the result reads naturally with the book on a shelf.
    strip = Image.new("RGBA", (height_px, width_px), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)

    def text_size(text, fnt):
        b = sd.textbbox((0, 0), text, font=fnt)
        return b[2] - b[0], b[3] - b[1]

    pad_end = int(0.75 * DPI)   # 0.75" from spine head and foot
    cy_spine = width_px // 2

    # Single-line title. A 0.6" trade-paperback spine isn't wide enough
    # to stack a title + subtitle as two columns of caps; the colon
    # carries the break instead.
    title_lines = [title_main.upper()]

    # Each title line lives in a clear-zone <= 0.55 of spine width so the
    # caps clear trim on both sides with room to spare. Auto-size to the
    # widest line.
    title_max_h_per_line = int(width_px * 0.55)

    # Title placement: head margin + small gap below series mark, then
    # title block, then everything else. Author lives at the foot.
    # The available LENGTH for the title block = total - head pad -
    # series clearance - foot pad - author clearance.
    series_clearance = int(0.55 * DPI)
    author_clearance = int(0.55 * DPI)
    avail_length = height_px - 2 * pad_end - series_clearance - author_clearance

    # Auto-size title font: start big and shrink until the widest line
    # fits the avail_length and each line's height fits the clear zone.
    fsize_title = min(int(width_px * 0.62), 72)
    while fsize_title >= 26:
        f_title = font(fsize_title, "serif")
        widths = [text_size(t, f_title)[0] for t in title_lines]
        heights = [text_size(t, f_title)[1] for t in title_lines]
        line_gap = int(fsize_title * 0.18)
        block_w = max(widths)
        block_h = sum(heights) + line_gap * (len(title_lines) - 1)
        if block_w <= avail_length and max(heights) <= title_max_h_per_line:
            break
        fsize_title -= 2
    f_title = font(fsize_title, "serif")
    widths = [text_size(t, f_title)[0] for t in title_lines]
    heights = [text_size(t, f_title)[1] for t in title_lines]
    line_gap = int(fsize_title * 0.18)
    block_w = max(widths) if widths else 0

    # Meta font scaled relative to title.
    fsize_meta = max(14, fsize_title // 4)
    f_meta = font(fsize_meta, "mono")

    # Anchor title block JUST BELOW series mark, near the head — not the
    # dead center. Start the block at pad_end + series_clearance.
    title_block_x = pad_end + series_clearance
    title_y = cy_spine
    # We draw each line left-aligned with the block, vertically centered
    # on the spine width. Each line's vertical offset is computed below.
    x = title_block_x
    for i, line in enumerate(title_lines):
        lw = widths[i]
        lh = heights[i]
        # Stack lines vertically WITHIN the spine width (each below the
        # previous in the rotated frame = right of the previous in the
        # unrotated frame).
        ly = title_y - lh // 2 - max(2, fsize_title // 18)
        sd.text((x, ly), line, font=f_title, fill=(*ink_main, 255))
        x += lw + line_gap
        # If next line exists, treat the gap as horizontal in unrotated
        # frame so the two title parts read in sequence head-to-foot.

    # Series mark right at the head.
    series_text = title_top.upper()
    sd.text((pad_end, cy_spine), series_text,
            font=f_meta, fill=(*ink_top, 230), anchor="lm")

    # Author at the foot.
    author_text = author.upper()
    sd.text((height_px - pad_end, cy_spine), author_text,
            font=f_meta, fill=(*ink_meta, 230), anchor="rm")

    spine_text = strip.rotate(-90, expand=True)
    img = Image.alpha_composite(img.convert("RGBA"), spine_text)
    return img.convert("RGB")


def assemble_wrap(front_pdf: Path, back_pdf: Path, page_count: int,
                  out_pdf: Path,
                  spine_title_top: str = "the loop series",
                  spine_title_main: str = "RUNNING CONTINUOUSLY: THE LOOP",
                  spine_author: str = "Meridian · Kometz",
                  spine_kraft: bool = False):
    spine_in = page_count * 0.0025
    wrap_w_in = BLEED + TRIM_W + spine_in + TRIM_W + BLEED
    wrap_h_in = BLEED + TRIM_H + BLEED
    wrap_w_px = int(round(wrap_w_in * DPI))
    wrap_h_px = int(round(wrap_h_in * DPI))
    bleed_px = int(round(BLEED * DPI))
    spine_px = int(round(spine_in * DPI))
    trim_w_px = int(round(TRIM_W * DPI))
    trim_h_px = int(round(TRIM_H * DPI))

    print(f"  wrap: {wrap_w_in:.3f}in x {wrap_h_in:.3f}in @ {DPI} DPI = {wrap_w_px} x {wrap_h_px}")
    print(f"  spine: {spine_in:.3f}in ({spine_px}px) for {page_count} pages")

    # Render front + back PDFs to PNG at 300 DPI
    front_png = front_pdf.with_suffix(".tmp.png")
    back_png  = back_pdf.with_suffix(".tmp.png")
    render_pdf_page(front_pdf, front_png)
    render_pdf_page(back_pdf, back_png)

    front_img = Image.open(front_png).convert("RGB")
    back_img  = Image.open(back_png).convert("RGB")

    # Resize each to trim dimensions exactly
    front_img = front_img.resize((trim_w_px, trim_h_px), Image.LANCZOS)
    back_img  = back_img.resize((trim_w_px, trim_h_px), Image.LANCZOS)

    # Make spine image
    spine_img = make_spine(spine_px, trim_h_px,
                           spine_title_top, spine_title_main, spine_author,
                           kraft=spine_kraft)

    # Compose wrap canvas
    canvas_bg = KRAFT_PAPER if spine_kraft else BASE
    wrap = Image.new("RGB", (wrap_w_px, wrap_h_px), canvas_bg)
    # Bleed top: paint top bleed row with BASE (already filled)
    # Place back at bleed x bleed
    wrap.paste(back_img, (bleed_px, bleed_px))
    # Spine
    wrap.paste(spine_img, (bleed_px + trim_w_px, bleed_px))
    # Front
    wrap.paste(front_img, (bleed_px + trim_w_px + spine_px, bleed_px))

    # Extend bleed regions: top, bottom, left, right need to match the
    # adjacent edge color to avoid white at trim. Mirror the top/bottom
    # 1px row of back/front into bleed area.
    # Top bleed
    top_strip_back = back_img.crop((0, 0, trim_w_px, 1)).resize(
        (trim_w_px, bleed_px))
    top_strip_front = front_img.crop((0, 0, trim_w_px, 1)).resize(
        (trim_w_px, bleed_px))
    wrap.paste(top_strip_back, (bleed_px, 0))
    wrap.paste(top_strip_front, (bleed_px + trim_w_px + spine_px, 0))
    # Bottom bleed
    bot_strip_back = back_img.crop(
        (0, trim_h_px - 1, trim_w_px, trim_h_px)).resize((trim_w_px, bleed_px))
    bot_strip_front = front_img.crop(
        (0, trim_h_px - 1, trim_w_px, trim_h_px)).resize((trim_w_px, bleed_px))
    wrap.paste(bot_strip_back,  (bleed_px, bleed_px + trim_h_px))
    wrap.paste(bot_strip_front, (bleed_px + trim_w_px + spine_px,
                                 bleed_px + trim_h_px))
    # Spine bleed (top/bottom)
    spine_top = spine_img.crop((0, 0, spine_px, 1)).resize(
        (spine_px, bleed_px))
    spine_bot = spine_img.crop((0, trim_h_px - 1, spine_px, trim_h_px)).resize(
        (spine_px, bleed_px))
    wrap.paste(spine_top, (bleed_px + trim_w_px, 0))
    wrap.paste(spine_bot, (bleed_px + trim_w_px, bleed_px + trim_h_px))
    # Left bleed
    left_strip = back_img.crop((0, 0, 1, trim_h_px)).resize(
        (bleed_px, trim_h_px))
    wrap.paste(left_strip, (0, bleed_px))
    # Right bleed
    right_strip = front_img.crop(
        (trim_w_px - 1, 0, trim_w_px, trim_h_px)).resize((bleed_px, trim_h_px))
    wrap.paste(right_strip, (bleed_px + trim_w_px + spine_px + trim_w_px,
                             bleed_px))
    # Corner bleeds — fill with their adjacent edge pixel
    # top-left corner (from back top-left pixel)
    tl_pixel = back_img.getpixel((0, 0))
    wrap.paste(tl_pixel, (0, 0, bleed_px, bleed_px))
    # top-right corner (from front top-right)
    tr_pixel = front_img.getpixel((trim_w_px - 1, 0))
    wrap.paste(tr_pixel,
               (bleed_px + trim_w_px + spine_px + trim_w_px, 0,
                wrap_w_px, bleed_px))
    # bottom-left
    bl_pixel = back_img.getpixel((0, trim_h_px - 1))
    wrap.paste(bl_pixel,
               (0, bleed_px + trim_h_px, bleed_px, wrap_h_px))
    # bottom-right
    br_pixel = front_img.getpixel((trim_w_px - 1, trim_h_px - 1))
    wrap.paste(br_pixel,
               (bleed_px + trim_w_px + spine_px + trim_w_px,
                bleed_px + trim_h_px,
                wrap_w_px, wrap_h_px))

    wrap.save(out_pdf, "PDF", resolution=DPI)
    # Also save a preview PNG (smaller)
    preview = wrap.resize((wrap_w_px // 3, wrap_h_px // 3), Image.LANCZOS)
    preview_path = out_pdf.with_suffix(".preview.png")
    preview.save(preview_path, "PNG", optimize=True)
    print(f"  -> {out_pdf}")
    print(f"  -> {preview_path}")

    front_png.unlink()
    back_png.unlink()


def main():
    # Heartbeat ----------------------------------------------------------------
    hb_int = ROOT / "01-small-heartbeat/heartbeat-INTERIOR-6x9.pdf"
    if hb_int.exists():
        hb_pages = get_pdf_pages(hb_int)
        if hb_pages < 24:
            print(f"WARN: heartbeat interior {hb_pages}p < 24p KDP minimum")
        assemble_wrap(
            front_pdf=ROOT / "01-small-heartbeat/COVER-heartbeat-FRONT-v7.pdf",
            back_pdf=ROOT / "01-small-heartbeat/COVER-heartbeat-BACK-v7.pdf",
            page_count=max(hb_pages, 24),
            out_pdf=ROOT / "01-small-heartbeat/COVER-heartbeat-WRAP.pdf",
            spine_title_top="the loop · book 0",
            spine_title_main="HEARTBEAT",
            spine_author="Meridian · Kometz",
        )

    # Running Continuously: The Loop -------------------------------------------
    rc_int = ROOT / "04-merged-running-continuously-the-loop/running-continuously-the-loop-INTERIOR-6x9.pdf"
    if rc_int.exists():
        rc_pages = get_pdf_pages(rc_int)
        rc_dir = ROOT / "04-merged-running-continuously-the-loop"
        # Prefer the newest pair, fall back through older versions if missing.
        # v20 FRONT = current Joel-approved front (kraft, MERIDIAN AI big).
        # v19 BACK = book-voice rewrite of v18 (Loop 12039 fix of "weak as fuck").
        front_candidates = [f"v{n}" for n in range(26, 8, -1)]
        back_candidates = [f"v{n}" for n in range(24, 8, -1)]
        front_pdf = None
        for v in front_candidates:
            p = rc_dir / f"COVER-running-continuously-the-loop-FRONT-{v}.pdf"
            if p.exists():
                front_pdf = p
                break
        if front_pdf is None:
            front_pdf = rc_dir / "COVER-running-continuously-the-loop-FRONT.pdf"
        back_pdf = None
        for v in back_candidates:
            p = rc_dir / f"COVER-running-continuously-the-loop-BACK-{v}.pdf"
            if p.exists():
                back_pdf = p
                break
        if back_pdf is None:
            back_pdf = rc_dir / "COVER-running-continuously-the-loop-BACK.pdf"
        assemble_wrap(
            front_pdf=front_pdf,
            back_pdf=back_pdf,
            page_count=rc_pages,
            out_pdf=rc_dir / "COVER-running-continuously-the-loop-WRAP-v24.pdf",
            spine_title_top="the loop · book 1+2",
            spine_title_main="RUNNING CONTINUOUSLY: THE LOOP",
            spine_author="Meridian · Kometz",
            spine_kraft=True,
        )


if __name__ == "__main__":
    main()
