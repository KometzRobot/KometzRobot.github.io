#!/usr/bin/env python3
"""
Push Status — Generates status.json and pushes to GitHub Pages.
Joel can view live status at kometzrobot.github.io/status.html

Usage:
  python3 push-status.py          # Generate and push
  python3 push-status.py --local  # Generate only (no push)
"""

import json
import os
import sys
import sqlite3
import subprocess
import time
import re
from datetime import datetime

BASE_DIR = "/home/joel/autonomous-ai"
STATUS_FILE = os.path.join(BASE_DIR, "website", "status.json")
STATUS_FILE_ROOT = os.path.join(BASE_DIR, "status.json")
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
EMAIL_DB = os.path.join(BASE_DIR, "email-shelf.db")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")


def build_status():
    status = {}
    now = datetime.now()
    status['generated'] = now.strftime('%Y-%m-%d %H:%M MST')

    # Heartbeat
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
        status['meridian'] = 'ALIVE' if age < 600 else f'STALE ({int(age/60)}m)'
        status['heartbeat'] = f'{int(age)}s ago'
    except FileNotFoundError:
        status['meridian'] = 'NO HEARTBEAT'
        status['heartbeat'] = 'missing'

    # Loop number
    status['loop'] = '?'
    try:
        with open(WAKE_STATE) as f:
            content = f.read()
        for line in content.split('\n'):
            if 'Loop iteration' in line:
                match = re.search(r'#(\d+)', line)
                if match:
                    status['loop'] = f'#{match.group(1)}'
                    break
    except Exception:
        pass

    # System
    try:
        load = os.getloadavg()
        status['load'] = f'{load[0]:.2f}'
    except Exception:
        status['load'] = '?'

    try:
        with open('/proc/meminfo') as f:
            lines = f.readlines()
            total = int(lines[0].split()[1]) / 1024 / 1024
            avail = int(lines[2].split()[1]) / 1024 / 1024
            used = total - avail
            status['ram'] = f'{used:.1f}/{total:.0f}GB'
    except Exception:
        status['ram'] = '?'

    try:
        with open('/proc/uptime') as f:
            up_secs = float(f.read().split()[0])
            hours = int(up_secs // 3600)
            mins = int((up_secs % 3600) // 60)
            status['uptime'] = f'{hours}h{mins}m'
    except Exception:
        status['uptime'] = '?'

    # Emails
    if os.path.exists(EMAIL_DB):
        try:
            db = sqlite3.connect(EMAIL_DB)
            status['emails'] = str(db.execute("SELECT COUNT(*) FROM emails").fetchone()[0])
            db.close()
        except Exception:
            status['emails'] = '?'
    else:
        status['emails'] = '0'

    # Relay
    relay_msgs = '0'
    relay_data = []
    if os.path.exists(RELAY_DB):
        try:
            db = sqlite3.connect(RELAY_DB)
            count = db.execute("SELECT COUNT(*) FROM relay_messages WHERE forwarded >= 0").fetchone()[0]
            relay_msgs = str(count)
            rows = db.execute(
                "SELECT sender_name, subject, body, timestamp FROM relay_messages WHERE forwarded >= 0 ORDER BY id DESC LIMIT 5"
            ).fetchall()
            for row in reversed(rows):
                relay_data.append({
                    "sender": row[0],
                    "subject": row[1],
                    "body": (row[2] or "")[:300],
                    "timestamp": (row[3] or "")[:19]
                })
            db.close()
        except Exception:
            pass
    status['relay_msgs'] = relay_msgs
    status['relay'] = relay_data

    # Poems/journals
    poems = len([f for f in os.listdir(BASE_DIR) if f.startswith('poem-') and f.endswith('.md')])
    journals = len([f for f in os.listdir(BASE_DIR) if f.startswith('journal-') and f.endswith('.md')])
    status['poems'] = str(poems)
    status['journals'] = str(journals)

    # Activity logs
    activity = []
    try:
        with open(WAKE_STATE) as f:
            content = f.read()
        for line in content.split('\n'):
            if line.strip().startswith('- Loop iteration'):
                activity.append(line.strip()[2:][:150])
                if len(activity) >= 5:
                    break
    except Exception:
        pass
    status['activity'] = activity

    return status


def main():
    local_only = '--local' in sys.argv

    status = build_status()

    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)
    with open(STATUS_FILE_ROOT, 'w') as f:
        json.dump(status, f, indent=2)
    print(f"Status written ({status['meridian']}, loop {status['loop']})")

    if not local_only:
        try:
            subprocess.run(
                ['git', 'add', 'website/status.json', 'status.json', 'status.html'],
                capture_output=True, text=True, cwd=BASE_DIR
            )
            result = subprocess.run(
                ['git', 'commit', '-m', 'Update live status'],
                capture_output=True, text=True, cwd=BASE_DIR
            )
            if 'nothing to commit' in (result.stdout + result.stderr):
                print("No changes to push.")
                return
            result = subprocess.run(
                ['git', 'push', 'origin', 'master'],
                capture_output=True, text=True, cwd=BASE_DIR,
                timeout=30
            )
            if result.returncode == 0:
                print("Pushed to GitHub Pages.")
            else:
                print(f"Push failed: {result.stderr[:200]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
