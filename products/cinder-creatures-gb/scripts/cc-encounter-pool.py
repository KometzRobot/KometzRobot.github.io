#!/usr/bin/env python3
"""
Cinder Creatures — Encounter Pool driver.

Joel directive (Loop 9710): catching/collecting must be a core function tied to
the consistent loop of using the Cinder USB. This is the part that turns the
spec in CINDER-CREATURES-RPG.md §2b into an actual file the ROM can read.

What it does
------------
Reads recent USB activity from the Cinder companion app's SQLite databases and
writes `cinder-creatures.pool.json` next to the save file. The pool is a list
of 16 creature IDs (1..56) plus modifier flags. The GB ROM picks from this
pool at every wild encounter via `eventCCPoolEncounter`, so what the player
encounters is shaped by what they did on the USB that day.

Activity sources (all optional — the driver degrades gracefully)
  - workspace_chats           : chat messages → 5% spawn chance per message,
                                creature type weighted by message length bucket
  - cinder_growth_events      : journal entries / saves to vault → adds a
                                creature to today's pool, raises catch-rate
  - cinder_devices            : USB mounted on a new machine → roaming
                                legendary slot 15
  - daily streak (any activity 7 days running) → unlocks rare-tier slot 14

Pool layout (16 slots)
  slots  0..11 : common encounters (creature IDs 1..30, weighted by activity)
  slot   12    : uncommon (IDs 31..45) if any vault save in last 24h
  slot   13    : uncommon (IDs 31..45) if 3+ chats in last 24h
  slot   14    : rare (IDs 46..52)     if streak >= 7 days
  slot   15    : legendary (53..56)    if new machine seen in last 24h

Writes
  cinder-creatures.pool.json   — pool of 16 creature IDs + modifiers
                                 (read by the companion app's save-syncer)

CLI
  python3 cc-encounter-pool.py                    # default paths, writes pool
  python3 cc-encounter-pool.py --dry-run          # print pool, don't write
  python3 cc-encounter-pool.py --usb /CINDER      # custom USB root
  python3 cc-encounter-pool.py --cinder-db PATH   # custom cinder.db path
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# --- defaults ---------------------------------------------------------------

DEFAULT_USB_ROOT = "/CINDER"
DEFAULT_GAMES_DIR = "games"
POOL_NAME = "cinder-creatures.pool.json"

# search order for cinder.db when --cinder-db not given
CANDIDATE_DBS = [
    "/CINDER/companion/cinder.db",
    str(Path(__file__).resolve().parents[3] / "products/cinder-anythingllm/server/storage/cinder.db"),
    str(Path.home() / ".cinder/cinder.db"),
]

# Creature ID bands by tier (matches CINDER-CREATURES-RPG.md type chart spread).
# 56 creatures total; bands chosen so wild encounters skew common.
COMMON_IDS = list(range(1, 31))      # 30 common
UNCOMMON_IDS = list(range(31, 46))   # 15 uncommon
RARE_IDS = list(range(46, 53))       #  7 rare
LEGENDARY_IDS = list(range(53, 57))  #  4 legendary

POOL_SIZE = 16


# --- pool model -------------------------------------------------------------

@dataclass
class EncounterPool:
    schema_version: str = "1.0"
    generated_at: str = ""
    seed: int = 0
    slots: list[int] = field(default_factory=list)
    catch_rate_modifier: float = 1.0
    party_decay: bool = False
    sources: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --- activity readers -------------------------------------------------------

def _safe_connect(path: str) -> sqlite3.Connection | None:
    try:
        if not os.path.exists(path):
            return None
        # read-only — never mutate the companion's db
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None


def read_activity(cinder_db: str | None, now: datetime) -> dict:
    """Return activity counters for the last 24h and streak day count."""
    out = {
        "chats_24h": 0,
        "growth_events_24h": 0,
        "vault_saves_24h": 0,
        "journal_entries_24h": 0,
        "new_devices_24h": 0,
        "streak_days": 0,
        "longest_chat_chars": 0,
        "db_present": False,
    }
    if not cinder_db:
        return out
    conn = _safe_connect(cinder_db)
    if conn is None:
        return out
    out["db_present"] = True
    cutoff = (now - timedelta(hours=24)).isoformat(sep=" ", timespec="seconds")
    try:
        cur = conn.cursor()

        # chats in 24h + max length
        try:
            cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(LENGTH(prompt)), 0) "
                "FROM workspace_chats WHERE createdAt >= ?",
                (cutoff,),
            )
            row = cur.fetchone()
            if row:
                out["chats_24h"] = row[0] or 0
                out["longest_chat_chars"] = row[1] or 0
        except sqlite3.Error:
            pass

        # growth events split by event-name prefix (vault / journal)
        try:
            cur.execute(
                "SELECT event, COUNT(*) FROM cinder_growth_events "
                "WHERE createdAt >= ? GROUP BY event",
                (cutoff,),
            )
            for ev, n in cur.fetchall():
                out["growth_events_24h"] += n
                ev_lower = (ev or "").lower()
                if "vault" in ev_lower:
                    out["vault_saves_24h"] += n
                if "journal" in ev_lower or "diary" in ev_lower:
                    out["journal_entries_24h"] += n
        except sqlite3.Error:
            pass

        # new devices seen in 24h
        try:
            cur.execute(
                "SELECT COUNT(*) FROM cinder_devices WHERE createdAt >= ?",
                (cutoff,),
            )
            row = cur.fetchone()
            if row:
                out["new_devices_24h"] = row[0] or 0
        except sqlite3.Error:
            pass

        # streak: count distinct days with any growth event in last 14 days,
        # walk backwards from today, stop on first gap.
        try:
            since = (now - timedelta(days=14)).isoformat(sep=" ", timespec="seconds")
            cur.execute(
                "SELECT DISTINCT DATE(createdAt) FROM cinder_growth_events "
                "WHERE createdAt >= ? ORDER BY DATE(createdAt) DESC",
                (since,),
            )
            days = [r[0] for r in cur.fetchall()]
            streak = 0
            cursor_day = now.date()
            day_set = set(days)
            while cursor_day.isoformat() in day_set:
                streak += 1
                cursor_day = cursor_day - timedelta(days=1)
            out["streak_days"] = streak
        except sqlite3.Error:
            pass

    finally:
        conn.close()
    return out


# --- pool composer ----------------------------------------------------------

def compose_pool(activity: dict, now: datetime, seed: int | None = None) -> EncounterPool:
    """Compose a 16-slot pool from activity. Deterministic per (seed, day)."""
    pool = EncounterPool()
    pool.generated_at = now.isoformat(timespec="seconds")
    if seed is None:
        # daily seed: stable for a given day so re-running mid-day doesn't
        # rotate the entire pool every minute.
        day_seed = int(now.strftime("%Y%m%d"))
        seed = day_seed
    pool.seed = seed
    rng = random.Random(seed)

    # slots 0..11 — common, weighted toward "frequent activity = wider variety"
    chats = activity.get("chats_24h", 0)
    growth = activity.get("growth_events_24h", 0)
    diversity = min(12, 6 + chats // 5 + growth // 2)
    common_pick = rng.sample(COMMON_IDS, k=min(diversity, len(COMMON_IDS)))
    # fill 0..11 by tiling the diversity pick (so we get repeats of fewer
    # creatures when activity is low — feels like the pool concentrated)
    slots: list[int] = []
    while len(slots) < 12:
        slots.extend(common_pick)
    pool.slots = slots[:12]

    # slot 12 — uncommon if vault save in 24h
    if activity.get("vault_saves_24h", 0) > 0:
        pool.slots.append(rng.choice(UNCOMMON_IDS))
        pool.notes.append("slot12=uncommon (vault save in 24h)")
    else:
        pool.slots.append(rng.choice(COMMON_IDS))

    # slot 13 — uncommon if 3+ chats
    if activity.get("chats_24h", 0) >= 3:
        pool.slots.append(rng.choice(UNCOMMON_IDS))
        pool.notes.append(f"slot13=uncommon (chats_24h={activity['chats_24h']})")
    else:
        pool.slots.append(rng.choice(COMMON_IDS))

    # slot 14 — rare if 7-day streak
    if activity.get("streak_days", 0) >= 7:
        pool.slots.append(rng.choice(RARE_IDS))
        pool.notes.append(f"slot14=rare (streak={activity['streak_days']}d)")
    else:
        pool.slots.append(rng.choice(COMMON_IDS))

    # slot 15 — legendary if new machine seen
    if activity.get("new_devices_24h", 0) > 0:
        pool.slots.append(rng.choice(LEGENDARY_IDS))
        pool.notes.append("slot15=LEGENDARY (USB on new machine)")
    else:
        pool.slots.append(rng.choice(COMMON_IDS))

    # catch-rate modifier: vault saves give a small bonus that lasts 24h
    if activity.get("vault_saves_24h", 0) > 0:
        pool.catch_rate_modifier = round(1.0 + 0.10 * min(5, activity["vault_saves_24h"]), 2)

    # party decay: skipped a day in the streak
    if activity.get("streak_days", 0) == 0 and activity.get("growth_events_24h", 0) == 0:
        pool.party_decay = True
        pool.notes.append("party_decay=true (no activity today — 1HP drain)")

    pool.sources = activity
    return pool


# --- writer -----------------------------------------------------------------

def find_pool_path(usb_root: str) -> Path:
    """Pool file lives next to the save file in /CINDER/games/."""
    return Path(usb_root) / DEFAULT_GAMES_DIR / POOL_NAME


def write_pool(pool: EncounterPool, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(pool)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    tmp.replace(path)


# --- CLI --------------------------------------------------------------------

def resolve_cinder_db(arg: str | None) -> str | None:
    if arg:
        return arg if os.path.exists(arg) else None
    for p in CANDIDATE_DBS:
        if os.path.exists(p):
            return p
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compose Cinder Creatures encounter pool from USB activity.")
    ap.add_argument("--usb", default=os.environ.get("CINDER_USB_ROOT", DEFAULT_USB_ROOT),
                    help="USB root (default /CINDER or $CINDER_USB_ROOT)")
    ap.add_argument("--cinder-db", default=None, help="Path to cinder.db (auto-detected)")
    ap.add_argument("--dry-run", action="store_true", help="Print pool, don't write")
    ap.add_argument("--seed", type=int, default=None, help="Override RNG seed (default: today YYYYMMDD)")
    ap.add_argument("--out", default=None, help="Override output path")
    args = ap.parse_args(argv)

    now = datetime.now()
    cinder_db = resolve_cinder_db(args.cinder_db)
    activity = read_activity(cinder_db, now)
    pool = compose_pool(activity, now, seed=args.seed)

    out_path = Path(args.out) if args.out else find_pool_path(args.usb)
    if args.dry_run:
        print(json.dumps(asdict(pool), indent=2, sort_keys=True))
        print(f"\n[dry-run] would write to: {out_path}", file=sys.stderr)
        return 0

    try:
        write_pool(pool, out_path)
    except OSError as e:
        # USB not mounted yet — still print so the user can see what would ship.
        print(f"warn: could not write {out_path}: {e}", file=sys.stderr)
        print(json.dumps(asdict(pool), indent=2, sort_keys=True))
        return 2

    print(f"wrote {out_path}  slots={pool.slots}  catch_mod={pool.catch_rate_modifier}  decay={pool.party_decay}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
