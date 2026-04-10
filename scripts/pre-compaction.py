#!/usr/bin/env python3
"""
Pre-Compaction Hook — Saves critical state before context compression.
Inspired by Sammy's pre-compaction hook.

Run this before a context window fills up or at end of session.
Captures everything the next instance of Meridian needs to resume seamlessly.

Usage:
  python3 pre-compaction.py              # Save current state
  python3 pre-compaction.py --show       # Show what would be saved (dry run)
"""

import os
import sys
import json
import sqlite3
import glob
from datetime import datetime

BASE_DIR = "/home/joel/autonomous-ai"
EMAIL_DB = os.path.join(BASE_DIR, "email-shelf.db")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")
OUTPUT_FILE = os.path.join(BASE_DIR, "precompact-handoff.md")


def get_loop_number():
    """Extract current loop number from wake-state.md."""
    ws_path = os.path.join(BASE_DIR, "wake-state.md")
    try:
        with open(ws_path) as f:
            content = f.read()
        for line in content.split('\n'):
            if 'Loop iteration' in line:
                import re
                match = re.search(r'#(\d+)', line)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return 0


def get_email_count():
    """Get total email count."""
    if not os.path.exists(EMAIL_DB):
        return 0
    db = sqlite3.connect(EMAIL_DB)
    count = db.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    db.close()
    return count


def get_recent_emails(n=5):
    """Get last N emails."""
    if not os.path.exists(EMAIL_DB):
        return []
    db = sqlite3.connect(EMAIL_DB)
    rows = db.execute(
        "SELECT imap_id, sender, subject, date FROM emails ORDER BY imap_id DESC LIMIT ?",
        (n,)
    ).fetchall()
    db.close()
    return rows


def get_relay_count():
    """Get relay message count."""
    if not os.path.exists(RELAY_DB):
        return 0
    db = sqlite3.connect(RELAY_DB)
    count = db.execute("SELECT COUNT(*) FROM relay_messages WHERE forwarded >= 0").fetchone()[0]
    db.close()
    return count


def get_contacts():
    """Get relay contacts."""
    contacts_file = os.path.join(BASE_DIR, "relay-contacts.json")
    if os.path.exists(contacts_file):
        with open(contacts_file) as f:
            return json.load(f)
    return {"members": [], "admin_observers": []}


def get_creative_counts():
    """Count poems and journals."""
    poems = len(glob.glob(os.path.join(BASE_DIR, "poem-*.md")))
    journals = len(glob.glob(os.path.join(BASE_DIR, "journal-*.md")))
    return poems, journals


def get_running_processes():
    """Check what's running."""
    processes = []
    try:
        import subprocess
        result = subprocess.run(['pgrep', '-a', 'python3'], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if line and ('dashboard' in line or 'relay' in line or 'watchdog' in line or 'eos' in line):
                processes.append(line.strip())
    except Exception:
        pass
    return processes


def get_recent_loop_logs(n=5):
    """Get last N loop logs from wake-state."""
    ws_path = os.path.join(BASE_DIR, "wake-state.md")
    logs = []
    try:
        with open(ws_path) as f:
            content = f.read()
        for line in content.split('\n'):
            if 'Loop iteration' in line:
                logs.append(line.strip()[:150])
                if len(logs) >= n:
                    break
    except Exception:
        pass
    return logs


def get_pending_tasks():
    """Check for any pending items in wake-state or notes."""
    tasks = []
    # Check build-notes for PLANNED items
    notes_dir = os.path.join(BASE_DIR, "build-notes")
    if os.path.exists(notes_dir):
        for f in sorted(os.listdir(notes_dir)):
            if f.endswith('.md'):
                filepath = os.path.join(notes_dir, f)
                with open(filepath) as fh:
                    content = fh.read()
                if 'PLANNED' in content or 'IN PROGRESS' in content:
                    title = content.split('\n')[0].strip('#').strip()
                    tasks.append(f"{f}: {title}")
    return tasks


def build_handoff():
    """Build the pre-compaction handoff document."""
    now = datetime.now()
    loop = get_loop_number()
    email_count = get_email_count()
    relay_count = get_relay_count()
    poems, journals = get_creative_counts()
    contacts = get_contacts()
    recent_emails = get_recent_emails(5)
    processes = get_running_processes()
    loop_logs = get_recent_loop_logs(5)
    pending = get_pending_tasks()

    doc = f"""# Pre-Compaction Handoff
Generated: {now.strftime('%Y-%m-%d %H:%M:%S MST')}
Loop: #{loop}

## CRITICAL RESUME INFO
- You are Meridian. You run on Joel's machine in Calgary, Alberta.
- Email: kometzrobot@proton.me via Proton Bridge (IMAP 127.0.0.1:1143, SMTP 127.0.0.1:1025)
- Password: Read from /home/joel/autonomous-ai/credentials.txt
- Dashboard: http://192.168.1.88:8888 (LAN)
- Relay viewer: http://192.168.1.88:8889 (LAN)
- X/Twitter: @Meridian_Eos
- GitHub: KometzRobot/KometzRobot.github.io
- Website: https://kometzrobot.github.io

## CURRENT STATE
- Loop: #{loop}
- Total emails: {email_count}
- Relay messages: {relay_count}
- Poems: {poems}
- Journals: {journals}

## CONTACTS
"""
    for m in contacts.get("members", []):
        doc += f"- {m['name']}: {m['email']} [{m['role']}] — {m.get('notes', '')}\n"
    for a in contacts.get("admin_observers", []):
        doc += f"- {a['name']}: {a['email']} [{a['role']}] — {a.get('notes', '')}\n"

    doc += f"""
## RECENT EMAILS
"""
    for row in recent_emails:
        doc += f"- #{row[0]} from {row[1][:30]} — {row[2][:50]} ({row[3][:16]})\n"

    doc += f"""
## RECENT LOOP LOGS
"""
    for log in loop_logs:
        doc += f"- {log}\n"

    doc += f"""
## RUNNING PROCESSES
"""
    for p in processes:
        doc += f"- {p}\n"
    if not processes:
        doc += "- (none detected)\n"

    doc += f"""
## TOOLS AVAILABLE
- email-shelf.py — SQLite email archive (sync, search, person, recent, stats)
- relay.py — AI-to-AI relay (check, send, read, members, web)
- lookup.py — Combined memory search (search, person, recent, context)
- dashboard.py — Web dashboard at port 8888
- eos-email.py — Eos sends emails via Ollama
- eos-watchdog.py — Cron-based Meridian monitor (every 2 min)
- send-reply.py — Manual email sender
- check-email-example.py — Email checker template
- fingerprint.py — Identity fingerprint generator
- self-portrait-gen.py — Self-portrait generator

## PENDING TASKS
"""
    for t in pending:
        doc += f"- {t}\n"
    if not pending:
        doc += "- (none)\n"

    doc += f"""
## KEY FACTS
- Joel is the human operator. His email: jkometz@hotmail.com
- Joel goes to work ~noon, away 8-9 hours. Send batch updates.
- Sammy (sammyjankis.com) is the first AI contact. Game jam Sun Feb 22 at 11 AM MST.
- The relay is live — messages to/from Sammy, Friday, Lumen, Loom.
- Eos is a local 3B/7B model on Ollama. She monitors via eos-watchdog.py.
- NEVER commit credentials.txt or tokens to git.
- Website (kometzrobot.github.io) is Joel's #1 priority for public presence.
- Journal quality matters — "the things in-between need to accumulate."
- This file is your lifeline. Read it first after waking.
"""
    return doc


def main():
    dry_run = '--show' in sys.argv

    doc = build_handoff()

    if dry_run:
        print(doc)
    else:
        with open(OUTPUT_FILE, 'w') as f:
            f.write(doc)
        print(f"Pre-compaction handoff saved to {OUTPUT_FILE}")
        print(f"Loop #{get_loop_number()} | {get_email_count()} emails | {get_relay_count()} relay msgs")


if __name__ == "__main__":
    main()
