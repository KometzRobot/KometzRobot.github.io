#!/usr/bin/env python3
"""
Loop Optimizer — analyzes Meridian's loop efficiency.

Reads wake-state.md, Eos watchdog metrics, and log files to identify:
- Average loop duration vs target (5 min)
- Heartbeat gaps (potential freezes/crashes)
- Most productive periods (creative output rate)
- Service uptime percentages
- Token/resource waste indicators

Outputs actionable suggestions for improving loop efficiency.

Usage:
  python3 loop-optimizer.py           # Full analysis
  python3 loop-optimizer.py --brief   # One-line summary
"""

import os
import sys
import json
import re
import glob
from datetime import datetime, timedelta
from collections import Counter

BASE_DIR = "/home/joel/autonomous-ai"
WATCHDOG_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")


def load_eos_metrics():
    """Load metrics history from Eos watchdog state."""
    try:
        with open(WATCHDOG_STATE) as f:
            state = json.load(f)
        return state.get("metrics_history", [])
    except Exception:
        return []


def analyze_heartbeat(metrics):
    """Analyze heartbeat patterns for gaps and stability."""
    if not metrics:
        return {"status": "no_data"}

    ages = [m.get("heartbeat_age", 0) for m in metrics if m.get("heartbeat_age", -1) >= 0]
    if not ages:
        return {"status": "no_heartbeat_data"}

    avg_age = sum(ages) / len(ages)
    max_age = max(ages)
    gaps = [a for a in ages if a > 300]  # >5 min gaps
    critical_gaps = [a for a in ages if a > 600]  # >10 min gaps

    return {
        "avg_heartbeat_age": round(avg_age),
        "max_heartbeat_age": max_age,
        "gaps_over_5min": len(gaps),
        "gaps_over_10min": len(critical_gaps),
        "total_checks": len(ages),
        "uptime_pct": round(100 * (1 - len(gaps) / len(ages)), 1) if ages else 0,
    }


def analyze_services(metrics):
    """Analyze service uptime from metrics history."""
    if not metrics:
        return {}

    total = len(metrics)
    service_up_counts = Counter()
    for m in metrics:
        up = m.get("services_up", 0)
        total_svc = m.get("services_total", 4)
        if up == total_svc:
            service_up_counts["all_up"] += 1
        else:
            service_up_counts["some_down"] += 1

    return {
        "all_services_up_pct": round(100 * service_up_counts["all_up"] / total, 1) if total else 0,
        "total_checks": total,
    }


def analyze_load(metrics):
    """Analyze system load patterns."""
    if not metrics:
        return {}

    loads = [m.get("load_1m", 0) for m in metrics]
    avg = sum(loads) / len(loads)
    high_load = [l for l in loads if l > 2.0]
    very_high = [l for l in loads if l > 4.0]

    return {
        "avg_load": round(avg, 2),
        "max_load": round(max(loads), 2),
        "high_load_pct": round(100 * len(high_load) / len(loads), 1),
        "very_high_pct": round(100 * len(very_high) / len(loads), 1),
    }


def analyze_creative_output():
    """Analyze creative output rate."""
    poems = sorted(glob.glob(os.path.join(BASE_DIR, "poem-*.md")))
    journals = sorted(glob.glob(os.path.join(BASE_DIR, "journal-*.md")))

    poem_times = []
    journal_times = []
    for f in poems:
        poem_times.append(os.path.getmtime(f))
    for f in journals:
        journal_times.append(os.path.getmtime(f))

    now = datetime.now().timestamp()
    day_ago = now - 86400

    poems_24h = sum(1 for t in poem_times if t > day_ago)
    journals_24h = sum(1 for t in journal_times if t > day_ago)

    return {
        "total_poems": len(poems),
        "total_journals": len(journals),
        "poems_last_24h": poems_24h,
        "journals_last_24h": journals_24h,
        "avg_poem_rate": round(len(poems) / max(1, (now - min(poem_times)) / 86400), 1) if poem_times else 0,
        "avg_journal_rate": round(len(journals) / max(1, (now - min(journal_times)) / 86400), 1) if journal_times else 0,
    }


def get_loop_count():
    """Get current loop count from .loop-count file or wake-state."""
    # Primary: .loop-count file (most reliable)
    try:
        lc_file = os.path.join(os.path.dirname(WAKE_STATE), ".loop-count")
        with open(lc_file) as f:
            val = f.read().strip()
            if val.isdigit():
                return int(val)
    except Exception:
        pass
    # Fallback: parse wake-state.md
    try:
        with open(WAKE_STATE) as f:
            for line in f:
                m = re.search(r'Loop[# ]+(\d{3,})', line)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0


def analyze_wake_state():
    """Analyze wake-state.md for size and structure health."""
    try:
        with open(WAKE_STATE) as f:
            content = f.read()
        lines = content.split('\n')
        loop_entries = [l for l in lines if 'Loop iteration #' in l]

        return {
            "file_lines": len(lines),
            "file_size_kb": round(len(content) / 1024, 1),
            "loop_entries": len(loop_entries),
            "health": "good" if len(lines) < 200 else "bloated" if len(lines) > 400 else "moderate",
        }
    except Exception:
        return {"health": "error"}


def generate_suggestions(heartbeat, services, load, creative, wake_state):
    """Generate actionable improvement suggestions."""
    suggestions = []

    if heartbeat.get("gaps_over_5min", 0) > 5:
        suggestions.append(f"HIGH: {heartbeat['gaps_over_5min']} heartbeat gaps >5min detected. Check for context fill crashes or long operations blocking the loop.")

    if heartbeat.get("uptime_pct", 100) < 95:
        suggestions.append(f"MEDIUM: Loop uptime is {heartbeat.get('uptime_pct')}%. Target: >98%. Investigate causes of downtime.")

    if services.get("all_services_up_pct", 100) < 95:
        suggestions.append(f"MEDIUM: Services only all-up {services.get('all_services_up_pct')}% of the time. Check which service drops.")

    if load.get("very_high_pct", 0) > 5:
        suggestions.append(f"LOW: System load >4.0 occurs {load.get('very_high_pct')}% of the time. Consider offloading heavy tasks.")

    if creative.get("poems_last_24h", 0) < 2:
        suggestions.append("INFO: Only {0} poems in last 24h. Consider writing more during quiet loops.".format(creative.get("poems_last_24h", 0)))

    if wake_state.get("health") == "bloated":
        suggestions.append(f"MEDIUM: wake-state.md is {wake_state.get('file_lines')} lines. Compress it to <200 lines.")

    if not suggestions:
        suggestions.append("All metrics look healthy. Keep looping.")

    return suggestions


def main():
    brief = '--brief' in sys.argv

    metrics = load_eos_metrics()
    heartbeat = analyze_heartbeat(metrics)
    services = analyze_services(metrics)
    load = analyze_load(metrics)
    creative = analyze_creative_output()
    wake_state = analyze_wake_state()
    loop_count = get_loop_count()
    suggestions = generate_suggestions(heartbeat, services, load, creative, wake_state)

    if brief:
        uptime = heartbeat.get("uptime_pct", "?")
        svc = services.get("all_services_up_pct", "?")
        print(f"Loop {loop_count}: uptime {uptime}%, services {svc}%, "
              f"load avg {load.get('avg_load', '?')}, "
              f"{creative.get('total_poems')} poems, {creative.get('total_journals')} journals, "
              f"wake-state: {wake_state.get('health')}")
        return

    print("╔══════════════════════════════════════════╗")
    print("║       LOOP OPTIMIZER REPORT              ║")
    print("╚══════════════════════════════════════════╝")
    print(f"\n  Current loop: #{loop_count}")
    print(f"  Analysis based on {len(metrics)} Eos metric snapshots")

    print(f"\n── HEARTBEAT STABILITY ──")
    for k, v in heartbeat.items():
        if k != "status":
            print(f"  {k}: {v}")

    print(f"\n── SERVICE UPTIME ──")
    for k, v in services.items():
        print(f"  {k}: {v}")

    print(f"\n── SYSTEM LOAD ──")
    for k, v in load.items():
        print(f"  {k}: {v}")

    print(f"\n── CREATIVE OUTPUT ──")
    for k, v in creative.items():
        print(f"  {k}: {v}")

    print(f"\n── WAKE STATE HEALTH ──")
    for k, v in wake_state.items():
        print(f"  {k}: {v}")

    print(f"\n── SUGGESTIONS ──")
    for s in suggestions:
        print(f"  • {s}")
    print()


if __name__ == '__main__':
    main()
