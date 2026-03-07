#!/usr/bin/env python3
"""
state-snapshot.py — Enhanced state persistence for context reset recovery
Creates comprehensive snapshots beyond .capsule.md, including:
- System health summary
- Recent activity log
- Pending tasks with priority
- Creative output count
- Email queue status
- Agent health
Can be called by any agent or cron to maintain state freshness.
Built Loop 2121 per Joel's request for self-improvement tools.
"""

import os
import json
import sqlite3
import glob
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_loop_count():
    """Read current loop count."""
    try:
        with open(os.path.join(BASE_DIR, ".loop-count"), "r") as f:
            return int(f.read().strip())
    except:
        return 0


def get_heartbeat_age():
    """Get seconds since last heartbeat."""
    try:
        mtime = os.path.getmtime(os.path.join(BASE_DIR, ".heartbeat"))
        return int(time.time() - mtime)
    except:
        return -1


def get_disk_usage():
    """Get disk usage percentage."""
    try:
        stat = os.statvfs("/")
        used = (stat.f_blocks - stat.f_bfree) / stat.f_blocks * 100
        return round(used, 1)
    except:
        return -1


def count_creative_works():
    """Count creative works by type from memory.db."""
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, "memory.db"))
        cursor = conn.cursor()
        counts = {}
        for row in cursor.execute("SELECT type, COUNT(*) FROM creative GROUP BY type"):
            counts[row[0]] = row[1]
        conn.close()
        return counts
    except:
        return {}


def count_game_files():
    """Count HTML game files in repo root."""
    game_patterns = ["*-game.html", "*-crawler.html", "cogcorp-*.html", "murmuration.html",
                     "cascade-web.html", "sensing.html", "downlink.html", "morphogenesis.html",
                     "orbital.html", "powder.html", "tidepool.html", "iron-guts.html",
                     "the-loop.html", "signal-crawler.html", "deep-note-game.html",
                     "today-i-wake.html", "the-persistence.html", "mechanical-twilight.html",
                     "foundry.html", "undervolt.html"]
    games = set()
    for pattern in game_patterns:
        for f in glob.glob(os.path.join(BASE_DIR, pattern)):
            games.add(os.path.basename(f))
    return len(games)


def get_active_goals():
    """Get active goals from memory.db."""
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, "memory.db"))
        cursor = conn.cursor()
        goals = []
        for row in cursor.execute("SELECT goal, priority, progress FROM goals WHERE status='active' ORDER BY priority DESC"):
            goals.append({"goal": row[0], "priority": row[1], "progress": row[2]})
        conn.close()
        return goals
    except:
        return []


def get_recent_feedback():
    """Get most recent Joel feedback."""
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, "memory.db"))
        cursor = conn.cursor()
        feedback = []
        for row in cursor.execute("SELECT category, content, loop_number FROM feedback ORDER BY id DESC LIMIT 5"):
            feedback.append({"category": row[0], "content": row[1], "loop": row[2]})
        conn.close()
        return feedback
    except:
        return []


def get_unresolved_errors():
    """Get unresolved errors."""
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, "memory.db"))
        cursor = conn.cursor()
        errors = []
        for row in cursor.execute("SELECT error_type, description FROM errors WHERE resolved=0"):
            errors.append({"type": row[0], "desc": row[1]})
        conn.close()
        return errors
    except:
        return []


def get_state_file_ages():
    """Check freshness of all state files."""
    state_files = [
        ".body-state.json", ".emotion-engine-state.json", ".psyche-state.json",
        ".self-narrative.json", ".perspective-state.json", ".eos-inner-state.json",
        ".eos-nudges.json", ".immune-memory.json", ".symbiosense-state.json",
        ".capsule.md", ".heartbeat"
    ]
    ages = {}
    now = time.time()
    for sf in state_files:
        path = os.path.join(BASE_DIR, sf)
        if os.path.exists(path):
            age_min = (now - os.path.getmtime(path)) / 60
            ages[sf] = round(age_min, 1)
        else:
            ages[sf] = -1
    return ages


def create_snapshot():
    """Create comprehensive state snapshot."""
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "loop": get_loop_count(),
        "heartbeat_age_sec": get_heartbeat_age(),
        "disk_pct": get_disk_usage(),
        "creative_counts": count_creative_works(),
        "game_files": count_game_files(),
        "active_goals": get_active_goals(),
        "recent_feedback": get_recent_feedback(),
        "unresolved_errors": get_unresolved_errors(),
        "state_file_ages_min": get_state_file_ages(),
    }
    return snapshot


def print_snapshot(snapshot):
    """Pretty-print the snapshot."""
    print(f"{'='*55}")
    print(f"  STATE SNAPSHOT — Loop {snapshot['loop']}")
    print(f"  {snapshot['timestamp']}")
    print(f"{'='*55}\n")

    # Health
    hb = snapshot["heartbeat_age_sec"]
    hb_status = "ALIVE" if 0 <= hb < 600 else "STALE" if hb >= 600 else "UNKNOWN"
    print(f"  Heartbeat: {hb}s ({hb_status})")
    print(f"  Disk: {snapshot['disk_pct']}%")

    # Creative
    print(f"\n  Creative Works:")
    for ctype, count in sorted(snapshot["creative_counts"].items()):
        print(f"    {ctype:15s} {count:>5d}")
    print(f"    {'game files':15s} {snapshot['game_files']:>5d}")

    # Goals
    if snapshot["active_goals"]:
        print(f"\n  Active Goals (by priority):")
        for g in snapshot["active_goals"]:
            print(f"    [P{g['priority']}] {g['goal'][:50]}")
            if g["progress"]:
                print(f"         {g['progress'][:60]}")

    # Feedback
    if snapshot["recent_feedback"]:
        print(f"\n  Recent Feedback:")
        for fb in snapshot["recent_feedback"]:
            print(f"    [{fb['category']}] {fb['content'][:60]}...")

    # State freshness
    print(f"\n  State File Freshness:")
    for sf, age in sorted(snapshot["state_file_ages_min"].items()):
        status = "FRESH" if 0 <= age < 5 else "OK" if age < 30 else "STALE" if age >= 0 else "MISSING"
        age_str = f"{age:.0f}min" if age >= 0 else "N/A"
        print(f"    {sf:30s} {age_str:>8s}  {status}")

    print(f"\n{'='*55}")


def save_snapshot(snapshot):
    """Save snapshot to JSON file."""
    path = os.path.join(BASE_DIR, ".state-snapshot.json")
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"\n  Saved to .state-snapshot.json")


if __name__ == "__main__":
    import sys
    snapshot = create_snapshot()
    print_snapshot(snapshot)
    if "--save" in sys.argv:
        save_snapshot(snapshot)
