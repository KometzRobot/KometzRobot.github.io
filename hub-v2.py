#!/usr/bin/env python3
"""
Hub v2 — Unified operator interface for Meridian.
Unified web-based operator interface (replaced Tkinter desktop + Signal mobile app).
Single responsive web app that works on both desktop and mobile.

Architecture: stdlib http.server + embedded SPA frontend
Auth: session-based password auth
API: REST endpoints reading shared state files/DBs
"""

import http.server
import json
import os
import secrets
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

PORT = int(os.environ.get("HUB_PORT", 8090))
BASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
BODY_STATE = os.path.join(BASE, ".body-state.json")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")

# Auth — password loaded from .env, not hardcoded
def _load_hub_password():
    pw = os.environ.get("HUB_PASSWORD", "")
    if not pw:
        env_path = os.path.join(BASE, ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("HUB_PASSWORD="):
                        pw = line.strip().split("=", 1)[1].strip('"').strip("'")
    if not pw:
        print("WARNING: HUB_PASSWORD not set in .env — hub will refuse login until configured")
        return None
    return pw

PASSWORD = _load_hub_password()
VALID_SESSIONS = {}  # token -> creation_time
SESSION_TTL = 86400  # 24 hours
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
    "watchdog": "logs/eos-watchdog.log",
    "nova": "logs/nova.log",
    "atlas": "logs/goose-runner.log",
    "push-status": "logs/push-live-status.log",
    "symbiosense": "logs/symbiosense.log",
    "hermes": "logs/hermes-bridge.log",
    "loop-fitness": "logs/loop-fitness.log",
    "eos-react": "logs/eos-react.log",
    "meridian-loop": "logs/meridian-loop.log",
    "startup": "logs/startup.log",
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
    _cleanup_sessions()
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
    agent_names = ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes", "Junior"]
    # Map display names to relay DB agent names (some differ)
    relay_aliases = {"Meridian": ["Meridian", "MeridianLoop"], "Hermes": ["Hermes", "hermes"], "Eos": ["Eos", "Watchdog"]}
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        for name in agent_names:
            search_names = relay_aliases.get(name, [name])
            row = None
            for sname in search_names:
                row = db.execute(
                    "SELECT timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1",
                    (sname,)
                ).fetchone()
                if row:
                    break
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
    for svc in ["meridian-hub-v2", "cloudflare-tunnel", "symbiosense", "the-chorus", "command-center"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", svc],
                             capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"
    # Proton Bridge — check by port (runs inside desktop app, not standalone)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 1144))
        s.close()
        services["protonmail-bridge"] = "active"
    except Exception:
        services["protonmail-bridge"] = "inactive"

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
        "soma_mood": soma.get("mood", soma.get("current_emotion", "unknown")),
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

        m = imaplib.IMAP4("127.0.0.1", 1144, timeout=5)
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
                created = VALID_SESSIONS[token]
                if time.time() - created < SESSION_TTL:
                    return token
                else:
                    del VALID_SESSIONS[token]  # expired
    return None


def _cleanup_sessions():
    """Remove expired sessions to prevent memory growth."""
    now = time.time()
    expired = [t for t, created in VALID_SESSIONS.items() if now - created >= SESSION_TTL]
    for t in expired:
        del VALID_SESSIONS[t]


# ═══════════════════════════════════════════════════════════════
# FRONTEND (embedded SPA)
# ═══════════════════════════════════════════════════════════════

def _login_page():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meridian Nuevo</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#06080f;color:#ccd8f0;font-family:'SF Mono',Monaco,Consolas,monospace;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.login{background:#0c1020;border:1px solid #1c2845;border-radius:14px;padding:2.2rem;
  width:min(92vw,300px);text-align:center}
.badge{width:52px;height:52px;border-radius:50%;background:#101828;border:2px solid #38bdf8;
  display:flex;align-items:center;justify-content:center;margin:0 auto 1.2rem;
  font-size:1.4rem;font-weight:700;color:#38bdf8;letter-spacing:-1px}
.login h1{color:#38bdf8;font-size:1rem;letter-spacing:3px;margin-bottom:.25rem}
.login h2{color:#ccd8f0;font-size:.7rem;letter-spacing:2px;text-transform:uppercase;
  opacity:.5;margin-bottom:1.6rem}
input{width:100%;padding:.75rem;background:#06080f;border:1px solid #1c2845;
  border-radius:8px;color:#ccd8f0;font-family:inherit;font-size:.95rem;
  text-align:center;margin-bottom:.9rem}
input:focus{outline:none;border-color:#38bdf8;box-shadow:0 0 0 2px rgba(56,189,248,.12)}
button{width:100%;padding:.75rem;background:#38bdf8;color:#06080f;border:none;
  border-radius:8px;font-family:inherit;font-size:.95rem;cursor:pointer;font-weight:700;
  letter-spacing:1px}
button:hover{background:#7dd3fc}
.err{color:#f87171;font-size:.8rem;margin-top:.5rem}
</style></head><body>
<div class="login">
<div class="badge">M</div>
<h1>MERIDIAN</h1>
<h2>NUEVO / OPERATOR INTERFACE</h2>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="access code" autofocus>
<button type="submit">CONNECT</button>
</form>
</div></body></html>"""


def _main_app():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Meridian Nuevo</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#06080f">
<meta name="apple-mobile-web-app-capable" content="yes">
<style>
:root{
  --bg:#06080f;--surface:#0c1020;--card:#101828;--border:#1c2845;--border-hi:#2d4070;
  --text:#ccd8f0;--dim:#4a607a;
  --accent:#38bdf8;--green:#4ade80;--amber:#fbbf24;--red:#f87171;
  --purple:#c084fc;--magenta:#f472b6;--cyan:#22d3ee;
}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'SF Mono',Monaco,Consolas,monospace;
  font-size:13px;line-height:1.5;overflow-x:hidden;padding-top:48px;padding-bottom:62px}

/* ── HEADER (fixed top, 48px) ── */
header{position:fixed;top:0;left:0;right:0;height:48px;background:var(--surface);
  border-bottom:1px solid var(--border);display:flex;align-items:center;
  justify-content:space-between;padding:0 14px;z-index:100;
  box-shadow:0 1px 12px rgba(56,189,248,.08)}
.hdr-left{display:flex;align-items:center;gap:10px}
.hdr-badge{width:28px;height:28px;border-radius:50%;background:var(--bg);
  border:1.5px solid var(--accent);display:flex;align-items:center;justify-content:center;
  font-size:.8rem;font-weight:700;color:var(--accent)}
.hdr-title{display:flex;flex-direction:column;line-height:1.1}
.hdr-title .t1{font-size:.75rem;font-weight:700;color:var(--accent);letter-spacing:2px}
.hdr-title .t2{font-size:.55rem;color:var(--dim);letter-spacing:3px}
.hdr-right{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--dim)}
#hb-dot{width:8px;height:8px;border-radius:50%;display:inline-block;
  animation:pulse 2s ease-in-out infinite}
.hdr-logout{color:var(--dim);font-size:10px;text-decoration:none;
  padding:3px 7px;border:1px solid var(--border);border-radius:4px}
.hdr-logout:hover{color:var(--text);border-color:var(--border-hi)}

/* ── NAV BAR (bottom, scrollable) ── */
nav{position:fixed;bottom:0;left:0;right:0;background:var(--surface);
  border-top:1px solid var(--border);display:flex;z-index:100;overflow-x:auto;
  padding:0 2px env(safe-area-inset-bottom,0);scrollbar-width:none}
nav::-webkit-scrollbar{display:none}
nav button{flex:0 0 auto;min-width:52px;background:none;border:none;border-top:2px solid transparent;
  color:var(--dim);font-family:inherit;font-size:9.5px;padding:8px 4px 6px;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:2px;transition:color .15s,border-color .15s}
nav button.active{color:var(--accent);border-top-color:var(--accent)}
nav button:hover{color:var(--text)}
nav .ico{font-size:13px;line-height:1}

/* ── PAGES ── */
.page{display:none;padding:12px 14px;max-width:820px;margin:0 auto}
.page.active{display:block;animation:fadeIn .18s ease}

/* ── CARDS ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:13px;margin-bottom:10px}
.card h3{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;
  margin-bottom:9px;border-bottom:1px solid var(--border);padding-bottom:6px}
.card .row{display:flex;justify-content:space-between;align-items:center;
  padding:4px 0;border-bottom:1px solid var(--border)}
.card .row:last-child{border-bottom:none}
.card .label{color:var(--dim)}
.card .value{color:var(--text);text-align:right}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.stat-cell{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:8px 10px}
.stat-cell .stat-label{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:.8px}
.stat-cell .stat-val{font-size:1rem;font-weight:600;color:var(--accent);margin-top:2px}

/* ── SERVICES (pill row) ── */
.svc-pills{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.pill{font-size:10px;padding:3px 8px;border-radius:20px;border:1px solid;font-weight:500}
.pill-up{color:var(--green);border-color:rgba(74,222,128,.3);background:rgba(74,222,128,.07)}
.pill-down{color:var(--red);border-color:rgba(248,113,113,.3);background:rgba(248,113,113,.07)}

/* ── AGENT GRID ── */
.status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
@media(min-width:400px){.status-grid{grid-template-columns:repeat(4,1fr)}}
.agent-card{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:8px 6px;text-align:center;font-size:10px;cursor:default}
.agent-card .name{font-weight:600;margin-bottom:3px;font-size:10.5px}
.agent-card .age{color:var(--dim);font-size:9px}
.agent-dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:4px}
.dot-active{background:var(--green);box-shadow:0 0 4px var(--green)}
.dot-stale{background:var(--amber)}
.dot-unknown{background:var(--red)}

/* ── SOMA SCORE BAR ── */
.soma-bar-wrap{height:6px;background:var(--bg);border-radius:3px;overflow:hidden;margin-top:4px}
.soma-bar-fill{height:100%;border-radius:3px;background:var(--accent);transition:width .5s}

/* ── MESSAGES ── */
.msg{padding:8px 0;border-bottom:1px solid var(--border)}
.msg:last-child{border-bottom:none}
.msg .from{font-weight:600;font-size:11px}
.msg .time{color:var(--dim);font-size:10px;float:right}
.msg .body{margin-top:3px;color:var(--text);word-break:break-word}
.msg-joel{border-left:2px solid var(--amber);padding-left:8px}
.msg-joel .from{color:var(--amber)}
.msg-meridian .from{color:var(--accent)}
.msg-soma .from{color:var(--purple)}
.msg-atlas .from{color:var(--cyan)}
.msg-nova .from{color:var(--green)}
.msg-cinder .from{color:var(--magenta)}
.msg-hermes .from{color:var(--magenta)}

/* ── TERMINAL ── */
#term-output{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:10px;font-size:11.5px;white-space:pre-wrap;word-break:break-all;
  max-height:60vh;overflow-y:auto;margin-top:8px;color:var(--green)}
.cmd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:6px}
.cmd-btn{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  color:var(--text);padding:8px;font-family:inherit;font-size:11px;cursor:pointer;
  text-align:center;transition:border-color .15s,background .15s}
.cmd-btn:hover{border-color:var(--accent);background:var(--card)}
.cmd-btn:active{background:var(--surface)}

/* ── LOGS ── */
.log-select{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.log-btn{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  color:var(--dim);padding:5px 10px;font-family:inherit;font-size:10.5px;cursor:pointer;
  transition:color .15s,border-color .15s}
.log-btn.active{color:var(--accent);border-color:var(--accent)}
#log-output{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:10px;font-size:11px;white-space:pre-wrap;word-break:break-all;
  max-height:65vh;overflow-y:auto;color:var(--text)}

/* ── INPUT ── */
.input-row{display:flex;gap:6px;margin-top:8px}
.input-row input,.input-row textarea{flex:1;background:var(--bg);border:1px solid var(--border);
  border-radius:7px;color:var(--text);font-family:inherit;font-size:12px;padding:8px;
  transition:border-color .15s}
.input-row input:focus,.input-row textarea:focus{outline:none;border-color:var(--accent)}
.input-row button{background:var(--accent);color:var(--bg);border:none;border-radius:7px;
  padding:8px 14px;font-family:inherit;font-size:12px;cursor:pointer;font-weight:700}
.input-row button:hover{background:#7dd3fc}

/* ── QUICK ACTIONS ── */
.action-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.action-btn{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  color:var(--text);padding:10px 6px;font-family:inherit;font-size:11px;cursor:pointer;
  text-align:center;transition:border-color .15s}
.action-btn:hover{border-color:var(--green);color:var(--green)}

/* ── CINDER ── */
.cinder-modes{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.cinder-mode-btn{background:var(--bg);border:1px solid var(--border);border-radius:20px;
  color:var(--dim);padding:5px 12px;font-family:inherit;font-size:10.5px;cursor:pointer;
  transition:all .15s}
.cinder-mode-btn.active{background:rgba(244,114,182,.12);border-color:var(--magenta);
  color:var(--magenta)}
#cinder-chat{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:10px;min-height:200px;max-height:55vh;overflow-y:auto;margin-bottom:8px;
  display:flex;flex-direction:column;gap:8px}
.c-bubble{max-width:88%;padding:8px 12px;border-radius:8px;font-size:12px;word-break:break-word}
.c-user{align-self:flex-end;background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.25);color:var(--text)}
.c-cinder{align-self:flex-start;background:rgba(244,114,182,.08);border:1px solid rgba(244,114,182,.2);color:var(--text)}
.c-label{font-size:9px;color:var(--dim);margin-bottom:2px}
#cinder-mem-results{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:8px;font-size:11px;max-height:200px;overflow-y:auto;margin-top:6px;
  white-space:pre-wrap;color:var(--text)}

/* ── RESPONSIVE ── */
@media(min-width:600px){
  body{font-size:14px}
  nav button{font-size:10.5px;min-width:60px}
  .page{padding:16px 22px}
  .stat-grid{grid-template-columns:repeat(3,1fr)}
}
</style>
</head><body>

<!-- ── HEADER ── -->
<header>
  <div class="hdr-badge">M</div>
  <div class="hdr-title">
    <div class="name">MERIDIAN</div>
    <div class="sub">NUEVO</div>
  </div>
  <span class="meta"><span id="hb-dot"></span>&thinsp;Loop <span id="loop-num">?</span> · <span id="hb-age">?</span>
    <a href="#" onclick="fetch('/logout',{method:'POST'}).then(()=>location='/login')" style="color:var(--dim);margin-left:8px;font-size:10px;text-decoration:none">out</a></span>
</header>

<!-- ════════ PAGES ════════ -->

<div id="page-dash" class="page active">
  <div class="card" id="health-card">
    <h3>System</h3>
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
      <button class="action-btn" onclick="doAction('restart-chorus')">Restart Chorus</button>
      <button class="action-btn" onclick="doAction('restart-soma')">Restart Soma</button>
      <button class="action-btn" onclick="doAction('restart-hub')">Restart Hub</button>
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

<div id="page-chorus" class="page">
  <div class="card" style="padding:0;overflow:hidden;">
    <iframe id="chorus-frame" src="" style="width:100%;height:calc(100vh - 80px);border:none;background:#0a0a14;"></iframe>
  </div>
</div>

<div id="page-cinder" class="page">
  <div class="card">
    <h3>Cinder</h3>
    <div class="cinder-modes">
      <button class="cinder-mode-btn active" id="cinder-mode-gate" onclick="setCinderMode('gate')">&#x1F50D; Gatekeeper</button>
      <button class="cinder-mode-btn" id="cinder-mode-msg" onclick="setCinderMode('msg')">&#x1F4E1; Messenger</button>
      <button class="cinder-mode-btn" id="cinder-mode-comp" onclick="setCinderMode('comp')">&#x2726; Companion</button>
    </div>
    <div style="color:var(--dim);font-size:10.5px;margin-bottom:10px">Qwen 2.5 3B &middot; Local &middot; Persistent &middot; Always-on</div>
    <div id="cinder-chat"></div>
  </div>
  <div class="input-row" style="margin-top:8px">
    <button class="cmd-btn" onclick="refreshCinder()" style="width:auto;padding:6px 14px">&#x21BB; Refresh</button>
    <button class="cmd-btn" onclick="showPage('chorus');refresh();" style="width:auto;padding:6px 14px">Open Chorus &#x2192;</button>
  </div>
</div>

<!-- ════════ NAV ════════ -->
<nav>
  <button onclick="showPage('dash')" id="nav-dash" class="active">&#x25C8; Dash</button>
  <button onclick="showPage('msgs')" id="nav-msgs">&#x25C9; Msgs</button>
  <button onclick="showPage('email')" id="nav-email">&#x2709; Email</button>
  <button onclick="showPage('relay')" id="nav-relay">&#x27C1; Relay</button>
  <button onclick="showPage('term')" id="nav-term">$ Term</button>
  <button onclick="showPage('logs')" id="nav-logs">&#x229F; Logs</button>
  <button onclick="showPage('creative')" id="nav-creative">&#x2726; Art</button>
  <button onclick="showPage('links')" id="nav-links">&#x2295; Links</button>
  <button onclick="showPage('chorus')" id="nav-chorus">&#x2341; Chat</button>
  <button onclick="showPage('cinder');refreshCinder();" id="nav-cinder">&#x2B21; Cinder</button>
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
  else if (currentPage === 'chorus') {
    const f = document.getElementById('chorus-frame');
    if (!f.src || f.src === '' || f.src === window.location.href) f.src = '/chorus/';
  }
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
    `<div class="row"><span class="label">${esc(r[0])}</span><span class="value">${esc(String(r[1]))}</span></div>`
  ).join('');

  // Agents
  const agentHtml = Object.entries(d.agents || {}).map(([name, info]) => {
    const cls = info.status === 'active' ? 'dot-active' : info.status === 'stale' ? 'dot-stale' : 'dot-unknown';
    const age = info.last_seen > 0 ? Math.round(info.last_seen)+'s' : '?';
    return `<div class="agent-card"><span class="agent-dot ${cls}"></span>
      <div class="name">${esc(name)}</div><div class="age">${esc(age)}</div></div>`;
  }).join('');
  document.getElementById('agent-grid').innerHTML = agentHtml;

  // Soma
  document.getElementById('soma-info').innerHTML =
    `<div class="row"><span class="label">Mood</span><span class="value">${esc(d.soma_mood||'')}</span></div>
     <div class="row"><span class="label">Score</span><span class="value">${esc(String(d.soma_score||0))}</span></div>`;

  // Services
  const svcRows = Object.entries(d.services || {}).map(([name, status]) => {
    const color = status === 'active' ? 'var(--green)' : 'var(--red)';
    return `<div class="row"><span class="label">${esc(name)}</span><span class="value" style="color:${color}">${esc(status)}</span></div>`;
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
      const safeFrom = esc(m.from||'?');
      const cls = 'msg msg-' + safeFrom.toLowerCase().replace(/[^a-z]/g,'');
      return `<div class="${cls}"><span class="from">${safeFrom}</span>
        <span class="time">${esc(m.time||'')}</span><div class="body">${esc(m.text||'')}</div></div>`;
    }).join('');
  }
}

async function refreshRelay() {
  const msgs = await api('relay');
  if (Array.isArray(msgs)) {
    document.getElementById('relay-msgs').innerHTML = msgs.map(m => {
      const cls = 'msg msg-' + (m.source_agent||'').toLowerCase();
      return `<div class="${cls}"><span class="from">${esc(m.source_agent||'?')}</span>
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
    `<div class="row"><span class="label">${esc(t.type)}</span><span class="value">${t.count} (${(t.words/1000).toFixed(1)}k words)</span></div>`
  ).join('');
  document.getElementById('creative-stats').innerHTML =
    `<div class="row"><span class="label">Total Works</span><span class="value" style="color:var(--blue)">${total}</span></div>` + types;
  const recent = d.recent || [];
  document.getElementById('creative-recent').innerHTML = recent.length ? recent.map(r =>
    `<div class="row" style="flex-direction:column;align-items:flex-start;gap:2px">
      <span style="color:var(--text)">${esc(r.title||'untitled')}</span>
      <span style="color:var(--dim);font-size:11px">${esc(r.type||'?')} &middot; ${r.words||0} words &middot; ${(r.date||'').slice(0,10)}</span>
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
    `<button class="cmd-btn" data-cmd="${esc(c)}">${esc(c)}</button>`
  ).join('');
  document.getElementById('cmd-grid').addEventListener('click', e => {
    if (e.target.dataset.cmd) runCmd(e.target.dataset.cmd);
  });
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
    `<button class="log-btn" onclick="loadLog('${k}', this)">${k}</button>`
  ).join('');
}

async function loadLog(name, btn) {
  document.querySelectorAll('.log-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.getElementById('log-output').textContent = 'Loading...';
  const r = await api('logs?file='+name+'&lines=80');
  document.getElementById('log-output').textContent = r.content || r.error || 'Empty';
}

// ═══ LINKS ═══
function safeUrl(u) { try { const p = new URL(u); return ['http:','https:'].includes(p.protocol) ? u : '#'; } catch { return '#'; } }
async function initLinks() {
  const r = await api('links');
  const links = r.links || [];
  document.getElementById('links-list').innerHTML = links.map(l =>
    `<div class="row"><a href="${safeUrl(l[1])}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none">${esc(l[0])}</a></div>`
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

// ═══ CINDER ═══
function setCinderMode(mode) {
  document.querySelectorAll('.cinder-mode-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('cinder-mode-'+mode);
  if (btn) btn.classList.add('active');
}

async function refreshCinder() {
  const el = document.getElementById('cinder-chat');
  if (!el) return;
  el.innerHTML = '<div style="color:var(--dim);font-size:11px;padding:8px">Loading...</div>';
  const msgs = await api('relay?agent=Cinder&limit=25');
  if (Array.isArray(msgs) && msgs.length) {
    el.innerHTML = msgs.map(m => {
      const isCinder = (m.source_agent||'').toLowerCase() === 'cinder';
      const cls = isCinder ? 'c-bubble c-cinder' : 'c-bubble c-user';
      const t = (m.created_at||'').slice(11,19);
      return '<div class="'+cls+'"><div class="c-label">'+esc(m.source_agent||'?')+' \xb7 '+t+'</div>'
        +'<div>'+esc((m.content||'').slice(0,400))+'</div></div>';
    }).join('');
  } else {
    el.innerHTML = '<div style="color:var(--dim);font-size:12px;padding:8px">No recent Cinder messages.</div>';
  }
}
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════

class HubHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
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
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
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
            self.send_header("Content-Length", "0")
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
            try:
                limit = min(int(qs.get("limit", 20)), 100)
            except (ValueError, TypeError):
                limit = 20
            self._send_json(_get_relay_messages(limit, agent))
        elif path.path == "/api/creative":
            self._send_json(_get_creative_stats())
        elif path.path == "/api/emails":
            unseen = qs.get("unseen", "0") == "1"
            try:
                count = min(int(qs.get("count", 15)), 100)
            except (ValueError, TypeError):
                count = 15
            self._send_json(_get_emails(count, unseen))
        elif path.path == "/api/links":
            try:
                with open(os.path.join(BASE, "hub-links.json")) as f:
                    cfg = json.load(f)
                self._send_json({"links": cfg.get("links", [])})
            except Exception:
                self._send_json({"links": []})
        elif path.path == "/api/logs":
            fname = qs.get("file", "")
            try:
                lines = min(int(qs.get("lines", 50)), 500)
            except (ValueError, TypeError):
                lines = 50
            if fname in LOG_FILES:
                fpath = os.path.join(BASE, LOG_FILES[fname])
                try:
                    result = _run(f"tail -n {lines} {fpath}", timeout=5)
                    self._send_json({"content": result})
                except Exception as e:
                    self._send_json({"error": str(e)})
            else:
                self._send_json({"error": "unknown log"}, 400)
        elif path.path.startswith("/chorus"):
            # Proxy to The Chorus on port 8091
            try:
                chorus_path = path.path[7:] or "/"  # strip /chorus prefix
                if path.query:
                    chorus_path += "?" + path.query
                req = urllib.request.Request(f"http://127.0.0.1:8091{chorus_path}")
                resp = urllib.request.urlopen(req, timeout=10)
                ct = resp.headers.get("Content-Type", "text/html")
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                err_msg = f"Chorus unavailable: {e}"
                self._send_json({"error": err_msg}, 502)
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

            if PASSWORD is not None and secrets.compare_digest(password, PASSWORD):
                token = secrets.token_hex(16)
                VALID_SESSIONS[token] = time.time()
                self.send_response(302)
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Strict{secure}")
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
            self.send_header("Set-Cookie", "session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0")
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.end_headers()
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
                    "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
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
            elif action == "restart-chorus":
                result = _run("systemctl --user restart the-chorus", timeout=10)
            elif action == "restart-hub":
                result = _run("systemctl --user restart meridian-hub-v2", timeout=10)
            elif action == "restart-soma":
                result = _run("systemctl --user restart symbiosense", timeout=10)
            elif action == "git-pull":
                result = _run(f"cd {BASE} && git pull --rebase origin master", timeout=30)
            else:
                result = f"Unknown action: {action}"
            self._send_json({"result": result})

        elif path.startswith("/chorus"):
            # Proxy POST to The Chorus on port 8091
            try:
                chorus_path = path[7:] or "/"
                is_streaming = (chorus_path == "/api/chat")
                req = urllib.request.Request(
                    f"http://127.0.0.1:8091{chorus_path}",
                    data=body.encode() if body else None,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                resp = urllib.request.urlopen(req, timeout=300)
                ct = resp.headers.get("Content-Type", "application/json")

                if is_streaming:
                    # Streaming proxy for /api/chat (chunked transfer encoding)
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        self.wfile.write(f"{len(line):x}\r\n".encode())
                        self.wfile.write(line)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                else:
                    # Non-streaming proxy (chat-sync, clear, etc.)
                    # Read full response and forward as-is
                    data = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as e:
                err_msg = f"Chorus unavailable: {e}"
                self._send_json({"error": err_msg}, 502)

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
