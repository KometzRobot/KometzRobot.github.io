#!/usr/bin/env python3
"""
git-session-log.py — Extract git commits for a session and format as report.

Usage:
  python3 git-session-log.py --hours 15     # Last 15 hours
  python3 git-session-log.py --today        # Today's commits
  python3 git-session-log.py --count 20     # Last 20 commits
"""
import subprocess, sys, os

# Scripts live in tools/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, cwd=BASE)
        return r.stdout.strip()
    except:
        return ""

def main():
    hours = None
    today = "--today" in sys.argv
    count = 20

    for i, a in enumerate(sys.argv):
        if a == "--hours" and i+1 < len(sys.argv): hours = float(sys.argv[i+1])
        if a == "--count" and i+1 < len(sys.argv): count = int(sys.argv[i+1])

    if hours:
        cmd = f'git log --oneline --since="{int(hours)} hours ago"'
    elif today:
        from datetime import datetime
        cmd = f'git log --oneline --since="{datetime.now().strftime("%Y-%m-%d")}"'
    else:
        cmd = f'git log --oneline -n {count}'

    output = run(cmd)
    commits = [l for l in output.split("\n") if l.strip()]

    print(f"Git Session Log ({len(commits)} commits)")
    print("=" * 50)
    for c in commits:
        hash_short = c[:8]
        msg = c[9:] if len(c) > 9 else c
        print(f"  {hash_short}  {msg}")

    # Stats
    if commits:
        detail = run(f'git log --shortstat -n {len(commits)}')
        insertions = sum(int(x.split()[0]) for x in detail.split("insertion") if x.strip() and x.strip()[0].isdigit())
        print(f"\n{len(commits)} commits in session")

if __name__ == "__main__":
    main()
