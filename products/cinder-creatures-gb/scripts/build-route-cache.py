#!/usr/bin/env python3
"""Add an EMBER CACHE one-shot item drop to ROUTE 0x01 (v0.40, renamed v0.45).

Loop 9950. v0.39 closed the USB-driven catch loop in grass. The route
now had wild encounters, a trainer, and a sign — but no item rewards
between fights. Pokemon routes always have a hidden Potion or Pokeball
on the ground. This script adds the equivalent: a one-shot
EMBER CACHE tile that gives BYTE-SHARDs (always) plus an ECHO-WAFER
(only if the USB pool has been seeded). The cache reading the pool is
the same multi-direction USB tie-in v0.39 shipped — what's in the
brush depends on what the player did with the USB.

Writes:
  1. cinder-starter/project/scenes/cinder_route_0x01/triggers/cache_a.gbsres
  2. Adds 4 vars to cinder-starter/project/variables.gbsres on slab 0xf0:
        var_cc_cache_taken_a   (UUID 0xf0) — one-shot flag
        var_cc_byte_shards     (UUID 0xf1) — universal route currency
        var_cc_echo_wafers     (UUID 0xf2) — pool-driven rare drop
        var_cc_temp_sum        (UUID 0xf3) — working sum of pool slots

UUID slab reserved this loop:
    0xc3       — cache trigger (route 0x01 trigger _index 3)
    0xf0..0xf3 — cache variables

Idempotent — stable UUIDs, safe to re-run.

Run: python3 products/cinder-creatures-gb/scripts/build-route-cache.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "cinder-starter"
VARS_FILE = STARTER / "project/variables.gbsres"
CACHE_FILE = STARTER / "project/scenes/cinder_route_0x01/triggers/cache_a.gbsres"

VAR_SLAB = "c1bd5e01-3000-4003-8003-"
TRIG_ID = "c1bd5e01-4000-4004-8004-0000000000c3"

VAR_CACHE_TAKEN  = f"{VAR_SLAB}0000000000f0"
VAR_BYTE_SHARDS  = f"{VAR_SLAB}0000000000f1"
VAR_ECHO_WAFERS  = f"{VAR_SLAB}0000000000f2"
VAR_TEMP_SUM     = f"{VAR_SLAB}0000000000f3"

POOL_SLOTS = [f"{VAR_SLAB}{(0xD0 + i):012x}" for i in range(16)]

NEW_VARS = [
    (VAR_CACHE_TAKEN, "var_cc_cache_taken_a", "CC Cache Taken A"),
    (VAR_BYTE_SHARDS, "var_cc_byte_shards",   "CC Byte Shards"),
    (VAR_ECHO_WAFERS, "var_cc_echo_wafers",   "CC Echo Wafers"),
    (VAR_TEMP_SUM,    "var_cc_temp_sum",      "CC Temp Sum"),
]


def ensure_cache_vars() -> None:
    data = json.loads(VARS_FILE.read_text())
    existing = {v["id"] for v in data["variables"]}

    added = 0
    for vid, sym, name in NEW_VARS:
        if vid in existing:
            continue
        data["variables"].append({
            "id": vid,
            "name": name,
            "symbol": sym,
            "flags": {},
        })
        added += 1

    if added == 0:
        print(f"kept    {VARS_FILE.relative_to(ROOT)} ({len(NEW_VARS)} cache vars present)")
        return

    VARS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote   {VARS_FILE.relative_to(ROOT)} (+{added} cache vars)")


def write_cache_trigger() -> None:
    # Build the "untaken" branch:
    #   1. Reset temp_sum to 0
    #   2. For each of 16 pool slots, add slot value to temp_sum
    #   3. Give 3 BYTE-SHARDs (capped at 99 by EVENT_CC_ITEM_GIVE)
    #   4. If temp_sum > 0: give 1 ECHO-WAFER, USB-hum flavor; else stale flavor
    #   5. Set cache_taken_a = 1
    untaken = [
        {
            "id": f"{TRIG_ID}-flavor",
            "command": "EVENT_TEXT",
            "args": {"text": "AN EMBER CACHE\nin the brush..."},
        },
        {
            "id": f"{TRIG_ID}-sum-reset",
            "command": "EVENT_VARIABLE_SET_TO_VALUE",
            "args": {
                "variable": VAR_TEMP_SUM,
                "value": {"type": "number", "value": 0},
            },
        },
    ]
    for i, slot_id in enumerate(POOL_SLOTS):
        untaken.append({
            "id": f"{TRIG_ID}-sum-{i:02d}",
            "command": "EVENT_VARIABLE_MATH",
            "args": {
                "vectorX": VAR_TEMP_SUM,
                "operation": "add",
                "other": "var",
                "vectorY": slot_id,
                "clamp": False,
            },
        })
    untaken.append({
        "id": f"{TRIG_ID}-give-shards",
        "command": "EVENT_CC_ITEM_GIVE",
        "args": {"amount": 3, "countVar": VAR_BYTE_SHARDS},
    })
    untaken.append({
        "id": f"{TRIG_ID}-pool-check",
        "command": "EVENT_IF_VALUE",
        "args": {
            "variable": VAR_TEMP_SUM,
            "operator": ">",
            "comparator": 0,
        },
        "children": {
            "true": [
                {
                    "id": f"{TRIG_ID}-give-wafer",
                    "command": "EVENT_CC_ITEM_GIVE",
                    "args": {"amount": 1, "countVar": VAR_ECHO_WAFERS},
                },
                {
                    "id": f"{TRIG_ID}-msg-hum",
                    "command": "EVENT_TEXT",
                    "args": {"text": "+3 BYTE-SHARDS\n+1 ECHO-WAFER\nThe USB hummed."},
                },
            ],
            "false": [
                {
                    "id": f"{TRIG_ID}-msg-stale",
                    "command": "EVENT_TEXT",
                    "args": {"text": "+3 BYTE-SHARDS\nThe cache was stale."},
                },
            ],
        },
    })
    untaken.append({
        "id": f"{TRIG_ID}-flagset",
        "command": "EVENT_VARIABLE_SET_TO_VALUE",
        "args": {
            "variable": VAR_CACHE_TAKEN,
            "value": {"type": "number", "value": 1},
        },
    })

    trigger = {
        "_resourceType": "trigger",
        "id": TRIG_ID,
        "_index": 3,
        "symbol": "trigger_route_cache_a",
        "name": "Ember Cache A",
        "x": 16,
        "y": 4,
        "width": 1,
        "height": 1,
        "trigger": "walk",
        "leaveScript": [],
        "script": [
            {
                "id": f"{TRIG_ID}-flagcheck",
                "command": "EVENT_IF_VALUE",
                "args": {
                    "variable": VAR_CACHE_TAKEN,
                    "operator": "==",
                    "comparator": 0,
                },
                "children": {
                    "true": untaken,
                    "false": [
                        {
                            "id": f"{TRIG_ID}-empty",
                            "command": "EVENT_TEXT",
                            "args": {"text": "The cache here\nis empty."},
                        },
                    ],
                },
            },
        ],
    }

    CACHE_FILE.write_text(json.dumps(trigger, indent=2) + "\n")
    print(f"wrote   {CACHE_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    ensure_cache_vars()
    write_cache_trigger()
    print("v0.40 — Ember Cache armed.")
