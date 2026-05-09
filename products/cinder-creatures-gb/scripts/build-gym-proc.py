#!/usr/bin/env python3
"""Build GYM-PROC scene — third gym, CONDUCTOR TEMPO, 4 trainers + leader.

Generates:
  cinder-starter/assets/backgrounds/cc_gym_proc.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_gym_proc.png.gbsres
  cinder-starter/project/scenes/cinder_gym_proc/{scene.gbsres,triggers/*}
  Updates variables.gbsres (adds PROC badge flag + per-trainer flags)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-gym-proc.py

Idempotent — stable UUIDs, safe to re-run.

Design (CINDER-CREATURES-RPG.md):
  - GYM-PROC, leader CONDUCTOR TEMPO, badge PROC, bit value = 4.
  - Personality: rapid, clipped, dancer. Specialty: speed + interrupts (STUN).
  - Floor layout: running lanes / metronome motif. 4 RUNNER trainer pads on lanes.
  - Trainers fight PROC creatures (THREDLE / PIDGON / NICEKIT / SCHEDOG).
  - Leader team: SIGNAUR / ZYBORG / FORKLING (fast attackers, interrupt-heavy).
  - Leader gate: only opens when all 4 trainer bits set (PROC trainers var == 15).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs — distinct from gym-logic/mem (000000000030+)
ID_BG_GYM_PROC = "c1bd5e01-1000-4001-8001-000000000030"
ID_SCENE_GYM_PROC = "c1bd5e01-2000-4002-8002-000000000030"

# Reused vars
ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# New for gym-proc
ID_VAR_PROC_TRAINERS = "c1bd5e01-3000-4003-8003-000000000070"
ID_VAR_BADGE_FLAG_PROC = "c1bd5e01-3000-4003-8003-000000000071"

TRG_TRAINER = [f"c1bd5e01-4000-4004-8004-0000000000{80+i:02d}" for i in range(4)]
TRG_LEADER = "c1bd5e01-4000-4004-8004-000000000090"
TRG_RIDDLE = "c1bd5e01-4000-4004-8004-000000000091"

# CONDUCTOR TEMPO — rapid, clipped, dancer. Speed + interrupts (STUN).
# Trainers wear "RUNNER" titles — they pace the lanes.
TRAINERS = [
    ("RUNNER", "PULSE", 13, "THREDLE",
     "On the beat. Keep up.",
     "THREDLE forks again.\nStay on count.",
     "Off-tempo. I yield\nthe lane.", 1),
    ("RUNNER", "RELAY", 15, "PIDGON",
     "Pass the baton.\nNo stops.",
     "PIDGON carries\nthe process forward.",
     "Handoff dropped.\nClear the track.", 2),
    ("RUNNER", "TICK", 17, "NICEKIT",
     "I move slow on\npurpose. Yield me.",
     "NICEKIT lowers\nits priority. Sneaky.",
     "Niced out. Step\nthrough.", 4),
    ("RUNNER", "QUANT", 18, "SCHEDOG",
     "Time-slice. You\nget a turn. So do I.",
     "SCHEDOG takes turns.\nFair. Fast. Final.",
     "Quantum exhausted.\nThe lane is yours.", 8),
]

LEADER_TEAM = [
    (16, "SIGNAUR"),   # 22 HP, ATK 7 — opener with signal/STUN
    (14, "ZYBORG"),    # 24 HP, ATK 6 — won't stay dead
    (1,  "FORKLING"),  # 18 HP, ATK 6 — cleaves into two
]


def build_gym_bg():
    """160x144 DMG-palette gym interior — running lanes / conductor stage.

    Layout (16x16 tile grid -> 10 cols x 9 rows):
      - North wall: metronome wedges (triangular ticks)
      - Floor: 4 running lanes (vertical bands separated by line markers)
      - 4 trainer pads on lanes (round, lane-1..lane-4)
      - Conductor's stage at north pedestal — square dais with baton mark
      - South entry door
      - E/W: lane fencing (vertical pickets)
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), LIGHTEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Floor — 4 vertical lane bands, separated by dashed lines
    lanes_x = [32, 64, 96, 128]
    for lx in lanes_x[:-1]:
        for y in range(20, H - 20, 4):
            d.line((lx + 16, y, lx + 16, y + 1), fill=DARK)

    # North wall — metronome wedges (triangle teeth)
    d.rectangle((0, 0, W - 1, 15), fill=DARK)
    for i in range(0, W, 8):
        d.polygon([(i, 14), (i + 4, 4), (i + 8, 14)], fill=DARKEST)

    # E/W walls — lane fencing (vertical pickets)
    d.rectangle((0, 16, 15, H - 17), fill=DARK)
    d.rectangle((W - 16, 16, W - 1, H - 17), fill=DARK)
    for y in range(20, H - 20, 6):
        d.line((4, y, 4, y + 3), fill=DARKEST)
        d.line((10, y, 10, y + 3), fill=DARKEST)
        d.line((W - 11, y, W - 11, y + 3), fill=DARKEST)
        d.line((W - 5, y, W - 5, y + 3), fill=DARKEST)

    # South wall + door
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)

    # Conductor's stage — square dais centered N, baton mark
    px, py = 64, 22
    d.rectangle((px, py, px + 31, py + 9), fill=DARKEST)
    d.rectangle((px + 2, py + 2, px + 29, py + 7), fill=DARK)
    # PROC rune on dais: arrow-tail (right-pointing chevron)
    d.line((px + 12, py + 4, px + 18, py + 4), fill=LIGHTEST)
    d.line((px + 16, py + 2, px + 18, py + 4), fill=LIGHTEST)
    d.line((px + 16, py + 6, px + 18, py + 4), fill=LIGHTEST)

    # 4 trainer pads — round (lane runners), one per lane
    pads = [(32, 80), (64, 80), (96, 80), (128, 80)]
    for (cx, cy) in pads:
        # Round-ish pad (DMG only does pixel rects — fake circle)
        d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=DARK)
        d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=LIGHT)
        # Tick mark on pad — runner number
        d.point((cx, cy), fill=DARKEST)
        d.point((cx, cy - 2), fill=DARKEST)
        d.point((cx, cy + 2), fill=DARKEST)

    # Start line below pads — solid horizontal bar
    d.line((16, 100, W - 17, 100), fill=DARKEST)
    d.line((16, 102, W - 17, 102), fill=DARK)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_gym_proc.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_GYM_PROC,
        "name": "CC Gym Proc",
        "symbol": "bg_cc_gym_proc",
        "tileColors": "",
        "filename": "cc_gym_proc.png",
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
    s.append(text(eid(0), f"{title} {tname}\nblocks the lane."))
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
    # TEMPO-flavored fight beats — fast, interrupt-heavy
    s.append(text(eid(5), f"You attack.\n{cname} ducks the\nfirst beat."))
    s.append(text(eid(6), f"{cname} inflicts\nSTUN. You skip a turn."))
    s.append(text(eid(7), f"You catch the rhythm.\n{cname} fainted."))
    s.append(text(eid(8), f"{title} {tname}:\n{boast}"))
    s.append(text(eid(9), f"{title} {tname}:\n{defeat}"))
    return s


def write_trainer_flags(idx, eid_base):
    bit = TRAINERS[idx][7]
    var_id = f"c1bd5e01-3000-4003-8003-0000000000{72+idx:02d}"
    return [
        evt(f"{eid_base}-flagcheck", "EVENT_IF_VALUE", {
            "variable": var_id, "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(f"{eid_base}-flagset", var_id, 1),
            evt(f"{eid_base}-bitadd", "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_PROC_TRAINERS,
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
        text(eid(base + 0), f"TEMPO sends out\n{cname}!"),
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
        "variable": ID_VAR_PROC_TRAINERS, "operator": "<", "comparator": 15,
    }, {"true": [
        text(eid(1),
             "CONDUCTOR TEMPO:\nFinish the lanes.\nThen the stage."),
    ], "false": [
        text(eid(2),
             "CONDUCTOR TEMPO:\nOn time. Good.\nKeep up."),
        evt(eid(3), "EVENT_CC_TRAINER_CHALLENGE", {
            "title": "CONDUCTOR", "trainer": "TEMPO",
            "intro": "challenges you!",
            "boast": "Three beats. Three falls.\nGo.",
        }),
        *_leader_battle_block(eid, 4, LEADER_TEAM[0], [
            "You attack.\nSIGNAUR signals first.",
            "SIGNAUR inflicts\nSTUN. You miss a beat.",
            "You answer in tempo.\nSIGNAUR fainted.",
        ]),
        *_leader_battle_block(eid, 20, LEADER_TEAM[1], [
            "You attack.\nZYBORG won't stay down.",
            "ZYBORG inflicts\nINTERRUPT. Reroll.",
            "You time it right.\nZYBORG fainted.",
        ]),
        *_leader_battle_block(eid, 40, LEADER_TEAM[2], [
            "You attack.\nFORKLING splits in two.",
            "FORKLING inflicts\nFORK. Two hits at once.",
            "You finish the line.\nFORKLING fainted.",
        ]),
        text(eid(60),
             "CONDUCTOR TEMPO:\nYou kept tempo.\nThat's rare. Move on."),
        evt(eid(61), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGE_FLAG_PROC,
            "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(eid(62), ID_VAR_BADGE_FLAG_PROC, 1),
            evt(eid(63), "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_BADGES,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": 4},  # PROC bit
                "clamp": False,
            }),
        ], "false": []}),
        evt(eid(64), "EVENT_CC_BADGE_UNLOCK", {
            "badge": "PROC",
            "leaderName": "CONDUCTOR TEMPO",
        }),
        text(eid(65),
             "CONDUCTOR TEMPO:\nFind HERMES next.\nThey talk fast. Listen."),
    ]}))
    return s


def riddle_script(trg_id):
    base = f"{trg_id}-riddle"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "GYM SIGN:\nGYM-PROC.\nLeader: CONDUCTOR TEMPO."),
        text(eid(1),
             "Status note:\nPROC moves use STUN\nand INTERRUPT — skip turns."),
        text(eid(2),
             "DATA folds to PROC\n(2x). Bring a scheduler."),
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

    (BG_DIR / "cc_gym_proc.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_PROC_TRAINERS, "CC Gym Proc Trainers Defeated",
         "var_cc_proc_trainers_defeated"),
        (ID_VAR_BADGE_FLAG_PROC, "CC Badge Flag PROC", "var_cc_badge_flag_proc"),
    ]
    for i in range(4):
        new_vars.append((
            f"c1bd5e01-3000-4003-8003-0000000000{72+i:02d}",
            f"CC Gym Proc Trainer {i+1} Flag",
            f"var_cc_gym_proc_trainer_{i+1}_flag",
        ))
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    scene_dir = SCENES_DIR / "cinder_gym_proc"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_GYM_PROC,
        "_index": 4,
        "type": "TOPDOWN",
        "name": "GYM-PROC",
        "symbol": "scene_gym_proc",
        "x": 1500, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_GYM_PROC,
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
    leader_tile = (10, 4)   # in front of conductor's stage
    riddle_tile = (9, 16)   # near south door

    trigger_files = []
    for i in range(4):
        tx, ty = pads_tile[i]
        s = trainer_script(i, TRG_TRAINER[i])
        s += write_trainer_flags(i, f"{TRG_TRAINER[i]}-postfight")
        tf = trigger_file(
            TRG_TRAINER[i], f"Proc Trainer {i+1}", f"trigger_proc_t{i+1}",
            tx, ty, 2, 2, i, s,
        )
        trigger_files.append((f"trainer_{i+1}.gbsres", tf))

    tf_leader = trigger_file(
        TRG_LEADER, "Proc Leader TEMPO", "trigger_proc_leader",
        leader_tile[0], leader_tile[1], 2, 2, 4,
        leader_script(TRG_LEADER),
    )
    trigger_files.append(("leader.gbsres", tf_leader))

    tf_riddle = trigger_file(
        TRG_RIDDLE, "Proc Sign", "trigger_proc_sign",
        riddle_tile[0], riddle_tile[1], 2, 1, 5,
        riddle_script(TRG_RIDDLE),
    )
    trigger_files.append(("sign.gbsres", tf_riddle))

    for fname, tf in trigger_files:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(trigger_files)} triggers")

    print("\nGYM-PROC built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
