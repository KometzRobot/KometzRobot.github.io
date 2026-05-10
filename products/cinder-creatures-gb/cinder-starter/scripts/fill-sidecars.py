#!/usr/bin/env python3
"""Generate any missing .gbsres sidecar files in the project.

GB Studio v4 expects each asset PNG/WAV/MOD/SAV to have a sibling
.gbsres metadata file. When sidecars are missing, GB Studio prints
"No .gbsres exists yet for file: ..." on load and creates them
on-the-fly — slow + can leave the project in a half-loaded state
that Joel sees as "doesn't open."

Pre-creating the sidecars makes opens deterministic.

Scans:
- assets/backgrounds, assets/sprites, assets/tilesets, assets/sounds,
  assets/music, assets/avatars, assets/emotes, assets/fonts, assets/ui
- plugins/<plugin>/{backgrounds,sprites,tilesets,sounds,music}

Skips files that already have a sidecar.
"""
import json
import re
import struct
import uuid
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def png_size(p: Path):
    with p.open("rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        f.read(4)  # length
        if f.read(4) != b"IHDR":
            return None
        w, h = struct.unpack(">II", f.read(8))
        return w, h


def stable_uuid(seed: str) -> str:
    h = zlib.crc32(seed.encode())
    return str(uuid.UUID(bytes=h.to_bytes(4, "big") + bytes(12)))


def name_from(p: Path) -> str:
    return p.stem


def symbol_from(prefix: str, p: Path) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", p.stem.lower()).strip("_")
    return f"{prefix}_{s}"


def write_if_missing(side: Path, payload: dict) -> bool:
    if side.exists():
        return False
    side.write_text(json.dumps(payload, indent=2) + "\n")
    return True


def background_payload(p: Path):
    sz = png_size(p)
    if not sz:
        return None
    iw, ih = sz
    return {
        "_resourceType": "background",
        "id": stable_uuid(f"bg:{p}"),
        "name": name_from(p),
        "symbol": symbol_from("bg", p),
        "tileColors": "",
        "filename": p.name,
        "width": iw // 8,
        "height": ih // 8,
        "imageWidth": iw,
        "imageHeight": ih,
        "autoColor": False,
    }


def sprite_payload(p: Path):
    sz = png_size(p)
    if not sz:
        return None
    iw, ih = sz
    canvas_w = 16
    canvas_h = 16
    state_id = stable_uuid(f"sprite-state:{p}")
    return {
        "_resourceType": "sprite",
        "id": stable_uuid(f"sprite:{p}"),
        "name": name_from(p),
        "symbol": symbol_from("sprite", p),
        "states": [
            {
                "id": state_id,
                "name": "",
                "animationType": "fixed",
                "flipLeft": False,
                "animations": [
                    {"id": stable_uuid(f"anim:{p}:{i}"), "frames": [
                        {"id": stable_uuid(f"frame:{p}:{i}"), "tiles": []}
                    ]} for i in range(8)
                ],
            }
        ],
        "numTiles": 0,
        "canvasOriginX": 0,
        "canvasOriginY": 0,
        "canvasWidth": canvas_w,
        "canvasHeight": canvas_h,
        "boundsX": 0,
        "boundsY": -8,
        "boundsWidth": 16,
        "boundsHeight": 16,
        "animSpeed": 15,
        "filename": p.name,
        "width": iw,
        "height": ih,
    }


def tileset_payload(p: Path):
    sz = png_size(p)
    if not sz:
        return None
    iw, ih = sz
    return {
        "_resourceType": "tileset",
        "id": stable_uuid(f"tileset:{p}"),
        "name": name_from(p),
        "symbol": symbol_from("tileset", p),
        "width": iw // 8,
        "height": ih // 8,
        "imageWidth": iw,
        "imageHeight": ih,
        "filename": p.name,
    }


def sound_payload(p: Path):
    return {
        "_resourceType": "sound",
        "id": stable_uuid(f"sound:{p}"),
        "name": name_from(p),
        "symbol": symbol_from("sound", p),
        "type": "wav",
        "filename": p.name,
    }


def music_payload(p: Path):
    return {
        "_resourceType": "music",
        "id": stable_uuid(f"music:{p}"),
        "name": name_from(p),
        "symbol": symbol_from("song", p),
        "settings": {},
        "filename": p.name,
        "type": "mod",
    }


HANDLERS = {
    "backgrounds": ("png", background_payload),
    "sprites": ("png", sprite_payload),
    "tilesets": ("png", tileset_payload),
    "avatars": ("png", sprite_payload),
    "emotes": ("png", sprite_payload),
    "ui": ("png", sprite_payload),
    "sounds": ("wav", sound_payload),
    "music": ("mod", music_payload),
}


def scan_dir(d: Path):
    created = 0
    for sub, (ext, handler) in HANDLERS.items():
        target = d / sub
        if not target.is_dir():
            continue
        for p in target.glob(f"*.{ext}"):
            sidecar = p.with_suffix(p.suffix + ".gbsres")
            if sidecar.exists():
                continue
            payload = handler(p)
            if payload is None:
                continue
            sidecar.write_text(json.dumps(payload, indent=2) + "\n")
            created += 1
    return created


def main():
    total = 0
    for root in [ROOT / "assets"]:
        if root.is_dir():
            total += scan_dir(root)
    plugins_dir = ROOT / "plugins"
    if plugins_dir.is_dir():
        for plugin in plugins_dir.iterdir():
            if plugin.is_dir():
                total += scan_dir(plugin)
    print(f"sidecars created: {total}")


if __name__ == "__main__":
    main()
