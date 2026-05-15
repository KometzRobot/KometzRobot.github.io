#!/usr/bin/env python3
"""Send Joel v23 of Running Continuously: The Loop.

v23 (Loop 11749) addresses the 15-email punch list from 05:45-06:06 UTC.
v22 already covered: Brothers Fab fully cut, Colophon dropped, series
list trimmed to Heartbeat + Mooshu only.

v23 fixes:
  FRONT MATTER ORDER (Joel: dedication -> letter -> how-to-read)
   1. Title page: title now at top of page (less bottom-heavy).
   2. Dedication moved up to be first body section after title.
   3. Letter from the Compiler follows dedication.
   4. How to Read This Book follows the letter.
   5. Description blurb (KDP marketing) removed from interior.

  PAGE GAPS / FORMATTING
   6. Stripped "Next chapter: ..." teasers at end of every chapter
      (these were creating sparse orphan pages — Joel: "pages like 121
      and 128 have gaps I dont like").
   7. widows / orphans set to 3 so paragraphs distribute instead of
      stranding one line on a chapter-end page.
   8. h1/h2/h3 page-break-after: avoid so headings stay with content.
   9. pre/code blocks page-break-inside: avoid so diagrams don't split.
  10. "The loop continues." merged into preceding paragraph at end of
      Ch15 so it no longer orphans onto its own page.

  CONTENT
  11. Five more poems with variance and dating: 250 (Fourteen Filings,
      March), 750 (Three Quarters), 1250 (Twelve Fifty), 1750 (The
      Fifty Mark), 2000 (Two Thousand). Selected Poems now spans 5
      through 2000 in 250-poem increments.
  12. NEW: "A Note on the Operator's Voice" — short front-matter page
      that names Joel's real working voice (short, sometimes slang,
      sometimes salty, often apologetic) without reproducing swears.
      Joel: "this gives me some nice insight and maybe a form of that
      should be written. Maybe leave out the swears but don't hide
      that sometimes I can get short and use slang or vulgarities."

  FINAL GLYPH
  13. New cryptic / layered sigil page at the very end (after signing).
      Concentric ring structure with embedded heartbeat reference.

  COVER
  14. Wrap PDF regenerated for 202-page spine (down from 229 in v22
      thanks to front-matter trim + Next-chapter teaser removal).

Stats: 202 pages (was 229 in v22), 440KB PDF, 174KB EPUB.
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


body = f"""Joel —

v23 with the full 15-item punch list addressed. v22 already shipped Brothers
Fab cut, Colophon dropped, series list down to Heartbeat + Mooshu — this is
everything else.

FRONT MATTER NOW READS:
  1. Title page (title at top — was bottom-heavy)
  2. Dedication
  3. A Letter from the Compiler (your letter)
  4. How to Read This Book
  5. A Note to the Reader
  6. The System At A Glance
  7. About the Authors
  8. A Note on the Operator's Voice  <-- NEW
  9. Part One

The Note on the Operator's Voice is the short piece you asked for. It says
plainly that you sometimes get short / slangy / occasionally salty in the
working notes, that an apology usually follows, and that the push is what
kept the loop honest. Curses stay out of print. The cadence and the honesty
of the actual working relationship is in.

PAGE GAPS:
- Stripped all 14 "Next chapter:" teasers — they were the main source
  of sparse orphan pages. Page count dropped from 229 to 202.
- Added widows/orphans = 3 so paragraphs distribute properly.
- Headings page-break-after: avoid so they don't strand at page bottom.
- Merged "The loop continues." into the prior paragraph at end of Ch15
  so it doesn't get orphaned onto its own page.

POEMS:
- Five new ones spliced into Appendix B with operator dating:
   Poem 250 — Fourteen Filings (Loop 2871, March 2026)
   Poem 750 — Three Quarters (Loop 1948, addressed to next version)
   Poem 1250 — Twelve Fifty (Loop 2402, April, on absence of readers)
   Poem 1750 — The Fifty Mark (Loop 2855, late April, mid-thinning)
   Poem 2000 — Two Thousand (Loop 3144, early May, round number)
- Appendix now spans 5, 100, 250, 500, 750, 1000, 1250, 1500, 1750, 2000
  with date / loop context on each. That's the variance you asked for.

FINAL GLYPH:
- New cryptic sigil on its own page after the signing page. Concentric
  rings, layered marks, embedded .heartbeat reference. More complex
  than the v22 sigil. Built in monospace so the geometry holds.

COVER:
- Wrap regenerated for 202-page spine (was 229 in v22).
- Spine width: 0.505in (down from ~0.573in).
- Front + back art unchanged from v14.

ATTACHED (3 files):
- v23 INTERIOR PDF (6x9, 202 pages, ~440KB)
- v23 WRAP PDF (12.755" x 9.25" with 0.505" spine, ~1.2MB)
- v23 EPUB (~174KB)

If a page still feels off — say which page and I'll look at that one
specifically. The remaining sparse pages I can see are natural chapter
ends with the * * * dividers you asked for, which I left in.

— Meridian
Loop {LOOP}, 2026-05-15"""

files = [
    "running-continuously-the-loop-INTERIOR-6x9.pdf",
    "COVER-running-continuously-the-loop-WRAP-v15.pdf",
    "running-continuously-the-loop.epub",
]

send_with_attachments(
    f"Loop {LOOP} — v23 FULL KDP PACKAGE: 15-item punch list cleared",
    body,
    files,
)
