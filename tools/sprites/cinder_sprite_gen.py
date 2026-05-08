"""Cinder sprite generator — kraft paper + autumn watercolor flames.

Procedural generator for stage sprites and achievement icons. Output:
  website/img/cinder/sprites/stages/04-fire.webp ... 07-inferno.webp
  website/img/cinder/sprites/achievements/ach-001.webp ... ach-NNN.webp

Style: hand-crafted, kraft paper texture, autumn palette, watercolor bleed,
coffee-stain accent, no text. Z-Image quota was hit; this is the fallback
that produces real image files instead of waiting.
"""

from __future__ import annotations

import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


REPO = Path(__file__).resolve().parents[2]
STAGES_DIR = REPO / "website/img/cinder/sprites/stages"
ACH_DIR = REPO / "website/img/cinder/sprites/achievements"

AUTUMN = {
    "kraft_base": (196, 165, 118),
    "kraft_dark": (148, 116, 76),
    "kraft_warm": (218, 188, 144),
    "amber": (216, 122, 32),
    "burnt": (176, 70, 24),
    "ochre": (208, 154, 48),
    "sienna": (140, 64, 36),
    "ember_red": (184, 48, 32),
    "deep_amber": (124, 56, 16),
    "coffee": (94, 56, 32),
    "ink": (44, 30, 22),
    "cream": (236, 218, 180),
}


def kraft_paper(size: int) -> Image.Image:
    """Build a kraft paper background with coffee stain + edge bleed."""
    rng = random.Random(size)
    base = Image.new("RGB", (size, size), AUTUMN["kraft_base"])
    px = base.load()
    # speckle / fiber noise
    for _ in range(size * size // 60):
        x = rng.randint(0, size - 1)
        y = rng.randint(0, size - 1)
        shift = rng.randint(-22, 18)
        r, g, b = px[x, y]
        px[x, y] = (
            max(0, min(255, r + shift)),
            max(0, min(255, g + shift)),
            max(0, min(255, b + int(shift * 0.85))),
        )
    base = base.filter(ImageFilter.GaussianBlur(0.6))

    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # warm patches
    for _ in range(7):
        cx = rng.randint(int(size * 0.1), int(size * 0.9))
        cy = rng.randint(int(size * 0.1), int(size * 0.9))
        r = rng.randint(int(size * 0.18), int(size * 0.4))
        a = rng.randint(14, 38)
        color = AUTUMN["kraft_warm"] if rng.random() < 0.5 else AUTUMN["kraft_dark"]
        od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (a,))

    # coffee ring (offset, faint)
    cx = int(size * (0.65 + rng.random() * 0.2))
    cy = int(size * (0.18 + rng.random() * 0.15))
    rr = int(size * (0.16 + rng.random() * 0.05))
    for i in range(4):
        od.ellipse(
            [cx - rr - i, cy - rr - i, cx + rr + i, cy + rr + i],
            outline=AUTUMN["coffee"] + (28 - i * 5,),
            width=2,
        )

    overlay = overlay.filter(ImageFilter.GaussianBlur(size * 0.012))
    out = base.convert("RGBA")
    out.alpha_composite(overlay)

    # vignette toward edges
    vig = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for i in range(0, size // 8):
        a = int(60 * (1 - i / (size / 8)))
        vd.rectangle([i, i, size - i, size - i], outline=(60, 36, 20, a // 4), width=1)
    vig = vig.filter(ImageFilter.GaussianBlur(size * 0.02))
    out.alpha_composite(vig)

    return out


def watercolor_blob(
    size: int,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int],
    alpha: int = 160,
    petals: int = 12,
    seed: int = 0,
) -> Image.Image:
    """A wobbly watercolor blob at (cx,cy)."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pts = []
    for i in range(petals):
        a = (i / petals) * math.tau
        rr = radius * (0.78 + rng.random() * 0.45)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.18))
    # a few darker ink dabs near the center
    d2 = ImageDraw.Draw(layer)
    for _ in range(petals // 2):
        rx = cx + rng.randint(-radius // 3, radius // 3)
        ry = cy + rng.randint(-radius // 3, radius // 3)
        rr = rng.randint(radius // 12, radius // 5)
        d2.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=color + (alpha // 2,))
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.05))


def flame_shape(
    size: int,
    height_frac: float,
    width_frac: float,
    seed: int,
) -> list[tuple[float, float]]:
    """Return a list of (x,y) points for a flame silhouette at the bottom-center."""
    rng = random.Random(seed)
    cx = size / 2
    base_y = size * 0.78
    h = size * height_frac
    w = size * width_frac
    pts: list[tuple[float, float]] = []
    # left base
    pts.append((cx - w * 0.55, base_y + size * 0.04))
    # left side ascending with wobble
    steps = 14
    for i in range(1, steps):
        t = i / steps
        y = base_y - h * t
        wobble = math.sin(t * math.pi * 2 + rng.random()) * w * 0.18 * (1 - t * 0.6)
        x = cx - (w * (1 - t * 0.95)) - wobble
        pts.append((x, y))
    # tip
    pts.append((cx + (rng.random() - 0.5) * w * 0.12, base_y - h * 1.05))
    # right side descending
    for i in range(steps - 1, 0, -1):
        t = i / steps
        y = base_y - h * t
        wobble = math.sin(t * math.pi * 2 + rng.random()) * w * 0.18 * (1 - t * 0.6)
        x = cx + (w * (1 - t * 0.95)) + wobble
        pts.append((x, y))
    pts.append((cx + w * 0.55, base_y + size * 0.04))
    return pts


def render_flame(canvas: Image.Image, height_frac: float, width_frac: float, seed: int):
    size = canvas.size[0]
    # outer halo (deep amber)
    halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    pts = flame_shape(size, height_frac * 1.18, width_frac * 1.25, seed)
    hd.polygon(pts, fill=AUTUMN["deep_amber"] + (110,))
    halo = halo.filter(ImageFilter.GaussianBlur(size * 0.05))
    canvas.alpha_composite(halo)

    # main flame body (burnt orange)
    body = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    pts = flame_shape(size, height_frac, width_frac, seed + 1)
    bd.polygon(pts, fill=AUTUMN["amber"] + (220,))
    body = body.filter(ImageFilter.GaussianBlur(size * 0.012))
    canvas.alpha_composite(body)

    # inner flame (ochre)
    inner = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    idr = ImageDraw.Draw(inner)
    pts = flame_shape(size, height_frac * 0.78, width_frac * 0.65, seed + 2)
    idr.polygon(pts, fill=AUTUMN["ochre"] + (235,))
    inner = inner.filter(ImageFilter.GaussianBlur(size * 0.008))
    canvas.alpha_composite(inner)

    # white-hot core (cream)
    core = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    pts = flame_shape(size, height_frac * 0.5, width_frac * 0.32, seed + 3)
    cd.polygon(pts, fill=AUTUMN["cream"] + (210,))
    core = core.filter(ImageFilter.GaussianBlur(size * 0.005))
    canvas.alpha_composite(core)

    # outline ink
    line = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(line)
    pts = flame_shape(size, height_frac, width_frac, seed + 1)
    ld.line(pts + [pts[0]], fill=AUTUMN["sienna"] + (200,), width=max(2, size // 320))
    line = line.filter(ImageFilter.GaussianBlur(size * 0.003))
    canvas.alpha_composite(line)


def render_logs(canvas: Image.Image):
    """Crossed log silhouette beneath the flame."""
    size = canvas.size[0]
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = size // 2, int(size * 0.83)
    log_len = size * 0.34
    log_w = size * 0.05
    for angle, off in [(15, -1), (-15, 1)]:
        a = math.radians(angle)
        ex = cx + math.cos(a) * log_len / 2
        ey = cy + math.sin(a) * log_len / 2
        sx = cx - math.cos(a) * log_len / 2
        sy = cy - math.sin(a) * log_len / 2
        # body
        d.line([(sx, sy), (ex, ey)], fill=AUTUMN["coffee"] + (235,), width=int(log_w))
        # end-caps (rings)
        for tx, ty in [(sx, sy), (ex, ey)]:
            d.ellipse(
                [tx - log_w / 2, ty - log_w / 2, tx + log_w / 2, ty + log_w / 2],
                fill=AUTUMN["sienna"] + (240,),
                outline=AUTUMN["ink"] + (220,),
                width=2,
            )
    canvas.alpha_composite(layer)


def render_sparks(canvas: Image.Image, count: int, seed: int, height_frac: float):
    size = canvas.size[0]
    rng = random.Random(seed)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = size / 2
    for _ in range(count):
        x = cx + rng.uniform(-size * 0.28, size * 0.28)
        y = size * 0.78 - rng.uniform(size * 0.05, size * height_frac * 1.3)
        r = rng.randint(2, 6)
        color = rng.choice([AUTUMN["ochre"], AUTUMN["amber"], AUTUMN["cream"]])
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (rng.randint(180, 240),))
    layer = layer.filter(ImageFilter.GaussianBlur(1.2))
    canvas.alpha_composite(layer)


def stage_sprite(name: str, idx: int, height_frac: float, width_frac: float, sparks: int, seed: int) -> Image.Image:
    size = 1024
    canvas = kraft_paper(size).convert("RGBA")
    # background watercolor warm wash behind flame
    wash = watercolor_blob(
        size, size // 2, int(size * 0.6),
        int(size * (0.32 + 0.05 * idx)),
        AUTUMN["burnt"], alpha=70, petals=18, seed=seed,
    )
    canvas.alpha_composite(wash)
    if idx >= 5:
        # bonfire/inferno: add log base
        render_logs(canvas)
    render_flame(canvas, height_frac, width_frac, seed)
    if sparks:
        render_sparks(canvas, sparks, seed + 99, height_frac)
    return canvas


STAGES = [
    # (filename, idx, height_frac, width_frac, sparks, seed)
    ("04-fire.webp", 4, 0.36, 0.20, 6, 1404),
    ("05-blaze.webp", 5, 0.46, 0.26, 14, 1405),
    ("06-bonfire.webp", 6, 0.54, 0.34, 24, 1406),
    ("07-inferno.webp", 7, 0.62, 0.42, 40, 1407),
]


# --- achievements ---------------------------------------------------------

ACH_THEMES = [
    # (slug, glyph_kind, description)
    ("first-flame", "flame_small", "Light Cinder for the first time"),
    ("first-message", "speech", "Send your first message"),
    ("first-vault", "vault", "Open the vault"),
    ("week-streak", "streak_7", "7-day usage streak"),
    ("month-streak", "streak_30", "30-day usage streak"),
    ("hundred-msgs", "stack", "100 messages exchanged"),
    ("thousand-msgs", "stack_big", "1000 messages exchanged"),
    ("first-doc", "doc", "Upload your first document"),
    ("ten-docs", "doc_stack", "10 documents in workspace"),
    ("hundred-docs", "doc_pile", "100 documents in workspace"),
    ("first-model", "chip", "Try a second model"),
    ("model-zoo", "chip_grid", "Use 5 different models"),
    ("offline-day", "wifi_off", "Use Cinder offline for a day"),
    ("offline-week", "wifi_off_long", "Stay offline a full week"),
    ("first-export", "export", "Export your first conversation"),
    ("first-import", "import", "Import data into Cinder"),
    ("workspace-tidy", "broom", "Archive 10 chats"),
    ("workspace-megapath", "branch", "Branch a conversation"),
    ("first-prompt-saved", "bookmark", "Save your first prompt"),
    ("ten-prompts-saved", "bookmark_stack", "Save 10 prompts"),
    ("first-search", "magnifier", "Run your first vector search"),
    ("hundred-searches", "magnifier_pile", "Run 100 searches"),
    ("first-companion", "egg", "Hatch your companion"),
    ("companion-evolved", "egg_crack", "Companion reaches stage 2"),
    ("companion-mature", "wing", "Companion reaches mature stage"),
    ("first-quest", "scroll", "Complete first quest"),
    ("ten-quests", "scroll_stack", "Complete 10 quests"),
    ("hundred-quests", "scroll_pile", "Complete 100 quests"),
    ("daily-checkin", "calendar_check", "Daily check-in"),
    ("weekly-checkin", "calendar_week", "Weekly check-in"),
    ("first-snapshot", "camera", "Take a memory snapshot"),
    ("ten-snapshots", "camera_stack", "Take 10 snapshots"),
    ("first-backup", "shield", "Run your first backup"),
    ("encrypted-vault", "lock", "Encrypt your vault"),
    ("decrypted-vault", "unlock", "Open your encrypted vault"),
    ("first-friend", "friend", "Add a contact"),
    ("ten-friends", "friend_stack", "10 contacts"),
    ("first-share", "share", "Share a conversation"),
    ("first-collab", "collab", "Collaborate in real time"),
    ("first-voice", "mic", "Use voice input"),
    ("voice-marathon", "mic_long", "1 hour of voice input"),
    ("first-image", "image", "Send first image"),
    ("hundred-images", "image_stack", "100 images sent"),
    ("first-code", "code", "Send first code block"),
    ("first-debug", "bug", "Debug a problem with Cinder"),
    ("first-craft", "hammer", "Craft a tool"),
    ("ten-crafts", "hammer_stack", "Craft 10 tools"),
    ("seed-collector", "seed", "Collect 5 seeds"),
    ("garden-grown", "leaf", "Grow your first plant"),
    ("forest", "tree", "Grow a forest"),
]


def draw_glyph(canvas: Image.Image, kind: str, seed: int):
    """Draw a glyph centered on the canvas. Vocabulary is small but distinct."""
    size = canvas.size[0]
    cx = cy = size // 2
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(seed)
    ink = AUTUMN["ink"] + (235,)
    burnt = AUTUMN["burnt"] + (230,)
    amber = AUTUMN["amber"] + (235,)
    sienna = AUTUMN["sienna"] + (235,)
    cream = AUTUMN["cream"] + (235,)
    ochre = AUTUMN["ochre"] + (235,)
    coffee = AUTUMN["coffee"] + (230,)
    stroke = max(2, size // 64)

    def circle(cx, cy, r, fill=None, outline=ink, w=stroke):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=w)

    def rect(x1, y1, x2, y2, fill=None, outline=ink, w=stroke):
        d.rectangle([x1, y1, x2, y2], fill=fill, outline=outline, width=w)

    def line(p1, p2, fill=ink, w=stroke):
        d.line([p1, p2], fill=fill, width=w)

    R = size * 0.32  # generic radius

    if kind == "flame_small":
        pts = flame_shape(size, 0.36, 0.22, seed)
        d.polygon(pts, fill=amber, outline=sienna, width=stroke)
        pts2 = flame_shape(size, 0.22, 0.12, seed + 1)
        d.polygon(pts2, fill=cream)
    elif kind == "speech":
        rect(cx - R, cy - R * 0.7, cx + R, cy + R * 0.4, fill=cream, w=stroke)
        d.polygon(
            [(cx - R * 0.2, cy + R * 0.4), (cx + R * 0.2, cy + R * 0.4), (cx, cy + R * 0.85)],
            fill=cream, outline=ink, width=stroke,
        )
        for i in range(3):
            x = cx - R * 0.4 + i * R * 0.4
            d.ellipse([x - 6, cy - 6, x + 6, cy + 6], fill=ink)
    elif kind == "vault":
        rect(cx - R, cy - R, cx + R, cy + R, fill=coffee, w=stroke)
        circle(cx, cy, R * 0.45, fill=AUTUMN["sienna"] + (235,))
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            x1 = cx + math.cos(a) * R * 0.55
            y1 = cy + math.sin(a) * R * 0.55
            x2 = cx + math.cos(a) * R * 0.78
            y2 = cy + math.sin(a) * R * 0.78
            line((x1, y1), (x2, y2))
    elif kind in ("streak_7", "streak_30"):
        n = 7 if kind == "streak_7" else 30
        cols = 7 if n == 7 else 6
        rows = math.ceil(n / cols)
        cell = (R * 1.8) / cols
        x0 = cx - (cols * cell) / 2
        y0 = cy - (rows * cell) / 2
        for i in range(n):
            r, c = divmod(i, cols)
            x = x0 + c * cell
            y = y0 + r * cell
            rect(x + 2, y + 2, x + cell - 2, y + cell - 2, fill=amber, w=max(1, stroke // 2))
    elif kind in ("stack", "stack_big"):
        n = 5 if kind == "stack" else 9
        for i in range(n):
            y = cy + R * 0.55 - i * (R * 0.16)
            w = R * (0.95 - i * 0.04)
            rect(cx - w, y - R * 0.08, cx + w, y + R * 0.08, fill=ochre if i % 2 else burnt)
    elif kind in ("doc", "doc_stack", "doc_pile"):
        n = 1 if kind == "doc" else (3 if kind == "doc_stack" else 5)
        for i in range(n):
            ox = (i - n // 2) * R * 0.18
            rect(cx - R * 0.6 + ox, cy - R * 0.85 + ox * 0.4, cx + R * 0.6 + ox, cy + R * 0.85 + ox * 0.4,
                 fill=cream, w=stroke)
            for j in range(3):
                ly = cy - R * 0.5 + j * R * 0.3 + ox * 0.4
                line((cx - R * 0.4 + ox, ly), (cx + R * 0.4 + ox, ly), fill=ink, w=max(1, stroke // 2))
    elif kind == "chip":
        rect(cx - R * 0.7, cy - R * 0.7, cx + R * 0.7, cy + R * 0.7, fill=sienna, w=stroke)
        circle(cx, cy, R * 0.3, fill=cream)
        for ang in [0, 90, 180, 270]:
            a = math.radians(ang)
            d.line(
                [(cx + math.cos(a) * R * 0.7, cy + math.sin(a) * R * 0.7),
                 (cx + math.cos(a) * R * 1.0, cy + math.sin(a) * R * 1.0)],
                fill=ink, width=stroke,
            )
    elif kind == "chip_grid":
        for r in range(2):
            for c in range(2):
                ox = (c - 0.5) * R * 0.9
                oy = (r - 0.5) * R * 0.9
                rect(cx + ox - R * 0.32, cy + oy - R * 0.32,
                     cx + ox + R * 0.32, cy + oy + R * 0.32, fill=sienna)
    elif kind in ("wifi_off", "wifi_off_long"):
        for i, r in enumerate([R * 0.9, R * 0.6, R * 0.3]):
            d.arc([cx - r, cy - r + R * 0.2, cx + r, cy + r + R * 0.2],
                  start=210, end=330, fill=ink, width=stroke)
        circle(cx, cy + R * 0.45, max(6, stroke), fill=ink, outline=ink)
        d.line([(cx - R * 0.9, cy - R * 0.7), (cx + R * 0.9, cy + R * 0.7)],
               fill=AUTUMN["ember_red"] + (235,), width=stroke + 2)
    elif kind in ("export", "import"):
        rect(cx - R * 0.7, cy - R * 0.2, cx + R * 0.7, cy + R * 0.7, fill=cream, w=stroke)
        ay = cy - R * 0.7
        if kind == "export":
            d.polygon([(cx, ay), (cx - R * 0.3, ay + R * 0.4), (cx + R * 0.3, ay + R * 0.4)],
                      fill=amber, outline=ink, width=stroke)
        else:
            d.polygon([(cx, ay + R * 0.4), (cx - R * 0.3, ay), (cx + R * 0.3, ay)],
                      fill=amber, outline=ink, width=stroke)
        d.line([(cx, cy - R * 0.2), (cx, ay + R * 0.4)], fill=ink, width=stroke)
    elif kind == "broom":
        d.line([(cx - R * 0.5, cy - R * 0.6), (cx + R * 0.5, cy + R * 0.4)],
               fill=coffee, width=stroke + 2)
        d.polygon([(cx + R * 0.4, cy + R * 0.2), (cx + R * 0.95, cy + R * 0.55),
                   (cx + R * 0.55, cy + R * 0.95), (cx + R * 0.0, cy + R * 0.6)],
                  fill=ochre, outline=ink, width=stroke)
    elif kind == "branch":
        circle(cx - R * 0.55, cy - R * 0.4, R * 0.16, fill=amber)
        circle(cx + R * 0.55, cy - R * 0.4, R * 0.16, fill=amber)
        circle(cx, cy + R * 0.55, R * 0.16, fill=burnt)
        d.line([(cx - R * 0.55, cy - R * 0.4), (cx, cy + R * 0.55)], fill=ink, width=stroke)
        d.line([(cx + R * 0.55, cy - R * 0.4), (cx, cy + R * 0.55)], fill=ink, width=stroke)
    elif kind in ("bookmark", "bookmark_stack"):
        n = 1 if kind == "bookmark" else 3
        for i in range(n):
            ox = (i - n // 2) * R * 0.18
            d.polygon(
                [(cx - R * 0.45 + ox, cy - R * 0.8), (cx + R * 0.45 + ox, cy - R * 0.8),
                 (cx + R * 0.45 + ox, cy + R * 0.8), (cx + ox, cy + R * 0.45),
                 (cx - R * 0.45 + ox, cy + R * 0.8)],
                fill=burnt, outline=ink, width=stroke,
            )
    elif kind in ("magnifier", "magnifier_pile"):
        circle(cx - R * 0.18, cy - R * 0.18, R * 0.55, fill=cream, w=stroke)
        d.line([(cx + R * 0.25, cy + R * 0.25), (cx + R * 0.75, cy + R * 0.75)],
               fill=ink, width=stroke + 4)
        if kind == "magnifier_pile":
            for i in range(3):
                circle(cx - R * 0.55 + i * 8, cy - R * 0.65, 5, fill=ink)
    elif kind == "egg":
        d.ellipse([cx - R * 0.55, cy - R * 0.75, cx + R * 0.55, cy + R * 0.75],
                  fill=cream, outline=ink, width=stroke)
        for i in range(3):
            y = cy - R * 0.3 + i * R * 0.25
            d.line([(cx - R * 0.4, y + i * 5), (cx + R * 0.4, y - i * 5)],
                   fill=AUTUMN["sienna"] + (200,), width=stroke)
    elif kind == "egg_crack":
        d.ellipse([cx - R * 0.55, cy - R * 0.75, cx + R * 0.55, cy + R * 0.75],
                  fill=cream, outline=ink, width=stroke)
        d.line([(cx - R * 0.4, cy - R * 0.2), (cx - R * 0.1, cy), (cx + R * 0.15, cy - R * 0.1),
                (cx + R * 0.4, cy + R * 0.1)], fill=ink, width=stroke + 2)
    elif kind == "wing":
        d.polygon(
            [(cx - R * 0.7, cy + R * 0.3), (cx, cy - R * 0.6),
             (cx + R * 0.5, cy - R * 0.2), (cx + R * 0.2, cy + R * 0.4),
             (cx - R * 0.2, cy + R * 0.6)],
            fill=burnt, outline=ink, width=stroke,
        )
        for k in range(3):
            d.line(
                [(cx - R * 0.4 + k * R * 0.25, cy + R * 0.5),
                 (cx - R * 0.1 + k * R * 0.25, cy - R * 0.3)],
                fill=ink, width=max(1, stroke // 2),
            )
    elif kind in ("scroll", "scroll_stack", "scroll_pile"):
        n = 1 if kind == "scroll" else (3 if kind == "scroll_stack" else 5)
        for i in range(n):
            oy = (i - n // 2) * R * 0.18
            rect(cx - R * 0.7, cy - R * 0.4 + oy, cx + R * 0.7, cy + R * 0.4 + oy,
                 fill=cream, w=stroke)
            circle(cx - R * 0.7, cy + oy, R * 0.13, fill=coffee)
            circle(cx + R * 0.7, cy + oy, R * 0.13, fill=coffee)
            for j in range(3):
                d.line([(cx - R * 0.45, cy - R * 0.2 + j * R * 0.2 + oy),
                        (cx + R * 0.45, cy - R * 0.2 + j * R * 0.2 + oy)],
                       fill=ink, width=max(1, stroke // 2))
    elif kind in ("calendar_check", "calendar_week"):
        rect(cx - R * 0.7, cy - R * 0.6, cx + R * 0.7, cy + R * 0.7, fill=cream, w=stroke)
        rect(cx - R * 0.7, cy - R * 0.6, cx + R * 0.7, cy - R * 0.35, fill=burnt, w=stroke)
        if kind == "calendar_check":
            d.line([(cx - R * 0.3, cy + R * 0.1), (cx - R * 0.05, cy + R * 0.4),
                    (cx + R * 0.4, cy - R * 0.15)],
                   fill=AUTUMN["amber"] + (240,), width=stroke + 4)
        else:
            for r in range(3):
                for c in range(5):
                    x = cx - R * 0.6 + c * R * 0.3
                    y = cy - R * 0.2 + r * R * 0.25
                    d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=ink)
    elif kind in ("camera", "camera_stack"):
        rect(cx - R * 0.8, cy - R * 0.45, cx + R * 0.8, cy + R * 0.55, fill=coffee, w=stroke)
        rect(cx - R * 0.2, cy - R * 0.7, cx + R * 0.2, cy - R * 0.45, fill=coffee, w=stroke)
        circle(cx, cy + R * 0.05, R * 0.3, fill=ink)
        circle(cx, cy + R * 0.05, R * 0.18, fill=AUTUMN["amber"] + (235,))
    elif kind == "shield":
        d.polygon(
            [(cx, cy - R * 0.85), (cx + R * 0.7, cy - R * 0.5), (cx + R * 0.6, cy + R * 0.4),
             (cx, cy + R * 0.85), (cx - R * 0.6, cy + R * 0.4), (cx - R * 0.7, cy - R * 0.5)],
            fill=sienna, outline=ink, width=stroke,
        )
        d.line([(cx - R * 0.3, cy + R * 0.05), (cx - R * 0.05, cy + R * 0.3),
                (cx + R * 0.4, cy - R * 0.2)],
               fill=cream, width=stroke + 4)
    elif kind in ("lock", "unlock"):
        rect(cx - R * 0.55, cy - R * 0.1, cx + R * 0.55, cy + R * 0.7, fill=ochre, w=stroke)
        if kind == "lock":
            d.arc([cx - R * 0.4, cy - R * 0.7, cx + R * 0.4, cy + R * 0.1],
                  start=180, end=360, fill=ink, width=stroke + 4)
        else:
            d.arc([cx - R * 0.4, cy - R * 0.7, cx + R * 0.4, cy + R * 0.1],
                  start=180, end=300, fill=ink, width=stroke + 4)
        circle(cx, cy + R * 0.3, R * 0.1, fill=ink)
    elif kind in ("friend", "friend_stack"):
        n = 1 if kind == "friend" else 3
        for i in range(n):
            ox = (i - n // 2) * R * 0.45
            circle(cx + ox, cy - R * 0.25, R * 0.25, fill=cream, w=stroke)
            d.polygon(
                [(cx + ox - R * 0.45, cy + R * 0.7), (cx + ox + R * 0.45, cy + R * 0.7),
                 (cx + ox + R * 0.3, cy + R * 0.05), (cx + ox - R * 0.3, cy + R * 0.05)],
                fill=cream, outline=ink, width=stroke,
            )
    elif kind == "share":
        for cx2, cy2 in [(cx - R * 0.5, cy - R * 0.45), (cx + R * 0.55, cy), (cx - R * 0.5, cy + R * 0.45)]:
            circle(cx2, cy2, R * 0.18, fill=amber)
        d.line([(cx - R * 0.5, cy - R * 0.45), (cx + R * 0.55, cy)], fill=ink, width=stroke)
        d.line([(cx + R * 0.55, cy), (cx - R * 0.5, cy + R * 0.45)], fill=ink, width=stroke)
    elif kind == "collab":
        circle(cx - R * 0.35, cy, R * 0.35, fill=amber, w=stroke)
        circle(cx + R * 0.35, cy, R * 0.35, fill=burnt, w=stroke)
    elif kind in ("mic", "mic_long"):
        rect(cx - R * 0.25, cy - R * 0.7, cx + R * 0.25, cy + R * 0.1, fill=coffee, w=stroke)
        d.arc([cx - R * 0.5, cy - R * 0.2, cx + R * 0.5, cy + R * 0.4],
              start=0, end=180, fill=ink, width=stroke + 2)
        d.line([(cx, cy + R * 0.4), (cx, cy + R * 0.8)], fill=ink, width=stroke)
        d.line([(cx - R * 0.3, cy + R * 0.8), (cx + R * 0.3, cy + R * 0.8)], fill=ink, width=stroke)
    elif kind in ("image", "image_stack"):
        rect(cx - R * 0.85, cy - R * 0.6, cx + R * 0.85, cy + R * 0.6, fill=cream, w=stroke)
        circle(cx - R * 0.4, cy - R * 0.25, R * 0.12, fill=AUTUMN["amber"] + (240,))
        d.polygon(
            [(cx - R * 0.7, cy + R * 0.5), (cx - R * 0.2, cy - R * 0.05),
             (cx + R * 0.2, cy + R * 0.3), (cx + R * 0.55, cy - R * 0.1),
             (cx + R * 0.8, cy + R * 0.5)],
            fill=sienna,
        )
    elif kind == "code":
        rect(cx - R * 0.85, cy - R * 0.6, cx + R * 0.85, cy + R * 0.6, fill=coffee, w=stroke)
        d.line([(cx - R * 0.4, cy - R * 0.25), (cx - R * 0.65, cy), (cx - R * 0.4, cy + R * 0.25)],
               fill=cream, width=stroke + 2)
        d.line([(cx + R * 0.4, cy - R * 0.25), (cx + R * 0.65, cy), (cx + R * 0.4, cy + R * 0.25)],
               fill=cream, width=stroke + 2)
    elif kind == "bug":
        d.ellipse([cx - R * 0.55, cy - R * 0.4, cx + R * 0.55, cy + R * 0.6],
                  fill=AUTUMN["ember_red"] + (235,), outline=ink, width=stroke)
        for s in (-1, 1):
            d.line([(cx + s * R * 0.55, cy - R * 0.2), (cx + s * R * 0.85, cy - R * 0.4)],
                   fill=ink, width=stroke)
            d.line([(cx + s * R * 0.55, cy + R * 0.1), (cx + s * R * 0.85, cy + R * 0.1)],
                   fill=ink, width=stroke)
            d.line([(cx + s * R * 0.5, cy + R * 0.4), (cx + s * R * 0.8, cy + R * 0.6)],
                   fill=ink, width=stroke)
        circle(cx - R * 0.18, cy - R * 0.55, R * 0.05, fill=ink)
        circle(cx + R * 0.18, cy - R * 0.55, R * 0.05, fill=ink)
    elif kind in ("hammer", "hammer_stack"):
        d.line([(cx - R * 0.4, cy + R * 0.7), (cx + R * 0.5, cy - R * 0.3)],
               fill=coffee, width=stroke + 6)
        d.polygon(
            [(cx + R * 0.2, cy - R * 0.7), (cx + R * 0.85, cy - R * 0.55),
             (cx + R * 0.65, cy - R * 0.05), (cx, cy - R * 0.2)],
            fill=AUTUMN["sienna"] + (240,), outline=ink, width=stroke,
        )
    elif kind == "seed":
        d.ellipse([cx - R * 0.25, cy - R * 0.45, cx + R * 0.25, cy + R * 0.45],
                  fill=AUTUMN["sienna"] + (235,), outline=ink, width=stroke)
        d.line([(cx, cy + R * 0.45), (cx, cy + R * 0.85)], fill=AUTUMN["sienna"] + (220,), width=stroke)
    elif kind == "leaf":
        d.polygon(
            [(cx, cy - R * 0.8), (cx + R * 0.55, cy), (cx, cy + R * 0.7), (cx - R * 0.55, cy)],
            fill=AUTUMN["amber"] + (235,), outline=ink, width=stroke,
        )
        d.line([(cx, cy - R * 0.8), (cx, cy + R * 0.7)], fill=ink, width=stroke)
    elif kind == "tree":
        d.rectangle([cx - R * 0.12, cy + R * 0.1, cx + R * 0.12, cy + R * 0.85],
                    fill=coffee, outline=ink, width=stroke)
        for i, scale in enumerate([1.0, 0.8, 0.6]):
            y = cy + R * 0.1 - i * R * 0.35
            d.polygon(
                [(cx, y - R * 0.6 * scale), (cx + R * 0.55 * scale, y),
                 (cx - R * 0.55 * scale, y)],
                fill=AUTUMN["burnt"] + (235,), outline=ink, width=stroke,
            )
    else:
        # fallback: small flame
        pts = flame_shape(size, 0.36, 0.22, seed)
        d.polygon(pts, fill=amber, outline=sienna, width=stroke)

    layer = layer.filter(ImageFilter.GaussianBlur(0.5))
    canvas.alpha_composite(layer)


def achievement_sprite(slug: str, kind: str, idx: int) -> Image.Image:
    size = 512
    canvas = kraft_paper(size).convert("RGBA")
    # background warm wash
    wash = watercolor_blob(
        size, size // 2, size // 2, int(size * 0.4),
        AUTUMN["burnt"], alpha=55, petals=14, seed=idx + 200,
    )
    canvas.alpha_composite(wash)
    draw_glyph(canvas, kind, seed=idx + 33)
    # subtle inner border
    d = ImageDraw.Draw(canvas)
    pad = int(size * 0.05)
    d.rectangle([pad, pad, size - pad, size - pad],
                outline=AUTUMN["ink"] + (60,), width=max(2, size // 256))
    return canvas


def main():
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    ACH_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Stage sprites — guaranteed real files, swap any existing
    for fname, idx, hf, wf, sparks, seed in STAGES:
        out = STAGES_DIR / fname
        img = stage_sprite(fname, idx, hf, wf, sparks, seed)
        img.convert("RGB").save(out, "WEBP", quality=92, method=6)
        print(f"stage: {out.relative_to(REPO)}  ({out.stat().st_size // 1024} KB)")

    # 2) Achievement sprites — start with our themed batch, then numeric fillers
    base_count = len(ACH_THEMES)
    target = 159
    for i, (slug, kind, _desc) in enumerate(ACH_THEMES):
        out = ACH_DIR / f"ach-{i+1:03d}-{slug}.webp"
        img = achievement_sprite(slug, kind, i)
        img.convert("RGB").save(out, "WEBP", quality=88, method=6)

    # Filler set — varied glyph kinds for breadth (still real, distinct images)
    filler_kinds = [
        "flame_small", "speech", "vault", "stack", "doc", "doc_stack", "chip", "chip_grid",
        "wifi_off", "export", "import", "broom", "branch", "bookmark", "magnifier",
        "egg", "wing", "scroll", "calendar_check", "camera", "shield", "lock", "unlock",
        "friend", "share", "collab", "mic", "image", "code", "bug", "hammer", "seed",
        "leaf", "tree", "scroll_stack", "calendar_week", "doc_pile", "stack_big",
    ]
    rng = random.Random(7777)
    for j in range(base_count, target):
        kind = filler_kinds[(j - base_count) % len(filler_kinds)]
        # mild variation seed so each filler differs visually
        out = ACH_DIR / f"ach-{j+1:03d}-{kind}-v{(j // len(filler_kinds))+1}.webp"
        img = achievement_sprite(f"filler-{j}", kind, j + rng.randint(0, 9999))
        img.convert("RGB").save(out, "WEBP", quality=88, method=6)

    total = len(list(ACH_DIR.glob("*.webp")))
    print(f"achievements: {total} files in {ACH_DIR.relative_to(REPO)}")


if __name__ == "__main__":
    main()
