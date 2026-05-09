#!/usr/bin/env python3
"""Build GYM-DATA scene — fourth gym, CARRIER WICK, 4 trainers + leader.

Generates:
  cinder-starter/assets/backgrounds/cc_gym_data.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_gym_data.png.gbsres
  cinder-starter/project/scenes/cinder_gym_data/{scene.gbsres,triggers/*}
  Updates variables.gbsres (adds DATA badge flag + per-trainer flags)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-gym-data.py

Idempotent — stable UUIDs, safe to re-run.

Design (CINDER-CREATURES-RPG.md):
  - GYM-DATA, leader CARRIER WICK, badge DATA, bit value = 8.
  - Personality: restless, talkative. Specialty: RNG fights, swarms, multi-hits.
  - Floor layout: parcel sort station / pneumatic tubes. 4 sorting-table pads.
  - Trainers fight DATA creatures (BYTEFLY / CACHEBIT / CSVOLE / JSONIA).
  - Leader team: REGEXEL / INTGAR / STRTERM (chatty DATA hitters, swarm motifs).
  - Leader gate: only opens when all 4 trainer bits set (DATA trainers var == 15).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs — distinct from gym-logic/mem/proc.
ID_BG_GYM_DATA = "c1bd5e01-1000-4001-8001-000000000040"
ID_SCENE_GYM_DATA = "c1bd5e01-2000-4002-8002-000000000040"

# Reused vars
ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# New for gym-data
ID_VAR_DATA_TRAINERS = "c1bd5e01-3000-4003-8003-000000000080"
ID_VAR_BADGE_FLAG_DATA = "c1bd5e01-3000-4003-8003-000000000081"

TRG_TRAINER = [f"c1bd5e01-4000-4004-8004-0000000000{0xa0+i:02x}" for i in range(4)]
TRG_LEADER = "c1bd5e01-4000-4004-8004-0000000000b0"
TRG_RIDDLE = "c1bd5e01-4000-4004-8004-0000000000b1"

# CARRIER WICK — restless, talkative. Swarm + multi-hit + RNG.
# Trainers wear "COURIER" titles — they sort the mail.
TRAINERS = [
    ("COURIER", "PACKET", 6, "BYTEFLY",
     "Five updates, every minute.\nKeep up.",
     "BYTEFLY swarms\nthe inbox. Loud.",
     "Channel quiet.\nClear the desk.", 1),
    ("COURIER", "STREAM", 12, "CACHEBIT",
     "I never stop talking.\nNeither does my mon.",
     "CACHEBIT replays\nthe last beat. Annoying.",
     "Pipe drained.\nMove along.", 2),
    ("COURIER", "QUEUE", 33, "CSVOLE",
     "Wait your turn.\nThen dont.",
     "CSVOLE drops\nthree at once. Catch up.",
     "Backlog cleared.\nGo.", 4),
    ("COURIER", "FLUSH", 32, "JSONIA",
     "Bracket. Comma. Bracket.\nBrace yourself.",
     "JSONIA opens twelve\nbraces. Confusing.",
     "Buffer empty.\nThe lane is yours.", 8),
]

LEADER_TEAM = [
    (8,  "REGEXEL"),   # 17/7/3 — pattern-match opener with SWARM
    (36, "INTGAR"),    # 18/5/4 — talky tank, MISDIRECT
    (38, "STRTERM"),   # 16/5/3 (placeholder if stats differ) — closer, BURST
]


def build_gym_bg():
    """160x144 DMG-palette gym interior — courier sort station / tubes.

    Layout (16x16 tile grid -> 10 cols x 9 rows):
      - North wall: parcel grid (small cell stacks)
      - E/W: pneumatic tubes (vertical pipes with capsule blips)
      - Floor: 4 sorting tables (square pads with rune)
      - Hub (north center): WICK's console — wide dais with stacked-dot rune
      - South: entry door
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), LIGHTEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Floor — light pattern of address lines (faint horizontal bands)
    for y in range(20, H - 20, 8):
        d.line((20, y, W - 21, y), fill=LIGHT)

    # North wall — parcel grid (rows of small cells)
    d.rectangle((0, 0, W - 1, 15), fill=DARK)
    for cx in range(2, W - 2, 8):
        for cy in range(2, 14, 6):
            d.rectangle((cx, cy, cx + 5, cy + 3), fill=DARKEST)
            d.point((cx + 4, cy + 2), fill=LIGHTEST)  # tiny address bit

    # E/W walls — pneumatic tubes (vertical pipes with capsule blips)
    d.rectangle((0, 16, 15, H - 17), fill=DARK)
    d.rectangle((W - 16, 16, W - 1, H - 17), fill=DARK)
    for tx in (4, 10, W - 11, W - 5):
        d.line((tx, 16, tx, H - 17), fill=DARKEST)
    # Capsule blips — moving capsules at varying heights
    for y in (28, 56, 88, 116):
        d.rectangle((3, y, 5, y + 4), fill=LIGHTEST)
        d.rectangle((9, y - 8, 11, y - 4), fill=LIGHTEST)
        d.rectangle((W - 6, y + 4, W - 4, y + 8), fill=LIGHTEST)
        d.rectangle((W - 12, y, W - 10, y + 4), fill=LIGHTEST)

    # South wall + door
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)

    # WICK's console — wide dais, stacked-dot rune (DATA signature)
    px, py = 56, 22
    d.rectangle((px, py, px + 47, py + 9), fill=DARKEST)
    d.rectangle((px + 2, py + 2, px + 45, py + 7), fill=DARK)
    # DATA rune: 3 stacked dots, lower-right
    rx, ry = px + 38, py + 3
    d.point((rx, ry), fill=LIGHTEST)
    d.point((rx, ry + 2), fill=LIGHTEST)
    d.point((rx, ry + 4), fill=LIGHTEST)
    # Console terminals: small bumps on the front of the dais
    for tx in (px + 6, px + 18, px + 30):
        d.rectangle((tx, py + 4, tx + 3, py + 6), fill=LIGHTEST)

    # 4 sorting tables — square pads with parcel stack
    pads = [(32, 80), (64, 80), (96, 80), (128, 80)]
    for (cx, cy) in pads:
        d.rectangle((cx - 8, cy - 8, cx + 8, cy + 8), fill=DARK)
        d.rectangle((cx - 6, cy - 6, cx + 6, cy + 6), fill=LIGHT)
        # Tiny parcel stack
        d.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), fill=DARKEST)
        d.line((cx - 3, cy, cx + 3, cy), fill=LIGHT)
        d.line((cx, cy - 3, cx, cy + 3), fill=LIGHT)

    # Conveyor belt below pads — dashed bar
    d.rectangle((16, 100, W - 17, 102), fill=DARKEST)
    for bx in range(20, W - 20, 6):
        d.point((bx, 101), fill=LIGHTEST)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_gym_data.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_GYM_DATA,
        "name": "CC Gym Data",
        "symbol": "bg_cc_gym_data",
        "tileColors": "",
        "filename": "cc_gym_data.png",
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
    s.append(text(eid(0), f"{title} {tname}\nopens the channel."))
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
    # WICK-flavored fight beats — swarm / multi-hit / RNG
    s.append(text(eid(5), f"You attack.\n{cname} forks into\nthree copies."))
    s.append(text(eid(6), f"{cname} inflicts\nSWARM. Three hits."))
    s.append(text(eid(7), f"You hit the broadcast.\n{cname} fainted."))
    s.append(text(eid(8), f"{title} {tname}:\n{boast}"))
    s.append(text(eid(9), f"{title} {tname}:\n{defeat}"))
    return s


def write_trainer_flags(idx, eid_base):
    bit = TRAINERS[idx][7]
    var_id = f"c1bd5e01-3000-4003-8003-0000000000{82+idx:02d}"
    return [
        evt(f"{eid_base}-flagcheck", "EVENT_IF_VALUE", {
            "variable": var_id, "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(f"{eid_base}-flagset", var_id, 1),
            evt(f"{eid_base}-bitadd", "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_DATA_TRAINERS,
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
        text(eid(base + 0), f"WICK sends out\n{cname}!"),
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
        "variable": ID_VAR_DATA_TRAINERS, "operator": "<", "comparator": 15,
    }, {"true": [
        text(eid(1),
             "CARRIER WICK:\nThere are letters out.\nRead the room first."),
    ], "false": [
        text(eid(2),
             "CARRIER WICK:\nManifest is settled.\nFeed me into the flame."),
        evt(eid(3), "EVENT_CC_TRAINER_CHALLENGE", {
            "title": "CARRIER", "trainer": "WICK",
            "intro": "challenges you!",
            "boast": "I send. You receive.\nThree messages. Go.",
        }),
        *_leader_battle_block(eid, 4, LEADER_TEAM[0], [
            "You attack.\nREGEXEL captures the\npattern of your move.",
            "REGEXEL inflicts\nSWARM. Two hits, then a third.",
            "You break the regex.\nREGEXEL fainted.",
        ]),
        *_leader_battle_block(eid, 20, LEADER_TEAM[1], [
            "You attack.\nINTGAR overflows. Reverts.",
            "INTGAR inflicts\nMISDIRECT. Wrong target.",
            "You hit the right one.\nINTGAR fainted.",
        ]),
        *_leader_battle_block(eid, 40, LEADER_TEAM[2], [
            "You attack.\nSTRTERM truncates\nyour string.",
            "STRTERM inflicts\nBURST. Three back-to-back.",
            "You finish the message.\nSTRTERM fainted.",
        ]),
        text(eid(60),
             "CARRIER WICK:\nDelivered. Receipt signed.\nThe DATA type holds."),
        evt(eid(61), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGE_FLAG_DATA,
            "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(eid(62), ID_VAR_BADGE_FLAG_DATA, 1),
            evt(eid(63), "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_BADGES,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": 8},  # DATA bit
                "clamp": False,
            }),
        ], "false": []}),
        evt(eid(64), "EVENT_CC_BADGE_UNLOCK", {
            "badge": "DATA",
            "leaderName": "CARRIER WICK",
        }),
        text(eid(65),
             "CARRIER WICK:\nSealed and stamped.\nSTOKER HEARTH closes the loop."),
    ]}))
    return s


def riddle_script(trg_id):
    base = f"{trg_id}-riddle"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "GYM SIGN:\nGYM-DATA.\nLeader: CARRIER WICK."),
        text(eid(1),
             "Status note:\nDATA moves use SWARM\nand MISDIRECT — multi-hit RNG."),
        text(eid(2),
             "MEM folds to DATA?\nNo. CORE folds to MEM.\nDATA folds to PROC."),
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

    (BG_DIR / "cc_gym_data.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_DATA_TRAINERS, "CC Gym Data Trainers Defeated",
         "var_cc_data_trainers_defeated"),
        (ID_VAR_BADGE_FLAG_DATA, "CC Badge Flag DATA", "var_cc_badge_flag_data"),
    ]
    for i in range(4):
        new_vars.append((
            f"c1bd5e01-3000-4003-8003-0000000000{82+i:02d}",
            f"CC Gym Data Trainer {i+1} Flag",
            f"var_cc_gym_data_trainer_{i+1}_flag",
        ))
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    scene_dir = SCENES_DIR / "cinder_gym_data"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_GYM_DATA,
        "_index": 5,
        "type": "TOPDOWN",
        "name": "GYM-DATA",
        "symbol": "scene_gym_data",
        "x": 1900, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_GYM_DATA,
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
    leader_tile = (10, 4)   # in front of WICK's console
    riddle_tile = (9, 16)   # near south door

    trigger_files = []
    for i in range(4):
        tx, ty = pads_tile[i]
        s = trainer_script(i, TRG_TRAINER[i])
        s += write_trainer_flags(i, f"{TRG_TRAINER[i]}-postfight")
        tf = trigger_file(
            TRG_TRAINER[i], f"Data Trainer {i+1}", f"trigger_data_t{i+1}",
            tx, ty, 2, 2, i, s,
        )
        trigger_files.append((f"trainer_{i+1}.gbsres", tf))

    tf_leader = trigger_file(
        TRG_LEADER, "Data Leader WICK", "trigger_data_leader",
        leader_tile[0], leader_tile[1], 2, 2, 4,
        leader_script(TRG_LEADER),
    )
    trigger_files.append(("leader.gbsres", tf_leader))

    tf_riddle = trigger_file(
        TRG_RIDDLE, "Data Sign", "trigger_data_sign",
        riddle_tile[0], riddle_tile[1], 2, 1, 5,
        riddle_script(TRG_RIDDLE),
    )
    trigger_files.append(("sign.gbsres", tf_riddle))

    for fname, tf in trigger_files:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(trigger_files)} triggers")

    print("\nGYM-DATA built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
