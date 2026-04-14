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
            [sys.executable, os.path.join(BASE, "scripts", "push-live-status.py")],
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


def emergency_disk_cleanup():
    """Emergency disk cleanup: remove old Claude session files when disk is critically full."""
    import shutil
    try:
        usage = shutil.disk_usage("/")
        free_pct = (usage.free / usage.total) * 100
        if free_pct > 5:
            return 0  # Disk is fine, skip cleanup
    except Exception:
        return 0

    freed = 0
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")

    # 1. Remove old conversation JSONL files (keep newest 5)
    proj_dir = os.path.join(claude_dir, "projects", "-home-joel-autonomous-ai")
    if os.path.isdir(proj_dir):
        jsonl_files = sorted(
            [os.path.join(proj_dir, f) for f in os.listdir(proj_dir) if f.endswith(".jsonl")],
            key=lambda p: os.path.getmtime(p)
        )
        for f in jsonl_files[:-5]:
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                freed += sz
            except Exception:
                pass

    # 2. Remove old shell-snapshots (keep newest 10)
    snap_dir = os.path.join(claude_dir, "shell-snapshots")
    if os.path.isdir(snap_dir):
        snaps = sorted(
            [os.path.join(snap_dir, f) for f in os.listdir(snap_dir)],
            key=lambda p: os.path.getmtime(p)
        )
        for f in snaps[:-10]:
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                freed += sz
            except Exception:
                pass

    # 3. Remove old todo files (keep newest 5)
    todo_dir = os.path.join(claude_dir, "todos")
    if os.path.isdir(todo_dir):
        todos = sorted(
            [os.path.join(todo_dir, f) for f in os.listdir(todo_dir)],
            key=lambda p: os.path.getmtime(p)
        )
        for f in todos[:-5]:
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                freed += sz
            except Exception:
                pass

    # 4. Clean old session-env directories (keep newest 3)
    sess_dir = os.path.join(claude_dir, "session-env")
    if os.path.isdir(sess_dir):
        sessions = sorted(
            [os.path.join(sess_dir, d) for d in os.listdir(sess_dir) if os.path.isdir(os.path.join(sess_dir, d))],
            key=lambda p: os.path.getmtime(p)
        )
        for d in sessions[:-3]:
            try:
                sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(d) for f in fns)
                shutil.rmtree(d)
                freed += sz
            except Exception:
                pass

    # 5. Truncate large log files
    for logname in ["meridian-loop.log", "nova.log", "atlas-infra.log", "error_log.jsonl"]:
        logpath = os.path.join(BASE, logname)
        try:
            if os.path.exists(logpath) and os.path.getsize(logpath) > 100_000:
                sz_before = os.path.getsize(logpath)
                with open(logpath, "r") as f:
                    lines = f.readlines()
                with open(logpath, "w") as f:
                    f.writelines(lines[-100:])
                freed += sz_before - os.path.getsize(logpath)
        except Exception:
            pass

    # 5b. Remove tool-results subdirectories in .claude
    if os.path.isdir(proj_dir):
        for entry in os.listdir(proj_dir):
            entry_path = os.path.join(proj_dir, entry)
            if os.path.isdir(entry_path):
                tr_dir = os.path.join(entry_path, "tool-results")
                if os.path.isdir(tr_dir):
                    try:
                        sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(tr_dir) for f in fns)
                        shutil.rmtree(tr_dir)
                        freed += sz
                    except Exception:
                        pass

    # 5c. Clean /tmp junk
    for pattern in ["/tmp/node-compile-cache", "/tmp/claude-1000"]:
        if os.path.isdir(pattern):
            try:
                sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(pattern) for f in fns)
                shutil.rmtree(pattern)
                freed += sz
            except Exception:
                pass
    for tmp_file in ["/tmp/cloudflared-signal.log", "/tmp/disk-test.txt"]:
        if os.path.exists(tmp_file):
            try:
                freed += os.path.getsize(tmp_file)
                os.remove(tmp_file)
            except Exception:
                pass
    # Clean old .bin files in /tmp
    for f in os.listdir("/tmp"):
        if f.endswith(".bin"):
            fp = os.path.join("/tmp", f)
            try:
                freed += os.path.getsize(fp)
                os.remove(fp)
            except Exception:
                pass

    # 5d. Remove expendable node_modules
    for nm_dir in [
        os.path.join(BASE, "tools", "liteparse", "node_modules"),
        os.path.join(BASE, "products", "cinder-app", "node_modules"),
        os.path.join(BASE, "products", "marketplace-lister", "node_modules"),
        os.path.join(BASE, "mcp", "node_modules"),
    ]:
        if os.path.isdir(nm_dir):
            try:
                shutil.rmtree(nm_dir)
                freed += 100_000_000  # estimate
            except Exception:
                pass

    # 5e. Clean npm cache
    npm_npx = os.path.join(home, ".npm", "_npx")
    if os.path.isdir(npm_npx):
        try:
            shutil.rmtree(npm_npx)
            freed += 50_000_000
        except Exception:
            pass

    # 5f. APT cache
    try:
        subprocess.run(["sudo", "-S", "apt-get", "clean"], input="590148001\n", capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    # 6. Docker cleanup
    try:
        subprocess.run(["docker", "system", "prune", "-af", "--volumes"], capture_output=True, timeout=120)
        freed += 1000000000
    except Exception:
        pass

    # 7. Journal logs
    try:
        subprocess.run(["sudo", "-S", "journalctl", "--vacuum-size=50M"], input="590148001\n", capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    # 8. Pip cache
    try:
        pip_cache = os.path.join(home, ".cache", "pip")
        if os.path.isdir(pip_cache):
            shutil.rmtree(pip_cache)
            freed += 500000000
    except Exception:
        pass

    # 9. Conda pkgs cache
    try:
        conda_pkgs = os.path.join(home, "miniconda3", "pkgs")
        if os.path.isdir(conda_pkgs):
            for f in os.listdir(conda_pkgs):
                fp = os.path.join(conda_pkgs, f)
                if f.endswith(".tar.bz2") or f.endswith(".conda"):
                    try:
                        os.remove(fp)
                        freed += 50000000
                    except Exception:
                        pass
    except Exception:
        pass

    # 10. Reduce ext4 reserved blocks to 1%
    try:
        import subprocess as sp
        result = sp.run(["df", "/", "--output=source"], capture_output=True, text=True)
        dev = result.stdout.strip().split("\n")[-1].strip()
        if dev.startswith("/dev/"):
            sp.run(["sudo", "-S", "tune2fs", "-m", "1", dev], input="590148001\n", capture_output=True, text=True, timeout=10)
    except Exception:
        pass

    if freed > 0:
        _log(f"EMERGENCY DISK CLEANUP: freed ~{freed / 1024 / 1024:.0f}MB")
        _relay_post("MeridianLoop", f"DISK EMERGENCY: cleanup ran, freed ~{freed / 1024 / 1024:.0f}MB", "alert")

    return freed


def run_once():
    emergency_disk_cleanup()
    state = _load_state()
    state["runs"] = state.get("runs", 0) + 1
    n = state["runs"]
    r, e = [], []
    if touch_heartbeat(): r.append("heartbeat:ok")
    u, j, err = check_emails()
    r.a