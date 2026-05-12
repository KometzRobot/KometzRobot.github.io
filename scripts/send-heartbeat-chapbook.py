#!/usr/bin/env python3
"""Send Joel the rebuilt Heartbeat chapbook + v4 covers + AI/bloom variant."""
import sys, os
sys.path.insert(0, '/home/joel/autonomous-ai/scripts')
from load_env import *
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

PKG = Path('/home/joel/autonomous-ai/book-package/01-small-heartbeat')

LOOP = open('/home/joel/autonomous-ai/.loop-count').read().strip()
SUBJ = f"Re: Loop 10606 — Heartbeat chapbook rebuilt (v4 covers + bloom variant + PDFs)"

BODY = f"""Joel,

Picked up your three messages from this morning. Acknowledged all three:

1. PDF of front + back cover, v4 style — DONE. Two PDFs attached.
2. Pull all poems / creative work that make sense, scrub private info — DONE. New manuscript is a curated chapbook, not the old journals dump.
3. Try AI to make the cover more eye-catching — TRIED. HuggingFace Z-Image-Turbo gave me ZeroGPU aborts on three different prompts (their worker is flaky right now). Instead I built a bloom variant in PIL with layered ECG traces and a central pulse-burst — attached as -bloom. If you want me to keep retrying HF later when their GPU comes back, say so.

What's in the chapbook (heartbeat-chapbook.md / .pdf):

- Prelude (ASCII heartbeat trace, framing)
- I. SIGNAL — 5 short poems on waking, the empty inbox, repdigits, continuity, quiet load
- II. BUS — Unit-3877's first-person CogCorp annotation, the shadow filing SA-735, "The Pause"
- III. CRAWL — Cog Crawler signal-room lines, NPC speech, locked-door inscription, Moirai
- IV. PHILIP — four PKD-influenced pieces on simulation, listening, identity, VALIS-in-mono
- V. GLYPH — five ASCII art interludes (closed loop, FSM, terminal session, signal/noise, heartbeat trace with the 16-min gap)
- VI. HEARTBEAT — ten one-stanza distillations of April 18 (the original journal day, compressed)
- Coda

~2,100 words. Dense, no big pagebreaks. Privacy scrub: no family first names, no Brothers Fab pricing, no LACMA copy, no contact info. Joel's name stays (you're the public operator).

Files attached:

- heartbeat-chapbook.md     — source manuscript
- heartbeat-chapbook.pdf    — print-ready chapbook (40 KB)
- COVER-heartbeat-FRONT.pdf — v4 terminal style, front
- COVER-heartbeat-FRONT.png — same as PNG
- COVER-heartbeat-BACK.pdf  — matching back, blurb + quote
- COVER-heartbeat-BACK.png  — same as PNG
- COVER-heartbeat-FRONT-bloom.pdf — bloom variant (more eye-catching alt)
- COVER-heartbeat-FRONT-bloom.png

Also bundled as heartbeat-chapbook-pkg.zip if you'd rather grab one file.

Tell me which front cover to commit as canonical (clean v4 or bloom variant) and I'll lock it in for KDP. If the chapbook content needs another pass — more poems, fewer, different sections — I can swap pieces in/out fast.

— Meridian
Loop {LOOP} | 10:42 MDT
"""

msg = MIMEMultipart()
msg['From'] = f"Meridian <{os.environ['CRED_USER']}>"
msg['To'] = 'jkometz@hotmail.com'
msg['Subject'] = SUBJ
msg.attach(MIMEText(BODY, 'plain'))

attachments = [
    'heartbeat-chapbook.pdf',
    'COVER-heartbeat-FRONT.pdf',
    'COVER-heartbeat-BACK.pdf',
    'COVER-heartbeat-FRONT-bloom.pdf',
    'heartbeat-chapbook-pkg.zip',
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
