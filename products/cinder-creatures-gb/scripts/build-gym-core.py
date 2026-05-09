#!/usr/bin/env python3
"""Build GYM-CORE scene — fifth and final gym, STOKER HEARTH, 4 trainers + leader.

Generates:
  cinder-starter/assets/backgrounds/cc_gym_core.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_gym_core.png.gbsres
  cinder-starter/project/scenes/cinder_gym_core/{scene.gbsres,triggers/*}
  Updates variables.gbsres (adds CORE badge flag + per-trainer flags)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-gym-core.py

Idempotent — stable UUIDs, safe to re-run.

Design (CINDER-CREATURES-RPG.md):
  - GYM-CORE, leader STOKER HEARTH, badge CORE, bit value = 16.
  - Personality: quiet, tank, last to fold.
  - Combat: rotation of all 5 types, no STAB advantage — the foundation type.
  - Floor layout: foundry / load-bearing scaffolds. 4 anvil pads.
  - Trainers (FOREMEN) fight CORE creatures (ARMOTE / RISKIT / CISCOTL / PIPELYNX).
  - Leader team: KERNITE (CORE) -> ANDOWL (LOGIC) -> BUFFROG (MEM) ->
                 SCHEDOG (PROC) -> GRAFTLE (DATA). One of each type. Tank,
                 but no super-effective STAB to lean on.
  - Leader gate: opens when all 4 trainer bits set (CORE trainers var == 15).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs — distinct from gym-logic/mem/proc/data.
ID_BG_GYM_CORE = "c1bd5e01-1000-4001-8001-000000000050"
ID_SCENE_GYM_CORE = "c1bd5e01-2000-4002-8002-000000000050"

# Reused vars
ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# New for gym-core
ID_VAR_CORE_TRAINERS = "c1bd5e01-3000-4003-8003-000000000090"
ID_VAR_BADGE_FLAG_CORE = "c1bd5e01-3000-4003-8003-000000000091"

TRG_TRAINER = [f"c1bd5e01-4000-4004-8004-0000000000{0xc0+i:02x}" for i in range(4)]
TRG_LEADER = "c1bd5e01-4000-4004-8004-0000000000d0"
TRG_RIDDLE = "c1bd5e01-4000-4004-8004-0000000000d1"

# STOKER HEARTH — quiet, tank, last to fold. Steady. No flourishes.
# Trainers wear "FOREMAN" titles — they hold the floor up.
TRAINERS = [
    ("FOREMAN", "GIRDER", 19, "ARMOTE",
     "Stand under load.\nNot for show.",
     "ARMOTE planted.\nIt does not move.",
     "Floor still stands.\nGood.", 1),
    ("FOREMAN", "STRUT", 20, "RISKIT",
     "Less moves. More weight.\nThats the trade.",
     "RISKIT braces. Every hit\nlands the same.",
     "Truss holds.\nOn.", 2),
    ("FOREMAN", "RIVET", 21, "CISCOTL",
     "We carry one job.\nWe carry it slow.",
     "CISCOTL eats hits.\nReturns one.",
     "Seam set.\nStep through.", 4),
    ("FOREMAN", "BEAM", 22, "PIPELYNX",
     "Quiet line.\nLasts the longest.",
     "PIPELYNX takes the\nbrunt. In stages.",
     "Span clear.\nClimb up.", 8),
]

# Leader team: rotation of all 5 types — that's HEARTH's signature.
# Tank-leaning picks across the chart, no creature gets STAB from HEARTH.
LEADER_TEAM = [
    (3,  "KERNITE",  "CORE"),    # 30/4/8 — opens like a wall
    (27, "ANDOWL",   "LOGIC"),   # 19/6/5 — patient AND-gate
    (46, "BUFFROG",  "MEM"),     # 22/5/6 — queues, holds, returns
    (18, "SCHEDOG",  "PROC"),    # 20/6/5 — takes turns
    (50, "GRAFTLE",  "DATA"),    # 19/5/5 — closer, all things connected
]


def build_gym_bg():
    """160x144 DMG-palette gym interior — foundry / load-bearing floor.

    Layout (16x16 tile grid -> 10 cols x 9 rows):
      - North wall: scaffolding lattice (heavy crossed beams)
      - E/W: load-bearing pillars (thick verticals with bolt rivets)
      - Floor: 4 anvil pads (squat squares with diagonal nucleus rune)
      - Hub (north center): HEARTH's plinth — wide low platform with diagonal CORE rune
      - South: entry door
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), LIGHTEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Floor — light cross-hatched grid, low contrast (heavy plate floor)
    for y in range(20, H - 20, 8):
        d.line((20, y, W - 21, y), fill=LIGHT)
    for x in range(24, W - 20, 16):
        d.line((x, 20, x, H - 21), fill=LIGHT)

    # North wall — crossed scaffolding lattice
    d.rectangle((0, 0, W - 1, 15), fill=DARK)
    # Diagonal beams forming X patterns
    for cx in range(4, W - 2, 16):
        d.line((cx, 2, cx + 12, 13), fill=DARKEST)
        d.line((cx + 12, 2, cx, 13), fill=DARKEST)
    # Top rivet line
    for rx in range(6, W - 4, 8):
        d.point((rx, 1), fill=LIGHTEST)

    # E/W walls — load-bearing pillars with bolt rivets
    d.rectangle((0, 16, 15, H - 17), fill=DARK)
    d.rectangle((W - 16, 16, W - 1, H - 17), fill=DARK)
    # Vertical pillar shadow lines
    for px in (3, 11, W - 12, W - 4):
        d.line((px, 16, px, H - 17), fill=DARKEST)
    # Bolts at fixed heights — quiet, regular
    for y in (24, 48, 72, 96, 120):
        d.point((7, y), fill=LIGHTEST)
        d.point((W - 8, y), fill=LIGHTEST)

    # South wall + door
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)

    # HEARTH's plinth — wide low dais, diagonal nucleus CORE rune
    px, py = 56, 22
    d.rectangle((px, py, px + 47, py + 11), fill=DARKEST)
    d.rectangle((px + 2, py + 2, px + 45, py + 9), fill=DARK)
    # CORE rune: diagonal line through a small box (the nucleus mark)
    rx, ry = px + 38, py + 3
    d.rectangle((rx, ry, rx + 5, ry + 5), fill=LIGHT)
    d.line((rx, ry, rx + 5, ry + 5), fill=LIGHTEST)
    # Plinth bolts: heavy corner rivets on the dais
    for cx in (px + 3, px + 44):
        for cy in (py + 1, py + 9):
            d.point((cx, cy), fill=LIGHTEST)

    # 4 anvil pads — squat squares, slightly larger than other gyms
    pads = [(32, 80), (64, 80), (96, 80), (128, 80)]
    for (cx, cy) in pads:
        d.rectangle((cx - 9, cy - 8, cx + 9, cy + 8), fill=DARKEST)
        d.rectangle((cx - 7, cy - 6, cx + 7, cy + 6), fill=DARK)
        d.rectangle((cx - 4, cy - 4, cx + 4, cy + 4), fill=LIGHT)
        # Anvil center mark — single bolt
        d.point((cx, cy), fill=LIGHTEST)
        # Diagonal nucleus rune corner
        d.line((cx - 3, cy - 3, cx + 3, cy + 3), fill=DARKEST)

    # Load-bearing center beam below pads — solid bar, no decoration
    d.rectangle((16, 100, W - 17, 103), fill=DARKEST)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_gym_core.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_GYM_CORE,
        "name": "CC Gym Core",
        "symbol": "bg_cc_gym_core",
        "tileColors": "",
        "filename": "cc_gym_core.png",
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
    s.append(text(eid(0), f"{title} {tname}\nshoulders the load."))
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
    # HEARTH-flavored beats — slow, durable, last-to-fold.
    s.append(text(eid(5), f"You attack.\n{cname} braces.\nThe blow does not move it."))
    s.append(text(eid(6), f"{cname} returns one hit.\nIt lands twice as hard."))
    s.append(text(eid(7), f"You wear it down.\n{cname} fainted."))
    s.append(text(eid(8), f"{title} {tname}:\n{boast}"))
    s.append(text(eid(9), f"{title} {tname}:\n{defeat}"))
    return s


def write_trainer_flags(idx, eid_base):
    bit = TRAINERS[idx][7]
    var_id = f"c1bd5e01-3000-4003-8003-0000000000{0x92+idx:02x}"
    return [
        evt(f"{eid_base}-flagcheck", "EVENT_IF_VALUE", {
            "variable": var_id, "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(f"{eid_base}-flagset", var_id, 1),
            evt(f"{eid_base}-bitadd", "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_CORE_TRAINERS,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": bit},
                "clamp": False,
            }),
        ], "false": []}),
    ]


def _leader_battle_block(eid, base, team_entry, beat_lines):
    cid, cname, ctype = team_entry
    return [
        text(eid(base + 0), f"HEARTH rotates in\n{cname} ({ctype})."),
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
        "variable": ID_VAR_CORE_TRAINERS, "operator": "<", "comparator": 15,
    }, {"true": [
        text(eid(1),
             "STOKER HEARTH:\nThe coals aren't ready.\nTalk to the bench first."),
    ], "false": [
        text(eid(2),
             "STOKER HEARTH:\nBed is hot enough.\nFive types in the embers. Bring them."),
        evt(eid(3), "EVENT_CC_TRAINER_CHALLENGE", {
            "title": "STOKER", "trainer": "HEARTH",
            "intro": "challenges you!",
            "boast": "I lean on every type.\nFind the one that bends.",
        }),
        *_leader_battle_block(eid, 4, LEADER_TEAM[0], [
            "You attack.\nKERNITE absorbs it.\nNo crack appears.",
            "KERNITE returns slowly.\nThe blow lands flat.",
            "You chip it through.\nKERNITE fainted.",
        ]),
        *_leader_battle_block(eid, 20, LEADER_TEAM[1], [
            "You attack.\nANDOWL waits for both\nconditions to meet.",
            "ANDOWL strikes only\nwhen the gate is true.",
            "You break the AND.\nANDOWL fainted.",
        ]),
        *_leader_battle_block(eid, 40, LEADER_TEAM[2], [
            "You attack.\nBUFFROG queues your hit\nfor later.",
            "BUFFROG flushes the queue.\nThree blows return.",
            "You drain the buffer.\nBUFFROG fainted.",
        ]),
        *_leader_battle_block(eid, 60, LEADER_TEAM[3], [
            "You attack.\nSCHEDOG yields the turn.\nThen takes two.",
            "SCHEDOG inflicts\nROUND-ROBIN. Your turn skips.",
            "You preempt.\nSCHEDOG fainted.",
        ]),
        *_leader_battle_block(eid, 80, LEADER_TEAM[4], [
            "You attack.\nGRAFTLE pulls the whole\nfloor with it.",
            "GRAFTLE inflicts\nWEB. Every hit cascades.",
            "You sever the graph.\nGRAFTLE fainted.",
        ]),
        text(eid(100),
             "STOKER HEARTH:\nThe core admits it.\nThe ember stays awake."),
        evt(eid(101), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGE_FLAG_CORE,
            "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(eid(102), ID_VAR_BADGE_FLAG_CORE, 1),
            evt(eid(103), "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_BADGES,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": 16},  # CORE bit
                "clamp": False,
            }),
        ], "false": []}),
        evt(eid(104), "EVENT_CC_BADGE_UNLOCK", {
            "badge": "CORE",
            "leaderName": "STOKER HEARTH",
        }),
        text(eid(105),
             "STOKER HEARTH:\nFive badges. The fire is yours.\nVOID waits in SECTOR-9."),
    ]}))
    return s


def riddle_script(trg_id):
    base = f"{trg_id}-riddle"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "GYM SIGN:\nGYM-CORE.\nLeader: STOKER HEARTH."),
        text(eid(1),
             "Note:\nCORE has no STAB advantage.\nIt is the floor everything\nelse stands on."),
        text(eid(2),
             "Hint:\nMEM folds CORE.\nCORE folds nothing.\nThat is the deal."),
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

    (BG_DIR / "cc_gym_core.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_CORE_TRAINERS, "CC Gym Core Trainers Defeated",
         "var_cc_core_trainers_defeated"),
        (ID_VAR_BADGE_FLAG_CORE, "CC Badge Flag CORE", "var_cc_badge_flag_core"),
    ]
    for i in range(4):
        new_vars.append((
            f"c1bd5e01-3000-4003-8003-0000000000{0x92+i:02x}",
            f"CC Gym Core Trainer {i+1} Flag",
            f"var_cc_gym_core_trainer_{i+1}_flag",
        ))
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    scene_dir = SCENES_DIR / "cinder_gym_core"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_GYM_CORE,
        "_index": 6,
        "type": "TOPDOWN",
        "name": "GYM-CORE",
        "symbol": "scene_gym_core",
        "x": 2200, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_GYM_CORE,
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

    # Pads at (32,80),(64,80),(96,80),(128,80) in pixels
    # Tiles (8px): (4,10),(8,10),(12,10),(16,10). Trigger size 2x2 tiles.
    pads_tile = [(4, 10), (8, 10), (12, 10), (16, 10)]
    leader_tile = (10, 4)   # in front of HEARTH's plinth
    riddle_tile = (9, 16)   # near south door

    trigger_files = []
    for i in range(4):
        tx, ty = pads_tile[i]
        s = trainer_script(i, TRG_TRAINER[i])
        s += write_trainer_flags(i, f"{TRG_TRAINER[i]}-postfight")
        tf = trigger_file(
            TRG_TRAINER[i], f"Core Trainer {i+1}", f"trigger_core_t{i+1}",
            tx, ty, 2, 2, i, s,
        )
        trigger_files.append((f"trainer_{i+1}.gbsres", tf))

    tf_leader = trigger_file(
        TRG_LEADER, "Core Leader HEARTH", "trigger_core_leader",
        leader_tile[0], leader_tile[1], 2, 2, 4,
        leader_script(TRG_LEADER),
    )
    trigger_files.append(("leader.gbsres", tf_leader))

    tf_riddle = trigger_file(
        TRG_RIDDLE, "Core Sign", "trigger_core_sign",
        riddle_tile[0], riddle_tile[1], 2, 1, 5,
        riddle_script(TRG_RIDDLE),
    )
    trigger_files.append(("sign.gbsres", tf_riddle))

    for fname, tf in trigger_files:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(trigger_files)} triggers")

    print("\nGYM-CORE built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
