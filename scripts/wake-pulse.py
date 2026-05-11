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

    data.setdefault("messages", []).append(msg)
    data["messages"] = data["messages"][-200:]

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
