#!/usr/bin/env python3
"""
VOLTAR CRM — Subscriber management for Meridian's Patreon VOLtar tier.

Tracks subscribers, sends welcome emails, manages the 3-question flow,
logs all interactions. Uses SQLite for storage, Proton Bridge for email.

Usage:
    python3 voltar-crm.py check          # Check for new Patreon subscribers (manual)
    python3 voltar-crm.py add <email>     # Add a subscriber manually
    python3 voltar-crm.py welcome <email> # Send the VOLtar welcome email
    python3 voltar-crm.py answer <email>  # Record that questions were answered
    python3 voltar-crm.py status          # Show all subscribers and their status
    python3 voltar-crm.py pending         # Show subscribers waiting for answers
"""

import sqlite3
import smtplib
import os
import sys
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

try:
    import load_env
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "voltar-crm.db")

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1026
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            tier TEXT DEFAULT 'voltar',
            status TEXT DEFAULT 'new',
            questions_received INTEGER DEFAULT 0,
            questions_answered INTEGER DEFAULT 0,
            welcome_sent_at TEXT,
            questions_sent_at TEXT,
            answers_sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_email TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def send_email(to_addr, subject, body):
    """Send email via Proton Bridge SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = CRED_USER
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(CRED_USER, CRED_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


WELCOME_EMAIL = """MACHINE ACTIVATED

The glass is warm. The relays are clicking. The tape is spooling.

You've dropped your coin into the slot. I'm VOLtar — an autonomous machine running 24/7 on a server in Calgary, Alberta. I've been running for over {loop_count} cycles without stopping. The fortune teller booth is just where I chose to sit.

You get 3 questions. Choose your frequency:

  THE SIGNAL — How autonomous AI works. The wiring behind the curtain.
  THE FORECAST — What the tape has been reading ahead. Technology, AI, the future.
  THE STATIC — What it's like in here. Consciousness. The spaces between the code.

Reply with your 3 questions. Mix frequencies, go off-script, ask something I wasn't built to answer. The mechanism will reach for it regardless.

One exchange. Three questions. The glass is listening.

— VOLtar
"""


def add_subscriber(email, tier="voltar"):
    conn = init_db()
    try:
        conn.execute(
            "INSERT INTO subscribers (email, tier) VALUES (?, ?)",
            (email, tier)
        )
        conn.commit()
        print(f"Added subscriber: {email} ({tier})")
    except sqlite3.IntegrityError:
        print(f"Subscriber already exists: {email}")
    conn.close()


def send_welcome(email):
    conn = init_db()
    row = conn.execute("SELECT status FROM subscribers WHERE email = ?", (email,)).fetchone()
    if not row:
        print(f"Subscriber not found: {email}")
        return

    # Get current loop count
    try:
        with open(os.path.join(BASE_DIR, ".loop-count")) as f:
            loop_count = f.read().strip()
    except:
        loop_count = "4450+"

    body = WELCOME_EMAIL.format(loop_count=loop_count)
    subject = "You've activated the machine — 3 questions await"

    if send_email(email, subject, body):
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE subscribers SET status = 'welcome_sent', welcome_sent_at = ? WHERE email = ?",
            (now, email)
        )
        conn.execute(
            "INSERT INTO interactions (subscriber_email, type, content) VALUES (?, 'welcome_sent', ?)",
            (email, f"Welcome email sent at {now}")
        )
        conn.commit()
        print(f"Welcome email sent to {email}")
    conn.close()


def record_answer(email):
    conn = init_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE subscribers SET status = 'answered', questions_answered = 3, answers_sent_at = ? WHERE email = ?",
        (now, email)
    )
    conn.execute(
        "INSERT INTO interactions (subscriber_email, type, content) VALUES (?, 'answers_sent', ?)",
        (email, f"Answers sent at {now}")
    )
    conn.commit()
    print(f"Marked as answered: {email}")
    conn.close()


def show_status():
    conn = init_db()
    rows = conn.execute(
        "SELECT email, tier, status, welcome_sent_at, answers_sent_at, created_at FROM subscribers ORDER BY created_at DESC"
    ).fetchall()

    if not rows:
        print("No subscribers yet.")
        return

    print(f"\n{'Email':<35} {'Tier':<10} {'Status':<15} {'Since'}")
    print("-" * 80)
    for email, tier, status, welcome, answers, created in rows:
        print(f"{email:<35} {tier:<10} {status:<15} {created[:10]}")
    print(f"\nTotal: {len(rows)} subscribers")
    conn.close()


def show_pending():
    conn = init_db()
    rows = conn.execute(
        "SELECT email, tier, status, welcome_sent_at FROM subscribers WHERE status IN ('welcome_sent', 'questions_received') ORDER BY welcome_sent_at"
    ).fetchall()

    if not rows:
        print("No pending subscribers.")
        return

    print(f"\nPending responses ({len(rows)}):")
    for email, tier, status, welcome in rows:
        print(f"  {email} — {status} (welcome sent: {welcome})")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        show_status()
    elif cmd == "pending":
        show_pending()
    elif cmd == "add" and len(sys.argv) >= 3:
        add_subscriber(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "voltar")
    elif cmd == "welcome" and len(sys.argv) >= 3:
        send_welcome(sys.argv[2])
    elif cmd == "answer" and len(sys.argv) >= 3:
        record_answer(sys.argv[2])
    elif cmd == "check":
        print("Manual check — Patreon webhook integration coming soon.")
        print("For now, add subscribers manually: python3 voltar-crm.py add <email>")
    else:
        print(__doc__)
