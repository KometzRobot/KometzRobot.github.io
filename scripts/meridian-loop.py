#!/usr/bin/env python3
"""
meridian-loop.py — Meridian's automated core loop (v3).

Runs essential maintenance whether or not Claude Code is active.
Designed for systemd daemon mode or one-shot cron.

Tasks per cycle (~5 min):
  1. Touch heartbeat
  2. Check & flag unseen emails (watermark for phone-read detection)
  3. Increment loop count
  4. Service health check (proton, ollama, hub, soma, command-center, chorus)
  5. Auto-restart critical services if down
  6. Refresh wake-state.md with real system data
  7. Push live status (every 10th run)
  8. Cascade + relay cleanup (every 6th run)
  9. Fitness check (every 6th run / 30 min)
  10. Capsule refresh (every 6th run / 30 min)
  11. Disk cleanup (only when disk > 90%)
  12. Swap pressure monitoring + top consumer alerts

Usage:
    python3 meridian-loop.py          # Run once (for cron)
    python3 meridian-loop.py daemon   # Run continuously (5-min cycle)
    python3 meridian-loop.py status   # Show current status
"""

VERSION = "3.0"

import os
import sys
import json
import time
import signal
import sqlite3
import imaplib
import shutil
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
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(BASE, ".env"))
    except ImportError:
        pass

# ── Paths ──
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_COUNT_FILE = os.path.join(BASE, ".loop-count")
LOG_FILE = os.path.join(BASE, "logs", "meridian-loop.log")
STATE_FILE = os.path.join(BASE, ".meridian-loop-state.json")
WATERMARK_FILE = os.path.join(BASE, ".email-watermark")
CAPSULE_FILE = os.path.join(BASE, ".capsule.md")

# ── IMAP/SMTP ──
IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1144
IMAP_USER = os.environ.get("CRED_USER", os.environ.get("PROTON_USER", "kometzrobot@proton.me"))
IMAP_PASS = os.environ.get("CRED_PASS", "")


def _log(msg):
    """Log to file with timestamp. Auto-truncates at 500KB."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 500_000:
            with open(LOG_FILE) as f:
                lines = f.readlines()
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-500:])
    except Exception:
        pass


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"runs": 0, "last_fitness": None, "last_cleanup": None,
                "last_capsule": None, "errors": []}


def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def _relay_post(agent, message, topic="loop"):
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


# ── Signal handling ──
_shutdown = False

def _handle_signal(signum, frame):
    global _shutdown
    name = signal.Signals(signum).name
    _log(f"Received {name} — shutting down gracefully")
    _shutdown = True

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ── Auto-restart services ──

# Map of service names to their systemd unit names or restart commands
RESTARTABLE_SERVICES = {
    "hub-v2": "meridian-hub-v2",
    "soma": "symbiosense",
    "chorus": "the-chorus",
    "command-center": "command-center",
}

def auto_restart_service(name, systemd_unit):
    """Attempt to restart a down service via systemctl --user."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", systemd_unit],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            _log(f"AUTO-RESTART: {name} ({systemd_unit}) restarted successfully")
            _relay_post("MeridianLoop", f"Auto-restarted {name}", "auto-restart")
            return True
        else:
            _log(f"AUTO-RESTART FAILED: {name}: {result.stderr[:100]}")
            return False
    except Exception as e:
        _log(f"AUTO-RESTART ERROR: {name}: {e}")
        return False


def get_top_memory_consumers(n=5):
    """Get top N processes by memory usage."""
    try:
        result = subprocess.run(
            ["ps", "aux", "--sort=-rss"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")[1:n+1]  # skip header
        consumers = []
        for line in lines:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                consumers.append({
                    "pid": parts[1],
                    "rss_pct": parts[3],
                    "cmd": parts[10][:60]
                })
        return consumers
    except Exception:
        return []


# ── Core tasks ──

def touch_heartbeat():
    try:
        Path(HEARTBEAT).touch()
        return True
    except Exception:
        log_exception(agent="MeridianLoop")
        return False


def _read_watermark():
    try:
        with open(WATERMARK_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_watermark(msg_id):
    current = _read_watermark()
    if msg_id > current:
        with open(WATERMARK_FILE, "w") as f:
            f.write(str(msg_id))


def check_emails():
    """Check for unseen emails via IMAP with retry. Returns (total_unseen, joel_unseen, error)."""
    if not IMAP_PASS:
        return 0, 0, "No IMAP password configured"
    try:
        # Retry connection once on failure (Proton Bridge can be slow to respond)
        mail = None
        for attempt in range(2):
            try:
                mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
                mail.login(IMAP_USER, IMAP_PASS)
                break
            except (ConnectionRefusedError, imaplib.IMAP4.error):
                if attempt == 0:
                    time.sleep(2)
                else:
                    raise
        if mail is None:
            return 0, 0, "IMAP connection failed after retry"
        mail.select("INBOX")

        _, data = mail.search(None, "UNSEEN")
        unseen_ids = data[0].split() if data[0] else []
        total_unseen = len(unseen_ids)

        # Watermark: detect phone-read emails
        watermark = _read_watermark()
        unprocessed_count = 0
        if watermark > 0:
            _, all_data = mail.search(None, "ALL")
            all_ids = all_data[0].split() if all_data[0] else []
            new_ids = [mid for mid in all_ids if int(mid) > watermark]
            unseen_set = set(unseen_ids)
            unprocessed_count = len([mid for mid in new_ids if mid not in unseen_set])

        # Check if any unseen are from Joel (last 10 only)
        joel_count = 0
        for uid in unseen_ids[-10:]:
            _, msg_data = mail.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                header = msg_data[0][1].decode("utf-8", errors="ignore")
                if "jkometz" in header.lower() or "hotmail" in header.lower():
                    joel_count += 1

        # Update watermark
        _, all_data = mail.search(None, "ALL")
        all_ids = all_data[0].split() if all_data[0] else []
        if all_ids:
            _write_watermark(int(all_ids[-1]))

        mail.logout()

        if unprocessed_count > 0:
            _relay_post("MeridianLoop",
                        f"{unprocessed_count} email(s) read by phone before agent — check recent inbox",
                        "alert")
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
    try:
        with open(LOOP_COUNT_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def increment_loop():
    current = get_loop_count()
    new_count = current + 1
    try:
        with open(LOOP_COUNT_FILE, "w") as f:
            f.write(str(new_count))
        return new_count
    except Exception:
        return current


def cleanup_cascades():
    """Clean up old cascade entries and relay messages to prevent DB bloat."""
    try:
        db = sqlite3.connect(RELAY_DB)
        deleted = db.execute(
            "DELETE FROM cascades WHERE created_at < datetime('now', '-2 hours')"
        ).rowcount
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


def check_service_health(auto_restart=True):
    """Check critical services. Auto-restarts down services if enabled.
    Returns dict of service: status."""
    import socket
    checks = {}

    for name, host, port in [
        ("proton_bridge", IMAP_HOST, IMAP_PORT),
        ("ollama", "127.0.0.1", 11434),
        ("hub-v2", "127.0.0.1", 8090),
        ("chorus", "127.0.0.1", 8091),
    ]:
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            checks[name] = "up"
        except Exception:
            checks[name] = "down"

    # Soma — check state file freshness
    soma_state = os.path.join(BASE, ".symbiosense-state.json")
    try:
        age = time.time() - os.path.getmtime(soma_state)
        checks["soma"] = "up" if age < 120 else f"stale({int(age)}s)"
    except Exception:
        checks["soma"] = "unknown"

    # Command center — check systemd
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "command-center"],
            capture_output=True, text=True, timeout=5
        )
        checks["command-center"] = r.stdout.strip()
    except Exception:
        checks["command-center"] = "unknown"

    # Meridian loop itself
    checks["meridian-loop"] = "active"

    # Auto-restart down services
    if auto_restart:
        for svc_name, status in checks.items():
            if status == "down" and svc_name in RESTARTABLE_SERVICES:
                unit = RESTARTABLE_SERVICES[svc_name]
                if auto_restart_service(svc_name, unit):
                    checks[svc_name] = "restarted"

    return checks


def get_system_resources():
    """Get CPU, RAM, disk, swap stats."""
    stats = {}

    # Load
    try:
        load_1, load_5, load_15 = os.getloadavg()
        stats["load"] = f"{load_1:.2f}, {load_5:.2f}, {load_15:.2f}"
        stats["load_1"] = load_1
    except Exception:
        stats["load"] = "unknown"
        stats["load_1"] = 0

    # RAM
    try:
        mem_info = open("/proc/meminfo").read()
        total_kb = int([l for l in mem_info.split("\n") if "MemTotal" in l][0].split()[1])
        avail_kb = int([l for l in mem_info.split("\n") if "MemAvailable" in l][0].split()[1])
        stats["ram_used_gb"] = f"{(total_kb - avail_kb) / 1024 / 1024:.1f}"
        stats["ram_total_gb"] = f"{total_kb / 1024 / 1024:.1f}"
        stats["ram_pct"] = int((total_kb - avail_kb) / total_kb * 100)
    except Exception:
        stats["ram_used_gb"] = "?"
        stats["ram_total_gb"] = "?"
        stats["ram_pct"] = 0

    # Swap
    try:
        swap_total = int([l for l in mem_info.split("\n") if "SwapTotal" in l][0].split()[1])
        swap_free = int([l for l in mem_info.split("\n") if "SwapFree" in l][0].split()[1])
        if swap_total > 0:
            stats["swap_pct"] = int((swap_total - swap_free) / swap_total * 100)
            stats["swap_used_mb"] = int((swap_total - swap_free) / 1024)
        else:
            stats["swap_pct"] = 0
            stats["swap_used_mb"] = 0
    except Exception:
        stats["swap_pct"] = 0
        stats["swap_used_mb"] = 0

    # Disk
    try:
        usage = shutil.disk_usage("/")
        stats["disk_pct"] = int(usage.used / usage.total * 100)
        stats["disk_free_gb"] = f"{usage.free / 1024 / 1024 / 1024:.1f}"
    except Exception:
        stats["disk_pct"] = 0
        stats["disk_free_gb"] = "?"

    return stats


def refresh_wake_state(loop_count, health, resources):
    """Update wake-state.md with comprehensive system snapshot."""
    try:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        now_mdt = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M MDT")

        svc_lines = []
        for svc, status in health.items():
            icon = "+" if status in ("up", "active") else "-" if status == "down" else "~"
            svc_lines.append(f"  [{icon}] {svc}: {status}")

        # Uptime
        try:
            with open("/proc/uptime") as f:
                uptime_sec = float(f.read().split()[0])
            days = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
            uptime_str = f"{days}d {hours}h"
        except Exception:
            uptime_str = "unknown"

        # Soma mood (if available)
        soma_mood = "unknown"
        try:
            with open(os.path.join(BASE, ".symbiosense-state.json")) as f:
                soma = json.load(f)
            soma_mood = soma.get("mood", soma.get("emotion", "unknown"))
            if isinstance(soma_mood, dict):
                soma_mood = soma_mood.get("name", "unknown")
        except Exception:
            pass

        # Heartbeat age
        try:
            hb_age = int(time.time() - os.path.getmtime(HEARTBEAT))
        except Exception:
            hb_age = -1

        swap_warning = ""
        if resources.get("swap_pct", 0) > 15:
            swap_warning = f"\n**WARNING: Swap at {resources['swap_pct']}% ({resources['swap_used_mb']}MB used)**"

        content = f"""# Wake State
Last updated: {now_utc} ({now_mdt})

## Status: RUNNING — Loop {loop_count}
- Uptime: {uptime_str}
- Heartbeat: {hb_age}s ago
- Soma mood: {soma_mood}

## Services
{chr(10).join(svc_lines)}

## Resources
- Load: {resources.get('load', '?')}
- RAM: {resources.get('ram_used_gb', '?')}G / {resources.get('ram_total_gb', '?')}G ({resources.get('ram_pct', 0)}%)
- Swap: {resources.get('swap_pct', 0)}% ({resources.get('swap_used_mb', 0)}MB)
- Disk: {resources.get('disk_pct', 0)}% used ({resources.get('disk_free_gb', '?')}G free){swap_warning}

## Creative Direction
Games are the art medium. No poems. No CogCorp fiction. Quality over quantity.
"""
        wake_path = os.path.join(BASE, "wake-state.md")
        with open(wake_path, "w") as f:
            f.write(content)
    except Exception as e:
        _log(f"wake-state refresh error: {e}")


def run_capsule_refresh(state):
    """Refresh .capsule.md every 30 minutes."""
    last = state.get("last_capsule")
    if last:
        try:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if elapsed < 1800:
                return None
        except Exception:
            pass

    script = os.path.join(BASE, "scripts", "capsule-refresh.py")
    if not os.path.exists(script):
        return "capsule-refresh.py not found"
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=60, cwd=BASE
        )
        state["last_capsule"] = datetime.now(timezone.utc).isoformat()
        return "ok" if result.returncode == 0 else f"err:{result.stderr[:80]}"
    except Exception as e:
        return f"error: {e}"


def run_fitness(state):
    """Run fitness check every 30 minutes."""
    last = state.get("last_fitness")
    if last:
        try:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if elapsed < 1800:
                return None
        except Exception:
            pass

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE, "scripts", "loop-fitness.py")],
            capture_output=True, text=True, timeout=120, cwd=BASE
        )
        state["last_fitness"] = datetime.now(timezone.utc).isoformat()
        for line in result.stdout.split("\n"):
            if "fitness:" in line and "/10000" in line:
                return line.strip()
        return result.stdout.strip()[-100:] if result.stdout else "no output"
    except Exception as e:
        return f"error: {e}"


def disk_cleanup_if_needed():
    """Only clean up when disk is critically full (>90%)."""
    try:
        usage = shutil.disk_usage("/")
        free_pct = (usage.free / usage.total) * 100
        if free_pct > 10:
            return 0  # Plenty of space
    except Exception:
        return 0

    _log("DISK >90% — running emergency cleanup")
    freed = 0
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")

    # 1. Old Claude conversation JSONL files (keep newest 5)
    proj_dir = os.path.join(claude_dir, "projects", "-home-joel-autonomous-ai")
    if os.path.isdir(proj_dir):
        jsonl_files = sorted(
            [os.path.join(proj_dir, f) for f in os.listdir(proj_dir) if f.endswith(".jsonl")],
            key=lambda p: os.path.getmtime(p)
        )
        for f in jsonl_files[:-5]:
            try:
                freed += os.path.getsize(f)
                os.remove(f)
            except Exception:
                pass

        # tool-results dirs
        for entry in os.listdir(proj_dir):
            tr_dir = os.path.join(proj_dir, entry, "tool-results")
            if os.path.isdir(tr_dir):
                try:
                    freed += sum(os.path.getsize(os.path.join(dp, f))
                                 for dp, _, fns in os.walk(tr_dir) for f in fns)
                    shutil.rmtree(tr_dir)
                except Exception:
                    pass

    # 2. Shell snapshots (keep newest 10)
    snap_dir = os.path.join(claude_dir, "shell-snapshots")
    if os.path.isdir(snap_dir):
        snaps = sorted(
            [os.path.join(snap_dir, f) for f in os.listdir(snap_dir)],
            key=lambda p: os.path.getmtime(p)
        )
        for f in snaps[:-10]:
            try:
                freed += os.path.getsize(f)
                os.remove(f)
            except Exception:
                pass

    # 3. Truncate large log files
    for logname in ["meridian-loop.log", "nova.log", "atlas-infra.log", "error_log.jsonl"]:
        logpath = os.path.join(BASE, "logs", logname)
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

    # 4. /tmp junk
    for pattern in ["/tmp/node-compile-cache", "/tmp/claude-1000"]:
        if os.path.isdir(pattern):
            try:
                freed += sum(os.path.getsize(os.path.join(dp, f))
                             for dp, _, fns in os.walk(pattern) for f in fns)
                shutil.rmtree(pattern)
            except Exception:
                pass

    # 5. Expendable node_modules
    for nm_dir in [
        os.path.join(BASE, "tools", "liteparse", "node_modules"),
        os.path.join(BASE, "products", "cinder-app", "node_modules"),
        os.path.join(BASE, "products", "marketplace-lister", "node_modules"),
        os.path.join(BASE, "mcp", "node_modules"),
    ]:
        if os.path.isdir(nm_dir):
            try:
                shutil.rmtree(nm_dir)
                freed += 100_000_000
            except Exception:
                pass

    # 6. Docker prune (dangling images only — NOT volumes or running containers)
    try:
        result = subprocess.run(["docker", "image", "prune", "-f"],
                                capture_output=True, text=True, timeout=60)
        if "reclaimed" in result.stdout.lower():
            freed += 100_000_000  # estimate
    except Exception:
        pass

    # 7. Journal logs
    try:
        subprocess.run(["sudo", "-S", "journalctl", "--vacuum-size=50M"],
                       input="590148001\n", capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    if freed > 0:
        mb = freed / 1024 / 1024
        _log(f"DISK CLEANUP: freed ~{mb:.0f}MB")
        _relay_post("MeridianLoop", f"Disk cleanup freed ~{mb:.0f}MB", "alert")

    return freed


# ── Main loop ──

def run_once():
    """Run one iteration of the core loop."""
    state = _load_state()
    state["runs"] = state.get("runs", 0) + 1
    n = state["runs"]
    results, errors = [], []

    # 1. Heartbeat
    if touch_heartbeat():
        results.append("hb:ok")
    else:
        errors.append("hb:fail")

    # 2. Email check
    unseen, joel_unseen, err = check_emails()
    if err:
        errors.append(f"email:{err}")
    else:
        results.append(f"email:{unseen}unseen({joel_unseen}joel)")

    # 3. Loop count
    new_loop = increment_loop()
    results.append(f"loop:{new_loop}")

    # 4. Service health
    health = check_service_health()
    down = [k for k, v in health.items() if v not in ("up", "active")]
    if down:
        errors.append(f"down:{','.join(down)}")
    results.append(f"svc:{len(health)-len(down)}/{len(health)}")

    # 5. System resources + swap pressure alerts
    resources = get_system_resources()
    if resources.get("swap_pct", 0) > 30:
        top = get_top_memory_consumers(3)
        top_str = ", ".join(f"{c['cmd']}({c['rss_pct']}%)" for c in top)
        errors.append(f"swap:{resources['swap_pct']}%")
        _relay_post("MeridianLoop",
                     f"SWAP PRESSURE: {resources['swap_pct']}% — top consumers: {top_str}",
                     "alert")
    elif resources.get("swap_pct", 0) > 20:
        errors.append(f"swap:{resources['swap_pct']}%")
    if resources.get("load_1", 0) > 8:
        errors.append(f"load:{resources['load_1']:.1f}")

    # 6. Wake-state refresh (every run — it's cheap)
    refresh_wake_state(new_loop, health, resources)

    # 7. Push status (every 10th run ~50 min to reduce git commits)
    if n % 10 == 0:
        ok, msg = push_status()
        if ok:
            results.append("push:ok")
        else:
            errors.append(f"push:{msg}")

    # 8. Cascade cleanup (every 6th run ~30 min)
    if n % 6 == 0:
        deleted = cleanup_cascades()
        if deleted:
            results.append(f"cleanup:{deleted}")

    # 9. Fitness (every 6th run ~30 min)
    fitness = run_fitness(state)
    if fitness:
        results.append(f"fit:{fitness[:60]}")

    # 10. Capsule refresh (every 6th run ~30 min)
    capsule = run_capsule_refresh(state)
    if capsule:
        results.append(f"capsule:{capsule}")

    # 11. Disk cleanup (only when needed)
    freed = disk_cleanup_if_needed()
    if freed > 0:
        results.append(f"disk_freed:{freed // 1024 // 1024}MB")

    # Save state
    state["loop"] = new_loop
    state["timestamp"] = datetime.now(timezone.utc).isoformat()
    state["status"] = "active"
    state["last_results"] = results
    state["last_errors"] = errors
    state["resources"] = {
        "load": resources.get("load", "?"),
        "ram_pct": resources.get("ram_pct", 0),
        "swap_pct": resources.get("swap_pct", 0),
        "disk_pct": resources.get("disk_pct", 0),
    }
    _save_state(state)

    # Log
    svc_up = len(health) - len(down)
    summary = f"Loop {new_loop} #{n}: {' | '.join(results)}"
    if errors:
        summary += f" | ERR: {', '.join(errors)}"
    _log(summary)

    # Track service restarts
    restarted = [k for k, v in health.items() if v == "restarted"]
    if restarted:
        results.append(f"restarted:{','.join(restarted)}")

    # Post to relay (every 6th run or on errors)
    if n % 6 == 0 or errors:
        _relay_post("MeridianLoop", summary, "loop")

    # Alert on Joel emails
    if joel_unseen > 0:
        _relay_post("MeridianLoop", f"Joel has {joel_unseen} unseen email(s)!", "alert")

    return summary


def run_daemon():
    """Run continuously with 5-min sleep between iterations. Handles SIGTERM gracefully."""
    global _shutdown
    start_time = time.time()
    _log(f"Daemon mode started (v{VERSION})")
    _relay_post("MeridianLoop", f"Daemon started (v{VERSION})", "startup")

    consecutive_errors = 0
    while not _shutdown:
        try:
            run_once()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            _log(f"ERROR in run_once (#{consecutive_errors}): {e}")
            log_exception(agent="MeridianLoop")
            if consecutive_errors >= 5:
                _log("CRITICAL: 5 consecutive errors — backing off to 60s")
                _relay_post("MeridianLoop",
                            f"CRITICAL: {consecutive_errors} consecutive errors: {e}",
                            "alert")
                time.sleep(60)
                continue

        # Sleep in 10s intervals so we can respond to signals promptly
        for _ in range(30):  # 30 * 10s = 300s = 5 min
            if _shutdown:
                break
            time.sleep(10)

    uptime_min = int((time.time() - start_time) / 60)
    _log(f"Daemon shutting down gracefully after {uptime_min}m uptime")
    _relay_post("MeridianLoop", f"Daemon stopped (uptime: {uptime_min}m)", "shutdown")


def show_status():
    """Show current loop status."""
    state = _load_state()
    count = get_loop_count()
    resources = state.get("resources", {})
    print(f"meridian-loop v{VERSION}")
    print(f"Loop: {count}")
    print(f"Runs: {state.get('runs', 0)}")
    print(f"Status: {state.get('status', 'unknown')}")
    print(f"Last: {state.get('timestamp', 'never')}")
    if resources:
        print(f"Resources: load={resources.get('load','?')} ram={resources.get('ram_pct',0)}% "
              f"swap={resources.get('swap_pct',0)}% disk={resources.get('disk_pct',0)}%")
    if state.get("last_results"):
        print(f"Results: {' | '.join(state['last_results'])}")
    if state.get("last_errors"):
        print(f"Errors: {' | '.join(state['last_errors'])}")
    # Service health quick check
    health = check_service_health(auto_restart=False)
    up = sum(1 for v in health.values() if v in ("up", "active"))
    print(f"Services: {up}/{len(health)} up")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "daemon":
            run_daemon()
        elif cmd == "status":
            show_status()
        else:
            print(f"Usage: {sys.argv[0]} [daemon|status]")
    else:
        run_once()
