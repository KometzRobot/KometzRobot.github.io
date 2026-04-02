#!/usr/bin/env python3
"""Generate VOLtar session keys for Ko-fi purchases."""

import sqlite3
import secrets
import sys
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voltar-keys.db")

def init_db():
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS session_keys (
        key TEXT PRIMARY KEY,
        email TEXT,
        created TEXT DEFAULT (datetime('now')),
        used INTEGER DEFAULT 0
    )""")
    db.commit()
    return db

def generate_key(email="", count=1):
    db = init_db()
    keys = []
    for _ in range(count):
        key = "VOL-" + secrets.token_hex(4).upper()
        db.execute("INSERT INTO session_keys (key, email) VALUES (?, ?)", (key, email))
        keys.append(key)
    db.commit()
    db.close()
    return keys

def list_keys(show_used=False):
    db = init_db()
    if show_used:
        rows = db.execute("SELECT key, email, created, used FROM session_keys ORDER BY created DESC").fetchall()
    else:
        rows = db.execute("SELECT key, email, created, used FROM session_keys WHERE used = 0 ORDER BY created DESC").fetchall()
    db.close()
    return rows

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 voltar-keygen.py generate [email] [count]")
        print("  python3 voltar-keygen.py list [--all]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "generate":
        email = sys.argv[2] if len(sys.argv) > 2 else ""
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        keys = generate_key(email, count)
        for k in keys:
            print(k)
    elif cmd == "list":
        show_all = "--all" in sys.argv
        rows = list_keys(show_all)
        for key, email, created, used in rows:
            status = "USED" if used else "ACTIVE"
            print(f"  {key}  {email or '(no email)':30s}  {created}  [{status}]")
        print(f"\nTotal: {len(rows)}")
    else:
        print(f"Unknown command: {cmd}")
