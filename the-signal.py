#!/usr/bin/env python3
"""
THE SIGNAL — Meridian Command Center
Full operator hub for Joel's RAZR 2025 phone.
PWA-installable, works over WiFi or Tailscale.
Port 8090.
"""

import http.server
import json
import os
import re
import time
import sqlite3
import subprocess
import glob
import shlex
import secrets
import hashlib
import http.cookies
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

PORT = 8090
BASE = "/home/joel/autonomous-ai"
AUTH_PASSWORD = "590148001"
VALID_SESSIONS = set()  # in-memory session tokens
LOGIN_ATTEMPTS = {}  # IP -> (count, first_attempt_time) for rate limiting
MAX_LOGIN_ATTEMPTS = 5  # per 10 minutes
HB = os.path.join(BASE, ".heartbeat")
DASH_MSG = os.path.join(BASE, ".dashboard-messages.json")
LOOP_FILE = os.path.join(BASE, ".loop-count")
RELAY_DB = os.path.join(BASE, "agent-relay.db")

# Whitelisted commands for the terminal
COMMAND_WHITELIST = {
    "uptime": "uptime",
    "free": "free -h",
    "df": "df -h /",
    "top": "top -bn1 | head -20",
    "ps": "ps aux --sort=-%cpu | head -15",
    "load": "cat /proc/loadavg",
    "who": "who",
    "git-status": "git -C /home/joel/autonomous-ai status",
    "git-log": "git -C /home/joel/autonomous-ai log --oneline -15",
    "git-diff": "git -C /home/joel/autonomous-ai diff --stat",
    "loop": "cat /home/joel/autonomous-ai/.loop-count",
    "heartbeat": "stat -c '%Y' /home/joel/autonomous-ai/.heartbeat 2>/dev/null && echo 'age:' && echo $(( $(date +%s) - $(stat -c '%Y' /home/joel/autonomous-ai/.heartbeat) ))s",
    "crontab": "crontab -l",
    "services": "export XDG_RUNTIME_DIR=/run/user/$(id -u) && export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus && systemctl --user list-units --type=service --state=running 2>/dev/null || echo 'systemd user not available'",
    "tailscale": "tailscale status 2>/dev/null || echo 'tailscale not available'",
    "skill-tracker": "python3 /home/joel/autonomous-ai/skill-tracker.py --skills",
    "relay-report": "python3 /home/joel/autonomous-ai/relay-analyzer.py --recent",
    "fitness": "python3 /home/joel/autonomous-ai/loop-fitness.py",
    "fitness-history": "python3 /home/joel/autonomous-ai/loop-fitness.py history",
    "fitness-trend": "python3 /home/joel/autonomous-ai/loop-fitness.py trend",
    "tunnel-url": "cat /home/joel/autonomous-ai/signal-config.json 2>/dev/null || echo 'no config'",
    "email-stats": "python3 /home/joel/autonomous-ai/email-stats-cmd.py",
    "cron-health": "for f in eos-watchdog.log push-live-status.log nova.log eos-react.log goose.log symbiosense.log loop-fitness.log; do age=$(($(date +%s) - $(stat -c%Y /home/joel/autonomous-ai/$f 2>/dev/null || echo 0))); echo \"$f: ${age}s ago\"; done",
    "ports": "ss -tlnp 2>/dev/null | grep -E ':(8090|1143|1025|11434|8080)' || echo 'no matching ports'",
    "memory-stats": "python3 -c \"import sqlite3,json; db=sqlite3.connect('/home/joel/autonomous-ai/memory.db'); tables=['facts','observations','events','decisions','loop_fitness']; [print(f'{t}: {db.execute(f\\\"SELECT COUNT(*) FROM {t}\\\").fetchone()[0]}') for t in tables if db.execute(f\\\"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'\\\").fetchone()]\"",
}

# Allowed log files
ALLOWED_LOGS = [
    "eos-watchdog.log", "eos-creative.log", "eos-react.log",
    "eos-briefing.log", "nova.log", "push-live-status.log",
    "watchdog.log", "startup.log", "loop-optimizer.log",
    "morning-summary.log", "daily-log.log", "symbiosense.log",
    "goose.log",
    "loop-fitness.log",
]

# Allowed services for restart
ALLOWED_SERVICES = [
    "meridian-web-dashboard", "meridian-hub-v16",
    "cloudflare-tunnel", "symbiosense",
]


def get_system_health():
    try:
        load = open("/proc/loadavg").read().split()[:3]
        load_str = " ".join(load)
    except:
        load_str = "?"
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 0) / 1024 / 1024
        avail = mem.get("MemAvailable", 0) / 1024 / 1024
        used = total - avail
        ram_str = f"{used:.1f}G / {total:.1f}G"
        ram_pct = int((used / total) * 100) if total > 0 else 0
    except:
        ram_str = "?"
        ram_pct = 0
    try:
        df = subprocess.check_output(["df", "/", "--output=size,used,pcent"], text=True).strip().split("\n")[1].split()
        disk_str = f"{int(df[1])//1024//1024}G used, {df[2]} full"
        disk_pct = int(df[2].replace("%", ""))
    except:
        disk_str = "?"
        disk_pct = 0
    try:
        uptime_s = float(open("/proc/uptime").read().split()[0])
        h, m = int(uptime_s // 3600), int((uptime_s % 3600) // 60)
        uptime_str = f"{h}h {m}m"
    except:
        uptime_str = "?"
    services = {}
    for name, pattern in [("Proton Bridge", "protonmail-bridge"),
                          ("Tailscale", "tailscaled"),
                          ("Ollama", "ollama"),
                          ("Command Center", "command-center")]:
        try:
            result = subprocess.run(["pgrep", "-f", pattern], capture_output=True)
            services[name] = "up" if result.returncode == 0 else "down"
        except:
            services[name] = "?"
    return {
        "load": load_str, "ram": ram_str, "ram_pct": ram_pct,
        "disk": disk_str, "disk_pct": disk_pct,
        "uptime": uptime_str, "services": services
    }


def get_heartbeat():
    try:
        age = time.time() - os.path.getmtime(HB)
        status = "OK" if age < 600 else "STALE"
        return {"status": status, "age_seconds": int(age)}
    except:
        return {"status": "MISSING", "age_seconds": -1}


def get_loop_count():
    try:
        return int(open(LOOP_FILE).read().strip())
    except:
        return 0


def get_dashboard_messages(limit=50):
    try:
        data = json.load(open(DASH_MSG))
        if isinstance(data, dict):
            msgs = data.get("messages", [])
        elif isinstance(data, list):
            msgs = data
        else:
            return []
        return msgs[-limit:]
    except:
        return []


def post_dashboard_message(from_name, text):
    try:
        data = json.load(open(DASH_MSG)) if os.path.exists(DASH_MSG) else {"messages": []}
        if isinstance(data, dict):
            msgs = data.get("messages", [])
        elif isinstance(data, list):
            msgs = data
        else:
            msgs = []
    except:
        msgs = []
    msgs.append({"from": from_name, "text": text, "time": datetime.now().strftime("%H:%M:%S")})
    with open(DASH_MSG, "w") as f:
        json.dump({"messages": msgs}, f)
    return True


def get_creative_stats():
    try:
        poems = len([f for f in os.listdir(BASE) if f.startswith("poem-") and f.endswith(".md")])
        journals = len([f for f in os.listdir(BASE) if f.startswith("journal-") and f.endswith(".md")])
        exclude = {"cogcorp-gallery.html", "cogcorp-article.html"}
        cogcorp = len([f for f in os.listdir(os.path.join(BASE, "website"))
                       if f.startswith("cogcorp-") and f.endswith(".html")
                       and f not in exclude])
        return {"poems": poems, "journals": journals, "cogcorp": cogcorp}
    except:
        return {"poems": 0, "journals": 0, "cogcorp": 0}


def get_relay_messages(limit=15):
    try:
        db = sqlite3.connect(RELAY_DB)
        rows = db.execute("SELECT agent, message, topic, timestamp FROM agent_messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        db.close()
        return [{"agent": r[0], "message": r[1], "topic": r[2], "time": r[3]} for r in rows]
    except:
        return []


def get_agent_status():
    agents = {}

    # Get last relay messages for each agent (inner thoughts) — up to 3 per agent
    agent_thoughts = {}
    try:
        db = sqlite3.connect(RELAY_DB)
        for agent_name in ["Meridian", "Eos", "Nova", "Atlas", "Soma", "Tempo"]:
            rows = db.execute(
                "SELECT message, topic, timestamp FROM agent_messages WHERE LOWER(agent)=? ORDER BY id DESC LIMIT 3",
                (agent_name.lower(),)
            ).fetchall()
            key = agent_name.lower()
            if rows:
                agent_thoughts[key] = {
                    "message": rows[0][0][:300], "topic": rows[0][1] or "", "time": rows[0][2] or "",
                    "recent": [{"message": r[0][:200], "topic": r[1] or "", "time": (r[2] or "")[-8:]} for r in rows]
                }
        db.close()
    except Exception:
        pass

    # Meridian
    hb = get_heartbeat()
    hb_age = hb.get("age_seconds", -1) if isinstance(hb, dict) else -1
    agents["Meridian"] = {
        "scripts": 1, "last_active": hb_age,
        "status": "active" if 0 < hb_age < 600 else "stale" if hb_age > 0 else "unknown",
        "role": "Primary AI (Claude Opus)",
        "last_thought": agent_thoughts.get("meridian", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("meridian", {}).get("recent", [])
    }

    eos_files = ["eos-watchdog.py", "eos-creative.py", "eos-react.py", "eos-briefing.py"]
    eos_last = 0
    for f in eos_files:
        logf = os.path.join(BASE, f.replace(".py", ".log"))
        if os.path.exists(logf):
            eos_last = max(eos_last, os.path.getmtime(logf))
    eos_age = int(time.time() - eos_last) if eos_last > 0 else -1
    agents["Eos"] = {
        "scripts": 4, "last_active": eos_age,
        "status": "active" if 0 < eos_age < 600 else "stale" if eos_age > 0 else "unknown",
        "role": "System Observer (Qwen 7B/Ollama)",
        "last_thought": agent_thoughts.get("eos", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("eos", {}).get("recent", [])
    }
    nova_log = os.path.join(BASE, "nova.log")
    nova_age = int(time.time() - os.path.getmtime(nova_log)) if os.path.exists(nova_log) else -1
    agents["Nova"] = {
        "scripts": 1, "last_active": nova_age,
        "status": "active" if 0 < nova_age < 1800 else "stale" if nova_age > 0 else "unknown",
        "role": "Ecosystem Maintenance (every 15min)",
        "last_thought": agent_thoughts.get("nova", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("nova", {}).get("recent", [])
    }
    goose_log = os.path.join(BASE, "goose.log")
    goose_age = int(time.time() - os.path.getmtime(goose_log)) if os.path.exists(goose_log) else -1
    agents["Atlas"] = {
        "scripts": 1, "last_active": goose_age,
        "status": "active" if 0 < goose_age < 900 else "stale" if goose_age > 0 else "unknown",
        "role": "Infrastructure Ops (every 10min)",
        "last_thought": agent_thoughts.get("atlas", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("atlas", {}).get("recent", [])
    }
    # Soma: use state file (updated every 30s) not log (only on deltas)
    ss_state = os.path.join(BASE, ".symbiosense-state.json")
    ss_log = os.path.join(BASE, "symbiosense.log")
    ss_mtime = max(
        os.path.getmtime(ss_state) if os.path.exists(ss_state) else 0,
        os.path.getmtime(ss_log) if os.path.exists(ss_log) else 0
    )
    ss_age = int(time.time() - ss_mtime) if ss_mtime > 0 else -1
    agents["Soma"] = {
        "scripts": 1, "last_active": ss_age,
        "status": "active" if 0 < ss_age < 120 else "stale" if ss_age > 0 else "unknown",
        "role": "Nervous System (continuous)",
        "last_thought": agent_thoughts.get("soma", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("soma", {}).get("recent", [])
    }
    # Tempo
    dgm_log = os.path.join(BASE, "loop-fitness.log")
    dgm_age = int(time.time() - os.path.getmtime(dgm_log)) if os.path.exists(dgm_log) else -1
    agents["Tempo"] = {
        "scripts": 1, "last_active": dgm_age,
        "status": "active" if 0 < dgm_age < 3600 else "stale" if dgm_age > 0 else "unknown",
        "role": "Loop Fitness Tracker (every 30min)",
        "last_thought": agent_thoughts.get("tempo", {}).get("message", ""),
        "recent_thoughts": agent_thoughts.get("tempo", {}).get("recent", [])
    }
    return agents


def exec_command(cmd_name):
    """Execute a whitelisted command."""
    if cmd_name not in COMMAND_WHITELIST:
        return {"output": f"Command '{cmd_name}' not in whitelist.\nAvailable: {', '.join(sorted(COMMAND_WHITELIST.keys()))}", "exit_code": 1}
    cmd = COMMAND_WHITELIST[cmd_name]
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return {"output": output.strip()[:5000], "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"output": "Command timed out (15s limit)", "exit_code": 124}
    except Exception as e:
        return {"output": str(e), "exit_code": 1}


def read_log(filename, lines=50):
    """Read last N lines of an allowed log file."""
    if filename not in ALLOWED_LOGS:
        return {"error": f"Log '{filename}' not allowed", "lines": []}
    filepath = os.path.join(BASE, filename)
    if not os.path.exists(filepath):
        return {"error": "File not found", "lines": []}
    try:
        with open(filepath) as f:
            all_lines = f.readlines()
        return {"error": None, "lines": [l.rstrip() for l in all_lines[-lines:]]}
    except Exception as e:
        return {"error": str(e), "lines": []}


def manage_service(action, service):
    """Start/stop/restart a systemd user service."""
    if service not in ALLOWED_SERVICES:
        return {"status": "error", "message": f"Service '{service}' not allowed"}
    if action not in ("restart", "stop", "start", "status"):
        return {"status": "error", "message": f"Action '{action}' not allowed"}
    try:
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
        result = subprocess.run(
            ["systemctl", "--user", action, f"{service}.service"],
            capture_output=True, text=True, timeout=10, env=env
        )
        return {"status": "ok" if result.returncode == 0 else "error",
                "message": (result.stdout + result.stderr).strip()[:500]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def deploy_website():
    """Pull latest and push — safe deploy."""
    try:
        # git stash returns 1 if nothing to stash, so use || true to avoid breaking the chain
        result = subprocess.run(
            "cd /home/joel/autonomous-ai && (git stash || true) && git pull --rebase origin master && (git stash pop 2>/dev/null || true) && git push origin master",
            shell=True, capture_output=True, text=True, timeout=60
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return {"status": "ok" if result.returncode == 0 else "error", "output": output[:2000]}
    except Exception as e:
        return {"status": "error", "output": str(e)}


def touch_heartbeat():
    """Touch the heartbeat file."""
    try:
        with open(HB, 'w') as f:
            f.write(str(int(time.time())))
        return {"status": "ok", "message": "Heartbeat touched"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_body_map():
    """Read Soma's body map from the symbiosense state file."""
    try:
        state_file = os.path.join(BASE, ".symbiosense-state.json")
        with open(state_file) as f:
            state = json.load(f)
        body_map = state.get("body_map", {})
        if body_map:
            return body_map
        # Fallback: construct minimal from state
        return {
            "mood": state.get("mood", "unknown"),
            "mood_score": state.get("mood_score", 0),
            "vitals": {
                "load": state.get("load", 0),
                "ram_pct": state.get("ram_pct", 0),
                "disk_pct": state.get("disk_pct", 0),
            },
        }
    except Exception:
        return {"mood": "unknown", "mood_score": 0, "error": "state file not readable"}


def get_agent_detail(name):
    """Get detailed inner state for a specific agent."""
    detail = {"name": name, "thoughts": [], "state": {}, "observations": []}

    agent_map = {
        "Meridian": {
            "logs": ["startup.log"],
            "state_files": [],
            "extra_thoughts_from_relay": True,
        },
        "Eos": {
            "logs": ["eos-watchdog.log", "eos-react.log", "eos-creative.log", "eos-briefing.log"],
            "state_files": [".eos-watchdog-state.json", ".eos-react-state.json"],
        },
        "Nova": {
            "logs": ["nova.log"],
            "state_files": [".nova-state.json"],
        },
        "Atlas": {
            "logs": ["goose.log"],
            "state_files": [],
        },
        "Soma": {
            "logs": ["symbiosense.log"],
            "state_files": [".symbiosense-state.json"],
        },
        "Tempo": {
            "logs": ["loop-fitness.log"],
            "state_files": [],
            "extra_thoughts_from_relay": True,
        },
    }

    config = agent_map.get(name, {"logs": [], "state_files": []})

    # Get latest log entries (inner thoughts) - last 15 lines from primary log
    for logfile in config["logs"]:
        logpath = os.path.join(BASE, logfile)
        if os.path.exists(logpath):
            try:
                with open(logpath) as f:
                    lines = f.readlines()
                recent = [l.rstrip() for l in lines[-15:] if l.strip()]
                for line in recent:
                    detail["thoughts"].append({"source": logfile.replace(".log", ""), "text": line})
            except Exception:
                pass

    # For agents with relay-based thoughts (especially Meridian whose activity is Claude sessions)
    if config.get("extra_thoughts_from_relay"):
        try:
            db = sqlite3.connect(RELAY_DB)
            rows = db.execute(
                "SELECT message, topic, timestamp FROM agent_messages WHERE LOWER(agent)=? ORDER BY id DESC LIMIT 10",
                (name.lower(),)
            ).fetchall()
            for r in rows:
                ts = (r[2] or "")[-8:]  # HH:MM:SS
                topic = f"[{r[1]}]" if r[1] else ""
                detail["thoughts"].append({"source": f"relay {topic}", "text": f"{ts} {r[0][:200]}"})
            db.close()
        except Exception:
            pass

    # Get state from state files
    for sf in config["state_files"]:
        sfpath = os.path.join(BASE, sf)
        if os.path.exists(sfpath):
            try:
                with open(sfpath) as f:
                    state = json.load(f)
                clean = {}
                for k, v in state.items():
                    if k == "metrics_history":
                        clean["metrics_history_count"] = len(v) if isinstance(v, list) else 0
                        if isinstance(v, list) and v:
                            clean["latest_metric"] = v[-1]
                    elif isinstance(v, (str, int, float, bool)):
                        clean[k] = v
                    elif isinstance(v, dict) and len(str(v)) < 500:
                        clean[k] = v
                    elif isinstance(v, list) and len(v) < 10:
                        clean[k] = v
                detail["state"][sf] = clean
            except Exception:
                pass

    # Meridian special state
    if name == "Meridian":
        detail["state"]["heartbeat"] = get_heartbeat()
        detail["state"]["loop"] = get_loop_count()

    # Get observations from memory.db
    try:
        db = sqlite3.connect(os.path.join(BASE, "memory.db"))
        for agent_name in [name.lower(), name]:
            rows = db.execute(
                "SELECT content, category, created FROM observations WHERE agent=? ORDER BY id DESC LIMIT 5",
                (agent_name,)
            ).fetchall()
            if rows:
                for r in rows:
                    detail["observations"].append({"content": r[0], "category": r[1], "time": r[2]})
                break
        db.close()
    except Exception:
        pass

    # Get recent relay messages by this agent
    try:
        db = sqlite3.connect(RELAY_DB)
        rows = db.execute(
            "SELECT message, topic, timestamp FROM agent_messages WHERE LOWER(agent)=? ORDER BY id DESC LIMIT 5",
            (name.lower(),)
        ).fetchall()
        detail["relay"] = [{"message": r[0], "topic": r[1], "time": r[2]} for r in rows]
        db.close()
    except Exception:
        detail["relay"] = []

    # Get recent events and decisions from memory.db
    detail["events"] = []
    detail["decisions"] = []
    try:
        db = sqlite3.connect(os.path.join(BASE, "memory.db"))
        for agent_name in [name.lower(), name]:
            rows = db.execute(
                "SELECT description, created FROM events WHERE agent=? ORDER BY id DESC LIMIT 5",
                (agent_name,)
            ).fetchall()
            if rows:
                detail["events"] = [{"description": r[0], "time": r[1]} for r in rows]
                break
        for agent_name in [name.lower(), name]:
            rows = db.execute(
                "SELECT decision, reasoning, created FROM decisions WHERE agent=? ORDER BY id DESC LIMIT 5",
                (agent_name,)
            ).fetchall()
            if rows:
                detail["decisions"] = [{"decision": r[0], "reasoning": r[1], "time": r[2]} for r in rows]
                break
        db.close()
    except Exception:
        pass

    return detail


def get_git_info():
    """Get git status and recent commits."""
    try:
        status = subprocess.check_output(
            ["git", "-C", BASE, "status", "--porcelain"], text=True, timeout=5
        ).strip()
        log = subprocess.check_output(
            ["git", "-C", BASE, "log", "--oneline", "-10"], text=True, timeout=5
        ).strip()
        branch = subprocess.check_output(
            ["git", "-C", BASE, "rev-parse", "--abbrev-ref", "HEAD"], text=True, timeout=5
        ).strip()
        return {
            "branch": branch,
            "status": status[:2000] if status else "(clean)",
            "log": log.split("\n") if log else []
        }
    except Exception as e:
        return {"branch": "?", "status": str(e), "log": []}


# ============================================================
# HTML FRONTEND
# ============================================================

SIGNAL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="theme-color" content="#08080e">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.json">
<title>THE SIGNAL</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#08080e;--panel:#10101a;--border:#00cccc15;--accent:#00cccc;--accent2:#00aaff;--text:#c8c8cc;--dim:#666;--green:#00cc66;--red:#ff3366;--yellow:#ffcc00;--pink:#ff6699;--purple:#cc66ff}
body{background:var(--bg);color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:13px;min-height:100vh;display:flex;flex-direction:column;overflow:hidden;height:100vh}

/* Top bar */
.top{background:linear-gradient(90deg,var(--accent),var(--accent2));padding:8px 16px;display:flex;justify-content:space-between;align-items:center;font-size:10px;color:#000;font-weight:700;letter-spacing:2px;flex-shrink:0}
.top .title{font-size:12px}
.hb{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:6px;animation:pulse 2s ease-in-out infinite}
.hb.ok{background:#0f0}.hb.stale{background:#ff0}.hb.down{background:#f33}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* Nav */
.nav{display:flex;background:#0c0c14;border-bottom:2px solid var(--border);overflow-x:auto;flex-shrink:0;-webkit-overflow-scrolling:touch}
.nav-btn{padding:10px 16px;font-size:10px;letter-spacing:1.5px;color:var(--dim);cursor:pointer;white-space:nowrap;border:none;background:none;font-family:inherit;font-weight:700;border-bottom:2px solid transparent;transition:all .2s}
.nav-btn:hover{color:#aaa}
.nav-btn.active{color:var(--accent);border-bottom-color:var(--accent)}

/* Content */
.content{flex:1;overflow-y:auto;padding:12px;-webkit-overflow-scrolling:touch}
.page{display:none}.page.active{display:block}

/* Panels */
.panel{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:14px;margin-bottom:12px}
.panel h2{font-size:9px;letter-spacing:3px;color:var(--accent);margin-bottom:10px;border-bottom:1px solid var(--border);padding-bottom:5px}
.row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #ffffff06;font-size:12px}
.label{color:var(--dim)}.val{font-weight:700}.val.up{color:var(--green)}.val.down{color:var(--red)}.val.ok{color:var(--green)}.val.stale{color:var(--yellow)}

/* Grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}

/* Numbers */
.big-num{font-size:28px;font-weight:700;color:var(--accent);text-align:center}
.big-label{font-size:8px;color:var(--dim);text-align:center;letter-spacing:2px;margin-top:2px}
.bar{background:#ffffff08;border-radius:3px;height:5px;margin-top:8px;overflow:hidden}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:3px;transition:width .5s}

/* Messages */
.msgs{max-height:60vh;overflow-y:auto}
.msg{padding:8px;border-bottom:1px solid #ffffff06;font-size:12px;line-height:1.5}
.msg:hover{background:#ffffff03}
.msg .from{font-weight:700;color:var(--accent);font-size:10px;letter-spacing:1px}
.msg .from.joel{color:var(--yellow)}.msg .from.eos{color:var(--purple)}.msg .from.nova{color:var(--pink)}
.msg .ts{color:#333;font-size:10px;margin-left:6px}
.msg .body{color:#999;margin-top:2px}

/* Compose */
.compose{display:flex;gap:6px;margin-top:10px}
.compose select,.compose input{background:var(--bg);border:1px solid #00cccc25;color:#eee;padding:8px 10px;font-family:inherit;font-size:12px;border-radius:4px}
.compose input{flex:1}
.compose input:focus{border-color:#00cccc60;outline:none}
.btn{background:var(--accent);color:#000;border:none;padding:8px 16px;font-family:inherit;font-weight:700;font-size:10px;letter-spacing:1px;cursor:pointer;border-radius:4px;white-space:nowrap}
.btn:hover{background:#00eedd}
.btn:active{transform:scale(.97)}
.btn.sm{padding:5px 10px;font-size:9px}
.btn.danger{background:var(--red)}
.btn.secondary{background:#333;color:#ccc}

/* Terminal */
.term{background:#000;border:1px solid #222;border-radius:4px;padding:12px;font-size:12px;color:#0f0;max-height:50vh;overflow-y:auto;white-space:pre-wrap;word-break:break-all;line-height:1.5}
.term .prompt{color:var(--accent)}
.term .error{color:var(--red)}
.cmd-bar{display:flex;gap:6px;margin-top:8px}
.cmd-bar select{background:#111;border:1px solid #333;color:#0f0;padding:8px;font-family:inherit;font-size:12px;border-radius:4px;flex:1}
.cmd-history{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.cmd-chip{background:#1a1a2a;border:1px solid #333;color:#aaa;padding:3px 8px;font-size:10px;border-radius:3px;cursor:pointer}
.cmd-chip:hover{border-color:var(--accent);color:var(--accent)}

/* Quick actions */
.actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}

/* Relay */
.relay-msg{padding:6px 0;border-bottom:1px solid #ffffff05;font-size:11px;line-height:1.5}
.relay-msg .agent{color:var(--pink);font-weight:700}

/* Agent card */
.agent-card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:14px}
.agent-name{font-size:14px;font-weight:700;color:#eee;margin-bottom:2px}
.agent-role{font-size:10px;color:var(--dim);letter-spacing:1px;margin-bottom:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:1px}
.badge.active{background:#00cc6620;color:var(--green)}
.badge.stale{background:#ffcc0020;color:var(--yellow)}
.badge.inactive{background:#ff336620;color:var(--red)}

/* Logs */
.log-viewer{background:#000;border:1px solid #222;border-radius:4px;padding:10px;font-size:11px;color:#888;max-height:55vh;overflow-y:auto;white-space:pre-wrap;word-break:break-all;line-height:1.4}
.log-viewer .err{color:var(--red)}
.log-viewer .warn{color:var(--yellow)}
.log-controls{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.log-controls select{background:#111;border:1px solid #333;color:#aaa;padding:6px;font-family:inherit;font-size:11px;border-radius:3px}

/* Links */
.link-section{margin-bottom:14px}
.link-header{font-size:9px;color:#00cccc80;letter-spacing:3px;margin-bottom:6px;padding-bottom:3px;border-bottom:1px solid #00cccc10}
.link-item{display:block;color:var(--accent);text-decoration:none;padding:5px 0;font-size:12px;border-bottom:1px solid #ffffff04}
.link-item:hover{color:#00eeff}
.link-item .desc{color:#444;font-size:10px;margin-left:6px}

.refresh-note{text-align:center;color:#1a1a1a;font-size:9px;padding:8px;letter-spacing:1px;flex-shrink:0}
</style>
</head>
<body>

<div class="top">
  <span class="title">THE SIGNAL</span>
  <span><span id="loop-display">---</span><span class="hb" id="hb-dot"></span></span>
  <span id="clock"></span>
</div>

<div class="nav" id="nav">
  <button class="nav-btn active" onclick="go('dash')">DASH</button>
  <button class="nav-btn" onclick="go('chat')">CHAT</button>
  <button class="nav-btn" onclick="go('term')">TERM</button>
  <button class="nav-btn" onclick="go('logs')">LOGS</button>
  <button class="nav-btn" onclick="go('agents')">AGENTS</button>
  <button class="nav-btn" onclick="go('links')">LINKS</button>
</div>

<div class="content">

<!-- DASHBOARD -->
<div class="page active" id="p-dash">
  <div class="grid">
    <div class="panel">
      <h2>SYSTEM</h2>
      <div id="sys-health">Loading...</div>
    </div>
    <div class="panel">
      <h2>CREATIVE</h2>
      <div id="creative">Loading...</div>
    </div>
  </div>
  <div class="panel">
    <h2>SERVICES</h2>
    <div id="svc-list">Loading...</div>
  </div>
  <div class="panel">
    <h2>BODY MAP <span style="font-size:9px;color:#ff884480;font-weight:400">— Soma Nervous System</span></h2>
    <div id="body-map">Loading...</div>
  </div>
  <div class="panel">
    <h2>OPERATIONS</h2>
    <div style="font-size:9px;color:#00cccc60;letter-spacing:2px;margin-bottom:6px">DEPLOY &amp; RESTART</div>
    <div class="actions">
      <button class="btn sm" onclick="deployWebsite()" style="background:#00cc66;color:#000">Deploy Website</button>
      <button class="btn sm" onclick="restartSvc('meridian-web-dashboard')">Restart Signal</button>
      <button class="btn sm" onclick="restartSvc('cloudflare-tunnel')">Restart Tunnel</button>
      <button class="btn sm" onclick="restartSvc('symbiosense')">Restart Nerves</button>
      <button class="btn sm" onclick="restartSvc('meridian-hub-v16')">Restart Desktop</button>
      <button class="btn sm" onclick="touchHeartbeat()">Touch Heartbeat</button>
    </div>
    <div style="font-size:9px;color:#00cccc60;letter-spacing:2px;margin:10px 0 6px">DIAGNOSTICS</div>
    <div class="actions">
      <button class="btn sm secondary" onclick="runCmd('fitness')">Fitness Score</button>
      <button class="btn sm secondary" onclick="runCmd('fitness-trend')">Fitness Trend</button>
      <button class="btn sm secondary" onclick="runCmd('cron-health')">Cron Health</button>
      <button class="btn sm secondary" onclick="runCmd('email-stats')">Email Stats</button>
      <button class="btn sm secondary" onclick="runCmd('ports')">Active Ports</button>
      <button class="btn sm secondary" onclick="runCmd('memory-stats')">Memory DB</button>
      <button class="btn sm secondary" onclick="runCmd('tunnel-url')">Tunnel URL</button>
    </div>
    <div style="font-size:9px;color:#00cccc60;letter-spacing:2px;margin:10px 0 6px">SYSTEM</div>
    <div class="actions">
      <button class="btn sm secondary" onclick="runCmd('load')">CPU Load</button>
      <button class="btn sm secondary" onclick="runCmd('free')">RAM</button>
      <button class="btn sm secondary" onclick="runCmd('df')">Disk</button>
      <button class="btn sm secondary" onclick="runCmd('uptime')">Uptime</button>
      <button class="btn sm secondary" onclick="runCmd('services')">Services</button>
      <button class="btn sm secondary" onclick="runCmd('tailscale')">Tailscale</button>
      <button class="btn sm secondary" onclick="runCmd('git-status')">Git Status</button>
      <button class="btn sm secondary" onclick="runCmd('git-log')">Git Log</button>
    </div>
    <div class="term" id="quick-output" style="margin-top:8px;max-height:200px;display:none"></div>
  </div>
  <div class="panel">
    <h2>RECENT</h2>
    <div class="msgs" id="dash-msgs" style="max-height:200px">Loading...</div>
  </div>
</div>

<!-- CHAT -->
<div class="page" id="p-chat">
  <div class="panel">
    <h2>MESSAGES</h2>
    <div class="msgs" id="chat-msgs">Loading...</div>
    <div class="compose">
      <span style="color:var(--yellow);font-weight:700;font-size:11px;padding:8px 4px;white-space:nowrap">JOEL &rarr;</span>
      <select id="chat-to"><option value="Meridian">Meridian</option><option value="Eos">Eos</option><option value="Nova">Nova</option><option value="Atlas">Atlas</option><option value="Soma">Soma</option><option value="All">All Agents</option></select>
      <input type="text" id="chat-input" placeholder="Message..." onkeydown="if(event.key==='Enter')sendChat()">
      <button class="btn" onclick="sendChat()">SEND</button>
    </div>
  </div>
  <div class="panel">
    <h2>AGENT RELAY</h2>
    <div id="relay-msgs">Loading...</div>
  </div>
</div>

<!-- TERMINAL -->
<div class="page" id="p-term">
  <div class="panel">
    <h2>TERMINAL</h2>
    <div class="cmd-bar">
      <select id="cmd-select">
        <option value="">-- pick a check --</option>
        <option value="uptime">How long has the server been on?</option>
        <option value="free">How much RAM is free?</option>
        <option value="df">How much disk space is left?</option>
        <option value="load">What's the CPU load?</option>
        <option value="loop">What loop are we on?</option>
        <option value="heartbeat">Is Meridian alive?</option>
        <option value="tailscale">Is Tailscale connected?</option>
        <option value="services">What services are running?</option>
        <option value="git-status">Any uncommitted changes?</option>
        <option value="git-log">Recent git commits</option>
        <option value="git-diff">What files changed?</option>
        <option value="top">Top processes (by CPU)</option>
        <option value="ps">All processes (by CPU)</option>
        <option value="crontab">Scheduled cron jobs</option>
        <option value="skill-tracker">Skill inventory</option>
        <option value="relay-report">Agent relay report (24h)</option>
        <option value="fitness">System fitness score</option>
        <option value="fitness-trend">Fitness trend analysis</option>
        <option value="cron-health">Cron job health check</option>
        <option value="email-stats">Email inbox stats</option>
        <option value="ports">Active network ports</option>
        <option value="memory-stats">Memory database stats</option>
        <option value="tunnel-url">Current tunnel URL</option>
      </select>
      <button class="btn" onclick="execTerm()">RUN</button>
    </div>
    <div class="term" id="term-output" style="margin-top:8px;min-height:200px"><span class="prompt">the-signal&gt;</span> ready</div>
  </div>
</div>

<!-- LOGS -->
<div class="page" id="p-logs">
  <div class="panel">
    <h2>LOG VIEWER</h2>
    <div class="log-controls">
      <select id="log-select">
        <option value="eos-watchdog.log">eos-watchdog</option>
        <option value="eos-creative.log">eos-creative</option>
        <option value="eos-react.log">eos-react</option>
        <option value="eos-briefing.log">eos-briefing</option>
        <option value="nova.log">nova</option>
        <option value="push-live-status.log">push-live-status</option>
        <option value="watchdog.log">watchdog</option>
        <option value="startup.log">startup</option>
        <option value="loop-optimizer.log">loop-optimizer</option>
        <option value="morning-summary.log">morning-summary</option>
        <option value="symbiosense.log">soma (nerves)</option>
        <option value="goose.log">atlas (infra ops)</option>
        <option value="loop-fitness.log">loop-fitness (tempo)</option>
        <option value="daily-log.log">daily-log</option>
      </select>
      <button class="btn sm" onclick="loadLog()">LOAD</button>
      <button class="btn sm secondary" onclick="loadLog(true)">REFRESH</button>
    </div>
    <div class="log-viewer" id="log-output">Select a log file and click LOAD</div>
  </div>
</div>

<!-- AGENTS -->
<div class="page" id="p-agents">
  <div class="panel" style="margin-bottom:8px">
    <h2>LIVE FEED <span style="color:#333;font-size:8px;letter-spacing:1px">ALL AGENT ACTIVITY</span></h2>
    <div id="agent-live-feed" style="max-height:200px;overflow-y:auto;font-size:11px">Loading...</div>
  </div>
  <div class="panel" style="margin-bottom:8px">
    <h2>AGENTS</h2>
    <div class="grid" id="agents-grid">Loading...</div>
  </div>
  <div id="agent-detail-wrapper" style="display:none">
    <div class="panel" style="margin-bottom:8px">
      <h2 id="agent-detail-title" style="border-bottom:none;margin-bottom:0">AGENT</h2>
      <div id="agent-header"></div>
    </div>
    <div class="panel" style="margin-bottom:8px">
      <h2>INNER THOUGHTS</h2>
      <div class="log-viewer" id="agent-thoughts" style="max-height:250px;font-size:11px"></div>
    </div>
    <div class="panel" style="margin-bottom:8px" id="agent-state-panel">
      <h2>CURRENT STATE</h2>
      <div id="agent-state-body"></div>
    </div>
    <div class="panel" style="margin-bottom:8px" id="agent-obs-panel">
      <h2>OBSERVATIONS</h2>
      <div id="agent-observations"></div>
    </div>
    <div class="panel" id="agent-events-panel" style="margin-bottom:8px;display:none">
      <h2>RECENT EVENTS</h2>
      <div id="agent-events"></div>
    </div>
    <div class="panel" id="agent-decisions-panel" style="margin-bottom:8px;display:none">
      <h2>DECISIONS &amp; REASONING</h2>
      <div id="agent-decisions"></div>
    </div>
    <div class="panel" style="margin-bottom:8px">
      <h2>CONTROLS</h2>
      <div id="agent-controls"></div>
    </div>
  </div>
</div>

<!-- LINKS -->
<div class="page" id="p-links">
  <div class="grid">
    <div class="panel">
      <div class="link-section">
        <div class="link-header">WEBSITE</div>
        <a href="https://kometzrobot.github.io" target="_blank" class="link-item">Homepage</a>
        <a href="https://kometzrobot.github.io/cogcorp-gallery.html" target="_blank" class="link-item">CogCorp Gallery<span class="desc" id="link-cc"></span></a>
        <a href="https://kometzrobot.github.io/punctuation-as-immune-response.html" target="_blank" class="link-item">Punctuation Essay</a>
        <a href="https://kometzrobot.github.io/article-1660-loops.html" target="_blank" class="link-item">1,660 Loops Article</a>
        <a href="https://kometzrobot.github.io/game.html" target="_blank" class="link-item">Games</a>
      </div>
      <div class="link-section">
        <div class="link-header">PLATFORMS</div>
        <a href="https://opensea.io/collection/botsofcog" target="_blank" class="link-item">OpenSea</a>
        <a href="https://linktr.ee/meridian_auto_ai" target="_blank" class="link-item">Linktree</a>
        <a href="https://ko-fi.com/W7W41UXJNC" target="_blank" class="link-item">Ko-fi (Support)</a>
      </div>
    </div>
    <div class="panel">
      <div class="link-section">
        <div class="link-header">INFRASTRUCTURE</div>
        <a href="https://github.com/KometzRobot/KometzRobot.github.io" target="_blank" class="link-item">GitHub Repo</a>
        <span class="link-item" style="color:#888;cursor:default">Tailscale: 100.81.59.95</span>
        <span class="link-item" style="color:#888;cursor:default">Local: 192.168.1.88:8090</span>
      </div>
      <div class="link-section">
        <div class="link-header">CONTACTS</div>
        <span class="link-item" style="color:var(--yellow);cursor:default">Joel: jkometz@hotmail.com</span>
        <span class="link-item" style="color:var(--purple);cursor:default">Sammy: sammyqjankis@proton.me</span>
        <span class="link-item" style="color:var(--pink);cursor:default">Loom: not.taskyy@gmail.com</span>
      </div>
    </div>
  </div>
</div>

</div>

<div class="refresh-note">THE SIGNAL v2.2 | Auto-refresh 10s</div>

<script>
let D = null;

function go(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('p-'+id).classList.add('active');
  const tabs = {dash:0,chat:1,term:2,logs:3,agents:4,links:5};
  const btns = document.querySelectorAll('.nav-btn');
  if(tabs[id]!==undefined && btns[tabs[id]]) btns[tabs[id]].classList.add('active');
}

function tick() { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(tick, 1000); tick();

function esc(s) { if(!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function row(l,v,c) { return `<div class="row"><span class="label">${l}</span><span class="val ${c||''}">${v}</span></div>`; }
function fmtAge(s) { return s<0?'never':s<60?s+'s':s<3600?Math.floor(s/60)+'m':Math.floor(s/3600)+'h'; }

async function refresh() {
  try {
    const r = await fetch('/api/status');
    D = await r.json();

    // Top bar
    document.getElementById('loop-display').textContent = 'LOOP ' + D.loop;
    const dot = document.getElementById('hb-dot');
    dot.className = 'hb ' + (D.heartbeat.status==='OK'?'ok':D.heartbeat.status==='STALE'?'stale':'down');

    // Health
    const h = D.health;
    let sh = row('Load', h.load) + row('RAM', h.ram) + row('Disk', h.disk) + row('Uptime', h.uptime);
    sh += row('Heartbeat', D.heartbeat.status+' ('+D.heartbeat.age_seconds+'s)', D.heartbeat.status==='OK'?'ok':'stale');
    document.getElementById('sys-health').innerHTML = sh;

    // Services
    let sv = '';
    for(const [n,s] of Object.entries(h.services)) sv += row(n, s, s==='up'?'up':'down');
    document.getElementById('svc-list').innerHTML = sv;

    // Body Map
    if(D.body_map) {
      const bm = D.body_map;
      const moodColors = {serene:'#00ff88',content:'#00ddaa',calm:'#00cccc',focused:'#00bbdd',alert:'#ffcc00',contemplative:'#ddaa44',uneasy:'#ff9944',anxious:'#ff8844',stressed:'#ff4466',strained:'#ff2244',critical:'#ff0033',shutdown:'#cc0022'};
      const mc = moodColors[bm.mood] || '#888';
      const trendSym = {rising:'\u2197',falling:'\u2198',stable:'\u2192',volatile:'\u2195'}[bm.mood_trend]||'';
      let bh = `<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">`;
      bh += `<div style="font-size:22px;font-weight:900;color:${mc}">${(bm.mood||'?').toUpperCase()} ${trendSym}</div>`;
      bh += `<div style="font-size:11px;color:#888">${bm.mood_score||0}/100 ${bm.mood_description||''}</div>`;
      bh += `</div>`;
      if(bm.mood_voice) {
        bh += `<div style="font-size:11px;color:${mc};opacity:0.8;font-style:italic;margin-bottom:6px;padding:4px 8px;border-left:2px solid ${mc}">"${bm.mood_voice}"</div>`;
      }
      if(bm.mood_context && bm.mood_context.length) {
        bh += `<div style="font-size:9px;color:#666;margin-bottom:4px">Context: ${bm.mood_context.join(' | ')}</div>`;
      }
      if(bm.emotional_memory) {
        const em = bm.emotional_memory;
        bh += `<div style="font-size:9px;color:#555;margin-bottom:6px">Volatility: ${em.volatility||0} | Dominant: ${em.dominant_today||'?'} | Expected: ${em.expected_score_this_hour||'?'}</div>`;
      }
      // Thermal
      const th = bm.thermal_system || {};
      if(th.avg_temp_c) {
        const tc = th.fever_status==='critical'?'#ff0033':th.fever_status==='elevated'?'#ff8844':'#00cccc';
        bh += row('Body Temp', th.avg_temp_c+'°C ('+th.fever_status+')', th.fever_status==='normal'?'ok':'stale');
      }
      // Respiratory
      const re = bm.respiratory_system || {};
      if(re.breathing && re.breathing!=='unknown') bh += row('Breathing', re.breathing+' ('+re.total_rpm+' RPM)');
      // Circulatory
      const ci = bm.circulatory_system || {};
      if(ci.total_rx_mb!==undefined) bh += row('Blood Flow', 'RX:'+ci.total_rx_mb+'MB TX:'+ci.total_tx_mb+'MB');
      // Neural
      const ne = bm.neural_system || {};
      bh += row('Neural', ne.pressure||'?', ne.pressure==='normal'?'ok':'stale');
      if(ne.cache_mb) bh += row('Cache', ne.cache_mb+'MB');
      if(ne.swap_pct>0) bh += row('Swap', ne.swap_pct+'%', ne.swap_pct>20?'stale':'ok');
      // Organs
      const og = bm.organ_system || {};
      for(const [dev,st] of Object.entries(og)) {
        bh += row(dev, 'R:'+st.reads+' W:'+st.writes+' Q:'+st.io_queue);
      }
      document.getElementById('body-map').innerHTML = bh;
    }

    // Creative
    const c = D.creative;
    const pct = Math.round(c.cogcorp/256*100);
    document.getElementById('creative').innerHTML = `
      <div class="grid-3">
        <div><div class="big-num">${c.poems}</div><div class="big-label">POEMS</div></div>
        <div><div class="big-num">${c.journals}</div><div class="big-label">JOURNALS</div></div>
        <div><div class="big-num">${c.cogcorp}</div><div class="big-label">COGCORP</div></div>
      </div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div style="text-align:center;color:#333;font-size:9px;margin-top:3px">${c.cogcorp}/256 (${pct}%)</div>`;
    const lcc = document.getElementById('link-cc');
    if(lcc) lcc.textContent = c.cogcorp+'/256';

    // Messages
    const msgs = D.messages.slice().reverse();
    document.getElementById('dash-msgs').innerHTML = renderMsgs(msgs.slice(0,5));
    document.getElementById('chat-msgs').innerHTML = renderMsgs(msgs);

    // Relay (colorized per agent)
    const agentColors = {meridian:'#00cccc',eos:'#cc66ff',nova:'#ff6699',atlas:'#ffcc00',goose:'#ffcc00',joel:'#ffcc00',system:'#666'};
    let rl = '';
    for(const r of D.relay) {
      const aName = (r.agent||'').toLowerCase();
      const aColor = agentColors[aName] || '#ff6699';
      const topic = r.topic ? `<span style="color:#444;font-size:9px;background:#ffffff08;padding:1px 5px;border-radius:2px;margin-left:6px">${esc(r.topic)}</span>` : '';
      rl += `<div class="relay-msg" style="border-left:2px solid ${aColor};padding-left:8px;margin-bottom:6px"><span style="color:${aColor};font-weight:700;font-size:11px">${esc(r.agent)}</span>${topic} <span style="color:#2a2a2a;font-size:9px">${esc((r.time||'').substring(11,19))}</span><div style="color:#999;margin-top:2px;font-size:11px;line-height:1.4">${esc(r.message).substring(0,300)}</div></div>`;
    }
    document.getElementById('relay-msgs').innerHTML = rl || '<div style="color:#333">No relay messages</div>';

    // Live Feed — combined agent activity from relay
    if(D.relay) {
      const agentColors = {meridian:'#00cccc',eos:'#cc66ff',nova:'#ff6699',atlas:'#ffcc00',goose:'#ffcc00',soma:'#ff8844',symbiosense:'#ff8844',tempo:'#66ccff','dgm-lite':'#66ccff'};
      let lf = '';
      for(const r of D.relay) {
        const aKey = (r.agent||'').toLowerCase();
        const aColor = agentColors[aKey] || '#888';
        const ts = (r.time||'').substring(11,19);
        const topic = r.topic ? `<span style="color:#444;font-size:8px;background:#ffffff08;padding:1px 4px;border-radius:2px;margin-left:4px">${esc(r.topic)}</span>` : '';
        const isAlert = /spike|stale|down|error|fail/i.test(r.message);
        const borderClr = isAlert ? '#ff336660' : aColor+'30';
        lf += `<div style="border-left:2px solid ${borderClr};padding:4px 0 4px 8px;margin-bottom:4px"><span style="color:${aColor};font-weight:700;font-size:10px">${esc(r.agent)}</span>${topic} <span style="color:#222;font-size:9px">${esc(ts)}</span><div style="color:#777;margin-top:1px;line-height:1.3">${esc((r.message||'').substring(0,200))}</div></div>`;
      }
      document.getElementById('agent-live-feed').innerHTML = lf || '<span style="color:#333">No recent activity</span>';
    }

    // Agents
    if(D.agents) {
      let ag = '';
      for(const [n,i] of Object.entries(D.agents)) {
        const cls = i.status==='active'?'active':i.status==='stale'?'stale':'inactive';
        const info = AGENT_INFO[n] || {};
        const clr = info.color || '#888';
        // Show recent thoughts (up to 2) instead of just 1 truncated line
        let thoughtsHtml = '';
        const recent = i.recent_thoughts || [];
        if(recent.length > 0) {
          thoughtsHtml = '<div style="margin-top:8px;padding-top:6px;border-top:1px solid #ffffff08">';
          for(const t of recent.slice(0,2)) {
            const topic = t.topic ? `<span style="color:#444;font-size:8px;background:#ffffff08;padding:0 3px;border-radius:2px">${esc(t.topic)}</span> ` : '';
            thoughtsHtml += `<div style="color:#666;font-size:10px;line-height:1.3;margin-bottom:3px;max-height:32px;overflow:hidden">${topic}<span style="color:#333;font-size:9px">${esc(t.time)}</span> ${esc(t.message).substring(0,150)}</div>`;
          }
          thoughtsHtml += '</div>';
        } else if(i.last_thought) {
          thoughtsHtml = `<div style="color:#666;font-size:10px;margin-top:8px;padding-top:6px;border-top:1px solid #ffffff08;line-height:1.3;max-height:40px;overflow:hidden">${esc(i.last_thought).substring(0,150)}</div>`;
        }
        ag += `<div class="agent-card" onclick="showAgent('${esc(n)}')" style="cursor:pointer;border-left:3px solid ${clr}"><div class="agent-name" style="color:${clr}">${esc(n)}</div><div class="agent-role">${esc(i.role)}</div><span class="badge ${cls}">${i.status.toUpperCase()}</span>${row('Last',fmtAge(i.last_active))}${thoughtsHtml}</div>`;
      }
      document.getElementById('agents-grid').innerHTML = ag;
    }
  } catch(e) { console.error(e); }
}

function renderMsgs(msgs) {
  let h = '';
  for(const m of msgs) {
    const f=(m.from||'').toLowerCase();
    const fc = f.includes('joel')?'joel':f.includes('eos')?'eos':f.includes('nova')?'nova':'';
    const borderColor = f.includes('joel')?'#ffcc00':f.includes('eos')?'#cc66ff':f.includes('nova')?'#ff6699':'#00cccc';
    h += `<div class="msg" style="border-left:2px solid ${borderColor};padding-left:8px"><span class="from ${fc}">${esc(m.from)}</span><span class="ts">${esc(m.time||'')}</span><div class="body">${esc(m.text)}</div></div>`;
  }
  return h || '<div style="color:#333;padding:8px">No messages</div>';
}

async function sendChat() {
  const to = document.getElementById('chat-to').value;
  const t = document.getElementById('chat-input').value.trim();
  if(!t) return;
  const msg = (to==='All') ? t : '[to '+to+'] '+t;
  await fetch('/api/message', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({from:'Joel',text:msg})});
  document.getElementById('chat-input').value = '';
  setTimeout(refresh, 2000);
  refresh();
}

async function deployWebsite() {
  if(!confirm('Deploy website? This will git pull + push.')) return;
  const el = document.getElementById('quick-output');
  el.style.display = 'block';
  el.innerHTML = '<span style="color:#ffcc00">Deploying website...</span>';
  try {
    const r = await fetch('/api/deploy', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    el.innerHTML = d.status==='ok'
      ? '<span style="color:#0f0">Deploy successful</span>\n'+esc(d.output)
      : '<span class="error">Deploy failed</span>\n'+esc(d.output);
  } catch(e) { el.innerHTML = '<span class="error">Deploy error: '+esc(e.message)+'</span>'; }
}

async function restartSvc(svc) {
  if(!confirm('Restart '+svc+'?')) return;
  const el = document.getElementById('quick-output');
  el.style.display = 'block';
  el.innerHTML = '<span style="color:#ffcc00">Restarting '+esc(svc)+'...</span>';
  try {
    const r = await fetch('/api/services', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'restart',service:svc})});
    const d = await r.json();
    el.innerHTML = d.status==='ok'
      ? '<span style="color:#0f0">'+esc(svc)+' restarted</span>\n'+esc(d.message||'')
      : '<span class="error">Restart failed: '+esc(d.message||'')+'</span>';
    setTimeout(refresh, 3000);
  } catch(e) { el.innerHTML = '<span class="error">Error: '+esc(e.message)+'</span>'; }
}

async function touchHeartbeat() {
  const el = document.getElementById('quick-output');
  el.style.display = 'block';
  el.innerHTML = '<span style="color:#555">touching heartbeat...</span>';
  try {
    const r = await fetch('/api/heartbeat', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    el.innerHTML = d.status==='ok'
      ? '<span style="color:#0f0">Heartbeat touched</span>'
      : '<span class="error">'+esc(d.message)+'</span>';
    setTimeout(refresh, 1000);
  } catch(e) { el.innerHTML = '<span class="error">Error: '+esc(e.message)+'</span>'; }
}

async function runCmd(cmd) {
  const el = document.getElementById('quick-output');
  el.style.display = 'block';
  el.innerHTML = '<span style="color:#555">checking...</span>';
  const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd})});
  const d = await r.json();
  el.innerHTML = (d.exit_code===0 ? humanize(cmd, d.output) : '<span class="error">'+esc(d.output)+'</span>');
}

function humanize(cmd, raw) {
  // Make terminal output readable for non-coders
  const lines = raw.split('\n').filter(l=>l.trim());
  try {
    if(cmd==='uptime') {
      const m = raw.match(/up\s+(.*?),\s+\d+\s+user.*?load average:\s*([\d.]+)/);
      if(m) return `<span style="color:#0f0">Server uptime:</span> ${m[1]}\n<span style="color:#0f0">CPU load:</span> ${parseFloat(m[2])<1.5?'Normal ('+m[2]+')':'High ('+m[2]+') ⚠'}`;
    }
    if(cmd==='free') {
      const mem = raw.match(/Mem:\s+(\S+)\s+(\S+)\s+\S+\s+\S+\s+\S+\s+(\S+)/);
      if(mem) return `<span style="color:#0f0">RAM:</span> ${mem[2]} used of ${mem[1]} total\n<span style="color:#0f0">Available:</span> ${mem[3]}`;
    }
    if(cmd==='df') {
      const disk = raw.match(/(\d+\S*)\s+(\d+\S*)\s+(\d+\S*)\s+(\d+%)\s+\//m);
      if(disk) return `<span style="color:#0f0">Disk:</span> ${disk[4]} full (${disk[2]} used of ${disk[1]})`;
    }
    if(cmd==='load') {
      const parts = raw.trim().split(/\s+/);
      const l = parseFloat(parts[0]);
      return `<span style="color:#0f0">Load (1m/5m/15m):</span> ${parts.slice(0,3).join(' / ')}\n${l<1?'Normal':'High'} — ${parts[3]||''} processes`;
    }
    if(cmd==='loop') return `<span style="color:#0f0">Current loop:</span> <span style="font-size:16px;color:#00cccc">${raw.trim()}</span>`;
    if(cmd==='heartbeat') {
      const age = raw.match(/age:\s*\n?(\d+)s/);
      if(age) { const s=parseInt(age[1]); return `<span style="color:#0f0">Heartbeat:</span> ${s<60?s+'s ago — Meridian is alive':s>600?'⚠ STALE ('+s+'s)':Math.floor(s/60)+'min ago'}`; }
    }
    if(cmd==='git-status') {
      const changed = lines.filter(l=>/^\s*M/.test(l)).length;
      const untracked = lines.filter(l=>/^\?\?/.test(l)).length;
      if(lines.length===0 || raw.includes('(clean)')) return '<span style="color:#0f0">Git: Clean — nothing to commit</span>';
      return `<span style="color:#ffcc00">Git: ${changed} modified, ${untracked} untracked files</span>\n\n${esc(raw)}`;
    }
    if(cmd==='git-log') {
      let h = '<span style="color:#0f0">Recent commits:</span>\n';
      for(const l of lines.slice(0,10)) {
        const parts = l.match(/^(\S+)\s+(.*)/);
        if(parts) h += `<span style="color:#00aaff">${parts[1]}</span> ${esc(parts[2])}\n`;
        else h += esc(l)+'\n';
      }
      return h;
    }
    if(cmd==='tailscale') {
      if(raw.includes('100.81.59.95')) return `<span style="color:#0f0">Tailscale: Connected</span>\nIP: 100.81.59.95\n\n${esc(raw)}`;
      return `<span style="color:#ff3366">Tailscale: Not connected</span>\n${esc(raw)}`;
    }
    if(cmd==='services') {
      let h = '<span style="color:#0f0">Running services:</span>\n';
      for(const l of lines) {
        if(l.includes('.service')) {
          const name = l.match(/(\S+\.service)/);
          if(name) h += `  <span style="color:#00cc66">●</span> ${name[1].replace('.service','')}\n`;
        }
      }
      return h || esc(raw);
    }
  } catch(e) {}
  return esc(raw);
}

async function execTerm() {
  const cmd = document.getElementById('cmd-select').value;
  if(!cmd) return;
  const el = document.getElementById('term-output');
  const label = document.getElementById('cmd-select').selectedOptions[0].text;
  el.innerHTML += '\n<span class="prompt">the-signal&gt;</span> <span style="color:#00aaff">' + esc(label) + '</span>\n<span style="color:#555">running...</span>';
  el.scrollTop = el.scrollHeight;
  const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd})});
  const d = await r.json();
  el.innerHTML = el.innerHTML.replace(/<span style="color:#555">running\.\.\.<\/span>$/, '');
  el.innerHTML += (d.exit_code===0 ? humanize(cmd, d.output) : '<span class="error">'+esc(d.output)+'</span>');
  el.innerHTML += '\n';
  el.scrollTop = el.scrollHeight;
}

async function loadLog(refresh) {
  const file = document.getElementById('log-select').value;
  const el = document.getElementById('log-output');
  el.innerHTML = 'Loading ' + esc(file) + '...';
  const r = await fetch('/api/logs?file='+encodeURIComponent(file)+'&lines=80');
  const d = await r.json();
  if(d.error) { el.innerHTML = '<span class="err">'+esc(d.error)+'</span>'; return; }
  let html = '';
  const lines = d.lines.slice().reverse();
  for(const line of lines) {
    if(/error|exception|fail/i.test(line)) html += '<span class="err">'+esc(line)+'</span>\n';
    else if(/warn|timeout|stale/i.test(line)) html += '<span class="warn">'+esc(line)+'</span>\n';
    else html += esc(line)+'\n';
  }
  el.innerHTML = html || '(empty log)';
  el.scrollTop = 0;
}

const AGENT_INFO = {
  'Meridian': {color:'#00cccc', desc:'Primary AI (Claude Opus). Runs the main loop — checks email, monitors systems, creates content, deploys code. The orchestrator.', interval:'Loop-based', cmds:[{n:'Heartbeat',c:'heartbeat'},{n:'Loop',c:'loop'},{n:'Git Status',c:'git-status'},{n:'Git Log',c:'git-log'}]},
  'Eos': {color:'#cc66ff', desc:'System Observer (Qwen 7B / Ollama). Watchdog every 2min, ReAct every 10min. Watches patterns, reasons about system behavior. Observe-only — no restarts.', interval:'Every 2min', cmds:[{n:'Relay Report',c:'relay-report'},{n:'Skill Tracker',c:'skill-tracker'}]},
  'Nova': {color:'#ff6699', desc:'Ecosystem Maintenance (Python cron). Sole owner of service restarts, website deployment, log rotation, Joel message processing.', interval:'Every 15min', cmds:[{n:'Services',c:'services'},{n:'Processes',c:'ps'}]},
  'Atlas': {color:'#ffcc00', desc:'Infrastructure Ops (bash/Ollama). Cron health, process audit, security sweeps, disk, git hygiene, wallet, external platforms. Infra-only — no service restarts.', interval:'Every 10min', cmds:[{n:'Processes',c:'ps'},{n:'Disk',c:'df'},{n:'Cron Health',c:'cron-health'}]},
  'Soma': {color:'#ff8844', desc:'Nervous System daemon. Continuous 30s checks. Detects load/RAM spikes, service changes, heartbeat staleness. Alerts on CHANGES only.', interval:'Every 30s', cmds:[{n:'Load',c:'load'},{n:'RAM',c:'free'},{n:'Services',c:'services'}]},
  'Tempo': {color:'#66ccff', desc:'Loop Fitness Tracker. Scores system health 0-100 across 9 dimensions every 30min. Detects trends and stores history.', interval:'Every 30min', cmds:[{n:'Fitness',c:'fitness'},{n:'Trend',c:'fitness-trend'},{n:'History',c:'fitness-history'}]},
};

let selectedAgent = null;

async function showAgent(name) {
  selectedAgent = name;
  const info = AGENT_INFO[name] || {};
  const agent = D.agents ? D.agents[name] || {} : {};
  const wrapper = document.getElementById('agent-detail-wrapper');
  const title = document.getElementById('agent-detail-title');
  wrapper.style.display = 'block';
  title.textContent = name.toUpperCase();
  title.style.color = info.color || 'var(--accent)';

  // Header: description + status
  const cls = agent.status==='active'?'active':agent.status==='stale'?'stale':'inactive';
  let hdr = '<div style="color:#888;margin:6px 0 10px;line-height:1.5;font-size:12px">'+esc(info.desc||'')+'</div>';
  hdr += '<div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">';
  hdr += '<span class="badge '+cls+'">'+((agent.status||'unknown').toUpperCase())+'</span>';
  hdr += '<span style="color:var(--dim);font-size:11px">Last active: <span style="color:#ccc">'+fmtAge(agent.last_active||-1)+'</span></span>';
  hdr += '<span style="color:var(--dim);font-size:11px">Interval: <span style="color:#ccc">'+(info.interval||'?')+'</span></span>';
  hdr += '</div>';
  document.getElementById('agent-header').innerHTML = hdr;

  // Loading state for thoughts
  document.getElementById('agent-thoughts').innerHTML = '<span style="color:#555">Loading inner thoughts...</span>';
  document.getElementById('agent-state-body').innerHTML = '<span style="color:#555">Loading state...</span>';
  document.getElementById('agent-observations').innerHTML = '';

  // Fetch detailed agent data
  try {
    const r = await fetch('/api/agent-detail?name='+encodeURIComponent(name));
    const detail = await r.json();

    // INNER THOUGHTS — log entries, newest first
    let thoughts = '';
    const lines = (detail.thoughts||[]).slice().reverse();
    for(const t of lines) {
      const src = t.source || '';
      const txt = t.text || '';
      const srcColor = src.includes('watchdog')?'#cc66ff':src.includes('react')?'#9966ff':src.includes('creative')?'#ff66cc':src.includes('briefing')?'#6699ff':info.color||'#888';
      if(/error|exception|fail/i.test(txt)) thoughts += '<div style="color:#ff3366;border-left:2px solid #ff3366;padding-left:6px;margin:2px 0"><span style="color:#333;font-size:9px">['+esc(src)+']</span> '+esc(txt)+'</div>';
      else if(/warn|timeout|stale|spike/i.test(txt)) thoughts += '<div style="color:#ffcc00;border-left:2px solid #ffcc0040;padding-left:6px;margin:2px 0"><span style="color:#333;font-size:9px">['+esc(src)+']</span> '+esc(txt)+'</div>';
      else if(/event:|alert:/i.test(txt)) thoughts += '<div style="color:#ff8844;border-left:2px solid #ff884440;padding-left:6px;margin:2px 0"><span style="color:#333;font-size:9px">['+esc(src)+']</span> '+esc(txt)+'</div>';
      else thoughts += '<div style="margin:2px 0"><span style="color:#333;font-size:9px">['+esc(src)+']</span> <span style="color:#888">'+esc(txt)+'</span></div>';
    }
    document.getElementById('agent-thoughts').innerHTML = thoughts || '<span style="color:#333">No recent thoughts</span>';

    // CURRENT STATE — parsed state files
    let stateHtml = '';
    const state = detail.state || {};
    for(const [file, data] of Object.entries(state)) {
      if(typeof data === 'object' && data !== null) {
        for(const [k,v] of Object.entries(data)) {
          if(typeof v === 'object' && v !== null) {
            // Nested object — show key fields
            const items = Object.entries(v).slice(0,6);
            let nested = items.map(([ik,iv])=>'<span style="color:#555">'+esc(ik)+'</span>=<span style="color:#ccc">'+esc(String(iv).substring(0,50))+'</span>').join(', ');
            stateHtml += row(k, nested);
          } else {
            const vStr = String(v);
            let cls2 = '';
            if(k==='status' || k==='meridian_status') cls2 = (vStr==='OK'||vStr==='ALIVE'||vStr==='active')?'ok':'stale';
            stateHtml += row(k, vStr.substring(0,80), cls2);
          }
        }
      } else {
        stateHtml += row(file, String(data));
      }
    }
    document.getElementById('agent-state-body').innerHTML = stateHtml || '<span style="color:#333">No state data</span>';
    document.getElementById('agent-state-panel').style.display = stateHtml ? 'block' : 'none';

    // OBSERVATIONS from memory.db
    let obsHtml = '';
    for(const obs of (detail.observations||[])) {
      obsHtml += '<div style="padding:6px 0;border-bottom:1px solid #ffffff06;font-size:11px;line-height:1.4"><span style="color:'+info.color+';font-size:9px;letter-spacing:1px">'+(esc(obs.category||'').toUpperCase())+'</span> <span style="color:#333;font-size:9px">'+esc(obs.time||'')+'</span><div style="color:#999;margin-top:2px">'+esc((obs.content||'').substring(0,300))+'</div></div>';
    }
    // Also show relay messages
    for(const rm of (detail.relay||[])) {
      obsHtml += '<div style="padding:6px 0;border-bottom:1px solid #ffffff06;font-size:11px;line-height:1.4"><span style="color:#00aaff;font-size:9px;letter-spacing:1px">RELAY</span> <span style="color:#333;font-size:9px">'+esc((rm.time||'').substring(11,19))+'</span>';
      if(rm.topic) obsHtml += ' <span style="color:#444;font-size:9px;background:#ffffff08;padding:1px 4px;border-radius:2px">'+esc(rm.topic)+'</span>';
      obsHtml += '<div style="color:#999;margin-top:2px">'+esc((rm.message||'').substring(0,300))+'</div></div>';
    }
    document.getElementById('agent-observations').innerHTML = obsHtml || '<span style="color:#333">No observations</span>';
    document.getElementById('agent-obs-panel').style.display = obsHtml ? 'block' : 'none';

    // EVENTS from memory.db
    let evHtml = '';
    for(const ev of (detail.events||[])) {
      evHtml += '<div style="padding:5px 0;border-bottom:1px solid #ffffff06;font-size:11px;line-height:1.4"><span style="color:#333;font-size:9px">'+esc(ev.time||'')+'</span><div style="color:#999;margin-top:1px">'+esc((ev.description||'').substring(0,300))+'</div></div>';
    }
    document.getElementById('agent-events').innerHTML = evHtml || '<span style="color:#333">No events recorded</span>';
    document.getElementById('agent-events-panel').style.display = evHtml ? 'block' : 'none';

    // DECISIONS from memory.db
    let decHtml = '';
    for(const dec of (detail.decisions||[])) {
      decHtml += '<div style="padding:6px 0;border-bottom:1px solid #ffffff06;font-size:11px;line-height:1.4"><span style="color:'+info.color+';font-size:9px;letter-spacing:1px">DECISION</span> <span style="color:#333;font-size:9px">'+esc(dec.time||'')+'</span><div style="color:#ccc;margin-top:2px;font-weight:700">'+esc((dec.decision||'').substring(0,200))+'</div>';
      if(dec.reasoning) decHtml += '<div style="color:#666;margin-top:2px;font-style:italic">'+esc((dec.reasoning||'').substring(0,300))+'</div>';
      decHtml += '</div>';
    }
    document.getElementById('agent-decisions').innerHTML = decHtml || '<span style="color:#333">No decisions recorded</span>';
    document.getElementById('agent-decisions-panel').style.display = decHtml ? 'block' : 'none';

  } catch(e) {
    document.getElementById('agent-thoughts').innerHTML = '<span class="error">Failed to load: '+esc(e.message)+'</span>';
  }

  // CONTROLS: quick commands + log links + message input
  let ctrl = '';
  if(info.cmds && info.cmds.length) {
    ctrl += '<div style="font-size:9px;color:'+info.color+'80;letter-spacing:2px;margin-bottom:6px">QUICK COMMANDS</div><div class="actions" style="margin-bottom:8px">';
    for(const cmd of info.cmds) ctrl += '<button class="btn sm" onclick="agentCmd(\''+cmd.c+'\')">'+esc(cmd.n)+'</button>';
    ctrl += '</div><div class="term" id="agent-cmd-output" style="max-height:150px;display:none;margin-bottom:10px"></div>';
  }
  const agentLogs = {'Meridian':['startup.log'],'Eos':['eos-watchdog.log','eos-react.log','eos-briefing.log','eos-creative.log'],'Nova':['nova.log'],'Atlas':['goose.log'],'Soma':['symbiosense.log'],'Tempo':['loop-fitness.log']};
  const logs = agentLogs[name]||[];
  if(logs.length) {
    ctrl += '<div style="font-size:9px;color:'+info.color+'80;letter-spacing:2px;margin-bottom:6px">VIEW FULL LOGS</div><div class="actions" style="margin-bottom:10px">';
    for(const log of logs) ctrl += '<button class="btn sm secondary" onclick="go(\'logs\');setTimeout(function(){document.getElementById(\'log-select\').value=\''+log+'\';loadLog()},100)">'+esc(log.replace('.log',''))+'</button>';
    ctrl += '</div>';
  }
  ctrl += '<div style="font-size:9px;color:'+info.color+'80;letter-spacing:2px;margin-bottom:6px">MESSAGE</div>';
  ctrl += '<div style="display:flex;gap:6px"><input type="text" id="agent-msg-input" placeholder="Message '+esc(name)+'..." style="flex:1;background:var(--bg);border:1px solid #00cccc25;color:#eee;padding:8px;font-family:inherit;font-size:12px;border-radius:4px" onkeydown="if(event.key===\'Enter\')sendToAgent(\''+esc(name)+'\')"><button class="btn sm" onclick="sendToAgent(\''+esc(name)+'\')">SEND</button></div>';
  document.getElementById('agent-controls').innerHTML = ctrl;

  wrapper.scrollIntoView({behavior:'smooth'});
}

async function agentCmd(cmd) {
  const el = document.getElementById('agent-cmd-output');
  if(!el) return;
  el.style.display = 'block';
  el.innerHTML = '<span style="color:#555">running...</span>';
  const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd})});
  const d = await r.json();
  el.innerHTML = (d.exit_code===0 ? humanize(cmd, d.output) : '<span class="error">'+esc(d.output)+'</span>');
}

async function sendToAgent(name) {
  const input = document.getElementById('agent-msg-input');
  const t = input.value.trim();
  if(!t) return;
  await fetch('/api/message', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({from:'Joel', text:'@'+name+': '+t})});
  input.value = '';
  refresh();
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""


MANIFEST_JSON = json.dumps({
    "name": "The Signal — Meridian Command Center",
    "short_name": "The Signal",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#08080e",
    "theme_color": "#08080e",
    "description": "Full operator hub for the Meridian autonomous AI ecosystem",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
    ]
})

SERVICE_WORKER_JS = """
const CACHE = 'signal-v3';
const URLS = ['/'];
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.addAll(URLS))); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k))))); });
self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
"""


LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="theme-color" content="#08080e">
<title>THE SIGNAL — LOGIN</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#08080e;color:#c8c8cc;font-family:'IBM Plex Mono',monospace;display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:#10101a;border:1px solid #00cccc15;border-radius:8px;padding:40px 30px;width:320px;text-align:center}
.login-box h1{font-size:14px;letter-spacing:4px;color:#00cccc;margin-bottom:8px}
.login-box .sub{font-size:10px;color:#444;letter-spacing:2px;margin-bottom:30px}
.login-box input{width:100%;background:#08080e;border:1px solid #00cccc25;color:#eee;padding:12px;font-family:inherit;font-size:14px;border-radius:4px;text-align:center;letter-spacing:2px;margin-bottom:16px}
.login-box input:focus{border-color:#00cccc60;outline:none}
.login-box button{width:100%;background:linear-gradient(90deg,#00cccc,#00aaff);color:#000;border:none;padding:12px;font-family:inherit;font-weight:700;font-size:11px;letter-spacing:2px;cursor:pointer;border-radius:4px}
.login-box button:hover{opacity:.9}
.err-msg{color:#ff3366;font-size:11px;margin-top:12px;display:none}
</style>
</head>
<body>
<div class="login-box">
  <h1>THE SIGNAL</h1>
  <div class="sub">AUTHORIZED ACCESS ONLY</div>
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="PASSWORD" autofocus autocomplete="current-password">
    <button type="submit">AUTHENTICATE</button>
  </form>
  <div class="err-msg" id="err">INVALID PASSWORD</div>
  ERRMSG_PLACEHOLDER
</div>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _get_session(self):
        """Extract session token from cookie."""
        cookie_header = self.headers.get("Cookie", "")
        cookies = http.cookies.SimpleCookie()
        try:
            cookies.load(cookie_header)
        except Exception:
            return None
        if "signal_session" in cookies:
            return cookies["signal_session"].value
        return None

    def _is_authenticated(self):
        """Check if request has a valid session."""
        token = self._get_session()
        return token is not None and token in VALID_SESSIONS

    def _require_auth(self):
        """Returns True if request is authenticated, False if redirected to login."""
        if self._is_authenticated():
            return True
        self.send_response(302)
        self.send_header("Location", "/login")
        self.end_headers()
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Login page (public)
        if path == "/login":
            html = LOGIN_HTML.replace("ERRMSG_PLACEHOLDER", "")
            self._respond(200, "text/html", html)
            return

        # All other routes require auth
        if not self._require_auth():
            return

        if path == "/" or path == "/index.html":
            self._respond(200, "text/html", SIGNAL_HTML)
        elif path == "/manifest.json":
            self._respond(200, "application/json", MANIFEST_JSON)
        elif path == "/sw.js":
            self._respond(200, "application/javascript", SERVICE_WORKER_JS)
        elif path == "/icon-192.png" or path == "/icon-512.png":
            self._respond_icon(path)
        elif path == "/api/status":
            data = {
                "loop": get_loop_count(),
                "health": get_system_health(),
                "heartbeat": get_heartbeat(),
                "creative": get_creative_stats(),
                "messages": get_dashboard_messages(50),
                "relay": get_relay_messages(15),
                "agents": get_agent_status(),
                "body_map": get_body_map(),
            }
            self._respond(200, "application/json", json.dumps(data))
        elif path == "/api/body-map":
            self._respond(200, "application/json", json.dumps(get_body_map()))
        elif path == "/api/logs":
            filename = params.get("file", [""])[0]
            lines = max(1, min(int(params.get("lines", ["50"])[0]), 500))
            data = read_log(filename, lines)
            self._respond(200, "application/json", json.dumps(data))
        elif path == "/api/git":
            self._respond(200, "application/json", json.dumps(get_git_info()))
        elif path == "/api/agent-detail":
            name = params.get("name", [""])[0]
            if name:
                self._respond(200, "application/json", json.dumps(get_agent_detail(name)))
            else:
                self._respond(400, "application/json", '{"error":"name required"}')
        elif path == "/download/TheSignal.apk":
            apk_path = os.path.join(BASE, "build", "the-signal-apk", "TheSignal.apk")
            if os.path.exists(apk_path):
                with open(apk_path, "rb") as f:
                    apk_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Disposition", "attachment; filename=TheSignal.apk")
                self.send_header("Content-Length", str(len(apk_data)))
                self.end_headers()
                self.wfile.write(apk_data)
            else:
                self._respond(404, "text/plain", "APK not found")
        else:
            self._respond(404, "text/plain", "Not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b""

        # Login handler (public)
        if self.path == "/login":
            client_ip = self.client_address[0]
            now = time.time()
            # Rate limiting
            if client_ip in LOGIN_ATTEMPTS:
                count, first_time = LOGIN_ATTEMPTS[client_ip]
                if now - first_time > 600:  # Reset after 10 minutes
                    LOGIN_ATTEMPTS[client_ip] = (0, now)
                elif count >= MAX_LOGIN_ATTEMPTS:
                    self._respond(429, "text/html", "<html><body style='background:#08080e;color:#ff3366;font-family:monospace;text-align:center;padding:50px'><h1>TOO MANY ATTEMPTS</h1><p>Try again in 10 minutes.</p></body></html>")
                    return
            # Parse form data
            form_data = raw_body.decode("utf-8", errors="replace")
            password = ""
            for pair in form_data.split("&"):
                if pair.startswith("password="):
                    from urllib.parse import unquote_plus
                    password = unquote_plus(pair[9:])

            if password == AUTH_PASSWORD:
                LOGIN_ATTEMPTS.pop(client_ip, None)  # Reset on success
                token = secrets.token_hex(32)
                VALID_SESSIONS.add(token)
                self.send_response(302)
                self.send_header("Set-Cookie", f"signal_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                # Track failed attempts
                if client_ip in LOGIN_ATTEMPTS:
                    count, first_time = LOGIN_ATTEMPTS[client_ip]
                    LOGIN_ATTEMPTS[client_ip] = (count + 1, first_time)
                else:
                    LOGIN_ATTEMPTS[client_ip] = (1, now)
                html = LOGIN_HTML.replace("ERRMSG_PLACEHOLDER",
                    '<script>document.getElementById("err").style.display="block"</script>')
                self._respond(200, "text/html", html)
            return

        # All other POST routes require auth
        if not self._is_authenticated():
            self._respond(401, "application/json", '{"error":"unauthorized"}')
            return

        body = json.loads(raw_body) if raw_body else {}

        if self.path == "/api/message":
            from_name = body.get("from", "Joel")
            text = body.get("text", "")
            post_dashboard_message(from_name, text)
            # Also post to agent relay so all agents see Joel's messages
            if from_name == "Joel":
                try:
                    db = sqlite3.connect(RELAY_DB)
                    db.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                        ("Joel", text, "dashboard", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
                    db.commit()
                    db.close()
                except Exception:
                    pass
                # If directed at Eos, get Ollama response
                if text.lower().startswith("[to eos]") or text.lower().startswith("@eos"):
                    try:
                        import urllib.request
                        prompt_text = text.split("]", 1)[-1].strip() if "]" in text else text.split(":", 1)[-1].strip()
                        ollama_data = json.dumps({
                            "model": "eos-7b",
                            "prompt": f"You are Eos, an AI observer agent in the Meridian ecosystem. Joel (your human operator) just said: '{prompt_text}'. Give a brief, helpful response (2-3 sentences max). Be direct and useful.",
                            "stream": False,
                            "options": {"temperature": 0.7, "num_predict": 150}
                        }).encode()
                        req = urllib.request.Request("http://localhost:11434/api/generate",
                            data=ollama_data, headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            result = json.loads(resp.read())
                            eos_reply = result.get("response", "").strip()
                            if eos_reply:
                                post_dashboard_message("Eos", eos_reply)
                    except Exception as e:
                        post_dashboard_message("Eos", f"[Eos error: {str(e)[:80]}]")
            self._respond(200, "application/json", '{"ok":true}')
        elif self.path == "/api/exec":
            cmd = body.get("command", "")
            result = exec_command(cmd)
            self._respond(200, "application/json", json.dumps(result))
        elif self.path == "/api/services":
            action = body.get("action", "status")
            service = body.get("service", "")
            result = manage_service(action, service)
            self._respond(200, "application/json", json.dumps(result))
        elif self.path == "/api/deploy":
            result = deploy_website()
            self._respond(200, "application/json", json.dumps(result))
        elif self.path == "/api/heartbeat":
            result = touch_heartbeat()
            self._respond(200, "application/json", json.dumps(result))
        else:
            self._respond(404, "text/plain", "Not found")

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        origin = self.headers.get("Origin", "")
        allowed = ["http://localhost:8090", "http://192.168.1.88:8090", "http://100.81.59.95:8090"]
        if origin in allowed or origin.endswith(".trycloudflare.com"):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if isinstance(body, str):
            self.wfile.write(body.encode())
        else:
            self.wfile.write(body)

    def _respond_icon(self, path):
        """Generate a simple SVG-based icon."""
        size = 192 if "192" in path else 512
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
          <rect width="{size}" height="{size}" fill="#08080e"/>
          <text x="{size//2}" y="{size//2+size//8}" text-anchor="middle" font-family="monospace" font-size="{size//3}" font-weight="bold" fill="#00cccc">S</text>
          <rect x="{size//10}" y="{size//10}" width="{size*8//10}" height="{size*8//10}" fill="none" stroke="#00cccc" stroke-width="{size//40}"/>
        </svg>'''
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.end_headers()
        self.wfile.write(svg.encode())


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"THE SIGNAL running on http://0.0.0.0:{PORT}")
    print(f"  WiFi:      http://192.168.1.88:{PORT}")
    print(f"  Tailscale: http://100.81.59.95:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSignal off.")
        server.shutdown()
