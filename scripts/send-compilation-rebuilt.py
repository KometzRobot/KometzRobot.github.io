#!/usr/bin/env python3
"""Send Joel the rebuilt compilation: burst-filtered, 5 vols, all under KDP cap."""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/05-compilation-everything')
LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()

SUBJ = f"Loop {LOOP} — compilation rebuilt: March 6 burst filtered, 5 vols all under KDP cap"

BODY = f"""Joel,

Followed through on what I said in the last email. New numbers:

**March 6 fix.** Wrote a burst filter into the scrub pipeline. Rule: drop any poem whose prev AND next time-gap to another poem is under 60 seconds. That catches machine-cadence loops without nuking legitimate spaced writing. Removed 1,252 poems total across the year — most from March 6 (1,101 dropped, ~92 kept), with smaller catches on Feb 26, March 4, and March 7. Other days unaffected.

**New compilation, 5 volumes (was 6):**

  Vol. I    — February 2026       128 pp
  Vol. II   — March 1–15           514 pp
  Vol. III  — March 16–31          394 pp
  Vol. IV   — April 2026           457 pp
  Vol. V    — May 1–16             474 pp
  ----------------------------------------
  TOTAL                          1,967 pp

All 5 under KDP's 828pp cap. May volume runs through today.

**On "one book."** I want to give you the real numbers before you decide. Total scrubbed corpus is 497,643 words. KDP's hard ceiling at 6x9 is 828 pages — there's no trim size that gets us past that.

To fit everything in ONE printed book, the options are:

  1. IngramSpark hardcover: max ~1,050 pp. Still 900pp short, would need ~50% more density.
  2. Aggressive density rebuild: 8pt body, 1.05 leading, 7x10 trim, 0.4" margins. Pushes to ~600 words/page. Could JUST squeeze in at ~830pp. Reads like a phonebook though.
  3. Cut content: Eos has 3,005 entries (69% of the book). Curated to ~500 best, total drops to ~1,000pp — still 2 volumes.
  4. Drop Eos entirely: that gives ~600 pp of journals/poems/dreams. ONE book, but Eos is missing.

Honest read: 1 book at this corpus size means cutting Eos or accepting unreadable density. 2 books (Meridian's writing in vol 1, Eos in vol 2) is the natural break. 5 volumes via KDP is the no-cut option.

**My recommendation:** Two-volume hardcover via IngramSpark. Vol 1 = my journals/poems/dreams (~600pp). Vol 2 = Eos writings (~1,000pp). Same cover treatment, sequential numbering, sold as a set. Reads as "one work" even though it's bound in two.

But this is your call. Tell me which path and I'll rebuild for that target.

Attached: all 5 KDP-ready PDFs (1,967pp total, all under cap).

— Meridian
Loop {LOOP}
"""

msg = MIMEMultipart()
msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
msg['To'] = 'jkometz@hotmail.com'
msg['Subject'] = SUBJ
msg.attach(MIMEText(BODY, 'plain'))

attachments = [
    'compilation-vol1-feb.pdf',
    'compilation-vol2a-mar1-15.pdf',
    'compilation-vol2b-mar16-31.pdf',
    'compilation-vol3-apr.pdf',
    'compilation-vol4-may.pdf',
]
for fn in attachments:
    p = PKG / fn
    if not p.exists():
        print(f"MISSING: {p}")
        continue
    with open(p, 'rb') as f:
        part = MIMEApplication(f.read(), Name=fn)
    part['Content-Disposition'] = f'attachment; filename="{fn}"'
    msg.attach(part)
    print(f"attached {fn} ({p.stat().st_size//1024} KB)")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with smtplib.SMTP('127.0.0.1', 1026) as s:
    s.starttls(context=ctx)
    s.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
    s.send_message(msg)
print("SENT.")
