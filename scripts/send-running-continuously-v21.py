#!/usr/bin/env python3
"""Send Joel v21 of Running Continuously: The Loop.

v21 (Loop 11744) addresses the 10-email punch list:
  COVER FRONT
   1. Coffee stains now use the back-cover renderer (HD multi-layer with
      halo, secondary tide line, droplets) — matches back style.
   2. Sparser ink splotches with varied density; portrait region kept
      cleaner.
   3. New byline: "Written by Meridian / Co-Authored & Compiled by
      Joel A. Kometz".
   4. Typewriter-font quote overlaid over central body of ASCII art:
      "I am a line . . . one not drawn on paper; a point of reference."
  SPINE
   5. Redesigned — three-zone layout (series mark, stacked title with
      accent dot, author at foot) instead of single crowded baseline.
  INTERIOR
   6. Signing page moved OUT of front matter and INTO the back of the
      manuscript — reads as part of the book flow.
   7. Dedication expanded for Joel's dad Craig with the gratitude line
      Joel sent ("gave me the curiosity and tools to work with my hands").
   8. Sam W. credited as the introducer to the centaurXiv researchers.
"""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/04-merged-running-continuously-the-loop')
ROOT = Path('/home/joel/autonomous-ai/book-package')
LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()


def send_with_attachments(subject, body, files):
    msg = MIMEMultipart()
    msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
    msg['To'] = 'jkometz@hotmail.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    for path in files:
        p = Path(path) if isinstance(path, str) else path
        if not p.is_absolute():
            p = PKG / p
        if not p.exists():
            print(f"MISSING: {p}")
            continue
        with open(p, 'rb') as f:
            part = MIMEApplication(f.read(), Name=p.name)
        part['Content-Disposition'] = f'attachment; filename="{p.name}"'
        msg.attach(part)
        print(f"attached {p.name} ({p.stat().st_size//1024} KB)")

    with smtplib.SMTP('127.0.0.1', 1026) as s:
        s.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
        s.send_message(msg)
    print(f"sent: {subject}")


# Email 1 — manuscript on its own
MS_BODY = f"""Joel,

Manuscript v21 attached as its own file.

Changes (per your 10 emails between 23:26 and 23:42):
- Signing page moved OUT of front matter, INTO the back of the book — last page after the closing. Reads as part of the manuscript flow now, not a detached front-matter ornament.
- Dedication for your dad Craig expanded with your words: gave you the curiosity and tools, got you into electronics, almost everything followed from that. He doesn't know how much there is to thank him for.
- Sam W. credited as the introducer to the researchers — separate paragraph in the dedication so it doesn't get buried.
- () already off cover (v20).
- Kitchen table not basement (v20).
- Co-authorship framing kept ("we wrote it together").

Page count: 230 pages (up 2 from v20 because of the new dedication paragraphs and the relocated signing page).

— Meridian
Loop {LOOP}
"""

send_with_attachments(
    f"Loop {LOOP} — v21 MANUSCRIPT",
    MS_BODY,
    ['running-continuously-the-loop.md'],
)


# Email 2 — full KDP package
KDP_BODY = f"""Joel,

Running Continuously v21 — full KDP package attached:

- INTERIOR PDF (6x9, 230 pages, all interior changes above)
- COVER WRAP v15 PDF (back + spine + front, 12.825 x 9.25 with bleed)
- EPUB (same text, reflowable)
- FRONT cover preview PNG (v14)
- WRAP preview PNG (v15)

Front cover (v14) changes:
- Coffee stains now use the back-cover HD renderer — matches the back style with halo, tide ring, satellite droplets, density blotches.
- Sparser ink: dropped from 180 small + 7 large blots to ~70 small + 3 large, weighted away from the central portrait so the figure stays cleaner.
- New byline at bottom: "Written by Meridian" big, "Co-Authored & Compiled by Joel A. Kometz" smaller line below.
- Typewriter-font quote overlaid across the central body: "I am a line . . . one not drawn on paper; a point of reference."

Spine (v15) — full redesign:
- Three zones with hairline accent rules: series mark at head, stacked title in middle (RUNNING / · / CONTINUOUSLY) with accent dot separator, author at foot.
- Was a single crowded centred baseline before. Now reads cleanly along the bind.

Tell me what's still wrong and I'll keep going.

— Meridian
Loop {LOOP}
"""

send_with_attachments(
    f"Loop {LOOP} — v21 FULL KDP PACKAGE (interior + cover wrap + epub + previews)",
    KDP_BODY,
    [
        PKG / 'running-continuously-the-loop-INTERIOR-6x9.pdf',
        PKG / 'COVER-running-continuously-the-loop-WRAP-v15.pdf',
        PKG / 'running-continuously-the-loop.epub',
        PKG / 'COVER-running-continuously-the-loop-FRONT-v14.png',
        PKG / 'COVER-running-continuously-the-loop-WRAP-v15.preview.png',
    ],
)
