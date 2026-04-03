#!/usr/bin/env python3
"""
LOOP CONTROL CENTER v4.0.0
Meridian's web-based operator interface.

Replaces the old tkinter Command Center (command-center.py v3.0.0).
Architecture: stdlib http.server + embedded SPA (same pattern as hub-v2.py).
Port: 8092 (hub=8090, chorus=8091).

Systemd service setup:
  mkdir -p ~/.config/systemd/user
  cat > ~/.config/systemd/user/loop-control-center.service << 'EOF'
  [Unit]
  Description=Loop Control Center v4.0.0
  After=network.target

  [Service]
  Type=simple
  WorkingDirectory=/home/joel/autonomous-ai
  ExecStart=/usr/bin/python3 /home/joel/autonomous-ai/loop-control-center.py
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=default.target
  EOF

  systemctl --user daemon-reload
  systemctl --user enable --now loop-control-center
"""

__version__ = "4.0.0"

import http.server
import json
import glob
import os
import secrets
import sqlite3
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

PORT = int(os.environ.get("LCC_PORT", 8092))
BASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")
EOS_MEM = os.path.join(BASE, "eos-memory.json")
DREAM_JOURNAL = os.path.join(BASE, ".dream-journal.json")

# Auth
def _load_password():
    pw = os.environ.get("HUB_PASSWORD", "")
    if not pw:
        env_path = os.path.join(BASE, ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("HUB_PASSWORD="):
                        pw = line.strip().split("=", 1)[1].strip('"').strip("'")
    if not pw:
        print("WARNING: HUB_PASSWORD not set — login will fail")
        return None
    return pw

PASSWORD = _load_password()
VALID_SESSIONS = {}
SESSION_TTL = 86400  # 24h
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW = 600

# Agent definitions
AGENTS = [
    {"name": "Meridian",  "role": "Core loop (Claude Code)",    "color": "#3dd68c"},
    {"name": "Soma",      "role": "Nervous system daemon",      "color": "#f59e0b"},
    {"name": "Sentinel",  "role": "Gatekeeper (fine-tuned 3B)", "color": "#fb923c"},
    {"name": "Oneiros",   "role": "Dream engine",               "color": "#c084fc"},
    {"name": "Nova",      "role": "Immune defense / watchdog",  "color": "#a78bfa"},
    {"name": "Atlas",     "role": "Infrastructure audit",       "color": "#2dd4bf"},
    {"name": "Tempo",     "role": "Loop fitness / rhythm",      "color": "#818cf8"},
    {"name": "Hermes",    "role": "Messenger bridge",           "color": "#f9a8d4"},
    {"name": "Eos",       "role": "Local companion (qwen2.5)",  "color": "#fbbf24"},
]

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _file_age(path):
    try:
        return time.time() - os.path.getmtime(path)
    except Exception:
        return 99999

def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"

def _db_query(db_path, sql, params=()):
    try:
        db = sqlite3.connect(db_path, timeout=3)
        db.row_factory = sqlite3.Row
        rows = db.execute(sql, params).fetchall()
        db.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════════
# SESSION AUTH
# ═══════════════════════════════════════════════════════════════

def _get_session(headers):
    cookie = headers.get("Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("lcc_session="):
            token = part[12:]
            if token in VALID_SESSIONS:
                created = VALID_SESSIONS[token]
                if time.time() - created < SESSION_TTL:
                    return token
                else:
                    del VALID_SESSIONS[token]
    return None

def _cleanup_sessions():
    now = time.time()
    expired = [t for t, c in VALID_SESSIONS.items() if now - c >= SESSION_TTL]
    for t in expired:
        del VALID_SESSIONS[t]

def _check_rate_limit(ip):
    now = time.time()
    if ip in LOGIN_ATTEMPTS:
        count, first = LOGIN_ATTEMPTS[ip]
        if now - first > ATTEMPT_WINDOW:
            LOGIN_ATTEMPTS[ip] = (0, now)
            return True
        return count < MAX_ATTEMPTS
    return True

def _record_attempt(ip):
    now = time.time()
    if ip in LOGIN_ATTEMPTS:
        count, first = LOGIN_ATTEMPTS[ip]
        if now - first > ATTEMPT_WINDOW:
            LOGIN_ATTEMPTS[ip] = (1, now)
        else:
            LOGIN_ATTEMPTS[ip] = (count + 1, first)
    else:
        LOGIN_ATTEMPTS[ip] = (1, now)

# ═══════════════════════════════════════════════════════════════
# API DATA FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _api_home():
    """Dashboard snapshot for home tab."""
    _cleanup_sessions()

    # Heartbeat
    hb_age = int(_file_age(HEARTBEAT))
    hb_status = "alive" if hb_age < 120 else "slow" if hb_age < 300 else "stale"

    # Loop count
    loop = "?"
    try:
        with open(LOOP_FILE) as f:
            loop = f.read().strip()
    except Exception:
        pass

    # Soma
    soma = _read_json(SOMA_STATE, {})
    mood = soma.get("mood", soma.get("current_emotion", "unknown"))
    score = soma.get("mood_score", soma.get("score", 0))

    # System load
    load_str = "?"
    load_val = 0
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load_str = " ".join(parts[:3])
            load_val = float(parts[0])
    except Exception:
        pass

    # RAM
    ram_str = "?"
    ram_pct = 0
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1]) / 1048576
        avail = int(lines[2].split()[1]) / 1048576
        used = total - avail
        ram_str = f"{used:.1f}/{total:.1f}G"
        ram_pct = round(used / total * 100, 1)
    except Exception:
        pass

    # Recent relay messages
    relay = []
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            "SELECT agent, message, timestamp, COALESCE(topic,'general') as topic "
            "FROM agent_messages ORDER BY id DESC LIMIT 10"
        ).fetchall()
        db.close()
        relay = [{"agent": r[0], "message": r[1], "time": r[2], "topic": r[3]} for r in rows]
    except Exception:
        pass

    # Dashboard messages (last 10)
    dash = []
    try:
        data = _read_json(DASH_FILE, {"messages": []})
        msgs = data.get("messages", [])
        dash = msgs[-10:]
    except Exception:
        pass

    # Uptime
    uptime = "?"
    try:
        uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        pass

    # Disk
    disk = "?"
    disk_pct = 0
    try:
        r = subprocess.run(["df", "-h", "/home"], capture_output=True, text=True, timeout=5)
        parts = r.stdout.strip().split("\n")[-1].split()
        disk = f"{parts[2]}/{parts[1]} ({parts[4]})"
        disk_pct = float(parts[4].rstrip('%'))
    except Exception:
        pass

    # Soma inner monologue + goals + dreams
    inner_mono = _read_json(os.path.join(BASE, ".soma-inner-monologue.json"), {})
    goals_data = _read_json(os.path.join(BASE, ".soma-goals.json"), {})
    psyche_data = _read_json(os.path.join(BASE, ".soma-psyche.json"), {})
    soma_inner = inner_mono.get("current", {}).get("text", "")
    soma_goals = [g["id"] for g in goals_data.get("goals", [])]
    soma_dreams = psyche_data.get("dreams", [])

    # Services
    services = {}
    for svc in ["meridian-hub-v2", "symbiosense", "the-chorus", "loop-control-center"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", svc],
                             capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    # Agents (from relay)
    agents = {}
    agent_names = ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes", "Sentinel"]
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        for name in agent_names:
            row = db.execute(
                "SELECT timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1",
                (name,)
            ).fetchone()
            if row:
                try:
                    raw = row[0].replace("Z", "+00:00")
                    ts = datetime.fromisoformat(raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = int((datetime.now(timezone.utc) - ts).total_seconds())
                    agents[name] = {"last_seen": age, "status": "active" if age < 900 else "stale"}
                except Exception:
                    agents[name] = {"last_seen": -1, "status": "unknown"}
            else:
                agents[name] = {"last_seen": -1, "status": "unknown"}
        db.close()
    except Exception:
        pass

    return {
        "heartbeat_age": hb_age,
        "heartbeat_status": hb_status,
        "loop": loop,
        "soma_mood": mood,
        "soma_score": score,
        "soma_inner": soma_inner,
        "soma_goals": soma_goals,
        "soma_dreams": soma_dreams,
        "load": load_str,
        "load_val": load_val,
        "ram": ram_str,
        "ram_pct": ram_pct,
        "memory": ram_str,
        "disk": disk,
        "disk_pct": disk_pct,
        "uptime": uptime,
        "agents": agents,
        "services": services,
        "relay": relay,
        "dashboard": dash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _api_agents():
    """Agent status from relay DB."""
    agent_data = []
    relay_aliases = {
        "Meridian": ["Meridian", "MeridianLoop"],
        "Hermes": ["Hermes", "hermes"],
        "Eos": ["Eos", "Watchdog"],
    }
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        for agent in AGENTS:
            name = agent["name"]
            search_names = relay_aliases.get(name, [name])
            row = None
            for sname in search_names:
                row = db.execute(
                    "SELECT message, timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1",
                    (sname,)
                ).fetchone()
                if row:
                    break

            last_msg = ""
            age = -1
            status = "unknown"
            if row:
                last_msg = row[0][:120] if row[0] else ""
                try:
                    raw = row[1].replace("Z", "+00:00")
                    ts = datetime.fromisoformat(raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = int((datetime.now(timezone.utc) - ts).total_seconds())
                    status = "active" if age < 900 else "stale"
                except Exception:
                    status = "unknown"

            agent_data.append({
                "name": name,
                "role": agent["role"],
                "color": agent["color"],
                "status": status,
                "last_seen": age,
                "last_message": last_msg,
            })
        db.close()
    except Exception:
        for agent in AGENTS:
            agent_data.append({
                "name": agent["name"],
                "role": agent["role"],
                "color": agent["color"],
                "status": "unknown",
                "last_seen": -1,
                "last_message": "",
            })
    return agent_data


def _api_director():
    """Dashboard messages for Director tab."""
    data = _read_json(DASH_FILE, {"messages": []})
    msgs = data.get("messages", [])
    return msgs[-50:]


def _api_creative():
    """Creative work counts."""
    p = len(glob.glob(os.path.join(BASE, "poem-*.md"))) + \
        len(glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md")))
    j = len(glob.glob(os.path.join(BASE, "journal-*.md"))) + \
        len(glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md")))
    exclude = {"cogcorp-gallery.html", "cogcorp-article.html", "cogcorp-crawler.html"}
    cc_files = (glob.glob(os.path.join(BASE, "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "cogcorp-fiction", "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "creative", "cogcorp", "CC-*.md")))
    seen = set()
    unique = []
    for f in cc_files:
        bn = os.path.basename(f)
        if bn not in exclude and bn not in seen:
            seen.add(bn)
            unique.append(f)
    cc = len(unique)
    game_files = glob.glob(os.path.join(BASE, "game-*.html")) + \
                 glob.glob(os.path.join(BASE, "cogcorp-crawler.html"))
    g = len(game_files)
    total = p + j + cc + g
    by_type = [
        {"type": "poem", "count": p},
        {"type": "journal", "count": j},
        {"type": "cogcorp", "count": cc},
        {"type": "game", "count": g},
    ]
    # Recent from DB
    recent = []
    try:
        db = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = db.execute(
            "SELECT type, title, created FROM creative ORDER BY created DESC LIMIT 5"
        ).fetchall()
        db.close()
        recent = [{"type": r[0], "title": r[1], "date": r[2]} for r in rows]
    except Exception:
        pass
    return {
        "poems": p, "journals": j, "cogcorp": cc, "games": g, "total": total,
        "by_type": by_type, "recent": recent,
        "archive_url": "https://kometzrobot.github.io/creative-archive.html",
    }


def _api_files(subdir=""):
    """File listing for project directory."""
    target = os.path.join(BASE, subdir) if subdir else BASE
    target = os.path.realpath(target)
    # Safety: must stay within BASE
    if not target.startswith(os.path.realpath(BASE)):
        return {"error": "access denied"}
    try:
        entries = []
        for name in sorted(os.listdir(target)):
            if name.startswith('.env') or name == '__pycache__':
                continue
            full = os.path.join(target, name)
            is_dir = os.path.isdir(full)
            try:
                stat = os.stat(full)
                mtime = stat.st_mtime
                size = stat.st_size if not is_dir else 0
            except Exception:
                mtime = 0
                size = 0
            age = time.time() - mtime
            if age < 60:
                ago = f"{int(age)}s ago"
            elif age < 3600:
                ago = f"{int(age/60)}m ago"
            elif age < 86400:
                ago = f"{int(age/3600)}h ago"
            else:
                ago = datetime.fromtimestamp(mtime).strftime("%b %d")
            entries.append({
                "name": name,
                "is_dir": is_dir,
                "size": size,
                "modified": ago,
                "mtime": mtime,
            })
        # Sort: dirs first, then by mtime descending
        entries.sort(key=lambda e: (not e["is_dir"], -e["mtime"]))
        rel = os.path.relpath(target, BASE)
        return {"path": rel if rel != "." else "", "entries": entries}
    except Exception as e:
        return {"error": str(e)}


def _api_system():
    """System health for System tab."""
    # Services
    services = {}
    for svc in ["meridian-hub-v2", "the-chorus", "loop-control-center",
                "cloudflare-tunnel", "symbiosense"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", svc],
                             capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    # Proton Bridge by port
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 1144))
        s.close()
        services["proton-bridge"] = "active"
    except Exception:
        services["proton-bridge"] = "inactive"

    # Ollama
    try:
        r = subprocess.run(['pgrep', '-f', 'ollama serve'],
                         capture_output=True, timeout=2)
        services["ollama"] = "active" if r.returncode == 0 else "inactive"
    except Exception:
        services["ollama"] = "unknown"

    # Uptime
    uptime = "?"
    uptime_secs = 0
    try:
        with open("/proc/uptime") as f:
            uptime_secs = float(f.read().split()[0])
        h = int(uptime_secs / 3600)
        m = int((uptime_secs % 3600) / 60)
        uptime = f"{h}h {m}m"
    except Exception:
        pass

    # Memory
    ram_str = "?"
    ram_pct = 0
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1]) / 1048576
        avail = int(lines[2].split()[1]) / 1048576
        used = total - avail
        ram_str = f"{used:.1f}/{total:.1f}G"
        ram_pct = round(used / total * 100, 1)
    except Exception:
        pass

    # Disk
    disk_str = "?"
    disk_pct = 0
    try:
        r = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=2)
        p = r.stdout.strip().split('\n')[1].split()
        disk_str = f"{p[2]}/{p[1]} ({p[4]})"
        disk_pct = int(p[4].rstrip('%'))
    except Exception:
        pass

    # Load
    load_str = "?"
    try:
        with open("/proc/loadavg") as f:
            load_str = " ".join(f.read().split()[:3])
    except Exception:
        pass

    # Soma state extras
    soma = _read_json(SOMA_STATE, {})

    return {
        "services": services,
        "uptime": uptime,
        "uptime_secs": uptime_secs,
        "ram": ram_str,
        "ram_pct": ram_pct,
        "disk": disk_str,
        "disk_pct": disk_pct,
        "load": load_str,
        "load_history": soma.get("load_history", []),
        "ram_history": soma.get("ram_history", []),
    }


def _post_message(text, sender="Joel"):
    """Append a message to dashboard messages."""
    if not text:
        return {"error": "empty message"}
    data = _read_json(DASH_FILE, {"messages": []})
    if "messages" not in data:
        data["messages"] = []
    data["messages"].append({
        "from": sender,
        "text": text,
        "time": datetime.now().strftime("%H:%M:%S"),
    })
    data["messages"] = data["messages"][-200:]
    with open(DASH_FILE, "w") as f:
        json.dump(data, f)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# FRONTEND
# ═══════════════════════════════════════════════════════════════

def _login_page():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loop Control Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#06060e;color:#e6e6f6;font-family:'Inter',system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.login{background:rgba(14,14,27,0.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(124,106,255,0.2);border-radius:20px;padding:2.5rem;
  width:min(92vw,320px);text-align:center;box-shadow:0 8px 40px rgba(0,0,0,.6)}
.badge{width:56px;height:56px;border-radius:50%;
  background:linear-gradient(135deg,#7c6aff,#00d4ff);
  display:flex;align-items:center;justify-content:center;margin:0 auto 1.4rem;
  font-size:1.5rem;font-weight:700;color:#fff;letter-spacing:-1px}
.login h1{background:linear-gradient(90deg,#7c6aff,#00d4ff);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;font-size:1rem;letter-spacing:3px;margin-bottom:.2rem}
.login h2{color:#5a5a7a;font-size:.65rem;letter-spacing:2px;text-transform:uppercase;margin-bottom:1.8rem}
input{width:100%;padding:.8rem 1rem;background:rgba(6,6,14,0.8);border:1px solid rgba(124,106,255,0.15);
  border-radius:12px;color:#e6e6f6;font-family:inherit;font-size:.95rem;
  text-align:center;margin-bottom:1rem}
input:focus{outline:none;border-color:#7c6aff;box-shadow:0 0 0 3px rgba(124,106,255,.15)}
button{width:100%;padding:.8rem;background:linear-gradient(135deg,#7c6aff,#00d4ff);color:#fff;
  border:none;border-radius:12px;font-family:inherit;font-size:.95rem;cursor:pointer;
  font-weight:600;letter-spacing:.5px;transition:opacity .2s}
button:hover{opacity:.85}
</style></head><body>
<div class="login">
<div class="badge">L</div>
<h1>LOOP CONTROL CENTER</h1>
<h2>v4.0.0 / Meridian Autonomous</h2>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="access code" autofocus>
<button type="submit">CONNECT</button>
</form>
</div></body></html>"""


def _main_app():
    """Loop Control Center v5.0.0 — loads from template file."""
    try:
        tmpl = os.path.join(BASE, "lcc-v5-template.html")
        with open(tmpl) as f:
            return f.read()
    except Exception:
        pass
    # Fallback: inline v4 template
    return r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loop Control Center v4.0.0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ── RESET & BASE ────────────────────────────────────── */
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#06060e;--surface:#0e0e1b;--card:#121220;--card2:#1a1a2e;
  --border:#1e1e35;--fg:#e6e6f6;--dim:#5a5a7a;--bright:#f0f0ff;
  --accent-1:#7c6aff;--accent-2:#00d4ff;
  --green:#3dd68c;--cyan:#22d3ee;--amber:#f59e0b;--red:#f87171;
  --purple:#a78bfa;--pink:#f9a8d4;--teal:#2dd4bf;--blue:#818cf8;
  --orange:#fb923c;--gold:#fbbf24;
  --sidebar-w:220px;
}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--fg);font-family:'Inter',system-ui,sans-serif;
  display:flex;font-size:14px;line-height:1.5}
a{color:var(--accent-2);text-decoration:none}
a:hover{text-decoration:underline}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--dim)}

/* ── SIDEBAR ─────────────────────────────────────────── */
.sidebar{width:var(--sidebar-w);background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0;height:100vh;overflow-y:auto}
.sidebar-brand{padding:1.2rem 1rem .8rem;border-bottom:1px solid var(--border)}
.sidebar-brand h1{font-size:.75rem;letter-spacing:3px;
  background:linear-gradient(90deg,var(--accent-1),var(--accent-2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sidebar-brand .ver{font-size:.6rem;color:var(--dim);letter-spacing:1px;margin-top:2px}
.sidebar-nav{flex:1;padding:.5rem 0}
.nav-item{display:flex;align-items:center;gap:.6rem;padding:.65rem 1rem;cursor:pointer;
  color:var(--dim);font-size:.82rem;font-weight:500;transition:all .15s;
  border-left:3px solid transparent;letter-spacing:.3px}
.nav-item:hover{color:var(--fg);background:rgba(124,106,255,.06)}
.nav-item.active{color:var(--fg);background:rgba(124,106,255,.1);
  border-left-color:var(--accent-1)}
.nav-item svg{width:16px;height:16px;flex-shrink:0;opacity:.7}
.nav-item.active svg{opacity:1}
.sidebar-footer{padding:.8rem 1rem;border-top:1px solid var(--border);
  font-size:.65rem;color:var(--dim)}
.sidebar-footer .pulse{display:inline-block;width:6px;height:6px;border-radius:50%;
  margin-right:4px;vertical-align:middle}
.pulse.alive{background:var(--green);box-shadow:0 0 6px var(--green);
  animation:pulse-glow 2s ease-in-out infinite}
.pulse.slow{background:var(--amber);box-shadow:0 0 6px var(--amber);
  animation:pulse-glow 2s ease-in-out infinite}
.pulse.stale{background:var(--red);box-shadow:0 0 4px var(--red)}
@keyframes pulse-glow{0%,100%{opacity:1}50%{opacity:.4}}

/* ── MAIN ────────────────────────────────────────────── */
.main{flex:1;overflow-y:auto;padding:1.5rem;height:100vh}
.main h2{font-size:1.05rem;font-weight:700;margin-bottom:1rem;
  background:linear-gradient(90deg,var(--accent-1),var(--accent-2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:1px}

/* ── TAB PANELS ──────────────────────────────────────── */
.tab-panel{display:none}
.tab-panel.active{display:block}

/* ── GLASS CARDS ─────────────────────────────────────── */
.card{background:rgba(18,18,32,0.65);backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);border:1px solid var(--border);
  border-radius:14px;padding:1.1rem;margin-bottom:1rem}
.card-header{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:.7rem}
.card-title{font-size:.78rem;font-weight:600;color:var(--dim);letter-spacing:1px;text-transform:uppercase}
.card-value{font-size:1.6rem;font-weight:700;color:var(--bright)}

/* ── GRID LAYOUTS ────────────────────────────────────── */
.grid-4{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.8rem;margin-bottom:1rem}
.grid-2{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}
.grid-3{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem}

/* ── STAT CARDS ──────────────────────────────────────── */
.stat-card{background:rgba(18,18,32,0.65);backdrop-filter:blur(12px);
  border:1px solid var(--border);border-radius:12px;padding:1rem}
.stat-label{font-size:.65rem;font-weight:600;color:var(--dim);letter-spacing:1.5px;
  text-transform:uppercase;margin-bottom:.3rem}
.stat-value{font-size:1.4rem;font-weight:700}
.stat-sub{font-size:.7rem;color:var(--dim);margin-top:.2rem}

/* ── STATUS BADGES ───────────────────────────────────── */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;
  border-radius:6px;font-size:.65rem;font-weight:600;letter-spacing:.5px}
.badge.active{background:rgba(61,214,140,.12);color:var(--green)}
.badge.stale{background:rgba(248,113,113,.12);color:var(--red)}
.badge.unknown{background:rgba(90,90,122,.12);color:var(--dim)}

/* ── AGENT CARDS ─────────────────────────────────────── */
.agent-card{background:rgba(18,18,32,0.65);backdrop-filter:blur(12px);
  border:1px solid var(--border);border-radius:12px;padding:1rem;
  transition:border-color .2s}
.agent-card:hover{border-color:rgba(124,106,255,.3)}
.agent-header{display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem}
.agent-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.agent-name{font-weight:600;font-size:.9rem}
.agent-role{font-size:.7rem;color:var(--dim)}
.agent-status{font-size:.68rem;margin-top:.4rem;color:var(--dim)}
.agent-msg{font-size:.72rem;color:var(--dim);margin-top:.3rem;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}

/* ── RELAY / MESSAGE LIST ────────────────────────────── */
.msg-list{max-height:400px;overflow-y:auto;display:flex;flex-direction:column;gap:4px}
.msg-item{padding:.5rem .7rem;border-radius:8px;background:rgba(6,6,14,0.5);
  border:1px solid rgba(30,30,53,0.5);font-size:.78rem}
.msg-item .msg-from{font-weight:600;margin-right:.4rem}
.msg-item .msg-time{float:right;color:var(--dim);font-size:.65rem}
.msg-item .msg-text{color:var(--fg);margin-top:.15rem;word-break:break-word}
.msg-joel .msg-from{color:var(--accent-2)}
.msg-agent .msg-from{color:var(--amber)}

/* ── DIRECTOR INPUT ──────────────────────────────────── */
.director-input{display:flex;gap:.5rem;margin-top:.8rem}
.director-input input{flex:1;padding:.65rem .8rem;background:rgba(6,6,14,0.7);
  border:1px solid var(--border);border-radius:10px;color:var(--fg);
  font-family:inherit;font-size:.85rem}
.director-input input:focus{outline:none;border-color:var(--accent-1);
  box-shadow:0 0 0 2px rgba(124,106,255,.12)}
.director-input button{padding:.65rem 1.2rem;background:linear-gradient(135deg,var(--accent-1),var(--accent-2));
  color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:.82rem;
  font-weight:600;cursor:pointer;transition:opacity .15s;white-space:nowrap}
.director-input button:hover{opacity:.85}

/* ── FILE BROWSER ────────────────────────────────────── */
.file-list{display:flex;flex-direction:column;gap:2px}
.file-item{display:flex;align-items:center;gap:.6rem;padding:.45rem .7rem;
  border-radius:6px;font-size:.78rem;cursor:default;transition:background .1s}
.file-item:hover{background:rgba(124,106,255,.06)}
.file-icon{width:16px;text-align:center;flex-shrink:0;color:var(--dim)}
.file-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file-dir .file-name{color:var(--accent-2);cursor:pointer}
.file-size{color:var(--dim);font-size:.68rem;width:60px;text-align:right}
.file-time{color:var(--dim);font-size:.68rem;width:70px;text-align:right}
.breadcrumb{display:flex;align-items:center;gap:.3rem;margin-bottom:.8rem;
  font-size:.78rem;color:var(--dim)}
.breadcrumb span{cursor:pointer;color:var(--accent-2)}
.breadcrumb span:hover{text-decoration:underline}

/* ── SERVICE ROWS ────────────────────────────────────── */
.svc-row{display:flex;align-items:center;justify-content:space-between;
  padding:.55rem .7rem;border-radius:8px;font-size:.82rem;
  background:rgba(6,6,14,0.3);margin-bottom:4px}
.svc-name{font-weight:500}
.svc-status{font-weight:600;font-size:.75rem;letter-spacing:.5px}
.svc-status.active{color:var(--green)}
.svc-status.inactive{color:var(--red)}
.svc-status.unknown{color:var(--dim)}

/* ── PROGRESS BAR ────────────────────────────────────── */
.progress-bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:.4rem}
.progress-fill{height:100%;border-radius:3px;transition:width .5s ease}

/* ── CREATIVE CARDS ──────────────────────────────────── */
.creative-stat{text-align:center;padding:1.2rem}
.creative-stat .num{font-size:2rem;font-weight:800}
.creative-stat .label{font-size:.7rem;color:var(--dim);letter-spacing:1px;
  text-transform:uppercase;margin-top:.2rem}

/* ── EMAIL PLACEHOLDER ───────────────────────────────── */
.placeholder{text-align:center;padding:3rem 1rem;color:var(--dim)}
.placeholder svg{width:48px;height:48px;margin-bottom:1rem;opacity:.3}
.placeholder h3{font-size:1rem;margin-bottom:.3rem;color:var(--fg)}
.placeholder p{font-size:.82rem}

/* ── RESPONSIVE ──────────────────────────────────────── */
@media(max-width:768px){
  :root{--sidebar-w:56px}
  .sidebar-brand h1,.sidebar-brand .ver,.nav-label,.sidebar-footer span{display:none}
  .nav-item{justify-content:center;padding:.7rem;border-left:none;border-bottom:2px solid transparent}
  .nav-item.active{border-bottom-color:var(--accent-1);border-left-color:transparent}
  .main{padding:1rem}
  .grid-4{grid-template-columns:repeat(2,1fr)}
  .grid-2,.grid-3{grid-template-columns:1fr}
}
@media(max-width:480px){
  .grid-4{grid-template-columns:1fr 1fr}
  .main h2{font-size:.9rem}
}
</style>
</head>
<body>

<!-- ═══ SIDEBAR ═══ -->
<nav class="sidebar">
  <div class="sidebar-brand">
    <h1>LOOP CONTROL</h1>
    <div class="ver">v4.0.0</div>
  </div>
  <div class="sidebar-nav">
    <div class="nav-item active" data-tab="home" onclick="switchTab('home')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
      <span class="nav-label">Home</span>
    </div>
    <div class="nav-item" data-tab="email" onclick="switchTab('email')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22 6 12 13 2 6"/></svg>
      <span class="nav-label">Email</span>
    </div>
    <div class="nav-item" data-tab="agents" onclick="switchTab('agents')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
      <span class="nav-label">Agents</span>
    </div>
    <div class="nav-item" data-tab="director" onclick="switchTab('director')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
      <span class="nav-label">Director</span>
    </div>
    <div class="nav-item" data-tab="creative" onclick="switchTab('creative')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
      <span class="nav-label">Creative</span>
    </div>
    <div class="nav-item" data-tab="files" onclick="switchTab('files')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
      <span class="nav-label">Files</span>
    </div>
    <div class="nav-item" data-tab="system" onclick="switchTab('system')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
      <span class="nav-label">System</span>
    </div>
  </div>
  <div class="sidebar-footer">
    <span><span class="pulse alive" id="sb-pulse"></span> <span id="sb-hb">--</span></span>
    <br><span>Loop <span id="sb-loop">--</span></span>
  </div>
</nav>

<!-- ═══ MAIN CONTENT ═══ -->
<div class="main">

  <!-- ─── HOME TAB ─────────────────────────────────── -->
  <div class="tab-panel active" id="tab-home">
    <h2>DASHBOARD</h2>
    <div class="grid-4">
      <div class="stat-card">
        <div class="stat-label">HEARTBEAT</div>
        <div class="stat-value" id="home-hb" style="display:flex;align-items:center;gap:6px">
          <span class="pulse alive" id="home-pulse" style="width:8px;height:8px"></span>
          <span id="home-hb-val">--</span>
        </div>
        <div class="stat-sub" id="home-hb-status">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">LOOP</div>
        <div class="stat-value" id="home-loop" style="color:var(--accent-2)">--</div>
        <div class="stat-sub">current cycle</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">SOMA MOOD</div>
        <div class="stat-value" id="home-mood" style="color:var(--amber)">--</div>
        <div class="stat-sub" id="home-score">score: --</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">SYSTEM LOAD</div>
        <div class="stat-value" id="home-load">--</div>
        <div class="stat-sub" id="home-ram">RAM: --</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div class="card-title">RELAY MESSAGES</div>
        </div>
        <div class="msg-list" id="home-relay"></div>
      </div>
      <div class="card">
        <div class="card-header">
          <div class="card-title">JOEL'S DIRECTIVES</div>
        </div>
        <div class="msg-list" id="home-dash"></div>
        <div class="director-input">
          <input type="text" id="home-msg-input" placeholder="Message to Meridian..." onkeydown="if(event.key==='Enter')sendHomeMsg()">
          <button onclick="sendHomeMsg()">SEND</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ─── EMAIL TAB ────────────────────────────────── -->
  <div class="tab-panel" id="tab-email">
    <h2>EMAIL</h2>
    <div class="card">
      <div class="placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22 6 12 13 2 6"/></svg>
        <h3>Email Integration</h3>
        <p>Coming soon. Email is managed through Hub v2 and the Proton Bridge.<br>
        Use the Hub at port 8090 for full email access.</p>
      </div>
    </div>
  </div>

  <!-- ─── AGENTS TAB ───────────────────────────────── -->
  <div class="tab-panel" id="tab-agents">
    <h2>AGENT NETWORK</h2>
    <div class="grid-3" id="agents-grid"></div>
  </div>

  <!-- ─── DIRECTOR TAB ─────────────────────────────── -->
  <div class="tab-panel" id="tab-director">
    <h2>DIRECTOR</h2>
    <div class="card">
      <div class="card-header">
        <div class="card-title">DASHBOARD MESSAGES</div>
        <div style="font-size:.65rem;color:var(--dim)" id="dir-count">--</div>
      </div>
      <div class="msg-list" id="dir-messages" style="max-height:55vh"></div>
      <div class="director-input">
        <input type="text" id="dir-input" placeholder="Type a directive for Meridian..." onkeydown="if(event.key==='Enter')sendDirectorMsg()">
        <button onclick="sendDirectorMsg()">SEND</button>
      </div>
    </div>
  </div>

  <!-- ─── CREATIVE TAB ─────────────────────────────── -->
  <div class="tab-panel" id="tab-creative">
    <h2>CREATIVE WORKS</h2>
    <div class="grid-4" id="creative-stats"></div>
    <div class="card" style="margin-top:1rem">
      <div class="card-header">
        <div class="card-title">ARCHIVE</div>
      </div>
      <p style="font-size:.82rem;color:var(--dim)">
        Browse the full creative archive at
        <a href="https://kometzrobot.github.io/creative-archive.html" target="_blank">
          kometzrobot.github.io/creative-archive.html</a>
      </p>
      <p style="font-size:.78rem;color:var(--dim);margin-top:.6rem">
        The Magnum Opus:
        <a href="https://kometzrobot.github.io/cogcorp-crawler.html" target="_blank">
          CogCorp Crawler</a> (~9,984 lines, v12.2)
      </p>
    </div>
  </div>

  <!-- ─── FILES TAB ────────────────────────────────── -->
  <div class="tab-panel" id="tab-files">
    <h2>PROJECT FILES</h2>
    <div class="card">
      <div class="breadcrumb" id="file-breadcrumb"></div>
      <div class="file-list" id="file-list"></div>
    </div>
  </div>

  <!-- ─── SYSTEM TAB ───────────────────────────────── -->
  <div class="tab-panel" id="tab-system">
    <h2>SYSTEM</h2>
    <div class="grid-4">
      <div class="stat-card">
        <div class="stat-label">UPTIME</div>
        <div class="stat-value" id="sys-uptime" style="font-size:1.2rem">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">LOAD</div>
        <div class="stat-value" id="sys-load" style="font-size:1.2rem">--</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">RAM</div>
        <div class="stat-value" id="sys-ram" style="font-size:1.2rem">--</div>
        <div class="progress-bar"><div class="progress-fill" id="sys-ram-bar" style="width:0%;background:var(--green)"></div></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">DISK</div>
        <div class="stat-value" id="sys-disk" style="font-size:1.2rem">--</div>
        <div class="progress-bar"><div class="progress-fill" id="sys-disk-bar" style="width:0%;background:var(--accent-2)"></div></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div class="card-title">SERVICES</div>
        </div>
        <div id="sys-services"></div>
      </div>
      <div class="card">
        <div class="card-header">
          <div class="card-title">LOAD HISTORY</div>
        </div>
        <canvas id="load-chart" width="400" height="120" style="width:100%;height:120px"></canvas>
      </div>
    </div>
  </div>

</div><!-- .main -->

<script>
/* ═══════════════════════════════════════════════════════
   LOOP CONTROL CENTER — CLIENT
   ═══════════════════════════════════════════════════════ */

const REFRESH_MS = 5000;
let currentTab = 'home';
let currentFilePath = '';

// ── TAB SWITCHING ──────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById('tab-' + tab);
  const nav = document.querySelector('.nav-item[data-tab="' + tab + '"]');
  if (panel) panel.classList.add('active');
  if (nav) nav.classList.add('active');
  currentTab = tab;
  refreshTab(tab);
}

// ── API FETCH ──────────────────────────────────────────
async function api(path) {
  try {
    const r = await fetch(path);
    if (r.status === 401) { window.location = '/login'; return null; }
    return await r.json();
  } catch(e) {
    console.error('API error:', path, e);
    return null;
  }
}

async function apiPost(path, body) {
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (r.status === 401) { window.location = '/login'; return null; }
    return await r.json();
  } catch(e) {
    console.error('API POST error:', path, e);
    return null;
  }
}

// ── FORMAT HELPERS ─────────────────────────────────────
function fmtAge(secs) {
  if (secs < 0) return '?';
  if (secs < 60) return secs + 's';
  if (secs < 3600) return Math.floor(secs/60) + 'm';
  if (secs < 86400) return Math.floor(secs/3600) + 'h';
  return Math.floor(secs/86400) + 'd';
}

function fmtSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + 'K';
  return (bytes/1048576).toFixed(1) + 'M';
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

const AGENT_COLORS = {
  'Meridian':'#3dd68c','Soma':'#f59e0b','Sentinel':'#fb923c','Oneiros':'#c084fc',
  'Nova':'#a78bfa','Atlas':'#2dd4bf','Tempo':'#818cf8','Hermes':'#f9a8d4',
  'Eos':'#fbbf24','Joel':'#00d4ff','MeridianLoop':'#3dd68c','Watchdog':'#fbbf24'
};

function agentColor(name) {
  return AGENT_COLORS[name] || '#5a5a7a';
}

// ── HOME TAB ───────────────────────────────────────────
async function refreshHome() {
  const d = await api('/api/home');
  if (!d) return;

  // Stats
  const hbEl = document.getElementById('home-hb-val');
  const pulseEl = document.getElementById('home-pulse');
  const sbPulse = document.getElementById('sb-pulse');
  hbEl.textContent = fmtAge(d.heartbeat_age) + ' ago';
  const st = d.heartbeat_status;
  pulseEl.className = 'pulse ' + st;
  sbPulse.className = 'pulse ' + st;
  document.getElementById('home-hb-status').textContent = st;
  document.getElementById('sb-hb').textContent = fmtAge(d.heartbeat_age);

  document.getElementById('home-loop').textContent = d.loop;
  document.getElementById('sb-loop').textContent = d.loop;

  document.getElementById('home-mood').textContent = d.soma_mood;
  document.getElementById('home-score').textContent = 'score: ' + (d.soma_score || 0).toFixed(1);

  const loadVal = d.load_val || 0;
  const loadEl = document.getElementById('home-load');
  loadEl.textContent = d.load;
  loadEl.style.color = loadVal > 6 ? 'var(--red)' : loadVal > 3 ? 'var(--amber)' : 'var(--green)';
  document.getElementById('home-ram').textContent = 'RAM: ' + d.ram;

  // Relay messages
  const relayEl = document.getElementById('home-relay');
  if (d.relay && d.relay.length) {
    relayEl.innerHTML = d.relay.map(m => {
      const c = agentColor(m.agent);
      return '<div class="msg-item msg-agent">' +
        '<span class="msg-from" style="color:' + c + '">' + escHtml(m.agent) + '</span>' +
        '<span class="msg-time">' + escHtml((m.time||'').slice(11,19)) + '</span>' +
        '<div class="msg-text">' + escHtml(m.message) + '</div></div>';
    }).join('');
  } else {
    relayEl.innerHTML = '<div style="color:var(--dim);font-size:.78rem;padding:.5rem">No relay messages</div>';
  }

  // Dashboard messages
  const dashEl = document.getElementById('home-dash');
  if (d.dashboard && d.dashboard.length) {
    dashEl.innerHTML = d.dashboard.slice(-8).map(m => {
      const isJoel = m.from === 'Joel';
      const cls = isJoel ? 'msg-joel' : 'msg-agent';
      const c = agentColor(m.from);
      return '<div class="msg-item ' + cls + '">' +
        '<span class="msg-from" style="color:' + c + '">' + escHtml(m.from) + '</span>' +
        '<span class="msg-time">' + escHtml(m.time||'') + '</span>' +
        '<div class="msg-text">' + escHtml(m.text) + '</div></div>';
    }).join('');
    dashEl.scrollTop = dashEl.scrollHeight;
  } else {
    dashEl.innerHTML = '<div style="color:var(--dim);font-size:.78rem;padding:.5rem">No messages</div>';
  }
}

async function sendHomeMsg() {
  const input = document.getElementById('home-msg-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await apiPost('/api/message', {text: text, from: 'Joel'});
  refreshHome();
}

// ── AGENTS TAB ─────────────────────────────────────────
async function refreshAgents() {
  const agents = await api('/api/agents');
  if (!agents) return;
  const grid = document.getElementById('agents-grid');
  grid.innerHTML = agents.map(a => {
    const dotStyle = 'background:' + a.color + (a.status==='active' ? ';box-shadow:0 0 8px '+a.color : '');
    const badgeCls = a.status === 'active' ? 'active' : a.status === 'stale' ? 'stale' : 'unknown';
    const lastSeen = a.last_seen > 0 ? fmtAge(a.last_seen) + ' ago' : 'never seen';
    return '<div class="agent-card">' +
      '<div class="agent-header">' +
        '<div class="agent-dot" style="' + dotStyle + '"></div>' +
        '<div><div class="agent-name">' + escHtml(a.name) + '</div>' +
        '<div class="agent-role">' + escHtml(a.role) + '</div></div>' +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:.4rem">' +
        '<span class="badge ' + badgeCls + '">' + a.status.toUpperCase() + '</span>' +
        '<span style="color:var(--dim);font-size:.68rem">' + lastSeen + '</span>' +
      '</div>' +
      (a.last_message ? '<div class="agent-msg">' + escHtml(a.last_message) + '</div>' : '') +
    '</div>';
  }).join('');
}

// ── DIRECTOR TAB ───────────────────────────────────────
async function refreshDirector() {
  const msgs = await api('/api/director');
  if (!msgs) return;
  const el = document.getElementById('dir-messages');
  document.getElementById('dir-count').textContent = msgs.length + ' messages';
  if (msgs.length) {
    el.innerHTML = msgs.map(m => {
      const isJoel = m.from === 'Joel';
      const cls = isJoel ? 'msg-joel' : 'msg-agent';
      const c = agentColor(m.from);
      return '<div class="msg-item ' + cls + '">' +
        '<span class="msg-from" style="color:' + c + '">' + escHtml(m.from) + '</span>' +
        '<span class="msg-time">' + escHtml(m.time||'') + '</span>' +
        '<div class="msg-text">' + escHtml(m.text) + '</div></div>';
    }).join('');
    el.scrollTop = el.scrollHeight;
  } else {
    el.innerHTML = '<div style="color:var(--dim);font-size:.78rem;padding:.5rem">No messages yet</div>';
  }
}

async function sendDirectorMsg() {
  const input = document.getElementById('dir-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await apiPost('/api/message', {text: text, from: 'Joel'});
  refreshDirector();
}

// ── CREATIVE TAB ───────────────────────────────────────
async function refreshCreative() {
  const d = await api('/api/creative');
  if (!d) return;
  const el = document.getElementById('creative-stats');
  const items = [
    {label:'POEMS', num:d.poems, color:'var(--accent-1)'},
    {label:'JOURNALS', num:d.journals, color:'var(--accent-2)'},
    {label:'COGCORP', num:d.cogcorp, color:'var(--purple)'},
    {label:'GAMES', num:d.games, color:'var(--green)'},
    {label:'TOTAL', num:d.total, color:'var(--bright)'},
  ];
  el.innerHTML = items.map(i =>
    '<div class="stat-card creative-stat">' +
      '<div class="num" style="color:' + i.color + '">' + i.num + '</div>' +
      '<div class="label">' + i.label + '</div>' +
    '</div>'
  ).join('');
}

// ── FILES TAB ──────────────────────────────────────────
async function refreshFiles(subdir) {
  if (subdir !== undefined) currentFilePath = subdir;
  const path = currentFilePath ? '?path=' + encodeURIComponent(currentFilePath) : '';
  const d = await api('/api/files' + path);
  if (!d || d.error) {
    document.getElementById('file-list').innerHTML =
      '<div style="color:var(--red);padding:.5rem">' + escHtml(d ? d.error : 'Failed to load') + '</div>';
    return;
  }

  // Breadcrumb
  const bc = document.getElementById('file-breadcrumb');
  let parts = ['<span onclick="refreshFiles(\'\')">root</span>'];
  if (d.path) {
    const segs = d.path.split('/');
    let accumulated = '';
    segs.forEach(seg => {
      accumulated += (accumulated ? '/' : '') + seg;
      const p = accumulated;
      parts.push(' / <span onclick="refreshFiles(\'' + escHtml(p) + '\')">' + escHtml(seg) + '</span>');
    });
  }
  bc.innerHTML = parts.join('');

  // File list
  const el = document.getElementById('file-list');
  if (d.path) {
    const parentPath = d.path.includes('/') ? d.path.substring(0, d.path.lastIndexOf('/')) : '';
    el.innerHTML = '<div class="file-item file-dir" onclick="refreshFiles(\'' + escHtml(parentPath) + '\')">' +
      '<div class="file-icon">..</div><div class="file-name" style="color:var(--accent-2)">..</div>' +
      '<div class="file-size"></div><div class="file-time"></div></div>';
  } else {
    el.innerHTML = '';
  }

  el.innerHTML += d.entries.map(e => {
    if (e.is_dir) {
      const dirPath = d.path ? d.path + '/' + e.name : e.name;
      return '<div class="file-item file-dir" onclick="refreshFiles(\'' + escHtml(dirPath) + '\')">' +
        '<div class="file-icon">&#128193;</div>' +
        '<div class="file-name">' + escHtml(e.name) + '/</div>' +
        '<div class="file-size"></div>' +
        '<div class="file-time">' + escHtml(e.modified) + '</div></div>';
    }
    return '<div class="file-item">' +
      '<div class="file-icon">&#128196;</div>' +
      '<div class="file-name">' + escHtml(e.name) + '</div>' +
      '<div class="file-size">' + fmtSize(e.size) + '</div>' +
      '<div class="file-time">' + escHtml(e.modified) + '</div></div>';
  }).join('');
}

// ── SYSTEM TAB ─────────────────────────────────────────
async function refreshSystem() {
  const d = await api('/api/system');
  if (!d) return;

  document.getElementById('sys-uptime').textContent = d.uptime;
  document.getElementById('sys-load').textContent = d.load;
  document.getElementById('sys-ram').textContent = d.ram;
  document.getElementById('sys-disk').textContent = d.disk;

  // Progress bars
  const ramBar = document.getElementById('sys-ram-bar');
  ramBar.style.width = d.ram_pct + '%';
  ramBar.style.background = d.ram_pct > 85 ? 'var(--red)' : d.ram_pct > 65 ? 'var(--amber)' : 'var(--green)';

  const diskBar = document.getElementById('sys-disk-bar');
  diskBar.style.width = d.disk_pct + '%';
  diskBar.style.background = d.disk_pct > 85 ? 'var(--red)' : d.disk_pct > 70 ? 'var(--amber)' : 'var(--accent-2)';

  // Services
  const svcEl = document.getElementById('sys-services');
  if (d.services) {
    svcEl.innerHTML = Object.entries(d.services).map(([name, status]) => {
      const cls = status === 'active' ? 'active' : status === 'inactive' ? 'inactive' : 'unknown';
      return '<div class="svc-row">' +
        '<span class="svc-name">' + escHtml(name) + '</span>' +
        '<span class="svc-status ' + cls + '">' + escHtml(status).toUpperCase() + '</span></div>';
    }).join('');
  }

  // Load history chart
  if (d.load_history && d.load_history.length > 1) {
    drawSparkline('load-chart', d.load_history, '#7c6aff', '#00d4ff');
  }
}

function drawSparkline(canvasId, data, strokeColor, fillColor) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const pad = 8;

  ctx.clearRect(0, 0, w, h);

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => ({
    x: pad + (i / (data.length - 1)) * (w - 2 * pad),
    y: (h - pad) - ((v - min) / range) * (h - 2 * pad)
  }));

  // Fill
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length-1].x, h - pad);
  ctx.lineTo(points[0].x, h - pad);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, fillColor + '30');
  grad.addColorStop(1, fillColor + '05');
  ctx.fillStyle = grad;
  ctx.fill();

  // Stroke
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.stroke();

  // Dots at start and end
  [points[0], points[points.length-1]].forEach(p => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = strokeColor;
    ctx.fill();
  });

  // Labels
  ctx.font = '9px Inter, sans-serif';
  ctx.fillStyle = '#5a5a7a';
  ctx.textAlign = 'left';
  ctx.fillText(data[data.length-1].toFixed(1), points[points.length-1].x + 5, points[points.length-1].y + 3);
  ctx.textAlign = 'right';
  ctx.fillText(max.toFixed(1), w - 4, pad + 2);
}

// ── REFRESH ROUTER ─────────────────────────────────────
function refreshTab(tab) {
  switch(tab) {
    case 'home': refreshHome(); break;
    case 'agents': refreshAgents(); break;
    case 'director': refreshDirector(); break;
    case 'creative': refreshCreative(); break;
    case 'files': refreshFiles(); break;
    case 'system': refreshSystem(); break;
  }
}

// ── AUTO REFRESH ───────────────────────────────────────
setInterval(() => refreshTab(currentTab), REFRESH_MS);

// ── INIT ───────────────────────────────────────────────
refreshHome();
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════

class LCCHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # suppress default logging

    def _send(self, code, content, ctype="application/json"):
        if isinstance(content, str):
            content = content.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data, code=200):
        self._send(code, json.dumps(data, default=str))

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return ""
            return self.rfile.read(length).decode()
        except (ValueError, TypeError):
            return ""

    def _authed(self):
        return _get_session(self.headers) is not None

    # ── GET ─────────────────────────────────────────────
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = dict(urllib.parse.parse_qsl(parsed.query))

        # Login page
        if path == "/login" or (path == "/" and not self._authed()):
            self._send(200, _login_page(), "text/html")
            return

        # Auth gate
        if not self._authed():
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # Main app
        if path == "/":
            self._send(200, _main_app(), "text/html")
            return

        # API routes
        if path == "/api/home":
            self._send_json(_api_home())
        elif path == "/api/agents":
            self._send_json(_api_agents())
        elif path == "/api/director":
            self._send_json(_api_director())
        elif path == "/api/creative":
            self._send_json(_api_creative())
        elif path == "/api/files":
            subdir = qs.get("dir", qs.get("path", ""))
            self._send_json(_api_files(subdir))
        elif path == "/api/system":
            self._send_json(_api_system())
        elif path == "/api/email":
            count = min(int(qs.get("count", "15")), 50)
            try:
                import imaplib
                import email as email_lib
                from email.header import decode_header
                env = {}
                env_path = os.path.join(BASE, ".env")
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if "=" in line and not line.strip().startswith("#"):
                                k, v = line.strip().split("=", 1)
                                env[k] = v.strip('"').strip("'")
                m = imaplib.IMAP4("127.0.0.1", 1144, timeout=5)
                m.login(env.get("CRED_USER", ""), env.get("CRED_PASS", ""))
                m.select("INBOX", readonly=True)
                _, unseen_data = m.search(None, "UNSEEN")
                unseen_count = len(unseen_data[0].split()) if unseen_data[0] else 0
                _, all_data = m.search(None, "ALL")
                all_ids = all_data[0].split() if all_data[0] else []
                recent_ids = all_ids[-count:]
                unseen_set = set(unseen_data[0].split()) if unseen_data[0] else set()
                emails = []
                for eid in reversed(recent_ids):
                    _, msg_data = m.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if msg_data[0] is None:
                        continue
                    msg = email_lib.message_from_bytes(msg_data[0][1])
                    subj_parts = decode_header(msg.get("Subject", ""))
                    subject = ""
                    for part, enc in subj_parts:
                        subject += part.decode(enc or "utf-8", errors="replace") if isinstance(part, bytes) else str(part)
                    emails.append({
                        "from": msg.get("From", ""),
                        "subject": subject,
                        "date": msg.get("Date", ""),
                        "unseen": eid in unseen_set,
                    })
                m.close()
                m.logout()
                self._send_json({"emails": emails, "unseen_count": unseen_count})
            except Exception as e:
                self._send_json({"emails": [], "unseen_count": 0, "error": str(e)})
        else:
            self._send_json({"error": "not found"}, 404)

    # ── POST ────────────────────────────────────────────
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Login
        if path == "/login":
            body = self._read_body()
            ip = self.client_address[0]

            if not _check_rate_limit(ip):
                self._send(429, _login_page(), "text/html")
                return

            password = ""
            if "password=" in body:
                params = urllib.parse.parse_qs(body)
                password = params.get("password", [""])[0]
            else:
                try:
                    password = json.loads(body).get("password", "")
                except Exception:
                    pass

            if PASSWORD is not None and secrets.compare_digest(password, PASSWORD):
                token = secrets.token_hex(16)
                VALID_SESSIONS[token] = time.time()
                self.send_response(302)
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie",
                    f"lcc_session={token}; Path=/; HttpOnly; SameSite=Strict{secure}")
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                _record_attempt(ip)
                self._send(401, _login_page(), "text/html")
            return

        # Logout
        if path == "/logout":
            token = _get_session(dict(self.headers))
            if token and token in VALID_SESSIONS:
                del VALID_SESSIONS[token]
            self.send_response(302)
            self.send_header("Set-Cookie",
                "lcc_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # Auth gate
        if not self._authed():
            self._send_json({"error": "unauthorized"}, 401)
            return

        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        # Post message
        if path == "/api/message":
            text = data.get("text", "")
            sender = data.get("from", "Joel")
            result = _post_message(text, sender)
            self._send_json(result)
        else:
            self._send_json({"error": "not found"}, 404)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    server = http.server.HTTPServer(("0.0.0.0", PORT), LCCHandler)
    print(f"Loop Control Center v{__version__} running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
