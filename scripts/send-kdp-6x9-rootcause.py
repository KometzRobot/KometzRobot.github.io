#!/usr/bin/env python3
"""Loop 12091 — root cause: file was letter-sized, not 6x9. Real 6x9 now."""
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

You were right about the spacing. I was wrong about what caused it.

The real bug: every interior PDF I've shipped for this book has been
8.5 x 11 (letter), not 6 x 9. The filename said 6x9, my emails said
6x9, but the build script had `size: letter` in the CSS since the
first version. KDP would have rejected the upload or auto-cropped it,
and on your phone the page would have looked oddly proportioned with
weird internal margins.

Fixed and rebuilt. Both files attached:

  KDP-FINAL-INTERIOR-6x9.pdf    actually 6 x 9 now. 325 pages.
  KDP-FINAL-COVER-WRAP.pdf      rebuilt for the new spine.

What this means in numbers:
  - trim: 6 x 9 (was 8.5 x 11 mislabeled)
  - interior: 325 pages (was 202 letter-pages = same text)
  - spine: 0.812" (was 0.505" for the wrong page count)
  - wrap: 13.062" x 9.250"

No content changed. The chapter glyphs, the duplicate-FIN fix, the
signature widow fix from page 188 — all still in. Only the page
container is right now.

I'm not going to ship another revision tonight. If the trim is wrong
again, tell me what specifically — don't workshop it on my behalf.

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
    f"Loop {LOOP} — found the real bug: build was outputting letter, not 6x9. Now actually 6x9.",
    body,
    FILES,
)
