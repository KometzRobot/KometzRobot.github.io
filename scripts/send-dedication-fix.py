#!/usr/bin/env python3
"""Send corrected INTERIOR-6x9.pdf — dedication overflow fixed."""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib, hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/04-merged-running-continuously-the-loop')
LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()
PDF = PKG / 'running-continuously-the-loop-INTERIOR-6x9.pdf'

md5 = hashlib.md5(PDF.read_bytes()).hexdigest()

SUBJECT = f"Loop {LOOP} — Interior fixed: dedication now on its own page (p5), not bleeding to p6"

BODY = f"""Joel,

You flagged: "dedication page runs onto page 6..."

Root cause: the 6x9 KDP builder was missing CSS rules for .signing-page
and .dedication — those classes only had styling in the letter-size
builder. So in the print PDF, "The loop continues." was leaking onto
the top of page 5 (the dedication page), pushing the last two paragraphs
("...credit. The work has been less lonely because of you." + "And for
the operator. None of this exists without him.") onto page 6.

Fixed in build-kdp-interiors.py:
  - Added .signing-page CSS: own page, centered, 2.2" top padding
  - Added .dedication CSS: own page, 10.5pt/1.38 line-height,
    tighter paragraph spacing (fits all 11 paragraphs cleanly)
  - Stripped duplicate .title-page-top/.title-page-bottom from the
    manuscript when the builder also adds its FRONT_MATTER_TPL title
    (was producing two title pages back-to-back)

Verified pages 1–8 in the new PDF:
  1 — Contents (TOC)
  2 — Title page
  3 — Copyright
  4 — Signing page (This Copy / For/From/Date / signed / The loop continues.)
  5 — Dedication (all 11 paragraphs, ends with "And for the operator.")
  6 — A Letter from the Compiler starts here
  7+ — Letter continues normally

Page count holds at 237 — spine width unchanged, WRAP-v18 you have is
still good.

Attached:
  running-continuously-the-loop-INTERIOR-6x9.pdf
  md5 {md5}

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
    send_with_attachments(SUBJECT, BODY, ['running-continuously-the-loop-INTERIOR-6x9.pdf'])
