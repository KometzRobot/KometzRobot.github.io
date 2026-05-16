#!/usr/bin/env python3
"""Loop 12079 — Joel flagged 3 defects in the v23/v24 KDP-FINAL files:
   page 55 graphic bad, stars at chapter starts off-center, duplicate
   FIN+glyph ending page. All three fixed; re-attach the new pair."""
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

interior_kb = FILES[0].stat().st_size // 1024
wrap_kb = FILES[1].stat().st_size // 1024

body = f"""Joel —

Three things you flagged are fixed. Re-attached pair below.

1. Page 55 graphic — the One Writer / Many Readers diagram was
   designed for letter width and was overflowing the 6x9 column,
   boxes breaking across lines. Redrew it stacked: state-file box at
   the top, single SOMA writer, readers listed in a vertical box
   below. Same idea, fits the page cleanly now. Lands on p53 in
   the new pagination.

2. Stars off-center at chapter starts — the chapter-separator glyph
   (※ · ※ · ※) had no CSS in the 6x9 builder, so it rendered
   left-aligned with no margins and pushed the next chapter heading
   down weirdly. Added the .chapter-sep rule. Now it centers, has
   breathing room above and below, and the chapter heading after it
   stays glued so nothing falls onto an awkward line.

3. Duplicate FIN+glyph at the end — root cause: the merged
   manuscript already wrote one FIN+mandala block, and the KDP
   builder was appending its own "Also in the Series" + pyramid FIN
   on top of that. Two closings. Fixed the builder to strip the
   merged manuscript's closing blocks before appending its back
   matter. Only one FIN page now, the pyramid+FIN one you'd seen.

Page count dropped from 238 to 233 (the extra closing was 5 pages).
That changed the spine width, so I rebuilt the wrap:

  KDP-FINAL-INTERIOR-6x9.pdf   233 pages, 6 x 9 trim, {interior_kb} KB
  KDP-FINAL-COVER-WRAP.pdf     wrap 12.832 x 9.25 in, {wrap_kb} KB
  Spine: 0.583" for 233 pages (was 0.595" for 238)

Both attached, both go straight to KDP — interior in the manuscript
slot, wrap in the cover slot.

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
    f"Loop {LOOP} — KDP FINAL re-attached: page 55 / chapter stars / duplicate FIN all fixed",
    body,
    FILES,
)
