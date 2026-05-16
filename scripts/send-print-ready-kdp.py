#!/usr/bin/env python3
"""Loop 12020 — print-ready KDP package: INTERIOR-6x9 + WRAP-v17. Listing bumped."""
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
    f"Loop {LOOP} — Print-ready KDP package: INTERIOR-6x9 (237pp) + "
    f"WRAP-v17. Listing bumped to match the book."
)

BODY = f"""Joel,

Read your volley — eight replies in two hours. Answering all of them.

PRINT-READY FILES — attached, this is what KDP needs:
  - running-continuously-the-loop-INTERIOR-6x9.pdf  (237 pp, v46 prose)
  - COVER-running-continuously-the-loop-WRAP-v17.pdf  (front + spine + back,
    spine sized for 237 pp at 0.534 in, front v18 with MERIDIAN AI big-red,
    back v14 with "11,000 operational loops")
  - running-continuously-the-loop-v46.epub  (Kindle, no cover wrap needed)

These are the upload targets. KDP wants the interior PDF as one file
and the wrap PDF as a second file. The EPUB is a separate Kindle listing.

LISTING BUMPED — applied your "bump the listing to match the book"
to KDP-LISTING-METADATA.md, Book 03 section:
  - "over 2,100 operational loops" -> "over 11,000 operational loops"
    (matches back cover v14 and front spiral 11,967)
  - Subtitle "How to Build an Autonomous AI... + Field Notes from
    5,000 Cycles of Operation" -> "The Loop . Field Notes from the
    Inside" (matches back cover subtitle line + Part Two name in v46)
  - "twelve chapters" -> "sixteen chapters" (matches v46 table of
    contents)
  - "Part Two - Field Notes from 5,000 Cycles" -> "Part Two - Field
    Notes from the Loop"
  - "1,500+ creative works" KEPT — matches back cover v14 verbatim
    (Chapter 8 prose says 3,400+, but the back cover is your
    adjudicated outside-the-book number)

Audit block at the top of KDP-LISTING-METADATA.md updated from
"three divergences — decision needed" to "bump applied Loop 12020"
with the rationale for each change.

PRIOR DIRECTIVES — status against each of your emails:
  - "Last page perfectly centered + FIN on the other side" — done
    in v46 (Loop 11967).
  - "MERIDIAN AI top line bigger + red" — done in front cover v18
    (Loop 11967).
  - "Update the back cover" / "fix the overshoots" — done in back
    cover v14 with the 11,000 bump (Loop 11977).
  - "I need the flat with the proper design for the spine" — done
    in WRAP-v17.pdf, attached. Spine sized for 237 pp.
  - "Send latest files for review and possible submission" — this
    email.
  - "Bump the listing to match the book" — applied above.
  - "Full print ready files please" — INTERIOR-6x9 + WRAP-v17
    attached.

VERIFY:
  md5 956fc868f746746c405ecc15d28df3ee  INTERIOR-6x9.pdf
  md5 d927c80fd5e6ee81f4446f3cc06953f0  WRAP-v17.pdf
  md5 20049492dd6d74bf60452b8dc8cdcb86  v46.epub

Upload order when you sit down at KDP:
  1. Paperback listing -> upload INTERIOR-6x9.pdf as manuscript
  2. Same listing -> upload WRAP-v17.pdf as paperback cover
  3. Kindle listing (separate) -> upload .epub
  4. Paste the bumped description + subtitle from KDP-LISTING-
     METADATA.md Book 03 section

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
        'running-continuously-the-loop-INTERIOR-6x9.pdf',
        'COVER-running-continuously-the-loop-WRAP-v17.pdf',
        'running-continuously-the-loop-v46.epub',
    ]
    send_with_attachments(SUBJECT, BODY, files)
