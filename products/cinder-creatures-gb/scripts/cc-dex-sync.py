#!/usr/bin/env python3
"""
Cinder Creatures — Dex sync (closes the catch -> USB loop).

Joel directive (Loop 9710 + 9713): catching/collecting creatures must be a
core function tied to the consistent Cinder USB loop. cc-encounter-pool.py
runs the *forward* half (USB activity -> wild encounters). This script runs
the *reverse* half:

    GB save -> decoded JSON -> per-creature lore -> growth events in cinder.db

What it does
------------
1. Calls cinder-save-decoder.decode() to read /CINDER/games/cinder-creatures.sav
2. Loads the lore table (data/lore.json)
3. Enriches the decoded JSON with:
     dex.entries[]   = [{id, name, lore, type}, ...] for each caught creature
     dex.completion  = caught / 56 (float 0..1)
     dex.milestones  = list of completion milestones reached (10/25/40/56)
4. Writes /CINDER/games/cinder-creatures.json (companion app reads this)
5. Diffs against last sync and writes one cinder_growth_events row per newly
   caught creature (event='cinder.creature.caught', meta=creature name).
   Activity fed back into encounter-pool tier the next day.

Result: catching loops back into the USB activity feed, which raises
encounter pool tier, which grants more creatures, which fills more lore,
which writes more growth events. Closed loop. Joel's "consistent USB
loop for people using cinder USB."

CLI
  python3 cc-dex-sync.py              # default paths, write JSON + events
  python3 cc-dex-sync.py --dry-run    # print result, write nothing
  python3 cc-dex-sync.py --usb /CINDER --cinder-db /path/to/cinder.db
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# --- paths ------------------------------------------------------------------

THIS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = THIS_DIR.parent / "plugins" / "cinder-creatures"
LORE_PATH = PLUGIN_DIR / "data" / "lore.json"
CREATURES_PATH = PLUGIN_DIR / "data" / "creatures.json"
DECODER_PATH = THIS_DIR / "cinder-save-decoder.py"

DEFAULT_USB_ROOT = "/CINDER"
DEFAULT_GAMES_DIR = "games"
DEX_JSON_NAME = "cinder-creatures.json"
LAST_SYNC_NAME = ".cinder-creatures.last-sync.json"

CANDIDATE_DBS = [
    "/CINDER/companion/cinder.db",
    str(Path(__file__).resolve().parents[3] / "products/cinder-anythingllm/server/storage/cinder.db"),
    str(Path.home() / ".cinder/cinder.db"),
]

MILESTONES = [10, 25, 40, 56]


# --- helpers ----------------------------------------------------------------

def _load_decoder():
    """Load cinder-save-decoder.py (its filename has a hyphen — no plain import)."""
    spec = importlib.util.spec_from_file_location("cc_decoder", DECODER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_json(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _resolve_cinder_db(arg: str | None) -> str | None:
    if arg:
        return arg if os.path.exists(arg) else None
    for p in CANDIDATE_DBS:
        if os.path.exists(p):
            return p
    return None


def _safe_connect_rw(path: str) -> sqlite3.Connection | None:
    try:
        if not os.path.exists(path):
            return None
        return sqlite3.connect(path, timeout=2)
    except sqlite3.Error:
        return None


# --- enrichment -------------------------------------------------------------

def enrich_payload(payload: dict, lore: dict, creatures: dict) -> dict:
    """Attach lore + completion to the decoded save payload."""
    species = {s["id"]: s for s in creatures.get("species", [])}
    lore_entries = lore.get("entries", {})
    total = len(species) or 56

    dex = payload.setdefault("dex", {"caught": [], "seen": []})
    caught_ids = sorted(set(int(x) for x in dex.get("caught", [])))

    entries = []
    for cid in caught_ids:
        sp = species.get(cid, {})
        entries.append({
            "id": cid,
            "name": sp.get("name", f"#{cid:02d}"),
            "type": sp.get("type", "?"),
            "lore": lore_entries.get(str(cid), ""),
        })
    dex["entries"] = entries
    dex["completion"] = round(len(caught_ids) / total, 4) if total else 0.0
    dex["caught_count"] = len(caught_ids)
    dex["total"] = total
    dex["milestones"] = [m for m in MILESTONES if len(caught_ids) >= m]

    payload["dex"] = dex
    return payload


def diff_new_catches(payload: dict, last_sync: dict | None) -> list[int]:
    """Return creature IDs newly caught since last sync."""
    now_caught = set(int(x) for x in payload.get("dex", {}).get("caught", []))
    prev_caught = set(int(x) for x in (last_sync or {}).get("caught", []))
    return sorted(now_caught - prev_caught)


def diff_new_milestones(payload: dict, last_sync: dict | None) -> list[int]:
    now_ms = set(payload.get("dex", {}).get("milestones", []))
    prev_ms = set((last_sync or {}).get("milestones", []))
    return sorted(now_ms - prev_ms)


# --- growth-event writer ----------------------------------------------------

def ensure_growth_table(conn: sqlite3.Connection) -> bool:
    """Create cinder_growth_events table if missing. Return True if available."""
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cinder_growth_events ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  event TEXT NOT NULL,"
            "  meta TEXT,"
            "  createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False


def write_growth_events(
    conn: sqlite3.Connection,
    new_catches: list[int],
    new_milestones: list[int],
    creatures: dict,
) -> int:
    """Insert one row per new catch + one per milestone. Return count written."""
    species = {s["id"]: s for s in creatures.get("species", [])}
    n = 0
    cur = conn.cursor()
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    for cid in new_catches:
        sp = species.get(cid, {})
        meta = json.dumps({
            "creature_id": cid,
            "name": sp.get("name", f"#{cid:02d}"),
            "type": sp.get("type", "?"),
        })
        cur.execute(
            "INSERT INTO cinder_growth_events (event, meta, createdAt) VALUES (?, ?, ?)",
            ("cinder.creature.caught", meta, now),
        )
        n += 1
    for ms in new_milestones:
        cur.execute(
            "INSERT INTO cinder_growth_events (event, meta, createdAt) VALUES (?, ?, ?)",
            ("cinder.dex.milestone", json.dumps({"milestone": ms}), now),
        )
        n += 1
    conn.commit()
    return n


# --- last-sync state --------------------------------------------------------

def read_last_sync(games_dir: Path) -> dict | None:
    p = games_dir / LAST_SYNC_NAME
    if not p.exists():
        return None
    try:
        return _load_json(p)
    except Exception:
        return None


def write_last_sync(games_dir: Path, payload: dict) -> None:
    p = games_dir / LAST_SYNC_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    snap = {
        "caught": payload.get("dex", {}).get("caught", []),
        "milestones": payload.get("dex", {}).get("milestones", []),
        "synced_at": datetime.now().isoformat(timespec="seconds"),
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(snap, indent=2))
    tmp.replace(p)


# --- writer -----------------------------------------------------------------

def write_dex_json(payload: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(out_path)


# --- CLI --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync GB save -> companion-app dex JSON + growth events.")
    ap.add_argument("--usb", default=os.environ.get("CINDER_USB_ROOT", DEFAULT_USB_ROOT))
    ap.add_argument("--cinder-db", default=None, help="Path to cinder.db (auto-detected)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None, help="Override dex JSON output path")
    args = ap.parse_args(argv)

    games_dir = Path(args.usb) / DEFAULT_GAMES_DIR

    decoder = _load_decoder()
    payload = decoder.decode(str(games_dir) if games_dir.exists() else None)

    lore = _load_json(LORE_PATH)
    creatures = _load_json(CREATURES_PATH)
    payload = enrich_payload(payload, lore, creatures)

    last_sync = read_last_sync(games_dir)
    new_catches = diff_new_catches(payload, last_sync)
    new_milestones = diff_new_milestones(payload, last_sync)

    out_path = Path(args.out) if args.out else (games_dir / DEX_JSON_NAME)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        print(f"\n[dry-run] would write {out_path}", file=sys.stderr)
        print(f"[dry-run] new catches: {new_catches}", file=sys.stderr)
        print(f"[dry-run] new milestones: {new_milestones}", file=sys.stderr)
        return 0

    try:
        write_dex_json(payload, out_path)
    except OSError as e:
        print(f"warn: could not write {out_path}: {e}", file=sys.stderr)

    events_written = 0
    cinder_db = _resolve_cinder_db(args.cinder_db)
    if cinder_db and (new_catches or new_milestones):
        conn = _safe_connect_rw(cinder_db)
        if conn is not None and ensure_growth_table(conn):
            events_written = write_growth_events(conn, new_catches, new_milestones, creatures)
            conn.close()

    # write last-sync snapshot
    target_dir = games_dir if games_dir.exists() else Path(args.usb)
    try:
        write_last_sync(target_dir, payload)
    except OSError:
        pass

    print(
        f"sync ok: caught={payload['dex']['caught_count']}/{payload['dex']['total']} "
        f"({payload['dex']['completion']*100:.1f}%) "
        f"new_catches={len(new_catches)} new_milestones={new_milestones} "
        f"events_written={events_written} "
        f"cinder_db={'yes' if cinder_db else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
