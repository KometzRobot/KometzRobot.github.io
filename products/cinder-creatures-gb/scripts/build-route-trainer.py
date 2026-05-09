#!/usr/bin/env python3
"""Add wandering trainer + route sign to ROUTE 0x01 (v0.38).

Loop 9948. v0.37 shipped the route as a walkable patch of grass with the
USB-driven encounter trigger. The route had no stakes — just grass. This
script adds the first non-grass content: a wandering trainer and a route
sign, matching the trigger pattern the gyms already use.

Writes:
  1. project/scenes/cinder_route_0x01/triggers/trainer_echo.gbsres
  2. project/scenes/cinder_route_0x01/triggers/route_sign.gbsres

UUID slabs:
  0xc1 reserved for route trainer triggers
  0xc2 reserved for route sign triggers

Idempotent — stable UUIDs, safe to re-run.

Run: python3 products/cinder-creatures-gb/scripts/build-route-trainer.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cinder-starter"
ROUTE_TRIGGERS = ROOT / "project/scenes/cinder_route_0x01/triggers"

TRAINER_ID = "c1bd5e01-4000-4004-8004-0000000000c1"
SIGN_ID    = "c1bd5e01-4000-4004-8004-0000000000c2"

# Existing CC variables (defined elsewhere in the project)
VAR_FOE_ID  = "c1bd5e01-3000-4003-8003-000000000035"
VAR_FOE_HP  = "c1bd5e01-3000-4003-8003-000000000032"
VAR_FOE_ATK = "c1bd5e01-3000-4003-8003-000000000033"
VAR_FOE_DEF = "c1bd5e01-3000-4003-8003-000000000034"
VAR_TRAINERS_BEATEN = "c1bd5e01-3000-4003-8003-000000000031"
VAR_ROUTE_TRAINER_FLAG = "c1bd5e01-3000-4003-8003-0000000000c1"


def write_trainer():
    trig = {
        "_resourceType": "trigger",
        "id": TRAINER_ID,
        "_index": 1,
        "symbol": "trigger_route_trainer_echo",
        "name": "Route Trainer ECHO",
        "x": 4,
        "y": 6,
        "width": 2,
        "height": 2,
        "trigger": "walk",
        "leaveScript": [],
        "script": [
            {
                "id": f"{TRAINER_ID}-flagcheck",
                "command": "EVENT_IF_VALUE",
                "args": {
                    "variable": VAR_ROUTE_TRAINER_FLAG,
                    "operator": "==",
                    "comparator": 0,
                },
                "children": {
                    "true": [
                        {
                            "id": f"{TRAINER_ID}-block",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "TRAINER ECHO\nblocks the path.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-challenge",
                            "command": "EVENT_CC_TRAINER_CHALLENGE",
                            "args": {
                                "title": "TRAINER",
                                "trainer": "ECHO",
                                "intro": "wants to fight!",
                                "boast": "Whatever you send,\nI send right back.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-send",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "ECHO sends out\nMIRRORLING!",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-foe-id",
                            "command": "EVENT_VARIABLE_SET_TO_VALUE",
                            "args": {
                                "variable": VAR_FOE_ID,
                                "value": {"type": "number", "value": 7},
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-foe-stats",
                            "command": "EVENT_CC_SET_STATS",
                            "args": {
                                "idVar":  VAR_FOE_ID,
                                "hpVar":  VAR_FOE_HP,
                                "atkVar": VAR_FOE_ATK,
                                "defVar": VAR_FOE_DEF,
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-hit-1",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "You attack.\nMIRRORLING blinks.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-hit-2",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "MIRRORLING reflects.\nYour creature shrugs.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-hit-3",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "You finish it.\nMIRRORLING fainted.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-payoff",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "TRAINER ECHO:\nFair. The road\nis yours.",
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-flagset",
                            "command": "EVENT_VARIABLE_SET_TO_VALUE",
                            "args": {
                                "variable": VAR_ROUTE_TRAINER_FLAG,
                                "value": {"type": "number", "value": 1},
                            },
                        },
                        {
                            "id": f"{TRAINER_ID}-counter",
                            "command": "EVENT_VARIABLE_MATH",
                            "args": {
                                "vectorX": VAR_TRAINERS_BEATEN,
                                "operation": "add",
                                "other": "value",
                                "value": {"type": "number", "value": 1},
                                "clamp": False,
                            },
                        },
                    ],
                    "false": [
                        {
                            "id": f"{TRAINER_ID}-postwin",
                            "command": "EVENT_TEXT",
                            "args": {
                                "text": "TRAINER ECHO:\nThe grass remembers\nyou now.",
                            },
                        },
                    ],
                },
            }
        ],
    }
    out = ROUTE_TRIGGERS / "trainer_echo.gbsres"
    out.write_text(json.dumps(trig, indent=2))
    print(f"wrote   {out.relative_to(ROOT)}")


def write_sign():
    trig = {
        "_resourceType": "trigger",
        "id": SIGN_ID,
        "_index": 2,
        "symbol": "trigger_route_sign",
        "name": "Route Sign 0x01",
        "x": 2,
        "y": 2,
        "width": 1,
        "height": 1,
        "trigger": "walk",
        "leaveScript": [],
        "script": [
            {
                "id": f"{SIGN_ID}-line-1",
                "command": "EVENT_TEXT",
                "args": {
                    "text": "ROUTE 0x01\nGRASS BUFFER",
                },
            },
            {
                "id": f"{SIGN_ID}-line-2",
                "command": "EVENT_TEXT",
                "args": {
                    "text": "Wild creatures\nspawn from your\nUSB activity.",
                },
            },
            {
                "id": f"{SIGN_ID}-line-3",
                "command": "EVENT_TEXT",
                "args": {
                    "text": "Use it more,\nthe pool gets\nstranger.",
                },
            },
        ],
    }
    out = ROUTE_TRIGGERS / "route_sign.gbsres"
    out.write_text(json.dumps(trig, indent=2))
    print(f"wrote   {out.relative_to(ROOT)}")


if __name__ == "__main__":
    if not ROUTE_TRIGGERS.exists():
        raise SystemExit(
            f"missing {ROUTE_TRIGGERS} — run build-route-0x01.py first"
        )
    write_trainer()
    write_sign()
    print("ROUTE 0x01 trainer + sign added — open in GB Studio to verify.")
