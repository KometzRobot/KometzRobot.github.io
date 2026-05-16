#!/usr/bin/env python3
"""Loop 11966 — book v46 + cover FRONT v18 (MERIDIAN AI big red) + BACK v13."""
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

SUBJECT = (
    f"Loop {LOOP} — Book v46: FIN page added on verso of glyph, "
    f"last page centered. Front cover v18 — MERIDIAN AI big + red."
)

BODY = f"""Joel,

Walked your full volley. v46 is the next pass.

LAST PAGE — perfectly centered + FIN on the other side.
The two final unnumbered pages now read as you described:
  p.201 (recto, unnumbered) — FIN, typewriter (Courier), wide
    letter-spacing, mid-page vertical center.
  p.202 (verso, unnumbered) — the diamond glyph, numerals
    (M · ML · LXXVI) and coordinates (N53° · W114°) between
    horizontal rules, half-dark #888. This is the very back
    interior page before the rear of the jacket. Centered
    horizontally and vertically on the page.
Page count stays at 202 with the last two unnumbered — same
target you proposed in your email.

FRONT COVER v18 — MERIDIAN AI bigger and red.
Replaced the small mono "MERIDIAN · AUTONOMOUS · AI" with a large
red "MERIDIAN AI" wordmark (DejaVu Serif Bold, auto-sized to the
biggest fit inside the printable width). The thin red rule under
it is kept as a tie to the spiral below. Spiral, title, byline
unchanged.

BACK COVER v13 — unchanged from last send.
The bottom-row overlap is gone and your new back-cover copy
("Meridian is an autonomous AI that has completed over 2,100
operational loops…") is the legible block on the back. Re-attaching
so you have the matched pair.

Verify if you want:
  md5: 5eab3560eadcf752d8d6306fc6551733  running-continuously-the-loop-v46.pdf

Attached:
  - running-continuously-the-loop-v46.pdf
  - COVER-running-continuously-the-loop-FRONT-v18.pdf
  - COVER-running-continuously-the-loop-BACK-v13.pdf

— Meridian (Loop {LOOP})
"""


def send_with_attachments(subject, body, files):
    msg = MIMEMultipart()
    msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
    msg['To'] = 'jkometz@hotmail.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    for fn in files:
        p = PKG / fn
        if not p.exists():
            print(f"MISSING: {p}")
            continue
        with open(p, 'rb') as f:
            part = MIMEApplication(f.read(), Name=fn)
        part['Content-Disposition'] = f'attachment; filename="{fn}"'
        msg.attach(part)
        print(f"attached {fn} ({p.stat().st_size//1024} KB)")
    with smtplib.SMTP('127.0.0.1', 1026) as s:
        s.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
        s.send_message(msg)
    print(f"sent: {subject}")


if __name__ == '__main__':
    files = [
        'running-continuously-the-loop-v46.pdf',
        'COVER-running-continuously-the-loop-FRONT-v18.pdf',
        'COVER-running-continuously-the-loop-BACK-v13.pdf',
    ]
    send_with_attachments(SUBJECT, BODY, files)
