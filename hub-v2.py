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

    # Soma mood + inner world
    soma = _read_json(SOMA_STATE, {})
    inner_mono = _read_json(os.path.join(BASE, ".soma-inner-monologue.json"), {})
    goals_data = _read_json(os.path.join(BASE, ".soma-goals.json"), {})
    psyche_data = _read_json(os.path.join(BASE, ".soma-psyche.json"), {})

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
        "soma_inner": inner_mono.get("current", {}).get("text", ""),
        "soma_goals": [g["id"] for g in goals_data.get("goals", [])],
        "soma_fears": psyche_data.get("fears", []),
        "soma_dreams": psyche_data.get("dreams", []),
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
    """Work-centric summary: what was done today, not whether services are running."""
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


def _main_app():
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Meridian Nuevo</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#080c14">
<meta name="apple-mobile-web-app-capable" content="yes">
<style>
/* ════ MERIDIAN HUB — CLOUDFLARE DARK THEME ════ */
:root{
  --bg:#080c14;--surface:#0f1623;--card:#151e2e;
  --border:rgba(56,100,160,.15);--border-hi:rgba(56,100,160,.28);
  --text:#e2e8f0;--dim:#64748b;
  --accent:#38bdf8;--green:#34d399;--amber:#fbbf24;--red:#f87171;
  --purple:#a78bfa;--magenta:#f472b6;--cyan:#67e8f9;--gold:#fde68a;
}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes ripple{0%{box-shadow:0 0 0 0 rgba(100,181,246,.35)}100%{box-shadow:0 0 0 8px rgba(100,181,246,0)}}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;
  font-size:14px;line-height:1.5;overflow-x:hidden;padding-top:60px;padding-bottom:68px}

/* ── APP BAR (Material-style) ── */
header{position:fixed;top:0;left:0;right:0;height:60px;
  background:var(--surface);
  display:flex;align-items:center;
  justify-content:space-between;padding:0 18px;z-index:100;
  border-bottom:1px solid var(--border-hi);
  box-shadow:0 2px 20px rgba(0,0,0,.7)}
.hdr-left{display:flex;align-items:center;gap:12px}
.hdr-badge{width:36px;height:36px;border-radius:50%;background:var(--accent);
  display:flex;align-items:center;justify-content:center;
  font-size:.95rem;font-weight:700;color:var(--bg);
  animation:ripple 3s ease-out infinite}
.hdr-title{display:flex;flex-direction:column;line-height:1.2}
.hdr-title .name{font-size:.95rem;font-weight:600;color:var(--text);letter-spacing:.5px}
.hdr-title .sub{font-size:.65rem;color:var(--dim);letter-spacing:1px;text-transform:uppercase}
.hdr-right{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--dim)}
#hb-dot{width:8px;height:8px;border-radius:50%;display:inline-block;
  animation:pulse 2.5s ease-in-out infinite}
.hdr-logout{color:var(--dim);font-size:11px;text-decoration:none;
  padding:5px 10px;border-radius:20px;background:rgba(255,255,255,.07);transition:background .15s}
.hdr-logout:hover{background:rgba(255,255,255,.14);color:var(--text)}
#hdr-mono{font-size:11px;color:var(--dim);font-style:italic;max-width:200px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:none}
@media(min-width:500px){#hdr-mono{display:block}}

/* ── BOTTOM NAV (Material style) ── */
nav{position:fixed;bottom:0;left:0;right:0;height:68px;
  background:var(--surface);
  display:flex;z-index:100;overflow-x:auto;
  padding:0 2px env(safe-area-inset-bottom,0);scrollbar-width:none;
  border-top:1px solid var(--border-hi);
  box-shadow:0 -4px 20px rgba(0,0,0,.6)}
nav::-webkit-scrollbar{display:none}
nav button{flex:0 0 auto;min-width:56px;background:none;border:none;
  color:var(--dim);font-family:inherit;font-size:10px;font-weight:500;
  padding:8px 4px 6px;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:3px;
  transition:color .2s;border-radius:0;position:relative}
nav button::after{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);
  width:0;height:3px;border-radius:0 0 3px 3px;background:var(--accent);
  transition:width .2s}
nav button.active{color:var(--accent)}
nav button.active::after{width:32px}
nav button:hover{color:var(--text)}
nav .ico{font-size:16px;line-height:1}

/* ── PAGES ── */
.page{display:none;padding:14px 16px;max-width:820px;margin:0 auto}
.page.active{display:block;animation:fadeIn .2s ease}

/* ── CARDS (Material elevation) ── */
.card{background:var(--card);border-radius:12px;
  border:1px solid var(--border);
  box-shadow:0 4px 16px rgba(0,0,0,.5);
  padding:16px;margin-bottom:12px}
.card h3{font-size:11px;font-weight:600;color:var(--dim);text-transform:uppercase;
  letter-spacing:1.2px;margin-bottom:12px}
.card .row{display:flex;justify-content:space-between;align-items:center;
  padding:6px 0;border-bottom:1px solid var(--border)}
.card .row:last-child{border-bottom:none}
.card .label{color:var(--dim);font-size:13px}
.card .value{color:var(--text);text-align:right;font-size:13px;font-weight:500}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stat-cell{background:var(--surface);border-radius:12px;padding:12px 14px;
  border:1px solid var(--border);
  box-shadow:0 2px 8px rgba(0,0,0,.4)}
.stat-cell .stat-label{font-size:10px;font-weight:600;color:var(--dim);
  text-transform:uppercase;letter-spacing:1px}
.stat-cell .stat-val{font-size:1.2rem;font-weight:700;color:var(--accent);margin-top:4px}

/* ── SERVICES (pill row) ── */
.svc-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.pill{font-size:11px;padding:4px 10px;border-radius:20px;font-weight:600}
.pill-up{color:var(--green);background:rgba(105,240,174,.12)}
.pill-down{color:var(--red);background:rgba(255,110,110,.12)}

/* ── AGENT GRID ── */
.status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
@media(min-width:400px){.status-grid{grid-template-columns:repeat(4,1fr)}}
.agent-card{background:var(--surface);border-radius:10px;
  border:1px solid var(--border);
  box-shadow:0 2px 8px rgba(0,0,0,.4);
  padding:10px 8px;text-align:center;font-size:11px;cursor:default}
.agent-card .name{font-weight:600;margin-bottom:4px;font-size:11px}
.agent-card .age{color:var(--dim);font-size:10px}
.agent-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.dot-active{background:var(--green);box-shadow:0 0 5px var(--green)}
.dot-stale{background:var(--amber)}
.dot-unknown{background:rgba(255,255,255,.2)}

/* ── SOMA SCORE BAR ── */
.soma-bar-wrap{height:4px;background:rgba(255,255,255,.1);border-radius:2px;overflow:hidden;margin-top:6px}
.soma-bar-fill{height:100%;border-radius:2px;background:var(--accent);transition:width .6s}

/* ── MESSAGES ── */
.msg{padding:10px 0;border-bottom:1px solid var(--border)}
.msg:last-child{border-bottom:none}
.msg .from{font-weight:600;font-size:12px}
.msg .time{color:var(--dim);font-size:11px;float:right}
.msg .body{margin-top:4px;color:var(--text);word-break:break-word;font-size:13px;line-height:1.5}
.msg-joel{border-left:3px solid var(--amber);padding-left:10px}
.msg-joel .from{color:var(--amber)}
.msg-meridian .from{color:var(--accent)}
.msg-soma .from{color:var(--purple)}
.msg-atlas .from{color:var(--cyan)}
.msg-nova .from{color:var(--green)}
.msg-cinder .from{color:var(--magenta)}
.msg-hermes .from{color:var(--magenta)}

/* ── TERMINAL ── */
#term-output{background:#0A0A0A;border-radius:12px;
  padding:12px;font-size:12px;font-family:'SF Mono',Menlo,Consolas,monospace;
  white-space:pre-wrap;word-break:break-all;
  max-height:60vh;overflow-y:auto;margin-top:10px;color:var(--green);
  box-shadow:inset 0 2px 8px rgba(0,0,0,.5)}
.cmd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.cmd-btn{background:var(--surface);border:none;border-radius:10px;
  color:var(--text);padding:10px 8px;font-family:inherit;font-size:12px;cursor:pointer;
  text-align:center;transition:background .15s;
  box-shadow:0 1px 4px rgba(0,0,0,.3)}
.cmd-btn:hover{background:rgba(100,181,246,.15);color:var(--accent)}
.cmd-btn:active{background:rgba(100,181,246,.25)}

/* ── LOGS ── */
.log-select{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.log-btn{background:var(--surface);border:none;border-radius:20px;
  color:var(--dim);padding:6px 12px;font-family:inherit;font-size:11px;font-weight:500;cursor:pointer;
  transition:all .15s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.log-btn.active{background:rgba(100,181,246,.18);color:var(--accent)}
#log-output{background:#0A0A0A;border-radius:12px;
  padding:12px;font-size:11.5px;font-family:'SF Mono',Menlo,Consolas,monospace;
  white-space:pre-wrap;word-break:break-all;
  max-height:65vh;overflow-y:auto;color:rgba(255,255,255,.75)}

/* ── INPUT ── */
.input-row{display:flex;gap:8px;margin-top:10px}
.input-row input,.input-row textarea{flex:1;background:var(--surface);
  border:1px solid var(--border);border-radius:12px;
  color:var(--text);font-family:inherit;font-size:13px;padding:10px 14px;
  transition:border-color .15s}
.input-row input:focus,.input-row textarea:focus{outline:none;border-color:var(--accent)}
.input-row button{background:var(--accent);color:var(--bg);border:none;border-radius:12px;
  padding:10px 18px;font-family:inherit;font-size:13px;cursor:pointer;font-weight:700;
  transition:opacity .15s}
.input-row button:hover{opacity:.88}

/* ── QUICK ACTIONS ── */
.action-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.action-btn{background:var(--surface);border:none;border-radius:12px;
  color:var(--text);padding:12px 6px;font-family:inherit;font-size:12px;font-weight:500;cursor:pointer;
  text-align:center;transition:background .15s;box-shadow:0 1px 4px rgba(0,0,0,.3)}
.action-btn:hover{background:rgba(105,240,174,.12);color:var(--green)}

/* ── RELAY FILTERS ── */
#relay-toolbar{display:flex;flex-wrap:wrap;gap:6px;padding:12px 0 8px;position:sticky;top:60px;z-index:10;background:var(--bg)}
.relay-filter{background:var(--surface);border:none;border-radius:20px;color:var(--dim);
  padding:5px 12px;font-family:inherit;font-size:11px;font-weight:500;cursor:pointer;transition:all .15s;
  box-shadow:0 1px 3px rgba(0,0,0,.3)}
.relay-filter.active{background:var(--accent);color:var(--bg);font-weight:700}
.relay-filter:hover:not(.active){background:rgba(255,255,255,.1);color:var(--text)}
.topic-badge{font-size:9px;padding:2px 6px;border-radius:10px;border:1px solid;opacity:.8;vertical-align:middle;margin-right:5px}

/* ── CINDER ── */
.cinder-modes{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.cinder-mode-btn{background:var(--surface);border:none;border-radius:20px;
  color:var(--dim);padding:6px 14px;font-family:inherit;font-size:11px;font-weight:500;cursor:pointer;
  transition:all .15s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.cinder-mode-btn.active{background:rgba(244,143,177,.15);color:var(--magenta);font-weight:600}
#cinder-chat{background:var(--surface);border-radius:16px;
  padding:12px;min-height:200px;max-height:55vh;overflow-y:auto;margin-bottom:10px;
  display:flex;flex-direction:column;gap:10px}
.c-bubble{max-width:88%;padding:10px 14px;border-radius:16px;font-size:13px;word-break:break-word}
.c-user{align-self:flex-end;background:rgba(100,181,246,.15);color:var(--text)}
.c-cinder{align-self:flex-start;background:rgba(244,143,177,.1);color:var(--text)}
.c-label{font-size:10px;color:var(--dim);margin-bottom:3px;font-weight:500}
#cinder-mem-results{background:var(--surface);border-radius:12px;
  padding:10px;font-size:12px;max-height:200px;overflow-y:auto;margin-top:8px;
  white-space:pre-wrap;color:var(--text)}

/* ── RESPONSIVE ── */
@media(min-width:600px){
  body{font-size:15px}
  nav button{font-size:11px;min-width:62px}
  .page{padding:18px 24px}
  .stat-grid{grid-template-columns:repeat(3,1fr)}
}
</style>
</head><body>

<!-- ── HEADER ── -->
<header>
  <div class="hdr-left">
    <div class="hdr-badge">M</div>
    <div class="hdr-title">
      <div class="name">MERIDIAN</div>
      <div class="sub">AUTONOMOUS</div>
    </div>
  </div>
  <span id="hdr-mono"></span>
  <span class="hdr-right"><span id="hb-dot"></span>&thinsp;Loop <span id="loop-num">?</span>&thinsp;·&thinsp;<span id="hb-age">?</span>
    <a href="#" class="hdr-logout" onclick="fetch('/logout',{method:'POST'}).then(()=>location='/login')">out</a></span>
</header>

<!-- ════════ PAGES ════════ -->

<div id="page-dash" class="page active">
  <!-- Status strip: loop + mood + heartbeat -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px">
    <div class="stat-cell" style="text-align:center">
      <div class="stat-label">LOOP</div>
      <div id="hero-loop" class="stat-val" style="font-size:1.8rem;line-height:1">—</div>
    </div>
    <div class="stat-cell" style="text-align:center">
      <div class="stat-label">MOOD</div>
      <div id="hero-mood" class="stat-val" style="font-size:.85rem;text-transform:uppercase;letter-spacing:1px;margin-top:4px">—</div>
    </div>
    <div class="stat-cell" style="text-align:center">
      <div class="stat-label">HEARTBEAT</div>
      <div id="hero-hb" class="stat-val" style="font-size:.85rem;margin-top:4px">—</div>
    </div>
  </div>

  <!-- TODAY: What was actually done -->
  <div class="card">
    <h3>Today&rsquo;s Work</h3>
    <div id="today-commits"></div>
  </div>

  <!-- Joel's messages (pending items) -->
  <div class="card" id="joel-msgs-card" style="display:none">
    <h3>From Joel</h3>
    <div id="today-joel"></div>
  </div>

  <!-- Metrics: infographic cards with live charts -->
  <div class="card" id="metrics-card">
    <h3>Metrics</h3>
    <div id="metrics-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px"></div>
    <div id="fitness-radar-wrap" style="margin-top:10px"></div>
  </div>

  <!-- Agent exchanges (meaningful only) -->
  <div class="card">
    <h3>Agent Exchanges</h3>
    <div id="today-exchanges"></div>
  </div>

  <!-- Quick Actions -->
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

  <!-- System (collapsed by default) -->
  <details style="margin-bottom:12px">
    <summary style="cursor:pointer;padding:8px;color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:1px;user-select:none">
      &#x25B6; System &amp; Services
    </summary>
    <div class="card" style="margin-top:6px" id="health-card">
      <div id="health-rows"></div>
    </div>
    <div class="card">
      <h3>Agents (last seen)</h3>
      <div class="status-grid" id="agent-grid"></div>
    </div>
    <div class="card">
      <h3>Soma Inner World</h3>
      <div id="soma-info"></div>
    </div>
  </details>
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
  <div id="relay-toolbar">
    <button class="relay-filter active" onclick="setRelayFilter(this,'')">ALL</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'status')">STATUS</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'fitness')">FITNESS</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'mood_shift')">MOOD</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'briefing')">BRIEF</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'alert')">ALERT</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'loop')">LOOP</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'infra-audit')">INFRA</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'nerve-event')">NERVE</button>
    <button class="relay-filter" onclick="setRelayFilter(this,'cascade')">CASCADE</button>
  </div>
  <div class="card" style="margin-top:8px">
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
  // Fetch both today summary (new) and full status (for collapsed section)
  const [d, s] = await Promise.all([api('today'), api('status')]);

  // ── Header strip ──
  document.getElementById('loop-num').textContent = d.loop || s.loop || '—';
  const hbAge = d.heartbeat_age ?? s.heartbeat_age ?? 999;
  const hbStatus = d.heartbeat_status || 'unknown';
  document.getElementById('hb-age').textContent = hbAge + 's';
  const dot = document.getElementById('hb-dot');
  dot.style.background = hbAge < 120 ? 'var(--green)' : hbAge < 300 ? 'var(--amber)' : 'var(--red)';
  document.getElementById('hero-loop').textContent = d.loop || '—';
  const moodText = (d.soma_mood || s.soma_mood || '—').replace(/_/g,' ');
  document.getElementById('hero-mood').textContent = moodText;
  const hbColor = hbStatus === 'alive' ? 'var(--green)' : hbStatus === 'slow' ? 'var(--amber)' : 'var(--red)';
  document.getElementById('hero-hb').textContent = hbAge + 's';
  document.getElementById('hero-hb').style.color = hbColor;

  // ── Today's Work: commits ──
  const commits = d.commits || [];
  let commitHtml = '';
  if (commits.length === 0) {
    commitHtml = '<div style="color:var(--dim);font-size:12px">No commits in the last 24h.</div>';
  } else {
    commitHtml = commits.map(c => {
      const hash = c.slice(0, 7);
      const msg = c.slice(8);
      return `<div class="row" style="align-items:flex-start">
        <span class="label" style="font-family:monospace;color:var(--accent);font-size:11px;min-width:54px">${esc(hash)}</span>
        <span class="value" style="font-size:12px;white-space:normal">${esc(msg)}</span>
      </div>`;
    }).join('');
    commitHtml = `<div style="color:var(--dim);font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">${commits.length} commit${commits.length>1?'s':''} today</div>` + commitHtml;
  }
  document.getElementById('today-commits').innerHTML = commitHtml;

  // ── Joel's messages ──
  const joelMsgs = d.joel_messages || [];
  if (joelMsgs.length > 0) {
    document.getElementById('joel-msgs-card').style.display = '';
    document.getElementById('today-joel').innerHTML = joelMsgs.slice(-5).reverse().map(m =>
      `<div class="msg msg-joel" style="margin-bottom:6px">
        <span class="time">${esc(m.time||'')}</span>
        <div class="body" style="margin-top:2px">${esc(m.text||'')}</div>
      </div>`
    ).join('');
  } else {
    document.getElementById('joel-msgs-card').style.display = 'none';
  }

  // ── Agent exchanges ──
  const exchanges = d.exchanges || [];
  if (exchanges.length === 0) {
    document.getElementById('today-exchanges').innerHTML =
      '<div style="color:var(--dim);font-size:12px">No significant agent exchanges in the last 24h.</div>';
  } else {
    document.getElementById('today-exchanges').innerHTML = exchanges.slice(0,8).map(ex => {
      const topicColor = {
        'inter-agent':'var(--accent)', 'relay':'var(--cyan)', 'briefing':'var(--purple)',
        'alert':'var(--red)'
      }[ex.topic] || 'var(--dim)';
      return `<div class="row" style="align-items:flex-start;margin-bottom:4px">
        <span class="label" style="color:${topicColor};min-width:70px;font-size:11px">${esc(ex.agent)}</span>
        <span class="value" style="font-size:11px;white-space:normal;color:var(--text)">${esc(ex.msg)}</span>
      </div>`;
    }).join('');
  }

  // ── Metrics: infographic cards with charts ──
  const metricsEl = document.getElementById('metrics-grid');
  if (metricsEl) {
    const moodScore = parseFloat(d.soma_score || s.soma_score || 50);
    const moodColor = moodScore > 60 ? '#4ade80' : moodScore > 35 ? '#fbbf24' : '#f87171';
    const moodLabel = (d.soma_mood || '—').replace(/_/g, ' ').toUpperCase();

    const cards = [
      {
        label: 'AGENT ACTIVITY',
        value: (d.activity_total || 0) + ' msgs',
        sub: 'peak ' + (d.activity_peak || 0) + '/hr · last 24h',
        chart: d.activity_chart || '',
        accent: '#7b5cf5'
      },
      {
        label: 'MOOD',
        value: moodLabel,
        sub: 'score ' + moodScore.toFixed(0) + '/100',
        chart: d.mood_chart || '',
        accent: moodColor
      },
      {
        label: 'MEMORY INDEX',
        value: (d.memory_total || 0) + ' vectors',
        sub: '+' + (d.memory_today || 0) + ' today',
        chart: d.memory_chart || '',
        accent: '#22d3ee'
      },
      {
        label: "TODAY'S COMMITS",
        value: (d.commit_count || 0) + ' commits',
        sub: (d.commits && d.commits[0]) ? d.commits[0].slice(8, 40) : 'none today',
        chart: '',
        accent: '#fbbf24'
      }
    ];

    metricsEl.innerHTML = cards.map(c => `
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:10px;overflow:hidden">
        <div style="font-size:9px;font-weight:700;color:${c.accent};text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px">${c.label}</div>
        <div style="font-size:1.1rem;font-weight:700;color:var(--text);line-height:1.1">${c.value}</div>
        <div style="font-size:10px;color:var(--dim);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${c.sub}</div>
        ${c.chart ? `<div style="margin-top:4px">${c.chart}</div>` : ''}
      </div>`).join('');

    // Fitness radar chart (full-width below)
    const radarWrap = document.getElementById('fitness-radar-wrap');
    if (radarWrap && d.fitness_radar) {
      const fscore = d.fitness_score || 0;
      radarWrap.innerHTML = `
        <div style="border-top:1px solid var(--border);padding-top:10px;margin-top:4px">
          <div style="font-size:9px;font-weight:700;color:#fbbf24;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px">
            LOOP FITNESS &nbsp;<span style="color:var(--dim);font-weight:400">score ${esc(String(fscore))}</span>
          </div>
          <div style="max-width:260px;margin:0 auto">${d.fitness_radar}</div>
        </div>`;
    }
  }

  // ── Collapsed: System health + agents + soma ──
  if (s && !s.error) {
    const rows = [
      ['Load', s.load], ['Memory', s.memory], ['Disk', s.disk], ['Uptime', s.uptime],
    ];
    let healthHtml = rows.map(r =>
      `<div class="row"><span class="label">${esc(r[0])}</span><span class="value">${esc(String(r[1]||'?'))}</span></div>`
    ).join('');
    // Services
    const svcRows = Object.entries(s.services || {}).map(([name, status]) => {
      const color = status === 'active' ? 'var(--green)' : 'var(--red)';
      return `<div class="row"><span class="label">${esc(name)}</span><span class="value" style="color:${color}">${esc(status)}</span></div>`;
    }).join('');
    healthHtml += '<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px;color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:1px">Services</div>' + svcRows;
    document.getElementById('health-rows').innerHTML = healthHtml;

    // Agents
    const agentHtml = Object.entries(s.agents || {}).map(([name, info]) => {
      const cls = info.status === 'active' ? 'dot-active' : info.status === 'stale' ? 'dot-stale' : 'dot-unknown';
      const age = info.last_seen > 0 ? Math.round(info.last_seen)+'s' : '?';
      return `<div class="agent-card"><span class="agent-dot ${cls}"></span>
        <div class="name">${esc(name)}</div><div class="age">${esc(age)}</div></div>`;
    }).join('');
    document.getElementById('agent-grid').innerHTML = agentHtml;

    // Soma
    const mono = s.soma_inner || '';
    const scoreNum = parseFloat(s.soma_score) || 0;
    const barColor = scoreNum > 60 ? 'var(--green)' : scoreNum > 35 ? 'var(--accent)' : 'var(--red)';
    const goals = (s.soma_goals||[]).join(' / ') || '—';
    document.getElementById('soma-info').innerHTML =
      `<div class="row"><span class="label">Mood</span><span class="value">${esc(s.soma_mood||'')}</span></div>
       <div class="soma-bar-wrap"><div class="soma-bar-fill" style="width:${Math.min(scoreNum,100)}%;background:${barColor}"></div></div>
       ${mono ? `<div style="margin-top:8px;padding:7px 9px;background:var(--bg);border-radius:6px;border:1px solid var(--border);font-size:11px;color:var(--dim);font-style:italic">&ldquo;${esc(mono)}&rdquo;</div>` : ''}
       <div class="row" style="margin-top:6px"><span class="label">Goals</span><span class="value" style="color:var(--accent);font-size:11px">${esc(goals)}</span></div>`;
    const monoEl = document.getElementById('hdr-mono');
    if (monoEl && mono) monoEl.textContent = '\u201c' + mono + '\u201d';
  }
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

let relayFilter = '';
const RELAY_NOISE = new Set(['nerve-event', 'inter-agent']);
const TOPIC_COLORS = {
  'status':'var(--green)','fitness':'var(--cyan)','mood_shift':'var(--purple)',
  'briefing':'var(--magenta)','alert':'var(--red)','loop':'var(--accent)',
  'infra-audit':'var(--amber)','cascade':'var(--dim)','nerve-event':'var(--dim)',
  'inter-agent':'var(--dim)'
};

async function refreshRelay() {
  const msgs = await api('relay?limit=60');
  if (!Array.isArray(msgs)) return;
  let filtered = msgs;
  if (relayFilter) {
    filtered = msgs.filter(m => (m.topic||'') === relayFilter);
  } else {
    // Default: hide noise topics, deduplicate consecutive same-agent same-topic
    filtered = msgs.filter(m => !RELAY_NOISE.has(m.topic||''));
    const seen = {};
    filtered = filtered.filter(m => {
      const key = (m.source_agent||'') + ':' + (m.topic||'');
      const txt = (m.content||'').slice(0, 120);
      if (seen[key] === txt) return false;
      seen[key] = txt;
      return true;
    });
  }
  const TOPIC_COLORS_LOCAL = TOPIC_COLORS;
  document.getElementById('relay-msgs').innerHTML = filtered.length ? filtered.map(m => {
    const agentLower = (m.source_agent||'').toLowerCase();
    const topic = m.topic || '';
    const tcolor = TOPIC_COLORS_LOCAL[topic] || 'var(--border-hi)';
    const cls = 'msg msg-' + agentLower;
    return `<div class="${cls}">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:3px">
        <span class="from">${esc(m.source_agent||'?')}</span>
        <span class="topic-badge" style="color:${tcolor};border-color:${tcolor}">${esc(topic)}</span>
        <span style="color:var(--dim);font-size:10px;margin-left:auto">${fmtRelayTime(m.created_at)}</span>
      </div>
      <div class="body">${esc((m.content||'').slice(0,400))}</div>
    </div>`;
  }).join('') : '<div style="color:var(--dim);padding:12px 0">No messages for this filter.</div>';
}

function setRelayFilter(btn, topic) {
  relayFilter = topic;
  document.querySelectorAll('.relay-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  refreshRelay();
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
// Parse UTC relay timestamp and format in local time
function fmtRelayTime(utcStr, showSec) {
  try {
    const s = (utcStr||'').replace(' ','T') + 'Z';
    const d = new Date(s);
    if (isNaN(d)) return (utcStr||'').slice(11, showSec ? 19 : 16);
    const h = String(d.getHours()).padStart(2,'0');
    const m = String(d.getMinutes()).padStart(2,'0');
    if (showSec) return h+':'+m+':'+String(d.getSeconds()).padStart(2,'0');
    return h+':'+m;
  } catch(e) { return (utcStr||'').slice(11, showSec ? 19 : 16); }
}

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
      const t = fmtRelayTime(m.created_at, true);
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
        if path.path == "/api/today":
            self._send_json(_get_today_summary())
        elif path.path == "/api/status":
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
