#!/usr/bin/env python3
"""
relay-export.py — Export agent relay messages to markdown for archival.

Usage:
  python3 relay-export.py                    # Last 50 messages
  python3 relay-export.py --agent Soma       # Filter by agent
  python3 relay-export.py --since 4800       # Since loop N
  python3 relay-export.py --hours 24         # Last N hours
  python3 relay-export.py --output relay.md  # Output file
"""
import os, sys, sqlite3, json
from datetime import datetime, timezone, timedelta

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
RELAY_DB = os.path.join(BASE, "agent-relay.db")

def main():
    agent = None
    since_loop = None
    hours = None
    output = None
    limit = 50

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--agent" and i+1 < len(args): agent = args[i+1]; i += 2
        elif args[i] == "--since" and i+1 < len(args): since_loop = int(args[i+1]); i += 2
        elif args[i] == "--hours" and i+1 < len(args): hours = float(args[i+1]); i += 2
        elif args[i] == "--output" and i+1 < len(args): output = args[i+1]; i += 2
        elif args[i] == "--limit" and i+1 < len(args): limit = int(args[i+1]); i += 2
        else: i += 1

    db = sqlite3.connect(RELAY_DB, timeout=3)
    sql = "SELECT agent, message, timestamp, COALESCE(topic,'') FROM agent_messages"
    conditions = []
    params = []

    if agent:
        conditions.append("agent = ?")
        params.append(agent)
    if hours:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conditions.append("timestamp > ?")
        params.append(cutoff)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    db.close()

    lines = [f"# Relay Export — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"Showing {len(rows)} messages" + (f" from {agent}" if agent else ""))
    lines.append("")

    current_agent = None
    for r in reversed(rows):
        ag, msg, ts, topic = r
        ts_short = ts[:19].replace("T", " ") if ts else ""
        topic_str = f" [{topic}]" if topic else ""
        if ag != current_agent:
            lines.append(f"\n### {ag}")
            current_agent = ag
        lines.append(f"- `{ts_short}`{topic_str} {msg[:200]}")

    result = "\n".join(lines)
    if output:
        with open(os.path.join(BASE, output), 'w') as f:
            f.write(result)
        print(f"Exported to {output} ({len(rows)} messages)")
    else:
        print(result)

if __name__ == "__main__":
    main()
