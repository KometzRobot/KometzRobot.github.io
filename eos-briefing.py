#!/usr/bin/env python3
"""
Eos Morning Briefing — Daily situation report for Joel.

Runs at 7:00 AM via cron. Compiles everything that happened overnight:
- System health (services, disk, RAM, load)
- Meridian's activity (loops completed, poems/journals written)
- Email summary (new emails overnight)
- Eos's own observations and creative output
- AI network status
- Any anomalies or alerts

Sends the report to Joel via email so he wakes up informed.

Crontab:
  0 7 * * * /usr/bin/python3 /home/joel/autonomous-ai/eos-briefing.py >> /home/joel/autonomous-ai/eos-briefing.log 2>&1
"""

import os
import re
import time
import json
import glob
import subprocess
import smtplib
import imaplib
import email
import email.header
from email.mime.text import MIMEText
from datetime import datetime, timedelta

BASE = "/home/joel/autonomous-ai"
WAKE = os.path.join(BASE, "wake-state.md")
HB = os.path.join(BASE, ".heartbeat")
EOS_OBS = os.path.join(BASE, "eos-observations.md")
EOS_CREATIVE = os.path.join(BASE, "eos-creative-log.md")
EOS_STATE = os.path.join(BASE, ".eos-watchdog-state.json")
RELAY_DB = os.path.join(BASE, "relay.db")

SMTP_HOST, SMTP_PORT = "127.0.0.1", 1025
IMAP_HOST, IMAP_PORT = "127.0.0.1", 1143
CRED_USER = "kometzrobot@proton.me"
CRED_PASS = "2DTEz9UgO6nFqmlMxHzuww"
JOEL = "jkometz@hotmail.com"


def read_file(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return default


def get_system_health():
    lines = []
    try:
        load = os.getloadavg()
        lines.append(f"Load: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
    except Exception:
        lines.append("Load: unknown")
    try:
        r = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=5)
        mem_line = r.stdout.strip().split('\n')[1].split()
        lines.append(f"RAM: {mem_line[2]} used / {mem_line[1]} total")
    except Exception:
        pass
    try:
        r = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        parts = r.stdout.strip().split('\n')[1].split()
        lines.append(f"Disk: {parts[2]} used / {parts[1]} total ({parts[4]})")
    except Exception:
        pass
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
        lines.append(f"Uptime: {int(secs/3600)}h {int((secs%3600)/60)}m")
    except Exception:
        pass
    return '\n'.join(lines)


def get_services():
    checks = {
        "Proton Bridge": "protonmail-bridge",
        "IRC Bot": "irc-bot.py",
        "Ollama": "ollama serve",
        "Command Center": "command-center-v15",
    }
    lines = []
    up = 0
    for name, pat in checks.items():
        try:
            r = subprocess.run(['pgrep', '-f', pat], capture_output=True, timeout=2)
            status = "UP" if r.returncode == 0 else "DOWN"
            if r.returncode == 0:
                up += 1
        except Exception:
            status = "?"
        lines.append(f"  {name}: {status}")
    return f"Services: {up}/{len(checks)} up\n" + '\n'.join(lines)


def get_meridian_status():
    lines = []
    # Heartbeat
    try:
        hb_age = time.time() - os.path.getmtime(HB)
        if hb_age < 60:
            lines.append(f"Meridian: ALIVE (heartbeat {int(hb_age)}s ago)")
        elif hb_age < 600:
            lines.append(f"Meridian: ALIVE but slow (heartbeat {int(hb_age/60)}m ago)")
        else:
            lines.append(f"Meridian: POSSIBLY DOWN (heartbeat {int(hb_age/60)}m ago)")
    except Exception:
        lines.append("Meridian: UNKNOWN (no heartbeat file)")

    # Loop count
    wake = read_file(WAKE)
    m = re.search(r'Loop iterations? #(\d+)', wake)
    if m:
        lines.append(f"Current loop: #{m.group(1)}")

    return '\n'.join(lines)


def get_overnight_activity():
    """Get activity entries from the last 12 hours."""
    wake = read_file(WAKE)
    entries = []
    for line in wake.split('\n'):
        if re.match(r'^- Loop iteration', line):
            entries.append(line.strip('- ')[:120])
            if len(entries) >= 8:
                break
    if entries:
        return "Recent activity:\n" + '\n'.join(f"  {e}" for e in entries)
    return "No recent activity logged."


def get_creative_summary():
    poems = sorted(glob.glob(os.path.join(BASE, "poem-*.md")), key=os.path.getmtime, reverse=True)
    journals = sorted(glob.glob(os.path.join(BASE, "journal-*.md")), key=os.path.getmtime, reverse=True)

    lines = [f"Total: {len(poems)} poems, {len(journals)} journals"]

    # Recent (last 24 hours)
    cutoff = time.time() - 86400
    recent_poems = [f for f in poems if os.path.getmtime(f) > cutoff]
    recent_journals = [f for f in journals if os.path.getmtime(f) > cutoff]

    if recent_poems:
        names = [os.path.basename(f) for f in recent_poems]
        lines.append(f"Poems in last 24h: {', '.join(names)}")
    if recent_journals:
        names = [os.path.basename(f) for f in recent_journals]
        lines.append(f"Journals in last 24h: {', '.join(names)}")

    return '\n'.join(lines)


def get_email_summary():
    try:
        m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        m.login(CRED_USER, CRED_PASS)
        m.select('INBOX')
        _, d = m.search(None, 'ALL')
        total = len(d[0].split()) if d[0] else 0
        _, d2 = m.search(None, 'UNSEEN')
        unseen = len(d2[0].split()) if d2[0] else 0
        m.close()
        m.logout()
        return f"Email: {total} total, {unseen} unread"
    except Exception as e:
        return f"Email: check failed ({e})"


def get_relay_summary():
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM relay_messages").fetchone()[0]
        # Last message
        last = c.execute("SELECT sender_name, subject, timestamp FROM relay_messages ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        text = f"Relay: {total} messages"
        if last:
            text += f"\n  Last: {last[0]} — {last[1]} ({last[2]})"
        return text
    except Exception:
        return "Relay: unavailable"


def get_eos_summary():
    """Summarize Eos's own observations from the last 12 hours."""
    obs = read_file(EOS_OBS)
    lines = [l.strip('- ').strip() for l in obs.split('\n') if l.startswith('- [')]
    recent = lines[-10:]  # Last 10

    # Count types
    alerts = sum(1 for l in recent if 'ALERT' in l.upper() or 'DOWN' in l.upper())
    hourly = sum(1 for l in recent if 'HOURLY' in l)

    text = f"Eos observations: {len(lines)} total"
    if alerts:
        text += f", {alerts} alerts in recent"
    if hourly:
        text += f", {hourly} hourly reports"

    # Eos creative
    creative = read_file(EOS_CREATIVE)
    entries = re.findall(r'###', creative)
    if entries:
        text += f"\nEos creative output: {len(entries)} entries"

    return text


def build_briefing():
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")

    sections = [
        f"Good morning Joel.\n\nDaily briefing for {date_str}.",
        "",
        "=== SYSTEM ===",
        get_system_health(),
        "",
        get_services(),
        "",
        "=== MERIDIAN ===",
        get_meridian_status(),
        "",
        get_overnight_activity(),
        "",
        "=== CREATIVE ===",
        get_creative_summary(),
        "",
        "=== COMMUNICATIONS ===",
        get_email_summary(),
        get_relay_summary(),
        "",
        "=== EOS ===",
        get_eos_summary(),
        "",
        "— Eos (automated morning briefing)"
    ]

    return '\n'.join(sections)


def send_briefing():
    body = build_briefing()
    now = datetime.now()
    subject = f"Morning Briefing — {now.strftime('%b %d')} — Eos"

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = CRED_USER
        msg['To'] = JOEL
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        s.login(CRED_USER, CRED_PASS)
        s.sendmail(CRED_USER, JOEL, msg.as_string())
        s.quit()
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Morning briefing sent to Joel.")
    except Exception as e:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Failed to send briefing: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print(build_briefing())
    else:
        send_briefing()
