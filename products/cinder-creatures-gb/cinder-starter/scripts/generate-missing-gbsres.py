#!/usr/bin/env python3
"""Generate missing .gbsres sidecar files for cinder-starter assets.

GB Studio v4.2 needs a .gbsres JSON sidecar for every PNG in assets/sprites
and assets/backgrounds. Without it, the sprite/background is invisible to
the editor and the project can fail to load cleanly.
"""
import hashlib, json, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPRITE_DIR = ROOT / "assets" / "sprites"
BG_DIR = ROOT / "assets" / "backgrounds"

NS = uuid.UUID("c1bd5e01-7000-4007-8007-000000000000")

def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()

def stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(NS, seed))

def state_blank(seed: str, name: str = "", anim_count: int = 8):
    """Create a single sprite state with N empty animations and 1 frame each.
    Frame 0 holds two 8x8 tiles forming the 16x16 sprite (sliceX 0 and 8)."""
    state_id = stable_uuid(seed + ":state0")
    animations = []
    for i in range(anim_count):
        anim_seed = f"{seed}:anim{i}"
        if i == 0:
            tiles = [
                {
                    "id": stable_uuid(anim_seed + ":tile0"),
                    "x": 0, "y": 0, "sliceX": 0, "sliceY": 0,
                    "flipX": False, "flipY": False,
                    "palette": 0, "paletteIndex": 0,
                    "objPalette": "OBP0", "priority": False
                },
                {
                    "id": stable_uuid(anim_seed + ":tile1"),
                    "x": 8, "y": 0, "sliceX": 8, "sliceY": 0,
                    "flipX": False, "flipY": False,
                    "palette": 0, "paletteIndex": 0,
                    "objPalette": "OBP0", "priority": False
                },
            ]
        else:
            tiles = []
        animations.append({
            "id": stable_uuid(anim_seed),
            "frames": [{
                "id": stable_uuid(anim_seed + ":frame0"),
                "tiles": tiles,
            }]
        })
    return {
        "id": state_id,
        "name": name,
        "animationType": "fixed",
        "flipLeft": False,
        "animations": animations,
    }

def make_sprite_sidecar(png: Path, name: str) -> dict:
    seed = png.name
    return {
        "_resourceType": "sprite",
        "id": stable_uuid(seed),
        "name": name,
        "symbol": f"sprite_{name.lower().replace('-', '_')}",
        "states": [state_blank(seed)],
        "numTiles": 2,
        "canvasOriginX": 0, "canvasOriginY": 0,
        "canvasWidth": 16, "canvasHeight": 16,
        "boundsX": 0, "boundsY": -8,
        "boundsWidth": 16, "boundsHeight": 16,
        "animSpeed": 15,
        "filename": png.name,
        "width": 16, "height": 16,
        "checksum": sha1(png),
    }

def make_background_sidecar(png: Path, name: str, symbol: str) -> dict:
    return {
        "_resourceType": "background",
        "id": stable_uuid("bg:" + png.name),
        "name": name,
        "symbol": symbol,
        "tileColors": "",
        "filename": png.name,
        "width": 20, "height": 18,
        "imageWidth": 160, "imageHeight": 144,
        "autoColor": False,
    }

def write_if_missing(path: Path, data: dict, label: str):
    sidecar = path.with_suffix(path.suffix + ".gbsres")
    if sidecar.exists():
        return False
    sidecar.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  + {label}: {sidecar.relative_to(ROOT)}")
    return True

def main():
    created = 0
    print("Sprites (assets/sprites):")
    for png in sorted(SPRITE_DIR.glob("*.png")):
        name = png.stem
        if write_if_missing(png, make_sprite_sidecar(png, name), name):
            created += 1
    print("\nBackgrounds (assets/backgrounds):")
    for png in sorted(BG_DIR.glob("*.png")):
        name = "CC " + png.stem.replace("cc_", "").replace("_", " ").title()
        symbol = "bg_" + png.stem
        if write_if_missing(png, make_background_sidecar(png, name, symbol), name):
            created += 1
    print(f"\n{created} sidecar(s) generated.")

if __name__ == "__main__":
    main()
