#!/usr/bin/env python3
"""Build ROUTE 0x01 — first wild-encounter scene (v0.37).

Loop 9947. Gap from the design doc: cc_route1_bg.png art has been sitting in
the plugin since v0.7 but no scene references it. The catch loop has all
the plumbing (encounter pool, sidecar, dex unlocks) but no actual route
where wild encounters fire. ROUTE 0x01 is the first walkable patch of grass
between PLAYER ROOM / CORE LAB and the gym world.

This script writes:
  1. assets/backgrounds/cc_route1_bg.png (copied from plugin)
  2. assets/backgrounds/cc_route1_bg.png.gbsres (background registration)
  3. project/scenes/cinder_route_0x01/scene.gbsres (the scene)
  4. project/scenes/cinder_route_0x01/triggers/grass_a.gbsres (encounter zone)

UUID slab: 0xc0 reserved for route resources.
Idempotent — stable UUIDs, safe to re-run.

Run: python3 products/cinder-creatures-gb/scripts/build-route-0x01.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
PLUGIN_BG = ROOT / "plugins/cinder-creatures/backgrounds"
ASSETS_BG = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

ROUTE_BG_ID    = "c1bd5e01-1000-4001-8001-0000000000c0"
ROUTE_SCENE_ID = "c1bd5e01-2000-4002-8002-0000000000c0"
GRASS_A_ID     = "c1bd5e01-4000-4004-8004-0000000000c0"
ENCOUNTER_VAR  = "c1bd5e01-3000-4003-8003-000000000021"  # CC Creature Buf (existing)


def copy_background():
    src = PLUGIN_BG / "cc_route1_bg.png"
    dst = ASSETS_BG / "cc_route1_bg.png"
    if not src.exists():
        raise SystemExit(f"missing source background: {src}")
    ASSETS_BG.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
        shutil.copy2(src, dst)
        print(f"copied  {dst.relative_to(ROOT)}")
    else:
        print(f"kept    {dst.relative_to(ROOT)} (up-to-date)")


def write_background_meta():
    meta = {
        "_resourceType": "background",
        "id": ROUTE_BG_ID,
        "name": "CC Route 0x01",
        "symbol": "bg_cc_route_0x01",
        "tileColors": "",
        "filename": "cc_route1_bg.png",
        "width": 20,
        "height": 18,
        "imageWidth": 160,
        "imageHeight": 144,
        "autoColor": False,
    }
    out = ASSETS_BG / "cc_route1_bg.png.gbsres"
    out.write_text(json.dumps(meta, indent=2))
    print(f"wrote   {out.relative_to(ROOT)}")


def write_scene():
    scene = {
        "_resourceType": "scene",
        "id": ROUTE_SCENE_ID,
        "_index": 200,
        "type": "TOPDOWN",
        "name": "ROUTE 0x01",
        "symbol": "scene_route_0x01",
        "x": 100,
        "y": 1500,
        "width": 20,
        "height": 18,
        "backgroundId": ROUTE_BG_ID,
        "tilesetId": "",
        "colorModeOverride": "none",
        "paletteIds": ["", "", "", "", "", "default-sprite"],
        "spritePaletteIds": [],
        "autoFadeSpeed": 1,
        "playerSpriteSheetId": "",
        "script": [
            {
                "id": f"{ROUTE_SCENE_ID}-init-001",
                "command": "EVENT_TEXT",
                "args": {
                    "text": "ROUTE 0x01\nWild signals roam\nthe grass."
                },
            }
        ],
        "playerHit1Script": [],
        "playerHit2Script": [],
        "playerHit3Script": [],
    }
    scene_dir = SCENES_DIR / "cinder_route_0x01"
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "scene.gbsres").write_text(json.dumps(scene, indent=2))
    print(f"wrote   {(scene_dir / 'scene.gbsres').relative_to(ROOT)}")


def write_grass_trigger():
    trig = {
        "_resourceType": "trigger",
        "id": GRASS_A_ID,
        "_index": 0,
        "symbol": "trigger_route_grass_a",
        "name": "Wild grass A",
        "x": 8,
        "y": 8,
        "width": 4,
        "height": 3,
        "trigger": "walk",
        "leaveScript": [],
        "script": [
            {
                "id": f"{GRASS_A_ID}-grass-001",
                "command": "EVENT_CC_ENCOUNTER",
                "args": {
                    "variable": ENCOUNTER_VAR,
                    "min": 1,
                    "max": 56,
                },
            }
        ],
    }
    trig_dir = SCENES_DIR / "cinder_route_0x01" / "triggers"
    trig_dir.mkdir(parents=True, exist_ok=True)
    (trig_dir / "grass_a.gbsres").write_text(json.dumps(trig, indent=2))
    print(f"wrote   {(trig_dir / 'grass_a.gbsres').relative_to(ROOT)}")


if __name__ == "__main__":
    copy_background()
    write_background_meta()
    write_scene()
    write_grass_trigger()
    print("ROUTE 0x01 ready — open in GB Studio to wire entry/exit doors.")
