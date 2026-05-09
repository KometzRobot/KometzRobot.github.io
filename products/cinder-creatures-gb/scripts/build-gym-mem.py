#!/usr/bin/env python3
"""Build GYM-MEM scene — second gym, KEEPER KILN, 4 trainers + leader.

Generates:
  cinder-starter/assets/backgrounds/cc_gym_mem.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_gym_mem.png.gbsres
  cinder-starter/project/scenes/cinder_gym_mem/{scene.gbsres,triggers/*}
  Updates variables.gbsres (adds MEM badge flag + per-trainer flags)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-gym-mem.py

Idempotent — stable UUIDs, safe to re-run.

Design (CINDER-CREATURES-RPG.md):
  - GYM-MEM, leader KEEPER KILN, badge MEM, bit value = 2.
  - Personality: grounded, slow, patient. Specialty: endurance + status (LEAK / BLOAT).
  - Floor layout: stockroom motif. 4 storage-keeper trainer pads, leader bench at north.
  - Trainers fight MEM-type creatures (STACKAT/CACHEY/PAGYL/MALLOCK).
  - Leader team: HEAPYR / ALLOCROC / NULLPUP (heavy HP/DEF, the stamina wall).
  - Leader gate: only opens when all 4 trainer bits set.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs — distinct from gym-logic block (000000000020+)
ID_BG_GYM_MEM = "c1bd5e01-1000-4001-8001-000000000020"
ID_SCENE_GYM_MEM = "c1bd5e01-2000-4002-8002-000000000020"

# Reused vars from gym-logic
ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# New for gym-mem
ID_VAR_MEM_TRAINERS = "c1bd5e01-3000-4003-8003-000000000050"
ID_VAR_BADGE_FLAG_MEM = "c1bd5e01-3000-4003-8003-000000000051"

TRG_TRAINER = [f"c1bd5e01-4000-4004-8004-0000000000{40+i:02d}" for i in range(4)]
TRG_LEADER = "c1bd5e01-4000-4004-8004-000000000050"
TRG_RIDDLE = "c1bd5e01-4000-4004-8004-000000000051"

# KEEPER KILN — grounded, slow, patient. Endurance + status (LEAK / BLOAT).
# Trainers wear "KEEPER" titles — they tend the storage tiers.
TRAINERS = [
    ("KEEPER", "STACK", 40, "STACKAT",
     "Last in, first out.\nThat's how I work.",
     "STACKAT pushes deep.\nPop only when full.",
     "Stack underflow.\nClean exit.", 1),
    ("KEEPER", "PAGE", 44, "PAGYL",
     "Wait while I swap.\nThis takes a moment.",
     "PAGYL holds steady.\nSwap pressure means\nnothing to it.",
     "Page fault. Yielding\nthe section.", 2),
    ("KEEPER", "LEDGER", 45, "CACHEY",
     "I keep what's recent.\nThe rest evicts.",
     "CACHEY remembers\nthe last move you made.",
     "Cache miss. Cleared\nfor reuse.", 4),
    ("KEEPER", "VAULT", 42, "MALLOCK",
     "Each allocation\nis a promise. Wait.",
     "MALLOCK claims its\nregion and holds.",
     "Region freed. Move\nthrough.", 8),
]

LEADER_TEAM = [
    (41, "HEAPYR"),    # 27 HP, 8 DEF — the wall
    (10, "ALLOCROC"),  # 28 HP, 5 DEF — heavy attacker
    (11, "NULLPUP"),   # 14 HP, 2 DEF — finisher (low stats but status motif)
]


def build_gym_bg():
    """160x144 DMG-palette gym interior — stockroom / archive motif.

    Layout (16x16 tile grid -> 10 cols x 9 rows):
      - North wall: filing cabinets (horizontal bands)
      - Floor: solid lightest, with shelf rows running E-W between trainer pads
      - 4 trainer pads in 2 rows (pads styled as storage carrels, not duel rings)
      - Leader bench at north pedestal — a long horizontal slab (the warden's desk)
      - South entry door
      - East/West: column shelves, denser than gym-logic (the warden hoards)
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), LIGHTEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Solid floor (lightest). Add subtle horizontal shelf-rails between rows.
    for ty in (3, 6):
        y = ty * 16 + 14
        d.line((16, y, W - 17, y), fill=DARK)
        d.line((16, y + 1, W - 17, y + 1), fill=DARKEST)

    # North wall — filing cabinets, 4 horizontal bands
    d.rectangle((0, 0, W - 1, 15), fill=DARK)
    for y in (3, 7, 11):
        d.line((0, y, W - 1, y), fill=DARKEST)
    for x in range(0, W, 16):
        d.line((x, 1, x, 14), fill=DARKEST)

    # E/W walls — denser shelving (warden hoards)
    d.rectangle((0, 16, 15, H - 17), fill=DARK)
    d.rectangle((W - 16, 16, W - 1, H - 17), fill=DARK)
    for y in range(16, H - 16, 3):
        d.line((2, y, 13, y), fill=DARKEST)
        d.line((W - 14, y, W - 3, y), fill=DARKEST)

    # South wall + door
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)

    # Warden's desk — long slab centered N (3 tiles wide x 1 tall)
    px, py = 56, 20
    d.rectangle((px, py, px + 47, py + 11), fill=DARKEST)
    d.rectangle((px + 2, py + 2, px + 45, py + 9), fill=DARK)
    # MEM rune on desk: lambda-bracket pair
    d.line((px + 6, py + 4, px + 6, py + 7), fill=LIGHTEST)
    d.line((px + 6, py + 4, px + 9, py + 4), fill=LIGHTEST)
    d.line((px + 38, py + 4, px + 41, py + 4), fill=LIGHTEST)
    d.line((px + 41, py + 4, px + 41, py + 7), fill=LIGHTEST)

    # 4 trainer pads — storage-carrel style (tall, narrow, with a cabinet shadow)
    pads = [(32, 60), (112, 60), (32, 100), (112, 100)]
    for (cx, cy) in pads:
        # Pad
        d.rectangle((cx - 8, cy - 8, cx + 7, cy + 7), fill=DARK)
        d.rectangle((cx - 6, cy - 6, cx + 5, cy + 5), fill=LIGHT)
        # Cabinet behind (small dark column above pad)
        d.rectangle((cx - 4, cy - 16, cx + 3, cy - 9), fill=DARKEST)
        d.line((cx - 4, cy - 13, cx + 3, cy - 13), fill=LIGHTEST)
        # Pad number glyph (single dot)
        d.point((cx, cy), fill=DARKEST)
        d.point((cx, cy - 1), fill=DARKEST)
        d.point((cx, cy + 1), fill=DARKEST)

    # Center aisle (narrower than gym-logic — the warden likes order)
    for y in range(48, 128, 4):
        d.line((79, y, 80, y), fill=DARK)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_gym_mem.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_GYM_MEM,
        "name": "CC Gym Mem",
        "symbol": "bg_cc_gym_mem",
        "tileColors": "",
        "filename": "cc_gym_mem.png",
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


def trainer_script(idx, trg_id):
    title, tname, cid, cname, intro, boast, defeat, bit = TRAINERS[idx]
    base = f"{trg_id}-trainer-{idx}"
    eid = lambda i: f"{base}-{i:03d}"
    s = []
    s.append(text(eid(0), f"{title} {tname}\nblocks the way."))
    s.append(evt(eid(1), "EVENT_CC_TRAINER_CHALLENGE", {
        "title": title, "trainer": tname,
        "intro": "wants to fight!", "boast": intro,
    }))
    s.append(text(eid(2), f"{tname} sends out\n{cname}!"))
    s.append(set_var(eid(3), ID_VAR_OPP_ID, cid))
    s.append(evt(eid(4), "EVENT_CC_SET_STATS", {
        "idVar": ID_VAR_OPP_ID, "hpVar": ID_VAR_OPP_HP,
        "atkVar": ID_VAR_OPP_ATK, "defVar": ID_VAR_OPP_DEF,
    }))
    # SOMA-flavored fight beats — slow, status-heavy
    s.append(text(eid(5), f"You attack.\n{cname} takes it\nin stride."))
    s.append(text(eid(6), f"{cname} inflicts\nLEAK. Slow drain."))
    s.append(text(eid(7), f"You press through.\n{cname} fainted."))
    s.append(text(eid(8), f"{title} {tname}:\n{boast}"))
    s.append(text(eid(9), f"{title} {tname}:\n{defeat}"))
    return s


def write_trainer_flags(idx, eid_base):
    bit = TRAINERS[idx][7]
    var_id = f"c1bd5e01-3000-4003-8003-0000000000{60+idx:02d}"
    return [
        evt(f"{eid_base}-flagcheck", "EVENT_IF_VALUE", {
            "variable": var_id, "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(f"{eid_base}-flagset", var_id, 1),
            evt(f"{eid_base}-bitadd", "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_MEM_TRAINERS,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": bit},
                "clamp": False,
            }),
        ], "false": []}),
    ]


def _leader_battle_block(eid, base, team_entry, beat_lines):
    cid, cname = team_entry
    return [
        text(eid(base + 0), f"KILN sends out\n{cname}!"),
        set_var(eid(base + 1), ID_VAR_OPP_ID, cid),
        evt(eid(base + 2), "EVENT_CC_SET_STATS", {
            "idVar": ID_VAR_OPP_ID, "hpVar": ID_VAR_OPP_HP,
            "atkVar": ID_VAR_OPP_ATK, "defVar": ID_VAR_OPP_DEF,
        }),
        text(eid(base + 3), beat_lines[0]),
        text(eid(base + 4), beat_lines[1]),
        text(eid(base + 5), beat_lines[2]),
    ]


def leader_script(trg_id):
    base = f"{trg_id}-leader"
    eid = lambda i: f"{base}-{i:03d}"
    s = []
    s.append(evt(eid(0), "EVENT_IF_VALUE", {
        "variable": ID_VAR_MEM_TRAINERS, "operator": "<", "comparator": 15,
    }, {"true": [
        text(eid(1),
             "KEEPER KILN:\nNothing's been fired yet.\nTry the kiln-hands first."),
    ], "false": [
        text(eid(2),
             "KEEPER KILN:\nThe wares are baked.\nWill yours hold the heat?"),
        evt(eid(3), "EVENT_CC_TRAINER_CHALLENGE", {
            "title": "KEEPER", "trainer": "KILN",
            "intro": "challenges you!",
            "boast": "Endurance is honest.\nYou'll feel each round.",
        }),
        *_leader_battle_block(eid, 4, LEADER_TEAM[0], [
            "You attack.\nHEAPYR barely moves.",
            "HEAPYR inflicts\nBLOAT. Stats sag.",
            "You finish it.\nHEAPYR fainted.",
        ]),
        *_leader_battle_block(eid, 20, LEADER_TEAM[1], [
            "You attack.\nALLOCROC opens wide.",
            "ALLOCROC inflicts\nLEAK. Slow drip.",
            "You finish it.\nALLOCROC fainted.",
        ]),
        *_leader_battle_block(eid, 40, LEADER_TEAM[2], [
            "You attack.\nNULLPUP yields.",
            "NULLPUP inflicts\nNULL DEREF. Stun.",
            "You finish it.\nNULLPUP fainted.",
        ]),
        text(eid(60),
             "KEEPER KILN:\nIntact, no cracks.\nThe MEM type yields."),
        evt(eid(61), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGE_FLAG_MEM,
            "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(eid(62), ID_VAR_BADGE_FLAG_MEM, 1),
            evt(eid(63), "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_BADGES,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": 2},  # MEM bit
                "clamp": False,
            }),
        ], "false": []}),
        evt(eid(64), "EVENT_CC_BADGE_UNLOCK", {
            "badge": "MEM",
            "leaderName": "KEEPER KILN",
        }),
        text(eid(65),
             "KEEPER KILN:\nHeat-tested. Logged.\nFOREMAN HUSKE waits."),
    ]}))
    return s


def riddle_script(trg_id):
    base = f"{trg_id}-riddle"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "GYM SIGN:\nGYM-MEM.\nLeader: KEEPER KILN."),
        text(eid(1),
             "Status note:\nMEM moves use LEAK\nand BLOAT — slow drains."),
        text(eid(2),
             "CORE creatures resist\nbest. Bring stamina."),
    ]


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
    bg_path = build_gym_bg()
    print(f"Wrote {bg_path}")

    (BG_DIR / "cc_gym_mem.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_MEM_TRAINERS, "CC Gym Mem Trainers Defeated",
         "var_cc_mem_trainers_defeated"),
        (ID_VAR_BADGE_FLAG_MEM, "CC Badge Flag MEM", "var_cc_badge_flag_mem"),
    ]
    for i in range(4):
        new_vars.append((
            f"c1bd5e01-3000-4003-8003-0000000000{60+i:02d}",
            f"CC Gym Mem Trainer {i+1} Flag",
            f"var_cc_gym_mem_trainer_{i+1}_flag",
        ))
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    scene_dir = SCENES_DIR / "cinder_gym_mem"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_GYM_MEM,
        "_index": 3,
        "type": "TOPDOWN",
        "name": "GYM-MEM",
        "symbol": "scene_gym_mem",
        "x": 1200, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_GYM_MEM,
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

    # Tile coords: pads at (32,60),(112,60),(32,100),(112,100) in pixels.
    # GB tile grid is 8x8 — but scene coords use 8px tiles for triggers, so
    # divide by 8: (4,7),(14,7),(4,12),(14,12). Trigger size 2x2 tiles.
    pads_tile = [(4, 7), (14, 7), (4, 12), (14, 12)]
    leader_tile = (9, 3)   # in front of warden's desk
    riddle_tile = (9, 16)  # near south door

    trigger_files = []
    for i in range(4):
        tx, ty = pads_tile[i]
        s = trainer_script(i, TRG_TRAINER[i])
        s += write_trainer_flags(i, f"{TRG_TRAINER[i]}-postfight")
        tf = trigger_file(
            TRG_TRAINER[i], f"Mem Trainer {i+1}", f"trigger_mem_t{i+1}",
            tx, ty, 2, 2, i, s,
        )
        trigger_files.append((f"trainer_{i+1}.gbsres", tf))

    tf_leader = trigger_file(
        TRG_LEADER, "Mem Leader KILN", "trigger_mem_leader",
        leader_tile[0], leader_tile[1], 2, 2, 4,
        leader_script(TRG_LEADER),
    )
    trigger_files.append(("leader.gbsres", tf_leader))

    tf_riddle = trigger_file(
        TRG_RIDDLE, "Mem Sign", "trigger_mem_sign",
        riddle_tile[0], riddle_tile[1], 2, 1, 5,
        riddle_script(TRG_RIDDLE),
    )
    trigger_files.append(("sign.gbsres", tf_riddle))

    for fname, tf in trigger_files:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(trigger_files)} triggers")

    print("\nGYM-MEM built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
