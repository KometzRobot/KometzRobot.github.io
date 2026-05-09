#!/usr/bin/env python3
"""Wire ROUTE 0x01 grass to USB-driven pool encounters (v0.39).

Loop 9949. v0.37 gave the route a grass patch firing EVENT_CC_ENCOUNTER
(uniform 1..56). v0.38 added a trainer + sign so the route had stakes.
v0.39 closes the actual catch-loop wiring: the grass now picks from a
16-slot encounter pool that the companion app seeds based on USB
activity (chats, journal, vault saves, streak). What the player meets
in the grass is shaped by what they did with the USB.

This script is idempotent — safe to re-run. It:

  1. Adds 17 variables to cinder-starter/project/variables.gbsres
        var_cc_pool_0 ... var_cc_pool_15  (UUIDs ...d0..df) — slot vars
        var_cc_pool_idx                   (UUID    ...e0)  — temp index

  2. Rewrites cinder-starter/project/scenes/cinder_route_0x01/
        triggers/grass_a.gbsres so the script becomes:

           EVENT_CC_POOL_ENCOUNTER  -> CC Creature Buf
           IF Buf == 0:
             EVENT_CC_ENCOUNTER 1..56 -> CC Creature Buf  (random fallback)
           ELSE:
             EVENT_CC_SHOW_NAME (Buf)                     (pool-spawn flavour)

     The IF branch is what makes this graceful — if the companion app
     hasn't seeded the pool yet (all slots == 0 on a fresh boot) the
     route falls back to uniform random so the game still works without
     a USB. Once the companion seeds the slots, every encounter is
     pool-driven.

  3. Emits two pool fixture samples for testing the wiring without
     a real Cinder USB:

        samples/pool-shim-empty.json   — zeroed pool, exercises fallback
        samples/pool-shim-active.json  — seeded pool, exercises pool path

UUID slabs reserved this loop:
    0xd0..0xdf — 16 pool slot variables
    0xe0       — pool index temp var

Run: python3 products/cinder-creatures-gb/scripts/build-pool-encounter-wiring.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "cinder-starter"
VARS_FILE = STARTER / "project/variables.gbsres"
GRASS_FILE = STARTER / "project/scenes/cinder_route_0x01/triggers/grass_a.gbsres"
SAMPLES = ROOT / "samples"

VAR_SLAB = "c1bd5e01-3000-4003-8003-"
SLOT_BASE = 0xD0      # 0xd0..0xdf for slots 0..15
INDEX_OFFSET = 0xE0   # 0xe0 for index temp
POOL_SIZE = 16

CREATURE_BUF_ID = f"{VAR_SLAB}000000000021"   # CC Creature Buf (existing)


def slot_uuid(i: int) -> str:
    return f"{VAR_SLAB}{(SLOT_BASE + i):012x}"


def index_uuid() -> str:
    return f"{VAR_SLAB}{INDEX_OFFSET:012x}"


# ---------------------------------------------------------------------------
# 1) variables.gbsres
# ---------------------------------------------------------------------------

def ensure_pool_vars() -> None:
    data = json.loads(VARS_FILE.read_text())
    existing = {v["id"] for v in data["variables"]}

    added = 0
    for i in range(POOL_SIZE):
        vid = slot_uuid(i)
        if vid in existing:
            continue
        data["variables"].append(
            {
                "id": vid,
                "name": f"CC Pool Slot {i:02d}",
                "symbol": f"var_cc_pool_{i:02d}",
                "flags": {},
            }
        )
        added += 1

    if index_uuid() not in existing:
        data["variables"].append(
            {
                "id": index_uuid(),
                "name": "CC Pool Index",
                "symbol": "var_cc_pool_idx",
                "flags": {},
            }
        )
        added += 1

    if added == 0:
        print(f"kept    {VARS_FILE.relative_to(ROOT)} ({POOL_SIZE + 1} pool vars already present)")
        return

    VARS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote   {VARS_FILE.relative_to(ROOT)} (+{added} pool vars)")


# ---------------------------------------------------------------------------
# 2) grass_a.gbsres trigger
# ---------------------------------------------------------------------------

GRASS_TRIGGER_ID = "c1bd5e01-4000-4004-8004-0000000000c0"


def write_grass_pool_script() -> None:
    pool_args = {
        "resultVar": CREATURE_BUF_ID,
        "indexVar": index_uuid(),
    }
    for i in range(POOL_SIZE):
        pool_args[f"slot{i}"] = slot_uuid(i)

    script = [
        # 1. Pool pick — copies one of 16 slot values into CC Creature Buf
        {
            "id": f"{GRASS_TRIGGER_ID}-pool-pick",
            "command": "EVENT_CC_POOL_ENCOUNTER",
            "args": pool_args,
        },
        # 2. If pool returned 0 (uninitialized), fall back to uniform random.
        #    Otherwise just show the name of what the pool spawned.
        {
            "id": f"{GRASS_TRIGGER_ID}-pool-guard",
            "command": "EVENT_IF_VALUE",
            "args": {
                "variable": CREATURE_BUF_ID,
                "operator": "==",
                "comparator": 0,
            },
            "children": {
                "true": [
                    {
                        "id": f"{GRASS_TRIGGER_ID}-fallback-roll",
                        "command": "EVENT_CC_ENCOUNTER",
                        "args": {
                            "variable": CREATURE_BUF_ID,
                            "min": 1,
                            "max": 56,
                            "prefix": "A wild ",
                            "suffix": " appeared!",
                        },
                    },
                ],
                "false": [
                    {
                        "id": f"{GRASS_TRIGGER_ID}-pool-show",
                        "command": "EVENT_CC_SHOW_NAME",
                        "args": {
                            "variable": CREATURE_BUF_ID,
                            "prefix": "A wild ",
                            "suffix": " appeared!",
                        },
                    },
                ],
            },
        },
    ]

    trigger = {
        "_resourceType": "trigger",
        "id": GRASS_TRIGGER_ID,
        "_index": 0,
        "symbol": "trigger_route_grass_a",
        "name": "Wild grass A",
        "x": 8,
        "y": 8,
        "width": 4,
        "height": 3,
        "trigger": "walk",
        "leaveScript": [],
        "script": script,
    }

    GRASS_FILE.write_text(json.dumps(trigger, indent=2) + "\n")
    print(f"wrote   {GRASS_FILE.relative_to(ROOT)} (pool encounter + fallback)")


# ---------------------------------------------------------------------------
# 3) pool fixture samples
# ---------------------------------------------------------------------------

def write_pool_shims() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)

    empty = {
        "schema_version": "1.0",
        "generated_at": "2026-05-09T00:00:00",
        "seed": 0,
        "slots": [0] * POOL_SIZE,
        "catch_rate_modifier": 1.0,
        "party_decay": False,
        "sources": {
            "db_present": False,
        },
        "notes": [
            "empty pool — companion app has not seeded yet",
            "ROM falls back to uniform 1..56 random encounter",
        ],
    }
    empty_path = SAMPLES / "pool-shim-empty.json"
    empty_path.write_text(json.dumps(empty, indent=2, sort_keys=True) + "\n")
    print(f"wrote   {empty_path.relative_to(ROOT)} (zeroed slots, exercises fallback)")

    active = {
        "schema_version": "1.0",
        "generated_at": "2026-05-09T16:00:00",
        "seed": 20260509,
        # 12 commons in slots 0..11 (RECURSE/BYTEFLY/CACHEY heavy → today's chats)
        # 2 uncommons (slots 12,13) → vault save + 4 chats
        # 1 rare (slot 14)        → 7-day streak
        # 1 legendary (slot 15)   → USB on new machine today
        "slots": [4, 6, 45, 4, 12, 6, 19, 45, 4, 6, 45, 12, 33, 38, 49, 53],
        "catch_rate_modifier": 1.10,
        "party_decay": False,
        "sources": {
            "chats_24h": 7,
            "growth_events_24h": 3,
            "vault_saves_24h": 1,
            "journal_entries_24h": 2,
            "new_devices_24h": 1,
            "streak_days": 8,
            "longest_chat_chars": 184,
            "db_present": True,
        },
        "notes": [
            "active pool — seeded from a busy USB day",
            "slot12=uncommon (vault save in 24h)",
            "slot13=uncommon (chats_24h=7)",
            "slot14=rare (streak=8d)",
            "slot15=LEGENDARY (USB on new machine)",
        ],
    }
    active_path = SAMPLES / "pool-shim-active.json"
    active_path.write_text(json.dumps(active, indent=2, sort_keys=True) + "\n")
    print(f"wrote   {active_path.relative_to(ROOT)} (seeded slots, exercises pool path)")


# ---------------------------------------------------------------------------

def main() -> int:
    ensure_pool_vars()
    write_grass_pool_script()
    write_pool_shims()
    print("\nv0.39 wiring complete. Reload project in GB Studio to pick up the new vars + grass script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
