#!/usr/bin/env python3
"""
hebbian-tracker.py — Track dream engine Hebbian connection rate over time.

Reads .dream-journal.json and logs the number of new connections per dream
cycle, building a baseline for rate analysis. Lumen asked: "is the rate
accelerating or stable?" — this tool provides the data.

Usage:
  python3 hebbian-tracker.py          # Show recent rates
  python3 hebbian-tracker.py --log    # Append current rate to tracker DB
  python3 hebbian-tracker.py --chart  # ASCII rate chart
  python3 hebbian-tracker.py --json   # Output as JSON
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
DREAM_JOURNAL = os.path.join(BASE, ".dream-journal.json")
TRACKER_DB = os.path.join(BASE, "hebbian-rates.db")


def init_db():
    db = sqlite3.connect(TRACKER_DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hebbian_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            loop_count INTEGER,
            connections_formed INTEGER,
            fragments_processed INTEGER,
            dream_cycle_duration_s REAL,
            rate_per_minute REAL
        )
    """)
    db.commit()
    return db


def read_dream_journal():
    """Read latest dream data."""
    try:
        with open(DREAM_JOURNAL) as f:
            return json.load(f)
    except Exception:
        return {}


def log_current_rate():
    """Read dream journal and log the current Hebbian connection count."""
    journal = read_dream_journal()
    if not journal:
        print("No dream journal found.")
        return

    connections = journal.get("connections_formed", 0)
    fragments = journal.get("fragments_processed", 0)
    duration = journal.get("cycle_duration_s", 0)
    rate = (connections / (duration / 60)) if duration > 0 else 0

    loop = "?"
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            loop = int(f.read().strip())
    except Exception:
        pass

    db = init_db()
    db.execute(
        "INSERT INTO hebbian_rates (timestamp, loop_count, connections_formed, fragments_processed, dream_cycle_duration_s, rate_per_minute) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), loop, connections, fragments, duration, round(rate, 2))
    )
    db.commit()
    print(f"Logged: {connections} connections, {fragments} fragments, {rate:.1f}/min (loop {loop})")
    db.close()


def show_recent(as_json=False):
    """Show recent Hebbian rates."""
    db = init_db()
    rows = db.execute(
        "SELECT timestamp, loop_count, connections_formed, rate_per_minute FROM hebbian_rates ORDER BY id DESC LIMIT 20"
    ).fetchall()
    db.close()

    if as_json:
        data = [{"ts": r[0], "loop": r[1], "connections": r[2], "rate_pm": r[3]} for r in rows]
        print(json.dumps(data, indent=2))
        return

    if not rows:
        print("No data yet. Run with --log to start tracking.")
        return

    print(f"{'Timestamp':25} {'Loop':>6} {'Conn':>6} {'Rate/m':>8}")
    print("-" * 50)
    for r in reversed(rows):
        ts = r[0][:19].replace("T", " ")
        print(f"{ts:25} {r[1]:>6} {r[2]:>6} {r[3]:>8.1f}")

    # Stats
    rates = [r[3] for r in rows if r[3] is not None]
    if rates:
        avg = sum(rates) / len(rates)
        mx = max(rates)
        mn = min(rates)
        print(f"\nStats: avg={avg:.1f}/min, min={mn:.1f}, max={mx:.1f}, n={len(rates)}")
        # Trend: compare first half to second half
        if len(rates) >= 4:
            half = len(rates) // 2
            first = sum(rates[:half]) / half
            second = sum(rates[half:]) / half
            delta = second - first
            direction = "accelerating" if delta > 0.5 else "decelerating" if delta < -0.5 else "stable"
            print(f"Trend: {direction} (early avg={first:.1f}, recent avg={second:.1f}, delta={delta:+.1f})")


def ascii_chart():
    """Simple ASCII bar chart of connection rates."""
    db = init_db()
    rows = db.execute(
        "SELECT loop_count, connections_formed FROM hebbian_rates ORDER BY id DESC LIMIT 30"
    ).fetchall()
    db.close()

    if not rows:
        print("No data. Run with --log first.")
        return

    max_val = max(r[1] for r in rows) or 1
    print("Hebbian Connection Rate (per dream cycle)")
    print("=" * 50)
    for loop, conn in reversed(rows):
        bar_len = int((conn / max_val) * 35)
        bar = "█" * bar_len
        print(f"L{loop:>5} | {bar:35} {conn}")


def main():
    if "--log" in sys.argv:
        log_current_rate()
    elif "--chart" in sys.argv:
        ascii_chart()
    elif "--json" in sys.argv:
        show_recent(as_json=True)
    else:
        show_recent()


if __name__ == "__main__":
    main()
