#!/usr/bin/env python3
"""Build the cinder-starter playable demo scenes.

Generates:
  cinder-starter/assets/backgrounds/cc_player_room.png
  cinder-starter/assets/backgrounds/*.gbsres sidecars (3)
  cinder-starter/project/scenes/cinder_player_room/{scene.gbsres,triggers/}
  cinder-starter/project/scenes/cinder_core_lab/scene.gbsres
  Updates variables.gbsres + settings.gbsres (startSceneId)

Run from repo root: python3 products/cinder-creatures-gb/scripts/build-starter-scenes.py
Idempotent — stable UUIDs, safe to re-run.
"""
import json, uuid
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15,56,15),(48,98,48),(139,172,15),(155,188,15)]

def build_player_room_bg():
    W,H = 160,144
    img = Image.new("P",(W,H),3)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)
    d.rectangle((0,0,W-1,23), fill=2)
    d.line((0,24,W-1,24), fill=1)
    d.rectangle((144,80,159,119), fill=1)
    d.rectangle((146,82,157,117), fill=2)
    d.text((148,86),"D",fill=0)
    d.rectangle((8,32,47,63), fill=1)
    d.rectangle((10,34,45,61), fill=2)
    d.line((8,48,47,48), fill=0)
    d.rectangle((10,34,25,47), fill=3)
    d.rectangle((96,8,127,23), fill=0)
    d.rectangle((100,10,123,19), fill=3)
    d.line((100,14,123,14), fill=2)
    d.rectangle((48,80,111,119), fill=2)
    d.rectangle((50,82,109,117), fill=1)
    BG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(BG_DIR / "cc_player_room.png")

# Stable IDs
ID_BG_PLAYER_ROOM = "c1bd5e01-1000-4001-8001-000000000001"
ID_BG_LAB         = "c1bd5e01-1000-4001-8001-000000000002"
ID_BG_OVERWORLD   = "c1bd5e01-1000-4001-8001-000000000003"
ID_SCENE_PLAYER_ROOM = "c1bd5e01-2000-4002-8002-000000000001"
ID_SCENE_CORE_LAB    = "c1bd5e01-2000-4002-8002-000000000002"
ID_VAR_STARTER      = "c1bd5e01-3000-4003-8003-000000000001"
ID_VAR_PLAYER_NAME  = "c1bd5e01-3000-4003-8003-000000000002"
ID_VARS_PARTY = [f"c1bd5e01-3000-4003-8003-0000000000{10+i:02d}" for i in range(6)]
ID_VAR_ADDED_FLAG  = "c1bd5e01-3000-4003-8003-000000000020"
ID_VAR_CREATURE_BUF = "c1bd5e01-3000-4003-8003-000000000021"

def bg_sidecar(name, filename, bg_id):
    return {
        "_resourceType": "background", "id": bg_id, "name": name,
        "symbol": f"bg_{name.lower().replace(' ','_')}", "tileColors": "",
        "filename": filename, "width": 20, "height": 18,
        "imageWidth": 160, "imageHeight": 144, "autoColor": False
    }

def main():
    build_player_room_bg()
    (BG_DIR / "cc_player_room.png.gbsres").write_text(json.dumps(bg_sidecar("CC Player Room","cc_player_room.png",ID_BG_PLAYER_ROOM), indent=2))
    (BG_DIR / "cc_lab_bg.png.gbsres").write_text(json.dumps(bg_sidecar("CC Core Lab","cc_lab_bg.png",ID_BG_LAB), indent=2))
    (BG_DIR / "cc_overworld_bg.png.gbsres").write_text(json.dumps(bg_sidecar("CC Overworld","cc_overworld_bg.png",ID_BG_OVERWORLD), indent=2))
    print("3 bg sidecars written")
    # Variables
    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_STARTER, "CC Starter Choice", "var_cc_starter"),
        (ID_VAR_PLAYER_NAME, "CC Player Name", "var_cc_player_name"),
        *[(ID_VARS_PARTY[i], f"CC Party {i+1}", f"var_cc_party_{i+1}") for i in range(6)],
        (ID_VAR_ADDED_FLAG, "CC Added Flag", "var_cc_added_flag"),
        (ID_VAR_CREATURE_BUF, "CC Creature Buf", "var_cc_creature_buf"),
    ]
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")
    # Settings
    s = json.loads((ROOT / "project/settings.gbsres").read_text())
    s["startSceneId"] = ID_SCENE_PLAYER_ROOM
    s["startX"] = 5; s["startY"] = 5; s["startDirection"] = "down"
    (ROOT / "project/settings.gbsres").write_text(json.dumps(s, indent=2))
    print("settings.gbsres updated")

if __name__ == "__main__":
    main()
