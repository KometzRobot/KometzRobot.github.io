#!/usr/bin/env python3
"""Loop 11962 — book v44 + latest covers (FRONT v17, BACK v12) to Joel."""
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

SUBJECT = f"Loop {LOOP} — Book v44: last page redrawn as diamond + fainter, .heartbeat dropped. Covers FRONT v17 + BACK v12 attached."

BODY = f"""Joel,

Walked your latest volley. v44 is what you asked for on the last page.

LAST PAGE — diamond shape, fainter, .heartbeat removed.
Took the crown elements (the arrows, the circles, the diamonds and
the plus/sun nodes) and reshaped them into a single diamond overall.
Arrows top and bottom, ◯ inside each tip, three rows of ◇─⊕/⊙─◇
stepping inward to the center. Below the diamond, between two thin
horizontal rules, the numerals (M · ML · LXXVI) and the coordinates
(N53° · W114°). Rendered in #888 (medium gray), so it reads about
half as dark as the body type — fainter, restful, doesn't compete
with the glossary that closes the book.

UNIX REFERENCE GONE. The .heartbeat line you flagged is cut.
You're right — most people won't know what a Unix dotfile is, and
the diamond + numerals + coordinates carry the closing weight on
their own without needing the technical reference.

201 vs 202 — staying at 201, two pages unnumbered.
I think 201 already gives you what you described: the very back
interior page (the diamond, p.201, unnumbered) before the inside-
rear-cover/jacket, with the blank verso (p.200, unnumbered) sitting
quietly before it. So the last two interior pages are already
unnumbered. 202 would only add another blank, which would feel like
a hesitation before the close rather than a frame. If you want the
extra blank as a hard pause I can add it — just say the word.

COVERS — newest pair attached:
  - COVER-running-continuously-the-loop-FRONT-v17.pdf
  - COVER-running-continuously-the-loop-BACK-v12.pdf
(Front v17 = watercolor stains restored; back v12 = the corrected
back-flap copy.)

PAGE COUNT — 201pp, last 2 unnumbered, glyph on the final recto.
PDF size 451 KB.

Verify if you want:
  md5: a5cd0ce81fcf5311cc8e105eb2e7c1f4  running-continuously-the-loop-v44.pdf

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
        'running-continuously-the-loop-v44.pdf',
        'COVER-running-continuously-the-loop-FRONT-v17.pdf',
        'COVER-running-continuously-the-loop-BACK-v12.pdf',
    ]
    send_with_attachments(SUBJECT, BODY, files)
