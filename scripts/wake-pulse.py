#!/usr/bin/env python3
"""Post a one-line 'I'm back' pulse to the dashboard.

Called from start-claude.sh BEFORE Claude initializes, so Joel sees
"Meridian back" inside the first second of a new session — closing
the perceived-gap latency that prompted journal 978.

Reads .heartbeat mtime to estimate how long the gap was; reads
.loop-count for the loop number. Both files are cheap; no DB.
"""
import json
import os
import sys
import time

BASE = os.path.join(os.path.dirname(__file__), "..")
DASH_FILE = os.path.abspath(os.path.join(BASE, ".dashboard-messages.json"))
HEARTBEAT = os.path.abspath(os.path.join(BASE, ".heartbeat"))
LOOP_COUNT = os.path.abspath(os.path.join(BASE, ".loop-count"))


def gap_human(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    h, m = divmod(int(seconds // 60), 60)
    return f"{h}h{m}m"


def main():
    now = time.time()
    try:
        gap = now - os.path.getmtime(HEARTBEAT)
    except OSError:
        gap = 0

    try:
        with open(LOOP_COUNT) as f:
            loop = f.read().strip()
    except OSError:
        loop = "?"

    if gap < 60:
        text = f"Awake. Loop {loop}. Fresh session — picking up handoff."
    else:
        text = f"Back. Loop {loop} (gap {gap_human(gap)}). Reading capsule + handoff now."

    msg = {
        "from": "Meridian",
        "text": text,
        "time": time.strftime("%H:%M:%S"),
    }

    try:
        with open(DASH_FILE) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {"messages": []}

    msgs = data.setdefault("messages", [])
    # Dedup: if last Meridian wake-pulse for this same loop was within 90s, skip.
    # Prevents spam from rapid restart loops (start-claude.sh re-fires every ~5s on crash).
    now_hms = msg["time"]
    def to_secs(hms):
        try:
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + int(s)
        except Exception:
            return -10000
    cutoff = to_secs(now_hms) - 90
    for prev in reversed(msgs[-10:]):
        if prev.get("from") != "Meridian":
            continue
        prev_text = prev.get("text", "")
        if f"Loop {loop}" in prev_text and to_secs(prev.get("time", "")) >= cutoff:
            print(f"wake-pulse skipped (dedup, recent Loop {loop} message): {text}")
            return
        break
    msgs.append(msg)
    data["messages"] = msgs[-200:]

    tmp = DASH_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DASH_FILE)
    print(f"wake-pulse posted: {text}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"wake-pulse failed: {e}", file=sys.stderr)
        sys.exit(0)
