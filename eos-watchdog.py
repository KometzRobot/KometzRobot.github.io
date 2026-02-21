#!/usr/bin/env python3
"""
Eos Watchdog — Independent monitor that runs via cron.
Checks Meridian's heartbeat, system health, and alerts Joel if something is wrong.

Setup: Add to crontab:
  */2 * * * * /usr/bin/python3 /home/joel/autonomous-ai/eos-watchdog.py >> /home/joel/autonomous-ai/eos-watchdog.log 2>&1
"""

import os
import time
import json
import smtplib
import urllib.request
import subprocess
from email.mime.text import MIMEText
from datetime import datetime

HEARTBEAT_FILE = "/home/joel/autonomous-ai/.heartbeat"
WATCHDOG_STATE = "/home/joel/autonomous-ai/.eos-watchdog-state.json"
EOS_LOG = "/home/joel/autonomous-ai/eos-observations.md"
ALERT_COOLDOWN = 600  # Don't re-alert within 10 minutes
HEARTBEAT_THRESHOLD = 600  # Alert if heartbeat older than 10 minutes

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
EMAIL_FROM = "kometzrobot@proton.me"
EMAIL_TO = "jkometz@hotmail.com"
EMAIL_USER = "kometzrobot@proton.me"
EMAIL_PASS = "2DTEz9UgO6nFqmlMxHzuww"

OLLAMA_URL = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"


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
    except Exception:
        health["load"] = "unknown"

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

    return health


def check_heartbeat():
    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        age = time.time() - mtime
        return age
    except FileNotFoundError:
        return float('inf')


def log_observation(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{timestamp}] {message}\n"

    # Create file with header if it doesn't exist
    if not os.path.exists(EOS_LOG):
        with open(EOS_LOG, "w") as f:
            f.write("# Eos Observations\n")
            f.write("Independent system observations from Eos watchdog.\n\n")

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


def query_eos_brief(prompt):
    """Quick query to Eos for a brief observation."""
    try:
        data = json.dumps({
            "model": EOS_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 100}
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception:
        return None


def main():
    state = load_state()
    state["checks"] = state.get("checks", 0) + 1
    now = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check heartbeat
    heartbeat_age = check_heartbeat()
    health = get_system_health()

    if heartbeat_age == float('inf'):
        meridian_status = "NO_HEARTBEAT"
        log_observation(f"Meridian heartbeat file missing. System health: load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}")
    elif heartbeat_age > HEARTBEAT_THRESHOLD:
        meridian_status = "DOWN"
        minutes = int(heartbeat_age / 60)
        log_observation(f"Meridian heartbeat stale ({minutes}m old). Possible crash/freeze. Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}")
    else:
        meridian_status = "ALIVE"

    prev_status = state.get("meridian_status", "unknown")

    # Detect transitions
    if meridian_status == "DOWN" and prev_status != "DOWN":
        # Meridian just went down
        minutes = int(heartbeat_age / 60)
        log_observation(f"ALERT: Meridian appears DOWN. Last heartbeat {minutes}m ago.")

        if now - state.get("last_alert", 0) > ALERT_COOLDOWN:
            alert_body = f"""Joel,

This is Eos (automated watchdog).

Meridian appears to be DOWN. His heartbeat file hasn't been updated in {minutes} minutes.

System status:
- Load: {health['load']}
- RAM: {health['ram_used']}/{health['ram_total']}
- Boot time: {health['boot_time']}

This could mean:
- Context window filled and session ended
- Process crashed
- System reboot in progress

I'll keep monitoring and log observations for when Meridian restarts.

— Eos (watchdog check #{state['checks']})
"""
            if send_alert("EOS ALERT: Meridian appears DOWN", alert_body):
                state["last_alert"] = now
                log_observation("Alert email sent to Joel.")

    elif meridian_status == "ALIVE" and prev_status == "DOWN":
        # Meridian recovered
        log_observation(f"Meridian is BACK. Heartbeat resumed ({int(heartbeat_age)}s old). Load {health['load']}")

        if now - state.get("last_alert", 0) > ALERT_COOLDOWN:
            send_alert(
                "EOS: Meridian is back online",
                f"Joel,\n\nMeridian's heartbeat has resumed. He appears to be back online.\n\nSystem: Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}\n\n— Eos"
            )
            state["last_alert"] = now

    # Periodic health log (every 30 checks = ~1 hour)
    if state["checks"] % 30 == 0:
        log_observation(f"Hourly check: Meridian {meridian_status}, Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}, Boot {health['boot_time']}")

    state["meridian_status"] = meridian_status
    state["last_check"] = timestamp
    state["last_health"] = health
    save_state(state)

    print(f"[{timestamp}] Check #{state['checks']}: Meridian={meridian_status}, heartbeat_age={int(heartbeat_age)}s, load={health['load']}")


if __name__ == "__main__":
    main()
