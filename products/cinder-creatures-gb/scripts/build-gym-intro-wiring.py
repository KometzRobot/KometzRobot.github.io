#!/usr/bin/env python3
"""Wire intro plates as one-shot scene transitions before each gym (v0.36).

Loop 9945. The plates from v0.35 (cc_intro_*.png) sat in the plugin folder
unwired. This script connects them to the gym scenes so the player actually
sees them on first walk-in:

  player walks into gym scene
    -> gym scene's on-init script checks VAR_CC_INTRO_<TYPE>_SEEN
    -> if 0: SWITCH_SCENE to intro card scene
       intro card scene shows plate, awaits A press, sets var=1, SWITCH_SCENE back to gym
    -> on second entry, var=1 -> intro skipped, normal play

Idempotent — stable UUIDs, safe to re-run. Writes to cinder-starter/.

Run: python3 products/cinder-creatures-gb/scripts/build-gym-intro-wiring.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
PLUGIN_BG = ROOT / "plugins/cinder-creatures/backgrounds"
ASSETS_BG = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"
VARS_FILE = ROOT / "project/variables.gbsres"

# 5 gyms. Each entry: type key, gym scene UUID, gym BG UUID, gym name
GYMS = [
    ("logic", "c1bd5e01-2000-4002-8002-000000000010", "c1bd5e01-1000-4001-8001-000000000010"),
    ("mem",   "c1bd5e01-2000-4002-8002-000000000011", "c1bd5e01-1000-4001-8001-000000000011"),
    ("proc",  "c1bd5e01-2000-4002-8002-000000000012", "c1bd5e01-1000-4001-8001-000000000012"),
    ("data",  "c1bd5e01-2000-4002-8002-000000000013", "c1bd5e01-1000-4001-8001-000000000013"),
    ("core",  "c1bd5e01-2000-4002-8002-000000000014", "c1bd5e01-1000-4001-8001-000000000014"),
]

# UUID slabs for new resources (offset 0xb0-0xbf reserved for intro wiring)
# Vars b0..b4
def var_id(i):       return f"c1bd5e01-3000-4003-8003-0000000000b{i:01x}"
# Intro card BGs b0..b4
def intro_bg_id(i):  return f"c1bd5e01-1000-4001-8001-0000000000b{i:01x}"
# Intro card scenes b0..b4
def intro_scene_id(i): return f"c1bd5e01-2000-4002-8002-0000000000b{i:01x}"


def update_variables():
    data = json.loads(VARS_FILE.read_text())
    have = {v["id"] for v in data["variables"]}
    added = 0
    for i, (typ, _, _) in enumerate(GYMS):
        vid = var_id(i)
        if vid in have:
            continue
        data["variables"].append({
            "id": vid,
            "name": f"CC Intro {typ.upper()} Seen",
            "symbol": f"var_cc_intro_{typ}_seen",
            "flags": {},
        })
        added += 1
    VARS_FILE.write_text(json.dumps(data, indent=2))
    print(f"[vars] +{added} intro_seen flags (have {len(data['variables'])} total)")


def copy_plates_and_register():
    """Copy intro PNGs from plugin/backgrounds to assets/backgrounds and
    write .gbsres metadata so GB Studio sees them as project backgrounds."""
    written = 0
    for i, (typ, _, _) in enumerate(GYMS):
        src = PLUGIN_BG / f"cc_intro_{typ}.png"
        dst = ASSETS_BG / f"cc_intro_{typ}.png"
        meta = ASSETS_BG / f"cc_intro_{typ}.png.gbsres"
        if not src.exists():
            print(f"[plate] MISSING {src}")
            continue
        shutil.copyfile(src, dst)
        meta.write_text(json.dumps({
            "_resourceType": "background",
            "id": intro_bg_id(i),
            "name": f"CC Intro {typ.upper()}",
            "symbol": f"bg_cc_intro_{typ}",
            "tileColors": "",
            "filename": f"cc_intro_{typ}.png",
            "width": 20,
            "height": 18,
            "imageWidth": 160,
            "imageHeight": 144,
            "autoColor": False,
        }, indent=2))
        written += 1
    print(f"[plate] copied + registered {written}/5")


def write_intro_scenes():
    """Each intro card scene: BG = intro plate, on-init script:
       1. EVENT_TEXT (with plate visible — keeps the card up until A pressed)
       2. EVENT_VARIABLE_SET_TO_VALUE intro_seen = 1
       3. EVENT_SWITCH_SCENE -> gym scene
    """
    written = 0
    for i, (typ, gym_scene_id, _) in enumerate(GYMS):
        scene_dir = SCENES_DIR / f"cinder_intro_{typ}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        # Single-line caption holds player at the plate until A is pressed.
        # The plate already shows GYM-<TYPE> + leader title + name; this just
        # gives the engine a "press A to continue" beat.
        caption = "..."
        scene = {
            "_resourceType": "scene",
            "id": intro_scene_id(i),
            "_index": 100 + i,
            "type": "TOPDOWN",
            "name": f"INTRO-{typ.upper()}",
            "symbol": f"scene_intro_{typ}",
            "x": 1500,
            "y": 100 + i * 200,
            "width": 20,
            "height": 18,
            "backgroundId": intro_bg_id(i),
            "tilesetId": "",
            "colorModeOverride": "none",
            "paletteIds": ["", "", "", "", "", "default-sprite"],
            "spritePaletteIds": [],
            "autoFadeSpeed": 1,
            "playerSpriteSheetId": "",
            "script": [
                {
                    "id": f"{intro_scene_id(i)}-intro-001",
                    "command": "EVENT_TEXT",
                    "args": {"text": caption},
                },
                {
                    "id": f"{intro_scene_id(i)}-intro-002",
                    "command": "EVENT_VARIABLE_SET_TO_VALUE",
                    "args": {
                        "variable": var_id(i),
                        "value": {"type": "number", "value": 1},
                    },
                },
                {
                    "id": f"{intro_scene_id(i)}-intro-003",
                    "command": "EVENT_SWITCH_SCENE",
                    "args": {
                        "sceneId": gym_scene_id,
                        "x": {"type": "number", "value": 9},
                        "y": {"type": "number", "value": 16},
                        "direction": "up",
                        "fadeSpeed": "2",
                    },
                },
            ],
            "playerHit1Script": [],
            "playerHit2Script": [],
            "playerHit3Script": [],
            "actors": [],
            "triggers": [],
            "collisions": [],
        }
        (scene_dir / "scene.gbsres").write_text(json.dumps(scene, indent=2))
        written += 1
    print(f"[intro-scene] wrote {written}/5 intro card scenes")


def patch_gym_scenes():
    """Prepend an IF intro_seen == 0 → SWITCH_SCENE intro_card to each gym
    scene's on-init script. Idempotent: only patches if not already patched."""
    patched = 0
    for i, (typ, gym_scene_id, _) in enumerate(GYMS):
        gym_dir = SCENES_DIR / f"cinder_gym_{typ}"
        scene_file = gym_dir / "scene.gbsres"
        if not scene_file.exists():
            print(f"[gym] MISSING {scene_file}")
            continue
        scene = json.loads(scene_file.read_text())
        marker = f"intro-redirect-{typ}"
        # Already patched?
        existing = scene.get("script") or []
        if any(s.get("id", "").endswith(marker) for s in existing):
            continue
        # Build the IF block
        guard = {
            "id": f"c1bd5e01-9000-4099-8099-{typ:>06s}-{marker}",
            "command": "EVENT_IF_VALUE",
            "args": {
                "variable": var_id(i),
                "operator": "==",
                "comparator": 0,
            },
            "children": {
                "true": [
                    {
                        "id": f"c1bd5e01-9000-4099-8099-{typ:>06s}-load",
                        "command": "EVENT_SWITCH_SCENE",
                        "args": {
                            "sceneId": intro_scene_id(i),
                            "x": {"type": "number", "value": 0},
                            "y": {"type": "number", "value": 0},
                            "direction": "down",
                            "fadeSpeed": "2",
                        },
                    },
                ],
                "false": [],
            },
        }
        scene["script"] = [guard] + existing
        scene_file.write_text(json.dumps(scene, indent=2))
        patched += 1
    print(f"[gym] patched {patched}/5 gym scenes with intro redirect")


def main():
    ASSETS_BG.mkdir(parents=True, exist_ok=True)
    update_variables()
    copy_plates_and_register()
    write_intro_scenes()
    patch_gym_scenes()
    print("\nv0.36 intro plate wiring complete.")
    print("In GB Studio: File -> Reload Project. Walk into any gym to see plate.")


if __name__ == "__main__":
    main()
