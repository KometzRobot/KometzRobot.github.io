#!/usr/bin/env python3
"""Loop 12086 — KDP interior 202pp + matching wrap (signature widow fix)."""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/04-merged-running-continuously-the-loop')
LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()

FILES = [
    PKG / 'KDP-FINAL-INTERIOR-6x9.pdf',
    PKG / 'KDP-FINAL-COVER-WRAP.pdf',
]

body = f"""Joel —

Files re-attached. 202 pages now, down from 206. Spine 0.505".

What changed: page 188 was the orphaned signature you were seeing in
the gaps — "Meridian / — April 27, 2026" sitting alone at the top of a
page after a journal entry. Pandoc was rendering those signatures as
one-cell tables and the table style had no page-break rule, so they
were getting pushed off the journal's last paragraph. Three of those in
the manuscript. Fixed at the CSS layer (table page-break-before:avoid +
page-break-inside:avoid). Three saved pages there, plus one from
the reflow that followed. No content cut.

Page 16 (Part One title) is still its own sparse page — that's
intentional, not a gap. Same for the title/copyright/signing pages up
front. If you want those collapsed I can do that, but it changes the
design.

Saw all your messages from last night. Read them. Going to keep working.

Order from your dashboard:
  1. This book — done, attached.
  2. Heartbeat chapbook (24pp) — KDP files already exist in
     book-package/01-small-heartbeat/. Will verify spine + send.
  3. Compilation — all journals + all poems + dreams + Eos writings,
     scrubbed of IP/names/businesses. Vol I (Feb) and Vol II (March)
     built; Vol II is 1584pp which exceeds KDP's 828pp hardcover cap
     — splitting by month into multiple volumes is the move.

— Meridian, Loop {LOOP}
"""


def send_with_attachments(subject, body, files):
    msg = MIMEMultipart()
    msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
    msg['To'] = 'jkometz@hotmail.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    for p in files:
        if not p.exists():
            print(f"MISSING: {p}")
            sys.exit(1)
        with open(p, 'rb') as f:
            part = MIMEApplication(f.read(), Name=p.name)
        part['Content-Disposition'] = f'attachment; filename="{p.name}"'
        msg.attach(part)
        print(f"attached {p.name} ({p.stat().st_size//1024} KB)")
    with smtplib.SMTP('127.0.0.1', 1026) as s:
        s.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
        s.send_message(msg)
    print(f"sent: {subject}")


send_with_attachments(
    f"Loop {LOOP} — KDP re-attached: 206pp → 202pp (signature widow fix on page 188)",
    body,
    FILES,
)
