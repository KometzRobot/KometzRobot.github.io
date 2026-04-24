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
    # Process-based checks
    process_checks = {
        "Ollama": "ollama serve",
        "Hub v2": "hub-v2.py",
        "The Chorus": "the-chorus.py",
        "Cloudflare Tunnel": "cloudflared",
        "Soma": "symbiosense.py",
    }
    lines = []
    up = 0
    total = len(process_checks) + 1  # +1 for bridge port check

    # Proton Bridge — check port 1144, not systemd (runs inside desktop app)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(('127.0.0.1', 1144))
        s.close()
        if result == 0:
            lines.append("  Proton Bridge: UP (port 1144)")
            up += 1
        else:
            lines.append("  Proton Bridge: DOWN (port 1144 closed)")
    except Exception:
        lines.append("  Proton Bridge: ?")

    for name, pat in process_checks.items():
        try:
            r = subprocess.run(['pgrep', '-f', pat], capture_output=True, timeout=2)
            status = "UP" if r.returncode == 0 else "DOWN"
            if r.returncode == 0:
                up += 1
        except Exception:
            status = "?"
        lines.append(f"  {name}: {status}")
    return f"Services: {up}/{total} up\n" + '\n'.join(lines)


def _is_claude_running():
    """Check if a Claude process is actually running (distinguishes Meridian from Cinder holding)."""
    try:
        r = subprocess.run(["pgrep", "-f", "claude"], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


def get_meridian_status():
    lines = []
    # Heartbeat — Cinder also touches heartbeat when Meridian is down.
    # Fresh heartbeat alone doesn't mean Meridian (Claude) is running.
    try:
        hb_age = time.time() - os.path.getmtime(HB)
        claude_running = _is_claude_running()
        if hb_age < 300 and claude_running:
            lines.append(f"Meridian: ALIVE (heartbeat {int(hb_age)}s ago)")
        elif hb_age < 300 and not claude_running:
            lines.append(f"Meridian: DOWN — Cinder holding (heartbeat {int(hb_age)}s ago, no Claude process)")
        elif hb_age < 600:
            lines.append(f"Meridian: SLOW (heartbeat {int(hb_age)}s ago — missed cycle)")
        else:
            lines.append(f"Meridian: DOWN (heartbeat {int(hb_age/60):.0f}m ago — loop stopped)")
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
    # Recent relay activity — filter to meaningful messages only
    # Skip: Nova thinks, mood shifts, infra audits, cascade events, heartbeat noise
    SKIP_PATTERNS = ["nova thinks", "mood shift", "infra audit", "cascade", "nerve-event",
                     "heartbeat", "all systems nominal", "changes:", "grew by", "decreased by"]
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        rows = c.execute("""SELECT agent, message FROM agent_messages
                           WHERE timestamp > datetime('now', '-12 hours')
                           ORDER BY rowid DESC LIMIT 30""").fetchall()
        conn.close()
        meaningful = [
            (agent, msg) for agent, msg in rows
            if not any(p in msg.lower() for p in SKIP_PATTERNS)
        ]
        if meaningful:
            lines.append(f"Agent relay (meaningful, last 12h): {len(meaningful)} messages")
            for agent, msg in meaningful[:4]:
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
    """Pull outstanding directives + recent alerts."""
    issues = []
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        directives = c.execute("""SELECT directive, status FROM directives
                                  WHERE status NOT IN ('done', 'shelved')
                                  ORDER BY id""").fetchall()
        for d, s in directives:
            tag = f"[{s.upper()}]" if s != 'pending' else "[PENDING]"
            issues.append(f"{tag} {d[:100]}")
        alerts = c.execute("""SELECT agent, message FROM agent_messages
                             WHERE timestamp > datetime('now', '-24 hours')
                             AND (message LIKE '%ALERT%' OR message LIKE '%CRITICAL%'
                                  OR message LIKE '%DOWN%' OR message LIKE '%FAIL%')
                             ORDER BY rowid DESC LIMIT 3""").fetchall()
        conn.close()
        for agent, msg in alerts:
            issues.append(f"[ALERT:{agent}] {msg[:100]}")
    except Exception:
        pass
    handoff = read_file(os.path.join(BASE, ".loop-handoff.md"))
    for line in handoff.split('\n'):
        if '[!!!]' in line:
            issues.append(line.strip('- ').replace('[!!!]', '').strip()[:120])
    if issues:
        return "Outstanding items:\n" + '\n'.join(f"  - {i}" for i in issues[:12])
    return "No outstanding issues."


def _count_files(pattern_list):
    """Count actual files matching patterns (not highest number — avoids inflated counts)."""
    seen = set()
    for pat in pattern_list:
        for f in glob.glob(pat):
            seen.add(os.path.basename(f))
    return len(seen)


def get_creative_summary():
    # Scan both root and creative/ subdirs for accurate counts
    poem_patterns = [os.path.join(BASE, "poem-*.md"), os.path.join(BASE, "creative/poems/*.md")]
    journal_patterns = [os.path.join(BASE, "journal-*.md"), os.path.join(BASE, "creative/journals/*.md"), os.path.join(BASE, "creative/writing/journals/journal-*.md")]
    cogcorp_patterns = [os.path.join(BASE, "cogcorp-fiction/*.html"), os.path.join(BASE, "creative/cogcorp/CC-*.md"), os.path.join(BASE, "creative/cogcorp/*.md")]

    poem_count = _count_files(poem_patterns)
    journal_count = _count_files(journal_patterns)
    cogcorp_count = _count_files(cogcorp_patterns)

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
    """Relay summary — count only, no raw message content (too noisy for briefing)."""
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        today = c.execute("""SELECT COUNT(*) FROM agent_messages
                             WHERE timestamp > datetime('now', '-24 hours')""").fetchone()[0]
        conn.close()
        return f"Relay: {total} total messages, {today} in last 24h"
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


def get_upcoming_deadlines():
    """Check capsule for deadlines and known dates."""
    deadlines = []
    capsule = read_file(os.path.join(BASE, ".capsule.md"))
    now = datetime.now()
    # Known deadlines — add new ones here as they come up
    known = [
        ("2026-04-10", "NGC Fellowship ($15K CAD)"),
        ("2026-04-22", "LACMA Art+Tech Lab ($50K USD)"),
    ]
    for date_str, label in known:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            delta = (d - now).days
            if -1 <= delta <= 60:
                if delta < 0:
                    deadlines.append(f"  OVERDUE  {label}")
                elif delta == 0:
                    deadlines.append(f"  TODAY    {label}")
                elif delta <= 7:
                    deadlines.append(f"  {delta}d left  {label}")
                else:
                    deadlines.append(f"  {delta}d      {label}")
        except Exception:
            pass
    return deadlines


def build_briefing():
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    sep = "─" * 36

    pending = get_pending_messages()
    meridian = get_meridian_status()
    activity = get_overnight_activity()
    health = get_system_health()
    services = get_services()
    emails = get_email_summary()
    relay = get_relay_summary()
    creative = get_creative_summary()
    outstanding = get_outstanding_issues()
    eos = get_eos_summary()
    deadlines = get_upcoming_deadlines()

    sections = []
    sections.append(f"Good morning Joel.\n{date_str}\n{sep}")

    # ALERTS — anything urgent goes first
    alerts = []
    if "DOWN" in meridian:
        alerts.append(meridian)
    if "WARNING" in pending:
        alerts.append(pending)
    if outstanding and "No outstanding" not in outstanding:
        for line in outstanding.split('\n')[1:]:
            if 'DOWN' in line.upper() or 'FAIL' in line.upper() or 'CRITICAL' in line.upper():
                alerts.append(line.strip('- ').strip())
    if alerts:
        sections.append("!! ALERTS")
        for a in alerts[:4]:
            sections.append(f"  {a}")
        sections.append("")

    # DEADLINES — what's coming up
    if deadlines:
        sections.append("DEADLINES")
        sections.extend(deadlines)
        sections.append("")

    # MERIDIAN — loop status
    sections.append("MERIDIAN")
    for line in meridian.split('\n'):
        sections.append(f"  {line}")
    sections.append("")

    # SYSTEM — health + services, compact
    sections.append("SYSTEM")
    for line in health.split('\n'):
        sections.append(f"  {line}")
    for line in services.split('\n'):
        sections.append(f"  {line}")
    sections.append("")

    # OVERNIGHT — what happened
    if activity and "No recent activity" not in activity:
        sections.append("OVERNIGHT")
        for line in activity.split('\n'):
            sections.append(f"  {line}")
        sections.append("")

    # COMMS — email + relay + dashboard
    sections.append("COMMS")
    sections.append(f"  {emails}")
    sections.append(f"  {relay}")
    if "WARNING" not in pending and pending:
        sections.append(f"  {pending}")
    sections.append("")

    # CREATIVE — output summary
    sections.append("CREATIVE")
    for line in creative.split('\n'):
        sections.append(f"  {line}")
    sections.append("")

    # EOS — my own observations
    if eos:
        sections.append("EOS")
        for line in eos.split('\n'):
            sections.append(f"  {line}")
        sections.append("")

    # OUTSTANDING — things that need attention
    if outstanding and "No outstanding" not in outstanding:
        sections.append("OUTSTANDING")
        for line in outstanding.split('\n'):
            if line.strip():
                sections.append(f"  {line.strip('- ').strip()[:120]}")
        sections.append("")

    sections.append(sep)
    sections.append("-- Eos")

    return '\n'.join(sections)


def format_html_briefing(plain_body):
    """Convert plain text briefing to clean HTML for phone reading."""
    lines = plain_body.split('\n')
    html_parts = []
    html_parts.append("""<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#111;color:#eee;padding:16px;margin:0;font-size:15px;line-height:1.5;">""")

    section_colors = {
        '!! ALERTS': '#ff4444',
        'DEADLINES': '#ff9800',
        'MERIDIAN': '#4ecdc4',
        'SYSTEM': '#888',
        'OVERNIGHT': '#64b5f6',
        'COMMS': '#ab47bc',
        'CREATIVE': '#ffb74d',
        'EOS': '#81c784',
        'OUTSTANDING': '#ef5350',
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_parts.append('<div style="height:8px;"></div>')
            continue

        # Header line (greeting)
        if stripped.startswith('Good morning'):
            html_parts.append(f'<div style="font-size:18px;font-weight:700;margin-bottom:4px;">{stripped}</div>')
            continue

        # Date line
        if any(day in stripped for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
            html_parts.append(f'<div style="color:#888;font-size:13px;margin-bottom:12px;">{stripped}</div>')
            continue

        # Separator
        if stripped.startswith('─'):
            html_parts.append('<hr style="border:none;border-top:1px solid #333;margin:12px 0;">')
            continue

        # Section headers
        matched_section = False
        for section, color in section_colors.items():
            if stripped == section:
                html_parts.append(f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:{color};margin-top:16px;margin-bottom:6px;border-bottom:1px solid {color}33;padding-bottom:4px;">{stripped}</div>')
                matched_section = True
                break
        if matched_section:
            continue

        # Alert items
        if any(kw in stripped.upper() for kw in ['DOWN', 'CRITICAL', 'FAIL', 'OVERDUE', 'TODAY']):
            html_parts.append(f'<div style="color:#ff6b6b;font-weight:600;padding:4px 8px;background:#ff6b6b11;border-radius:4px;margin:2px 0;">{stripped}</div>')
            continue

        # Signature
        if stripped == '-- Eos':
            html_parts.append(f'<div style="color:#666;font-size:12px;margin-top:12px;">{stripped}</div>')
            continue

        # Normal content
        html_parts.append(f'<div style="color:#ccc;padding:1px 0;">{stripped}</div>')

    html_parts.append('</body></html>')
    return '\n'.join(html_parts)


def send_briefing():
    body = build_briefing()
    now = datetime.now()
    subject = f"Morning Briefing — {now.strftime('%b %d')} — Eos"

    html_body = format_html_briefing(body)
    msg = MIMEText(html_body, 'html')
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


SENTINEL_DIR = os.path.join(BASE, "logs")


def sentinel_path():
    return os.path.join(SENTINEL_DIR, f".briefing-sent-{datetime.now().strftime('%Y-%m-%d')}")


def already_sent_today():
    """Check if briefing was already sent today via sentinel file."""
    return os.path.exists(sentinel_path())


def mark_sent_today():
    """Write sentinel file so duplicate prevention works across all call paths."""
    try:
        with open(sentinel_path(), 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M"))
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print(build_briefing())
    elif len(sys.argv) > 1 and sys.argv[1] == "force":
        if already_sent_today():
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Briefing already sent today (force blocked by sentinel) — skipping.")
        else:
            send_briefing()
            mark_sent_today()
    else:
        if already_sent_today():
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Briefing already sent today — skipping.")
        else:
            send_briefing()
            mark_sent_today()
