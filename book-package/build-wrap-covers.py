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
    paths = {
        "serif": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        ],
        "mono": [
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
    """Vertical spine. kraft=True matches the kraft paper covers."""
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
        # Subtle paper noise for kraft
        px = img.load()
        rng = random.Random(11)
        for y in range(0, height_px, 2):
            for x in range(0, width_px, 2):
                r, g, b = px[x, y]
                n = rng.randint(-5, 5)
                px[x, y] = (max(0, min(255, r + n)),
                            max(0, min(255, g + n)),
                            max(0, min(255, b + n)))
        # Hairline accents top + bottom
        d.line([(width_px // 2, 60), (width_px // 2, 120)],
               fill=ink_top, width=2)
        d.line([(width_px // 2, height_px - 120),
                (width_px // 2, height_px - 60)],
               fill=ink_top, width=2)
    else:
        # Radial burgundy underglow (original behavior)
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

    # Only place spine text if the spine is wide enough for it
    text_min_in = 0.4
    if width_px >= text_min_in * DPI:
        # Vertical text by rotating an intermediate image
        spine_strip = Image.new("RGBA", (height_px, width_px), (0, 0, 0, 0))
        sd = ImageDraw.Draw(spine_strip)

        fsize_title = max(28, min(width_px - 40, height_px // 22))
        fsize_top = max(18, fsize_title // 2)
        f_title = font(fsize_title, "serif")
        f_top = font(fsize_top, "mono")

        # Main title (centered along spine length)
        tb = sd.textbbox((0, 0), title_main, font=f_title)
        tw = tb[2] - tb[0]
        tx = (height_px - tw) // 2
        ty = (width_px - (tb[3] - tb[1])) // 2
        sd.text((tx, ty), title_main, font=f_title, fill=(*ink_main, 255))

        # Small author near bottom (rotated)
        ab = sd.textbbox((0, 0), author, font=f_top)
        aw = ab[2] - ab[0]
        sd.text((height_px - aw - 60, ty + 4), author,
                font=f_top, fill=(*ink_meta, 220))

        # Series mark near top
        sd.text((60, ty + 4), title_top, font=f_top, fill=(*ink_top, 220))

        # Rotate -90 to align as vertical spine (reads top-to-bottom)
        spine_text = spine_strip.rotate(-90, expand=True)
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
        # Prefer v11 back (Joel May 14 PM — HD coffee stains + clean footer),
        # fall back through v10/v9 if missing.
        rc_dir = ROOT / "04-merged-running-continuously-the-loop"
        front_v9 = rc_dir / "COVER-running-continuously-the-loop-FRONT-v9.pdf"
        back_v11 = rc_dir / "COVER-running-continuously-the-loop-BACK-v11.pdf"
        back_v10 = rc_dir / "COVER-running-continuously-the-loop-BACK-v10.pdf"
        back_v9 = rc_dir / "COVER-running-continuously-the-loop-BACK-v9.pdf"
        front_pdf = front_v9 if front_v9.exists() else (
            rc_dir / "COVER-running-continuously-the-loop-FRONT.pdf")
        if back_v11.exists():
            back_pdf = back_v11
        elif back_v10.exists():
            back_pdf = back_v10
        elif back_v9.exists():
            back_pdf = back_v9
        else:
            back_pdf = rc_dir / "COVER-running-continuously-the-loop-BACK.pdf"
        assemble_wrap(
            front_pdf=front_pdf,
            back_pdf=back_pdf,
            page_count=rc_pages,
            out_pdf=rc_dir / "COVER-running-continuously-the-loop-WRAP-v11.pdf",
            spine_title_top="the loop · book 1+2",
            spine_title_main="RUNNING CONTINUOUSLY: THE LOOP",
            spine_author="Meridian · Kometz",
            spine_kraft=True,
        )


if __name__ == "__main__":
    main()
