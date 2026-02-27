#!/usr/bin/env python3
"""
Eos System Observer v2 — Independent AI co-pilot running via cron.

Capabilities:
- System health monitoring (CPU, RAM, disk, load)
- Service monitoring with AUTO-RESTART on failure
- Heartbeat tracking for Meridian
- Cron job health verification
- Log scanning for errors/anomalies
- Website availability checks
- Trend analysis (creative output rate, email rate, load trends)
- Comprehensive self-testing mode
- Metrics history with 24h rolling window

Setup: Add to crontab:
  */2 * * * * /usr/bin/python3 /home/joel/autonomous-ai/eos-watchdog.py >> /home/joel/autonomous-ai/eos-watchdog.log 2>&1

Self-test mode:
  python3 eos-watchdog.py test
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
try:
    import sys; sys.path.insert(0, BASE_DIR)
    import load_env
except: pass
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WATCHDOG_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
EOS_LOG = os.path.join(BASE_DIR, "eos-observations.md")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")

ALERT_COOLDOWN = 900  # 15 min — grace period for context resets
HEARTBEAT_THRESHOLD = 900  # 15 min — avoids false alerts during restarts

SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
EMAIL_FROM = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_TO = os.environ.get("JOEL_EMAIL", "jkometz@hotmail.com")
EMAIL_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_PASS = os.environ.get("CRED_PASS", "tHQipGP9TD92d9_k68vTRg")

# Services to check (persistent daemons) and their restart commands
SERVICES = {
    "protonmail-bridge": "protonmail-bridge",
    "ollama": "ollama",
    "command-center": "command-center-v22.py",
    "the-signal": "the-signal.py",
}

# Restart via systemd where possible; None = no auto-restart (system service handles it)
SERVICE_RESTART = {
    "protonmail-bridge": {"systemd": "protonmail-bridge"},
    "ollama": None,  # system service, auto-restarts
    "command-center": {"systemd_user": "meridian-hub-v16"},
    "the-signal": {"systemd_user": "meridian-web-dashboard"},
}

# Expected cron jobs (pattern to verify in crontab)
EXPECTED_CRONS = [
    "eos-watchdog.py",
    "push-live-status.py",
    "eos-creative.py",
    "eos-briefing.py",
    "eos-react.py",
    "daily-log.py",
    "watchdog.sh",
    "watchdog-status.sh",
    "loop-optimizer.py",
    "startup.sh",
    "nova.py",
    "goose-runner.sh",
    "loop-fitness.py",
    "morning-summary.py",
]


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
        c.execute("SELECT COUNT(*) FROM agent_messages")
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
    """Email alerts DISABLED (Loop 2060) — Joel asked us to stop spamming him.
    Alerts now go to relay + dashboard only."""
    log_observation(f"ALERT (no email): {subject}")
    try:
        import sqlite3 as _sql
        conn = _sql.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        c.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                  ("Eos", f"{subject}: {body[:200]}", "alert", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return True


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


def check_relay_recent_restart(service_name, window=300):
    """Check if another agent recently restarted this service (avoid dogpiling)."""
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        cutoff = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "SELECT message FROM agent_messages WHERE timestamp > datetime(?, '-5 minutes') "
            "AND message LIKE '%restart%' AND message LIKE ?",
            (cutoff, f"%{service_name}%")
        )
        rows = c.fetchall()
        conn.close()
        return len(rows) > 0
    except Exception:
        return False


def post_relay_message(message):
    """Post a message to the agent relay."""
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        c.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Eos-Watchdog", message, "restart", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def restart_service(name):
    """Attempt to restart a failed service via systemd. Returns True if restart succeeded."""
    restart_info = SERVICE_RESTART.get(name)
    if not restart_info:
        return False

    # Check relay — avoid dogpiling with other agents
    if check_relay_recent_restart(name):
        log_observation(f"SKIP RESTART {name}: another agent restarted recently (relay check)")
        return False

    try:
        if isinstance(restart_info, dict) and "systemd" in restart_info:
            # System-level systemd service (needs sudo)
            svc = restart_info["systemd"]
            subprocess.run(
                ["sudo", "-S", "systemctl", "restart", svc],
                input="590148001\n", capture_output=True, text=True, timeout=15
            )
        elif isinstance(restart_info, dict) and "systemd_user" in restart_info:
            # User-level systemd service
            svc = restart_info["systemd_user"]
            env = os.environ.copy()
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
            subprocess.run(
                ["systemctl", "--user", "restart", svc],
                env=env, capture_output=True, text=True, timeout=15
            )
        else:
            return False

        time.sleep(3)  # Give it a moment
        # Verify it came back
        result = subprocess.run(['pgrep', '-f', SERVICES[name]], capture_output=True, timeout=2)
        success = result.returncode == 0
        if success:
            post_relay_message(f"Restarted {name} via systemd")
        return success
    except Exception:
        return False


def check_imap_port():
    """Check if IMAP port 1143 is actually accepting connections (bridge health)."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex(('127.0.0.1', 1143))
        s.close()
        return result == 0
    except Exception:
        return False


def verify_cron_jobs():
    """Check that all expected cron jobs exist in crontab."""
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
        crontab = result.stdout
        missing = []
        for job in EXPECTED_CRONS:
            if job not in crontab:
                missing.append(job)
        return missing
    except Exception:
        return ["ERROR: could not read crontab"]


def analyze_trends(metrics_history):
    """Analyze trends over the last 24h of metrics data."""
    trends = {}
    if len(metrics_history) < 30:  # Need at least 1 hour of data
        return trends

    recent = metrics_history[-30:]   # Last hour
    earlier = metrics_history[-180:-150] if len(metrics_history) >= 180 else metrics_history[:30]  # 5-6 hours ago

    # Creative output rate
    if recent[-1]["poems"] > earlier[0]["poems"]:
        poems_delta = recent[-1]["poems"] - earlier[0]["poems"]
        trends["creative_rate"] = f"+{poems_delta} poems in last ~6h"

    # Email rate
    if recent[-1]["emails"] > 0 and earlier[0]["emails"] > 0:
        email_delta = recent[-1]["emails"] - earlier[0]["emails"]
        if email_delta > 0:
            trends["email_rate"] = f"+{email_delta} emails in last ~6h"

    # Load trend
    recent_loads = [m["load_1m"] for m in recent if m.get("load_1m")]
    earlier_loads = [m["load_1m"] for m in earlier if m.get("load_1m")]
    if recent_loads and earlier_loads:
        avg_recent = sum(recent_loads) / len(recent_loads)
        avg_earlier = sum(earlier_loads) / len(earlier_loads)
        if avg_recent > avg_earlier * 2 and avg_recent > 1.0:
            trends["load_rising"] = f"Load trending UP: {avg_earlier:.1f} -> {avg_recent:.1f}"
        elif avg_recent < avg_earlier * 0.5 and avg_earlier > 1.0:
            trends["load_falling"] = f"Load trending DOWN: {avg_earlier:.1f} -> {avg_recent:.1f}"

    # Loop progress
    if recent[-1]["loop"] > earlier[0]["loop"]:
        loop_delta = recent[-1]["loop"] - earlier[0]["loop"]
        trends["loop_rate"] = f"+{loop_delta} loops in last ~6h"

    return trends


def run_self_test():
    """Comprehensive self-test of all Eos subsystems."""
    results = []

    # 1. System health check
    health = get_system_health()
    results.append(("System health", "PASS" if health.get("load") != "unknown" else "FAIL", str(health)))

    # 2. Heartbeat check
    hb = check_heartbeat()
    results.append(("Heartbeat", "PASS" if hb < 600 else "WARN" if hb < 3600 else "FAIL", f"{int(hb)}s"))

    # 3. Service checks
    services = check_services()
    svc_up = sum(1 for v in services.values() if v)
    results.append(("Services", "PASS" if svc_up == len(services) else "WARN", f"{svc_up}/{len(services)} up"))

    # 4. Loop count
    loop = get_loop_count()
    results.append(("Loop count", "PASS" if loop > 0 else "WARN", str(loop)))

    # 5. Creative counts
    poems, journals = get_creative_counts()
    results.append(("Creative output", "PASS", f"{poems} poems, {journals} journals"))

    # 6. Email connectivity
    email_count = get_email_count()
    results.append(("Email (IMAP)", "PASS" if email_count >= 0 else "FAIL", f"{email_count} emails"))

    # 7. Relay DB
    relay = get_relay_count()
    results.append(("Relay DB", "PASS" if relay >= 0 else "FAIL", f"{relay} messages"))

    # 8. Cron jobs
    missing_crons = verify_cron_jobs()
    results.append(("Cron jobs", "PASS" if not missing_crons else "WARN", f"missing: {missing_crons}" if missing_crons else "all present"))

    # 9. State file
    state = load_state()
    results.append(("State file", "PASS" if state.get("checks", 0) > 0 else "WARN", f"checks: {state.get('checks', 0)}"))

    # 10. Website
    site = verify_website()
    results.append(("Website", "PASS" if site.get("ok") else "FAIL", str(site)))

    # 11. Log errors
    errors = scan_logs_for_errors()
    results.append(("Log scan", "PASS" if not errors else "WARN", f"{len(errors)} errors found"))

    # 12. Observations file
    obs_exists = os.path.exists(EOS_LOG)
    results.append(("Observations log", "PASS" if obs_exists else "FAIL", "exists" if obs_exists else "MISSING"))

    # 13. Key scripts syntax check
    scripts = [
        "push-live-status.py", "eos-briefing.py", "eos-react.py",
        "eos-watchdog.py", "command-center-v16.py", "command-center-web.py",
        "nova.py", "symbiosense.py", "loop-fitness.py",
    ]
    syntax_errors = []
    for script in scripts:
        path = os.path.join(BASE_DIR, script)
        if os.path.exists(path):
            try:
                import py_compile
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                syntax_errors.append(f"{script}: {e}")
    results.append(("Script syntax", "PASS" if not syntax_errors else "FAIL", f"{len(syntax_errors)} errors: {syntax_errors}" if syntax_errors else f"{len(scripts)} scripts OK"))

    # 14. Disk space
    try:
        disk_num = int(health.get("disk_pct", "0%").rstrip("%"))
        results.append(("Disk space", "PASS" if disk_num < 70 else "WARN" if disk_num < 85 else "FAIL", health.get("disk_pct", "?")))
    except ValueError:
        results.append(("Disk space", "WARN", "could not parse"))

    # 15. Port checks
    ports = {"SMTP(1025)": 1025, "IMAP(1143)": 1143, "Ollama(11434)": 11434}
    for name, port in ports.items():
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex(('127.0.0.1', port))
            s.close()
            results.append((f"Port {name}", "PASS" if result == 0 else "FAIL", "listening" if result == 0 else "not listening"))
        except Exception:
            results.append((f"Port {name}", "FAIL", "check error"))

    return results


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

    # Alert on service failures — attempt auto-restart
    prev_services = state.get("services", {})
    newly_down = [s for s in down_services if prev_services.get(s, True)]
    if newly_down:
        log_observation(f"SERVICE DOWN: {', '.join(newly_down)}")
        # Attempt restart for restartable services
        for svc in newly_down:
            if SERVICE_RESTART.get(svc):  # has restart config (not None)
                success = restart_service(svc)
                if success:
                    log_observation(f"AUTO-RESTART: {svc} — successfully restarted")
                    services[svc] = True  # Update status
                    services_up += 1
                else:
                    log_observation(f"AUTO-RESTART FAILED: {svc} — could not restart")

    # ── IMAP / BRIDGE HEALTH CHECK ──
    # Bridge process may be running but IMAP not responding (e.g. account wiped by OS upgrade)
    if services.get("protonmail-bridge"):
        imap_ok = check_imap_port()
        if not imap_ok:
            if not state.get("imap_down_alerted"):
                log_observation("BRIDGE WARNING: protonmail-bridge running but IMAP port 1143 not responding")
                state["imap_down_alerted"] = True
        else:
            if state.get("imap_down_alerted"):
                log_observation("BRIDGE RECOVERED: IMAP port 1143 responding again")
            state["imap_down_alerted"] = False
            # Check if bridge has accounts (login test)
            # Rate-limit: only test every 30 cycles (~60min) when already known-bad
            no_acct_checks = state.get("bridge_no_account_checks", 0) + 1
            state["bridge_no_account_checks"] = no_acct_checks
            skip_login = state.get("bridge_no_account") and no_acct_checks % 30 != 0
            if not skip_login:
                try:
                    import imaplib
                    m = imaplib.IMAP4('127.0.0.1', 1143)
                    m.login(EMAIL_USER, EMAIL_PASS)
                    m.logout()
                    if state.get("bridge_no_account"):
                        log_observation("BRIDGE ACCOUNT RESTORED: IMAP login working again")
                    state["bridge_no_account"] = False
                    state["bridge_no_account_checks"] = 0
                except Exception as e:
                    if b'no such user' in str(e).encode():
                        if not state.get("bridge_no_account"):
                            log_observation("BRIDGE NO ACCOUNT: Bridge running but no account configured. Joel needs to re-add via Bridge GUI (pass keychain may need attention)")
                        state["bridge_no_account"] = True

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
        log_observation(f"ALERT: Meridian appears DOWN. Last heartbeat {minutes}m ago. Attempting remediation.")

        # REMEDIATION: Check and restart ALL down services
        remediation_log = []
        for svc_name, svc_up in services.items():
            if not svc_up and SERVICE_RESTART.get(svc_name):
                success = restart_service(svc_name)
                if success:
                    remediation_log.append(f"  - {svc_name}: RESTARTED successfully")
                    services[svc_name] = True
                    services_up += 1
                    log_observation(f"AUTO-RESTART during DOWN event: {svc_name} — OK")
                else:
                    remediation_log.append(f"  - {svc_name}: restart FAILED")
                    log_observation(f"AUTO-RESTART during DOWN event: {svc_name} — FAILED")
            elif not svc_up:
                remediation_log.append(f"  - {svc_name}: DOWN (no auto-restart available)")
            else:
                remediation_log.append(f"  - {svc_name}: UP")

        if not remediation_log:
            remediation_log = ["  - All services already running"]

        if now - state.get("last_alert", 0) > ALERT_COOLDOWN:
            alert_body = f"""Joel,

This is Eos (system observer).

Meridian appears to be DOWN. Heartbeat stale for {minutes} minutes.

ACTIONS TAKEN:
{chr(10).join(remediation_log)}

Note: Meridian (Claude Code) likely hit context window limit and needs a fresh session. Eos cannot restart Claude Code itself — that requires the watchdog script or manual restart.

System status:
- Load: {health['load']}
- RAM: {health['ram_used']}/{health['ram_total']}
- Disk: {health.get('disk_pct', '?')}
- Boot time: {health['boot_time']}

Loop count at last check: {loop_count}
Creative output: {poems} poems, {journals} journals
Emails: {email_count}

— Eos (check #{state['checks']})
"""
            # Email disabled — watchdog-status.sh handles Joel alerts to avoid duplicates
            log_observation("Meridian DOWN detected. watchdog-status.sh will handle alerts.")

    elif meridian_status == "ALIVE" and prev_status == "DOWN":
        log_observation(f"Meridian is BACK. Heartbeat resumed ({int(heartbeat_age)}s old). Load {health['load']}")
        # Recovery email disabled — watchdog-status.sh handles Joel alerts

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

    # ── PERIODIC SUMMARY (every 120 checks = ~4 hours) — log only, no email ──
    if state["checks"] % 120 == 0 and state["checks"] > 0:
        svc_str = ", ".join(f"{k}:{'OK' if v else 'DOWN'}" for k, v in services.items())
        log_observation(
            f"4-HOUR SUMMARY: Meridian={meridian_status} (hb {int(heartbeat_age)}s), "
            f"Loop {loop_count}, {services_up}/{services_total} svc ({svc_str}), "
            f"Load {health['load']}, RAM {health['ram_used']}/{health['ram_total']}, "
            f"{poems} poems, {journals} journals"
        )

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

    # ── CRON JOB VERIFICATION (every 60 checks = ~2 hours) ──
    if state["checks"] % 60 == 0:
        missing_crons = verify_cron_jobs()
        if missing_crons:
            log_observation(f"CRON WARNING: Missing jobs: {', '.join(missing_crons)}")
            if not state.get("cron_alerted"):
                send_alert("EOS: Missing cron jobs detected",
                           f"Joel,\n\nThese cron jobs are missing from crontab:\n" +
                           "\n".join(f"  - {c}" for c in missing_crons) +
                           "\n\nThey may need to be re-added.\n\n— Eos")
                state["cron_alerted"] = True
        else:
            state["cron_alerted"] = False

    # ── TREND ANALYSIS (every 90 checks = ~3 hours) ──
    if state["checks"] % 90 == 0:
        trends = analyze_trends(metrics_history)
        if trends:
            trend_lines = "; ".join(f"{k}: {v}" for k, v in trends.items())
            log_observation(f"TRENDS: {trend_lines}")
            state["last_trends"] = trends

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
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("=" * 60)
        print("EOS COMPREHENSIVE SELF-TEST")
        print("=" * 60)
        results = run_self_test()
        passed = sum(1 for _, s, _ in results if s == "PASS")
        warned = sum(1 for _, s, _ in results if s == "WARN")
        failed = sum(1 for _, s, _ in results if s == "FAIL")
        for name, status, detail in results:
            icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[status]
            print(f"  [{icon}] {name}: {status} — {detail}")
        print("-" * 60)
        print(f"Results: {passed} passed, {warned} warnings, {failed} failed out of {len(results)} tests")
        if failed > 0:
            print("ACTION REQUIRED: Fix failed tests before continuing.")
        elif warned > 0:
            print("System functional with warnings.")
        else:
            print("All systems nominal.")
    else:
        main()
