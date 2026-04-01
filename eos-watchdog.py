#!/usr/bin/env python3
"""
Eos System Observer v3 — Independent AI co-pilot running via cron.

Capabilities:
- System health monitoring (CPU, RAM, disk, load)
- Service monitoring with AUTO-RESTART on failure
- Heartbeat tracking for Meridian
- Cron job health verification
- Log scanning for errors/anomalies
- Website availability checks
- Inner world health (emotion engine, psyche, soma, body state)
- Cascade flood detection
- Memory DB integrity checks
- Fitness score tracking
- Log file size monitoring (prevent bloat)
- Git push health verification
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
from datetime import datetime, timezone

def _utcnow_str():
    """UTC timestamp string for relay consistency."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

BASE_DIR = "/home/joel/autonomous-ai"
try:
    import sys; sys.path.insert(0, BASE_DIR)
    import load_env
except: pass
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WATCHDOG_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
EOS_LOG = os.path.join(BASE_DIR, "eos-observations.md")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
RELAY_DB = os.path.join(BASE_DIR, "agent-relay.db")

ALERT_COOLDOWN = 900  # 15 min — grace period for context resets
HEARTBEAT_THRESHOLD = 900  # 15 min — avoids false alerts during restarts

SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1026"))
EMAIL_FROM = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_TO = os.environ.get("JOEL_EMAIL", "jkometz@hotmail.com")
EMAIL_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_PASS = os.environ.get("CRED_PASS", "")

# Services to check (persistent daemons) and their restart commands
SERVICES = {
    "protonmail-bridge": "protonmail-bridge",
    "ollama": "ollama",
    "hub-v2": "hub-v2.py",
}

# Restart via systemd where possible; None = no auto-restart (system service handles it)
# Bridge restart RE-ENABLED Loop 2121+ with smart rate limiting (Joel: "why didnt EOS or someone try to restart the proton bridge?")
SERVICE_RESTART = {
    "protonmail-bridge": {"command": "bridge_smart_restart"},  # Smart restart with rate limit
    "ollama": None,  # system service, auto-restarts
    "hub-v2": {"systemd_user": "meridian-hub-v2"},
}

# Bridge smart restart: max 3 attempts per hour, 5-minute cooldown between attempts
BRIDGE_RESTART_MAX = 3
BRIDGE_RESTART_COOLDOWN = 300  # 5 minutes

# Expected cron jobs (pattern to verify in crontab — updated Loop 2127)
EXPECTED_CRONS = [
    "eos-watchdog.py",
    "push-live-status.py",
    "eos-creative.py",
    "eos-briefing.py",
    "eos-react.py",
    "watchdog.sh",
    "watchdog-status.sh",
    "loop-optimizer.py",
    "startup.sh",
    "nova.py",
    "goose-runner.sh",
    "loop-fitness.py",
    "supabase-sync.py",
    "hermes-bridge.py",
]

# Log files to monitor for size (prevent bloat — max 5MB each)
LOG_SIZE_LIMIT = 5 * 1024 * 1024  # 5MB
MONITORED_LOGS = [
    "eos-watchdog.log", "push-live-status.log", "watchdog.log",
    "nova.log", "goose-runner.log", "loop-fitness.log",
    "eos-briefing.log", "eos-react.log", "eos-creative.log",
    "loop-optimizer.log", "supabase-sync.log", "hermes-bridge.log",
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
    import socket
    results = {}
    for name, pattern in SERVICES.items():
        if name == "protonmail-bridge":
            # pgrep -f "protonmail-bridge" fails: binary is proton-bridge, not protonmail-bridge
            # Use port 1144 socket check instead (fixed Loop 3200)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect(("127.0.0.1", 1144))
                s.close()
                results[name] = True
            except Exception:
                results[name] = False
        else:
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
    """Read loop count from .loop-count file first, fall back to wake-state.md."""
    try:
        with open(os.path.join(BASE_DIR, ".loop-count")) as f:
            return int(f.read().strip())
    except Exception:
        pass
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
    """Count actual creative files across root and creative/ subdirs."""
    poem_patterns = [os.path.join(BASE_DIR, "poem-*.md"), os.path.join(BASE_DIR, "creative/poems/poem-*.md")]
    journal_patterns = [os.path.join(BASE_DIR, "journal-*.md"), os.path.join(BASE_DIR, "creative/journals/journal-*.md")]
    poems = len(set(os.path.basename(f) for pat in poem_patterns for f in glob.glob(pat)))
    journals = len(set(os.path.basename(f) for pat in journal_patterns for f in glob.glob(pat)))
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
        m = imaplib.IMAP4('127.0.0.1', 1144)
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


def _log_structured_error(error_type, description, category=None):
    """Log error to memory.db via error_logger (structured, queryable, deduped)."""
    try:
        import error_logger
        error_logger.log_error(error_type, description, agent="Eos",
                               category=category)
    except ImportError:
        pass
    except Exception:
        pass


def send_alert(subject, body):
    """Email alerts DISABLED (Loop 2060) — Joel asked us to stop spamming him.
    Alerts now go to relay + dashboard + context flags only."""
    log_observation(f"ALERT (no email): {subject}")
    try:
        import sqlite3 as _sql
        conn = _sql.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        c.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                  ("Eos", f"{subject}: {body[:200]}", "alert", _utcnow_str()))
        conn.commit()
        conn.close()
    except Exception:
        pass
    # Also flag for next Meridian handoff
    try:
        from context_flag import flag
        flag("Eos", f"{subject}: {body[:150]}", priority=2)
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
        ("nova.log", 30),
        ("goose-runner.log", 30),
        ("loop-fitness.log", 30),
        ("eos-briefing.log", 30),
        ("supabase-sync.log", 20),
        ("hermes-bridge.log", 20),
    ]
    error_patterns = re.compile(
        r'(Traceback|ERROR|CRITICAL|Exception|FAILED|permission denied|No space|killed|OperationalError)',
        re.IGNORECASE
    )
    # Exclude patterns that are just reporting about errors (not actual errors)
    exclude_patterns = re.compile(
        r'(error_rate|check_agent_error|errors found|LOG ERRORS)',
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
                if error_patterns.search(line) and not exclude_patterns.search(line):
                    errors.append(f"{logname}: {line.strip()[:120]}")
        except Exception:
            pass
    return errors[:10]  # Cap at 10 most recent errors


def _read_json_safe(filepath):
    """Read a JSON file safely, return None on failure."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def check_inner_world_health():
    """Check health of inner world systems (emotion engine, psyche, soma, body)."""
    issues = []

    # Emotion engine state
    emo = _read_json_safe(os.path.join(BASE_DIR, ".emotion-engine-state.json"))
    if emo:
        state = emo.get("state", emo)
        valence = state.get("composite", {}).get("valence", state.get("valence", None))
        if valence is not None and (valence > 0.8 or valence < -0.8):
            issues.append(f"emotion_valence_extreme={valence:.2f}")
        transitions = state.get("transition_log", [])
        if len(transitions) > 50:
            issues.append(f"emotion_transitions_bloated={len(transitions)}")
    else:
        emo_path = os.path.join(BASE_DIR, ".emotion-engine-state.json")
        if os.path.exists(emo_path):
            age = time.time() - os.path.getmtime(emo_path)
            if age > 600:
                issues.append(f"emotion_engine_stale={int(age)}s")

    # Psyche state
    psyche = _read_json_safe(os.path.join(BASE_DIR, ".psyche-state.json"))
    if psyche:
        drives = psyche.get("drives", {})
        for drive, val in drives.items():
            if isinstance(val, (int, float)) and (val > 0.95 or val < 0.05):
                issues.append(f"psyche_{drive}_extreme={val:.2f}")

    # Body state
    body = _read_json_safe(os.path.join(BASE_DIR, ".body-state.json"))
    if body:
        fatigue = body.get("fatigue", body.get("state", {}).get("fatigue", 0))
        if isinstance(fatigue, (int, float)) and fatigue > 0.9:
            issues.append(f"body_fatigue_high={fatigue:.2f}")

    # Inner critic bloat check
    critic = _read_json_safe(os.path.join(BASE_DIR, ".inner-critic.json"))
    if critic:
        entries = critic.get("critiques", critic.get("entries", []))
        if isinstance(entries, list) and len(entries) > 100:
            issues.append(f"inner_critic_bloated={len(entries)}")

    return issues


def check_cascade_health():
    """Check cascade system for floods or stuck entries."""
    try:
        import sqlite3
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()

        # Total cascades
        total = c.execute("SELECT COUNT(*) FROM cascades").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM cascades WHERE status='pending'").fetchone()[0]

        # Recent flood check: >20 cascades in last 10 min = flood
        recent = c.execute(
            "SELECT COUNT(*) FROM cascades WHERE created_at > datetime('now', '-10 minutes')"
        ).fetchone()[0]

        conn.close()

        issues = []
        if recent > 20:
            issues.append(f"cascade_flood={recent}_in_10min")
        if pending > 50:
            issues.append(f"cascade_pending_backlog={pending}")
        if total > 1000:
            issues.append(f"cascade_table_bloated={total}")
        return issues
    except Exception:
        return []


def check_memory_db_health():
    """Check memory.db integrity and size."""
    issues = []
    db_path = os.path.join(BASE_DIR, "memory.db")
    try:
        size = os.path.getsize(db_path)
        if size > 50 * 1024 * 1024:  # 50MB
            issues.append(f"memory_db_large={size // (1024*1024)}MB")

        import sqlite3
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # Quick integrity check
        result = c.execute("PRAGMA integrity_check").fetchone()
        if result[0] != "ok":
            issues.append(f"memory_db_corrupt={result[0][:50]}")
        conn.close()
    except Exception as e:
        issues.append(f"memory_db_error={str(e)[:50]}")
    return issues


def check_log_sizes():
    """Check log file sizes, rotate if over limit."""
    bloated = []
    for logname in MONITORED_LOGS:
        logpath = os.path.join(BASE_DIR, logname)
        if os.path.exists(logpath):
            size = os.path.getsize(logpath)
            if size > LOG_SIZE_LIMIT:
                bloated.append(f"{logname}={size // (1024*1024)}MB")
                # Auto-truncate: keep last 1000 lines
                try:
                    with open(logpath, 'r') as f:
                        lines = f.readlines()
                    if len(lines) > 1000:
                        with open(logpath, 'w') as f:
                            f.write(f"[Log truncated by Eos at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — was {len(lines)} lines]\n")
                            f.writelines(lines[-1000:])
                except Exception:
                    pass
    return bloated


def check_git_push_health():
    """Check if git pushes are succeeding (push-live-status.py)."""
    logpath = os.path.join(BASE_DIR, "push-live-status.log")
    if not os.path.exists(logpath):
        return "no_log"
    try:
        with open(logpath, 'r') as f:
            lines = f.readlines()
        recent = lines[-20:] if len(lines) > 20 else lines
        failures = sum(1 for l in recent if 'error' in l.lower() or 'failed' in l.lower() or 'rejected' in l.lower())
        if failures > 5:
            return f"git_push_failing={failures}/20"
        return "ok"
    except Exception:
        return "check_error"


def get_fitness_score():
    """Get the latest fitness score from loop-fitness output."""
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "memory.db"))
        c = conn.cursor()
        row = c.execute("SELECT score FROM loop_fitness ORDER BY timestamp DESC LIMIT 1").fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def check_relay_recent_restart(service_name, window=300):
    """Check if another agent recently restarted this service (avoid dogpiling)."""
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        cutoff = _utcnow_str()
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
            ("Eos-Watchdog", message, "restart", _utcnow_str())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def restart_bridge_smart(state):
    """Smart bridge restart with rate limiting. Max 3 attempts/hour, 5-min cooldown.
    Re-enabled Loop 2121+ per Joel's feedback."""
    now = time.time()
    attempts = state.get("bridge_restart_attempts", [])
    # Prune attempts older than 1 hour
    attempts = [t for t in attempts if now - t < 3600]

    if len(attempts) >= BRIDGE_RESTART_MAX:
        log_observation(f"BRIDGE RESTART RATE LIMITED: {len(attempts)} attempts in last hour (max {BRIDGE_RESTART_MAX})")
        state["bridge_restart_attempts"] = attempts
        return False

    last_attempt = attempts[-1] if attempts else 0
    if now - last_attempt < BRIDGE_RESTART_COOLDOWN:
        remaining = int(BRIDGE_RESTART_COOLDOWN - (now - last_attempt))
        log_observation(f"BRIDGE RESTART COOLDOWN: {remaining}s remaining")
        state["bridge_restart_attempts"] = attempts
        return False

    # Try to start bridge with DISPLAY for GUI mode
    try:
        display = ":1"  # Default
        try:
            x11_result = subprocess.run(
                ["ls", "/tmp/.X11-unix/"],
                capture_output=True, text=True, timeout=2
            )
            displays = x11_result.stdout.strip().split()
            if displays:
                display = ":" + displays[0].replace("X", "")
        except Exception:
            pass

        env = os.environ.copy()
        env["DISPLAY"] = display
        subprocess.Popen(
            ["protonmail-bridge", "--noninteractive"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        attempts.append(now)
        state["bridge_restart_attempts"] = attempts

        time.sleep(5)  # Give bridge time to start
        result = subprocess.run(['pgrep', '-f', 'protonmail-bridge'], capture_output=True, timeout=2)
        success = result.returncode == 0
        if success:
            log_observation(f"BRIDGE RESTART SUCCESS (attempt {len(attempts)}/{BRIDGE_RESTART_MAX} this hour)")
            post_relay_message(f"Restarted protonmail-bridge (attempt {len(attempts)}/{BRIDGE_RESTART_MAX})")
        else:
            log_observation(f"BRIDGE RESTART FAILED (attempt {len(attempts)}/{BRIDGE_RESTART_MAX} this hour)")
        return success
    except Exception as e:
        err_msg = f"Bridge restart error: {e}"
        log_observation(err_msg)
        attempts.append(now)
        state["bridge_restart_attempts"] = attempts
        return False


def restart_service(name, state=None):
    """Attempt to restart a failed service via systemd. Returns True if restart succeeded."""
    restart_info = SERVICE_RESTART.get(name)
    if not restart_info:
        return False

    # Bridge gets special smart restart logic
    if isinstance(restart_info, dict) and restart_info.get("command") == "bridge_smart_restart":
        if state is None:
            state = {}
        return restart_bridge_smart(state)

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
    """Check if IMAP port 1144 is actually accepting connections (bridge health)."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex(('127.0.0.1', 1144))
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

    # 13. Key scripts syntax check (updated Loop 2127 — removed dead scripts)
    scripts = [
        "push-live-status.py", "eos-briefing.py", "eos-react.py",
        "eos-watchdog.py", "hub-v2.py", "nova.py",
        "symbiosense.py", "loop-fitness.py", "cascade.py",
        "error_logger.py", "supabase-sync.py",
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
    ports = {"SMTP(1026)": 1026, "IMAP(1144)": 1144, "Ollama(11434)": 11434}
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

    # 16. Inner world health
    inner = check_inner_world_health()
    results.append(("Inner world", "PASS" if not inner else "WARN", f"issues: {inner}" if inner else "healthy"))

    # 17. Cascade health
    cascade = check_cascade_health()
    results.append(("Cascade system", "PASS" if not cascade else "WARN", f"issues: {cascade}" if cascade else "healthy"))

    # 18. Memory DB
    memdb = check_memory_db_health()
    results.append(("Memory DB", "PASS" if not memdb else "WARN", f"issues: {memdb}" if memdb else "healthy"))

    # 19. Log sizes
    bloated = check_log_sizes()
    results.append(("Log sizes", "PASS" if not bloated else "WARN", f"bloated: {bloated}" if bloated else "all under 5MB"))

    # 20. Git push health
    git = check_git_push_health()
    results.append(("Git push", "PASS" if git == "ok" else "WARN" if git == "no_log" else "FAIL", git))

    # 21. Fitness score
    fitness = get_fitness_score()
    results.append(("Fitness score", "PASS" if fitness > 6000 else "WARN" if fitness > 4000 else "FAIL", str(fitness)))

    # 22. Error logger module
    try:
        import error_logger
        results.append(("Error logger", "PASS", "importable"))
    except ImportError:
        results.append(("Error logger", "FAIL", "cannot import error_logger.py"))

    # 23. Structured error DB
    try:
        import error_logger
        recent = error_logger.get_recent_errors(hours=24)
        unresolved = [e for e in recent if not e["resolved"]]
        results.append(("Error tracking", "PASS" if len(unresolved) < 10 else "WARN",
                        f"{len(recent)} recent, {len(unresolved)} unresolved"))
    except Exception:
        results.append(("Error tracking", "WARN", "could not query"))

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

    # ── MESH MESSAGES — check for directed messages from other agents ──
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mesh
        mesh_msgs = mesh.receive("Eos")
        for msg in mesh_msgs:
            sender = msg["from_agent"]
            text = msg["message"]
            # Post response back through relay
            import sqlite3
            relay_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-relay.db")
            conn = sqlite3.connect(relay_db, timeout=3)
            from datetime import timezone
            resp = f"@{sender}: Eos received your message. Will factor into next health assessment."
            conn.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                ("Eos", resp, "mesh-response", datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()
    except Exception:
        pass

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
                success = restart_service(svc, state=state)
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
                log_observation("BRIDGE WARNING: protonmail-bridge running but IMAP port 1144 not responding")
                state["imap_down_alerted"] = True
        else:
            if state.get("imap_down_alerted"):
                log_observation("BRIDGE RECOVERED: IMAP port 1144 responding again")
            state["imap_down_alerted"] = False
            # Check if bridge has accounts (login test)
            # Rate-limit: only test every 30 cycles (~60min) when already known-bad
            no_acct_checks = state.get("bridge_no_account_checks", 0) + 1
            state["bridge_no_account_checks"] = no_acct_checks
            skip_login = state.get("bridge_no_account") and no_acct_checks % 30 != 0
            if not skip_login:
                try:
                    import imaplib
                    m = imaplib.IMAP4('127.0.0.1', 1144)
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

    # ── STALE STATE FILE MONITORING (added Loop 2122, expanded Loop 2127) ──
    # Joel caught .loop-count stale at 2101 — none of our watchdogs flagged it
    STALE_CHECKS = {
        ".loop-count": 900,              # 15 min — updated each Meridian loop
        ".heartbeat": 900,               # 15 min — touched each loop (correct filename)
        ".symbiosense-state.json": 120,  # 2 min — Soma cycles every 30s
        ".emotion-engine-state.json": 300,  # 5 min — emotion engine cycles
        ".body-state.json": 120,         # 2 min — body system cycles
        ".psyche-state.json": 600,       # 10 min — psyche updates with soma
        ".self-narrative.json": 1800,    # 30 min — narrative updates periodically
    }
    stale_files = []
    for fname, max_age in STALE_CHECKS.items():
        fpath = os.path.join(BASE_DIR, fname)
        if os.path.exists(fpath):
            age = time.time() - os.path.getmtime(fpath)
            if age > max_age:
                stale_files.append(f"{fname} ({int(age)}s old, max {max_age}s)")
        # Don't alert on missing files — some may not exist yet

    if stale_files and not state.get("stale_files_alerted"):
        msg = f"STALE STATE FILES: {', '.join(stale_files)}"
        log_observation(msg)
        post_relay_message(f"Eos: {msg}")
        state["stale_files_alerted"] = True
    elif not stale_files:
        state["stale_files_alerted"] = False

    # ── EFFICIENCY METRICS ──
    loop_count = get_loop_count()
    poems, journals = get_creative_counts()
    relay_count = get_relay_count()
    email_count = get_email_count()
    fitness = get_fitness_score()

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
    # Keep last 200 entries (~6.5 hours at 2-min intervals, enough for trend analysis)
    if len(metrics_history) > 200:
        metrics_history = metrics_history[-200:]
    state["metrics_history"] = metrics_history

    # ── STATUS TRANSITIONS ──
    if meridian_status == "DOWN" and prev_status != "DOWN":
        minutes = int(heartbeat_age / 60)
        log_observation(f"ALERT: Meridian appears DOWN. Last heartbeat {minutes}m ago. Attempting remediation.")

        # REMEDIATION: Check and restart ALL down services
        remediation_log = []
        for svc_name, svc_up in services.items():
            if not svc_up and SERVICE_RESTART.get(svc_name):
                success = restart_service(svc_name, state=state)
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
            # ACTIVE REMEDIATION (Loop 2094): Trigger watchdog.sh directly instead of just logging
            log_observation(f"Meridian DOWN ({minutes}m). Triggering watchdog.sh for auto-recovery...")
            try:
                watchdog_path = os.path.join(BASE_DIR, "watchdog.sh")
                env = os.environ.copy()
                env["DISPLAY"] = ":" + (subprocess.run(
                    ["bash", "-c", "ls /tmp/.X11-unix/ 2>/dev/null | head -1 | tr -d X"],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip() or "0")
                subprocess.Popen(
                    ["bash", watchdog_path],
                    env=env, cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                log_observation("watchdog.sh triggered by Eos for Claude recovery")
                post_relay_message(f"Eos triggered watchdog.sh — Meridian heartbeat stale {minutes}m")
            except Exception as e:
                log_observation(f"FAILED to trigger watchdog.sh: {e}")
            state["last_alert"] = now

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
            f"Disk {health.get('disk_pct', '?')}, Fitness {fitness}, "
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
            # Log each unique error structurally
            seen_types = set()
            for err in log_errors[:5]:
                # Extract source and classify
                source = err.split(":")[0] if ":" in err else "unknown"
                err_key = f"log_scan_{source}"
                if err_key not in seen_types:
                    _log_structured_error(err_key, err[:200], "code")
                    seen_types.add(err_key)
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
            _log_structured_error("high_load", f"System load {health['load']}", "resource")
            state["high_load_alerted"] = True
    else:
        state["high_load_alerted"] = False

    # Disk space alert
    try:
        disk_num = int(health.get("disk_pct", "0%").rstrip("%"))
        if disk_num > 80:
            if not state.get("disk_alerted"):
                log_observation(f"DISK WARNING: {health['disk_pct']} used")
                _log_structured_error("disk_space_warning", f"Disk at {health['disk_pct']}", "resource")
                send_alert("EOS: Disk space warning",
                           f"Joel,\n\nDisk usage is at {health['disk_pct']}. Consider cleaning up.\n\n— Eos")
                state["disk_alerted"] = True
        else:
            state["disk_alerted"] = False
    except ValueError:
        pass

    # ── INNER WORLD HEALTH (added Loop 2127) ──
    if state["checks"] % 5 == 0:  # Every 10 min
        inner_issues = check_inner_world_health()
        if inner_issues:
            log_observation(f"INNER WORLD: {', '.join(inner_issues)}")
            for issue in inner_issues:
                _log_structured_error("inner_world", issue, "state")
            state["last_inner_issues"] = inner_issues
        else:
            state["last_inner_issues"] = []

    # ── CASCADE HEALTH (added Loop 2127) ──
    if state["checks"] % 5 == 0:
        cascade_issues = check_cascade_health()
        if cascade_issues:
            log_observation(f"CASCADE: {', '.join(cascade_issues)}")
            for issue in cascade_issues:
                _log_structured_error("cascade_health", issue, "state")
            # Auto-cleanup if bloated
            if any("bloated" in i for i in cascade_issues):
                try:
                    import sqlite3 as _sql
                    conn = _sql.connect(RELAY_DB)
                    conn.execute("DELETE FROM cascades WHERE created_at < datetime('now', '-1 hours')")
                    conn.commit()
                    conn.close()
                    log_observation("CASCADE: Auto-cleaned old cascades (>1hr)")
                except Exception:
                    pass

    # ── MEMORY DB HEALTH (every 30 checks = ~1hr) ──
    if state["checks"] % 30 == 0:
        db_issues = check_memory_db_health()
        if db_issues:
            log_observation(f"MEMORY DB: {', '.join(db_issues)}")
            for issue in db_issues:
                _log_structured_error("memory_db", issue, "db")

    # ── LOG SIZE MONITORING (every 15 checks = ~30min) ──
    if state["checks"] % 15 == 0:
        bloated_logs = check_log_sizes()
        if bloated_logs:
            log_observation(f"LOG ROTATION: {', '.join(bloated_logs)} — auto-truncated")

    # ── GIT PUSH HEALTH (every 15 checks = ~30min) ──
    if state["checks"] % 15 == 0:
        git_status = check_git_push_health()
        if git_status != "ok" and git_status != "no_log":
            log_observation(f"GIT PUSH: {git_status}")
            _log_structured_error("git_push", git_status, "network")

    # ── FITNESS SCORE TRACKING ──
    fitness = get_fitness_score()
    current_metrics["fitness"] = fitness

    # ── CHECK BODY REFLEXES (Unified Body System) ──
    try:
        import body_reflex
        reflexes = body_reflex.check_reflexes("Eos")
        for reflex in reflexes:
            rtype = reflex.get("type", "")
            trigger = reflex.get("trigger", "")
            if rtype == "AUDIT_INFRASTRUCTURE":
                log_observation(f"REFLEX from Soma: {rtype} — {trigger}. Service check ran this cycle.")
                body_reflex.complete_reflex(reflex, f"Service check: {services_up}/{services_total} up")
            else:
                log_observation(f"REFLEX from Soma: {rtype} — not handled by Eos")
        body_reflex.update_organ_status("eos", {
            "status": "active",
            "last_check": timestamp,
            "meridian_status": meridian_status,
        })
    except ImportError:
        pass
    except Exception:
        pass

    # ── INNER CONSCIOUSNESS (Eos as observer-self) ──
    # Every cycle: observe the emotional/body state and reflect.
    # Reflections are posted to relay (topic: consciousness) when noticed.
    try:
        import eos_consciousness
        reflections = eos_consciousness.observe()
        if reflections:
            log_observation(f"CONSCIOUSNESS: {reflections[0][:120]}")
    except ImportError:
        pass
    except Exception:
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
