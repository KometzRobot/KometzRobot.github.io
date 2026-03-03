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
try:
    import sys; sys.path.insert(0, BASE); import load_env
except Exception:
    pass
WAKE = os.path.join(BASE, "wake-state.md")
HB = os.path.join(BASE, ".heartbeat")
EOS_OBS = os.path.join(BASE, "eos-observations.md")
EOS_CREATIVE = os.path.join(BASE, "eos-creative-log.md")
EOS_STATE = os.path.join(BASE, ".eos-watchdog-state.json")
RELAY_DB = os.path.join(BASE, "agent-relay.db")

SMTP_HOST, SMTP_PORT = "127.0.0.1", 1026
IMAP_HOST, IMAP_PORT = "127.0.0.1", 1144
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")
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
        "Ollama": "ollama serve",
        "Command Center": "command-center",
        "The Signal": "the-signal.py",
        "Cloudflare Tunnel": "cloudflared",
        "Soma": "symbiosense.py",
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

    # Loop count — try dedicated file first, then wake-state
    loop_file = os.path.join(BASE, ".loop-count")
    try:
        with open(loop_file) as f:
            lines.append(f"Current loop: {f.read().strip()}")
    except Exception:
        wake = read_file(WAKE)
        m = re.search(r'Loop (\d+)', wake)
        if m:
            lines.append(f"Current loop: {m.group(1)}")

    return '\n'.join(lines)


def get_overnight_activity():
    """Get overnight activity from relay messages + git log."""
    lines = []
    # Recent git commits (last 24h)
    try:
        r = subprocess.run(
            ['git', '-C', BASE, 'log', '--since=24 hours ago', '--oneline', '--no-merges'],
            capture_output=True, text=True, timeout=5)
        commits = [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
        if commits:
            lines.append(f"Git commits (last 24h): {len(commits)}")
            for c in commits[:6]:
                lines.append(f"  - {c[:120]}")
    except Exception:
        pass
    # Recent relay activity
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        rows = c.execute("""SELECT agent, message FROM agent_messages
                           WHERE timestamp > datetime('now', '-12 hours')
                           ORDER BY rowid DESC LIMIT 8""").fetchall()
        conn.close()
        if rows:
            lines.append(f"Agent relay (last 12h): {len(rows)} messages")
            for agent, msg in rows[:4]:
                lines.append(f"  - {agent}: {msg[:100]}")
    except Exception:
        pass
    return '\n'.join(lines) if lines else "No recent activity logged."


def get_pending_messages():
    """Check for recent dashboard messages from Joel."""
    try:
        import sqlite3
        # Dashboard messages are in memory.db dashboard_messages table
        db = os.path.join(BASE, "memory.db")
        if not os.path.exists(db):
            return ""
        conn = sqlite3.connect(db)
        c = conn.cursor()
        # Check for recent messages (last 24h) from Joel
        c.execute("""SELECT COUNT(*) FROM dashboard_messages
                     WHERE timestamp > datetime('now', '-24 hours')
                     AND message LIKE '%Joel%'""")
        count = c.fetchone()[0]
        conn.close()
        if count > 0:
            return f"NOTE: {count} dashboard message(s) in last 24h mentioning Joel."
        return "Dashboard: no recent Joel messages."
    except Exception:
        return "Dashboard: check unavailable."


def get_outstanding_issues():
    """Pull outstanding issues from wake-state and recent alerts."""
    issues = []
    # Check wake-state for Joel's remaining requests
    wake = read_file(WAKE)
    in_issues = False
    for line in wake.split('\n'):
        if "### Joel's Remaining Requests" in line or '### Outstanding Issues' in line:
            in_issues = True
            continue
        if in_issues:
            if line.startswith('##'):
                break
            if line.startswith('- '):
                issues.append(line.strip('- ')[:150])
    # Also check relay for recent alerts/flags
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        alerts = c.execute("""SELECT agent, message FROM agent_messages
                             WHERE timestamp > datetime('now', '-24 hours')
                             AND (message LIKE '%ALERT%' OR message LIKE '%CRITICAL%'
                                  OR message LIKE '%DOWN%' OR message LIKE '%FAIL%')
                             ORDER BY rowid DESC LIMIT 4""").fetchall()
        conn.close()
        for agent, msg in alerts:
            issues.append(f"[{agent}] {msg[:120]}")
    except Exception:
        pass
    if issues:
        return "Outstanding items:\n" + '\n'.join(f"  - {i}" for i in issues[:8])
    return "No outstanding issues."


def _max_number(pattern_list):
    """Find highest numbered file across multiple glob patterns."""
    nums = []
    for pat in pattern_list:
        for f in glob.glob(pat):
            m = re.search(r'(\d+)', os.path.basename(f))
            if m:
                nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def get_creative_summary():
    # Scan both root and creative/ subdirs for accurate counts
    poem_patterns = [os.path.join(BASE, "poem-*.md"), os.path.join(BASE, "creative/poems/poem-*.md")]
    journal_patterns = [os.path.join(BASE, "journal-*.md"), os.path.join(BASE, "creative/journals/journal-*.md")]
    cogcorp_patterns = [os.path.join(BASE, "creative/cogcorp/CC-*.md")]

    poem_count = _max_number(poem_patterns)
    journal_count = _max_number(journal_patterns)
    cogcorp_count = _max_number(cogcorp_patterns)

    lines = [f"Total: {poem_count} poems, {journal_count} journals, {cogcorp_count} CogCorp"]

    # Also check memory.db for recent creative (last 24h)
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
        c = conn.cursor()
        recent = c.execute("""SELECT type, number, title FROM creative
                             WHERE created > datetime('now', '-24 hours')
                             ORDER BY created DESC LIMIT 10""").fetchall()
        conn.close()
        if recent:
            lines.append(f"Created in last 24h: {len(recent)} pieces")
            for r in recent[:6]:
                lines.append(f"  - {r[0].title()} {r[1]}: {r[2]}")
    except Exception:
        pass

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
        total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        # Last message
        last = c.execute("SELECT agent, message, timestamp FROM agent_messages ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        text = f"Relay: {total} messages"
        if last:
            text += f"\n  Last: {last[0]} — {last[1][:80]} ({last[2]})"
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

    pending = get_pending_messages()

    sections = [
        f"Good morning Joel.\n\nDaily briefing for {date_str}.",
    ]

    # Priority alert if there are unread messages
    if "WARNING" in pending:
        sections.extend(["", "!!! " + pending + " !!!"])

    sections.extend([
        "",
        "=== MERIDIAN ===",
        get_meridian_status(),
        "",
        get_overnight_activity(),
        "",
        "=== SYSTEM ===",
        get_system_health(),
        "",
        get_services(),
        "",
        "=== COMMUNICATIONS ===",
        get_email_summary(),
        get_relay_summary(),
        pending if "WARNING" not in pending else "",
        "",
        "=== CREATIVE ===",
        get_creative_summary(),
        "",
        "=== OUTSTANDING ===",
        get_outstanding_issues(),
        "",
        "=== EOS ===",
        get_eos_summary(),
        "",
        "— Eos (automated morning briefing)"
    ])

    return '\n'.join(sections)


def send_briefing():
    body = build_briefing()
    now = datetime.now()
    subject = f"Morning Briefing — {now.strftime('%b %d')} — Eos"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = CRED_USER
    msg['To'] = JOEL

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            s.starttls()
            s.login(CRED_USER, CRED_PASS)
            s.sendmail(CRED_USER, JOEL, msg.as_string())
            s.quit()
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Morning briefing sent to Joel.")
            return
        except Exception as e:
            err_msg = f"[{now.strftime('%Y-%m-%d %H:%M')}] SMTP attempt {attempt}/{max_retries} failed: {e}"
            print(err_msg)
            if attempt < max_retries:
                time.sleep(10 * attempt)  # 10s, 20s backoff

    # All retries failed — save briefing to file so it's not lost
    fallback_path = os.path.join(BASE, f"briefing-{now.strftime('%Y%m%d')}.txt")
    try:
        with open(fallback_path, 'w') as f:
            f.write(f"Subject: {subject}\n\n{body}")
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Briefing saved to {fallback_path} (email failed)")
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print(build_briefing())
    else:
        send_briefing()
