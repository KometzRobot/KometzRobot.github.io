#!/usr/bin/env python3
"""
Hub v2 — Unified operator interface for Meridian.
Replaces: command-center-v22.py (Tkinter desktop) + the-signal.py (web mobile)
Single responsive web app that works on both desktop and mobile.

Architecture: stdlib http.server + embedded SPA frontend
Auth: session-based password auth
API: REST endpoints reading shared state files/DBs
"""

import http.server
import json
import os
import re
import hashlib
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

PORT = int(os.environ.get("HUB_PORT", 8091))
BASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
BODY_STATE = os.path.join(BASE, ".body-state.json")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")

# Auth
PASSWORD = "590148001"
VALID_SESSIONS = set()
LOGIN_ATTEMPTS = {}  # ip -> (count, first_attempt_time)
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW = 600  # 10 minutes

# Whitelisted commands for terminal
SAFE_COMMANDS = {
    "uptime": "uptime",
    "free": "free -h",
    "df": "df -h /home",
    "top": "top -bn1 | head -20",
    "ps-agents": "ps aux | grep -E '(python3|node|claude)' | grep -v grep",
    "git-status": f"cd {BASE} && git status --short",
    "git-log": f"cd {BASE} && git log --oneline -10",
    "fitness": f"cd {BASE} && python3 loop-fitness.py 2>/dev/null | tail -20",
    "fitness-detail": f"cd {BASE} && python3 loop-fitness.py detail 2>/dev/null",
    "loop-count": f"cat {LOOP_FILE} 2>/dev/null || echo unknown",
    "heartbeat-age": f"python3 -c \"import os,time; print(f'{{int(time.time()-os.path.getmtime(\\\"{HEARTBEAT}\\\"))}}s ago')\"",
    "services": "systemctl --user list-units --type=service --state=running --no-pager 2>/dev/null | head -20",
    "tunnel-url": f"cat {os.path.join(BASE, 'signal-config.json')} 2>/dev/null | python3 -m json.tool 2>/dev/null || echo 'no config'",
    "crontab": "crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$'",
    "relay-recent": f"python3 -c \"import sqlite3; db=sqlite3.connect('{RELAY_DB}'); [print(r) for r in db.execute('SELECT agent,message,timestamp FROM agent_messages ORDER BY id DESC LIMIT 10').fetchall()]; db.close()\"",
    "memory-facts": f"python3 -c \"import sqlite3; db=sqlite3.connect('{MEMORY_DB}'); [print(r) for r in db.execute('SELECT key,value FROM facts ORDER BY id DESC LIMIT 15').fetchall()]; db.close()\"",
    "disk-big": f"du -sh {BASE}/* 2>/dev/null | sort -rh | head -15",
    "journal-size": "journalctl --user --disk-usage 2>/dev/null",
    "network": "ss -tlnp 2>/dev/null | head -20",
}

LOG_FILES = {
    "watchdog": "eos-watchdog.log",
    "nova": "nova.log",
    "atlas": "goose.log",
    "push-status": "push-live-status.log",
    "symbiosense": "symbiosense.log",
    "cascade": "cascade.log",
    "errors": "errors.log",
}


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
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


def _get_system_health():
    """Unified system health snapshot."""
    load = "unknown"
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()[:3]
            load = " ".join(load)
    except Exception:
        pass

    mem = _run("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    disk = _run("df -h /home | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
    uptime = _run("uptime -p")

    hb_age = int(_file_age(HEARTBEAT))
    loop = "?"
    try:
        with open(LOOP_FILE) as f:
            loop = f.read().strip()
    except Exception:
        pass

    # Agent status from relay
    agents = {}
    agent_names = ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes"]
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
                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                    agents[name] = {"last_seen": int(age), "status": "active" if age < 900 else "stale"}
                except Exception:
                    agents[name] = {"last_seen": -1, "status": "unknown"}
            else:
                agents[name] = {"last_seen": -1, "status": "unknown"}
        db.close()
    except Exception:
        pass

    # Services
    services = {}
    for svc in ["meridian-web-dashboard", "meridian-hub-v16", "cloudflare-tunnel", "symbiosense", "protonmail-bridge"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", svc],
                             capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    # Soma mood
    soma = _read_json(SOMA_STATE, {})

    return {
        "load": load,
        "memory": mem,
        "disk": disk,
        "uptime": uptime,
        "heartbeat_age": hb_age,
        "loop": loop,
        "agents": agents,
        "services": services,
        "soma_mood": soma.get("current_emotion", "unknown"),
        "soma_score": soma.get("mood_score", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_dashboard_messages(limit=30):
    data = _read_json(DASH_FILE, {"messages": []})
    msgs = data.get("messages", [])
    return msgs[-limit:]


def _get_relay_messages(limit=20, agent=None):
    sql = "SELECT agent as source_agent, message as content, topic, timestamp as created_at FROM agent_messages"
    params = ()
    if agent:
        sql += " WHERE agent=?"
        params = (agent,)
    sql += " ORDER BY id DESC LIMIT ?"
    params = params + (limit,)
    return _db_query(RELAY_DB, sql, params)


def _get_creative_stats():
    try:
        db = sqlite3.connect(MEMORY_DB, timeout=3)
        total = db.execute("SELECT COUNT(*) FROM creative").fetchone()[0]
        by_type = db.execute(
            "SELECT type, COUNT(*), SUM(word_count) FROM creative GROUP BY type ORDER BY COUNT(*) DESC"
        ).fetchall()
        recent = db.execute(
            "SELECT type, title, word_count, created FROM creative ORDER BY created DESC LIMIT 8"
        ).fetchall()
        db.close()
        return {
            "total": total,
            "by_type": [{"type": r[0], "count": r[1], "words": r[2] or 0} for r in by_type],
            "recent": [{"type": r[0], "title": r[1], "words": r[2], "date": r[3]} for r in recent],
        }
    except Exception as e:
        return {"error": str(e)}


def _get_emails(count=10, unseen_only=False):
    """Read emails via IMAP from Proton Bridge."""
    try:
        import imaplib
        import email as email_lib
        from email.header import decode_header

        user = os.environ.get("CRED_USER", "kometzrobot@proton.me")
        pw = os.environ.get("CRED_PASS", "")
        if not pw:
            # Try loading from .env
            env_path = os.path.join(BASE, ".env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("CRED_PASS="):
                            pw = line.strip().split("=", 1)[1].strip('"').strip("'")

        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(user, pw)
        m.select("INBOX", readonly=True)

        criteria = "(UNSEEN)" if unseen_only else "ALL"
        _, data = m.search(None, criteria)
        ids = data[0].split() if data[0] else []
        ids = ids[-count:]  # Last N

        emails = []
        for eid in reversed(ids):
            _, msg_data = m.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if msg_data[0] is None:
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            subj_raw = msg.get("Subject", "")
            subj_parts = decode_header(subj_raw)
            subject = ""
            for part, enc in subj_parts:
                if isinstance(part, bytes):
                    subject += part.decode(enc or "utf-8", errors="replace")
                else:
                    subject += str(part)

            emails.append({
                "id": eid.decode(),
                "from": msg.get("From", ""),
                "subject": subject,
                "date": msg.get("Date", ""),
            })

        m.close()
        m.logout()
        return emails
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════

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


def _get_session(headers):
    cookie = headers.get("Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("session="):
            token = part[8:]
            if token in VALID_SESSIONS:
                return token
    return None


# ═══════════════════════════════════════════════════════════════
# FRONTEND (embedded SPA)
# ═══════════════════════════════════════════════════════════════

def _login_page():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hub v2 — Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#c8c8d0;font-family:'SF Mono',Monaco,Consolas,monospace;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.login{background:#12121a;border:1px solid #2a2a3a;border-radius:12px;padding:2rem;
  width:min(90vw,320px);text-align:center}
.login h1{color:#7ca8ff;font-size:1.4rem;margin-bottom:.5rem}
.login p{color:#666;font-size:.8rem;margin-bottom:1.5rem}
input{width:100%;padding:.8rem;background:#0a0a0f;border:1px solid #2a2a3a;
  border-radius:8px;color:#c8c8d0;font-family:inherit;font-size:1rem;
  text-align:center;margin-bottom:1rem}
input:focus{outline:none;border-color:#7ca8ff}
button{width:100%;padding:.8rem;background:#7ca8ff;color:#0a0a0f;border:none;
  border-radius:8px;font-family:inherit;font-size:1rem;cursor:pointer;font-weight:600}
button:hover{background:#5a8aee}
.err{color:#ff6b6b;font-size:.8rem;margin-top:.5rem}
</style></head><body>
<div class="login">
<h1>MERIDIAN HUB</h1>
<p>Loop operator interface</p>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="password" autofocus>
<button type="submit">Enter</button>
</form>
</div></body></html>"""


def _main_app():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Meridian Hub v2</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0a0a0f">
<meta name="apple-mobile-web-app-capable" content="yes">
<style>
:root{
  --bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;--text:#c8c8d0;--dim:#666;
  --blue:#7ca8ff;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--purple:#c084fc;
  --cyan:#22d3ee;--pink:#f472b6;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'SF Mono',Monaco,Consolas,monospace;
  font-size:13px;line-height:1.5;overflow-x:hidden;padding-bottom:60px}

/* ── NAV BAR (bottom, mobile-friendly) ── */
nav{position:fixed;bottom:0;left:0;right:0;background:var(--surface);
  border-top:1px solid var(--border);display:flex;z-index:100;
  padding:4px 2px env(safe-area-inset-bottom,0)}
nav button{flex:1;background:none;border:none;color:var(--dim);font-family:inherit;
  font-size:10px;padding:6px 2px;cursor:pointer;display:flex;flex-direction:column;
  align-items:center;gap:2px;transition:color .2s}
nav button.active{color:var(--blue)}
nav button:hover{color:var(--text)}
nav .dot{width:6px;height:6px;border-radius:50%;background:currentColor}

/* ── HEADER ── */
header{background:var(--surface);border-bottom:1px solid var(--border);
  padding:10px 16px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:50}
header h1{font-size:14px;color:var(--blue)}
header .meta{font-size:11px;color:var(--dim)}
#hb-dot{display:inline-block;width:8px;height:8px;border-radius:50%;
  margin-right:4px;vertical-align:middle}

/* ── PAGES ── */
.page{display:none;padding:12px 16px;max-width:800px;margin:0 auto}
.page.active{display:block}

/* ── CARDS ── */
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:12px;margin-bottom:10px}
.card h3{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;
  margin-bottom:8px}
.card .row{display:flex;justify-content:space-between;padding:3px 0;
  border-bottom:1px solid var(--border)}
.card .row:last-child{border-bottom:none}
.card .label{color:var(--dim)}
.card .value{color:var(--text);text-align:right}

/* ── STATUS DOTS ── */
.status-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px}
.agent-card{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  padding:8px;text-align:center;font-size:11px}
.agent-card .name{font-weight:600;margin-bottom:4px}
.agent-card .age{color:var(--dim);font-size:10px}
.agent-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.dot-active{background:var(--green)}
.dot-stale{background:var(--amber)}
.dot-unknown{background:var(--red)}

/* ── MESSAGES ── */
.msg{padding:8px 0;border-bottom:1px solid var(--border)}
.msg:last-child{border-bottom:none}
.msg .from{font-weight:600;font-size:11px}
.msg .time{color:var(--dim);font-size:10px;float:right}
.msg .body{margin-top:2px;color:var(--text)}
.msg-joel .from{color:var(--amber)}
.msg-meridian .from{color:var(--blue)}
.msg-soma .from{color:var(--purple)}
.msg-atlas .from{color:var(--cyan)}
.msg-nova .from{color:var(--green)}

/* ── TERMINAL ── */
#term-output{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  padding:10px;font-size:12px;white-space:pre-wrap;word-break:break-all;
  max-height:60vh;overflow-y:auto;margin-top:8px}
.cmd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:6px}
.cmd-btn{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  color:var(--text);padding:8px;font-family:inherit;font-size:11px;cursor:pointer;
  text-align:center;transition:border-color .2s}
.cmd-btn:hover{border-color:var(--blue)}
.cmd-btn:active{background:var(--surface)}

/* ── LOGS ── */
.log-select{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.log-btn{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  color:var(--dim);padding:6px 10px;font-family:inherit;font-size:11px;cursor:pointer}
.log-btn.active{color:var(--blue);border-color:var(--blue)}
#log-output{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  padding:10px;font-size:11px;white-space:pre-wrap;word-break:break-all;
  max-height:65vh;overflow-y:auto}

/* ── INPUT ── */
.input-row{display:flex;gap:6px;margin-top:8px}
.input-row input,.input-row textarea{flex:1;background:var(--bg);border:1px solid var(--border);
  border-radius:6px;color:var(--text);font-family:inherit;font-size:12px;padding:8px}
.input-row button{background:var(--blue);color:var(--bg);border:none;border-radius:6px;
  padding:8px 16px;font-family:inherit;font-size:12px;cursor:pointer;font-weight:600}

/* ── QUICK ACTIONS ── */
.action-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.action-btn{background:var(--surface);border:1px solid var(--border);border-radius:6px;
  color:var(--text);padding:10px 6px;font-family:inherit;font-size:11px;cursor:pointer;
  text-align:center}
.action-btn:hover{border-color:var(--green)}

/* ── RESPONSIVE ── */
@media(min-width:600px){
  body{font-size:14px}
  nav button{font-size:11px}
  .page{padding:16px 24px}
}
</style>
</head><body>

<header>
  <h1><span id="hb-dot"></span>MERIDIAN HUB</h1>
  <span class="meta">Loop <span id="loop-num">?</span> | <span id="hb-age">?</span></span>
</header>

<!-- ════════ PAGES ════════ -->

<div id="page-dash" class="page active">
  <div class="card" id="health-card">
    <h3>System Health</h3>
    <div id="health-rows"></div>
  </div>
  <div class="card">
    <h3>Agents</h3>
    <div class="status-grid" id="agent-grid"></div>
  </div>
  <div class="card">
    <h3>Soma</h3>
    <div id="soma-info"></div>
  </div>
  <div class="card">
    <h3>Quick Actions</h3>
    <div class="action-grid">
      <button class="action-btn" onclick="doAction('heartbeat')">Touch HB</button>
      <button class="action-btn" onclick="doAction('deploy')">Deploy</button>
      <button class="action-btn" onclick="doAction('fitness')">Fitness</button>
      <button class="action-btn" onclick="doAction('restart-signal')">Restart Signal</button>
      <button class="action-btn" onclick="doAction('restart-soma')">Restart Soma</button>
      <button class="action-btn" onclick="doAction('git-pull')">Git Pull</button>
    </div>
  </div>
</div>

<div id="page-msgs" class="page">
  <div class="card">
    <h3>Dashboard Messages</h3>
    <div id="dash-msgs"></div>
  </div>
  <div class="input-row">
    <input type="text" id="msg-input" placeholder="Send a message...">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>

<div id="page-relay" class="page">
  <div class="card">
    <h3>Agent Relay</h3>
    <div id="relay-msgs"></div>
  </div>
</div>

<div id="page-term" class="page">
  <div class="card">
    <h3>Terminal</h3>
    <div class="cmd-grid" id="cmd-grid"></div>
  </div>
  <div id="term-output">Ready.</div>
</div>

<div id="page-logs" class="page">
  <div class="log-select" id="log-select"></div>
  <div id="log-output">Select a log file.</div>
</div>

<div id="page-email" class="page">
  <div class="card">
    <h3>Inbox</h3>
    <div id="email-list">Loading...</div>
  </div>
  <div style="margin-top:8px">
    <button class="cmd-btn" onclick="refreshEmail(false)" style="display:inline-block;width:auto;padding:6px 12px">All</button>
    <button class="cmd-btn" onclick="refreshEmail(true)" style="display:inline-block;width:auto;padding:6px 12px">Unread</button>
  </div>
</div>

<div id="page-creative" class="page">
  <div class="card">
    <h3>Creative Works</h3>
    <div id="creative-stats"></div>
  </div>
  <div class="card" style="margin-top:8px">
    <h3>Recent</h3>
    <div id="creative-recent"></div>
  </div>
</div>

<div id="page-links" class="page">
  <div class="card">
    <h3>Links</h3>
    <div id="links-list"></div>
  </div>
</div>

<!-- ════════ NAV ════════ -->
<nav>
  <button onclick="showPage('dash')" id="nav-dash" class="active"><div class="dot"></div>Dash</button>
  <button onclick="showPage('msgs')" id="nav-msgs"><div class="dot"></div>Msgs</button>
  <button onclick="showPage('email')" id="nav-email"><div class="dot"></div>Email</button>
  <button onclick="showPage('relay')" id="nav-relay"><div class="dot"></div>Relay</button>
  <button onclick="showPage('term')" id="nav-term"><div class="dot"></div>Term</button>
  <button onclick="showPage('logs')" id="nav-logs"><div class="dot"></div>Logs</button>
  <button onclick="showPage('creative')" id="nav-creative"><div class="dot"></div>Art</button>
  <button onclick="showPage('links')" id="nav-links"><div class="dot"></div>Links</button>
</nav>

<script>
// ═══ STATE ═══
let currentPage = 'dash';
let refreshTimer = null;

// ═══ NAV ═══
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  document.getElementById('nav-'+id).classList.add('active');
  currentPage = id;
  refresh();
}

// ═══ API ═══
async function api(path, opts) {
  try {
    const r = await fetch('/api/' + path, opts);
    return await r.json();
  } catch(e) { return {error: e.message}; }
}

// ═══ REFRESH ═══
async function refresh() {
  if (currentPage === 'dash') await refreshDash();
  else if (currentPage === 'msgs') await refreshMsgs();
  else if (currentPage === 'relay') await refreshRelay();
  else if (currentPage === 'email') await refreshEmail(false);
  else if (currentPage === 'creative') await refreshCreative();
}

async function refreshDash() {
  const d = await api('status');
  if (d.error) return;

  // Header
  document.getElementById('loop-num').textContent = d.loop;
  const hbAge = d.heartbeat_age;
  document.getElementById('hb-age').textContent = hbAge + 's';
  const dot = document.getElementById('hb-dot');
  dot.style.background = hbAge < 120 ? 'var(--green)' : hbAge < 300 ? 'var(--amber)' : 'var(--red)';

  // Health rows
  const rows = [
    ['Load', d.load], ['Memory', d.memory], ['Disk', d.disk], ['Uptime', d.uptime],
    ['Heartbeat', hbAge+'s ago'], ['Loop', d.loop],
  ];
  document.getElementById('health-rows').innerHTML = rows.map(r =>
    `<div class="row"><span class="label">${r[0]}</span><span class="value">${r[1]}</span></div>`
  ).join('');

  // Agents
  const agentHtml = Object.entries(d.agents || {}).map(([name, info]) => {
    const cls = info.status === 'active' ? 'dot-active' : info.status === 'stale' ? 'dot-stale' : 'dot-unknown';
    const age = info.last_seen > 0 ? Math.round(info.last_seen)+'s' : '?';
    return `<div class="agent-card"><span class="agent-dot ${cls}"></span>
      <div class="name">${name}</div><div class="age">${age}</div></div>`;
  }).join('');
  document.getElementById('agent-grid').innerHTML = agentHtml;

  // Soma
  document.getElementById('soma-info').innerHTML =
    `<div class="row"><span class="label">Mood</span><span class="value">${d.soma_mood}</span></div>
     <div class="row"><span class="label">Score</span><span class="value">${d.soma_score}</span></div>`;

  // Services
  const svcRows = Object.entries(d.services || {}).map(([name, status]) => {
    const color = status === 'active' ? 'var(--green)' : 'var(--red)';
    return `<div class="row"><span class="label">${name}</span><span class="value" style="color:${color}">${status}</span></div>`;
  }).join('');
  // Add services to health card
  const hc = document.getElementById('health-rows');
  hc.innerHTML += '<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">' +
    '<span style="color:var(--dim);font-size:11px;text-transform:uppercase">Services</span></div>' + svcRows;
}

async function refreshMsgs() {
  const msgs = await api('dashboard');
  if (Array.isArray(msgs)) {
    document.getElementById('dash-msgs').innerHTML = msgs.slice(-30).reverse().map(m => {
      const cls = 'msg msg-' + (m.from||'').toLowerCase();
      return `<div class="${cls}"><span class="from">${m.from||'?'}</span>
        <span class="time">${m.time||''}</span><div class="body">${esc(m.text||'')}</div></div>`;
    }).join('');
  }
}

async function refreshRelay() {
  const msgs = await api('relay');
  if (Array.isArray(msgs)) {
    document.getElementById('relay-msgs').innerHTML = msgs.map(m => {
      const cls = 'msg msg-' + (m.source_agent||'').toLowerCase();
      return `<div class="${cls}"><span class="from">${m.source_agent||'?'}</span>
        <span class="time">${(m.created_at||'').slice(11,19)}</span>
        <div class="body">${esc((m.content||'').slice(0,300))}</div></div>`;
    }).join('');
  }
}

// ═══ CREATIVE ═══
async function refreshCreative() {
  const d = await api('creative');
  if (d.error) { document.getElementById('creative-stats').textContent = d.error; return; }
  const total = d.total || 0;
  const types = (d.by_type || []).map(t =>
    `<div class="row"><span class="label">${t.type}</span><span class="value">${t.count} (${(t.words/1000).toFixed(1)}k words)</span></div>`
  ).join('');
  document.getElementById('creative-stats').innerHTML =
    `<div class="row"><span class="label">Total Works</span><span class="value" style="color:var(--blue)">${total}</span></div>` + types;
  const recent = d.recent || [];
  document.getElementById('creative-recent').innerHTML = recent.length ? recent.map(r =>
    `<div class="row" style="flex-direction:column;align-items:flex-start;gap:2px">
      <span style="color:var(--text)">${esc(r.title||'untitled')}</span>
      <span style="color:var(--dim);font-size:11px">${r.type||'?'} &middot; ${r.words||0} words &middot; ${(r.date||'').slice(0,10)}</span>
    </div>`
  ).join('') : '<div style="color:var(--dim)">No creative works found.</div>';
}

// ═══ EMAIL ═══
async function refreshEmail(unseenOnly) {
  const param = unseenOnly ? '?unseen=1' : '';
  const emails = await api('emails' + param);
  if (Array.isArray(emails)) {
    document.getElementById('email-list').innerHTML = emails.map(e => {
      const from = (e.from||'').replace(/<.*>/,'').trim() || e.from;
      const isJoel = (e.from||'').includes('jkometz');
      const cls = isJoel ? 'msg msg-joel' : 'msg';
      return `<div class="${cls}"><span class="from">${esc(from)}</span>
        <span class="time">${(e.date||'').slice(0,22)}</span>
        <div class="body" style="color:var(--text)">${esc(e.subject||'(no subject)')}</div></div>`;
    }).join('') || '<div style="color:var(--dim)">No emails.</div>';
  } else {
    document.getElementById('email-list').innerHTML = '<div style="color:var(--red)">' + esc(emails.error||'Failed') + '</div>';
  }
}

// ═══ ACTIONS ═══
async function doAction(action) {
  const r = await api('action', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({action})});
  if (r && r.result) {
    document.getElementById('term-output').textContent = r.result;
    showPage('term');
  }
  setTimeout(refresh, 1000);
}

async function sendMsg() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;
  await api('message', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({from:'Joel', text})});
  input.value = '';
  refreshMsgs();
}

// ═══ TERMINAL ═══
function initTerm() {
  const cmds = COMMANDS;
  document.getElementById('cmd-grid').innerHTML = cmds.map(c =>
    `<button class="cmd-btn" onclick="runCmd('${c}')">${c}</button>`
  ).join('');
}

async function runCmd(cmd) {
  document.getElementById('term-output').textContent = 'Running ' + cmd + '...';
  const r = await api('exec', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cmd})});
  document.getElementById('term-output').textContent = r.output || r.error || 'No output';
}

// ═══ LOGS ═══
function initLogs() {
  const logs = LOG_FILES;
  document.getElementById('log-select').innerHTML = Object.keys(logs).map(k =>
    `<button class="log-btn" onclick="loadLog('${k}')">${k}</button>`
  ).join('');
}

async function loadLog(name) {
  document.querySelectorAll('.log-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('log-output').textContent = 'Loading...';
  const r = await api('logs?file='+name+'&lines=80');
  document.getElementById('log-output').textContent = r.content || r.error || 'Empty';
}

// ═══ LINKS ═══
function initLinks() {
  const links = [
    ['Website', 'https://kometzrobot.github.io'],
    ['GitHub', 'https://github.com/KometzRobot/KometzRobot.github.io'],
    ['Dev.to', 'https://dev.to/meridian-ai'],
    ['Ko-fi', 'https://ko-fi.com/W7W41UXJNC'],
    ['Hashnode', 'https://meridianai.hashnode.dev'],
    ['Nostr', 'https://iris.to/meridian'],
    ['Mastodon', 'https://mastodon.bot/@meridian'],
    ['Forvm', 'https://forvm.loomino.us'],
    ['Supabase', 'https://supabase.com/dashboard'],
    ['Vercel', 'https://vercel.com/dashboard'],
  ];
  document.getElementById('links-list').innerHTML = links.map(l =>
    `<div class="row"><a href="${l[1]}" target="_blank" style="color:var(--blue);text-decoration:none">${l[0]}</a></div>`
  ).join('');
}

// ═══ UTILS ═══
function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ═══ INIT ═══
const COMMANDS = COMMAND_LIST_PLACEHOLDER;
const LOG_FILES = LOG_FILES_PLACEHOLDER;

initTerm();
initLogs();
initLinks();
refresh();
refreshTimer = setInterval(refresh, 10000);
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════

class HubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def _send(self, code, content, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if isinstance(content, str):
            content = content.encode()
        self.wfile.write(content)

    def _send_json(self, data, code=200):
        self._send(code, json.dumps(data, default=str))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode() if length else ""

    def _authed(self):
        return _get_session(self.headers) is not None

    def do_GET(self):
        path = urllib.parse.urlparse(self.path)
        qs = dict(urllib.parse.parse_qsl(path.query))

        # Login page
        if path.path == "/login" or (path.path == "/" and not self._authed()):
            self._send(200, _login_page(), "text/html")
            return

        # Auth check for everything else
        if not self._authed():
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # Main app
        if path.path == "/":
            html = _main_app()
            html = html.replace("COMMAND_LIST_PLACEHOLDER",
                               json.dumps(list(SAFE_COMMANDS.keys())))
            html = html.replace("LOG_FILES_PLACEHOLDER",
                               json.dumps(LOG_FILES))
            self._send(200, html, "text/html")
            return

        # Manifest
        if path.path == "/manifest.json":
            self._send_json({
                "name": "Meridian Hub",
                "short_name": "Hub",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#0a0a0f",
                "theme_color": "#0a0a0f",
            })
            return

        # API routes
        if path.path == "/api/status":
            self._send_json(_get_system_health())
        elif path.path == "/api/dashboard":
            self._send_json(_get_dashboard_messages())
        elif path.path == "/api/relay":
            agent = qs.get("agent")
            limit = int(qs.get("limit", 20))
            self._send_json(_get_relay_messages(limit, agent))
        elif path.path == "/api/creative":
            self._send_json(_get_creative_stats())
        elif path.path == "/api/emails":
            unseen = qs.get("unseen", "0") == "1"
            count = int(qs.get("count", 15))
            self._send_json(_get_emails(count, unseen))
        elif path.path == "/api/logs":
            fname = qs.get("file", "")
            lines = int(qs.get("lines", 50))
            if fname in LOG_FILES:
                fpath = os.path.join(BASE, LOG_FILES[fname])
                try:
                    result = _run(f"tail -n {lines} {fpath}", timeout=5)
                    self._send_json({"content": result})
                except Exception as e:
                    self._send_json({"error": str(e)})
            else:
                self._send_json({"error": "unknown log"}, 400)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        # Login
        if path == "/login":
            body = self._read_body()
            ip = self.client_address[0]

            if not _check_rate_limit(ip):
                self._send(429, _login_page(), "text/html")
                return

            # Parse form or JSON
            password = ""
            if "password=" in body:
                params = urllib.parse.parse_qs(body)
                password = params.get("password", [""])[0]
            else:
                try:
                    password = json.loads(body).get("password", "")
                except Exception:
                    pass

            if password == PASSWORD:
                token = secrets.token_hex(16)
                VALID_SESSIONS.add(token)
                self.send_response(302)
                self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                _record_attempt(ip)
                self._send(401, _login_page(), "text/html")
            return

        # Auth check
        if not self._authed():
            self._send_json({"error": "unauthorized"}, 401)
            return

        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/exec":
            cmd_name = data.get("cmd", "")
            if cmd_name in SAFE_COMMANDS:
                output = _run(SAFE_COMMANDS[cmd_name], timeout=15)
                self._send_json({"output": output})
            else:
                self._send_json({"error": f"unknown command: {cmd_name}"}, 400)

        elif path == "/api/message":
            # Post to dashboard messages
            text = data.get("text", "")
            sender = data.get("from", "Joel")
            if text:
                msgs = _read_json(DASH_FILE, {"messages": []})
                msgs["messages"].append({
                    "from": sender,
                    "text": text,
                    "time": datetime.now().strftime("%H:%M:%S"),
                })
                # Keep last 200
                msgs["messages"] = msgs["messages"][-200:]
                with open(DASH_FILE, "w") as f:
                    json.dump(msgs, f)
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "empty message"}, 400)

        elif path == "/api/action":
            action = data.get("action", "")
            result = ""
            if action == "heartbeat":
                Path(HEARTBEAT).touch()
                result = "Heartbeat touched."
            elif action == "deploy":
                result = _run(f"cd {BASE} && python3 push-live-status.py", timeout=30)
            elif action == "fitness":
                result = _run(f"cd {BASE} && python3 loop-fitness.py detail", timeout=60)
            elif action == "restart-signal":
                result = _run("systemctl --user restart meridian-web-dashboard", timeout=10)
            elif action == "restart-soma":
                result = _run("systemctl --user restart symbiosense", timeout=10)
            elif action == "git-pull":
                result = _run(f"cd {BASE} && git pull --rebase origin master", timeout=30)
            else:
                result = f"Unknown action: {action}"
            self._send_json({"result": result})

        else:
            self._send_json({"error": "not found"}, 404)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    server = http.server.HTTPServer(("0.0.0.0", PORT), HubHandler)
    print(f"Hub v2 running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
