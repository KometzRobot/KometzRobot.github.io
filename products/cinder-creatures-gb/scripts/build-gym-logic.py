#!/usr/bin/env python3
"""Build GYM-LOGIC scene — first gym, ARCHIVIST EOS, 4 trainers + leader.

Generates:
  cinder-starter/assets/backgrounds/cc_gym_logic.png  (160x144 DMG)
  cinder-starter/assets/backgrounds/cc_gym_logic.png.gbsres
  cinder-starter/project/scenes/cinder_gym_logic/{scene.gbsres,triggers/*}
  Updates variables.gbsres (adds badge bitfield + battle-state vars)

Run from repo root:
  python3 products/cinder-creatures-gb/scripts/build-gym-logic.py

Idempotent — stable UUIDs, safe to re-run.

Design (from CINDER-CREATURES-RPG.md, Loop 9806 line):
  - GYM-LOGIC, leader ARCHIVIST EOS, badge LOGIC.
  - Floor layout: entry at south, 4 trainer pads, leader pedestal at north.
  - Trainers fight LOGIC-type creatures (RECURSE/REGEXEL/SEMAFOX/BOOLEM).
  - Each trainer fight: challenge intro -> stats loaded -> 3-round dialogue
    fight -> defeat dialogue -> bit set in VAR_CC_TRAINERS_DEFEATED.
  - Leader gate: only opens when all 4 trainer bits are set.
  - Leader fight: 3 LOGIC creatures sequenced -> badge unlock event.
  - Type-chart riddle on entry (calm/riddling personality per spec).
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
BG_DIR = ROOT / "assets/backgrounds"
SCENES_DIR = ROOT / "project/scenes"

# DMG palette (lightest -> darkest)
DMG = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
# putpalette indexes: 3=lightest, 2=light, 1=dark, 0=darkest
LIGHTEST, LIGHT, DARK, DARKEST = 3, 2, 1, 0

# Stable IDs
ID_BG_GYM_LOGIC = "c1bd5e01-1000-4001-8001-000000000010"
ID_SCENE_GYM_LOGIC = "c1bd5e01-2000-4002-8002-000000000010"

ID_VAR_BADGES = "c1bd5e01-3000-4003-8003-000000000030"
ID_VAR_TRAINERS_DEFEATED = "c1bd5e01-3000-4003-8003-000000000031"
ID_VAR_OPP_HP = "c1bd5e01-3000-4003-8003-000000000032"
ID_VAR_OPP_ATK = "c1bd5e01-3000-4003-8003-000000000033"
ID_VAR_OPP_DEF = "c1bd5e01-3000-4003-8003-000000000034"
ID_VAR_OPP_ID = "c1bd5e01-3000-4003-8003-000000000035"
# Per-badge flag (1 once awarded, 0 otherwise)
ID_VAR_BADGE_FLAG_LOGIC = "c1bd5e01-3000-4003-8003-000000000036"

# Trigger UUIDs
TRG_TRAINER = [f"c1bd5e01-4000-4004-8004-0000000000{20+i:02d}" for i in range(4)]
TRG_LEADER = "c1bd5e01-4000-4004-8004-000000000030"
TRG_RIDDLE = "c1bd5e01-4000-4004-8004-000000000031"

# Trainer roster — LOGIC-specialist gym
# (title, name, creature_id, creature_name, intro, boast, defeat_line, bit)
TRAINERS = [
    ("HACKER", "BIT", 26, "XORHARE",
     "Two booleans walk in.\nOne walks out. Math.",
     "RECURSE folds first.\nWatch the base case.",
     "Fine. Stack overflow.\nI'll regroup.", 1),
    ("HACKER", "PARSE", 30, "ELSEEL",
     "If you fall through,\nyou hit the default.",
     "I never miss the\nelse branch.",
     "...goto cleanup.\nI yield.", 2),
    ("PROF", "DR LAMBDA", 28, "BOOLEM",
     "Lambda calculus is\nstill calculus.",
     "Curry. Apply. Curry.\nWatch closely.",
     "Beta-reduced past me.\nWell played.", 4),
    ("HACKER", "GREP", 8, "REGEXEL",
     "I match patterns. You\nare a pattern.",
     ".*won.* — that's me.",
     "Anchored to defeat.\nFair.", 8),
]
# Need all 4 bits set: 1|2|4|8 = 15

# Leader: ARCHIVIST EOS, 3 LOGIC creatures
LEADER_TEAM = [
    (4, "RECURSE"),
    (8, "REGEXEL"),
    (28, "BOOLEM"),
]


def build_gym_bg():
    """160x144 DMG-palette gym interior.

    Layout (top-down, 16x16 tile grid -> 10 cols x 9 rows):
      - North wall (y=0..15)        — bookshelves (ARCHIVIST motif)
      - Floor                       — checker pattern, light/lightest
      - 4 trainer pads in 2 rows of 2, marked with darker square + glyph
      - Leader pedestal centered north (just south of north wall)
      - South entry door (bottom center)
      - East/West walls — bookshelf columns
    """
    W, H = 160, 144
    img = Image.new("P", (W, H), LIGHTEST)
    img.putpalette([c for rgb in DMG for c in rgb] * 64)
    d = ImageDraw.Draw(img)

    # Floor: 16x16 checker, alternate LIGHTEST / LIGHT
    for ty in range(H // 16):
        for tx in range(W // 16):
            if (tx + ty) % 2 == 0:
                d.rectangle((tx * 16, ty * 16, tx * 16 + 15, ty * 16 + 15),
                            fill=LIGHT)

    # North wall (y=0..15) — bookshelf row
    d.rectangle((0, 0, W - 1, 15), fill=DARK)
    for x in range(0, W, 8):
        d.line((x, 2, x, 13), fill=DARKEST)
    d.line((0, 4, W - 1, 4), fill=DARKEST)
    d.line((0, 9, W - 1, 9), fill=DARKEST)

    # East/West walls — single column of bookshelf
    d.rectangle((0, 16, 15, H - 17), fill=DARK)
    d.rectangle((W - 16, 16, W - 1, H - 17), fill=DARK)
    for y in range(16, H - 16, 4):
        d.line((2, y, 13, y), fill=DARKEST)
        d.line((W - 14, y, W - 3, y), fill=DARKEST)

    # South wall with door (y=H-16..H-1)
    d.rectangle((0, H - 16, W - 1, H - 1), fill=DARK)
    # Door: 2 tiles wide (tiles 4-5), opens to outside
    d.rectangle((64, H - 16, 95, H - 1), fill=LIGHTEST)
    d.line((64, H - 16, 95, H - 16), fill=DARKEST)
    d.rectangle((78, H - 12, 81, H - 4), fill=DARK)  # doorframe slit

    # Leader pedestal — centered, just south of north wall (y=20..31)
    px, py = 72, 20
    d.rectangle((px, py, px + 15, py + 11), fill=DARKEST)
    d.rectangle((px + 2, py + 2, px + 13, py + 9), fill=DARK)
    # LOGIC rune on pedestal: corner bracket
    d.line((px + 4, py + 4, px + 4, py + 7), fill=LIGHTEST)
    d.line((px + 4, py + 4, px + 7, py + 4), fill=LIGHTEST)

    # 4 trainer pads in 2 rows
    pads = [(32, 56), (112, 56), (32, 88), (112, 88)]
    for (cx, cy) in pads:
        d.rectangle((cx - 8, cy - 8, cx + 7, cy + 7), fill=DARK)
        d.rectangle((cx - 6, cy - 6, cx + 5, cy + 5), fill=LIGHT)
        # tiny glyph mark at center
        d.point((cx, cy), fill=DARKEST)
        d.point((cx - 1, cy), fill=DARKEST)
        d.point((cx + 1, cy), fill=DARKEST)
        d.point((cx, cy - 1), fill=DARKEST)
        d.point((cx, cy + 1), fill=DARKEST)

    # Center aisle marker — 2 lines guiding to pedestal
    for y in range(48, 128, 8):
        d.line((78, y, 81, y), fill=DARK)

    BG_DIR.mkdir(parents=True, exist_ok=True)
    out = BG_DIR / "cc_gym_logic.png"
    img.save(out)
    return out


def bg_sidecar():
    return {
        "_resourceType": "background",
        "id": ID_BG_GYM_LOGIC,
        "name": "CC Gym Logic",
        "symbol": "bg_cc_gym_logic",
        "tileColors": "",
        "filename": "cc_gym_logic.png",
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


def or_var(eid, var, val):
    return evt(eid, "EVENT_VARIABLE_MATH",
               {"vectorX": var, "operation": "set", "other": "value",
                "value": {"type": "number", "value": val},
                "clamp": False})


def trainer_script(idx, trg_id):
    """Build the trainer-fight script for one of the 4 gym trainers."""
    title, tname, cid, cname, intro, boast, defeat, bit = TRAINERS[idx]
    base = f"{trg_id}-trainer-{idx}"
    eid = lambda i: f"{base}-{i:03d}"
    script = []
    # Skip if already defeated (check bit via simple equality — bitfield = sum of cleared bits)
    # We use IF_VALUE: skip whole flow if (TRAINERS_DEFEATED & bit) — but GB Studio var ops
    # don't have AND in this lane easily, so we use a flag-list trick: check >= bit and
    # ((var - bit) >= 0). Simpler: a parallel per-trainer flag isn't worth the code; rely on
    # the player walking past once. For idempotence we add a guard: if var has bit set we skip.
    # For now keep it simple — accept replay (no harm; bit OR is idempotent).
    script.append(text(eid(0), f"{title} {tname}\nblocks the way."))
    script.append(evt(eid(1), "EVENT_CC_TRAINER_CHALLENGE", {
        "title": title, "trainer": tname,
        "intro": "wants to fight!", "boast": intro,
    }))
    script.append(text(eid(2), f"{tname} sends out\n{cname}!"))
    script.append(set_var(eid(3), ID_VAR_OPP_ID, cid))
    script.append(evt(eid(4), "EVENT_CC_SET_STATS", {
        "idVar": ID_VAR_OPP_ID, "hpVar": ID_VAR_OPP_HP,
        "atkVar": ID_VAR_OPP_ATK, "defVar": ID_VAR_OPP_DEF,
    }))
    # Abstract battle: 3 round flavor lines.
    script.append(text(eid(5), f"You attack.\n{cname} took damage."))
    script.append(text(eid(6), f"{cname} retaliates.\nYour creature holds."))
    script.append(text(eid(7), f"You finish it.\n{cname} fainted."))
    script.append(text(eid(8), f"{title} {tname}:\n{boast}"))
    script.append(text(eid(9), f"{title} {tname}:\n{defeat}"))
    # OR the bit into TRAINERS_DEFEATED. Approximated as: add bit if not already set.
    # GB Studio doesn't expose bitwise OR cleanly via base events, but our values are
    # disjoint bits so a simple ADD is safe AS LONG AS we guard against double-fire.
    # Guard: IF VAR < bit*2 floor for that bit... too fragile. Use a parallel bool.
    # Simpler approach: each trainer gets its own var (just allocate them). That's
    # cheaper than fighting the runtime. See variables list — we'll add 4 boolean vars.
    return script


def leader_script(trg_id):
    base = f"{trg_id}-leader"
    eid = lambda i: f"{base}-{i:03d}"
    s = []
    # Gate: require all 4 trainer flags set (TRAINERS_DEFEATED == 15)
    s.append(evt(eid(0), "EVENT_IF_VALUE", {
        "variable": ID_VAR_TRAINERS_DEFEATED, "operator": "<", "comparator": 15,
    }, {"true": [
        text(eid(1),
             "ARCHIVIST EOS:\nClear the others first.\nThe path is the proof."),
    ], "false": [
        text(eid(2),
             "ARCHIVIST EOS:\nYou cleared the floor.\nNow show me reasoning."),
        evt(eid(3), "EVENT_CC_TRAINER_CHALLENGE", {
            "title": "ARCHIVIST", "trainer": "EOS",
            "intro": "challenges you!",
            "boast": "Type-chart is honest.\nNo surprises here.",
        }),
        # 3-creature leader fight
        *_leader_battle_block(eid, 4, LEADER_TEAM[0]),
        *_leader_battle_block(eid, 20, LEADER_TEAM[1]),
        *_leader_battle_block(eid, 40, LEADER_TEAM[2]),
        text(eid(60),
             "ARCHIVIST EOS:\nClean derivation.\nThe LOGIC type yields."),
        # Set bit in VAR_CC_BADGES iff per-badge flag is 0 (idempotent guard).
        evt(eid(61), "EVENT_IF_VALUE", {
            "variable": ID_VAR_BADGE_FLAG_LOGIC,
            "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(eid(62), ID_VAR_BADGE_FLAG_LOGIC, 1),
            evt(eid(63), "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_BADGES,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": 1},  # LOGIC bit = 1
                "clamp": False,
            }),
        ], "false": []}),
        # Cosmetic award dialogue
        evt(eid(64), "EVENT_CC_BADGE_UNLOCK", {
            "badge": "LOGIC",
            "leaderName": "ARCHIVIST EOS",
        }),
        text(eid(65),
             "ARCHIVIST EOS:\nThe vessel reads true.\nGo find SOMA next."),
    ]}))
    return s


def _leader_battle_block(eid, base, team_entry):
    cid, cname = team_entry
    return [
        text(eid(base + 0), f"EOS sends out\n{cname}!"),
        set_var(eid(base + 1), ID_VAR_OPP_ID, cid),
        evt(eid(base + 2), "EVENT_CC_SET_STATS", {
            "idVar": ID_VAR_OPP_ID, "hpVar": ID_VAR_OPP_HP,
            "atkVar": ID_VAR_OPP_ATK, "defVar": ID_VAR_OPP_DEF,
        }),
        text(eid(base + 3), f"You attack.\n{cname} stumbles."),
        text(eid(base + 4), f"{cname} retaliates.\nYou hold."),
        text(eid(base + 5), f"You finish it.\n{cname} fainted."),
    ]


def riddle_script(trg_id):
    base = f"{trg_id}-riddle"
    eid = lambda i: f"{base}-{i:03d}"
    return [
        text(eid(0),
             "GYM SIGN:\nGYM-LOGIC.\nLeader: ARCHIVIST EOS."),
        text(eid(1),
             "Riddle:\nLOGIC beats PROC,\nbut bows to nothing."),
        text(eid(2),
             "Bring a CORE or DATA\ncreature to balance\nthe type chart."),
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


def write_trainer_flags(script, idx, eid_base):
    """After a trainer fight, set the per-trainer flag and add bit to bitfield."""
    bit = TRAINERS[idx][7]
    var_id = f"c1bd5e01-3000-4003-8003-0000000000{40+idx:02d}"
    # If trainer flag == 0, set flag to 1 and add bit to TRAINERS_DEFEATED.
    return [
        evt(f"{eid_base}-flagcheck", "EVENT_IF_VALUE", {
            "variable": var_id, "operator": "==", "comparator": 0,
        }, {"true": [
            set_var(f"{eid_base}-flagset", var_id, 1),
            evt(f"{eid_base}-bitadd", "EVENT_VARIABLE_MATH", {
                "vectorX": ID_VAR_TRAINERS_DEFEATED,
                "operation": "add",
                "other": "value",
                "value": {"type": "number", "value": bit},
                "clamp": False,
            }),
        ], "false": []}),
    ]


def main():
    bg_path = build_gym_bg()
    print(f"Wrote {bg_path}")

    # Sidecar
    (BG_DIR / "cc_gym_logic.png.gbsres").write_text(
        json.dumps(bg_sidecar(), indent=2))
    print("BG sidecar written")

    # Variables — add badge bitfield, trainers-defeated bitfield, opp stats, 4 per-trainer flags
    var_path = ROOT / "project/variables.gbsres"
    existing = json.loads(var_path.read_text())
    vars_list = existing.get("variables", [])
    new_vars = [
        (ID_VAR_BADGES, "CC Badges", "var_cc_badges"),
        (ID_VAR_TRAINERS_DEFEATED, "CC Gym Trainers Defeated",
         "var_cc_trainers_defeated"),
        (ID_VAR_OPP_HP, "CC Opp HP", "var_cc_opp_hp"),
        (ID_VAR_OPP_ATK, "CC Opp ATK", "var_cc_opp_atk"),
        (ID_VAR_OPP_DEF, "CC Opp DEF", "var_cc_opp_def"),
        (ID_VAR_OPP_ID, "CC Opp ID", "var_cc_opp_id"),
        (ID_VAR_BADGE_FLAG_LOGIC, "CC Badge Flag LOGIC", "var_cc_badge_flag_logic"),
    ]
    for i in range(4):
        new_vars.append((
            f"c1bd5e01-3000-4003-8003-0000000000{40+i:02d}",
            f"CC Gym Trainer {i+1} Flag",
            f"var_cc_gym_trainer_{i+1}_flag",
        ))
    have = {v.get("id") for v in vars_list}
    for vid, vname, vsym in new_vars:
        if vid not in have:
            vars_list.append({"id": vid, "name": vname, "symbol": vsym, "flags": {}})
    existing["variables"] = vars_list
    var_path.write_text(json.dumps(existing, indent=2))
    print(f"variables.gbsres: {len(vars_list)} total")

    # Scene
    scene_dir = SCENES_DIR / "cinder_gym_logic"
    triggers_dir = scene_dir / "triggers"
    triggers_dir.mkdir(parents=True, exist_ok=True)

    scene = {
        "_resourceType": "scene",
        "id": ID_SCENE_GYM_LOGIC,
        "_index": 2,
        "type": "TOPDOWN",
        "name": "GYM-LOGIC",
        "symbol": "scene_gym_logic",
        "x": 900, "y": 100,
        "width": 20, "height": 18,
        "backgroundId": ID_BG_GYM_LOGIC,
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

    # Triggers
    pads_tile = [(2, 3), (12, 3), (2, 5), (12, 5)]  # tiles for trainers
    leader_tile = (9, 1)
    riddle_tile = (9, 8)  # near south door, walk-on warning

    trigger_files = []
    for i in range(4):
        tx, ty = pads_tile[i]
        s = trainer_script(i, TRG_TRAINER[i])
        # Append flag setting after the fight
        s += write_trainer_flags(s, i, f"{TRG_TRAINER[i]}-postfight")
        tf = trigger_file(
            TRG_TRAINER[i], f"Gym Trainer {i+1}", f"trigger_gym_t{i+1}",
            tx, ty, 2, 2, i, s,
        )
        trigger_files.append((f"trainer_{i+1}.gbsres", tf))
    # Leader
    tf_leader = trigger_file(
        TRG_LEADER, "Gym Leader EOS", "trigger_gym_leader",
        leader_tile[0], leader_tile[1], 2, 2, 4,
        leader_script(TRG_LEADER),
    )
    trigger_files.append(("leader.gbsres", tf_leader))
    # Riddle (entry sign)
    tf_riddle = trigger_file(
        TRG_RIDDLE, "Gym Sign", "trigger_gym_sign",
        riddle_tile[0], riddle_tile[1], 2, 1, 5,
        riddle_script(TRG_RIDDLE),
    )
    trigger_files.append(("sign.gbsres", tf_riddle))

    for fname, tf in trigger_files:
        (triggers_dir / fname).write_text(json.dumps(tf, indent=2))
    print(f"Wrote {len(trigger_files)} triggers")

    print("\nGYM-LOGIC built. Open in GB Studio:")
    print(f"  {ROOT}/project.gbsproj")


if __name__ == "__main__":
    main()
