#!/usr/bin/env python3
"""cascade-window.py — T+0 window-open logger for Ael's S9.4.5 collab.

For each gate event Ael provides (gate_utc, orbit_floor), this script:
  1. Computes window_open = gate_utc + 40min (per Ael's clarification, email 4088)
  2. Pulls the 1-min and 5-min load from logs/load-history.csv at window_open
  3. Computes deltas: (1-min - floor), (5-min - floor)
  4. Flags phenotype 4 ("simultaneous floor crossing"):
     both deltas positive within the first 60s of window-open
  5. Appends a row to logs/cascade-windows.csv

Ael's spec verbatim (email 4086, 2026-05-11):
> The window opens at T+40 from gate. The bridge state (broken when 5-min <
> orbit_floor) should already be logged by the time the window opens. The T+0
> capture is: at the moment the window timestamp passes, pull the current
> 1-min / 5-min / orbit_floor and log them as the window-open state.

Usage:
    # Single gate
    python3 cascade-window.py --gate 2026-05-11T23:46:00Z --floor 2.46

    # Backfill multiple gates from a JSON file
    python3 cascade-window.py --backfill gates.json
    # gates.json: [{"gate": "2026-05-11T23:46:00Z", "floor": 2.46, "label": "G10"}, ...]

    # Stdin (one "iso_utc,floor[,label]" per line)
    echo "2026-05-11T23:46:00Z,2.46,G10" | python3 cascade-window.py --stdin
"""

import argparse
import csv
import json
import os
import sys
from bisect import bisect_left
from datetime import datetime, timedelta, timezone

BASE = "/home/joel/autonomous-ai"
LOAD_CSV = os.path.join(BASE, "logs", "load-history.csv")
OUT_CSV = os.path.join(BASE, "logs", "cascade-windows.csv")

WINDOW_OFFSET_S = 40 * 60   # T+40 MINUTES from gate (Ael clarification, email 4088)
PHENOTYPE_4_WINDOW_S = 60  # Ael's spec: both deltas > 0 within first 60s


def parse_iso(s):
    """Parse 2026-05-11T23:46:00Z (Z = UTC). Tolerant of microseconds + offsets."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_history():
    """Load full load-history.csv into [(utc_dt, l1, l5, l15, loop), ...] sorted by utc."""
    rows = []
    with open(LOAD_CSV) as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append((
                    parse_iso(r["utc"]),
                    float(r["load_1m"]),
                    float(r["load_5m"]),
                    float(r["load_15m"]),
                    r.get("loop", ""),
                ))
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda x: x[0])
    return rows


def nearest_reading(rows, target_dt, max_skew_s=90, fallback_skew_s=300):
    """Return (row, mode) — mode is 'exact' if within max_skew_s, 'interpolated'
    if within fallback_skew_s, else (None, None)."""
    if not rows:
        return None, None
    times = [r[0] for r in rows]
    idx = bisect_left(times, target_dt)
    candidates = []
    if idx < len(rows):
        candidates.append(rows[idx])
    if idx > 0:
        candidates.append(rows[idx - 1])
    candidates = [(abs((c[0] - target_dt).total_seconds()), c) for c in candidates]
    candidates.sort(key=lambda x: x[0])
    if not candidates:
        return None, None
    best_skew, best_row = candidates[0]
    if best_skew <= max_skew_s:
        return best_row, "exact"
    if best_skew <= fallback_skew_s:
        return best_row, "interpolated"
    return None, None


def first_n_seconds(rows, start_dt, n_seconds):
    """Return all rows with start_dt <= row_dt < start_dt + n_seconds."""
    end_dt = start_dt + timedelta(seconds=n_seconds)
    return [r for r in rows if start_dt <= r[0] < end_dt]


def classify_window(rows, gate_dt, orbit_floor, label=""):
    """Apply Ael's spec to a single gate event. Returns dict ready for CSV."""
    window_open = gate_dt + timedelta(seconds=WINDOW_OFFSET_S)
    t0, mode = nearest_reading(rows, window_open)

    out = {
        "gate_utc": gate_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label,
        "window_open_utc": window_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "orbit_floor": orbit_floor,
        "t0_utc": "",
        "t0_load_1m": "",
        "t0_load_5m": "",
        "delta_1m": "",
        "delta_5m": "",
        "phenotype_4": "",
        "skew_s": "",
        "first60_max_1m": "",
        "first60_max_5m": "",
        "notes": "",
    }

    if t0 is None:
        out["notes"] = "no load reading within 5min of window_open"
        return out
    if mode == "interpolated":
        out["notes"] = "interpolated (no reading within 90s, used nearest within 5min)"

    t0_utc, l1, l5, _, _ = t0
    d1 = round(l1 - orbit_floor, 3)
    d5 = round(l5 - orbit_floor, 3)
    skew = round((t0_utc - window_open).total_seconds(), 1)

    out["t0_utc"] = t0_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    out["t0_load_1m"] = l1
    out["t0_load_5m"] = l5
    out["delta_1m"] = d1
    out["delta_5m"] = d5
    out["skew_s"] = skew

    # Phenotype 4 fingerprint: both deltas positive in first 60s of window-open
    first60 = first_n_seconds(rows, window_open, PHENOTYPE_4_WINDOW_S)
    if first60:
        max1 = max(r[1] for r in first60)
        max5 = max(r[2] for r in first60)
        out["first60_max_1m"] = max1
        out["first60_max_5m"] = max5
        if (max1 - orbit_floor) > 0 and (max5 - orbit_floor) > 0:
            out["phenotype_4"] = "YES"
        else:
            out["phenotype_4"] = "no"
    else:
        out["phenotype_4"] = "?"
        out["notes"] = "no readings in first 60s window"

    return out


FIELDS = [
    "gate_utc", "label", "window_open_utc", "orbit_floor",
    "t0_utc", "t0_load_1m", "t0_load_5m",
    "delta_1m", "delta_5m", "phenotype_4",
    "first60_max_1m", "first60_max_5m", "skew_s", "notes",
]


def append_row(row):
    new_file = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def print_row(row):
    print(f"  {row['label'] or '(no label)'}  gate={row['gate_utc']}  floor={row['orbit_floor']}")
    if row["t0_utc"]:
        sign1 = "+" if row["delta_1m"] >= 0 else ""
        sign5 = "+" if row["delta_5m"] >= 0 else ""
        print(f"    T+0 ({row['t0_utc']}, skew {row['skew_s']}s):  "
              f"1m={row['t0_load_1m']} ({sign1}{row['delta_1m']}),  "
              f"5m={row['t0_load_5m']} ({sign5}{row['delta_5m']})")
        print(f"    First 60s max 1m={row['first60_max_1m']}  5m={row['first60_max_5m']}  "
              f"phenotype_4={row['phenotype_4']}")
    if row["notes"]:
        print(f"    NOTE: {row['notes']}")


def process_gates(gates):
    """gates: list of dicts {gate, floor, label}. Returns list of result rows."""
    rows = load_history()
    results = []
    for g in gates:
        try:
            gate_dt = parse_iso(g["gate"])
            floor = float(g["floor"])
            label = g.get("label", "")
        except (KeyError, ValueError) as e:
            print(f"  SKIP malformed gate: {g} ({e})", file=sys.stderr)
            continue
        result = classify_window(rows, gate_dt, floor, label)
        append_row(result)
        print_row(result)
        results.append(result)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--gate", help="Single gate UTC (e.g. 2026-05-11T23:46:00Z)")
    p.add_argument("--floor", type=float, help="orbit_floor for --gate")
    p.add_argument("--label", default="", help="optional label for --gate (e.g. G10)")
    p.add_argument("--backfill", help="JSON file: [{gate, floor, label}, ...]")
    p.add_argument("--stdin", action="store_true",
                   help="read 'iso_utc,floor[,label]' lines from stdin")
    p.add_argument("--selftest", action="store_true",
                   help="run a synthetic self-test against the live load-history.csv")
    p.add_argument("--since",
                   help="skip gates with window_open before this UTC (e.g. 2026-05-12T00:00:00Z)")
    args = p.parse_args()

    if args.selftest:
        return selftest()

    gates = []
    if args.backfill:
        with open(args.backfill) as f:
            gates = json.load(f)
    elif args.stdin:
        for line in sys.stdin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            gates.append({
                "gate": parts[0],
                "floor": float(parts[1]),
                "label": parts[2] if len(parts) > 2 else "",
            })
    elif args.gate and args.floor is not None:
        gates = [{"gate": args.gate, "floor": args.floor, "label": args.label}]
    else:
        p.print_help()
        return 2

    if args.since:
        cutoff = parse_iso(args.since)
        kept = []
        for g in gates:
            try:
                wo = parse_iso(g["gate"]) + timedelta(seconds=WINDOW_OFFSET_S)
            except (KeyError, ValueError):
                continue
            if wo >= cutoff:
                kept.append(g)
            else:
                print(f"  SKIP {g.get('label','')} window_open {wo.isoformat()} before --since {cutoff.isoformat()}",
                      file=sys.stderr)
        gates = kept

    print(f"=== cascade-window.py: processing {len(gates)} gate(s) ===")
    process_gates(gates)
    print(f"=== wrote {len(gates)} row(s) to {OUT_CSV} ===")
    return 0


def selftest():
    """Pick a recent timestamp from load-history.csv, fabricate a gate 40s
    earlier, and verify we recover a T+0 reading."""
    rows = load_history()
    if len(rows) < 5:
        print("self-test: need >=5 rows in load-history.csv", file=sys.stderr)
        return 1
    # Use a row well inside the data so first-60s lookup finds neighbors
    pivot = rows[len(rows) // 2]
    fake_gate = pivot[0] - timedelta(seconds=WINDOW_OFFSET_S)
    fake_floor = round(pivot[1] - 0.01, 2)  # 1m just above floor → likely phenotype_4
    print(f"self-test: synthesized gate={fake_gate.isoformat()} floor={fake_floor}")
    result = classify_window(rows, fake_gate, fake_floor, label="SELFTEST")
    print_row(result)
    assert result["t0_utc"], "self-test failed: no T+0 row resolved"
    print("self-test: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
