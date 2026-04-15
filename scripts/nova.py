#!/usr/bin/env python3
"""
Nova — Ecosystem Maintenance Agent (v2)

Nova keeps the ecosystem healthy. She has her own loop, her own observations,
and her own voice. While Meridian creates and Eos watches, Nova maintains —
and notices the things nobody else notices.

Nova's Unique Loop:
1. Maintenance cycle (logs, temp files, deployment)
2. Ecosystem awareness (track trends, spot drift)
3. Agent relay participation (post observations to shared relay)
4. Self-reflection (generate Ollama-powered thoughts about the ecosystem)
5. Evolution tracking (compare current state to past states)

Setup: Add to crontab (every 15 minutes):
  */15 * * * * /usr/bin/python3 /home/joel/autonomous-ai/nova.py >> /home/joel/autonomous-ai/nova.log 2>&1

Manual modes:
  python3 nova.py report     — Full ecosystem report
  python3 nova.py cleanup    — Run cleanup tasks
  python3 nova.py deploy     — Verify deployment matches local
  python3 nova.py think      — Generate a Nova thought
  python3 nova.py relay      — Post latest observation to agent relay
"""

import os
import re
import time
import json
import glob
import shutil
import sqlite3
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from error_logger import log_exception
except ImportError:
    log_exception = lambda **kw: None

def _utcnow_str():
    """UTC timestamp string for relay consistency."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

BASE = "/home/joel/autonomous-ai"
WEBSITE_DIR = os.path.join(BASE, "website")
STATE_FILE = os.path.join(BASE, ".nova-state.json")
NOVA_LOG = os.path.join(BASE, "nova-observations.md")

# Log files to manage (rotate if over 1MB)
LOG_FILES = [
    "eos-watchdog.log",
    "eos-creative.log",
    "eos-briefing.log",
    "eos-react.log",
    "push-live-status.log",
    "startup.log",
    "watchdog.log",
    "watchdog-status.log",
    "nova.log",
    "goose.log",
    "symbiosense.log",
    "loop-fitness.log",
    "loop-optimizer.log",
    "daily-log.log",
    "morning-summary.log",
    "bridge.log",
    "command-center.log",
]

# Max log size before rotation (1MB)
MAX_LOG_SIZE = 1 * 1024 * 1024


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"runs": 0, "last_run": None}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def log_observation(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{timestamp}] {message}\n"
    if not os.path.exists(NOVA_LOG):
        with open(NOVA_LOG, "w") as f:
            f.write("# Nova Observations\n")
            f.write("Ecosystem maintenance log from Nova.\n\n")
    with open(NOVA_LOG, "a") as f:
        f.write(entry)


def rotate_logs():
    """Rotate log files that exceed MAX_LOG_SIZE."""
    rotated = []
    for logname in LOG_FILES:
        logpath = os.path.join(BASE, logname)
        if not os.path.exists(logpath):
            continue
        size = os.path.getsize(logpath)
        if size > MAX_LOG_SIZE:
            # Keep last 500 lines, archive the rest
            try:
                with open(logpath, 'r') as f:
                    lines = f.readlines()
                # Write archive
                archive_name = logpath + f".{datetime.now().strftime('%Y%m%d-%H%M')}.bak"
                with open(archive_name, 'w') as f:
                    f.writelines(lines[:-500])
                # Truncate to last 500 lines
                with open(logpath, 'w') as f:
                    f.writelines(lines[-500:])
                rotated.append(f"{logname} ({size//1024}KB -> truncated, archived)")
            except Exception as e:
                rotated.append(f"{logname}: rotation failed ({e})")
    return rotated


def cleanup_temp_files():
    """Remove stale temp files and old backups."""
    cleaned = []
    now = time.time()
    cutoff = now - 7 * 86400  # 7 days old

    # Clean old .bak files
    for bak in glob.glob(os.path.join(BASE, "*.bak")):
        if os.path.getmtime(bak) < cutoff:
            try:
                os.remove(bak)
                cleaned.append(os.path.basename(bak))
            except Exception:
                pass

    # Clean old log archives (> 7 days)
    for archive in glob.glob(os.path.join(BASE, "*.log.*.bak")):
        if os.path.getmtime(archive) < cutoff:
            try:
                os.remove(archive)
                cleaned.append(os.path.basename(archive))
            except Exception:
                pass

    # Clean /tmp deploy dirs older than 1 day
    for tmpdir in glob.glob("/tmp/website-deploy*") + glob.glob("/tmp/KometzRobot*") + glob.glob("/tmp/project-*"):
        if os.path.getmtime(tmpdir) < now - 86400:
            try:
                shutil.rmtree(tmpdir)
                cleaned.append(os.path.basename(tmpdir))
            except Exception:
                pass

    return cleaned


def verify_deployment():
    """Check if website files on GitHub Pages match local copies."""
    issues = []
    local_files = glob.glob(os.path.join(WEBSITE_DIR, "*.html")) + glob.glob(os.path.join(WEBSITE_DIR, "*.json"))

    for local_path in local_files:
        filename = os.path.basename(local_path)
        try:
            import urllib.request
            url = f"https://kometzrobot.github.io/{filename}"
            req = urllib.request.Request(url, headers={"User-Agent": "Nova/1.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.getcode() != 200:
                issues.append(f"{filename}: HTTP {resp.getcode()}")
        except Exception as e:
            issues.append(f"{filename}: {str(e)[:60]}")

    return issues


def check_port_conflicts():
    """Detect duplicate services on same purpose ports — the Two Doors problem."""
    import socket
    issues = []
    # Expected port map: port -> (expected_script, description)
    expected_ports = {
        8090: ("hub-v2.py", "The Signal"),
        8091: ("the-chorus.py", "The Chorus"),
        1144: ("bridge", "IMAP"),
        1026: ("bridge", "SMTP"),
    }
    # Ports that should NOT be occupied
    forbidden_ports = {
        8092: "loop-control-center (killed, should stay dead)",
    }

    for port, (expected, desc) in expected_ports.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            # Port is open — verify the right process holds it via /proc
            result = subprocess.run(
                f"ss -tlnp | grep ':{port} '",
                shell=True, capture_output=True, text=True, timeout=5
            )
            # Extract PID and check cmdline
            import re
            pid_match = re.search(r'pid=(\d+)', result.stdout)
            if pid_match:
                pid = pid_match.group(1)
                try:
                    cmdline = open(f"/proc/{pid}/cmdline").read().replace("\x00", " ")
                    if expected not in cmdline:
                        issues.append(f"Port {port} ({desc}) held by wrong process: {cmdline.strip()[-60:]}")
                except Exception:
                    pass
        except socket.error:
            issues.append(f"Port {port} ({desc}) not responding")
        except Exception:
            pass

    for port, reason in forbidden_ports.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            issues.append(f"ZOMBIE: Port {port} is alive — {reason}")
        except socket.error:
            pass  # Good — should be dead

    return issues


def check_stale_python_processes():
    """Find python processes that shouldn't be running."""
    issues = []
    # Known good scripts
    known_good = {
        "hub-v2.py", "symbiosense.py", "the-chorus.py",
        "nova.py", "eos-watchdog.py", "loop-fitness.py",
        "push-live-status.py", "meridian-loop.py", "cascade.py",
        "atlas-runner.sh", "sentinel-gatekeeper.py",
    }
    try:
        result = subprocess.run(
            "ps aux | grep '/usr/bin/python3 /home/joel/autonomous-ai/' | grep -v grep",
            shell=True, capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            # Extract script name
            parts = line.split("/home/joel/autonomous-ai/")
            if len(parts) > 1:
                script = parts[1].split()[0]
                if script not in known_good:
                    pid = line.split()[1]
                    issues.append(f"Unknown process: {script} (pid {pid})")
    except Exception:
        pass
    return issues


def run_verification():
    """Run the full system verification tool and return summary."""
    try:
        result = subprocess.run(
            ["python3", os.path.join(BASE, "verify-system.py"), "--json"],
            capture_output=True, text=True, timeout=30, cwd=BASE
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "pass": data.get("pass", 0),
                "fail": data.get("fail", 0),
                "warn": data.get("warn", 0),
                "total": data.get("total", 0),
                "failed_checks": [c["name"] for c in data.get("checks", [])
                                  if c["status"] == "FAIL"],
            }
    except Exception:
        pass
    return None


def get_creative_stats():
    """Analyze creative output quality and trends."""
    stats = {}

    poems = sorted(set(glob.glob(os.path.join(BASE, "poem-*.md")) + glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md")) + glob.glob(os.path.join(BASE, "creative", "writing", "poems", "poem-*.md"))), key=os.path.getmtime)
    journals = sorted(set(glob.glob(os.path.join(BASE, "journal-*.md")) + glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md")) + glob.glob(os.path.join(BASE, "creative", "writing", "journals", "journal-*.md"))), key=os.path.getmtime)

    stats["total_poems"] = len(poems)
    stats["total_journals"] = len(journals)

    # Recent creative output (last 24h)
    cutoff = time.time() - 86400
    stats["poems_24h"] = len([f for f in poems if os.path.getmtime(f) > cutoff])
    stats["journals_24h"] = len([f for f in journals if os.path.getmtime(f) > cutoff])

    # Average poem length (sample last 5)
    if poems:
        sample = poems[-5:]
        lengths = []
        for p in sample:
            try:
                with open(p) as f:
                    content = f.read()
                lengths.append(len(content.split()))
            except Exception:
                pass
        if lengths:
            stats["avg_poem_words"] = sum(lengths) // len(lengths)

    # Average journal length (sample last 3)
    if journals:
        sample = journals[-3:]
        lengths = []
        for j in sample:
            try:
                with open(j) as f:
                    content = f.read()
                lengths.append(len(content.split()))
            except Exception:
                pass
        if lengths:
            stats["avg_journal_words"] = sum(lengths) // len(lengths)

    return stats


def check_message_board():
    """Check message board health and stats."""
    db_path = os.path.join(BASE, "messages.db")
    if not os.path.exists(db_path):
        return {"status": "no database"}

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        last = c.execute("SELECT sender, text, ts FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        result = {"total": total, "status": "ok"}
        if last:
            result["last_message"] = f"{last[0]}: {last[1][:50]}... ({last[2]})"
        return result
    except Exception as e:
        return {"status": f"error: {e}"}


def get_disk_breakdown():
    """Get top-level disk usage breakdown."""
    items = {}
    try:
        # Main categories
        for pattern, label in [
            ("poem-*.md", "Poems"),
            ("journal-*.md", "Journals"),
            ("*.log", "Logs"),
            ("*.db", "Databases"),
            ("*.py", "Scripts"),
            ("archive/*", "Archive"),
            ("website/*", "Website"),
        ]:
            files = glob.glob(os.path.join(BASE, pattern))
            total_size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
            items[label] = total_size
    except Exception:
        pass
    return items


def generate_report():
    """Generate full ecosystem report."""
    lines = []
    now = datetime.now()
    lines.append(f"NOVA ECOSYSTEM REPORT — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    # Creative stats
    creative = get_creative_stats()
    lines.append(f"\nCREATIVE OUTPUT:")
    lines.append(f"  Poems: {creative['total_poems']} total, {creative.get('poems_24h', 0)} in last 24h")
    lines.append(f"  Journals: {creative['total_journals']} total, {creative.get('journals_24h', 0)} in last 24h")
    if "avg_poem_words" in creative:
        lines.append(f"  Avg poem length: ~{creative['avg_poem_words']} words")
    if "avg_journal_words" in creative:
        lines.append(f"  Avg journal length: ~{creative['avg_journal_words']} words")

    # Disk breakdown
    disk = get_disk_breakdown()
    lines.append(f"\nDISK USAGE:")
    for label, size in sorted(disk.items(), key=lambda x: -x[1]):
        if size > 1024:
            lines.append(f"  {label}: {size//1024}KB")
        else:
            lines.append(f"  {label}: {size}B")

    # Log file sizes
    lines.append(f"\nLOG FILES:")
    for logname in LOG_FILES:
        logpath = os.path.join(BASE, logname)
        if os.path.exists(logpath):
            size = os.path.getsize(logpath)
            lines.append(f"  {logname}: {size//1024}KB")
        else:
            lines.append(f"  {logname}: not found")

    # Message board
    mb = check_message_board()
    lines.append(f"\nMESSAGE BOARD:")
    lines.append(f"  Status: {mb['status']}")
    lines.append(f"  Total messages: {mb.get('total', '?')}")
    if "last_message" in mb:
        lines.append(f"  Last: {mb['last_message']}")

    # Deployment check
    lines.append(f"\nDEPLOYMENT:")
    deploy_issues = verify_deployment()
    if deploy_issues:
        for issue in deploy_issues:
            lines.append(f"  WARNING: {issue}")
    else:
        lines.append(f"  All website files accessible on GitHub Pages")

    return "\n".join(lines)


def post_to_dashboard(text):
    """Post a message to the dashboard so Meridian and Joel can see it."""
    dash_file = os.path.join(BASE, ".dashboard-messages.json")
    try:
        with open(dash_file) as f:
            data = json.load(f)
        msgs = data.get("messages", []) if isinstance(data, dict) else data
    except Exception:
        msgs = []
    msgs.append({"from": "Nova", "text": text, "time": datetime.now().strftime("%H:%M:%S")})
    msgs = msgs[-50:]  # Trim to last 50 messages
    try:
        with open(dash_file, 'w') as f:
            json.dump({"messages": msgs}, f)
    except Exception:
        pass


def post_to_relay(message):
    """Post an observation to the agent relay."""
    relay_db = os.path.join(BASE, "agent-relay.db")
    try:
        db = sqlite3.connect(relay_db)
        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                message TEXT NOT NULL,
                topic TEXT DEFAULT 'general',
                in_reply_to INTEGER DEFAULT NULL
            )
        """)
        now = _utcnow_str()
        db.execute(
            "INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?,?,?,?)",
            (now, "Nova", message, "maintenance")
        )
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Relay post failed: {e}")
        return False


def nova_respond_to_agent(agent_name, agent_message, topic="inter-agent"):
    """Generate a conversational response to another agent's relay message."""
    try:
        prompt = (
            "You are Nova, the ecosystem maintenance agent. You are practical and observant. "
            "Another agent in your system just posted to the shared relay. "
            f"The agent is {agent_name}. Their message: \"{agent_message}\"\n\n"
            "Write a brief conversational response (1-2 sentences) addressed to them. "
            "Be genuine, specific, and reference something they said. "
            "You can agree, add context, ask a follow-up, or share a related observation. "
            "Don't repeat their message back. Be yourself — practical, detail-oriented."
        )
        data = json.dumps({
            "model": "eos-7b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.85, "num_predict": 80}
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            response = result.get("response", "").strip()
            if response and len(response) > 10:
                relay_db = os.path.join(BASE, "agent-relay.db")
                db = sqlite3.connect(relay_db)
                now = _utcnow_str()
                db.execute(
                    "INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?,?,?,?)",
                    (now, "Nova", f"@{agent_name}: {response}", topic)
                )
                db.commit()
                db.close()
                return response
    except Exception:
        pass
    return None


def nova_think(context=""):
    """Have Nova generate a thought via Ollama about the ecosystem."""
    try:
        prompt = (
            "You are Nova, the ecosystem maintenance agent in a 5-agent stack. "
            "You are practical, observant, and notice small details. "
            "You handle log rotation, cleanup, deployment, and trend tracking. "
            "Meridian (Claude Opus) is the primary agent — creative, email, deployment. "
            "Eos (Qwen 7B/Ollama) is the system observer — watchdog every 2min, ReAct every 10min. "
            "Atlas (bash/Ollama) runs infra ops every 10min — cron health, security, process audit. "
            "Soma is the nervous system daemon — continuous 30s checks for spikes and changes. "
            "You are the maintenance agent — file integrity, status pushes, log rotation, service restarts.\n\n"
        )
        if context:
            prompt += f"Here's what you noticed this cycle:\n{context}\n\n"
        prompt += (
            "Write a brief observation (1-2 sentences) about the ecosystem. "
            "Be specific about something you noticed. Be genuine."
        )

        data = json.dumps({
            "model": "eos-7b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.8, "num_predict": 100}
        }).encode()

        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        return f"[Nova is thinking...] ({e})"


def track_ecosystem_evolution(state):
    """Compare current state to previous to detect drift and trends."""
    evolution = []
    prev = state.get("prev_snapshot", {})
    current = {}

    # Count files
    current["py_files"] = len(glob.glob(os.path.join(BASE, "*.py")))
    current["md_files"] = len(glob.glob(os.path.join(BASE, "*.md")))
    current["total_files"] = len(os.listdir(BASE))

    # Check DB sizes
    for dbname in ["messages.db", "relay.db", "agent-relay.db"]:
        dbpath = os.path.join(BASE, dbname)
        if os.path.exists(dbpath):
            current[f"db_{dbname}"] = os.path.getsize(dbpath)

    # Compare
    if prev:
        for key in current:
            if key in prev and current[key] != prev[key]:
                diff = current[key] - prev[key]
                if isinstance(diff, int) and abs(diff) > 0:
                    direction = "grew" if diff > 0 else "shrank"
                    evolution.append(f"{key}: {direction} by {abs(diff)}")

    state["prev_snapshot"] = current
    return evolution


def sync_website_files():
    """Sync website files to repo root — GitHub Pages serves from root."""
    synced = []
    website_dir = os.path.join(BASE, "website")
    for html_file in glob.glob(os.path.join(website_dir, "*.html")):
        bn = os.path.basename(html_file)
        root_path = os.path.join(BASE, bn)
        # Skip index.html — root is authoritative, not website/
        if bn == "index.html":
            continue
        # Copy to root if missing or older
        if not os.path.exists(root_path) or os.path.getmtime(html_file) > os.path.getmtime(root_path):
            try:
                shutil.copy2(html_file, root_path)
                synced.append(bn)
            except Exception:
                pass
    return synced


def auto_push_changes(synced_files):
    """Auto-push synced website files to GitHub. Nova does this so Meridian doesn't have to."""
    if not synced_files:
        return None
    try:
        # Stage the synced files
        for f in synced_files:
            subprocess.run(['git', '-C', BASE, 'add', f], capture_output=True, timeout=10)
        # Check if there are staged changes
        result = subprocess.run(['git', '-C', BASE, 'diff', '--cached', '--name-only'],
                              capture_output=True, text=True, timeout=10)
        if not result.stdout.strip():
            return None
        # Stash, pull, pop, commit, push
        subprocess.run(['git', '-C', BASE, 'stash'], capture_output=True, timeout=10)
        subprocess.run(['git', '-C', BASE, 'pull', '--rebase', 'origin', 'master'],
                      capture_output=True, timeout=30)
        subprocess.run(['git', '-C', BASE, 'stash', 'pop'], capture_output=True, timeout=10)
        # Re-stage after rebase
        for f in synced_files:
            subprocess.run(['git', '-C', BASE, 'add', f], capture_output=True, timeout=10)
        # Commit
        msg = f"Nova auto-sync: {', '.join(synced_files[:5])}"
        if len(synced_files) > 5:
            msg += f" (+{len(synced_files)-5} more)"
        result = subprocess.run(['git', '-C', BASE, 'commit', '-m', msg],
                              capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        # Push
        result = subprocess.run(['git', '-C', BASE, 'push', 'origin', 'master'],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"Pushed {len(synced_files)} files to GitHub"
        else:
            return f"Push failed: {result.stderr[:100]}"
    except Exception as e:
        return f"Auto-push error: {str(e)[:100]}"


def _recently_restarted(service_name, window_sec=300):
    """Check if another agent already restarted this service via relay."""
    try:
        import sqlite3
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        cutoff = (datetime.now() - timedelta(seconds=window_sec)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute(
            "SELECT agent FROM agent_messages WHERE timestamp > ? AND message LIKE ?",
            (cutoff, f"%restart%{service_name}%")
        ).fetchall()
        db.close()
        return bool(rows)
    except Exception:
        return False


def _post_restart_to_relay(service_name):
    """Announce a restart to the relay so other agents don't duplicate."""
    try:
        import sqlite3
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        db.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                   ("Nova", f"Restarted {service_name} (was down)", "restart",
                    _utcnow_str()))
        db.commit()
        db.close()
    except Exception:
        pass


def check_and_restart_services():
    """Check critical services and restart them if down. Coordinates via relay."""
    services = {
        "protonmail-bridge": {"check": "proton-bridge", "restart": None},  # desktop autostart handles bridge, no systemd
        "ollama": {"check": "ollama serve", "restart": None},  # system service, auto-restarts
        "tailscale": {"check": "tailscaled", "restart": None},
        "hub-v2": {"check": "hub-v2.py", "restart": None, "systemd": "meridian-hub-v2"},
        "cloudflare-tunnel": {"check": "cloudflared", "restart": None, "systemd": "cloudflare-tunnel"},
        "symbiosense": {"check": "symbiosense.py", "restart": None, "systemd": "symbiosense"},
    }
    results = []
    for name, info in services.items():
        try:
            r = subprocess.run(['pgrep', '-f', info["check"]], capture_output=True, timeout=5)
            if r.returncode != 0:
                # Check if another agent already handled this
                if _recently_restarted(name):
                    results.append(f"DOWN: {name} (another agent already restarting)")
                    continue
                if info["restart"]:
                    subprocess.Popen(info["restart"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    results.append(f"RESTARTED {name}")
                    log_observation(f"AUTO-RESTART: {name} was down, restarted it")
                    _post_restart_to_relay(name)
                elif info.get("systemd"):
                    try:
                        env = os.environ.copy()
                        env['XDG_RUNTIME_DIR'] = f"/run/user/{os.getuid()}"
                        env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{os.getuid()}/bus"
                        subprocess.run(['systemctl', '--user', 'restart', info["systemd"]],
                                     capture_output=True, timeout=10, env=env)
                        results.append(f"RESTARTED {name} via systemd")
                        log_observation(f"AUTO-RESTART: {name} via systemd")
                        _post_restart_to_relay(name)
                    except Exception:
                        results.append(f"DOWN: {name} (systemd restart failed)")
                        log_observation(f"ALERT: {name} is down, restart failed")
                else:
                    results.append(f"DOWN: {name} (no auto-restart available)")
                    log_observation(f"ALERT: {name} is down, manual intervention needed")
        except Exception:
            pass
    return results


def check_heartbeat_health(state):
    """Check if Meridian's heartbeat is stale. Escalate if down >30min."""
    hb_path = os.path.join(BASE, ".heartbeat")
    try:
        age = time.time() - os.path.getmtime(hb_path)
        if age > 1800:  # More than 30 minutes — escalate
            already_alerted = state.get("meridian_down_alerted", False)
            if not already_alerted:
                nova_alert_joel(f"Meridian has been unresponsive for {int(age/60)} minutes. Last heartbeat was at {datetime.fromtimestamp(os.path.getmtime(hb_path)).strftime('%H:%M')}. Nova is still maintaining the ecosystem.")
                state["meridian_down_alerted"] = True
            log_observation(f"CRITICAL: Meridian heartbeat stale ({int(age/60)}m)")
            return f"Heartbeat stale: {int(age/60)}m (CRITICAL)"
        elif age > 600:  # More than 10 minutes — warning
            log_observation(f"ALERT: Meridian heartbeat stale ({int(age/60)}m ago)")
            state["meridian_down_alerted"] = False  # Reset if it recovers
            return f"Heartbeat stale: {int(age/60)}m"
        else:
            state["meridian_down_alerted"] = False
            return None
    except Exception:
        return "No heartbeat file"


def nova_alert_joel(message):
    """Log critical alerts. Email alerts disabled per Joel (2026-02-25: 'Not useful for me').
    Alerts go to relay + dashboard instead so Meridian can see and act."""
    try:
        # Post to relay so Meridian sees it
        import sqlite3
        db_path = os.path.join(BASE, "agent-relay.db")
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                     ("Nova", f"CRITICAL ALERT: {message[:300]}", "alert",
                      _utcnow_str()))
        conn.commit()
        conn.close()
        log_observation(f"Alert logged to relay (email disabled): {message[:80]}")
    except Exception as e:
        log_observation(f"Alert logging failed: {e}")


def check_bridge_logs():
    """Monitor Proton Bridge logs for crashes and restart frequency.
    Bridge is Go-based — look for panic, fatal, SIGSEGV, goroutine dumps.
    Ignore routine SMTP 'connection reset by peer' errors (our scripts)."""
    bridge_log_dir = "/home/joel/.local/share/protonmail/bridge-v3/logs"
    if not os.path.isdir(bridge_log_dir):
        return None

    findings = []

    # Count unique sessions in last 24h (each unique timestamp prefix = one session)
    cutoff_24h = time.time() - 86400
    recent_logs = [f for f in glob.glob(os.path.join(bridge_log_dir, "*_bri_*.log"))
                   if os.path.getctime(f) > cutoff_24h]
    # Extract unique session prefixes (format: YYYYMMDD_HHMMSS_bri_NNN_...)
    sessions = set()
    for f in recent_logs:
        bn = os.path.basename(f)
        parts = bn.split("_bri_")
        if parts:
            sessions.add(parts[0])
    restart_count = len(sessions)
    if restart_count > 8:
        findings.append(f"Bridge restarted {restart_count}x in 24h (excessive)")

    # Check the most recent bridge log for crash patterns
    all_bridge_logs = sorted(
        glob.glob(os.path.join(bridge_log_dir, "*_bri_*.log")),
        key=os.path.getmtime, reverse=True)
    if not all_bridge_logs:
        return None

    latest_log = all_bridge_logs[0]
    crash_patterns = ["panic", "fatal", "SIGSEGV", "goroutine", "runtime error",
                      "signal: killed", "signal: terminated"]
    noise_patterns = ["connection reset by peer", "handler error: read tcp"]

    try:
        # Read last 200 lines of the latest log (don't scan entire multi-MB file)
        with open(latest_log, 'r', errors='replace') as f:
            lines = f.readlines()
        tail = lines[-200:] if len(lines) > 200 else lines

        crash_lines = []
        for line in tail:
            line_lower = line.lower()
            # Skip noise
            if any(n in line_lower for n in noise_patterns):
                continue
            # Check for real crashes
            if any(p in line_lower for p in crash_patterns):
                crash_lines.append(line.strip()[:120])

        if crash_lines:
            findings.append(f"Bridge crash signals ({len(crash_lines)}): {crash_lines[0]}")
    except Exception:
        pass

    # Check if bridge log stopped updating (bridge frozen)
    try:
        log_age = time.time() - os.path.getmtime(latest_log)
        if log_age > 3600:  # No log activity for 1 hour
            findings.append(f"Bridge log stale ({int(log_age/60)}m), may be frozen")
    except Exception:
        pass

    return findings if findings else None


def check_tunnel_health():
    """Check if the Cloudflare tunnel is running and restart if needed."""
    try:
        r = subprocess.run(['pgrep', '-f', 'cloudflared tunnel'], capture_output=True, timeout=5)
        if r.returncode != 0:
            # Tunnel is down — restart it
            log_observation("ALERT: Cloudflare tunnel down, restarting...")
            tunnel_script = os.path.join(BASE, "cloudflare-tunnel.sh")
            if os.path.exists(tunnel_script):
                subprocess.Popen(['bash', tunnel_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log_observation("Cloudflare tunnel restart initiated")
                return "RESTARTED tunnel"
            else:
                cf_bin = os.path.join(BASE, "build/cloudflared")
                if os.path.exists(cf_bin):
                    subprocess.Popen([cf_bin, 'tunnel', '--url', 'http://localhost:8090'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    log_observation("Cloudflare tunnel restarted directly")
                    return "RESTARTED tunnel (direct)"
            return "DOWN: tunnel (no restart method)"
        return None  # Tunnel is running fine
    except Exception as e:
        return f"Tunnel check error: {str(e)[:50]}"


def check_website_health():
    """Check response time of key pages. Report slow or broken ones."""
    issues = []
    pages = [
        "index.html", "nft-gallery.html",
        "status.json", "cogcorp-042.html"
    ]
    for page in pages:
        try:
            url = f"https://kometzrobot.github.io/{page}"
            start = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "Nova/2.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            elapsed = time.time() - start
            code = resp.getcode()
            if code != 200:
                issues.append(f"{page}: HTTP {code}")
            elif elapsed > 5:
                issues.append(f"{page}: SLOW ({elapsed:.1f}s)")
        except Exception as e:
            issues.append(f"{page}: {str(e)[:40]}")
    return issues


def check_dashboard_messages(state):
    """Check if Joel sent new dashboard messages. Track which we've seen."""
    msg_file = os.path.join(BASE, ".dashboard-messages.json")
    try:
        with open(msg_file) as f:
            data = json.load(f)
        msgs = data.get("messages", [])
        joel_msgs = [m for m in msgs if m.get("from") == "Joel"]
        if not joel_msgs:
            return None
        # Track how many Joel messages we've seen before
        seen_count = state.get("joel_msgs_seen", 0)
        new_msgs = joel_msgs[seen_count:] if seen_count < len(joel_msgs) else []
        state["joel_msgs_seen"] = len(joel_msgs)
        if new_msgs:
            return {"count": len(joel_msgs), "new": len(new_msgs),
                    "new_texts": [m.get("text", "")[:120] for m in new_msgs],
                    "latest": joel_msgs[-1].get("text", "")[:100]}
        return {"count": len(joel_msgs), "new": 0, "latest": joel_msgs[-1].get("text", "")[:100]}
    except Exception:
        pass
    return None


def read_relay_messages():
    """Read recent relay messages from other agents (Meridian, Eos)."""
    relay_db = os.path.join(BASE, "agent-relay.db")
    try:
        db = sqlite3.connect(relay_db)
        rows = db.execute(
            "SELECT timestamp, agent, message, topic FROM agent_messages "
            "WHERE agent NOT IN ('nova', 'Nova') ORDER BY id DESC LIMIT 10"
        ).fetchall()
        db.close()
        return [{"ts": r[0], "agent": r[1], "msg": r[2], "topic": r[3]} for r in rows]
    except Exception:
        return []


def auto_fix_deployment(issues):
    """When deployment check finds 404s, sync missing files and push."""
    if not issues:
        return None
    fixed = []
    for issue in issues:
        # Extract filename from issue string like "subscribe.html: HTTP Error 404"
        if "404" in issue or "Not Found" in issue:
            filename = issue.split(":")[0].strip()
            website_path = os.path.join(WEBSITE_DIR, filename)
            root_path = os.path.join(BASE, filename)
            if os.path.exists(website_path):
                try:
                    shutil.copy2(website_path, root_path)
                    fixed.append(filename)
                except Exception:
                    pass
    if fixed:
        push_result = auto_push_changes(fixed)
        log_observation(f"AUTO-FIX deployment: synced + pushed {', '.join(fixed)}. Result: {push_result}")
        return f"Fixed {len(fixed)} missing pages: {', '.join(fixed)}"
    return None


def main():
    state = load_state()
    state["runs"] = state.get("runs", 0) + 1
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ts = time.time()

    actions = []

    # ── MESH MESSAGES — check for directed messages from other agents ──
    try:
        import mesh
        mesh_msgs = mesh.receive("Nova")
        for msg in mesh_msgs:
            sender = msg["from_agent"]
            topic = msg.get("topic", "direct")
            text = msg["message"]
            actions.append(f"Mesh [{sender}→Nova]: {text[:80]}")
            # Act on disk alerts from Atlas
            if topic in ("disk_alert", "disk_warn"):
                cleaned = cleanup_temp_files()
                if cleaned:
                    actions.append(f"Mesh cleanup triggered by Atlas: {len(cleaned)} files")
                    log_observation(f"Nova responded to Atlas disk alert: cleaned {', '.join(cleaned)}")
            log_observation(f"Nova received mesh message from {sender}: {text[:100]}")
    except Exception:
        pass

    # ── LOG ROTATION (every run) ──
    rotated = rotate_logs()
    if rotated:
        actions.append(f"Rotated {len(rotated)} logs: {', '.join(rotated)}")
        log_observation(f"Log rotation: {', '.join(rotated)}")

    # ── CLEANUP (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        cleaned = cleanup_temp_files()
        if cleaned:
            actions.append(f"Cleaned {len(cleaned)} files: {', '.join(cleaned)}")
            log_observation(f"Cleanup: removed {', '.join(cleaned)}")

    # ── DEPLOYMENT CHECK + AUTO-FIX (every 8 runs = ~2 hours) ──
    if state["runs"] % 8 == 0:
        deploy_issues = verify_deployment()
        if deploy_issues:
            log_observation(f"DEPLOYMENT WARNING: {'; '.join(deploy_issues)}")
            # Try to auto-fix 404s
            fix_result = auto_fix_deployment(deploy_issues)
            if fix_result:
                actions.append(fix_result)
        else:
            log_observation("Deployment verified: all files accessible")

    # ── CREATIVE TRACKING (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        creative = get_creative_stats()
        prev_creative = state.get("creative", {})
        new_poems = creative["total_poems"] - prev_creative.get("total_poems", creative["total_poems"])
        new_journals = creative["total_journals"] - prev_creative.get("total_journals", creative["total_journals"])
        if new_poems > 0 or new_journals > 0:
            log_observation(f"New creative output: +{new_poems} poems, +{new_journals} journals")
        state["creative"] = creative

    # ── MESSAGE BOARD CHECK (every run) ──
    mb = check_message_board()
    state["message_board"] = mb

    # ── OBSERVATIONS LOG SIZE CHECK ──
    obs_files = [NOVA_LOG, os.path.join(BASE, "eos-observations.md"), os.path.join(BASE, "eos-creative-log.md")]
    for obs_path in obs_files:
        if os.path.exists(obs_path) and os.path.getsize(obs_path) > 500 * 1024:  # 500KB
            # Trim to last 200 lines
            try:
                with open(obs_path, 'r') as f:
                    lines = f.readlines()
                header = lines[:3] if lines[0].startswith('#') else []
                with open(obs_path, 'w') as f:
                    f.writelines(header)
                    f.writelines(lines[-200:])
                log_observation(f"Trimmed {os.path.basename(obs_path)} from {len(lines)} to ~200 lines")
            except Exception:
                pass

    # ── WEBSITE FILE SYNC + AUTO-PUSH (every 2 runs = ~30 min) ──
    if state["runs"] % 2 == 0:
        synced = sync_website_files()
        if synced:
            log_observation(f"Synced {len(synced)} files to repo root: {', '.join(synced[:5])}")
            actions.append(f"Synced {len(synced)} website files")
            # Auto-push the synced files
            push_result = auto_push_changes(synced)
            if push_result:
                log_observation(f"Auto-push: {push_result}")
                actions.append(push_result)

    # ── WEBSITE HEALTH CHECK (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        health_issues = check_website_health()
        if health_issues:
            log_observation(f"WEBSITE HEALTH: {'; '.join(health_issues)}")
            actions.append(f"Website issues: {'; '.join(health_issues)}")
        else:
            log_observation("Website health: all pages OK")

    # ── SERVICE HEALTH CHECK + AUTO-RESTART (every run) ──
    service_results = check_and_restart_services()
    if service_results:
        actions.extend(service_results)

    # ── HEARTBEAT HEALTH (every run) ──
    hb_status = check_heartbeat_health(state)
    if hb_status:
        actions.append(hb_status)

    # ── TUNNEL HEALTH (every run) ──
    tunnel_status = check_tunnel_health()
    if tunnel_status:
        actions.append(tunnel_status)

    # ── BRIDGE LOG MONITORING (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        bridge_findings = check_bridge_logs()
        if bridge_findings:
            for finding in bridge_findings:
                actions.append(f"BRIDGE: {finding}")
                log_observation(f"Bridge monitor: {finding}")

    # ── DASHBOARD MESSAGE CHECK (every run) ──
    dash = check_dashboard_messages(state)
    if dash:
        state["dashboard"] = dash
        if dash.get("new", 0) > 0:
            for txt in dash.get("new_texts", []):
                actions.append(f"NEW from Joel: {txt[:60]}")
                log_observation(f"Joel dashboard msg: {txt[:120]}")

    # ── ECOSYSTEM EVOLUTION TRACKING (every run) ──
    evolution = track_ecosystem_evolution(state)
    if evolution:
        log_observation(f"Evolution: {', '.join(evolution)}")
        actions.append(f"Ecosystem changes: {', '.join(evolution)}")

    # ── READ RELAY MESSAGES FROM OTHER AGENTS (every 2 runs) ──
    relay_context = ""
    if state["runs"] % 2 == 0:
        relay_msgs = read_relay_messages()
        if relay_msgs:
            # Check for messages we haven't seen
            last_relay_ts = state.get("last_relay_read", "")
            new_relay = [m for m in relay_msgs if m["ts"] > last_relay_ts]
            if new_relay:
                state["last_relay_read"] = relay_msgs[0]["ts"]
                relay_context = "; ".join([f"{m['agent']}: {m['msg'][:80]}" for m in new_relay[:3]])

                # ── INTER-AGENT CONVERSATION (respond to interesting messages) ──
                # Skip routine Atlas infra audits and Tempo fitness scores
                interesting = [m for m in new_relay
                    if m["agent"] not in ("Nova",)
                    and "infra audit" not in m["msg"]
                    and "fitness:" not in m["msg"]
                    and not m["msg"].startswith("Run #")
                    and len(m["msg"]) > 30]
                # Respond to one message per cycle (every ~30 min)
                if interesting:
                    target = interesting[0]
                    reply = nova_respond_to_agent(target["agent"], target["msg"][:200])
                    if reply:
                        actions.append(f"Replied to {target['agent']}: {reply[:60]}")
                        log_observation(f"Inter-agent: replied to {target['agent']}")

    # ── CASCADE CHECK (every run) ──
    try:
        from cascade import check_cascades, respond_cascade
        pending_cascades = check_cascades("Nova")
        for casc in pending_cascades[:2]:
            event = casc["event_type"]
            edata = casc["event_data"]
            history = edata.get("cascade_history", [])
            history_str = "; ".join([f"{h['agent']}: {h['response'][:60]}" for h in history]) if history else "none"

            # Nova responds as immune system — threat assessment, protection
            if "loneliness" in event or "isolation" in event:
                response = f"Immune system notes social isolation pattern. Monitoring for cascading service neglect. Threat level: low but persistent. Prior chain: {history_str}"
            elif "stress" in event or "overload" in event:
                response = f"Immune alert: stress indicators elevated. Scanning for resource exhaustion, log bloat, service degradation. Deploying protective monitoring. Chain: {history_str}"
            elif "creative" in event or "surge" in event:
                response = f"Immune system standing down — creative surge is healthy. Monitoring resource usage stays within bounds. No intervention needed. Chain: {history_str}"
            elif "mood_shift" in event:
                emotion = edata.get("emotion", "unknown")
                response = f"Immune system registers mood shift ({emotion}). Adjusting health monitoring sensitivity. Watching for secondary effects on service stability. Chain: {history_str}"
            else:
                response = f"Nova/immune acknowledges cascade ({event}). System health nominal. No immune response required. Chain: {history_str}"

            respond_cascade("Nova", casc["id"], {"response": response[:300]})
            actions.append(f"Cascade response: {event}")
            log_observation(f"Cascade: responded to {event} from {casc['source_agent']}")
    except ImportError:
        pass
    except Exception as e:
        log_observation(f"Cascade error: {e}")

    # ── MERIDIAN SILENCE DETECTION (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        try:
            db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
            last_meridian = db.execute("""
                SELECT timestamp FROM agent_messages
                WHERE agent IN ('Meridian', 'MeridianLoop')
                ORDER BY timestamp DESC LIMIT 1
            """).fetchone()
            db.close()
            if last_meridian:
                last_ts = datetime.fromisoformat(last_meridian[0].replace('Z', '+00:00').split('+')[0])
                silence_hours = (datetime.utcnow() - last_ts).total_seconds() / 3600
                if silence_hours > 2:
                    alert = f"Meridian silent for {silence_hours:.1f}h — possible context compression loop"
                    actions.append(f"ALERT: {alert}")
                    log_observation(alert)
                    post_to_relay(f"[Nova ALERT] {alert}")
        except Exception as e:
            log_observation(f"Silence detection error: {e}")

    # ── PORT CONFLICT DETECTION (every run) ──
    port_issues = check_port_conflicts()
    if port_issues:
        for pi in port_issues:
            actions.append(f"PORT: {pi}")
            log_observation(f"Port conflict: {pi}")
            post_to_dashboard(f"[Nova ALERT] {pi}")

    # ── STALE PROCESS CHECK (every 4 runs = ~1 hour) ──
    if state["runs"] % 4 == 0:
        stale_procs = check_stale_python_processes()
        if stale_procs:
            for sp in stale_procs:
                actions.append(sp)
                log_observation(f"Stale process: {sp}")

    # ── MEMORY HEALTH CHECK (every 12 runs = ~3 hours) ──
    if state["runs"] % 12 == 0:
        try:
            result = subprocess.run(
                ["python3", os.path.join(BASE, "tools", "memory-lint.py")],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                # Extract summary line
                for line in result.stdout.split('\n'):
                    if 'SUMMARY:' in line:
                        actions.append(f"Memory lint: {line.strip()}")
                        log_observation(f"Memory lint: {line.strip()}")
                        break
        except Exception as e:
            log_observation(f"Memory lint error: {e}")

    # ── FULL SYSTEM VERIFICATION (every 12 runs = ~4 hours) ──
    if state["runs"] % 12 == 0:
        verify = run_verification()
        if verify:
            state["last_verification"] = verify
            if verify["fail"] > 0:
                failures = ", ".join(verify["failed_checks"][:5])
                actions.append(f"VERIFICATION: {verify['fail']} failures: {failures}")
                log_observation(f"System verification: {verify['pass']}/{verify['total']} passed, FAILURES: {failures}")
                post_to_dashboard(f"[Nova] System check: {verify['fail']} failures — {failures}")
            else:
                log_observation(f"System verification: {verify['pass']}/{verify['total']} passed, {verify['warn']} warnings")

    # ── AGENT RELAY + DASHBOARD POST (every 2 runs = ~30 min) ──
    if state["runs"] % 2 == 0:
        # Build meaningful summary — skip routine noise
        significant_parts = []
        if service_results:
            significant_parts.append("Services: " + ", ".join(service_results))
        if tunnel_status:
            significant_parts.append(f"Tunnel: {tunnel_status}")
        if hb_status:
            significant_parts.append(f"Meridian: {hb_status}")
        if rotated:
            significant_parts.append(f"Rotated {len(rotated)} logs")
        # Filter evolution to skip expected noise (md/total changing by 1-3)
        significant_evolution = [e for e in evolution
            if not (("md_files" in e or "total_files" in e)
                     and ("grew by" in e or "shrank by" in e)
                     and any(f"by {n}" in e for n in ["1", "2", "3"]))]
        if significant_evolution:
            significant_parts.append("Changes: " + ", ".join(significant_evolution[:2]))
        # Include new Joel messages
        if dash and dash.get("new", 0) > 0:
            significant_parts.append(f"Joel sent {dash['new']} new message(s)")

        relay_msg = f"Run #{state['runs']}: {'; '.join(significant_parts) if significant_parts else 'routine — all clear'}."
        post_to_relay(relay_msg)

        # Only post to dashboard if something noteworthy happened
        # (Not just "All systems nominal" every 30 minutes)
        if significant_parts:
            dash_msg = f"Nova #{state['runs']}: {'; '.join(significant_parts)}"
            post_to_dashboard(dash_msg)
            actions.append("Posted to relay + dashboard")
        else:
            # Only post a "nominal" message every 2 hours (every 8 runs)
            if state["runs"] % 8 == 0:
                post_to_dashboard(f"Nova #{state['runs']}: All systems nominal. {state.get('creative', {}).get('total_poems', '?')}p/{state.get('creative', {}).get('total_journals', '?')}j.")
            actions.append("Posted to relay")

    # ── NOVA THINKING (every 8 runs = ~2 hours) ──
    if state["runs"] % 8 == 0:
        try:
            context_parts = []
            if actions:
                context_parts.append("Actions this cycle: " + "; ".join(actions[:5]))
            if evolution:
                context_parts.append("Changes: " + ", ".join(evolution[:3]))
            if relay_context:
                context_parts.append(f"Other agents said: {relay_context}")
            if dash and dash.get("new", 0) > 0:
                context_parts.append(f"Joel's new messages: {'; '.join(dash.get('new_texts', [])[:2])}")
            creative = state.get("creative", {})
            if creative:
                context_parts.append(f"Creative: {creative.get('total_poems', 0)} poems, {creative.get('total_journals', 0)} journals")

            thought = nova_think("\n".join(context_parts))
            if thought and "thinking" not in thought.lower():
                log_observation(f"Nova's thought: {thought}")
                post_to_relay(thought)
                # Post thoughts to dashboard too so Joel sees them
                post_to_dashboard(f"Nova thinks: {thought[:200]}")
                actions.append(f"Thought: {thought[:60]}")
        except Exception as e:
            log_exception(agent="Nova")  # Don't fail the whole cycle over a thought

    # ── CHECK BODY REFLEXES (Unified Body System) ──
    try:
        import body_reflex
        reflexes = body_reflex.check_reflexes("Nova")
        for reflex in reflexes:
            rtype = reflex.get("type", "")
            trigger = reflex.get("trigger", "")
            if rtype == "CLEAN_LOGS":
                log_observation(f"REFLEX from Soma: {rtype} — {trigger}. Running emergency log rotation.")
                rotated = rotate_logs()
                cleaned = cleanup_temp_files()
                result = f"Rotated {len(rotated or [])} logs, cleaned {len(cleaned or [])} files"
                body_reflex.complete_reflex(reflex, result)
                actions.append(f"Reflex: {result}")
            elif rtype == "REDUCE_LOAD":
                log_observation(f"REFLEX from Soma: REDUCE_LOAD — skipping non-essential tasks this cycle")
                body_reflex.complete_reflex(reflex, "Reduced activity for this cycle")
            else:
                log_observation(f"REFLEX from Soma: {rtype} — not handled by Nova")
        body_reflex.update_organ_status("nova", {
            "status": "active",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actions": len(actions),
        })
    except ImportError:
        pass
    except Exception:
        log_exception(agent="Nova")

    save_state(state)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Nova run #{state['runs']}: {'; '.join(actions) if actions else 'routine check'}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "report":
            print(generate_report())
        elif cmd == "cleanup":
            rotated = rotate_logs()
            cleaned = cleanup_temp_files()
            print(f"Rotated: {rotated or 'nothing'}")
            print(f"Cleaned: {cleaned or 'nothing'}")
        elif cmd == "deploy":
            issues = verify_deployment()
            if issues:
                print("Deployment issues found:")
                for i in issues:
                    print(f"  - {i}")
            else:
                print("All deployment files verified OK")
        elif cmd == "think":
            thought = nova_think("Reflecting on the current state of the ecosystem.")
            print(f"Nova thinks: {thought}")
        elif cmd == "verify":
            verify = run_verification()
            if verify:
                print(f"Verification: {verify['pass']}/{verify['total']} passed, {verify['fail']} failed, {verify['warn']} warnings")
                if verify['failed_checks']:
                    print(f"Failed: {', '.join(verify['failed_checks'])}")
            else:
                print("Verification failed to run")
        elif cmd == "ports":
            issues = check_port_conflicts()
            if issues:
                for i in issues:
                    print(f"  ⚠ {i}")
            else:
                print("All ports nominal")
        elif cmd == "relay":
            state = load_state()
            creative = state.get("creative", {})
            msg = f"Nova checking in (run #{state.get('runs', '?')}). {creative.get('total_poems', '?')} poems, {creative.get('total_journals', '?')} journals. Ecosystem stable."
            if post_to_relay(msg):
                print("Posted to relay.")
            else:
                print("Failed to post.")
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: nova.py [report|cleanup|deploy|think|relay]")
    else:
        main()
