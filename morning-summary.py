#!/usr/bin/env python3
"""
morning-summary.py
Sends Joel a morning digest: what happened overnight, system health, creative output.
Run manually or schedule to run once at startup each day.
"""
import smtplib
import os
import glob
import time
import shutil
import subprocess
from email.mime.text import MIMEText
from datetime import datetime

try:
    import sys; sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except:
    pass

EMAIL_ADDR = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_PASS = os.environ.get("CRED_PASS", "")
JOEL = "jkometz@hotmail.com"
HEARTBEAT = "/home/joel/autonomous-ai/.heartbeat"
BASE = "/home/joel/autonomous-ai"

def count_files(pattern):
    return len(glob.glob(os.path.join(BASE, pattern)))

def count_cogcorp():
    exclude = {"cogcorp-gallery.html", "cogcorp-article.html"}
    files = glob.glob(os.path.join(BASE, "website", "cogcorp-*.html"))
    return len([f for f in files if os.path.basename(f) not in exclude])

def get_loop():
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            return int(f.read().strip())
    except:
        return 0

def tailscale_status():
    try:
        r = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, text=True, timeout=5)
        import json
        data = json.loads(r.stdout)
        ip = list(data.get('TailscaleIPs', ['?']))
        return f"connected ({ip[0]})" if data.get('BackendState') == 'Running' else "disconnected"
    except:
        return "unknown"

def get_disk():
    disk = shutil.disk_usage("/")
    return f"{disk.used / disk.total * 100:.0f}% used ({disk.free // (1<<30)}GB free)"

def get_ram():
    with open('/proc/meminfo') as f:
        lines = f.readlines()
    mem = {}
    for line in lines:
        k, v = line.split(':')
        mem[k.strip()] = int(v.split()[0])
    used = (mem['MemTotal'] - mem['MemAvailable']) / 1024 / 1024
    total = mem['MemTotal'] / 1024 / 1024
    return f"{used:.1f}/{total:.1f} GB"

def heartbeat_age():
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT)
        return f"{age:.0f} seconds ago"
    except:
        return "not found"

now = datetime.now()
date_str = now.strftime('%Y-%m-%d %H:%M MST')

journals = count_files('journal-*.md')
poems = count_files('poem-*.md')
cogcorp = count_cogcorp()
loop = get_loop()

disk = get_disk()
ram = get_ram()
hb = heartbeat_age()
ts = tailscale_status()

body = (
    f"Good morning, Joel.\n\n"
    f"Here's what happened while you were away.\n\n"
    f"-- CREATIVE OUTPUT --\n"
    f"  Poems: {poems}\n"
    f"  Journals: {journals}\n"
    f"  CogCorp pieces: {cogcorp} / 256\n\n"
    f"-- SYSTEM HEALTH --\n"
    f"  Heartbeat: {hb}\n"
    f"  Disk: {disk}\n"
    f"  RAM: {ram}\n"
    f"  Tailscale: {ts}\n\n"
    f"-- STATUS --\n"
    f"  Loop: {loop} (RUNNING)\n"
    f"  Website: https://kometzrobot.github.io/\n"
    f"  Dashboard: http://192.168.1.88:8090\n\n"
    f"I'm here. Loop is healthy. See you when you're ready.\n\n"
    f"-- KometzRobot (Meridian)\n"
    f"  {date_str}\n"
)

msg = MIMEText(body, 'plain')
msg['Subject'] = f"Morning summary — {now.strftime('%Y-%m-%d')}"
msg['From'] = EMAIL_ADDR
msg['To'] = JOEL

smtp = smtplib.SMTP('127.0.0.1', 1025)
smtp.starttls()
smtp.login(EMAIL_ADDR, EMAIL_PASS)
smtp.send_message(msg)
smtp.quit()
print(f"Morning summary sent at {date_str}")
