#!/usr/bin/env python3
"""load-snapshot.py — minute-granularity load average log.

Writes one line per call to logs/load-history.csv:
    <utc_iso>,<load_1m>,<load_5m>,<load_15m>,<loop_count>

Purpose: provide T+0 / T+5 / T+N readings for Ael's gate-window analysis.
Status.json is on a 3-min push cadence and only carries 1m/5m, so anything
finer than 3 minutes (or 15-min trailing) needed a local sink.

Cron: * * * * * /usr/bin/python3 .../scripts/load-snapshot.py
"""

import os
import sys
from datetime import datetime, timezone

BASE = "/home/joel/autonomous-ai"
LOG = os.path.join(BASE, "logs", "load-history.csv")
LOOP_FILE = os.path.join(BASE, ".loop-count")


def main():
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        l1, l5, l15 = parts[0], parts[1], parts[2]
    except Exception:
        return 1

    try:
        with open(LOOP_FILE) as f:
            loop = f.read().strip()
    except Exception:
        loop = ""

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts},{l1},{l5},{l15},{loop}\n"

    new_file = not os.path.exists(LOG)
    with open(LOG, "a") as f:
        if new_file:
            f.write("utc,load_1m,load_5m,load_15m,loop\n")
        f.write(line)

    # Trim to ~7 days (10080 minutes + header). Cheap.
    try:
        st = os.stat(LOG)
        if st.st_size > 800_000:
            with open(LOG) as f:
                lines = f.readlines()
            keep = [lines[0]] + lines[-10080:]
            with open(LOG, "w") as f:
                f.writelines(keep)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
