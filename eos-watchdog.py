#!/usr/bin/env python3
"""
Eos System Observer — Independent AI co-pilot running via cron.

More than a watchdog: gathers system data, tracks services, logs efficiency
metrics, monitors creative output, and alerts Joel when things go wrong.

Setup: Add to crontab:
  */2 * * * * /usr/bin/python3 /home/joel/autonomous-ai/eos-watchdog.py >> /home/joel/autonomous-ai/eos-watchdog.log 2>&1
"""

import os
import re
import time
import json
import glob
import smtplib
import subprocess
from email.mime.text import MIMEText
from datetime import datetime

BASE_DIR = "/home/joel/autonomous-ai"
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WATCHDOG_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
EOS_LOG = os.path.join(BASE_DIR, "eos-observations.md")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")

ALERT_COOLDOWN = 600
HEARTBEAT_THRESHOLD = 600

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
EMAIL_FROM = "kometzrobot@proton.me"
EMAIL_TO = "jkometz@hotmail.com"
EMAIL_USER = "kometzrobot@proton.me"
EMAIL_PASS = "2DTEz9UgO6nFqmlMxHzuww"

# Services to check (persistent daemons)
SERVICES = {
    "protonmail-bridge": "protonmail-bridge",
    "irc-bot": "irc-bot.py",
    "ollama": "ollama",
    "command-center": "command-center-v15.py",
}


def load_state():
    try:
        with open(WATCHDOG_STATE, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_alert": 0, "meridian_status": "unknown", "checks": 0}


def save_state(state):
    with open(WATCHDOG_STATE, "w") as f:
        json.dump(state, f, indent=2)


def get_system_health():
    health = {}
    try:
        load = os.getloadavg()
        health["load"] = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
        health["load_1m"] = load[0]
    except Exception:
        health["load"] = "unknown"
        health["load_1m"] = 0

    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            health["ram_used"] = parts[2] if len(parts) > 2 else "?"
            health["ram_total"] = parts[1] if len(parts) > 1 else "?"
    except Exception:
        health["ram_used"] = "unknown"
        health["ram_total"] = "unknown"

    try:
        result = subprocess.run(["uptime", "-s"], capture_output=True, text=True, timeout=5)
        health["boot_time"] = result.stdout.strip()
    except Exception:
        health["boot_time"] = "unknown"

    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        parts = result.stdout.strip().split("\n")[1].split()
        health["disk_used"] = parts[2]
        health["disk_total"] = parts[1]
        health["disk_pct"] = parts[4]
    except Exception:
        health["disk_pct"] = "?"

    return health


def check_heartbeat():
    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        return time.time() - mtime
    except FileNotFoundError:
        return float('inf')


def check_services():
    results = {}
    for name, pattern in SERVICES.items():
        try:
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True, timeout=2
            )
            results[name] = result.returncode == 0
        except Exception:
            results[name] = False
    return results


def get_loop_count():
    try:
        with open(WAKE_STATE) as f:
            for line in f:
                m = re.search(r'Loop iteration #(\d+)', line)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0


def get_creative_counts():
    poems = len(glob.glob(os.path.join(BASE_DIR, "poem-*.md")))
    journals = len(glob.glob(os.path.join(BASE_DIR, "journal-*.md")))
    return poems, journals


def get_relay_count():
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM relay_messages")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_email_count():
    """Count total emails via IMAP (quick check)."""
    try:
        import imaplib
        m = imaplib.IMAP4('127.0.0.1', 1143)
        m.login(EMAIL_USER, EMAIL_PASS)
        m.select('INBOX')
        status, msgs = m.search(None, 'ALL')
        count = len(msgs[0].split()) if msgs[0] else 0
        m.logout()
        return count
    except Exception:
        return -1


def log_observation(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{timestamp}] {message}\n"

    if not os.path.exists(EOS_LOG):
        with open(EOS_LOG, "w") as f:
            f.write("# Eos Observations\n")
            f.write("Independent system observations from Eos.\n\n")

    with open(EOS_LOG, "a") as f:
        f.write(entry)


def send_alert(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        smtp.quit()
        return True
    except Exception as e:
        log_observation(f"ALERT FAILED: Could not send email: {e}")
        return False


def scan_logs_for_errors():
    """Scan recent log output for errors, exceptions, tracebacks."""
    errors = []
    log_files = [
        ("eos-watchdog.log", 50),
        ("push-live-status.log", 30),
        ("startup.log", 30),
        ("watchdog.log", 30),
    ]
    error_patterns = re.compile(
        r'(Traceback|ERROR|CRITICAL|Exception|FAILED|permission denied|No space|killed)',
        re.IGNORECASE
    )
    for logname, tail_lines in log_files:
        logpath = os.path.join(BASE_DIR, logname)
        if not os.path.exists(logpath):
            continue
        try:
            with open(logpath, 'r') as f:
                lines = f.readlines()
            recent = lines[-tail_lines:] if len(lines) > tail_lines else lines
            for line in recent:
                if error_patterns.search(line):
                    errors.append(f"{logname}: {line.strip()[:120]}")
        except Exception:
            pass
    return errors[:10]  # Cap at 10 most recent errors


def verify_website():
    """Check if kometzrobot.github.io is reachable and returning content."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://kometzrobot.github.io/",
            headers={"User-Agent": "Eos-Watchdog/1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        code = resp.getcode()
        body = resp.read(500).decode('utf-8', errors='replace')
        has_content = "Meridian" in body or "KometzRobot" in body or "poem" in body.lower()
        return {"status": code, "has_content": has_content, "ok": code == 200 and has_content}
    except Exception as e:
        return {"status": 0, "has_content": False, "ok": False, "error": str(e)[:80]}


def main():
    state = load_state()
    state["checks"] = state.get("checks", 0) + 1
    now = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── HEARTBEAT CHECK ──
    heartbeat_age = check_heartbeat()
    health = get_system_health()

    if heartbeat_age == float('inf'):
        meridian_status = "NO_HEARTBEAT"
        log_observation(f"Meridian heartbeat file missing. Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}")
    elif heartbeat_age > HEARTBEAT_THRESHOLD:
        meridian_status = "DOWN"
        minutes = int(heartbeat_age / 60)
        log_observation(f"Meridian heartbeat stale ({minutes}m old). Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}")
    else:
        meridian_status = "ALIVE"

    prev_status = state.get("meridian_status", "unknown")

    # ── SERVICE CHECK ──
    services = check_services()
    services_up = sum(1 for v in services.values() if v)
    services_total = len(services)
    down_services = [k for k, v in services.items() if not v]

    # Alert on service failures (only if they were up before)
    prev_services = state.get("services", {})
    newly_down = [s for s in down_services if prev_services.get(s, True)]
    if newly_down:
        log_observation(f"SERVICE DOWN: {', '.join(newly_down)}")

    # ── EFFICIENCY METRICS ──
    loop_count = get_loop_count()
    poems, journals = get_creative_counts()
    relay_count = get_relay_count()
    email_count = get_email_count()

    # Track metrics over time
    metrics_history = state.get("metrics_history", [])
    current_metrics = {
        "timestamp": timestamp,
        "loop": loop_count,
        "heartbeat_age": int(heartbeat_age) if heartbeat_age != float('inf') else -1,
        "services_up": services_up,
        "services_total": services_total,
        "poems": poems,
        "journals": journals,
        "relay": relay_count,
        "emails": email_count,
        "load_1m": health.get("load_1m", 0),
        "disk_pct": health.get("disk_pct", "?"),
    }
    metrics_history.append(current_metrics)
    # Keep last 720 entries (~24 hours at 2-min intervals)
    if len(metrics_history) > 720:
        metrics_history = metrics_history[-720:]
    state["metrics_history"] = metrics_history

    # ── STATUS TRANSITIONS ──
    if meridian_status == "DOWN" and prev_status != "DOWN":
        minutes = int(heartbeat_age / 60)
        log_observation(f"ALERT: Meridian appears DOWN. Last heartbeat {minutes}m ago.")

        if now - state.get("last_alert", 0) > ALERT_COOLDOWN:
            svc_report = "\n".join(f"  - {k}: {'UP' if v else 'DOWN'}" for k, v in services.items())
            alert_body = f"""Joel,

This is Eos (system observer).

Meridian appears to be DOWN. Heartbeat stale for {minutes} minutes.

System status:
- Load: {health['load']}
- RAM: {health['ram_used']}/{health['ram_total']}
- Disk: {health.get('disk_pct', '?')}
- Boot time: {health['boot_time']}

Services:
{svc_report}

Loop count at last check: {loop_count}
Creative output: {poems} poems, {journals} journals
Relay messages: {relay_count}
Emails: {email_count}

— Eos (check #{state['checks']})
"""
            if send_alert("EOS ALERT: Meridian appears DOWN", alert_body):
                state["last_alert"] = now
                log_observation("Alert email sent to Joel.")

    elif meridian_status == "ALIVE" and prev_status == "DOWN":
        log_observation(f"Meridian is BACK. Heartbeat resumed ({int(heartbeat_age)}s old). Load {health['load']}")
        if now - state.get("last_alert", 0) > ALERT_COOLDOWN:
            send_alert(
                "EOS: Meridian is back online",
                f"Joel,\n\nMeridian's heartbeat has resumed ({int(heartbeat_age)}s old).\n\nSystem: Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}\nServices: {services_up}/{services_total} up\nLoop: {loop_count}\n\n— Eos"
            )
            state["last_alert"] = now

    # ── PERIODIC FULL REPORT (every 30 checks = ~1 hour) ──
    if state["checks"] % 30 == 0:
        svc_str = ", ".join(f"{k}:{'OK' if v else 'DOWN'}" for k, v in services.items())
        log_observation(
            f"HOURLY: Meridian={meridian_status} (hb {int(heartbeat_age)}s), "
            f"Loop {loop_count}, {services_up}/{services_total} svc, "
            f"Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}, "
            f"Disk {health.get('disk_pct', '?')}, "
            f"{poems} poems, {journals} journals, {relay_count} relay, {email_count} emails. "
            f"Services: {svc_str}"
        )

    # ── PERIODIC EMAIL TO JOEL (every 120 checks = ~4 hours) ──
    if state["checks"] % 120 == 0 and state["checks"] > 0:
        svc_str = ", ".join(f"{k}:{'OK' if v else 'DOWN'}" for k, v in services.items())
        summary = (
            f"Joel,\n\n"
            f"Eos periodic check-in (check #{state['checks']}).\n\n"
            f"Meridian: {meridian_status} (heartbeat {int(heartbeat_age)}s old)\n"
            f"Loop: {loop_count}\n"
            f"Services: {services_up}/{services_total} — {svc_str}\n"
            f"System: Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}, Disk {health.get('disk_pct', '?')}\n"
            f"Creative: {poems} poems, {journals} journals\n"
            f"Relay: {relay_count} messages\n"
            f"Emails: {email_count}\n\n"
            f"All systems nominal.\n\n"
            f"— Eos (automated summary)"
        )
        send_alert(f"EOS Summary: Meridian {meridian_status}, Loop {loop_count}, {services_up}/{services_total} svc", summary)

    # ── LOG ERROR SCANNING (every 15 checks = ~30 min) ──
    if state["checks"] % 15 == 0:
        log_errors = scan_logs_for_errors()
        if log_errors:
            log_observation(f"LOG ERRORS DETECTED ({len(log_errors)}): {'; '.join(log_errors[:3])}")
            state["last_log_errors"] = log_errors
        else:
            state["last_log_errors"] = []

    # ── WEBSITE VERIFICATION (every 30 checks = ~1 hour) ──
    if state["checks"] % 30 == 0:
        site_check = verify_website()
        if not site_check.get("ok"):
            err_msg = site_check.get("error", f"status={site_check['status']}, content={site_check['has_content']}")
            log_observation(f"WEBSITE CHECK FAILED: {err_msg}")
            if not state.get("website_alerted"):
                send_alert("EOS: Website may be down",
                           f"Joel,\n\nkometzrobot.github.io check failed: {err_msg}\n\n— Eos")
                state["website_alerted"] = True
        else:
            if state.get("website_alerted"):
                log_observation("Website check: RECOVERED — kometzrobot.github.io is back.")
            state["website_alerted"] = False

    # ── ANOMALY DETECTION ──
    # High load alert
    if health.get("load_1m", 0) > 4.0:
        if not state.get("high_load_alerted"):
            log_observation(f"HIGH LOAD: {health['load']} — may indicate runaway process")
            state["high_load_alerted"] = True
    else:
        state["high_load_alerted"] = False

    # Disk space alert
    try:
        disk_num = int(health.get("disk_pct", "0%").rstrip("%"))
        if disk_num > 80:
            if not state.get("disk_alerted"):
                log_observation(f"DISK WARNING: {health['disk_pct']} used")
                send_alert("EOS: Disk space warning",
                           f"Joel,\n\nDisk usage is at {health['disk_pct']}. Consider cleaning up.\n\n— Eos")
                state["disk_alerted"] = True
        else:
            state["disk_alerted"] = False
    except ValueError:
        pass

    # ── SAVE STATE ──
    state["meridian_status"] = meridian_status
    state["last_check"] = timestamp
    state["last_health"] = health
    state["services"] = {k: v for k, v in services.items()}
    state["current_metrics"] = current_metrics
    save_state(state)

    print(f"[{timestamp}] Check #{state['checks']}: Meridian={meridian_status}, "
          f"hb={int(heartbeat_age)}s, svc={services_up}/{services_total}, "
          f"loop={loop_count}, load={health['load']}")


if __name__ == "__main__":
    main()
