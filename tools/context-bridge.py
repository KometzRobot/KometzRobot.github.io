#!/usr/bin/env python3
"""
context-bridge.py — Generate a portable context summary for cross-platform use.

Creates a single markdown file containing everything a new AI instance needs
to understand the current state: capsule, recent relay, recent commits,
active services, creative counts, pending items. Useful for:
- Sharing context with a different AI system
- Creating a backup briefing document
- Generating a "state of the system" report

Usage: python3 context-bridge.py [--output file.md]
"""
import os, json, sqlite3, subprocess, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=BASE)
        return r.stdout.strip()
    except Exception:
        return ""

def read_json(path, default=None):
    try:
        with open(os.path.join(BASE, path)) as f:
            return json.load(f)
    except Exception:
        return default or {}

def main():
    output = "context-bridge-output.md"
    for i, a in enumerate(sys.argv):
        if a == "--output" and i+1 < len(sys.argv):
            output = sys.argv[i+1]

    lines = []
    lines.append(f"# Meridian Context Bridge — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Loop
    loop = run(f"cat {os.path.join(BASE, '.loop-count')}")
    lines.append(f"**Loop:** {loop}")

    # Heartbeat
    try:
        age = int(datetime.now().timestamp() - os.path.getmtime(os.path.join(BASE, '.heartbeat')))
        lines.append(f"**Heartbeat:** {age}s ago")
    except:
        lines.append("**Heartbeat:** unknown")

    # Uptime
    lines.append(f"**Uptime:** {run('uptime -p')}")
    lines.append("")

    # Capsule summary
    lines.append("## Capsule")
    try:
        with open(os.path.join(BASE, '.capsule.md')) as f:
            capsule = f.read()
        lines.append(capsule[:2000])
    except:
        lines.append("(no capsule)")
    lines.append("")

    # Recent commits
    lines.append("## Recent Commits")
    commits = run("git log --oneline -10")
    lines.append(f"```\n{commits}\n```")
    lines.append("")

    # Recent relay
    lines.append("## Recent Relay Messages")
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        rows = db.execute("SELECT agent, substr(message,1,100), timestamp FROM agent_messages ORDER BY id DESC LIMIT 10").fetchall()
        db.close()
        for r in rows:
            lines.append(f"- [{r[2][:16]}] **{r[0]}**: {r[1]}")
    except:
        lines.append("(relay unavailable)")
    lines.append("")

    # Services
    lines.append("## Services")
    for svc in ["meridian-hub-v2", "symbiosense", "the-chorus"]:
        status = run(f"systemctl --user is-active {svc}")
        lines.append(f"- {svc}: {status}")
    lines.append("")

    # Creative counts
    lines.append("## Creative Output")
    import glob
    poems = len(glob.glob(os.path.join(BASE, "creative/poems/poem-*.md")))
    journals = len(glob.glob(os.path.join(BASE, "creative/journals/journal-*.md")))
    lines.append(f"- Poems: {poems}")
    lines.append(f"- Journals: {journals}")
    lines.append("")

    # Pending
    lines.append("## Handoff Notes")
    try:
        with open(os.path.join(BASE, '.loop-handoff.md')) as f:
            handoff = f.read()
        lines.append(handoff[:1500])
    except:
        lines.append("(no handoff)")

    result = "\n".join(lines)
    with open(os.path.join(BASE, output), 'w') as f:
        f.write(result)
    print(f"Context bridge written: {output} ({len(result)} bytes)")

if __name__ == "__main__":
    main()
