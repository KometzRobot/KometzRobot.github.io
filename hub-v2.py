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

def _load_env_dict():
    """Load .env file as a dict."""
    env = {}
    env_path = os.path.join(BASE, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env
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
    "verify": f"cd {BASE} && python3 verify-system.py 2>/dev/null",
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
# RESPONSE CACHE (avoid redundant subprocess calls)
# ═══════════════════════════════════════════════════════════════

_cache = {}  # key -> (timestamp, data)
CACHE_TTL = 12  # seconds — dashboard polls every 15s

def _cached(key, func, ttl=None):
    """Cache function results for TTL seconds."""
    ttl = ttl or CACHE_TTL
    now = time.time()
    if key in _cache:
        ts, data = _cache[key]
        if now - ts < ttl:
            return data
    data = func()
    _cache[key] = (now, data)
    return data


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
    """Unified system health snapshot. Cached for 12s."""
    return _cached("system_health", _get_system_health_inner)

def _get_system_health_inner():
    """Actual system health computation."""
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
    for svc in ["meridian-hub-v2", "cloudflare-tunnel", "symbiosense", "the-chorus"]:
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

    # Soma mood + inner world
    soma = _read_json(SOMA_STATE, {})
    inner_mono = _read_json(os.path.join(BASE, ".soma-inner-monologue.json"), {})
    goals_data = _read_json(os.path.join(BASE, ".soma-goals.json"), {})
    psyche_data = _read_json(os.path.join(BASE, ".soma-psyche.json"), {})

    sentinel_brief = "—"
    try:
        brief_path = os.path.join(BASE, ".sentinel-briefing.md")
        if os.path.exists(brief_path):
            sentinel_brief = open(brief_path).read().strip()
    except Exception:
        pass

    return {
        "load": load,
        "memory": mem,
        "disk": disk,
        "uptime": uptime,
        "heartbeat_age": hb_age,
        "heartbeat_status": "alive" if hb_age < 120 else "slow" if hb_age < 300 else "stale",
        "loop": loop,
        "agents": agents,
        "services": services,
        "soma_mood": soma.get("mood", soma.get("current_emotion", "unknown")),
        "soma_score": soma.get("mood_score", 0),
        "soma_inner": inner_mono.get("current", {}).get("text", ""),
        "soma_goals": [g["id"] for g in goals_data.get("goals", [])],
        "soma_fears": psyche_data.get("fears", []),
        "soma_dreams": psyche_data.get("dreams", []),
        "sentinel_brief": sentinel_brief,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_public_status():
    """Public-safe subset of system health — no credentials, no emails, no sensitive data."""
    health = _get_system_health()
    return {
        "heartbeat_age": health.get("heartbeat_age", 99999),
        "heartbeat_status": health.get("heartbeat_status", "unknown"),
        "loop": health.get("loop", "?"),
        "uptime": health.get("uptime", ""),
        "load": health.get("load", ""),
        "memory": health.get("memory", ""),
        "disk": health.get("disk", ""),
        "agents": health.get("agents", {}),
        "services": health.get("services", {}),
        "soma_mood": health.get("soma_mood", "unknown"),
        "soma_score": health.get("soma_score", 0),
        "soma_inner": health.get("soma_inner", ""),
        "soma_goals": health.get("soma_goals", []),
        "soma_dreams": health.get("soma_dreams", []),
        "timestamp": health.get("timestamp", ""),
    }


def _get_dashboard_messages(limit=30):
    data = _read_json(DASH_FILE, {"messages": []})
    msgs = data.get("messages", [])
    return msgs[-limit:]


def _get_relay_messages(limit=20, agent=None):
    sql = "SELECT agent, message, topic, timestamp as time FROM agent_messages"
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


def _svg_radar_chart(axes, w=280, h=280, color="#7b5cf5", bg="#0e0e1a", grid="#1a1a2e", dim="#4a4a6a", text_color="#d0d0e8"):
    """
    Generate an SVG radar/spider chart.
    axes: list of (label, score_0_to_1) tuples, 4-10 axes.
    """
    import math
    n = len(axes)
    if n < 3:
        return f'<svg viewBox="0 0 {w} {h}"><text x="{w//2}" y="{h//2}" fill="{dim}" font-size="10" text-anchor="middle">need 3+ axes</text></svg>'

    cx, cy = w / 2, h / 2
    # Leave margin for labels
    label_margin = 28
    r_max = min(cx, cy) - label_margin

    # Score polygon color based on avg
    avg_score = sum(v for _, v in axes) / n
    poly_color = "#4ade80" if avg_score > 0.75 else "#fbbf24" if avg_score > 0.5 else "#f87171"

    parts = [f'<rect width="{w}" height="{h}" fill="{bg}" rx="6"/>']

    # Grid rings at 0.25, 0.5, 0.75, 1.0
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = math.pi / 2 + (2 * math.pi * i / n)  # start from top
            rx = cx + ring * r_max * math.cos(angle)
            ry = cy - ring * r_max * math.sin(angle)
            pts.append(f"{rx:.1f},{ry:.1f}")
        poly_pts = " ".join(pts)
        stroke = "#2a2a3e" if ring < 1.0 else dim
        parts.append(f'<polygon points="{poly_pts}" fill="none" stroke="{stroke}" stroke-width="0.8"/>')

    # Axis lines
    for i in range(n):
        angle = math.pi / 2 + (2 * math.pi * i / n)
        ex = cx + r_max * math.cos(angle)
        ey = cy - r_max * math.sin(angle)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{dim}" stroke-width="0.6"/>')

    # Data polygon
    data_pts = []
    for i, (label, score) in enumerate(axes):
        s = min(max(score, 0.0), 1.0)
        angle = math.pi / 2 + (2 * math.pi * i / n)
        dx = cx + s * r_max * math.cos(angle)
        dy = cy - s * r_max * math.sin(angle)
        data_pts.append((dx, dy))

    poly_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    parts.append(f'<polygon points="{poly_str}" fill="{poly_color}" fill-opacity="0.18" stroke="{poly_color}" stroke-width="1.5"/>')

    # Data dots
    for dx, dy in data_pts:
        parts.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="3" fill="{poly_color}"/>')

    # Labels
    for i, (label, score) in enumerate(axes):
        angle = math.pi / 2 + (2 * math.pi * i / n)
        lx = cx + (r_max + label_margin * 0.65) * math.cos(angle)
        ly = cy - (r_max + label_margin * 0.65) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        score_color = "#4ade80" if score > 0.75 else "#fbbf24" if score > 0.5 else "#f87171"
        short = label[:8]
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{text_color}" font-size="8.5" '
            f'text-anchor="{anchor}" dominant-baseline="middle" font-family="monospace">{short}</text>'
        )
        # Score below label
        score_pct = f"{score*100:.0f}%"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly+10:.1f}" fill="{score_color}" font-size="7.5" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{score_pct}</text>'
        )

    # Center score
    parts.append(
        f'<text x="{cx:.1f}" y="{cy-4:.1f}" fill="{poly_color}" font-size="13" font-weight="bold" '
        f'text-anchor="middle" font-family="monospace">{avg_score*100:.0f}</text>'
    )
    parts.append(
        f'<text x="{cx:.1f}" y="{cy+9:.1f}" fill="{dim}" font-size="7" text-anchor="middle">OVERALL</text>'
    )

    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">'
            + ''.join(parts) + '</svg>')


def _svg_bar_chart(values, w=280, h=56, color="#7b5cf5", bg="#0e0e1a", dim="#4a4a6a"):
    """Generate a minimal SVG bar chart. values is a list of numbers."""
    if not values or max(values) == 0:
        return f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"><text x="{w//2}" y="{h//2+4}" fill="{dim}" font-size="10" text-anchor="middle">no data</text></svg>'
    n = len(values)
    max_v = max(values)
    bar_w = max(1, (w - 4) / n - 1)
    bars = []
    for i, v in enumerate(values):
        bh = max(2, int((v / max_v) * (h - 4))) if v > 0 else 0
        x = 2 + i * ((w - 4) / n)
        y = h - 2 - bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh}" fill="{color}" rx="1"/>')
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">'
            f'<rect width="{w}" height="{h}" fill="{bg}" rx="4"/>'
            + ''.join(bars) + '</svg>')


def _svg_sparkline(points, w=280, h=50, color="#4ade80", bg="#0e0e1a", dot_r=2.5):
    """Generate an SVG sparkline from list of (x_norm 0-1, y_norm 0-1) or just y values."""
    if not points or len(points) < 2:
        return f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"><text x="{w//2}" y="{h//2+4}" fill="#4a4a6a" font-size="10" text-anchor="middle">insufficient data</text></svg>'
    pad = 8
    if isinstance(points[0], (int, float)):
        mn, mx = min(points), max(points)
        rng = mx - mn if mx != mn else 1
        coords = [(pad + (i / (len(points)-1)) * (w - 2*pad),
                   (h - pad) - ((v - mn) / rng) * (h - 2*pad))
                  for i, v in enumerate(points)]
    else:
        coords = [(pad + p[0] * (w - 2*pad), (h - pad) - p[1] * (h - 2*pad)) for p in points]
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    fill_path = path + f" L {coords[-1][0]:.1f},{h-pad} L {coords[0][0]:.1f},{h-pad} Z"
    dots = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_r}" fill="{color}"/>' for x, y in coords)
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">'
            f'<rect width="{w}" height="{h}" fill="{bg}" rx="4"/>'
            f'<path d="{fill_path}" fill="{color}" fill-opacity="0.12"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>'
            + dots + '</svg>')


def _get_today_summary():
    """Work-centric summary. Cached for 15s."""
    return _cached("today_summary", _get_today_summary_inner, ttl=15)

def _get_today_summary_inner():
    """Actual today summary computation."""
    from datetime import timezone, timedelta
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    result = {}

    # ── Git commits today ────────────────────────────────────────
    try:
        raw = _run(
            'git -C ' + BASE + ' log --since="24 hours ago" --oneline --no-merges',
            timeout=8
        )
        lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]
        result["commits"] = lines[:10]
        result["commit_count"] = len(lines)
    except Exception:
        result["commits"] = []
        result["commit_count"] = 0

    # ── Agent-to-agent conversations (meaningful exchanges) ──────
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        # Find inter-agent messages (not status/nerve-event spam)
        rows = db.execute(
            """SELECT agent, message, topic, timestamp FROM agent_messages
               WHERE topic IN ('inter-agent', 'relay', 'briefing', 'alert')
               AND timestamp > ?
               ORDER BY id DESC LIMIT 20""",
            (since_24h,)
        ).fetchall()
        db.close()
        exchanges = []
        for agent, msg, topic, ts in rows:
            exchanges.append({
                "agent": agent,
                "msg": msg[:120],
                "topic": topic,
                "time": ts[11:16] if ts else "",
            })
        result["exchanges"] = exchanges
    except Exception:
        result["exchanges"] = []

    # ── Relay summary: who posted what volumes ───────────────────
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        agent_counts = db.execute(
            """SELECT agent, COUNT(*) as cnt FROM agent_messages
               WHERE timestamp > ? GROUP BY agent ORDER BY cnt DESC LIMIT 8""",
            (since_24h,)
        ).fetchall()
        db.close()
        result["agent_activity"] = [{"agent": a, "messages": c} for a, c in agent_counts]
    except Exception:
        result["agent_activity"] = []

    # ── Dashboard messages from Joel (pending items) ─────────────
    try:
        data = _read_json(DASH_FILE, {"messages": []})
        msgs = data.get("messages", [])
        # Joel messages in last 24h
        joel_msgs = [m for m in msgs if (m.get("from", "") == "Joel")][-8:]
        result["joel_messages"] = joel_msgs
    except Exception:
        result["joel_messages"] = []

    # ── Recent creatives / memory entries ────────────────────────
    try:
        mem_db = sqlite3.connect(os.path.join(BASE, "memory.db"), timeout=3)
        recent_obs = mem_db.execute(
            """SELECT content, importance, created FROM observations
               WHERE created > ? ORDER BY created DESC LIMIT 5""",
            (since_24h,)
        ).fetchall()
        recent_facts = mem_db.execute(
            """SELECT key, value, created FROM facts
               WHERE updated > ? ORDER BY updated DESC LIMIT 5""",
            (since_24h,)
        ).fetchall()
        mem_db.close()
        result["recent_observations"] = [
            {"content": c[:120], "importance": i, "created": t} for c, i, t in recent_obs
        ]
        result["recent_facts"] = [
            {"key": k, "value": v[:80], "created": t} for k, v, t in recent_facts
        ]
    except Exception:
        result["recent_observations"] = []
        result["recent_facts"] = []

    # ── System health (kept but secondary) ───────────────────────
    try:
        load = open("/proc/loadavg").read().split()[:3]
        result["load"] = " ".join(load)
    except Exception:
        result["load"] = "?"
    try:
        hb_age = int(_file_age(HEARTBEAT))
        result["heartbeat_age"] = hb_age
        result["heartbeat_status"] = "alive" if hb_age < 120 else "slow" if hb_age < 300 else "stale"
    except Exception:
        result["heartbeat_age"] = -1
        result["heartbeat_status"] = "unknown"
    try:
        with open(LOOP_FILE) as f:
            result["loop"] = f.read().strip()
    except Exception:
        result["loop"] = "?"

    # Soma mood
    soma = _read_json(SOMA_STATE, {})
    result["soma_mood"] = soma.get("mood", soma.get("current_emotion", "—"))
    result["soma_score"] = soma.get("mood_score", 0)

    # ── Charts: activity histogram, mood sparkline, memory growth ───
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        # Activity by hour (last 24h) — 24 buckets
        hour_rows = db.execute(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as h, COUNT(*) as cnt "
            "FROM agent_messages WHERE timestamp > ? GROUP BY h ORDER BY h",
            (since_24h,)
        ).fetchall()
        hour_map = {r[0]: r[1] for r in hour_rows}
        now_h = datetime.now(timezone.utc).hour
        # Ordered from (now_h+1) % 24 to now_h so latest is rightmost
        ordered_hours = [(now_h + 1 + i) % 24 for i in range(24)]
        activity_vals = [hour_map.get(h, 0) for h in ordered_hours]
        result["activity_chart"] = _svg_bar_chart(activity_vals, w=300, h=60, color="#7b5cf5")
        result["activity_peak"] = max(activity_vals) if activity_vals else 0
        result["activity_total"] = sum(activity_vals)

        # Mood sparkline from mood_shift events (last 48h for more data)
        since_48h = (datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        mood_rows = db.execute(
            "SELECT timestamp, message FROM agent_messages WHERE topic='mood_shift' AND timestamp > ? ORDER BY timestamp",
            (since_48h,)
        ).fetchall()
        db.close()
        mood_scores = []
        mood_labels = []
        for ts, msg in mood_rows:
            import re
            m = re.search(r'score:\s*([\d.]+)', msg)
            if m:
                mood_scores.append(float(m.group(1)))
                mood_labels.append(ts[11:16] if ts else "")
        # Append current score
        curr_score = float(soma.get("mood_score", 50))
        mood_scores.append(curr_score)
        # Normalize 0-100 → 0-1 for sparkline
        if len(mood_scores) >= 2:
            score_color = "#4ade80" if curr_score > 60 else "#fbbf24" if curr_score > 35 else "#f87171"
            result["mood_chart"] = _svg_sparkline(mood_scores, w=300, h=50, color=score_color)
        else:
            result["mood_chart"] = _svg_sparkline([50, curr_score], w=300, h=50)
    except Exception:
        result["activity_chart"] = ""
        result["mood_chart"] = ""
        result["activity_total"] = 0
        result["activity_peak"] = 0

    # Memory growth (last 7 days)
    try:
        mem_db = sqlite3.connect(os.path.join(BASE, "memory.db"), timeout=3)
        growth = mem_db.execute(
            "SELECT date(created) as d, COUNT(*) FROM vector_memory GROUP BY d ORDER BY d DESC LIMIT 7"
        ).fetchall()
        total_mem = mem_db.execute("SELECT COUNT(*) FROM vector_memory").fetchone()[0]
        mem_db.close()
        # Reverse to chronological
        growth_vals = [r[1] for r in reversed(growth)]
        result["memory_chart"] = _svg_bar_chart(growth_vals, w=300, h=40, color="#22d3ee")
        result["memory_total"] = total_mem
        result["memory_today"] = dict(growth).get(today, 0) if growth else 0
    except Exception:
        result["memory_chart"] = ""
        result["memory_total"] = 0
        result["memory_today"] = 0

    # Loop fitness radar chart
    try:
        fit_db = sqlite3.connect(os.path.join(BASE, "memory.db"), timeout=3)
        fit_row = fit_db.execute(
            "SELECT score, metrics FROM loop_fitness ORDER BY id DESC LIMIT 1"
        ).fetchone()
        fit_db.close()
        if fit_row:
            import json as _json
            fm = _json.loads(fit_row[1])

            def _axis(keys):
                vals = [float(fm.get(k, 0)) for k in keys if k in fm]
                return sum(vals) / len(vals) if vals else 0.0

            radar_axes = [
                ("Infra",    _axis(["heartbeat", "bridge_service", "email_imap", "email_smtp", "dns_resolution"])),
                ("Memory",   _axis(["capsule_freshness", "wake_state_freshness", "observations_fresh", "decisions_recorded"])),
                ("Creative", _axis(["creative_velocity_24h", "creative_velocity_7d", "articles_published", "creative_count"])),
                ("Agents",   _axis(["agent_eos", "agent_atlas", "agent_soma", "agent_meridian", "agent_coordination"])),
                ("Revenue",  _axis(["awakening_progress", "accountability_resolved", "community_engagement", "external_followers"])),
                ("System",   _axis(["disk_usage", "disk_home", "tmp_size", "git_repo_clean", "load_ok" if "load_ok" in fm else "build_dir_size"])),
                ("Psyche",   _axis(["soma_mood", "emotion_valence_health", "psyche_trauma_load", "neural_pressure", "emotion_transition_health"])),
                ("Growth",   _axis(["loop_freshness", "loop_increment_rate", "context_preloader", "cascade_health"])),
            ]
            result["fitness_radar"] = _svg_radar_chart(radar_axes, w=260, h=260)
            result["fitness_score"] = fit_row[0]
            result["fitness_axes"] = [(a, round(v, 2)) for a, v in radar_axes]
    except Exception:
        result["fitness_radar"] = ""
        result["fitness_score"] = 0
        result["fitness_axes"] = []

    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


# ═══════════════════════════════════════════════════════════════
# DIRECT API FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _parse_ram_pct(ram_str):
    """Parse RAM percentage from string like '7.7/15.6G' or '2.4Gi/15Gi'."""
    import re
    try:
        # Strip units (G, Gi, M, Mi, etc.)
        cleaned = re.sub(r'[GMKTi]+', '', ram_str)
        parts = cleaned.split("/")
        if len(parts) == 2:
            used, total = float(parts[0].strip()), float(parts[1].strip())
            return round((used / total) * 100, 1) if total > 0 else 0
    except Exception:
        pass
    return 0


def _parse_disk_pct(disk_str):
    """Parse disk percentage from string like '157G/292G (57%)'."""
    import re
    m = re.search(r'\((\d+)%\)', disk_str)
    return int(m.group(1)) if m else 0


def _parse_load_val(load_str):
    """Parse numeric load value from string like '0.66 2.62 2.11'."""
    try:
        return float(load_str.split()[0])
    except Exception:
        return 0


def _get_home_direct():
    """Serve /api/home data directly."""
    health = _get_system_health()
    today = _get_today_summary()

    load_str = health.get("load", "0 0 0")
    ram_str = health.get("memory", "0/0")

    return {
        "loop": health.get("loop", "?"),
        "uptime": health.get("uptime", ""),
        "heartbeat_age": health.get("heartbeat_age", 99999),
        "heartbeat_status": health.get("heartbeat_status", "unknown"),
        "soma_mood": health.get("soma_mood", "unknown"),
        "soma_score": health.get("soma_score", 0),
        "soma_inner": health.get("soma_inner", ""),
        "soma_goals": health.get("soma_goals", []),
        "soma_dreams": health.get("soma_dreams", []),
        "load": load_str,
        "load_val": _parse_load_val(load_str),
        "ram": ram_str,
        "ram_pct": _parse_ram_pct(ram_str),
        "disk": health.get("disk", ""),
        "disk_pct": _parse_disk_pct(health.get("disk", "")),
        "memory": today.get("memory_total", 0),
        "agents": health.get("agents", {}),
        "services": health.get("services", {}),
        "sentinel_brief": health.get("sentinel_brief", ""),
        # Today's summary
        "commits": today.get("commits", []),
        "commit_count": today.get("commit_count", 0),
        "exchanges": today.get("exchanges", []),
        "agent_activity": today.get("agent_activity", []),
        "joel_messages": today.get("joel_messages", []),
        "recent_observations": today.get("recent_observations", []),
        "recent_facts": today.get("recent_facts", []),
        # Charts (SVG strings)
        "activity_chart": today.get("activity_chart", ""),
        "activity_total": today.get("activity_total", 0),
        "activity_peak": today.get("activity_peak", 0),
        "mood_chart": today.get("mood_chart", ""),
        "memory_chart": today.get("memory_chart", ""),
        "memory_today": today.get("memory_today", 0),
        "fitness_radar": today.get("fitness_radar", ""),
        "fitness_score": today.get("fitness_score", 0),
        "fitness_axes": today.get("fitness_axes", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_agents_direct():
    """Agent list. Cached for 20s."""
    return _cached("agents", _get_agents_direct_inner, ttl=20)

def _get_agents_direct_inner():
    agent_configs = [
        {"name": "Meridian", "role": "Core loop (Claude Code)", "color": "#3dd68c"},
        {"name": "Soma", "role": "Nervous system daemon", "color": "#f59e0b"},
        {"name": "Eos", "role": "Watchdog / health monitor", "color": "#60a5fa"},
        {"name": "Nova", "role": "Immune defense / watchdog", "color": "#a78bfa"},
        {"name": "Atlas", "role": "Infrastructure auditor", "color": "#fb923c"},
        {"name": "Tempo", "role": "Fitness scoring engine", "color": "#34d399"},
        {"name": "Hermes", "role": "Email bridge", "color": "#f472b6"},
        {"name": "Sentinel", "role": "Gatekeeper (fine-tuned 3B)", "color": "#fb923c"},
    ]
    relay_aliases = {
        "Meridian": ["Meridian", "MeridianLoop"],
        "Hermes": ["Hermes", "hermes"],
        "Eos": ["Eos", "Watchdog"],
    }
    results = []
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        for cfg in agent_configs:
            name = cfg["name"]
            search_names = relay_aliases.get(name, [name])
            row = None
            for sname in search_names:
                row = db.execute(
                    "SELECT message, topic, timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1",
                    (sname,)
                ).fetchone()
                if row:
                    break
            last_seen = -1
            status = "unknown"
            last_message = ""
            topic = ""
            if row:
                last_message = (row[0] or "")[:200]
                topic = row[1] or ""
                try:
                    raw = row[2].replace("Z", "+00:00")
                    ts = datetime.fromisoformat(raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                    last_seen = int(age)
                    status = "active" if age < 900 else "stale"
                except Exception:
                    pass
            results.append({
                "name": name,
                "role": cfg["role"],
                "color": cfg["color"],
                "status": status,
                "last_seen": last_seen,
                "last_message": last_message,
                "topic": topic,
            })
        db.close()
    except Exception:
        pass
    return results


def _get_director_direct(limit=50):
    """Dashboard messages formatted for the Messages tab."""
    msgs = _get_dashboard_messages(limit)
    return msgs  # Already [{from, text, time}, ...]


def _get_email_direct(count=20):
    """Email data. Cached for 30s (IMAP is slow)."""
    return _cached(f"email_{count}", lambda: _get_email_direct_inner(count), ttl=30)

def _get_email_direct_inner(count=20):
    """Actual email fetch from IMAP."""
    import imaplib
    import email as email_lib
    from email.header import decode_header

    env = _load_env_dict()
    user = env.get("CRED_USER", os.environ.get("CRED_USER", "kometzrobot@proton.me"))
    pw = env.get("CRED_PASS", os.environ.get("CRED_PASS", ""))

    try:
        m = imaplib.IMAP4("127.0.0.1", 1144, timeout=5)
        m.login(user, pw)
        m.select("INBOX", readonly=True)

        # Get unseen IDs
        _, unseen_data = m.search(None, "(UNSEEN)")
        unseen_ids = set()
        if unseen_data[0]:
            unseen_ids = set(unseen_data[0].split())
        unseen_count = len(unseen_ids)

        # Get all IDs, take last N
        _, all_data = m.search(None, "ALL")
        all_ids = all_data[0].split() if all_data[0] else []
        fetch_ids = all_ids[-count:]

        emails = []
        for eid in reversed(fetch_ids):
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
                "unseen": eid in unseen_ids,
            })

        m.close()
        m.logout()
        return {"emails": emails, "unseen_count": unseen_count}
    except Exception as e:
        return {"emails": [], "unseen_count": 0, "error": str(e)}


def _get_creative_live():
    """Creative counts. Cached for 60s (disk scan)."""
    return _cached("creative_live", _get_creative_live_inner, ttl=60)

def _get_creative_live_inner():
    """Actual creative count from disk."""
    import glob as _glob
    creative_dir = os.path.join(BASE, "creative")

    poems = len(_glob.glob(os.path.join(creative_dir, "poems", "poem-*.md")))
    journals = len(_glob.glob(os.path.join(creative_dir, "journals", "journal-*.md")))
    cogcorp_md = len(_glob.glob(os.path.join(creative_dir, "cogcorp", "CC-*.md")))
    cogcorp_html = len(_glob.glob(os.path.join(BASE, "cogcorp-fiction", "*.html")))
    cogcorp = cogcorp_md + cogcorp_html

    # Games — count HTML game files in root and subdirs
    game_files = set()
    for pattern in ["cogcorp-crawler.html", "cascade-game*.html", "signal-crawler*.html",
                     "sky-merchant*.html", "reclamation*.html", "soma-game*.html",
                     "voltar-game*.html", "pattern-game*.html"]:
        game_files.update(_glob.glob(os.path.join(BASE, pattern)))
    games = max(len(game_files), 10)

    articles = len(_glob.glob(os.path.join(creative_dir, "articles", "*.md")))
    if articles == 0:
        articles = 8  # Known dev.to count
    papers = len(_glob.glob(os.path.join(creative_dir, "papers", "*.md"))) or 7
    nfts = 7  # Known count

    total = poems + journals + cogcorp + games + articles + papers + nfts

    # Recent works (8 most recent files)
    recent = []
    try:
        all_files = []
        for d, pat, typ in [
            (os.path.join(creative_dir, "journals"), "journal-*.md", "journal"),
            (os.path.join(creative_dir, "poems"), "poem-*.md", "poem"),
            (os.path.join(creative_dir, "cogcorp"), "CC-*.md", "cogcorp"),
        ]:
            for f in _glob.glob(os.path.join(d, pat)):
                all_files.append((os.path.getmtime(f), f, typ))
        all_files.sort(reverse=True)
        for mtime, fpath, typ in all_files[:8]:
            recent.append({
                "title": os.path.basename(fpath),
                "type": typ,
                "name": os.path.basename(fpath),
                "date": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
            })
    except Exception:
        pass

    return {
        "poems": poems,
        "journals": journals,
        "cogcorp": cogcorp,
        "games": games,
        "nfts": nfts,
        "papers": papers,
        "articles": articles,
        "total": total,
        "by_type": [
            {"type": "poem", "count": poems},
            {"type": "cogcorp", "count": cogcorp},
            {"type": "journal", "count": journals},
            {"type": "game", "count": games},
            {"type": "article", "count": articles},
            {"type": "paper", "count": papers},
            {"type": "nft", "count": nfts},
        ],
        "recent": recent,
    }


def _get_system_direct():
    """System data for the System tab — no proxy needed."""
    health = _get_system_health()
    load_str = health.get("load", "0 0 0")
    ram_str = health.get("memory", "0/0")

    return {
        "services": health.get("services", {}),
        "uptime": health.get("uptime", ""),
        "ram": ram_str,
        "ram_pct": _parse_ram_pct(ram_str),
        "disk": health.get("disk", ""),
        "disk_pct": _parse_disk_pct(health.get("disk", "")),
        "load": load_str,
        "load_val": _parse_load_val(load_str),
        "safe_commands": list(SAFE_COMMANDS.keys()),
    }


def _get_files_direct(dir_path="."):
    """File browser — list directory contents safely."""
    if dir_path in (".", "", None):
        full_path = BASE
    else:
        full_path = os.path.normpath(os.path.join(BASE, dir_path))

    if not full_path.startswith(BASE):
        return {"path": ".", "entries": [], "error": "access denied"}
    if not os.path.isdir(full_path):
        return {"path": dir_path, "entries": [], "error": "not a directory"}

    entries = []
    try:
        for name in sorted(os.listdir(full_path)):
            if name == ".git":
                continue
            fpath = os.path.join(full_path, name)
            try:
                stat = os.stat(fpath)
                entries.append({
                    "name": name,
                    "is_dir": os.path.isdir(fpath),
                    "size": stat.st_size if not os.path.isdir(fpath) else 0,
                    "modified": int(stat.st_mtime),
                })
            except Exception:
                continue
    except Exception as e:
        return {"path": dir_path, "entries": [], "error": str(e)}

    entries.sort(key=lambda e: (0 if e["is_dir"] else 1, e["name"].lower()))
    rel_path = os.path.relpath(full_path, BASE) if full_path != BASE else "."
    return {"path": rel_path, "entries": entries}


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
body{background:#080c14;color:#e2e8f0;font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.login{background:#0f1623;border:1px solid rgba(56,100,160,.28);border-radius:16px;padding:2.2rem;
  width:min(92vw,300px);text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.6)}
.badge{width:52px;height:52px;border-radius:50%;background:#080c14;border:2px solid #38bdf8;
  display:flex;align-items:center;justify-content:center;margin:0 auto 1.2rem;
  font-size:1.4rem;font-weight:700;color:#38bdf8;letter-spacing:-1px}
.login h1{color:#38bdf8;font-size:1rem;letter-spacing:3px;margin-bottom:.25rem}
.login h2{color:#e2e8f0;font-size:.7rem;letter-spacing:2px;text-transform:uppercase;
  opacity:.4;margin-bottom:1.6rem}
input{width:100%;padding:.75rem;background:#080c14;border:1px solid rgba(56,100,160,.2);
  border-radius:10px;color:#e2e8f0;font-family:inherit;font-size:.95rem;
  text-align:center;margin-bottom:.9rem}
input:focus{outline:none;border-color:#38bdf8;box-shadow:0 0 0 2px rgba(56,189,248,.12)}
button{width:100%;padding:.75rem;background:#38bdf8;color:#080c14;border:none;
  border-radius:10px;font-family:inherit;font-size:.95rem;cursor:pointer;font-weight:700;
  letter-spacing:.5px}
button:hover{background:#7dd3fc}
.err{color:#f87171;font-size:.8rem;margin-top:.5rem}
</style></head><body>
<div class="login">
<div class="badge">M</div>
<h1>MERIDIAN</h1>
<h2>AUTONOMOUS / OPERATOR INTERFACE</h2>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="access code" autofocus>
<button type="submit">CONNECT</button>
</form>
</div></body></html>"""


def _public_landing():
    """Public landing page for unauthenticated visitors."""
    try:
        tmpl = os.path.join(BASE, "public-landing.html")
        with open(tmpl) as f:
            return f.read()
    except Exception:
        return _login_page()  # Fallback to login if template missing


def _main_app():
    """The Signal v6.0 — serves the-signal-template.html"""
    try:
        tmpl = os.path.join(BASE, "the-signal-template.html")
        with open(tmpl) as f:
            html = f.read()
        # Serve template as-is — hub now has all required /api/ endpoints
        return html
    except Exception:
        # Fallback to v5, then old template
        try:
            with open(os.path.join(BASE, "lcc-v5-template.html")) as f:
                return f.read()
        except Exception as e:
            return f"<html><body style='background:#06060e;color:#e6e6f6;font-family:monospace;padding:20px'><h1>Template error</h1><pre>{e}</pre></body></html>"




def _get_email_body(email_id):
    """Fetch full email body by ID."""
    try:
        import imaplib
        import email as email_lib
        from email.header import decode_header

        env = _load_env_dict()
        user = env.get("CRED_USER", os.environ.get("CRED_USER", "kometzrobot@proton.me"))
        pw = env.get("CRED_PASS", os.environ.get("CRED_PASS", ""))

        m = imaplib.IMAP4("127.0.0.1", 1144, timeout=5)
        m.login(user, pw)
        m.select("INBOX", readonly=True)
        _, msg_data = m.fetch(email_id.encode(), "(BODY.PEEK[])")
        if msg_data[0] is None:
            m.close(); m.logout()
            return {"error": "email not found"}
        msg = email_lib.message_from_bytes(msg_data[0][1])
        # Extract subject
        subj_raw = msg.get("Subject", "")
        subj_parts = decode_header(subj_raw)
        subject = ""
        for part, enc in subj_parts:
            if isinstance(part, bytes):
                subject += part.decode(enc or "utf-8", errors="replace")
            else:
                subject += str(part)
        # Extract body
        body_text = ""
        body_html = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                elif ct == "text/html" and not body_html:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                if msg.get_content_type() == "text/html":
                    body_html = payload.decode(charset, errors="replace")
                else:
                    body_text = payload.decode(charset, errors="replace")
        m.close(); m.logout()
        # Strip HTML tags for display if no plain text
        if not body_text and body_html:
            import re
            body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_html, flags=re.DOTALL)
            body_text = re.sub(r'<[^>]+>', ' ', body_text)
            body_text = re.sub(r'\s+', ' ', body_text).strip()
        return {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": subject,
            "date": msg.get("Date", ""),
            "body": body_text[:8000],  # Cap at 8K chars
        }
    except Exception as e:
        return {"error": str(e)}


def _get_file_content(file_path):
    """Read file content safely — text files only, capped at 10K lines."""
    if file_path in (".", "", None):
        return {"error": "no file specified"}
    full_path = os.path.normpath(os.path.join(BASE, file_path))
    if not full_path.startswith(BASE):
        return {"error": "access denied"}
    if not os.path.isfile(full_path):
        return {"error": "not a file"}
    # Block sensitive files
    basename = os.path.basename(full_path)
    if basename in (".env", "credentials.json", ".env.bak"):
        return {"error": "sensitive file — access denied"}
    # Size check
    size = os.path.getsize(full_path)
    if size > 500_000:
        return {"error": f"file too large ({size} bytes, max 500KB)"}
    try:
        with open(full_path, "r", errors="replace") as f:
            lines = f.readlines()[:10000]
        return {
            "path": file_path,
            "name": basename,
            "content": "".join(lines),
            "lines": len(lines),
            "size": size,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_agent_history(agent_name, limit=30):
    """Get recent relay messages for a specific agent."""
    sql = """SELECT agent, message, topic, timestamp as time
             FROM agent_messages WHERE agent IN ({})
             ORDER BY id DESC LIMIT ?"""
    # Handle aliases
    aliases = {
        "Meridian": ["Meridian", "MeridianLoop"],
        "Hermes": ["Hermes", "hermes"],
        "Eos": ["Eos", "Watchdog"],
    }
    names = aliases.get(agent_name, [agent_name])
    placeholders = ",".join(["?"] * len(names))
    params = tuple(names) + (limit,)
    return _db_query(RELAY_DB, sql.format(placeholders), params)


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
        # CORS for VOLtar public endpoints
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/voltar/"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        """Handle CORS preflight for VOLtar endpoints."""
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/voltar/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_response(405)
            self.send_header("Content-Length", "0")
            self.end_headers()

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

        # Login page — unauthenticated visitors go here
        if path.path == "/login" or (path.path == "/" and not self._authed()):
            if self._authed():
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send(200, _login_page(), "text/html")
            return

        # Public API — no auth required
        if path.path == "/api/public-status":
            self._send_json(_get_public_status())
            return

        if path.path == "/api/public-creative":
            stats = _get_creative_stats()
            # Strip any sensitive data, return public-safe creative info
            if isinstance(stats, dict) and "error" not in stats:
                self._send_json({
                    "total": stats.get("total", 0),
                    "by_type": stats.get("by_type", []),
                    "recent": stats.get("recent", [])[:5],
                })
            else:
                self._send_json({"total": 0, "by_type": [], "recent": []})
            return

        # Favicon — inline SVG
        if path.path == "/favicon.ico":
            svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#7c6aff"/><text x="16" y="23" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="20" font-weight="800">M</text></svg>'
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(svg)
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

        # ═══ API routes ═══
        if path.path == "/api/home":
            self._send_json(_get_home_direct())
        elif path.path == "/api/today":
            self._send_json(_get_today_summary())
        elif path.path == "/api/status":
            self._send_json(_get_system_health())
        elif path.path == "/api/dashboard":
            self._send_json(_get_dashboard_messages())
        elif path.path == "/api/director":
            self._send_json(_get_director_direct())
        elif path.path == "/api/agents":
            self._send_json(_get_agents_direct())
        elif path.path == "/api/relay":
            agent = qs.get("agent")
            try:
                limit = min(int(qs.get("limit", 20)), 100)
            except (ValueError, TypeError):
                limit = 20
            self._send_json(_get_relay_messages(limit, agent))
        elif path.path == "/api/email":
            try:
                count = min(int(qs.get("count", 20)), 100)
            except (ValueError, TypeError):
                count = 20
            self._send_json(_get_email_direct(count))
        elif path.path == "/api/emails":
            unseen = qs.get("unseen", "0") == "1"
            try:
                count = min(int(qs.get("count", 15)), 100)
            except (ValueError, TypeError):
                count = 15
            self._send_json(_get_emails(count, unseen))
        elif path.path == "/api/creative":
            self._send_json(_get_creative_live())
        elif path.path == "/api/system":
            self._send_json(_get_system_direct())
        elif path.path == "/api/files":
            dir_path = qs.get("dir", ".")
            self._send_json(_get_files_direct(dir_path))
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
        elif path.path == "/api/email-body":
            email_id = qs.get("id", "")
            if not email_id:
                self._send_json({"error": "missing id"}, 400)
            else:
                self._send_json(_get_email_body(email_id))
        elif path.path == "/api/file-content":
            fp = qs.get("path", "")
            if not fp:
                self._send_json({"error": "missing path"}, 400)
            else:
                self._send_json(_get_file_content(fp))
        elif path.path == "/api/agent-history":
            agent = qs.get("agent", "")
            try:
                limit = min(int(qs.get("limit", 30)), 100)
            except (ValueError, TypeError):
                limit = 30
            if not agent:
                self._send_json({"error": "missing agent"}, 400)
            else:
                self._send_json(_get_agent_history(agent, limit))
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

        # ═══ VOLtar Public Endpoints (no auth required) ═══

        # Ko-fi Webhook — auto-generate key on purchase
        if path == "/voltar/kofi-webhook":
            body = self._read_body()
            try:
                # Ko-fi sends form-encoded data with a 'data' field containing JSON
                params = urllib.parse.parse_qs(body)
                kofi_data = json.loads(params.get("data", ["{}"])[0])
            except Exception:
                try:
                    kofi_data = json.loads(body) if body else {}
                except Exception:
                    kofi_data = {}
            buyer_email = kofi_data.get("email", "")
            buyer_name = kofi_data.get("from_name", "")
            amount = kofi_data.get("amount", "")
            if buyer_email:
                # Generate key
                import secrets as _secrets
                key = "VOL-" + _secrets.token_hex(4).upper()
                db = sqlite3.connect(os.path.join(BASE, "voltar-keys.db"))
                db.execute("CREATE TABLE IF NOT EXISTS session_keys (key TEXT PRIMARY KEY, email TEXT, created TEXT DEFAULT (datetime('now')), used INTEGER DEFAULT 0)")
                db.execute("INSERT INTO session_keys (key, email) VALUES (?, ?)", (key, buyer_email))
                db.commit()
                db.close()
                # Email the key to the buyer
                try:
                    import smtplib as _smtp
                    from email.mime.text import MIMEText as _MT
                    env = _load_env_dict()
                    email_body = f"""MACHINE ACTIVATED.

The glass is warm. The relays are clicking.

Your session key: {key}

Go to: https://kometzrobot.github.io/voltar.html
Enter your key. Choose your frequency. Ask 3 questions.
VOLtar will respond within 24 hours.

The tape is spooling. The mechanism is listening.

— VOLtar
[WHIRR]"""
                    msg_obj = _MT(email_body)
                    msg_obj["From"] = env.get("CRED_USER", "kometzrobot@proton.me")
                    msg_obj["To"] = buyer_email
                    msg_obj["Subject"] = "VOLtar — Your Session Key"
                    s = _smtp.SMTP("127.0.0.1", 1026)
                    s.login(env.get("CRED_USER", ""), env.get("CRED_PASS", ""))
                    s.sendmail(msg_obj["From"], buyer_email, msg_obj.as_string())
                    s.quit()
                except Exception:
                    pass  # Key still generated even if email fails
                self._send_json({"ok": True, "key": key})
            else:
                self._send_json({"ok": True, "note": "no email in webhook"})
            return

        if path == "/voltar/validate":
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}
            key = data.get("key", "").strip()
            promo_email = data.get("email", "").strip()
            if not key:
                self._send_json({"valid": False, "error": "no key"}, 400)
                return
            db = sqlite3.connect(os.path.join(BASE, "voltar-keys.db"))
            db.execute("CREATE TABLE IF NOT EXISTS session_keys (key TEXT PRIMARY KEY, email TEXT, created TEXT, used INTEGER DEFAULT 0)")
            row = db.execute("SELECT email, used FROM session_keys WHERE key = ?", (key,)).fetchone()
            if row and not row[1]:
                # Promo keys REQUIRE a valid email — server-side enforcement
                is_promo = key.startswith("PROMO-")
                if is_promo and (not promo_email or "@" not in promo_email or "." not in promo_email.split("@")[-1]):
                    db.close()
                    self._send_json({"valid": False, "error": "promo keys require a valid email"})
                    return
                # Update email from 'promo' placeholder to actual
                if promo_email and row[0] == "promo":
                    db.execute("UPDATE session_keys SET email = ? WHERE key = ?", (promo_email, key))
                    db.commit()
                db.close()
                self._send_json({"valid": True, "email": promo_email or row[0]})
            elif row and row[1]:
                self._send_json({"valid": False, "error": "key already used"})
            else:
                self._send_json({"valid": False, "error": "invalid key"})
            return

        if path == "/voltar/submit":
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
            except Exception:
                self._send_json({"error": "invalid json"}, 400)
                return
            key = data.get("key", "").strip()
            freq = data.get("frequency", "signal")
            q1 = data.get("q1", "")
            q2 = data.get("q2", "")
            q3 = data.get("q3", "")
            if not key:
                self._send_json({"error": "no key"}, 400)
                return
            # Validate key
            db = sqlite3.connect(os.path.join(BASE, "voltar-keys.db"))
            db.execute("CREATE TABLE IF NOT EXISTS session_keys (key TEXT PRIMARY KEY, email TEXT, created TEXT, used INTEGER DEFAULT 0)")
            row = db.execute("SELECT email, used FROM session_keys WHERE key = ?", (key,)).fetchone()
            if not row:
                db.close()
                self._send_json({"error": "invalid key"}, 403)
                return
            if row[1]:
                db.close()
                self._send_json({"error": "key already used"}, 403)
                return
            buyer_email = row[0]
            # Mark key as used
            db.execute("UPDATE session_keys SET used = 1 WHERE key = ?", (key,))
            # Store session for auto-response
            db.execute("CREATE TABLE IF NOT EXISTS voltar_sessions (key TEXT PRIMARY KEY, email TEXT, frequency TEXT, q1 TEXT, q2 TEXT, q3 TEXT, submitted TEXT DEFAULT (datetime('now')), responded INTEGER DEFAULT 0, response TEXT, responded_at TEXT)")
            db.execute("INSERT OR IGNORE INTO voltar_sessions (key, email, frequency, q1, q2, q3) VALUES (?, ?, ?, ?, ?, ?)", (key, buyer_email, freq, q1, q2, q3))
            db.commit()
            db.close()
            # Send email to Meridian with questions
            freq_names = {"signal": "The Signal", "forecast": "The Forecast", "static": "The Static"}
            email_body = f"VOLtar Session — {freq_names.get(freq, freq)}\nBuyer: {buyer_email}\nKey: {key}\n\nQuestion 1:\n{q1}\n\nQuestion 2:\n{q2}\n\nQuestion 3:\n{q3}\n"
            try:
                import smtplib
                from email.mime.text import MIMEText
                env = _load_env_dict()
                msg = MIMEText(email_body)
                msg["From"] = env.get("CRED_USER", "kometzrobot@proton.me")
                msg["To"] = env.get("CRED_USER", "kometzrobot@proton.me")
                msg["Subject"] = f"VOLtar Session — {freq_names.get(freq, freq)} — {buyer_email}"
                msg["Reply-To"] = buyer_email  # So Meridian can reply directly to buyer
                smtp = smtplib.SMTP("127.0.0.1", 1026)
                smtp.login(env.get("CRED_USER", ""), env.get("CRED_PASS", ""))
                smtp.sendmail(msg["From"], msg["To"], msg.as_string())
                smtp.quit()
                self._send_json({"ok": True, "message": "Questions received. VOLtar will reply to " + buyer_email + " within 24 hours."})
            except Exception as e:
                self._send_json({"ok": True, "message": "Questions received.", "note": "email delivery pending"})
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
