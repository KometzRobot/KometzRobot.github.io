#!/usr/bin/env python3
"""
Sanity tests for cc-encounter-pool.compose_pool().

Exercises every branch from CINDER-CREATURES-RPG.md §2b so that future edits
can't silently break the catch loop -> USB activity mapping. Run from anywhere:

    python3 products/cinder-creatures-gb/scripts/test-encounter-pool.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "cc_encounter_pool", HERE / "cc-encounter-pool.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["cc_encounter_pool"] = mod  # required for @dataclass to resolve names
spec.loader.exec_module(mod)

POOL_SIZE = mod.POOL_SIZE
COMMON = set(mod.COMMON_IDS)
UNCOMMON = set(mod.UNCOMMON_IDS)
RARE = set(mod.RARE_IDS)
LEGENDARY = set(mod.LEGENDARY_IDS)

NOW = datetime(2026, 5, 9, 4, 0, 0)


def base_activity(**overrides) -> dict:
    a = {
        "chats_24h": 0,
        "growth_events_24h": 0,
        "vault_saves_24h": 0,
        "journal_entries_24h": 0,
        "new_devices_24h": 0,
        "streak_days": 0,
        "longest_chat_chars": 0,
        "db_present": True,
    }
    a.update(overrides)
    return a


def assert_eq(label, got, want):
    if got != want:
        print(f"FAIL {label}: got={got} want={want}")
        sys.exit(1)
    print(f"  ok  {label}")


def assert_in(label, got, allowed):
    if got not in allowed:
        print(f"FAIL {label}: {got} not in expected band")
        sys.exit(1)
    print(f"  ok  {label}")


def test_idle_user():
    print("test: idle user (no activity)")
    pool = mod.compose_pool(base_activity(), NOW, seed=42)
    assert_eq("slot count", len(pool.slots), POOL_SIZE)
    assert_eq("party_decay", pool.party_decay, True)
    assert_eq("catch_rate=1.0", pool.catch_rate_modifier, 1.0)
    # All slots should be common when fully idle
    for i, s in enumerate(pool.slots):
        assert_in(f"slot{i} in COMMON", s, COMMON)


def test_chatty_user_unlocks_uncommon():
    print("test: chatty user (5 chats, 1 vault save) -> slot 12 + 13 uncommon")
    pool = mod.compose_pool(
        base_activity(chats_24h=5, vault_saves_24h=1, growth_events_24h=2),
        NOW, seed=42,
    )
    assert_in("slot12 uncommon", pool.slots[12], UNCOMMON)
    assert_in("slot13 uncommon", pool.slots[13], UNCOMMON)
    assert_eq("catch_rate boosted", pool.catch_rate_modifier, 1.10)
    assert_eq("party_decay off", pool.party_decay, False)


def test_streak_user_unlocks_rare():
    print("test: 7-day streak -> slot 14 rare")
    pool = mod.compose_pool(
        base_activity(streak_days=7, growth_events_24h=1),
        NOW, seed=42,
    )
    assert_in("slot14 rare", pool.slots[14], RARE)


def test_new_machine_unlocks_legendary():
    print("test: new machine -> slot 15 legendary")
    pool = mod.compose_pool(
        base_activity(new_devices_24h=1, growth_events_24h=1),
        NOW, seed=42,
    )
    assert_in("slot15 legendary", pool.slots[15], LEGENDARY)


def test_full_engagement():
    print("test: power-user (chats + vault + streak + new machine)")
    pool = mod.compose_pool(
        base_activity(
            chats_24h=20,
            growth_events_24h=8,
            vault_saves_24h=3,
            journal_entries_24h=2,
            streak_days=12,
            new_devices_24h=1,
        ),
        NOW, seed=42,
    )
    assert_in("slot12 uncommon", pool.slots[12], UNCOMMON)
    assert_in("slot13 uncommon", pool.slots[13], UNCOMMON)
    assert_in("slot14 rare", pool.slots[14], RARE)
    assert_in("slot15 legendary", pool.slots[15], LEGENDARY)
    assert_eq("catch_rate maxed at 1.30", pool.catch_rate_modifier, 1.30)
    assert_eq("decay off", pool.party_decay, False)


def test_deterministic_per_day():
    print("test: same day + same seed -> same pool")
    a = base_activity(chats_24h=4)
    p1 = mod.compose_pool(a, NOW, seed=20260509)
    p2 = mod.compose_pool(a, NOW, seed=20260509)
    assert_eq("slots match", p1.slots, p2.slots)


def main():
    test_idle_user()
    test_chatty_user_unlocks_uncommon()
    test_streak_user_unlocks_rare()
    test_new_machine_unlocks_legendary()
    test_full_engagement()
    test_deterministic_per_day()
    print("\nALL POOL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
