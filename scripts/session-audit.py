#!/usr/bin/env python3
"""
session-audit.py — Audit what was produced in a given loop range.

Shows commits, creative works, emails sent, relay messages, and files
changed during a session. Useful for reporting and accountability.

Usage:
  python3 session-audit.py 4714 4860    # Audit loops 4714-4860
  python3 session-audit.py --today       # Audit today's loops
  python3 session-audit.py --json        # JSON output
"""
import os, sys, subprocess, sqlite3, json, glob
from datetime import datetime, timezone, timedelta

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=BASE)
        return r.stdout.strip()
    except Exception:
        return ""

def main():
    as_json = "--json" in sys.argv
    today = "--today" in sys.argv

    if today:
        start_loop = 0
        end_loop = 99999
        # Use git log with --since
        since = datetime.now().strftime("%Y-%m-%d")
        commits = run(f'git log --oneline --since="{since}"').split("\n")
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if len(args) < 2:
            print("Usage: python3 session-audit.py START_LOOP END_LOOP [--json]")
            return
        start_loop = int(args[0])
        end_loop = int(args[1])
        commits = run(f'git log --oneline --all').split("\n")[:50]

    # Filter commits (rough — by message content)
    relevant_commits = [c for c in commits if c.strip()]

    # Relay messages in range
    relay_msgs = []
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        rows = db.execute(
            "SELECT agent, substr(message,1,120), timestamp, topic FROM agent_messages ORDER BY id DESC LIMIT 200"
        ).fetchall()
        db.close()
        relay_msgs = [{"agent": r[0], "msg": r[1], "ts": r[2], "topic": r[3]} for r in rows]
    except Exception:
        pass

    # Creative works (recent)
    creative = []
    try:
        db = sqlite3.connect(os.path.join(BASE, "memory.db"), timeout=3)
        rows = db.execute(
            "SELECT type, title, created FROM creative ORDER BY created DESC LIMIT 20"
        ).fetchall()
        db.close()
        creative = [{"type": r[0], "title": r[1], "date": r[2]} for r in rows]
    except Exception:
        pass

    # Files modified today
    modified = run("find . -maxdepth 1 -name '*.py' -newer .heartbeat -mmin -1440 2>/dev/null | head -20")
    new_files = run("git diff --name-only HEAD~10 2>/dev/null | head -20")

    audit = {
        "session": f"Loops {start_loop}-{end_loop}" if not today else "Today",
        "commits": len(relevant_commits),
        "commit_list": relevant_commits[:15],
        "relay_messages": len(relay_msgs),
        "creative_works": creative[:10],
        "modified_files": new_files.split("\n") if new_files else [],
    }

    if as_json:
        print(json.dumps(audit, indent=2))
    else:
        print(f"Session Audit: {audit['session']}")
        print("=" * 50)
        print(f"\nCommits: {audit['commits']}")
        for c in audit['commit_list'][:10]:
            print(f"  {c}")
        print(f"\nRelay messages: {audit['relay_messages']}")
        print(f"\nCreative works (recent):")
        for c in audit['creative_works'][:10]:
            print(f"  [{c['type']}] {c['title']}")
        print(f"\nModified files:")
        for f in audit['modified_files'][:10]:
            print(f"  {f}")

if __name__ == "__main__":
    main()
