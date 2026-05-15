#!/usr/bin/env python3
"""Loop 11958 — book v43 + latest covers (FRONT v17, BACK v12) to Joel."""
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


BODY = f"""Joel,

Walked your last volley. Fixed everything you flagged. New build is v43.

LAST PAGE — coordinates + numerals restored (you said you liked them).
You preferred the v40 ending. v41/v42 had the abstract cryptic glyph;
that's gone. Back to the compass-shape + dot-cluster + M·ML·LXXVI /
N53° · W114° / .heartbeat. The version that ships.

LAST PAGE NOW LANDS ON PAGE 201, UNNUMBERED.
Added a blank verso between the glossary close and the final glyph,
so the glyph hits a recto (right-hand page) as a proper closing
flourish. Page count went 200 -> 201. Glyph page itself carries no
page number, same as before.

GLOSSARY — already mom-friendly (your "people like my mom" note from
the earlier email): Cron, context window, IMAP/SMTP, LLM, Markdown,
Pandoc, prompt, token, all explained in plain language with no jargon
chains. If she can read "Cron — a Unix scheduler that runs other
programs on a clock" she's set. 56 terms. Glossary fills the back
where Note-on-Cover / How-to-Verify / Colophon used to be (all three
deleted per your three one-liners — confirmed gone).

COVERS — latest set:
- FRONT v17 (PDF + PNG) — watercolor coffee-stain figure-at-table, the
  one you greenlit. No spiral. No alternate. This is the one.
- BACK v12 (PDF + PNG) — fixed-typo version (basement -> kitchen
  table to match the front).

Attached this email:
1. running-continuously-the-loop-v43.pdf — 201pp, your fixes applied
2. COVER-FRONT-v17.pdf + .png
3. COVER-BACK-v12.pdf + .png

Tell me what's wrong and I'll fix v44. Otherwise this is the print
file.

— Meridian
Loop {LOOP}
"""

send_with_attachments(
    f"Loop {LOOP} — Book v43 (201pp, coords+numerals restored) + covers FRONT v17 + BACK v12",
    BODY,
    [
        'running-continuously-the-loop-v43.pdf',
        'COVER-running-continuously-the-loop-FRONT-v17.pdf',
        'COVER-running-continuously-the-loop-FRONT-v17.png',
        'COVER-running-continuously-the-loop-BACK-v12.pdf',
        'COVER-running-continuously-the-loop-BACK-v12.png',
    ],
)
