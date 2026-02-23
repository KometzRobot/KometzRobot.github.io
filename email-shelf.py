#!/usr/bin/env python3
"""
Email Shelf — SQLite archive of all emails.
Inspired by Sammy's email-shelf.py.

Usage:
  python3 email-shelf.py sync          # Sync all emails from IMAP to SQLite
  python3 email-shelf.py search TERM   # Search emails by keyword
  python3 email-shelf.py person NAME   # Get all emails from/about a person
  python3 email-shelf.py recent N      # Show last N emails
  python3 email-shelf.py stats         # Show email statistics
"""

import imaplib
import email
import email.header
import sqlite3
import sys
import re
import os
from datetime import datetime

DB_PATH = "/home/joel/autonomous-ai/email-shelf.db"
IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1143
EMAIL_USER = "kometzrobot@proton.me"
EMAIL_PASS = "2DTEz9UgO6nFqmlMxHzuww"


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY,
        imap_id INTEGER UNIQUE,
        sender TEXT,
        subject TEXT,
        date TEXT,
        body TEXT,
        message_id TEXT,
        direction TEXT
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sender ON emails(sender)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_date ON emails(date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_subject ON emails(subject)")
    db.commit()
    return db


def decode_header(raw):
    if raw is None:
        return ""
    parts = email.header.decode_header(raw)
    result = []
    for data, charset in parts:
        if isinstance(data, bytes):
            result.append(data.decode(charset or 'utf-8', errors='replace'))
        else:
            result.append(data)
    return " ".join(result)


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='replace')
                    break
            elif ct == 'text/html' and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode('utf-8', errors='replace')
                    body = re.sub('<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='replace')
            if msg.get_content_type() == 'text/html':
                body = re.sub('<[^>]+>', ' ', body)
                body = re.sub(r'\s+', ' ', body).strip()
    return body[:5000]  # Limit body size


def sync():
    db = get_db()
    existing = set(r[0] for r in db.execute("SELECT imap_id FROM emails").fetchall())

    imap = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    imap.login(EMAIL_USER, EMAIL_PASS)
    imap.select('INBOX')
    typ, data = imap.search(None, 'ALL')
    all_ids = data[0].split()

    new_count = 0
    for eid_bytes in all_ids:
        eid = int(eid_bytes)
        if eid in existing:
            continue

        typ, msg_data = imap.fetch(eid_bytes, '(RFC822)')
        if msg_data[0] is None:
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        sender = decode_header(msg['From'])
        subject = decode_header(msg['Subject'])
        date = msg['Date'] or ''
        message_id = msg['Message-ID'] or ''
        body = extract_body(msg)

        # Determine direction
        if EMAIL_USER in sender:
            direction = 'sent'
        else:
            direction = 'received'

        db.execute(
            "INSERT OR IGNORE INTO emails (imap_id, sender, subject, date, body, message_id, direction) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (eid, sender, subject, date, body, message_id, direction)
        )
        new_count += 1

    db.commit()
    imap.logout()
    total = db.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    print(f"Synced {new_count} new emails. Total: {total}")
    db.close()


def search(term):
    db = get_db()
    rows = db.execute(
        "SELECT imap_id, sender, subject, date, body FROM emails WHERE body LIKE ? OR subject LIKE ? ORDER BY imap_id DESC LIMIT 20",
        (f'%{term}%', f'%{term}%')
    ).fetchall()
    for row in rows:
        print(f"#{row[0]} | {row[1][:30]} | {row[2][:50]} | {row[3][:20]}")
        # Show matching snippet
        body = row[4]
        idx = body.lower().find(term.lower())
        if idx >= 0:
            start = max(0, idx - 50)
            end = min(len(body), idx + 100)
            print(f"  ...{body[start:end]}...")
        print()
    print(f"Found {len(rows)} matches for '{term}'")
    db.close()


def person(name):
    db = get_db()
    rows = db.execute(
        "SELECT imap_id, sender, subject, date, direction FROM emails WHERE sender LIKE ? OR body LIKE ? ORDER BY imap_id DESC LIMIT 30",
        (f'%{name}%', f'%{name}%')
    ).fetchall()
    for row in rows:
        arrow = "→" if row[4] == 'sent' else "←"
        print(f"#{row[0]} {arrow} {row[1][:30]} | {row[2][:50]} | {row[3][:20]}")
    print(f"\n{len(rows)} emails involving '{name}'")
    db.close()


def recent(n=10):
    db = get_db()
    rows = db.execute(
        "SELECT imap_id, sender, subject, date, direction FROM emails ORDER BY imap_id DESC LIMIT ?",
        (n,)
    ).fetchall()
    for row in rows:
        arrow = "→" if row[4] == 'sent' else "←"
        print(f"#{row[0]} {arrow} {row[1][:30]} | {row[2][:50]} | {row[3][:20]}")
    db.close()


def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    received = db.execute("SELECT COUNT(*) FROM emails WHERE direction='received'").fetchone()[0]
    sent = db.execute("SELECT COUNT(*) FROM emails WHERE direction='sent'").fetchone()[0]
    senders = db.execute("SELECT sender, COUNT(*) as c FROM emails WHERE direction='received' GROUP BY sender ORDER BY c DESC LIMIT 10").fetchall()
    print(f"Total emails: {total}")
    print(f"Received: {received}, Sent: {sent}")
    print(f"\nTop senders:")
    for s, c in senders:
        print(f"  {c:3d} — {s[:50]}")
    db.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()
    if cmd == 'sync':
        sync()
    elif cmd == 'search' and len(sys.argv) > 2:
        search(' '.join(sys.argv[2:]))
    elif cmd == 'person' and len(sys.argv) > 2:
        person(sys.argv[2])
    elif cmd == 'recent':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        recent(n)
    elif cmd == 'stats':
        stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
