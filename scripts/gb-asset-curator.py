#!/usr/bin/env python3
"""
GB Studio Asset Curator (Loop 9706)

Scans ~/Downloads for GB Studio assets Joel pulled down, identifies what each
archive is (plugin / sprite pack / font / SFX / tool / template), and stages the
GB-friendly subset into products/cinder-creatures-gb/asset-library/ organized by
category. Writes a manifest at asset-library/MANIFEST.json.

Joel's directive (Loop 9705 email): "I downloaded a shit ton of visuals and
assets and plugins all in the download folder of the Linux PC."

This is a curator, not a fork-bomb. It:
  - inspects ZIPs without extracting until categorized
  - flags GB-Studio-native plugins (plugin.json or events/ directory)
  - skips obviously irrelevant files (Etcher, banners, Figma templates)
  - produces a categorized index Joel can browse
"""
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"
LIB = Path("products/cinder-creatures-gb/asset-library")
MANIFEST = LIB / "MANIFEST.json"

CATEGORIES = ["plugins", "sprites", "backgrounds", "fonts", "sfx", "music", "ui", "tilesets", "tools", "templates", "uncategorized"]

SKIP_PREFIXES = ("balenaEtcher", "displaypic", "banner")

PLUGIN_HINT_DIRS = {"events", "engine", "lang", "plugin.json"}
PLUGIN_FILE_HINTS = {"plugin.json", "engine.json"}

FONT_HINTS = ("font", "Font", "FONT")
SFX_HINTS = ("SFX", "sfx", "sound", "Sound", "wav")
SPRITE_HINTS = ("sprite", "Sprite", "character", "Character", "monster", "creature", "rpg", "RPG")
BG_HINTS = ("background", "Background", "BG", "tileset", "Tileset", "scene", "Scene", "pattern", "Pattern")
UI_HINTS = ("UI", "menu", "Menu", "icon", "Icon", "portrait", "Portrait", "frame", "Frame", "dialog", "Dialog")
TOOL_HINTS = ("converter", "tilesetter", "engine", "morpheus", "GlyEngine")


def peek_zip(path: Path):
    """Return a small summary of zip contents for categorization."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()[:200]
            return names
    except (zipfile.BadZipFile, OSError):
        return None


def is_gb_plugin(names):
    if not names:
        return False
    lower = [n.lower() for n in names]
    if any(n.endswith("plugin.json") for n in lower):
        return True
    if any("/events/" in n and n.endswith(".js") for n in lower):
        return True
    if any("engine.json" in n for n in lower):
        return True
    # single-file event plugin at archive root
    if any(re.match(r"^event[a-z0-9_]+\.js$", n, re.I) for n in lower):
        return True
    return False


def is_gb_template(names):
    """Full GB Studio project — has .gbsproj or assets/backgrounds layout."""
    if not names:
        return False
    lower = [n.lower() for n in names]
    if any(n.endswith(".gbsproj") for n in lower):
        return True
    has_bg = any("assets/backgrounds" in n for n in lower)
    has_sprites = any("assets/sprites" in n for n in lower)
    return has_bg and has_sprites


def is_music_pack(names):
    if not names:
        return False
    return sum(1 for n in names if n.lower().endswith(".mod")) >= 2


def categorize(name: str, names_in_zip=None):
    n = name.lower()
    if names_in_zip:
        if is_gb_plugin(names_in_zip):
            return "plugins"
        if is_music_pack(names_in_zip):
            return "music"
        if is_gb_template(names_in_zip):
            return "templates"
    if n.endswith((".aseprite", ".ase")):
        return "sprites"
    if n.endswith(".wav") or any(h in name for h in SFX_HINTS):
        return "sfx"
    if any(h in name for h in FONT_HINTS) and "font" in n:
        return "fonts"
    if any(h in name for h in TOOL_HINTS) or "tilesetter" in n or "converter" in n:
        return "tools"
    if any(h in name for h in BG_HINTS) or "tileset" in n or "background" in n or "pattern" in n:
        return "backgrounds"
    if any(h in name for h in UI_HINTS) or "menu" in n or "portrait" in n or "icon" in n or "label" in n:
        return "ui"
    if any(h in name for h in SPRITE_HINTS) or "creature" in n or "monster" in n or "kenney" in n \
            or "ghouls" in n or "fantasy" in n or "dragoon" in n or "pokeman" in n or "minifantasy" in n \
            or "robots" in n or "animals" in n or "items" in n or "emote" in n or "portal" in n \
            or "techno" in n or "hospital" in n or "metroidvania" in n or "platformer" in n \
            or "tyler warren" in n or "petricake" in n or "asset" in n or "freebie" in n \
            or "dungeon" in n or "eerie" in n or "grindhaus" in n or "fhbattle" in n \
            or "tcg" in n or "fantasia" in n or "gumpy" in n or "warren" in n:
        return "sprites"
    if n.endswith(".fig") or "template" in n or "manual" in n:
        return "templates"
    return "uncategorized"


def make_dirs():
    for c in CATEGORIES:
        (LIB / c).mkdir(parents=True, exist_ok=True)


def scan():
    if not DOWNLOADS.exists():
        print(f"No {DOWNLOADS}", file=sys.stderr)
        return []
    entries = []
    for f in sorted(DOWNLOADS.iterdir()):
        if f.is_dir():
            continue
        if f.name.startswith(SKIP_PREFIXES):
            continue
        if f.suffix.lower() not in {".zip", ".rar", ".png", ".aseprite", ".svg", ".fig"}:
            continue
        names = peek_zip(f) if f.suffix.lower() == ".zip" else None
        cat = categorize(f.name, names)
        entries.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "category": cat,
            "is_gb_plugin": bool(names and is_gb_plugin(names)),
            "top_entries": (names[:8] if names else []),
        })
    return entries


def stage_links(entries):
    """Symlink (or copy if cross-fs) categorized files into the library."""
    staged = 0
    for e in entries:
        src = DOWNLOADS / e["filename"]
        dst = LIB / e["category"] / e["filename"]
        if dst.exists() or dst.is_symlink():
            continue
        try:
            os.symlink(src, dst)
            staged += 1
        except OSError as err:
            print(f"  symlink {dst.name} failed: {err}", file=sys.stderr)
    return staged


def write_readme(entries):
    by_cat = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e)
    lines = [
        "# Cinder GB Studio Asset Library",
        "",
        f"Curated from ~/Downloads on {os.popen('date -u +%Y-%m-%d').read().strip()}.",
        f"Total entries: {len(entries)}",
        "",
        "Each category is symlinks to the original archive in `~/Downloads`.",
        "When you find one you want, extract it into `plugins/` (for GB Studio plugins)",
        "or `assets/` (for art/sound). Then re-open the project so GB Studio re-scans.",
        "",
    ]
    for cat in CATEGORIES:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat} ({len(items)})")
        lines.append("")
        for e in sorted(items, key=lambda x: x["filename"].lower()):
            tag = " (GB plugin)" if e["is_gb_plugin"] else ""
            kb = e["size_bytes"] // 1024
            lines.append(f"- {e['filename']} — {kb}KB{tag}")
        lines.append("")
    (LIB / "README.md").write_text("\n".join(lines))


def extract_plugins(entries):
    """Extract detected GB Studio plugin archives into asset-library/extracted/."""
    out = LIB / "extracted"
    out.mkdir(exist_ok=True)
    extracted = []
    for e in entries:
        if not e["is_gb_plugin"]:
            continue
        src = DOWNLOADS / e["filename"]
        if src.suffix.lower() != ".zip":
            continue
        target = out / Path(e["filename"]).stem
        if target.exists():
            continue
        try:
            with zipfile.ZipFile(src) as z:
                # filter __MACOSX trash
                members = [m for m in z.namelist() if not m.startswith("__MACOSX") and "/.DS_Store" not in m]
                z.extractall(target, members=members)
            extracted.append(target.name)
        except Exception as err:
            print(f"  extract {e['filename']} failed: {err}", file=sys.stderr)
    return extracted


def main():
    make_dirs()
    entries = scan()
    staged = stage_links(entries)
    extracted = extract_plugins(entries)
    MANIFEST.write_text(json.dumps({"entries": entries, "total": len(entries), "extracted_plugins": extracted}, indent=2))
    write_readme(entries)
    by_cat = {}
    for e in entries:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
    print(f"Curated {len(entries)} files into {LIB}/  (staged {staged} new symlinks)")
    for k in sorted(by_cat):
        print(f"  {k:14} {by_cat[k]:3}")
    plugins = [e for e in entries if e["is_gb_plugin"]]
    if plugins:
        print(f"\nGB Studio plugins detected: {len(plugins)}, extracted: {len(extracted)}")
        for p in extracted:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
