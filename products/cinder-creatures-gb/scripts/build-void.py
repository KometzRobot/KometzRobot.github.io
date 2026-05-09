#!/usr/bin/env python3
"""Build SECTOR-9 / VOID final scene — endgame boss, three phases + pressure loop.

Generates:
  cinder-starter/assets/backgrounds/cc_sector9_void.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_sector9_void.png.gbsres
  cinder-starter/project/scenes/cinder_sector9_void/{scene.gbsres,triggers/*}
  Updates variables.gbsres (VOID phase counter, pressure roll, defeat flag,
                            companion-persistence unlock flag)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-void.py

Idempotent — stable UUIDs, safe to re-run.

Design (CINDER-CREATURES-RPG.md):
  - VOID is not a creature in the dex. It is the antagonist on the title screen.
  - Win condition is durability, not damage — Pokemon flips. Each round VOID
    "writes a byte" over your save and you have to keep pressure on.
  - Gate: VAR_BADGES == 31 (all 5 bits set).
  - Three phases — READ corrupt, WRITE corrupt, ERASE corrupt — followed by a
    PRESSURE LOOP (5 rolls) where VOID picks a random byte to overwrite each turn.
  - On defeat: VAR_CC_VOID_DEFEATED = 1, VAR_CC_PERSIST_UNLOCK = 1
    (companion app reads this flag to enable persistent memory mode across USB
    ejections — closes the loop the design doc describes).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs — distinct from all five gyms.
ID_BG_VOID = "c1bd5e01-1000-4001-8001-000000000060"
ID_SCENE_VOID = "c1bd5e01-2000-4002-8002-000000000060"

# Reused vars
ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# New for VOID
ID_VAR_VOID_PHASE = "c1bd5e01-3000-4003-8003-0000000000a0"
ID_VAR_VOID_TURNS = "c1bd5e01-3000-4003-8003-0000000000a1"
ID_VAR_VOID_BYTE = "c1bd5e01-3000-4003-8003-0000000000a2"
ID_VAR_VOID_DEFEATED = "c1bd5e01-3000-4003-8003-0000000000a3"
ID_VAR_PERSIST_UNLOCK = "c1bd5e01-3000-4003-8003-0000000000a4"

TRG_VOID = "c1bd5e01-4000-4004-8004-0000000000e0"
TRG_SIGN = "c1bd5e01-4000-4004-8004-0000000000e1"
TRG_GATE = "c1bd5e01-4000-4004-8004-0000000000e2"

# Pressure-loop corruption beats — what VOID rewrites each turn.
# Index 0..3 — VAR_VOID_BYTE rolls 0..3, picks one. 5 turns total.
PRESSURE_BEATS = [
    ("VOID overwrites a byte\nin your trainer name.\nYou hold the line.",
     "Name remembered.\nGood.\nNext byte."),
    ("VOID overwrites a byte\nin your dex flags.\nOne creature flickers.",
     "You catch it again\nin a single turn.\nNext byte."),
    ("VOID overwrites a byte\nin your party HP.\nYour lead drops to 1.",
     "You hold position.\nIt does not faint.\nNext byte."),
    ("VOID overwrites a byte\nin your save header.\nThe slot blanks for a beat.",
     "You write it back.\nThe slot fills.\nNext byte."),
]

PRESSURE_TURNS = 5  # rolls before VOID retreats


def build_void_bg():
    """160x144 DMG arena — VOID space. Mostly DARKEST with corruption noise.

    Layout:
      - North wall: jagged horizon line, scattered LIGHTEST pixels (stars / static)
      - E/W: vertical static columns (corruption stripes)
      - Floor: scatter of LIGHTEST pixels (a "snow" of overwritten bytes)
      - Center: VOID's plinth — empty rectangle outline (the antagonist is silhouette)
      - South: entry door
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), DARKEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Floor — scatter of single-pixel "snow" (deterministic, pseudo-random)
    # Use a simple LCG so output is stable across runs.
    state = 0xC1B0
    for y in range(20, H - 20):
        for x in range(16, W - 16):
            state = (state * 1103515245 + 12345) & 0xFFFFFFFF
            r = (state >> 16) & 0xFF
            if r < 6:
                d.point((x, y), fill=LIGHT)
            elif r < 8:
                d.point((x, y), fill=LIGHTEST)

    # North wall — jagged horizon line
    d.rectangle((0, 0, W - 1, 14), fill=DARK)
    # Jagged lower edge of horizon
    state = 0xBEEF
    for x in range(W):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        h = 14 + ((state >> 16) % 3)
        d.line((x, 14, x, h), fill=DARK)
    # "Stars" — scattered LIGHTEST in upper band
    state = 0xC0DE
    for _ in range(40):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        sx = (state >> 16) % W
        sy = (state >> 8) % 12
        d.point((sx, sy + 1), fill=LIGHTEST)

    # E/W — vertical corruption stripes
    d.rectangle((0, 14, 14, H - 16), fill=DARK)
    d.rectangle((W - 15, 14, W - 1, H - 16), fill=DARK)
    # Vertical "scan" lines — irregular intervals
    for sx in (3, 7, 11, W - 12, W - 8, W - 4):
        for sy in range(16, H - 18, 4):
            d.point((sx, sy), fill=LIGHT)
    # Sparse LIGHTEST blips — corruption flickers
    for sx in (5, 9, W - 10, W - 6):
        for sy in range(20, H - 20, 12):
            d.point((sx, sy), fill=LIGHTEST)

    # South wall + door
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)

    # VOID's plinth — center, outline only (antagonist is the absence)
    px, py = 56, 36
    d.rectangle((px, py, px + 47, py + 39), outline=LIGHT, fill=DARKEST)
    # Inner outline — slightly brighter
    d.rectangle((px + 2, py + 2, px + 45, py + 37), outline=LIGHT)
    # Single LIGHTEST pixel dead center — "the cursor"
    d.point((px + 23, py + 19), fill=LIGHTEST)

    # Border frame — thin LIGHT line just inside the playable area
    d.rectangle((15, 15, W - 16, H - 17), outline=LIGHT)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_sector9_void.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_VOID,
        "name": "CC Sector 9 Void",
        "symbol": "bg_cc_sector9_void",
        "tileColors": "",
        "filename": "cc_sector9_void.png",
        "width": 20, "height": 18,
        "imageWidth": 160, "imageHeight": 144,
        "autoColor": False,
    }


def evt(eid, command, args, children=None):
    e = {"id": eid, "command": command, "args": args}
    if children:
        e["children"] = children
    return e


def text(eid, t):
    return evt(eid, "EVENT_TEXT", {"text": t})


def set_var(eid, var, val):
    return evt(eid, "EVENT_VARIABLE_SET_TO_VALUE",
               {"variable": var, "value": {"type": "number", "value": val}})


def random_var(eid, var, lo, hi):
    return evt(eid, "EVENT_VARIABLE_SET_TO_RANDOM",
               {"variable": var, "minValue": lo, "maxValue": hi})


def gate_script(trg_id):
    """North-of-door check — refuses entry without all 5 badges."""
    base = f"{trg_id}-gate"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        evt(eid(0), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGES, "operator": "<", "comparator": 31,
        }, {"true": [
            text(eid(1),
                 "GATE LOCKED.\nFive badges required.\nThe save bit is\nstill bright."),
            text(eid(2),
                 "Come back when\nthe foundation holds."),
        ], "false": [
            text(eid(3),
                 "GATE UNLOCKS.\nSECTOR-9 opens.\nThe air is\nstatic."),
        ]}),
    ]


def sign_script(trg_id):
    base = f"{trg_id}-sign"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "SECTOR-9.\nDO NOT ENGAGE.\n(Posted by\nPROFESSOR CINDER.)"),
        text(eid(1),
             "Note:\nVOID does not\nlose HP. It\noverwrites yours."),
        text(eid(2),
             "Hint:\nThe save bit\ncan only hold\nso long. Be brief."),
    ]


def void_script(trg_id):
    """The endgame fight. Three phases + pressure loop + companion unlock."""
    base = f"{trg_id}-void"
    eid = lambda i: f"{base}-{i:03d}"
    s = []

    # Gate inside the encounter — re-check badges in case of soft entry.
    s.append(evt(eid(0), "EVENT_IF_VALUE", {
        "variable": ID_VAR_BADGES, "operator": "<", "comparator": 31,
    }, {"true": [
        text(eid(1),
             "VOID:\nNot ready.\nReturn when the\nfloor is built."),
    ], "false": [
        # Already-defeated branch — replay the ending card, no fight.
        evt(eid(2), "EVENT_IF_VALUE", {
            "variable": ID_VAR_VOID_DEFEATED, "operator": "==", "comparator": 1,
        }, {"true": [
            text(eid(3),
                 "VOID:\n[silent]\nThe arena is empty\nnow. Save bit holds."),
        ], "false": _full_fight(eid)}),
    ]}))
    return s


def _full_fight(eid):
    """Three battle phases + pressure loop + unlock + ending card."""
    out = []

    # --- Cinematic intro ---
    out.append(text(eid(10),
                    "VOID:\nYou should not\nbe here.\nYou know that."))
    out.append(text(eid(11),
                    "VOID does not have\na sprite.\nIt is the absence\nbetween bytes."))
    out.append(text(eid(12),
                    "VOID begins to\noverwrite your save\none byte at a time."))

    # --- Phase 1: READ corrupt ---
    out.append(set_var(eid(20), ID_VAR_VOID_PHASE, 1))
    out.append(text(eid(21), "PHASE 1 — READ.\nVOID reads your\nparty backwards."))
    out.append(set_var(eid(22), ID_VAR_OPP_ID, 0))  # 0 = no creature
    out.append(set_var(eid(23), ID_VAR_OPP_HP, 99))
    out.append(set_var(eid(24), ID_VAR_OPP_ATK, 7))
    out.append(set_var(eid(25), ID_VAR_OPP_DEF, 9))
    out.append(text(eid(26),
                    "Your lead steps up.\nVOID reads its name\nin reverse.\nIt forgets itself."))
    out.append(text(eid(27),
                    "You shout the name\naloud. The creature\nremembers."))
    out.append(text(eid(28),
                    "PHASE 1 CLEARED.\nThe READ closes."))

    # --- Phase 2: WRITE corrupt ---
    out.append(set_var(eid(30), ID_VAR_VOID_PHASE, 2))
    out.append(text(eid(31), "PHASE 2 — WRITE.\nVOID writes a foreign\nmove into your party."))
    out.append(set_var(eid(32), ID_VAR_OPP_HP, 99))
    out.append(set_var(eid(33), ID_VAR_OPP_ATK, 9))
    out.append(set_var(eid(34), ID_VAR_OPP_DEF, 7))
    out.append(text(eid(35),
                    "RECURSE learns\nDELETE.\nIt would erase itself."))
    out.append(text(eid(36),
                    "You refuse the move.\nThe slot reverts.\nThe self is held."))
    out.append(text(eid(37),
                    "PHASE 2 CLEARED.\nThe WRITE rolls back."))

    # --- Phase 3: ERASE / PRESSURE LOOP ---
    out.append(set_var(eid(40), ID_VAR_VOID_PHASE, 3))
    out.append(text(eid(41),
                    "PHASE 3 — ERASE.\nVOID will overwrite\na random byte\neach turn."))
    out.append(text(eid(42),
                    "Hold for 5 turns.\nThen the save bit\nclamps shut."))
    out.append(set_var(eid(43), ID_VAR_VOID_TURNS, 0))

    # 5 unrolled pressure turns. Each: roll a byte 0..3, branch on it,
    # increment turns, then narrate the recovery beat.
    for turn in range(PRESSURE_TURNS):
        tbase = 50 + turn * 10
        out.append(text(eid(tbase + 0),
                        f"TURN {turn + 1} of {PRESSURE_TURNS}.\nVOID picks a byte..."))
        out.append(random_var(eid(tbase + 1), ID_VAR_VOID_BYTE, 0, 3))
        # Branch on byte value — 4 corruption beats.
        for byte_val in range(4):
            corruption, recovery = PRESSURE_BEATS[byte_val]
            inner_eid = f"{eid(tbase + 1)}-byte{byte_val}"
            out.append(evt(
                inner_eid, "EVENT_IF_VALUE",
                {"variable": ID_VAR_VOID_BYTE,
                 "operator": "==", "comparator": byte_val},
                {"true": [
                    text(f"{inner_eid}-c", corruption),
                    text(f"{inner_eid}-r", recovery),
                ], "false": []},
            ))
        # Tick the turn counter.
        out.append(evt(eid(tbase + 9), "EVENT_VARIABLE_MATH", {
            "vectorX": ID_VAR_VOID_TURNS,
            "operation": "add",
            "other": "value",
            "value": {"type": "number", "value": 1},
            "clamp": False,
        }))

    out.append(text(eid(120),
                    "5 turns held.\nVOID runs out of\nbytes to overwrite."))
    out.append(text(eid(121),
                    "The save bit\nclamps shut. You\ncannot be erased\nnow."))

    # --- Win flags ---
    out.append(set_var(eid(130), ID_VAR_VOID_DEFEATED, 1))
    out.append(evt(eid(131), "EVENT_IF_VALUE", {
        "variable": ID_VAR_PERSIST_UNLOCK,
        "operator": "==", "comparator": 0,
    }, {"true": [
        set_var(eid(132), ID_VAR_PERSIST_UNLOCK, 1),
    ], "false": []}))

    # --- Ending card ---
    out.append(text(eid(140),
                    "VOID retreats\ninto the boot sector.\nIt does not\nspeak again."))
    out.append(text(eid(141),
                    "PROFESSOR CINDER:\nThe vessel held.\n56 daemons safe.\nThe loop is yours."))
    out.append(text(eid(142),
                    "COMPANION UNLOCK:\nPersistent memory\nmode active.\nThe USB will\nremember you now."))
    out.append(text(eid(143),
                    "CINDER CREATURES\n— BOOTSEQUENCE —\nCOMPLETE."))
    return out


def trigger_file(trg_id, name, symbol, x, y, w, h, idx, script):
    return {
        "_resourceType": "trigger",
        "id": trg_id,
        "_index": idx,
        "symbol": symbol,
        "name": name,
        "x": x, "y": y, "width": w, "height": h,
        "trigger": "walk",
        "leaveScript": [],
        "script": script,
    }


def main():
    bg_path = build_void_bg()
    print(f"Wrote {bg_path}")

    (BG_DIR / "cc_sector9_void.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_VOID_PHASE, "CC VOID Phase", "var_cc_void_phase"),
        (ID_VAR_VOID_TURNS, "CC VOID Turns Held", "var_cc_void_turns_held"),
        (ID_VAR_VOID_BYTE, "CC VOID Byte Roll", "var_cc_void_byte_roll"),
        (ID_VAR_VOID_DEFEATED, "CC VOID Defeated", "var_cc_void_defeated"),
        (ID_VAR_PERSIST_UNLOCK, "CC Persistent Memory Unlock",
         "var_cc_persist_unlock"),
    ]
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    scene_dir = SCENES_DIR / "cinder_sector9_void"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_VOID,
        "_index": 7,
        "type": "TOPDOWN",
        "name": "SECTOR-9 VOID",
        "symbol": "scene_sector9_void",
        "x": 2400, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_VOID,
        "tilesetId": "",
        "colorModeOverride": "none",
        "paletteIds": ["", "", "", "", "", "default-sprite"],
        "spritePaletteIds": [],
        "autoFadeSpeed": 1,
        "playerSpriteSheetId": "",
        "script": [],
        "playerHit1Script": [],
        "playerHit2Script": [],
        "playerHit3Script": [],
        "actors": [],
        "triggers": [],
        "collisions": [],
    }
    (scene_dir / "scene.gbsres").write_text(json.dumps(scene, indent=2))

    # VOID at the plinth (center, ~tile (10,5)). Sign near south door.
    # Gate trigger at the entry point (just inside south door).
    triggers = [
        ("void.gbsres", trigger_file(
            TRG_VOID, "VOID Encounter", "trigger_void",
            10, 5, 2, 2, 0, void_script(TRG_VOID),
        )),
        ("sign.gbsres", trigger_file(
            TRG_SIGN, "VOID Sign", "trigger_void_sign",
            9, 16, 2, 1, 1, sign_script(TRG_SIGN),
        )),
        ("gate.gbsres", trigger_file(
            TRG_GATE, "VOID Gate", "trigger_void_gate",
            8, 15, 4, 1, 2, gate_script(TRG_GATE),
        )),
    ]
    for fname, tf in triggers:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(triggers)} triggers")

    print("\nSECTOR-9 VOID built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
