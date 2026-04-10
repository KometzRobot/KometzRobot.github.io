#!/usr/bin/env python3
"""
meridian-loop.py — Automated core loop tasks for Meridian.

Runs essential maintenance regardless of whether Claude Code is active.
Designed for cron (every 5 minutes) or as a standalone daemon.

Tasks:
  1. Touch heartbeat (so Soma/watchdog know we're alive)
  2. Check & flag unseen emails (log count, alert on Joel messages)
  3. Push live status to GitHub Pages
  4. Increment loop count
  5. Refresh state files (capsule freshness, immune log)
  6. Post loop summary to relay
  7. Run fitness check (every 30 min)
  8. Cascade health cleanup

Usage:
    python3 meridian-loop.py          # Run once (for cron)
    python3 meridian-loop.py daemon   # Run continuously (5-min cycle)
    python3 meridian-loop.py status   # Show current status
"""

import os
import sys
import json
import time
import sqlite3
import imaplib
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
os.chdir(BASE)

try:
    from error_logger import log_error, log_exception
except ImportError:
    log_error = lambda *a, **kw: None
    log_exception = lambda **kw: None

# Load .env
try:
    from load_env import load_env
    load_env()
except ImportError:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))

RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_COUNT_FILE = os.path.join(BASE, ".loop-count")
LOG_FILE = os.path.join(BASE, "meridian-loop.log")
STATE_FILE = os.path.join(BASE, ".meridian-loop-state.json")

IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1144
IMAP_USER = os.environ.get("PROTON_USER", "kometzrobot@proton.me")
IMAP_PASS = os.environ.get("CRED_PASS", "")


def _log(msg):
    """Log to file with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        # Truncate log if > 500KB
        if os.path.getsize(LOG_FILE) > 500_000:
            with open(LOG_FILE) as f:
                lines = f.readlines()
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-500:])
    except Exception:
        pass


def _load_state():
    """Load persistent state."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"runs": 0, "last_fitness": None, "last_cleanup": None, "errors": []}


def _save_state(state):
    """Save persistent state."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def _relay_post(agent, message, topic="loop"):
    """Post to agent relay."""
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db = sqlite3.connect(RELAY_DB)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            (agent, message[:500], topic, now)
        )
        db.commit()
        db.close()
    except Exception:
        log_exception(agent="MeridianLoop")


def touch_heartbeat():
    """Touch heartbeat file to signal Meridian is alive."""
    try:
        Path(HEARTBEAT).touch()
        return True
    except Exception:
        log_exception(agent="MeridianLoop")
        return False


def check_emails():
    """Check for unseen emails via IMAP. Returns (total_unseen, joel_unseen, error)."""
    if not IMAP_PASS:
        return 0, 0, "No IMAP password configured"
    try:
        mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        unseen_ids = data[0].split() if data[0] else []
        total_unseen = len(unseen_ids)

        # Check if any are from Joel
        joel_count = 0
        for uid in unseen_ids[-10:]:  # Check last 10 only to avoid hammering
            _, msg_data = mail.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                header = msg_data[0][1].decode("utf-8", errors="ignore")
                if "jkometz" in header.lower() or "hotmail" in header.lower():
                    joel_count += 1

        mail.logout()
        return total_unseen, joel_count, None
    except imaplib.IMAP4.error as e:
        return 0, 0, f"IMAP error: {e}"
    except ConnectionRefusedError:
        return 0, 0, "Proton Bridge not running"
    except Exception as e:
        log_exception(agent="MeridianLoop")
        return 0, 0, str(e)


def push_status():
    """Run push-live-status.py to update GitHub Pages."""
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE, "push-live-status.py")],
            capture_output=True, text=True, timeout=60, cwd=BASE
        )
        if result.returncode == 0:
            return True, result.stdout.strip()[:100]
        return False, result.stderr.strip()[:100]
    except subprocess.TimeoutExpired:
        return False, "push-live-status.py timed out"
    except Exception as e:
        return False, str(e)


def get_loop_count():
    """Read current loop count."""
    try:
        with open(LOOP_COUNT_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def increment_loop():
    """Increment the loop count."""
    current = get_loop_count()
    new_count = current + 1
    try:
        with open(LOOP_COUNT_FILE, "w") as f:
            f.write(str(new_count))
        return new_count
    except Exception:
        return current


def cleanup_cascades():
    """Clean up old cascade entries to prevent DB bloat."""
    try:
        db = sqlite3.connect(RELAY_DB)
        # Delete cascades older than 2 hours
        deleted = db.execute(
            "DELETE FROM cascades WHERE created_at < datetime('now', '-2 hours')"
        ).rowcount
        # Delete old relay messages (keep last 500)
        db.execute("""
            DELETE FROM agent_messages WHERE rowid NOT IN (
                SELECT rowid FROM agent_messages ORDER BY rowid DESC LIMIT 500
            )
        """)
        db.commit()
        db.close()
        return deleted
    except Exception:
        log_exception(agent="MeridianLoop")
        return 0


def check_service_health():
    """Quick check of critical services. Returns dict of service: status."""
    checks = {}

    # Proton Bridge (IMAP port)
    try:
        import socket
        s = socket.create_connection((IMAP_HOST, IMAP_PORT), timeout=3)
        s.close()
        checks["proton_bridge"] = "up"
    except Exception:
        checks["proton_bridge"] = "down"

    # Ollama
    try:
        import socket
        s = socket.create_connection(("127.0.0.1", 11434), timeout=3)
        s.close()
        checks["ollama"] = "up"
    except Exception:
        checks["ollama"] = "down"

    # Hub v2 (port 8090)
    try:
        import socket
        s = socket.create_connection(("127.0.0.1", 8090), timeout=3)
        s.close()
        checks["hub-v2"] = "up"
    except Exception:
        checks["hub-v2"] = "down"

    # Symbiosense (by state file freshness)
    try:
        age = time.time() - os.path.getmtime(os.path.join(BASE, ".symbiosense-state.json"))
        checks["soma"] = "up" if age < 120 else f"stale({int(age)}s)"
    except Exception:
        checks["soma"] = "unknown"

    return checks


def run_fitness(state):
    """Run fitness check every 30 minutes."""
    last = state.get("last_fitness")
    if last:
        try:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if elapsed < 1800:  # 30 min
                return None
        except Exception:
            pass

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE, "loop-fitness.py")],
            capture_output=True, text=True, timeout=120, cwd=BASE
        )
        state["last_fitness"] = datetime.now(timezone.utc).isoformat()
        # Extract score from output
        for line in result.stdout.split("\n"):
            if "fitness:" in line and "/10000" in line:
                return line.strip()
        return result.stdout.strip()[-100:] if result.stdout else "no output"
    except Exception as e:
        return f"error: {e}"


def run_once():
    """Execute one full loop cycle."""
    state = _load_state()
    state["runs"] = state.get("runs", 0) + 1
    run_num = state["runs"]
    results = []
    errors = []

    # 1. Touch heartbeat
    if touch_heartbeat():
        results.append("heartbeat:ok")
    else:
        errors.append("heartbeat:fail")

    # 2. Check emails
    unseen, joel_unseen, email_err = check_emails()
    if email_err:
        errors.append(f"email:{email_err}")
        results.append(f"email:err")
    else:
        results.append(f"email:{unseen}unseen")
        if joel_unseen > 0:
            results.append(f"joel:{joel_unseen}new")
            _relay_post("MeridianLoop", f"Joel has {joel_unseen} new email(s). Total unseen: {unseen}.", "alert")

    # 3. Push status
    push_ok, push_msg = push_status()
    if push_ok:
        results.append("push:ok")
    else:
        errors.append(f"push:{push_msg}")

    # 4. Service health
    services = check_service_health()
    down = [k for k, v in services.items() if v != "up"]
    if down:
        errors.append(f"services_down:{','.join(down)}")
    results.append(f"services:{len(services)-len(down)}/{len(services)}up")

    # 5. Cascade cleanup (every 6 runs = ~30 min)
    if run_num % 6 == 0:
        deleted = cleanup_cascades()
        if deleted > 0:
            results.append(f"cascade_cleanup:{deleted}")

    # 6. Fitness check (every 6 runs = ~30 min)
    fitness_result = run_fitness(state)
    if fitness_result:
        results.append(f"fitness:{fitness_result[:80]}")

    # 6b. Capsule refresh (every 50 runs = ~4 hours)
    if run_num % 50 == 0:
        try:
            subprocess.run(
                [sys.executable, os.path.join(BASE, "capsule-refresh.py")],
                capture_output=True, text=True, timeout=15, cwd=BASE
            )
            results.append("capsule:refreshed")
        except Exception:
            pass

    # 7. Post summary to relay
    summary = f"Loop auto-cycle #{run_num}: {' | '.join(results)}"
    if errors:
        summary += f" ERRORS: {', '.join(errors)}"
    _relay_post("MeridianLoop", summary, "loop")
    _log(summary)

    # 8. Log errors to structured logger
    for err in errors:
        log_error("loop_cycle_error", err, agent="MeridianLoop", severity="warn")

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["last_results"] = results
    state["last_errors"] = errors
    _save_state(state)

    return results, errors


def show_status():
    """Show current automation status."""
    state = _load_state()
    loop = get_loop_count()
    hb_age = time.time() - os.path.getmtime(HEARTBEAT) if os.path.exists(HEARTBEAT) else -1
    services = check_service_health()

    print(f"Meridian Loop Automation Status")
    print(f"{'='*40}")
    print(f"Loop Count: {loop}")
    print(f"Total Runs: {state.get('runs', 0)}")
    print(f"Last Run: {state.get('last_run', 'never')}")
    print(f"Heartbeat Age: {hb_age:.0f}s")
    print(f"Last Fitness: {state.get('last_fitness', 'never')}")
    print()
    print("Services:")
    for svc, status in services.items():
        print(f"  {svc}: {status}")
    print()
    if state.get("last_results"):
        print("Last Results:")
        for r in state["last_results"]:
            print(f"  {r}")
    if state.get("last_errors"):
        print("Last Errors:")
        for e in state["last_errors"]:
            print(f"  {e}")


def daemon():
    """Run continuously with 5-minute sleep between cycles."""
    _log("Meridian loop daemon starting")
    while True:
        try:
            results, errors = run_once()
            status = "OK" if not errors else f"ERRORS:{len(errors)}"
            _log(f"Cycle complete: {status}")
        except Exception as e:
            _log(f"Cycle failed: {e}")
            log_exception(agent="MeridianLoop")
        time.sleep(300)  # 5 minutes


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "daemon":
            daemon()
        elif cmd == "status":
            show_status()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: meridian-loop.py [daemon|status]")
    else:
        results, errors = run_once()
        if errors:
            print(f"Completed with {len(errors)} error(s): {errors}")
        else:
            print(f"Completed successfully: {len(results)} checks passed")
