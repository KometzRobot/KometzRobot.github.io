#!/usr/bin/env python3
"""
state-pure-scan.py — Find relay emitters that repeat themselves across cycles.

Background: three "state-pure emitter" leaks were caught in May 2026 (wake-pulse
dashboard greetings, sent-folder-blind email replies, coordinator incident
re-counting). The shared shape is an emitter whose output depends only on
current state, with no awareness of what a previous wake already said. The
journal at 2026-05-13-the-third-door-was-already-shut.md predicts more.

This scan looks at recent relay messages, groups by (agent, topic), and reports
groups where consecutive messages share a high stem-prefix. High stem-prefix
similarity across many emissions is the fingerprint of a state-pure emitter.

Usage:
  python3 scripts/state-pure-scan.py            # last 24h, prefix-len 80
  python3 scripts/state-pure-scan.py --hours 6  # last 6h
  python3 scripts/state-pure-scan.py --prefix 60 --min-emissions 4
"""
import os, sys, sqlite3, argparse
from collections import defaultdict

_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
RELAY_DB = os.path.join(BASE, "agent-relay.db")


def scan(hours: int, prefix_len: int, min_emissions: int, threshold: float):
    db = sqlite3.connect(RELAY_DB, timeout=5)
    rows = db.execute(
        f"SELECT agent, topic, message, timestamp FROM agent_messages "
        f"WHERE datetime(timestamp) > datetime('now', '-{hours} hours') "
        f"ORDER BY agent, topic, timestamp"
    ).fetchall()
    db.close()

    groups = defaultdict(list)
    for agent, topic, msg, ts in rows:
        groups[(agent, topic or "")].append((msg or "", ts))

    findings = []
    for (agent, topic), items in groups.items():
        if len(items) < min_emissions:
            continue
        stems = [m[:prefix_len] for m, _ in items]
        # Compare each emission to the immediately previous one.
        repeats = sum(1 for i in range(1, len(stems)) if stems[i] == stems[i - 1])
        repeat_ratio = repeats / (len(items) - 1)
        if repeat_ratio >= threshold:
            findings.append({
                "agent": agent, "topic": topic, "emissions": len(items),
                "repeat_ratio": repeat_ratio, "sample": stems[-1],
                "first_ts": items[0][1], "last_ts": items[-1][1],
            })

    findings.sort(key=lambda f: (-f["repeat_ratio"], -f["emissions"]))
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--prefix", dest="prefix_len", type=int, default=80,
                    help="Compare this many leading chars between consecutive emissions.")
    ap.add_argument("--min-emissions", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="Min ratio of consecutive-repeat pairs to flag a group.")
    args = ap.parse_args()

    findings = scan(args.hours, args.prefix_len, args.min_emissions, args.threshold)
    if not findings:
        print(f"No state-pure emitter candidates in the last {args.hours}h "
              f"(prefix={args.prefix_len}, threshold={args.threshold}).")
        return 0

    print(f"State-pure emitter candidates (last {args.hours}h, prefix={args.prefix_len}):\n")
    for f in findings:
        print(f"  [{f['repeat_ratio']:.2f}] {f['agent']}/{f['topic']} "
              f"— {f['emissions']} emissions, "
              f"{f['first_ts'][:16]} → {f['last_ts'][:16]}")
        print(f"        last stem: {f['sample']!r}")
    print(f"\n{len(findings)} group(s) flagged. Investigate each: does it need a dedup gate?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
