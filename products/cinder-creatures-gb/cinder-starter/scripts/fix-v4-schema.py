#!/usr/bin/env python3
"""Strip v3-legacy fields from v4 scene/trigger .gbsres files.

GB Studio v4 split format keeps actors/triggers as separate files in
scenes/<scene>/{actors,triggers}/ subdirs. The scene.gbsres should NOT
contain inline `actors`, `triggers`, or `playerSpriteSheetId` arrays —
those are v3 leftovers and confuse the v4 loader.

Trigger.gbsres needs `prefabId` (empty) and `prefabScriptOverrides` ({})
and should drop the v3 `trigger` field.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "project" / "scenes"

LEGACY_SCENE_FIELDS = ("actors", "triggers", "playerSpriteSheetId")
LEGACY_TRIGGER_FIELDS = ("trigger",)


def load(p):
    return json.loads(p.read_text())


def save(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


def fix_scene(p):
    obj = load(p)
    changed = False
    for f in LEGACY_SCENE_FIELDS:
        if f in obj:
            del obj[f]
            changed = True
    if changed:
        save(p, obj)
    return changed


def fix_trigger(p):
    obj = load(p)
    changed = False
    for f in LEGACY_TRIGGER_FIELDS:
        if f in obj:
            del obj[f]
            changed = True
    if "prefabId" not in obj:
        obj["prefabId"] = ""
        changed = True
    if "prefabScriptOverrides" not in obj:
        obj["prefabScriptOverrides"] = {}
        changed = True
    if changed:
        save(p, obj)
    return changed


def main():
    scenes_fixed = 0
    triggers_fixed = 0
    for sp in ROOT.glob("*/scene.gbsres"):
        if fix_scene(sp):
            scenes_fixed += 1
    for tp in ROOT.glob("*/triggers/*.gbsres"):
        if fix_trigger(tp):
            triggers_fixed += 1
    print(f"scenes fixed: {scenes_fixed}")
    print(f"triggers fixed: {triggers_fixed}")


if __name__ == "__main__":
    main()
