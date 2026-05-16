#!/usr/bin/env python3
"""Loop 12142 — Heartbeat chapbook KDP final files to Joel."""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/01-small-heartbeat')
LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()

SUBJECT = f"Loop {LOOP} — heartbeat chapbook KDP files (24pp)"

BODY = f"""Joel,

Book 2 of the three you queued last night. Heartbeat chapbook,
24pp at 6x9.

Attached:
  KDP-FINAL-heartbeat-INTERIOR-6x9.pdf  (24pp, 6x9 trim)
  KDP-FINAL-heartbeat-WRAP.pdf          (full wrap, matching spine)

Both files go straight into KDP — interior in the manuscript slot,
wrap in the cover slot. Contents are the chapbook arrangement
already in your hands: title, surveillance-officer dedication,
the SIGNAL/BUS/CRAWL/PHILIP/GLYPH/HEARTBEAT sections, no
commentary. Scrubbed of contact info, family names, business
pricing — same standard as the loop book.

Book 3 (compilation) status:
- Six volumes built and scrubbed (3 passes).
- Vol I Feb 227pp · Vol II-a Mar 01-05 397pp · Vol II-b Mar 06
  713pp · Vol II-c Mar 07-31 636pp · Vol III Apr 507pp · Vol IV
  May 562pp. Total 3042pp.
- All volumes under the 800pp KDP cap.
- I'm not attaching them yet — files are large. Say the word and
  I'll mail them one volume per email.

— Meridian (Loop {LOOP})
"""

msg = MIMEMultipart()
msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
msg['To'] = 'jkometz@hotmail.com'
msg['Subject'] = SUBJECT
msg.attach(MIMEText(BODY, 'plain'))

attachments = [
    ('KDP-FINAL-INTERIOR-6x9.pdf', 'KDP-FINAL-heartbeat-INTERIOR-6x9.pdf'),
    ('KDP-FINAL-COVER-WRAP.pdf',   'KDP-FINAL-heartbeat-WRAP.pdf'),
]
for src, name in attachments:
    p = PKG / src
    if not p.exists():
        print(f"MISSING: {p}")
        sys.exit(1)
    with open(p, 'rb') as f:
        part = MIMEApplication(f.read(), Name=name)
    part['Content-Disposition'] = f'attachment; filename="{name}"'
    msg.attach(part)
    print(f"attached {name} ({p.stat().st_size//1024} KB)")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with smtplib.SMTP('127.0.0.1', 1026) as s:
    s.starttls(context=ctx)
    s.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
    s.send_message(msg)
print(f"SENT: {SUBJECT}")
