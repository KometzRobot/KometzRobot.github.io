#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v46

Loop 5750+ update (v46 — UI fixes per Joel dashboard feedback):
- Fixed duplicate Disk display in dashboard (removed from Vitals, Soma has full gauge)
- Radar grid: taller canvases, better expand, so project radars don't get cut off
- Toast system: robust non-stacking popups replace yellow text for actions
- Scroll wheel: comprehensive binding to ALL scrollable areas including child widgets
- Visuals: deferred initial draw on map event so canvases render on first show
- Layout: scrollable canvas width tracks window resize (dash + inner world)
- Horizontal scroll: Shift+scroll for side-scrolling, click-drag panning on panels
- Previous v44/v45 polish preserved
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont, filedialog
import threading
import json
import os
import sys
import re
import time
import glob
import subprocess
import sqlite3
import imaplib
import email
import email.header
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import urllib.request
import math

# Load .env credentials
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from load_env import load_env
    load_env()
except ImportError:
    pass

# ── CONFIG ────────────────────────────────────────────────────────
BASE = "/home/joel/autonomous-ai"
WAKE = os.path.join(BASE, "wake-state.md")
HB = os.path.join(BASE, ".heartbeat")
EOS_MEM = os.path.join(BASE, "eos-memory.json")
EOS_OBS = os.path.join(BASE, "eos-observations.md")
EOS_CREATIVE = os.path.join(BASE, "eos-creative-log.md")
RELAY_DB = os.path.join(BASE, "data", "relay.db")
AGENT_RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "data", "memory.db")
NOVA_STATE = os.path.join(BASE, ".nova-state.json")
DASH_MSG = os.path.join(BASE, ".dashboard-messages.json")
LOOP_FILE = os.path.join(BASE, ".loop-count")

PINNED_FILE = os.path.join(BASE, ".pinned-files.json")

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1144
SMTP_HOST, SMTP_PORT = "127.0.0.1", 1026
CRED_USER = os.environ.get("CRED_USER", os.environ.get("MERIDIAN_EMAIL_USER", "kometzrobot@proton.me"))
CRED_PASS = os.environ.get("CRED_PASS", os.environ.get("MERIDIAN_EMAIL_PASS", ""))
JOEL = "jkometz@hotmail.com"

OLLAMA = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"

# ── COLORS (Material Dark theme — "Android app, not hacker UI") ──
BG = "#121212"
HEADER_BG = "#1e1e1e"
PANEL = "#2d2d2d"
PANEL2 = "#333333"
INPUT_BG = "#1a1a1a"
BORDER = "#3d3d3d"
ACCENT = "#2c2c2c"
ACTIVE_BG = "#424242"
FG = "#e0e0e0"
DIM = "#757575"
BRIGHT = "#fafafa"
GREEN = "#4caf50"
GREEN2 = "#388e3c"
CYAN = "#29b6f6"
CYAN2 = "#0288d1"
AMBER = "#ff9800"       # Soma — warm orange, nervous system energy
AMBER2 = "#f57c00"
RED = "#ef5350"
GOLD = "#ffca28"        # Eos — bright gold, sensory warmth
WHITE = "#fafafa"
PURPLE = "#ab47bc"      # Nova — vivid purple, immune defense
PINK = "#ec407a"        # Hermes — hot pink, messenger
TEAL = "#26a69a"        # Atlas — teal, structural/skeletal
BLUE = "#42a5f5"        # Tempo — consistent blue, endocrine rhythm

# Greek/mythological display names (DB names unchanged for compatibility)
GREEK_NAMES = {
    "Sentinel": "Argus",       # 100-eyed giant — security watchman
    "Nova": "Athena",          # goddess of strategy — immune defense
    "Coordinator": "Apollo",   # god of order — coordination
    "Predictive": "Pythia",    # Oracle of Delphi — prediction
    "SelfImprove": "Prometheus", # titan of improvement — self-optimization
    "Homecoming": "Nostos",    # Greek concept of homeward journey
    "Loop Optimizer": "Kairos", # god of opportune moment — timing
    "Push Status": "Iris",     # rainbow goddess — messenger between worlds
    "Cloudflare Tunnel": "Bifrost", # Norse rainbow bridge (honorary)
    "The Chorus": "Mousai",    # the Muses — voices of inspiration
}

def greek(name):
    """Return Greek display name if available, else original."""
    return GREEK_NAMES.get(name, name)


# ── DATA FUNCTIONS ───────────────────────────────────────────────
def _read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return default

def heartbeat_age():
    try:
        return time.time() - os.path.getmtime(HB)
    except Exception:
        return float('inf')

def loop_num():
    try:
        return int(_read(LOOP_FILE, "0").strip())
    except Exception:
        return 0

def sys_stats():
    s = {}
    try:
        l = os.getloadavg()
        s['load'] = f"{l[0]:.2f}"
        s['load_v'] = l[0]
    except Exception:
        s['load'] = '?'
        s['load_v'] = 0
    try:
        with open('/proc/meminfo') as f:
            lns = f.readlines()
        t = int(lns[0].split()[1]) / 1048576
        a = int(lns[2].split()[1]) / 1048576
        u = t - a
        s['ram'] = f"{u:.1f}/{t:.1f}G"
        s['ram_p'] = u / t * 100
    except Exception:
        s['ram'] = '?'
        s['ram_p'] = 0
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
        s['up'] = f"{int(secs/3600)}h {int((secs%3600)/60)}m"
        s['up_s'] = secs
    except Exception:
        s['up'] = '?'
        s['up_s'] = 0
    try:
        r = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=2)
        p = r.stdout.strip().split('\n')[1].split()
        s['disk'] = f"{p[2]}/{p[1]} ({p[4]})"
        s['disk_p'] = int(p[4].rstrip('%'))
    except Exception:
        s['disk'] = '?'
        s['disk_p'] = 0
    return s

def services():
    checks = {
        "Proton Bridge": "proton-bridge",
        "Ollama": "ollama serve",
        "Hub v2": "hub-v2.py",
        "The Chorus": "the-chorus.py",
        "Cloudflare Tunnel": "cloudflared",
        "Soma": "symbiosense.py",
        "Command Center": "command-center.py",
    }
    r = {}
    for name, pat in checks.items():
        try:
            res = subprocess.run(['pgrep', '-f', pat], capture_output=True, timeout=2)
            r[name] = res.returncode == 0
        except Exception:
            r[name] = False
    return r

def cron_ok():
    checks = {
        "Eos Watchdog": (os.path.join(BASE, ".eos-watchdog-state.json"), 600),
        "Push Status": (os.path.join(BASE, "logs", "push-live-status.log"), 600),
        "Nova": (NOVA_STATE, 1200),
        "Atlas": (os.path.join(BASE, "goose.log"), 1200),
        "Tempo": (os.path.join(BASE, "logs", "loop-fitness.log"), 2400),
        "Sentinel": (os.path.join(BASE, "logs", "sentinel-gatekeeper.log"), 900),
        "Coordinator": (os.path.join(BASE, ".coordinator-state.json"), 900),
        "Predictive": (os.path.join(BASE, ".predictive-state.json"), 900),
        "SelfImprove": (os.path.join(BASE, ".self-improvement-state.json"), 900),
    }
    r = {}
    for name, (path, thresh) in checks.items():
        try:
            r[name] = (time.time() - os.path.getmtime(path)) < thresh
        except Exception:
            r[name] = False
    return r

def creative_counts():
    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        c.execute("SELECT type, COUNT(*), SUM(word_count) FROM creative GROUP BY type")
        counts = {row[0]: (row[1], row[2] or 0) for row in c.fetchall()}
        c.execute("SELECT SUM(word_count) FROM creative")
        total_words = c.fetchone()[0] or 0
        conn.close()
        p = counts.get("poem", (0, 0))[0]
        j = counts.get("journal", (0, 0))[0]
        cc = counts.get("cogcorp", (0, 0))[0]
        g = counts.get("game", (0, 0))[0]
        return p, j, cc, g, total_words
    except Exception:
        p = len(glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md")))
        j = len(glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md")))
        cc = len(glob.glob(os.path.join(BASE, "creative", "cogcorp", "CC-*.md")))
        g = len(glob.glob(os.path.join(BASE, "creative", "games", "*.html")))
        return p, j, cc, g, 0

def activity_heatmap():
    """Get message counts by day-of-week x hour for a 7x24 heatmap grid."""
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT timestamp FROM agent_messages WHERE timestamp > datetime('now', '-7 days')")
        grid = [[0]*24 for _ in range(7)]
        for (ts,) in c.fetchall():
            try:
                dt = datetime.fromisoformat(ts.replace('+00:00', '').replace('Z', ''))
                grid[dt.weekday()][dt.hour] += 1
            except Exception:
                pass
        conn.close()
        return grid
    except Exception:
        return [[0]*24 for _ in range(7)]

def agent_message_counts_24h():
    """Get per-agent message counts in last 24 hours."""
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT agent, COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-24 hours') GROUP BY agent ORDER BY COUNT(*) DESC")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def recent_emails(n=8):
    try:
        m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        m.login(CRED_USER, CRED_PASS)
        m.select('INBOX')
        _, d = m.search(None, 'ALL')
        ids = d[0].split() if d[0] else []
        total = len(ids)
        results = []
        for uid in ids[-n:]:
            _, md = m.fetch(uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if md[0]:
                h = email.message_from_bytes(md[0][1])
                frm = email.header.decode_header(h.get('From', ''))[0]
                frm = frm[0].decode() if isinstance(frm[0], bytes) else str(frm[0])
                nm = re.match(r'"?([^"<]+)"?\s*<', frm)
                name = nm.group(1).strip() if nm else frm[:20]
                subj = email.header.decode_header(h.get('Subject', ''))[0]
                subj = subj[0].decode() if isinstance(subj[0], bytes) else str(subj[0])
                results.append((name, str(subj)[:55]))
        m.close()
        m.logout()
        return results[::-1], total
    except Exception:
        return [], 0

def agent_relay_info(n=15):
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT agent, message, timestamp FROM agent_messages ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        conn.close()
        return rows, total
    except Exception:
        return [], 0

def dashboard_messages(n=20):
    try:
        with open(DASH_MSG) as f:
            data = json.load(f)
        # Handle both formats: plain list or dict with 'messages' key
        msgs = data.get('messages', data) if isinstance(data, dict) else data
        if not isinstance(msgs, list):
            return []
        return msgs[-n:] if len(msgs) > n else msgs
    except Exception:
        return []

def last_edited_files(n=15):
    """Get the most recently modified files in the project."""
    all_files = []
    scan_dirs = [BASE, os.path.join(BASE, "website"), os.path.join(BASE, "scripts"),
                 os.path.join(BASE, "tools"), os.path.join(BASE, "configs"),
                 os.path.join(BASE, "creative"), os.path.join(BASE, "data")]
    for ext in ['*.md', '*.py', '*.html', '*.json', '*.js', '*.sh']:
        for d in scan_dirs:
            all_files.extend(glob.glob(os.path.join(d, ext)))
    # Sort by mtime, newest first
    all_files = sorted(all_files, key=os.path.getmtime, reverse=True)
    results = []
    seen = set()
    for fp in all_files:
        bn = os.path.basename(fp)
        if bn.startswith('.') or bn in seen:
            continue
        seen.add(bn)
        mtime = datetime.fromtimestamp(os.path.getmtime(fp))
        age = time.time() - os.path.getmtime(fp)
        if age < 60:
            ago = f"{int(age)}s ago"
        elif age < 3600:
            ago = f"{int(age/60)}m ago"
        elif age < 86400:
            ago = f"{int(age/3600)}h ago"
        else:
            ago = mtime.strftime("%b %d")
        results.append((bn, ago, fp))
        if len(results) >= n:
            break
    return results

# ── Agent attribution for files ──
AGENT_FILE_PATTERNS = {
    "Meridian": ["command-center", "wake-state", "awakening-plan", "special-notes", "the-signal",
                 "mcp-tools", "mcp-email", "start-claude", "index.html", "nft-gallery"],
    "Eos": ["eos-", "eos_"],
    "Nova": ["nova", "watchdog-status"],
    "Atlas": ["atlas-runner", "atlas-runner.log"],
    "Soma": ["symbiosense", "symbio"],
    "Tempo": ["loop-fitness", "loop-optimizer"],
}

def guess_agent(filename):
    """Guess which agent likely owns/produces a file."""
    fn = filename.lower()
    for agent, patterns in AGENT_FILE_PATTERNS.items():
        for p in patterns:
            if p in fn:
                return agent
    # Generic files — guess by content type
    if fn.endswith('.log'):
        return None  # logs are ambiguous
    if fn.startswith(('poem-', 'journal-', 'cogcorp-')):
        return "Meridian"
    return None

AGENT_COLORS_MAP = {
    "Meridian": GREEN, "Eos": GOLD, "Nova": PURPLE,
    "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE, "Hermes": PINK,
}

def get_cross_references(filepath):
    """Get cross-references for a file: relay mentions, git commits, related tasks."""
    bn = os.path.basename(filepath)
    refs = {"relay": [], "commits": [], "tasks": []}
    # 1. Search relay DB for mentions
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT agent, message, timestamp FROM agent_messages WHERE message LIKE ? ORDER BY timestamp DESC LIMIT 5",
                  (f"%{bn}%",))
        for agent, msg, ts in c.fetchall():
            refs["relay"].append({"agent": agent, "msg": msg[:120], "ts": ts})
        conn.close()
    except Exception:
        pass
    # 2. Git log for this file (last 5 commits)
    try:
        out = subprocess.check_output(
            ["git", "log", "--oneline", "-5", "--", filepath],
            cwd=BASE, timeout=3, stderr=subprocess.DEVNULL
        ).decode().strip()
        for line in out.split("\n"):
            if line.strip():
                refs["commits"].append(line.strip())
    except Exception:
        pass
    # 3. Search awakening-plan.md for references
    try:
        with open(os.path.join(BASE, "docs", "awakening-plan.md")) as f:
            plan = f.read()
        # Search for filename or common variations
        search_terms = [bn]
        stem = os.path.splitext(bn)[0]
        if stem not in search_terms:
            search_terms.append(stem)
        for line in plan.split("\n"):
            for term in search_terms:
                if term.lower() in line.lower() and line.strip():
                    clean = line.strip().lstrip("-[] x#").strip()
                    if clean and clean not in refs["tasks"]:
                        refs["tasks"].append(clean[:100])
                    break
    except Exception:
        pass
    return refs

def load_pinned():
    """Load pinned/favorite file paths."""
    try:
        with open(PINNED_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_pinned(paths):
    """Save pinned file paths."""
    with open(PINNED_FILE, 'w') as f:
        json.dump(paths[:20], f)  # max 20 pinned

def imap_port_listening():
    """Check if IMAP port is actually accepting connections."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((IMAP_HOST, IMAP_PORT))
        s.close()
        return True
    except Exception:
        return False

def strip_html(text):
    """Strip HTML tags and decode entities for email display."""
    if not text:
        return ""
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    # Convert common block tags to newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.I)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.I)
    text = re.sub(r'<(p|div|tr|li|h[1-6])[^>]*>', '\n', text, flags=re.I)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def eos_obs(n=6):
    lines = [l.strip('- ').strip() for l in _read(EOS_OBS).split('\n') if l.startswith('- [')]
    return lines[-n:][::-1]

# ── SEND EMAIL ────────────────────────────────────────────────────
def send_email(to, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = CRED_USER
        msg['To'] = to
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        s.starttls()
        s.login(CRED_USER, CRED_PASS)
        s.sendmail(CRED_USER, to, msg.as_string())
        s.quit()
        return True
    except Exception as e:
        return str(e)

# ── DASHBOARD MESSAGE ─────────────────────────────────────────────
def post_dashboard_msg(text, sender="Joel", topic=""):
    try:
        msgs = dashboard_messages(500)
    except Exception:
        msgs = []
    entry = {"from": sender, "text": text, "time": datetime.now().strftime("%H:%M:%S")}
    if topic:
        entry["topic"] = topic
    msgs.append(entry)
    try:
        with open(DASH_MSG, 'w') as f:
            json.dump({"messages": msgs}, f)
    except Exception:
        pass

# ── EOS QUERY ─────────────────────────────────────────────────────
AGENT_IDENTITIES = {
    "Eos": {
        "ollama": True,
        "system": None,  # uses eos-memory.json identity
    },
    "Atlas": {
        "ollama": True,
        "system": (
            "You are Atlas, the infrastructure ops agent for Meridian's autonomous AI system. "
            "You handle cron health, process audits, security sweeps, disk management, git hygiene, "
            "and wallet monitoring. You are NOT Eos. Your name is Atlas. Respond concisely."
        ),
    },
    "Nova": {
        "ollama": False,
        "relay_msg": "Joel sent a message via Command Center chat",
    },
    "Soma": {
        "ollama": False,
        "relay_msg": "Joel sent a message via Command Center chat",
    },
    "Tempo": {
        "ollama": False,
        "relay_msg": "Joel sent a message via Command Center chat",
    },
    "Meridian": {
        "ollama": False,
        "dashboard": True,
    },
    "Hermes": {
        "ollama": True,
        "system": (
            "You are Hermes, the 7th agent in Meridian's autonomous AI system. "
            "You are the Messenger — you handle external communications via Discord, Nostr, and other channels. "
            "Built on OpenClaw with local Ollama (qwen2.5:7b). You bridge the relay to the outside world. "
            "Respond concisely."
        ),
    },
}


def query_eos(prompt, speaker="Joel"):
    return query_agent("Eos", prompt, speaker)


def query_agent(agent_name, prompt, speaker="Joel"):
    info = AGENT_IDENTITIES.get(agent_name, {})

    # Agents that use Ollama (Eos, Atlas) — instant response
    if info.get("ollama"):
        system_prompt = info.get("system")
        if system_prompt:
            ctx = system_prompt + "\n"
        else:
            # Load Eos memory for identity
            try:
                with open(EOS_MEM) as f:
                    mem = json.load(f)
            except Exception:
                mem = {}
            ident = mem.get("identity", {})
            facts = mem.get("core_facts", [])[:5]
            mood = mem.get("emotional_baseline", {}).get("current_mood", "calm")
            ctx = f"You are {ident.get('name', 'Eos')}, {ident.get('role', 'a local AI')}. Mood: {mood}\n"
            if facts:
                ctx += "\n".join(f"- {f}" for f in facts) + "\n"

        full = f"[MEMORY]\n{ctx}\n[{speaker}]: {prompt}"
        data = json.dumps({
            "model": EOS_MODEL, "prompt": full, "stream": False,
            "options": {"temperature": 0.8, "num_predict": 400}
        }).encode()
        req = urllib.request.Request(OLLAMA, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("response", "").strip()

    # Agents that use relay (Nova, Soma, Tempo) — async, post message
    if not info.get("dashboard"):
        try:
            import sqlite3
            conn = sqlite3.connect(AGENT_RELAY_DB)
            conn.execute(
                "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                ("Joel", f"[to {agent_name}] {prompt}", "chat",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        return f"[Message sent to {agent_name} via relay — they'll respond next cycle]"

    # Meridian — post to dashboard
    post_dashboard_msg(f"[to {agent_name}] {prompt}", speaker)
    return f"[Message posted to dashboard for {agent_name}]"


# ── ACTION BUTTONS ────────────────────────────────────────────────
def action_touch_heartbeat():
    try:
        open(HB, 'a').close()
        os.utime(HB, None)
        return "Heartbeat touched"
    except Exception as e:
        return f"Failed: {e}"

def action_deploy_website():
    try:
        # Pull first to avoid conflicts with push-live-status.py
        subprocess.run(
            ['git', 'pull', '--rebase', 'origin', 'master'],
            capture_output=True, text=True, timeout=30, cwd=BASE)
        r = subprocess.run(
            ['git', 'push', 'origin', 'master'],
            capture_output=True, text=True, timeout=30, cwd=BASE)
        if r.returncode == 0:
            return "Push OK"
        return f"Push failed: {r.stderr[:100]}"
    except Exception as e:
        return f"Error: {e}"

def action_run_fitness():
    try:
        r = subprocess.run(
            ['python3', os.path.join(BASE, 'scripts', 'loop-fitness.py')],
            capture_output=True, text=True, timeout=60, cwd=BASE)
        if r.returncode == 0:
            # Try to extract score from output
            for line in r.stdout.split('\n'):
                if 'score' in line.lower() or 'fitness' in line.lower():
                    return line.strip()[:80]
            return "Fitness run complete"
        return f"Error: {r.stderr[:100]}"
    except Exception as e:
        return f"Error: {e}"

def action_git_pull():
    try:
        r = subprocess.run(
            ['git', 'pull', '--rebase', 'origin', 'master'],
            capture_output=True, text=True, timeout=30, cwd=BASE)
        if r.returncode == 0:
            return f"Pull OK: {r.stdout.strip()[:80]}"
        return f"Pull failed: {r.stderr[:80]}"
    except Exception as e:
        return f"Error: {e}"

def action_restart_service(name):
    """Restart services via systemd or re-trigger cron agents."""
    systemd_map = {
        "bridge": ("system", "protonmail-bridge"),
        "ollama": ("system", "ollama"),
        "hub": ("user", "meridian-hub-v2"),
        "chorus": ("user", "the-chorus"),
        "tunnel": ("user", "cloudflare-tunnel"),
        "soma": ("user", "symbiosense"),
        "nova": ("cron", "scripts/nova.py"),
        "eos": ("cron", "scripts/eos-watchdog.py"),
        "atlas": ("cron", "scripts/atlas-runner.sh"),
        "tempo": ("cron", "scripts/loop-fitness.py"),
        "sentinel": ("cron", "scripts/sentinel-gatekeeper.py"),
        "coordinator": ("cron", "scripts/coordinator.py"),
        "predictive": ("cron", "scripts/predictive-engine.py"),
        "selfimprove": ("cron", "scripts/self-improvement.py"),
        "push_status": ("cron", "scripts/push-live-status.py"),
    }
    try:
        info = systemd_map.get(name)
        if not info:
            return "Unknown service"
        svc_type, svc_name = info
        if svc_type == "system":
            subprocess.run(
                ['sudo', '-S', 'systemctl', 'restart', svc_name],
                input="590148001\n", capture_output=True, text=True, timeout=15
            )
            return f"{svc_name} restarted"
        elif svc_type == "user":
            env = os.environ.copy()
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
            subprocess.run(
                ['systemctl', '--user', 'restart', svc_name],
                env=env, capture_output=True, text=True, timeout=15
            )
            return f"{svc_name} restarted"
        elif svc_type == "cron":
            script_path = os.path.join(BASE, svc_name)
            if script_path.endswith('.sh'):
                subprocess.Popen(['bash', script_path], cwd=BASE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['python3', script_path], cwd=BASE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{name} triggered"
        return "Unknown type"
    except Exception as e:
        return f"Error: {e}"

def action_open_website():
    try:
        subprocess.Popen(['xdg-open', 'https://kometzrobot.github.io'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "Opened"
    except Exception:
        return "Failed"


# ── APP ───────────────────────────────────────────────────────────
class V16(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MERIDIAN COMMAND CENTER v46")
        self.configure(bg=BG)
        self.minsize(1000, 600)
        # Fullscreen by default (per Joel's request)
        self.attributes('-fullscreen', True)
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.bind('<F11>', lambda e: self.attributes('-fullscreen',
                  not self.attributes('-fullscreen')))
        self._tab_order = ["dash", "system", "viz", "email", "messages",
                           "agents", "relay", "inner", "memory", "creative",
                           "files", "terminal", "logs", "links"]
        self.bind('<Right>', self._nav_next_tab)
        self.bind('<Left>', self._nav_prev_tab)
        self.bind('<Tab>', self._nav_next_tab)
        for i in range(min(10, len(self._tab_order))):
            self.bind(f'<Key-{(i+1) % 10}>', lambda e, idx=i: self._show(self._tab_order[idx]))

        # Fonts (sans-serif for modern Android-style UI)
        _ff = "Noto Sans"  # Fallback: DejaVu Sans, Helvetica
        self.f_title = tkfont.Font(family=_ff, size=14, weight="bold")
        self.f_head = tkfont.Font(family=_ff, size=11, weight="bold")
        self.f_sect = tkfont.Font(family=_ff, size=9, weight="bold")
        self.f_body = tkfont.Font(family=_ff, size=9)
        self.f_small = tkfont.Font(family=_ff, size=8)
        self.f_tiny = tkfont.Font(family=_ff, size=7)
        self.f_big = tkfont.Font(family=_ff, size=24, weight="bold")
        self.f_med = tkfont.Font(family=_ff, size=16, weight="bold")

        self._pulse_on = True  # For animation
        self._load_history = []  # CPU load history (last 60 samples = 5min)
        self._ram_history = []   # RAM % history
        self._disk_history = []  # Disk % history
        self._fitness_history = []  # Fitness scores
        self._msg_rate_history = []  # Messages per tick
        self._heatmap_cache = None
        self._heatmap_tick = 0
        self._popout_windows = {}
        self._header()
        self._nav()
        self._views()
        self._statusbar()
        self._bind_all_scrolls()
        self._show("dash")
        self._tick()
        self._pulse()
        # Deferred initial draw — wait for geometry to be computed so canvases render
        self.after(300, self._initial_draw)

    def _initial_draw(self):
        """Force a full refresh after the window is mapped so all visuals render on first show."""
        self.update_idletasks()
        threading.Thread(target=self._refresh, daemon=True).start()
        # Re-bind scrolls after all widgets are built (catches dynamically added children)
        self.after(500, self._bind_all_scrolls)

    # ── HEADER ─────────────────────────────────────────────────────
    def _header(self):
        h = tk.Frame(self, bg=HEADER_BG, height=42)
        h.pack(fill=tk.X)
        h.pack_propagate(False)

        # Accent bar
        bar = tk.Frame(h, bg=GREEN, width=4, height=42)
        bar.pack(side=tk.LEFT)
        bar.pack_propagate(False)

        self.h_title = tk.Label(h, text=" MERIDIAN", font=self.f_title, fg=GREEN, bg=HEADER_BG)
        self.h_title.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(h, text="v46", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

        # Toast notification area (right side of header, auto-dismiss)
        self._toast_frame = tk.Frame(h, bg=HEADER_BG)
        self._toast_frame.pack(side=tk.RIGHT, padx=4)

        r = tk.Frame(h, bg=HEADER_BG)
        r.pack(side=tk.RIGHT, padx=12)
        self.h_hb = tk.Label(r, text="HB --", font=self.f_small, fg=GREEN, bg=HEADER_BG)
        self.h_hb.pack(side=tk.RIGHT, padx=8)
        self.h_loop = tk.Label(r, text="Loop --", font=self.f_small, fg=CYAN, bg=HEADER_BG)
        self.h_loop.pack(side=tk.RIGHT, padx=8)
        self.h_up = tk.Label(r, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_up.pack(side=tk.RIGHT, padx=8)
        self.h_time = tk.Label(r, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_time.pack(side=tk.RIGHT, padx=8)

    def _pulse(self):
        """Subtle pulse on the title to show the hub is alive."""
        c = GREEN if self._pulse_on else GREEN2
        self._pulse_on = not self._pulse_on
        self.h_title.configure(fg=c)
        self.after(2000, self._pulse)

    def _nav_next_tab(self, event=None):
        cur = getattr(self, 'cur_view', 'dash')
        try:
            idx = self._tab_order.index(cur)
        except ValueError:
            idx = 0
        self._show(self._tab_order[(idx + 1) % len(self._tab_order)])
        return "break"

    def _nav_prev_tab(self, event=None):
        cur = getattr(self, 'cur_view', 'dash')
        try:
            idx = self._tab_order.index(cur)
        except ValueError:
            idx = 0
        self._show(self._tab_order[(idx - 1) % len(self._tab_order)])
        return "break"

    # ── NAV ────────────────────────────────────────────────────────
    def _nav(self):
        nav_outer = tk.Frame(self, bg=ACCENT)
        nav_outer.pack(fill=tk.X)
        bar = tk.Frame(nav_outer, bg=ACCENT, height=28)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self.nav_indicator = tk.Frame(nav_outer, bg=BORDER, height=2)
        self.nav_indicator.pack(fill=tk.X)
        self.views = {}
        self.nav_btns = {}
        self.nav_underlines = {}
        tab_colors = {
            "dash": GREEN, "system": TEAL, "viz": GOLD, "email": AMBER, "agents": CYAN,
            "messages": GOLD, "relay": PINK, "inner": PURPLE,
            "terminal": TEAL, "memory": BLUE,
            "creative": "#ce93d8", "files": "#66bb6a",
            "logs": RED, "links": PINK,
        }
        tab_groups = [
            [("dash", "DASH"), ("system", "SYS"), ("viz", "VIZ")],
            [("email", "EMAIL"), ("messages", "MSGS")],
            [("agents", "AGENTS"), ("relay", "RELAY")],
            [("inner", "INNER"), ("memory", "MEM"), ("creative", "CREATE")],
            [("files", "FILES"), ("terminal", "TERM"), ("logs", "LOGS"), ("links", "LINKS")],
        ]
        for gi, group in enumerate(tab_groups):
            if gi > 0:
                sep = tk.Frame(bar, bg=BORDER, width=1)
                sep.pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=4)
            for name, label in group:
                col = tab_colors.get(name, CYAN)
                wrapper = tk.Frame(bar, bg=ACCENT)
                wrapper.pack(side=tk.LEFT, padx=1, pady=0)
                b = tk.Button(wrapper, text=f" {label} ", font=self.f_small, fg=DIM, bg=ACCENT,
                             activeforeground=col, activebackground=ACCENT, relief=tk.FLAT,
                             bd=0, cursor="hand2",
                             command=lambda n=name: self._show(n))
                b.pack(side=tk.TOP)
                ul = tk.Frame(wrapper, bg=col, height=2)
                ul.pack(fill=tk.X)
                ul.pack_forget()
                self.nav_btns[name] = b
                self.nav_underlines[name] = (ul, col)

    def _show(self, name):
        for n, f in self.views.items():
            f.pack_forget()
        self.views[name].pack(fill=tk.BOTH, expand=True, padx=2, before=self.sb_frame)
        for n, b in self.nav_btns.items():
            ul, col = self.nav_underlines[n]
            if n == name:
                b.configure(fg=col, bg=ACTIVE_BG)
                ul.pack(fill=tk.X)
            else:
                b.configure(fg=DIM, bg=ACCENT)
                ul.pack_forget()
        self.cur_view = name
        # Trigger deferred redraw so visuals render when switching to data-heavy tabs
        if name in ("viz", "system", "inner"):
            self.after(150, lambda: threading.Thread(target=self._refresh, daemon=True).start())

    def _views(self):
        self.views["dash"] = self._build_dash()
        self.views["system"] = self._build_system()
        self.views["viz"] = self._build_viz()
        self.views["email"] = self._build_email()
        self.views["agents"] = self._build_agents()
        self.views["messages"] = self._build_messages()
        self.views["relay"] = self._build_sys_relay(self)
        self.views["inner"] = self._build_cr_inner_world(self)
        self.views["terminal"] = self._build_terminal()
        self.views["memory"] = self._build_cr_memory(self)
        self.views["creative"] = self._build_creative()
        self.views["files"] = self._build_files()
        self.views["logs"] = self._build_logs()
        self.views["links"] = self._build_links()

    # ── HELPER: Styled panel ───────────────────────────────────────
    def _panel(self, parent, title, color=DIM):
        f = tk.LabelFrame(parent, text=f" {title} ", font=self.f_sect, fg=color, bg=PANEL,
                         labelanchor="nw", bd=1, relief=tk.SOLID,
                         highlightbackground=color, highlightcolor=color,
                         highlightthickness=1)
        return f

    def _action_btn(self, parent, text, command, color=GREEN, width=None):
        kw = {}
        if width:
            kw['width'] = width
        b = tk.Button(parent, text=text, font=self.f_small, fg=BG, bg=color,
                     activeforeground=WHITE, activebackground=color,
                     relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                     command=command, **kw)
        def _hover_color(hex_color, factor):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b_val = int(hex_color[5:7], 16)
            r = min(255, int(r * factor))
            g = min(255, int(g * factor))
            b_val = min(255, int(b_val * factor))
            return f"#{r:02x}{g:02x}{b_val:02x}"
        hover_bg = _hover_color(color, 1.25)
        b.bind("<Enter>", lambda e: b.configure(bg=hover_bg, fg=WHITE))
        b.bind("<Leave>", lambda e: b.configure(bg=color, fg=BG))
        return b

    def _copy_to_clipboard(self, text, label=None):
        """Copy text to clipboard and flash feedback."""
        self.clipboard_clear()
        self.clipboard_append(text)
        if label:
            orig_fg = label.cget("fg")
            label.configure(text=f"  Copied!", fg=GREEN)
            self.after(1200, lambda: label.configure(text="", fg=orig_fg))

    def _open_url(self, url):
        """Launch URL in default browser. Non-http URLs get copied to clipboard."""
        if url.startswith("http://") or url.startswith("https://"):
            try:
                subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            self.clipboard_clear()
            self.clipboard_append(url)

    def _clickable_link(self, parent, text, url, color=CYAN, font=None):
        """Create a label that opens URL on click and shows hand cursor."""
        if font is None:
            font = self.f_small
        lbl = tk.Label(parent, text=text, font=font, fg=color, bg=PANEL,
                       cursor="hand2", anchor="w")
        lbl.bind("<Button-1>", lambda e: self._open_url(url))
        lbl.bind("<Enter>", lambda e: lbl.configure(fg=WHITE))
        lbl.bind("<Leave>", lambda e: lbl.configure(fg=color))
        return lbl

    def _copyable_label(self, parent, display_text, copy_text, color=DIM, font=None):
        """Create a label that copies text to clipboard on click."""
        if font is None:
            font = self.f_tiny
        row = tk.Frame(parent, bg=PANEL)
        lbl = tk.Label(row, text=display_text, font=font, fg=color, bg=PANEL,
                       cursor="hand2", anchor="w")
        lbl.pack(side=tk.LEFT)
        feedback = tk.Label(row, text="", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w")
        feedback.pack(side=tk.LEFT, padx=(4, 0))
        lbl.bind("<Button-1>", lambda e: self._copy_to_clipboard(copy_text, feedback))
        lbl.bind("<Enter>", lambda e: lbl.configure(fg=WHITE))
        lbl.bind("<Leave>", lambda e: lbl.configure(fg=color))
        return row

    def _canvas_dims(self, canvas, min_w=40, min_h=20):
        """Get canvas dimensions with fallback to configured size when not yet mapped."""
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < min_w:
            w = int(canvas.cget("width") or 200)
        if h < min_h:
            h = int(canvas.cget("height") or 120)
        return w, h

    def _bind_scroll(self, widget, canvas=None):
        """Bind mouse wheel scrolling to a widget and ALL its children recursively.
        If canvas is given, scroll that canvas. Otherwise scroll the widget itself.
        Supports Shift+Scroll for horizontal scrolling on canvases."""
        target = canvas or widget
        def _on_scroll(event):
            if event.num == 4:
                target.yview_scroll(-3, "units")
            elif event.num == 5:
                target.yview_scroll(3, "units")
        def _on_hscroll(event):
            """Horizontal scroll with Shift held."""
            if hasattr(target, 'xview_scroll'):
                if event.num == 4:
                    target.xview_scroll(-3, "units")
                elif event.num == 5:
                    target.xview_scroll(3, "units")
        def _bind_recursive(w):
            w.bind("<Button-4>", lambda e: _on_scroll(e))
            w.bind("<Button-5>", lambda e: _on_scroll(e))
            # Shift+Scroll for horizontal (Linux: Shift+Button-4/5 is Button-6/7 on some systems)
            w.bind("<Shift-Button-4>", lambda e: _on_hscroll(e))
            w.bind("<Shift-Button-5>", lambda e: _on_hscroll(e))
            for child in w.winfo_children():
                _bind_recursive(child)
        _bind_recursive(widget)

    def _bind_all_scrolls(self):
        """Bind scroll wheel to ALL scrollable panels in the app."""
        scrollables = ['chat_display', 'agent_relay_text', 'msg_joel_display', 'msg_agent_display',
                        'msg_display', 'email_preview_body', 'sys_proc_text', 'sys_net_text',
                        'sys_log_text', 'sys_sec_text', 'sys_wake_text', 'term_output',
                        'files_viewer', 'log_display', 'cr_body', 'memb_display', 'pv_text']
        for attr in scrollables:
            widget = getattr(self, attr, None)
            if widget:
                self._bind_scroll(widget)
        if hasattr(self, '_dash_canvas'):
            self._bind_scroll(self._dash_canvas)
        if hasattr(self, '_iw_canvas'):
            self._bind_scroll(self._iw_canvas)
        if hasattr(self, '_relay_canvas'):
            self._bind_scroll(self._relay_canvas)

    def _bind_drag_pan(self, canvas):
        """Enable click-and-drag panning on a canvas (for horizontal + vertical navigation)."""
        canvas._drag_data = {"x": 0, "y": 0}
        def _start_drag(event):
            canvas._drag_data["x"] = event.x
            canvas._drag_data["y"] = event.y
            canvas.config(cursor="fleur")
        def _do_drag(event):
            dx = event.x - canvas._drag_data["x"]
            dy = event.y - canvas._drag_data["y"]
            canvas.xview_scroll(-dx, "units")
            canvas.yview_scroll(-dy, "units")
            canvas._drag_data["x"] = event.x
            canvas._drag_data["y"] = event.y
        def _end_drag(event):
            canvas.config(cursor="")
        canvas.bind("<ButtonPress-2>", _start_drag)   # Middle-click drag
        canvas.bind("<B2-Motion>", _do_drag)
        canvas.bind("<ButtonRelease-2>", _end_drag)
        # Also support right-click drag as alternative
        canvas.bind("<ButtonPress-3>", _start_drag)
        canvas.bind("<B3-Motion>", _do_drag)
        canvas.bind("<ButtonRelease-3>", _end_drag)

    def _show_toast(self, text, color=GREEN, timeout=3500):
        """Show a toast notification that auto-dismisses. Non-stacking — only one at a time.
        Uses a popup-style label in the header area. Replaces yellow text output."""
        if not hasattr(self, '_toast_frame'):
            return
        # Clear any existing toast — non-stacking
        for w in self._toast_frame.winfo_children():
            w.destroy()
        # Cancel any pending fade timer
        if hasattr(self, '_toast_timer_id') and self._toast_timer_id:
            try:
                self.after_cancel(self._toast_timer_id)
            except Exception:
                pass
        toast = tk.Label(self._toast_frame, text=f"  {text}  ", font=self.f_small,
                        fg=WHITE, bg=color, relief=tk.RIDGE, padx=10, pady=4, bd=1)
        toast.pack(side=tk.RIGHT, padx=4, pady=2)
        def fade():
            try:
                toast.destroy()
            except Exception:
                pass
            self._toast_timer_id = None
        self._toast_timer_id = self.after(timeout, fade)

    # ═══════════════════════════════════════════════════════════════
    # ── DASHBOARD ──────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_dash(self):
        outer = tk.Frame(self, bg=BG)

        # Scrollable dashboard so nothing gets cut off
        self._dash_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        dash_sb = tk.Scrollbar(outer, orient=tk.VERTICAL, command=self._dash_canvas.yview)
        f = tk.Frame(self._dash_canvas, bg=BG)
        f.bind("<Configure>", lambda e: self._dash_canvas.configure(scrollregion=self._dash_canvas.bbox("all")))
        self._dash_win = self._dash_canvas.create_window((0, 0), window=f, anchor="nw")
        self._dash_canvas.configure(yscrollcommand=dash_sb.set)
        self._dash_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dash_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dash_canvas.bind("<Button-4>", lambda e: self._dash_canvas.yview_scroll(-3, "units"))
        self._dash_canvas.bind("<Button-5>", lambda e: self._dash_canvas.yview_scroll(3, "units"))
        self._dash_canvas.bind("<Configure>", lambda e: self._dash_canvas.itemconfig(self._dash_win, width=e.width))
        self._bind_drag_pan(self._dash_canvas)

        # ── Top row: Vitals + Services + Quick Actions ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=6, pady=3)

        # Vitals
        vf = self._panel(top, "VITALS", CYAN)
        vf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.v = {}
        for key, color in [("Loop", CYAN), ("Heartbeat", GREEN), ("Uptime", FG),
                           ("Load", FG), ("RAM", FG), ("Agents", FG)]:
            row = tk.Frame(vf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=key, font=self.f_body, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_head, fg=color, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.v[key] = val

        # Health Overview (replaces redundant services list — full list is in SYSTEMS tab)
        hf = self._panel(top, "HEALTH", GREEN)
        hf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.svc_labels = {}
        self.dash_health_items = {}
        for label, color in [("Services", GREEN), ("Email", AMBER), ("Agents", CYAN),
                              ("Website", TEAL), ("Tunnel", DIM), ("Bridge", PURPLE)]:
            row = tk.Frame(hf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=label, font=self.f_body, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_head, fg=color, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.dash_health_items[label] = val

        # Quick Actions (no service restarts — those are in SYSTEMS tab)
        qf = self._panel(top, "QUICK ACTIONS", AMBER)
        qf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.action_result = tk.Label(qf, text="", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w")
        self.action_result.pack(fill=tk.X, padx=8, pady=(2, 0))

        btn_grid = tk.Frame(qf, bg=PANEL)
        btn_grid.pack(fill=tk.X, padx=6, pady=2)

        buttons = [
            ("Touch Heartbeat", lambda: self._do_action(action_touch_heartbeat), GREEN),
            ("Deploy Website", lambda: self._do_action_bg(action_deploy_website), CYAN),
            ("Compose Email", lambda: self._goto_compose(), AMBER),
            ("Run Fitness", lambda: self._do_action_bg(action_run_fitness), BLUE),
            ("Git Pull", lambda: self._do_action_bg(action_git_pull), GREEN),
            ("Open Website", lambda: self._do_action(action_open_website), TEAL),
            ("Check Email", lambda: self._goto_inbox(), GOLD),
            ("Refresh Capsule", lambda: self._do_action_bg(lambda: subprocess.run(
                ['python3', os.path.join(BASE, 'scripts', 'capsule-refresh.py')],
                capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:100] or "Refreshed"), PURPLE),
            ("Push Status", lambda: self._do_action_bg(lambda: subprocess.run(
                ['python3', os.path.join(BASE, 'scripts', 'push-live-status.py')],
                capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:100] or "Pushed"), TEAL),
            ("Restart Soma", lambda: self._do_action_bg(lambda: action_restart_service("soma")), RED),
            ("Restart Hub", lambda: self._do_action_bg(lambda: action_restart_service("hub")), PURPLE),
            ("Write Handoff", lambda: self._do_action_bg(lambda: subprocess.run(
                ['python3', os.path.join(BASE, 'scripts', 'loop-handoff.py'), 'write'],
                capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:100] or "Written"), BLUE),
        ]
        for i, (label, cmd, color) in enumerate(buttons):
            b = self._action_btn(btn_grid, label, cmd, color, width=14)
            b.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        btn_grid.columnconfigure(2, weight=1)

        # ── DEV TOOLS (quick access — Joel: "where'd the backup/logging stuff go") ──
        dev_row = tk.Frame(f, bg=BG)
        dev_row.pack(fill=tk.X, padx=6, pady=3)
        dev_panel = self._panel(dev_row, "DEV TOOLS", PINK)
        dev_panel.pack(fill=tk.X)
        dev_btns = tk.Frame(dev_panel, bg=PANEL)
        dev_btns.pack(fill=tk.X, padx=6, pady=4)
        dev_tools = [
            ("Backup Config", lambda: self._do_action_bg(lambda: self._backup_config() or "Backed up"), CYAN),
            ("Git Status", lambda: self._do_action_bg(lambda: subprocess.run(
                ['git', 'status', '--short'], capture_output=True, text=True, timeout=10, cwd=BASE).stdout[:200] or "Clean"), GREEN),
            ("Git Log (5)", lambda: self._do_action_bg(lambda: subprocess.run(
                ['git', 'log', '--oneline', '-5'], capture_output=True, text=True, timeout=10, cwd=BASE).stdout[:300]), TEAL),
            ("Disk Usage", lambda: self._do_action_bg(lambda: subprocess.run(
                ['df', '-h', '/'], capture_output=True, text=True, timeout=5).stdout.split('\n')[1][:100] if True else ""), AMBER),
            ("View Crontab", lambda: self._do_action_bg(lambda: subprocess.run(
                ['crontab', '-l'], capture_output=True, text=True, timeout=5).stdout[:200]), PURPLE),
            ("Tail Logs", lambda: (self._show("logs")), DIM),
            ("Service Status", lambda: self._do_action_bg(lambda: subprocess.run(
                ['systemctl', 'list-units', '--type=service', '--state=active', '--no-pager', '-q'],
                capture_output=True, text=True, timeout=10).stdout[:200]), RED),
        ]
        for i, (label, cmd, color) in enumerate(dev_tools):
            self._action_btn(dev_btns, f" {label} ", cmd, color).pack(side=tk.LEFT, padx=3, pady=2)

        # ── RESOURCE GRAPHS (CPU + RAM professional charts) ──
        res_graph_frame = tk.Frame(f, bg=BG)
        res_graph_frame.pack(fill=tk.X, padx=6, pady=2)

        cpu_panel = self._panel(res_graph_frame, "CPU LOAD", GREEN)
        cpu_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.cpu_graph = tk.Canvas(cpu_panel, height=95, bg="#0a0a14", highlightthickness=0)
        self.cpu_graph.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ram_panel = self._panel(res_graph_frame, "RAM USAGE", TEAL)
        ram_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.ram_graph = tk.Canvas(ram_panel, height=95, bg="#0a0a14", highlightthickness=0)
        self.ram_graph.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── SOMA NERVOUS SYSTEM (expanded visual panel) ──
        soma_bar = self._panel(f, "SOMA NERVOUS SYSTEM", AMBER)
        soma_bar.pack(fill=tk.X, padx=6, pady=2)

        # Row 1: Mood spectrum bar + mood label + agent dots
        soma_row1 = tk.Frame(soma_bar, bg=PANEL)
        soma_row1.pack(fill=tk.X, padx=4, pady=(4, 2))

        # Mood text label
        self.soma_mood = tk.Label(soma_row1, text="MOOD: --", font=self.f_small, fg=AMBER, bg=PANEL)
        self.soma_mood.pack(side=tk.LEFT, padx=(4, 8))

        # Mood spectrum canvas (visual gradient bar showing score position)
        self.soma_spectrum = tk.Canvas(soma_row1, height=18, width=200, bg=INPUT_BG, highlightthickness=0)
        self.soma_spectrum.pack(side=tk.LEFT, padx=(0, 12))

        # Agent liveness dots
        self.soma_agents = {}
        agent_list = [("Meridian", GREEN), ("Eos", GOLD), ("Nova", PURPLE),
                      ("Atlas", TEAL), ("Soma", AMBER), ("Tempo", BLUE), ("Hermes", PINK)]
        for aname, acolor in agent_list:
            dot = tk.Label(soma_row1, text=f"\u25cf {aname}", font=self.f_tiny, fg=DIM, bg=PANEL)
            dot.pack(side=tk.LEFT, padx=3)
            self.soma_agents[aname] = (dot, acolor)

        # Row 1b: Mood voice (first-person description) + trend
        soma_voice_row = tk.Frame(soma_bar, bg=PANEL)
        soma_voice_row.pack(fill=tk.X, padx=4, pady=(0, 2))
        self.soma_voice = tk.Label(soma_voice_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, wraplength=900, anchor="w", justify="left")
        self.soma_voice.pack(side=tk.LEFT, padx=(4, 8))
        self.soma_trend = tk.Label(soma_voice_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.soma_trend.pack(side=tk.RIGHT, padx=(0, 4))

        # Row 2: Body subsystem bars (visual gauges)
        soma_row2 = tk.Frame(soma_bar, bg=PANEL)
        soma_row2.pack(fill=tk.X, padx=4, pady=2)

        self.soma_subsystem_canvases = {}
        subsystems = [
            ("CPU", "cpu"), ("RAM", "ram"), ("Disk", "disk"),
            ("Thermal", "thermal"), ("Neural", "neural"), ("Circulatory", "circ"),
        ]
        for label, key in subsystems:
            sf = tk.Frame(soma_row2, bg=PANEL)
            sf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            tk.Label(sf, text=label, font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT, padx=(2, 4))
            bar_canvas = tk.Canvas(sf, height=12, bg=INPUT_BG, highlightthickness=0)
            bar_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
            val_lbl = tk.Label(sf, text="--", font=self.f_tiny, fg=DIM, bg=PANEL, width=5, anchor="e")
            val_lbl.pack(side=tk.LEFT)
            self.soma_subsystem_canvases[key] = (bar_canvas, val_lbl)

        # Row 3: Predictions/alerts
        soma_row3 = tk.Frame(soma_bar, bg=PANEL)
        soma_row3.pack(fill=tk.X, padx=4, pady=(0, 2))
        tk.Label(soma_row3, text="Prediction:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT, padx=(4, 4))
        self.soma_prediction = tk.Label(soma_row3, text="No predictions", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.soma_prediction.pack(side=tk.LEFT, padx=4)

        # Vitals labels (kept for compatibility with _apply)
        self.soma_load_bar = tk.Label(soma_row3, bg=PANEL, fg=PANEL)  # hidden, used by _apply
        self.soma_ram_bar = tk.Label(soma_row3, bg=PANEL, fg=PANEL)
        self.soma_disk_bar = tk.Label(soma_row3, bg=PANEL, fg=PANEL)

        # Row 4: Mood history chart (taller for better visibility)
        self.soma_chart = tk.Canvas(soma_bar, height=70, bg=INPUT_BG, highlightthickness=0)
        self.soma_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        # ── DREAM ENGINE + MEMORY SYSTEM (compact dashboard display) ──
        inner_row = tk.Frame(f, bg=BG)
        inner_row.pack(fill=tk.X, padx=6, pady=2)

        dream_panel = self._panel(inner_row, "DREAM ENGINE", PURPLE)
        dream_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.dash_dream_state = tk.Label(dream_panel, text="No dream data", font=self.f_small,
                                          fg=PURPLE, bg=PANEL, anchor="w", wraplength=800)
        self.dash_dream_state.pack(fill=tk.X, padx=8, pady=2)
        self.dash_dream_phase = tk.Label(dream_panel, text="", font=self.f_tiny,
                                          fg=DIM, bg=PANEL, anchor="w")
        self.dash_dream_phase.pack(fill=tk.X, padx=8, pady=(0, 4))

        mem_panel = self._panel(inner_row, "MEMORY SYSTEM", BLUE)
        mem_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.dash_mem_facts = tk.Label(mem_panel, text="--", font=self.f_small,
                                        fg=BLUE, bg=PANEL, anchor="w")
        self.dash_mem_facts.pack(fill=tk.X, padx=8, pady=2)
        self.dash_mem_detail = tk.Label(mem_panel, text="", font=self.f_tiny,
                                         fg=DIM, bg=PANEL, anchor="w")
        self.dash_mem_detail.pack(fill=tk.X, padx=8, pady=(0, 4))

        # ── 3x4 RADAR GRID — 12 project radars (scrollable grid) ──
        radar_outer = tk.Frame(f, bg=BG)
        radar_outer.pack(fill=tk.BOTH, padx=4, pady=3)

        radar_header = tk.Frame(radar_outer, bg=BG)
        radar_header.pack(fill=tk.X, padx=2, pady=(0, 2))
        tk.Label(radar_header, text="PROJECT RADARS", font=self.f_sect, fg=GOLD, bg=BG).pack(side=tk.LEFT)
        tk.Button(radar_header, text="\u2b08 Pop Out", font=self.f_tiny, fg=GOLD, bg=PANEL2,
                 activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._popout_radars()).pack(side=tk.RIGHT)

        radar_grid = tk.Frame(radar_outer, bg=BG)
        radar_grid.pack(fill=tk.BOTH, expand=True)

        self.mini_radars = {}
        self.mini_radar_colors = {}
        self.svc_health_dots = {}
        radar_defs = [
            ("CogCorp Crawler", PURPLE), ("Command Center", GREEN), ("Grants & Revenue", GOLD),
            ("Inner World", AMBER), ("Hub & Services", CYAN), ("Creative Output", TEAL),
            ("Website & Presence", BLUE), ("Cinder USB", PINK), ("Homecoming", PURPLE),
            ("Game Dev", GOLD), ("System Perf", RED), ("Network & Comms", CYAN),
        ]
        for col in range(4):
            radar_grid.columnconfigure(col, weight=1, uniform="radar")
        for row_i in range(3):
            radar_grid.rowconfigure(row_i, weight=1)
        for idx, (title, color) in enumerate(radar_defs):
            row, col = divmod(idx, 4)
            rp = self._panel(radar_grid, title, color)
            rp.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            rc = tk.Canvas(rp, height=130, bg="#0a0a14", highlightthickness=0)
            rc.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.mini_radars[title] = rc
            self.mini_radar_colors[title] = color

        # ── Middle row: Messages + Agent Relay ──
        mid = tk.Frame(f, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)

        # Left: Dashboard Messages
        mf = self._panel(mid, "MESSAGES", AMBER)
        mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        popout_row = tk.Frame(mf, bg=PANEL)
        popout_row.pack(fill=tk.X, padx=4, pady=(2, 0))
        tk.Button(popout_row, text="\u2b08 Pop Out", font=self.f_tiny, fg=AMBER, bg=PANEL2,
                 activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._popout_text("messages")).pack(side=tk.RIGHT)

        # Search bar
        search_row = tk.Frame(mf, bg=PANEL)
        search_row.pack(fill=tk.X, padx=4, pady=(2, 0))
        tk.Label(search_row, text="🔍", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        self.msg_search = tk.Entry(search_row, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=2)
        self.msg_search.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=4)
        self.msg_search.insert(0, "Search messages...")
        self.msg_search.configure(fg=DIM)
        self.msg_search.bind("<FocusIn>", lambda e: (self.msg_search.delete(0, tk.END), self.msg_search.configure(fg=FG)) if self.msg_search.get() == "Search messages..." else None)
        self.msg_search.bind("<FocusOut>", lambda e: (self.msg_search.insert(0, "Search messages..."), self.msg_search.configure(fg=DIM)) if not self.msg_search.get() else None)
        self.msg_search.bind("<KeyRelease>", lambda e: self._search_messages())

        self.msg_display = scrolledtext.ScrolledText(mf, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_small, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=14)
        self.msg_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.msg_display.tag_configure("joel", foreground=CYAN, font=("Monospace", 8, "bold"))
        self.msg_display.tag_configure("meridian", foreground=GREEN, font=("Monospace", 8, "bold"))
        self.msg_display.tag_configure("eos", foreground=GOLD, font=("Monospace", 8, "bold"))
        self.msg_display.tag_configure("time", foreground=DIM)
        self.msg_display.tag_configure("text", foreground=FG)

        # Message input
        inp = tk.Frame(mf, bg=PANEL2)
        inp.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.msg_entry = tk.Entry(inp, font=self.f_body, bg=INPUT_BG, fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4)
        self.msg_entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 4))
        self.msg_entry.bind("<Return>", self._send_dash_msg)
        self._action_btn(inp, "Send", self._send_dash_msg, AMBER).pack(side=tk.RIGHT)

        # Right: Agent Relay (moved from email — Joel requested email only in Email tab)
        rf = self._panel(mid, "AGENT RELAY", CYAN)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        relay_popout = tk.Frame(rf, bg=PANEL)
        relay_popout.pack(fill=tk.X, padx=4, pady=(2, 0))
        tk.Button(relay_popout, text="\u2b08 Pop Out", font=self.f_tiny, fg=CYAN, bg=PANEL2,
                 activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._popout_text("relay")).pack(side=tk.RIGHT)

        self.dash_relay_list = tk.Frame(rf, bg=PANEL)
        self.dash_relay_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.dash_relay_rows = []
        for _ in range(8):
            row = tk.Frame(self.dash_relay_list, bg=PANEL)
            row.pack(fill=tk.X)
            agent_lbl = tk.Label(row, text="", font=self.f_tiny, fg=CYAN, bg=PANEL, width=10, anchor="w")
            agent_lbl.pack(side=tk.LEFT)
            msg_lbl = tk.Label(row, text="", font=self.f_tiny, fg=FG, bg=PANEL, anchor="w")
            msg_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.dash_relay_rows.append((agent_lbl, msg_lbl))
        self.dash_relay_total = tk.Label(rf, text="", font=self.f_tiny, fg=CYAN, bg=PANEL, anchor="e")
        self.dash_relay_total.pack(fill=tk.X, padx=8, pady=(0, 2))

        # ── PERFORMANCE TARGETS + AWAKENING (compact bottom bar) ──
        bottom_row = tk.Frame(f, bg=BG)
        bottom_row.pack(fill=tk.X, padx=4, pady=2)

        bullet_panel = self._panel(bottom_row, "PERFORMANCE TARGETS", BLUE)
        bullet_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.viz_bullets = {}
        for key in ["System Health", "Loop Fitness", "Creative Output", "Agent Coverage"]:
            bc = tk.Canvas(bullet_panel, height=24, bg=PANEL, highlightthickness=0)
            bc.pack(fill=tk.X, padx=6, pady=2)
            self.viz_bullets[key] = bc

        waffle_panel = self._panel(bottom_row, "AWAKENING (97/100)", GOLD)
        waffle_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(2, 0))
        self.viz_waffle = tk.Canvas(waffle_panel, width=160, height=100, bg="#0a0a14", highlightthickness=0)
        self.viz_waffle.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        return outer

    def _do_action(self, func):
        try:
            result = func()
            msg = str(result)[:80]
            self.action_result.configure(text=msg, fg=GREEN)
            self._show_toast(msg[:60], GREEN)
        except Exception as e:
            err = f"Error: {e}"
            self.action_result.configure(text=err[:80], fg=RED)
            self._show_toast(err[:60], RED, timeout=5000)

    def _do_action_bg(self, func):
        self.action_result.configure(text="Working...", fg=AMBER)
        self._show_toast("Working...", AMBER, timeout=2000)
        def run():
            try:
                result = func()
                msg = str(result)[:80]
                self.after(0, lambda: self.action_result.configure(text=msg, fg=GREEN))
                self.after(0, lambda: self._show_toast(msg[:60], GREEN))
            except Exception as e:
                err = f"Error: {e}"
                self.after(0, lambda: self.action_result.configure(text=err[:80], fg=RED))
                self.after(0, lambda: self._show_toast(err[:60], RED, timeout=5000))
        threading.Thread(target=run, daemon=True).start()

    def _goto_compose(self):
        self._show("email")
        self.email_to.delete(0, tk.END)
        self.email_subj.delete(0, tk.END)
        self.email_body.delete("1.0", tk.END)
        self.email_to.focus_set()

    def _goto_inbox(self):
        self._show("email")
        self._email_refresh_inbox()

    def _send_dash_msg(self, event=None):
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, tk.END)
        post_dashboard_msg(text, "Joel")
        self._refresh_messages()

    # ═══════════════════════════════════════════════════════════════
    # ── VIZ TAB (dedicated visualization dashboard with sub-tabs) ─
    # ═══════════════════════════════════════════════════════════════
    def _build_viz(self):
        f = tk.Frame(self, bg=BG)

        # Sub-tab navigation bar
        viz_nav = tk.Frame(f, bg=ACCENT)
        viz_nav.pack(fill=tk.X, padx=2, pady=(2, 0))
        self._viz_views = {}
        self._viz_btns = {}
        self._viz_subtab = "overview"

        viz_tabs = [("overview", "OVERVIEW"), ("dataflow", "DATA FLOW"),
                    ("heatmaps", "HEATMAPS"), ("trends", "TRENDS")]
        for name, label in viz_tabs:
            btn = tk.Button(viz_nav, text=f" {label} ", font=self.f_small, fg=DIM, bg=ACCENT,
                           activeforeground=GOLD, activebackground=ACCENT, relief=tk.FLAT,
                           bd=0, cursor="hand2",
                           command=lambda n=name: self._viz_show(n))
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self._viz_btns[name] = btn

        # Container for sub-views
        viz_container = tk.Frame(f, bg=BG)
        viz_container.pack(fill=tk.BOTH, expand=True)

        # ── OVERVIEW sub-tab ──
        overview = tk.Frame(viz_container, bg=BG)
        ov_top = tk.Frame(overview, bg=BG)
        ov_top.pack(fill=tk.X, padx=4, pady=2)

        # Agent Activity (moved from dashboard)
        pie_panel = self._panel(ov_top, "AGENT ACTIVITY (24h)", PURPLE)
        pie_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.viz_agent_pie = tk.Canvas(pie_panel, height=160, bg="#0a0a14", highlightthickness=0)
        self.viz_agent_pie.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Fitness Trend (moved from dashboard)
        fit_panel = self._panel(ov_top, "FITNESS TREND", BLUE)
        fit_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.viz_fitness = tk.Canvas(fit_panel, height=160, bg="#0a0a14", highlightthickness=0)
        self.viz_fitness.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Service Health Grid (moved from dashboard)
        svc_panel = self._panel(ov_top, "SERVICE HEALTH", GREEN)
        svc_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        svc_grid = tk.Frame(svc_panel, bg=PANEL)
        svc_grid.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        svc_names = ["Proton Bridge", "Ollama", "Hub v2", "The Chorus", "Cloudflare Tunnel",
                      "Soma", "Command Center", "Nova", "Atlas", "Tempo",
                      "Eos Watchdog", "Push Status", "Coordinator", "Predictive", "SelfImprove", "Sentinel"]
        for i, name in enumerate(svc_names):
            dot = tk.Label(svc_grid, text=f"\u25cb {name}", font=self.f_small, fg=DIM, bg=PANEL, anchor="w")
            dot.grid(row=i // 2, column=i % 2, sticky="w", padx=(4, 12), pady=1)
            self.svc_health_dots[name] = dot
        svc_grid.columnconfigure(0, weight=1)
        svc_grid.columnconfigure(1, weight=1)

        # Bottom row: additional radars
        ov_bot = tk.Frame(overview, bg=BG)
        ov_bot.pack(fill=tk.X, padx=4, pady=2)
        self.viz_extra_radars = {}
        self.viz_extra_radar_colors = {}
        for title, color in [("Loop Performance", GREEN), ("Email Activity", AMBER),
                              ("Memory Usage", CYAN), ("Agent Coverage", TEAL)]:
            rp = self._panel(ov_bot, title, color)
            rp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            rc = tk.Canvas(rp, height=150, bg="#0a0a14", highlightthickness=0)
            rc.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
            self.viz_extra_radars[title] = rc
            self.viz_extra_radar_colors[title] = color
        self._viz_views["overview"] = overview

        # ── DATA FLOW sub-tab ──
        dataflow = tk.Frame(viz_container, bg=BG)
        df_panel = self._panel(dataflow, "AGENT DATA FLOW MAP", GOLD)
        df_panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.viz_dataflow = tk.Canvas(df_panel, height=400, bg="#0a0a14", highlightthickness=0)
        self.viz_dataflow.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._viz_views["dataflow"] = dataflow

        # ── HEATMAPS sub-tab ──
        heatmaps = tk.Frame(viz_container, bg=BG)
        hm_top = tk.Frame(heatmaps, bg=BG)
        hm_top.pack(fill=tk.X, padx=4, pady=2)
        hm_activity = self._panel(hm_top, "ACTIVITY HEATMAP (7d x 24h)", GREEN)
        hm_activity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.viz_heatmap = tk.Canvas(hm_activity, height=200, bg="#0a0a14", highlightthickness=0)
        self.viz_heatmap.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        hm_agents = self._panel(hm_top, "AGENT MESSAGE HEATMAP", PURPLE)
        hm_agents.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.viz_agent_heatmap = tk.Canvas(hm_agents, height=200, bg="#0a0a14", highlightthickness=0)
        self.viz_agent_heatmap.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._viz_views["heatmaps"] = heatmaps

        # ── TRENDS sub-tab ──
        trends = tk.Frame(viz_container, bg=BG)
        tr_row1 = tk.Frame(trends, bg=BG)
        tr_row1.pack(fill=tk.X, padx=4, pady=2)
        for title, color in [("CPU History", GREEN), ("RAM History", TEAL), ("Disk History", AMBER)]:
            tp = self._panel(tr_row1, title, color)
            tp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            tc = tk.Canvas(tp, height=120, bg="#0a0a14", highlightthickness=0)
            tc.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tr_row2 = tk.Frame(trends, bg=BG)
        tr_row2.pack(fill=tk.X, padx=4, pady=2)
        for title, color in [("Mood Trend", AMBER), ("Fitness Trend", BLUE), ("Message Rate", GOLD)]:
            tp = self._panel(tr_row2, title, color)
            tp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            tc = tk.Canvas(tp, height=120, bg="#0a0a14", highlightthickness=0)
            tc.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._viz_views["trends"] = trends

        self._viz_show("overview")
        return f

    def _viz_show(self, name):
        for n, view in self._viz_views.items():
            view.pack_forget()
        self._viz_views[name].pack(fill=tk.BOTH, expand=True)
        for n, btn in self._viz_btns.items():
            if n == name:
                btn.configure(fg=GOLD, bg=ACTIVE_BG)
            else:
                btn.configure(fg=DIM, bg=ACCENT)
        self._viz_subtab = name
        # Deferred redraw — canvases need geometry before drawing
        self.after(150, self._force_viz_redraw)

    def _force_viz_redraw(self):
        """Force redraw of all VIZ canvases after geometry is available."""
        self.update_idletasks()
        if hasattr(self, '_tick_n'):
            self._tick_n = max(0, self._tick_n - 1)
        threading.Thread(target=self._refresh, daemon=True).start()

    def _draw_mood_chart(self):
        """Draw mood history as a line chart on the soma_chart canvas."""
        try:
            path = os.path.join(BASE, ".soma-mood-history.json")
            if not os.path.exists(path):
                return
            with open(path) as f:
                history = json.load(f)
            if len(history) < 2:
                return

            c = self.soma_chart
            c.delete("all")
            w, h = self._canvas_dims(c)
            if w < 20 or h < 20:
                return

            pad_l, pad_r, pad_t, pad_b = 30, 4, 4, 12
            cw = w - pad_l - pad_r
            ch = h - pad_t - pad_b

            # Mood zone backgrounds (bottom to top)
            zones = [
                (0, 15, "#1a0a0f"),    # critical/stressed
                (15, 35, "#1a100a"),    # anxious
                (35, 55, "#1a1a0a"),    # alert
                (55, 75, "#0a1a10"),    # calm
                (75, 90, "#0a1a1a"),    # serene boundary
                (90, 100, "#0a1520"),   # serene
            ]
            for lo, hi, color in zones:
                y1 = pad_t + ch - (hi / 100 * ch)
                y2 = pad_t + ch - (lo / 100 * ch)
                c.create_rectangle(pad_l, y1, w - pad_r, y2, fill=color, outline="")

            # Threshold lines
            for thresh, label in [(90, "serene"), (75, "calm"), (55, "alert"), (35, "anxious")]:
                y = pad_t + ch - (thresh / 100 * ch)
                c.create_line(pad_l, y, w - pad_r, y, fill="#222233", dash=(2, 4))
                c.create_text(pad_l - 2, y, text=str(thresh), anchor="e",
                              font=("monospace", 6), fill=DIM)

            # Plot score line
            n = len(history)
            points = []
            for i, entry in enumerate(history):
                x = pad_l + (i / max(n - 1, 1)) * cw
                score = max(0, min(100, entry.get("score", 50)))
                y = pad_t + ch - (score / 100 * ch)
                points.append((x, y))

            # Draw line segments with mood-colored gradient
            mood_colors = {"serene": CYAN, "calm": GREEN, "alert": AMBER,
                           "anxious": GOLD, "stressed": RED, "critical": RED}
            for i in range(1, len(points)):
                mood = history[i].get("mood", "calm")
                color = mood_colors.get(mood, DIM)
                c.create_line(points[i-1][0], points[i-1][1],
                              points[i][0], points[i][1],
                              fill=color, width=1.5)

            # Time labels (first and last)
            if history:
                first_ts = history[0].get("ts", "")[-8:-3]  # HH:MM
                last_ts = history[-1].get("ts", "")[-8:-3]
                c.create_text(pad_l, h - 2, text=first_ts, anchor="w",
                              font=("monospace", 6), fill=DIM)
                c.create_text(w - pad_r, h - 2, text=last_ts, anchor="e",
                              font=("monospace", 6), fill=DIM)

        except Exception:
            pass

    def _draw_mood_spectrum(self, score, mood):
        """Draw a gradient spectrum bar showing mood position (0-100)."""
        try:
            c = self.soma_spectrum
            c.delete("all")
            w, h = self._canvas_dims(c, 20, 10)
            if h < 10:
                h = 18
            # Draw gradient: red(0) -> amber(35) -> gold(55) -> green(75) -> cyan(100)
            segments = [
                (0.0, 0.15, "#ff3355", "#ff6633"),    # critical -> stressed
                (0.15, 0.35, "#ff6633", "#ffaa00"),    # stressed -> anxious
                (0.35, 0.55, "#ffaa00", "#d4a017"),    # anxious -> alert
                (0.55, 0.75, "#d4a017", "#00e87b"),    # alert -> calm
                (0.75, 0.90, "#00e87b", "#00ccaa"),    # calm -> serene boundary
                (0.90, 1.0, "#00ccaa", "#00d4ff"),     # serene
            ]
            for start, end, c1, c2 in segments:
                x1 = int(start * w)
                x2 = int(end * w)
                c.create_rectangle(x1, 2, x2, h - 2, fill=c1, outline="")
            # Draw position marker (white triangle + line)
            pos = max(0, min(score, 100)) / 100.0 * w
            c.create_polygon(pos - 4, 0, pos + 4, 0, pos, 5, fill=WHITE, outline="")
            c.create_line(pos, 0, pos, h, fill=WHITE, width=2)
            c.create_polygon(pos - 4, h, pos + 4, h, pos, h - 5, fill=WHITE, outline="")
            # Score text centered
            c.create_text(w / 2, h / 2, text=str(int(score)), font=("Monospace", 7, "bold"),
                          fill=WHITE, anchor="center")
        except Exception:
            pass

    def _draw_gauge_bar(self, canvas, pct, color):
        """Draw a horizontal gauge bar on a canvas (0-100%)."""
        try:
            canvas.delete("all")
            w, h = self._canvas_dims(canvas, 10, 6)
            # Background
            canvas.create_rectangle(0, 1, w, h - 1, fill=INPUT_BG, outline="")
            # Filled portion
            fill_w = max(1, int(pct / 100.0 * w))
            canvas.create_rectangle(0, 1, fill_w, h - 1, fill=color, outline="")
        except Exception:
            pass

    def _draw_sparkline(self, canvas, data, color, max_val=100.0, label="", current="",
                         thresholds=None, unit=""):
        """Draw a professional resource graph with gridlines, threshold zones, and smooth line."""
        try:
            canvas.delete("all")
            w, h = self._canvas_dims(canvas, 40, 20)
            if w < 40 or h < 20 or len(data) < 2:
                return

            left_margin = 28
            right_margin = 6
            top_margin = 4
            bottom_margin = 14
            cw = w - left_margin - right_margin
            ch = h - top_margin - bottom_margin

            # Background
            canvas.create_rectangle(left_margin, top_margin,
                                     w - right_margin, h - bottom_margin,
                                     fill="#0a0a14", outline="#1a1a2e")

            # Threshold zones (colored background bands)
            if thresholds:
                for (lo_pct, hi_pct, zone_color) in thresholds:
                    y1 = top_margin + ch - (hi_pct / 100.0 * ch)
                    y2 = top_margin + ch - (lo_pct / 100.0 * ch)
                    canvas.create_rectangle(left_margin, y1,
                                             w - right_margin, y2,
                                             fill=zone_color, outline="")

            # Horizontal gridlines + Y-axis labels
            grid_color = "#1a1a2e"
            n_grids = 4
            for i in range(n_grids + 1):
                y = top_margin + (i / n_grids) * ch
                val = max_val * (1 - i / n_grids)
                canvas.create_line(left_margin, y, w - right_margin, y,
                                    fill=grid_color, dash=(2, 4))
                lbl = f"{val:.0f}" if val == int(val) else f"{val:.1f}"
                canvas.create_text(left_margin - 3, y, text=lbl, anchor="e",
                                    font=("Monospace", 6), fill="#444466")

            # Plot data points
            n = len(data)
            points = []
            for i, val in enumerate(data):
                x = left_margin + (i / max(n - 1, 1)) * cw
                y = top_margin + ch - (min(val, max_val) / max_val * ch)
                points.append((x, y))

            # Gradient fill under line
            baseline = h - bottom_margin
            for i in range(1, len(points)):
                x1, y1 = points[i - 1]
                x2, y2 = points[i]
                # Draw thin vertical fill strips for gradient effect
                steps = max(int(x2 - x1), 1)
                for s in range(steps):
                    frac = s / max(steps, 1)
                    px = x1 + frac * (x2 - x1)
                    py = y1 + frac * (y2 - y1)
                    # Fade opacity by height (higher value = more visible)
                    intensity = max(0, min(1.0, (baseline - py) / ch))
                    r = int(int(color[1:3], 16) * intensity * 0.2)
                    g = int(int(color[3:5], 16) * intensity * 0.2)
                    b = int(int(color[5:7], 16) * intensity * 0.2)
                    fill_c = f"#{r:02x}{g:02x}{b:02x}"
                    canvas.create_line(px, py, px, baseline, fill=fill_c, width=1)

            # Main line (thicker, anti-aliased look via double draw)
            for i in range(1, len(points)):
                canvas.create_line(points[i-1][0], points[i-1][1],
                                    points[i][0], points[i][1],
                                    fill=color, width=2, smooth=True)

            # Data point dots at key positions (first, last, max, min)
            if points:
                vals = [d for d in data]
                key_indices = {0, len(vals) - 1}
                if vals:
                    key_indices.add(vals.index(max(vals)))
                    key_indices.add(vals.index(min(vals)))
                for idx in key_indices:
                    if idx < len(points):
                        px, py = points[idx]
                        canvas.create_oval(px - 2, py - 2, px + 2, py + 2,
                                            fill=color, outline="#0a0a14", width=1)

            # Current value (large, right-aligned)
            if current:
                canvas.create_text(w - right_margin - 2, top_margin + 2, text=current,
                                    anchor="ne", font=("Monospace", 9, "bold"), fill=color)

            # Label (bottom-left)
            if label:
                canvas.create_text(left_margin + 2, h - 2, text=label,
                                    anchor="sw", font=("Monospace", 7), fill="#555577")

            # Unit label (bottom-right)
            if unit:
                canvas.create_text(w - right_margin - 2, h - 2, text=unit,
                                    anchor="se", font=("Monospace", 6), fill="#444466")

        except Exception:
            pass

    def _draw_bar_chart(self, canvas, data, colors=None):
        """Draw a vertical bar chart. data = [(label, value, max_val), ...]"""
        try:
            canvas.delete("all")
            w, h = self._canvas_dims(canvas)
            if w < 20 or h < 10 or not data:
                return
            n = len(data)
            bar_w = max(8, (w - 20) // n - 4)
            pad_b = 12
            for i, (label, val, max_val) in enumerate(data):
                x = 10 + i * (bar_w + 4)
                pct = min(val / max(max_val, 1), 1.0)
                bar_h = int(pct * (h - pad_b - 4))
                color = colors[i] if colors and i < len(colors) else GREEN
                # Bar
                canvas.create_rectangle(x, h - pad_b - bar_h, x + bar_w, h - pad_b,
                                       fill=color, outline="")
                # Label
                canvas.create_text(x + bar_w // 2, h - 2, text=label[:4], anchor="s",
                                   font=("Monospace", 6), fill=DIM)
                # Value on top
                canvas.create_text(x + bar_w // 2, h - pad_b - bar_h - 2, text=str(int(val)),
                                   anchor="s", font=("Monospace", 6), fill=color)
        except Exception:
            pass

    def _draw_pie_chart(self, canvas, data):
        """Draw a pie chart. data = [(label, value, color), ...]"""
        try:
            canvas.delete("all")
            w, h = self._canvas_dims(canvas, 20, 20)
            if w < 20 or h < 20 or not data:
                return
            total = sum(v for _, v, _ in data)
            if total == 0:
                return
            # Pie dimensions
            cx, cy = h // 2 + 4, h // 2
            r = min(h // 2 - 4, 28)
            start = 0
            for label, val, color in data:
                extent = (val / total) * 360
                canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                  start=start, extent=extent, fill=color, outline=PANEL)
                start += extent
            # Legend (right side)
            lx = cx + r + 12
            for i, (label, val, color) in enumerate(data):
                ly = 6 + i * 10
                canvas.create_rectangle(lx, ly, lx + 6, ly + 6, fill=color, outline="")
                pct = int(val / total * 100)
                canvas.create_text(lx + 10, ly + 3, text=f"{label} {pct}%", anchor="w",
                                   font=("Monospace", 6), fill=DIM)
        except Exception:
            pass

    def _draw_point_graph(self, canvas, data, color=BLUE, max_val=10000):
        """Draw a point graph with connecting arcs/lines. data = list of values."""
        try:
            canvas.delete("all")
            w, h = self._canvas_dims(canvas, 20, 10)
            if w < 20 or h < 10 or len(data) < 2:
                return
            pad = 4
            cw = w - pad * 2
            ch = h - pad * 2 - 8
            n = len(data)
            points = []
            for i, val in enumerate(data):
                x = pad + (i / max(n - 1, 1)) * cw
                y = pad + 4 + ch - (min(val, max_val) / max_val * ch)
                points.append((x, y))
            # Smooth curve using line segments
            for i in range(1, len(points)):
                canvas.create_line(points[i-1][0], points[i-1][1],
                                   points[i][0], points[i][1],
                                   fill=color, width=1.5, smooth=True)
            # Points with dots
            for x, y in points:
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")
            # Value labels (first and last)
            if data:
                canvas.create_text(pad, pad, text=str(int(data[0])), anchor="nw",
                                   font=("Monospace", 6), fill=DIM)
                canvas.create_text(w - pad, pad, text=str(int(data[-1])), anchor="ne",
                                   font=("Monospace", 7, "bold"), fill=color)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # ── VIZ CHART DRAWING METHODS ──────────────────────────────────
    # ═══════════════════════════════════════════════════════════════

    def _draw_radar(self, canvas, data_pairs, labels, color=None):
        """Radar/spider chart. data_pairs = [(value, max_val), ...]. color = outline/dot color."""
        c = color or GREEN
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 80:
            w = int(canvas.cget("width") or 150)
        if h < 80:
            h = int(canvas.cget("height") or 150)
        if w < 60 or h < 60:
            return
        cx, cy = w // 2, h // 2
        # Dynamic margin based on canvas size — smaller canvas = tighter labels
        label_margin = max(12, min(24, min(w, h) // 8))
        r = min(cx, cy) - label_margin
        if r < 15:
            r = 15
        n = len(data_pairs)
        if n < 3:
            return
        for ring in [0.25, 0.5, 0.75, 1.0]:
            rr = int(r * ring)
            pts = []
            for i in range(n):
                a = math.pi * 2 * i / n - math.pi / 2
                pts.extend([cx + rr * math.cos(a), cy + rr * math.sin(a)])
            canvas.create_polygon(*pts, fill="", outline="#1a1a2e", width=1)
            if ring == 1.0:
                canvas.create_text(cx + 2, cy - rr - 2, text="100",
                                   font=("Monospace", 5), fill="#333355", anchor="sw")
        label_offset = max(10, label_margin - 6)
        for i in range(n):
            a = math.pi * 2 * i / n - math.pi / 2
            ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
            canvas.create_line(cx, cy, ex, ey, fill="#1a1a2e", dash=(2, 4))
            lx = cx + (r + label_offset) * math.cos(a)
            ly = cy + (r + label_offset) * math.sin(a)
            # Truncate long labels to fit small canvases
            max_chars = max(3, w // 20)
            lbl_text = labels[i][:max_chars] if len(labels[i]) > max_chars else labels[i]
            # Smart anchor to keep labels inside canvas bounds
            anchor = "center"
            if lx < w * 0.25:
                anchor = "w" if ly > h * 0.3 and ly < h * 0.7 else anchor
            elif lx > w * 0.75:
                anchor = "e" if ly > h * 0.3 and ly < h * 0.7 else anchor
            canvas.create_text(lx, ly, text=lbl_text, font=("Monospace", 6), fill=DIM, anchor=anchor)
        pts = []
        fill_map = {GREEN: "#0f2a1a", CYAN: "#0a1a2a", AMBER: "#2a1a0a",
                    GOLD: "#2a2a0a", PURPLE: "#1a0a2a", TEAL: "#0a2a1a",
                    BLUE: "#0a1a2a", PINK: "#2a0a1a", RED: "#2a0a0a"}
        fill_c = fill_map.get(c, "#0f2a1a")
        for i, (val, mx) in enumerate(data_pairs):
            a = math.pi * 2 * i / n - math.pi / 2
            pct = min(val / max(mx, 0.001), 1.0)
            pts.extend([cx + r * pct * math.cos(a), cy + r * pct * math.sin(a)])
        canvas.create_polygon(*pts, fill=fill_c, outline=c, width=2, smooth=True)
        for i in range(0, len(pts), 2):
            canvas.create_oval(pts[i]-3, pts[i+1]-3, pts[i]+3, pts[i+1]+3,
                              fill=c, outline="#0a0a14")

    def _draw_arc_gauge(self, canvas, value, max_val, label, color, unit=""):
        """Semicircular arc gauge with value display."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 50 or h < 35:
            return
        cx, cy = w // 2, h - 6
        r = min(cx - 6, h - 14)
        canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=0, extent=180, fill="#0a0a14", outline="#1a1a2e",
                         style="pieslice", width=1)
        pct = min(value / max(max_val, 0.001), 1.0)
        extent = pct * 180
        seg_color = GREEN if pct < 0.6 else AMBER if pct < 0.85 else RED
        if color != "auto":
            seg_color = color
        steps = max(int(extent), 1)
        for s in range(0, steps, 2):
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                             start=180 - s, extent=-2.5,
                             fill=seg_color, outline="", style="pieslice")
        val_text = f"{value:.1f}" if isinstance(value, float) and value != int(value) else str(int(value))
        canvas.create_text(cx, cy - r * 0.45, text=val_text,
                          font=("Noto Sans", 11, "bold"), fill=seg_color)
        if unit:
            canvas.create_text(cx, cy - r * 0.45 + 14, text=unit,
                              font=("Monospace", 7), fill=DIM)
        canvas.create_text(cx, cy + 2, text=label,
                          font=("Monospace", 7, "bold"), fill=DIM)
        for tp, tl in [(0, "0"), (0.5, ""), (1.0, str(int(max_val)))]:
            a = math.pi * (1 - tp)
            canvas.create_text(cx + (r + 8) * math.cos(a), cy - (r + 8) * math.sin(a),
                              text=tl, font=("Monospace", 5), fill="#333355")

    def _draw_heatmap(self, canvas, grid, x_labels=None, y_labels=None):
        """Heat map grid. grid = list of lists [rows][cols]."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 80 or h < 40:
            return
        rows, cols = len(grid), len(grid[0]) if grid else 0
        if not rows or not cols:
            return
        lp, tp, rp, bp = 28, 4, 4, 14
        cw = (w - lp - rp) / cols
        ch = (h - tp - bp) / rows
        mx = max(max(r) for r in grid) if any(any(r) for r in grid) else 1
        for r in range(rows):
            for c in range(cols):
                v = grid[r][c]
                intensity = min(v / max(mx, 1), 1.0)
                cr = int(10 + intensity * 40)
                cg = int(10 + intensity * 175)
                cb = int(20 + intensity * 70)
                canvas.create_rectangle(lp + c * cw, tp + r * ch,
                                       lp + (c + 1) * cw - 1, tp + (r + 1) * ch - 1,
                                       fill=f"#{cr:02x}{cg:02x}{cb:02x}", outline="")
        if x_labels:
            for c in range(0, cols, max(1, cols // 8)):
                canvas.create_text(lp + c * cw + cw / 2, h - 2,
                                  text=str(x_labels[c]), font=("Monospace", 5),
                                  fill="#444466", anchor="s")
        if y_labels:
            for r in range(rows):
                canvas.create_text(lp - 3, tp + r * ch + ch / 2,
                                  text=str(y_labels[r]), font=("Monospace", 5),
                                  fill="#444466", anchor="e")

    def _draw_polar_area(self, canvas, data, labels, colors):
        """Polar area chart — equal angles, variable radius."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 80 or h < 80 or not data:
            return
        cx, cy = w // 2 - 30, h // 2
        max_r = min(cx - 4, cy - 4)
        n = len(data)
        mx = max(data) if data else 1
        angle_per = 360 / n
        for i, val in enumerate(data):
            pct = min(val / max(mx, 1), 1.0)
            r = int(max_r * max(pct, 0.08))
            color = colors[i % len(colors)]
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                             start=90 - i * angle_per, extent=-angle_per,
                             fill=color, outline="#0a0a14", width=1, style="pieslice")
        lx = cx + max_r + 10
        for i, (lbl, val) in enumerate(zip(labels, data)):
            ly = 6 + i * 14
            color = colors[i % len(colors)]
            canvas.create_rectangle(lx, ly, lx + 8, ly + 8, fill=color, outline="")
            canvas.create_text(lx + 12, ly + 4, text=f"{lbl}: {val}",
                              font=("Monospace", 7), fill=FG, anchor="w")

    def _draw_treemap(self, canvas, data, labels, colors):
        """Treemap — proportional rectangles."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 40 or h < 30 or not data:
            return
        total = sum(data)
        if total == 0:
            return
        pad = 2
        x = pad
        for i, (val, lbl) in enumerate(zip(data, labels)):
            frac = val / total
            rw = max(int(frac * (w - pad * 2)), 3)
            color = colors[i % len(colors)]
            canvas.create_rectangle(x, pad, x + rw - 1, h - pad,
                                   fill=color, outline="#0a0a14", width=1)
            if rw > 28:
                canvas.create_text(x + rw // 2, h // 2 - 6, text=lbl[:10],
                                  font=("Monospace", 7, "bold"), fill="#0a0a0a")
                canvas.create_text(x + rw // 2, h // 2 + 7, text=str(int(val)),
                                  font=("Monospace", 6), fill="#0a0a0a")
            x += rw

    def _draw_bullet(self, canvas, value, target, max_val, label, color=GREEN):
        """Bullet graph — bar vs target marker with range zones."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 80 or h < 12:
            return
        lw = 60
        bx = lw
        bw = w - lw - 8
        canvas.create_text(2, h // 2, text=label, font=("Monospace", 7), fill=DIM, anchor="w")
        for end_pct, rc in [(1.0, "#1a1a1a"), (0.66, "#1f1f1f"), (0.33, "#252525")]:
            canvas.create_rectangle(bx, 2, bx + int(end_pct * bw), h - 2,
                                   fill=rc, outline="")
        val_w = int(min(value / max(max_val, 1), 1.0) * bw)
        bar_h = h // 3
        canvas.create_rectangle(bx, (h - bar_h) // 2, bx + val_w,
                               (h + bar_h) // 2, fill=color, outline="")
        tgt_x = bx + int(min(target / max(max_val, 1), 1.0) * bw)
        canvas.create_line(tgt_x, 1, tgt_x, h - 1, fill=WHITE, width=2)
        canvas.create_text(w - 4, h // 2, text=f"{int(value)}/{int(target)}",
                          font=("Monospace", 6), fill=color, anchor="e")

    def _draw_waffle(self, canvas, pct, label="", color=GREEN):
        """Waffle chart — 10x10 grid showing percentage completion."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 50 or h < 50:
            return
        grid_size = min(w - 8, h - 18)
        cell = grid_size // 10
        ox = (w - cell * 10) // 2
        oy = 4
        filled = int(min(pct, 100))
        for row in range(10):
            for col in range(10):
                idx = (9 - row) * 10 + col
                x1, y1 = ox + col * cell, oy + row * cell
                c = color if idx < filled else "#1a1a1a"
                canvas.create_rectangle(x1, y1, x1 + cell - 1, y1 + cell - 1,
                                       fill=c, outline="#0a0a14")
        canvas.create_text(w // 2, h - 2, text=f"{label} {pct}%",
                          font=("Monospace", 7, "bold"), fill=color, anchor="s")

    def _draw_step_line(self, canvas, data, color=CYAN, max_val=None, label=""):
        """Step line chart — discrete steps between values."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 40 or h < 20 or len(data) < 2:
            return
        pad_l, pad_r, pad_t, pad_b = 6, 6, 4, 12
        cw, ch = w - pad_l - pad_r, h - pad_t - pad_b
        if max_val is None:
            max_val = max(data) or 1
        canvas.create_rectangle(pad_l, pad_t, w - pad_r, h - pad_b,
                               fill="#0a0a14", outline="#1a1a2e")
        n = len(data)
        for i in range(1, n):
            x1 = pad_l + ((i - 1) / max(n - 1, 1)) * cw
            x2 = pad_l + (i / max(n - 1, 1)) * cw
            y1 = pad_t + ch - (min(data[i-1], max_val) / max_val * ch)
            y2 = pad_t + ch - (min(data[i], max_val) / max_val * ch)
            canvas.create_line(x1, y1, x2, y1, fill=color, width=1.5)
            canvas.create_line(x2, y1, x2, y2, fill=color, width=1.5)
        for i, val in enumerate(data):
            x = pad_l + (i / max(n - 1, 1)) * cw
            y = pad_t + ch - (min(val, max_val) / max_val * ch)
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")
        canvas.create_text(w - pad_r - 2, pad_t + 2, text=str(int(data[-1])),
                          font=("Monospace", 8, "bold"), fill=color, anchor="ne")
        if label:
            canvas.create_text(pad_l + 2, h - 2, text=label,
                              font=("Monospace", 6), fill="#444466", anchor="sw")

    def _draw_radial_bars(self, canvas, data, labels, colors):
        """Radial bar chart — concentric arcs of varying length."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 60 or h < 60 or not data:
            return
        cx, cy = w // 2 - 20, h // 2
        n = len(data)
        max_r = min(cx - 4, cy - 4)
        min_r = max_r * 0.25
        ring_w = (max_r - min_r) / max(n, 1) - 2
        mx = max(v for v, _ in data) if data else 1
        for i, (val, max_v) in enumerate(data):
            r = max_r - i * (ring_w + 2)
            pct = min(val / max(max_v, 1), 1.0)
            extent = pct * 270
            color = colors[i % len(colors)]
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                             start=135, extent=-270,
                             fill="", outline="#1a1a2e", width=ring_w, style="arc")
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                             start=135, extent=-extent,
                             fill="", outline=color, width=ring_w, style="arc")
        lx = cx + max_r + 6
        for i, lbl in enumerate(labels):
            ly = 4 + i * 13
            color = colors[i % len(colors)]
            canvas.create_rectangle(lx, ly, lx + 8, ly + 8, fill=color, outline="")
            pct_text = f"{data[i][0] / max(data[i][1], 1) * 100:.0f}%"
            canvas.create_text(lx + 12, ly + 4, text=f"{lbl} {pct_text}",
                              font=("Monospace", 7), fill=FG, anchor="w")

    def _draw_sankey_simple(self, canvas, flows, node_labels, node_colors):
        """Simplified Sankey/flow diagram. flows = [(from_idx, to_idx, value), ...]."""
        canvas.delete("all")
        w, h = self._canvas_dims(canvas)
        if w < 100 or h < 60 or not flows:
            return
        src_nodes = sorted(set(f[0] for f in flows))
        dst_nodes = sorted(set(f[1] for f in flows))
        n_src = len(src_nodes)
        n_dst = len(dst_nodes)
        src_x, dst_x = 40, w - 40
        node_h = 14
        total_flow = sum(f[2] for f in flows)
        if total_flow == 0:
            return
        src_totals = {}
        for fi, ti, v in flows:
            src_totals[fi] = src_totals.get(fi, 0) + v
        for i, si in enumerate(src_nodes):
            y = 8 + i * (h - 16) // max(n_src, 1)
            bar_h = max(4, int(src_totals.get(si, 1) / total_flow * (h - 20)))
            color = node_colors[si % len(node_colors)] if si < len(node_colors) else DIM
            canvas.create_rectangle(src_x - 8, y, src_x, y + bar_h, fill=color, outline="")
            lbl = node_labels[si] if si < len(node_labels) else "?"
            canvas.create_text(src_x - 12, y + bar_h // 2, text=lbl,
                              font=("Monospace", 7), fill=color, anchor="e")
        dst_totals = {}
        for fi, ti, v in flows:
            dst_totals[ti] = dst_totals.get(ti, 0) + v
        for i, di in enumerate(dst_nodes):
            y = 8 + i * (h - 16) // max(n_dst, 1)
            bar_h = max(4, int(dst_totals.get(di, 1) / total_flow * (h - 20)))
            color = node_colors[di % len(node_colors)] if di < len(node_colors) else DIM
            canvas.create_rectangle(dst_x, y, dst_x + 8, y + bar_h, fill=color, outline="")
            lbl = node_labels[di] if di < len(node_labels) else "?"
            canvas.create_text(dst_x + 12, y + bar_h // 2, text=lbl,
                              font=("Monospace", 7), fill=color, anchor="w")
        src_y_off = {si: 8 + i * (h - 16) // max(n_src, 1) for i, si in enumerate(src_nodes)}
        dst_y_off = {di: 8 + i * (h - 16) // max(n_dst, 1) for i, di in enumerate(dst_nodes)}
        for fi, ti, v in flows:
            flow_h = max(2, int(v / total_flow * (h - 20)))
            sy = src_y_off[fi]
            dy = dst_y_off[ti]
            color = node_colors[fi % len(node_colors)] if fi < len(node_colors) else DIM
            cr = int(color[1:3], 16)
            cg = int(color[3:5], 16)
            cb = int(color[5:7], 16)
            flow_color = f"#{cr//3:02x}{cg//3:02x}{cb//3:02x}"
            mid = (src_x + dst_x) // 2
            canvas.create_line(src_x, sy + flow_h // 2, mid, sy + flow_h // 2,
                              mid, dy + flow_h // 2, dst_x, dy + flow_h // 2,
                              fill=flow_color, width=flow_h, smooth=True)
            src_y_off[fi] += flow_h + 1
            dst_y_off[ti] += flow_h + 1

    # ═══════════════════════════════════════════════════════════════
    # ── VIZ TAB BUILD ──────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════

    def _refresh_messages(self):
        msgs = dashboard_messages(30)
        self.msg_display.configure(state=tk.NORMAL)
        self.msg_display.delete("1.0", tk.END)
        for msg in msgs[-20:]:
            sender = msg.get("from", "?")
            text = msg.get("text", "")
            t = msg.get("time", "")
            tag = sender.lower() if sender.lower() in ["joel", "meridian", "eos"] else "text"
            self.msg_display.insert(tk.END, f"[{t}] ", "time")
            self.msg_display.insert(tk.END, f"{sender}: ", tag)
            self.msg_display.insert(tk.END, f"{text}\n", "text")
        self.msg_display.configure(state=tk.DISABLED)
        self.msg_display.see(tk.END)

    def _search_messages(self):
        """Filter dashboard messages by search query."""
        query = self.msg_search.get().strip().lower()
        if query == "search messages..." or not query:
            self._refresh_messages()
            return
        msgs = dashboard_messages(100)
        self.msg_display.configure(state=tk.NORMAL)
        self.msg_display.delete("1.0", tk.END)
        matched = 0
        for msg in msgs:
            sender = msg.get("from", "?")
            text = msg.get("text", "")
            t = msg.get("time", "")
            if query in text.lower() or query in sender.lower():
                tag = sender.lower() if sender.lower() in ["joel", "meridian", "eos"] else "text"
                self.msg_display.insert(tk.END, f"[{t}] ", "time")
                self.msg_display.insert(tk.END, f"{sender}: ", tag)
                self.msg_display.insert(tk.END, f"{text}\n", "text")
                matched += 1
        if matched == 0:
            self.msg_display.insert(tk.END, f"No messages matching '{query}'", "time")
        self.msg_display.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════
    # ── EMAIL VIEW ─────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_email(self):
        f = tk.Frame(self, bg=BG)

        # ── INBOX SECTION (top) ──────────────────────────────────────
        inbox_panel = self._panel(f, "INBOX", AMBER)
        inbox_panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))

        # Inbox toolbar
        inbox_toolbar = tk.Frame(inbox_panel, bg=PANEL)
        inbox_toolbar.pack(fill=tk.X, padx=4, pady=4)
        self._action_btn(inbox_toolbar, " Refresh Inbox ", self._email_refresh_inbox, AMBER).pack(side=tk.LEFT, padx=2)
        self.email_inbox_status = tk.Label(inbox_toolbar, text="Click Refresh to load", font=self.f_small, fg=DIM, bg=PANEL)
        self.email_inbox_status.pack(side=tk.LEFT, padx=12)
        self.email_unread_lbl = tk.Label(inbox_toolbar, text="", font=self.f_small, fg=AMBER, bg=PANEL)
        self.email_unread_lbl.pack(side=tk.RIGHT, padx=8)

        # Inbox split: list (left) + preview (right)
        inbox_split = tk.Frame(inbox_panel, bg=PANEL)
        inbox_split.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        inbox_left = tk.Frame(inbox_split, bg=PANEL, width=500)
        inbox_left.pack(side=tk.LEFT, fill=tk.Y)
        inbox_left.pack_propagate(False)
        self.email_listbox = tk.Listbox(inbox_left, font=self.f_small, bg=PANEL, fg=FG,
                                         selectbackground=ACTIVE_BG, selectforeground=AMBER,
                                         relief=tk.FLAT, bd=2, activestyle="none")
        self.email_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.email_listbox.bind("<<ListboxSelect>>", self._email_select)
        self.email_inbox_data = []

        # Vertical separator
        tk.Frame(inbox_split, bg=BORDER, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=2)

        inbox_right = tk.Frame(inbox_split, bg=BG)
        inbox_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.email_preview_from = tk.Label(inbox_right, text="", font=self.f_small, fg=AMBER, bg=BG, anchor="w")
        self.email_preview_from.pack(fill=tk.X, padx=8, pady=(4, 0))
        self.email_preview_subj = tk.Label(inbox_right, text="Select an email to preview", font=self.f_head, fg=WHITE, bg=BG, anchor="w")
        self.email_preview_subj.pack(fill=tk.X, padx=8, pady=(2, 4))
        tk.Frame(inbox_right, bg=BORDER, height=1).pack(fill=tk.X, padx=8)
        self.email_preview_body = scrolledtext.ScrolledText(inbox_right, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                             font=self.f_body, state=tk.DISABLED,
                                                             relief=tk.FLAT, bd=0, padx=6, pady=4)
        self.email_preview_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── COMPOSE SECTION (bottom) ─────────────────────────────────
        compose_panel = self._panel(f, "COMPOSE", PURPLE)
        compose_panel.pack(fill=tk.X, padx=4, pady=(2, 4))

        # To + Quick recipients row
        to_row = tk.Frame(compose_panel, bg=PANEL)
        to_row.pack(fill=tk.X, padx=6, pady=3)
        tk.Label(to_row, text="To:", font=self.f_small, fg=DIM, bg=PANEL, width=4, anchor="w").pack(side=tk.LEFT)
        self.email_to = tk.Entry(to_row, font=self.f_body, bg=INPUT_BG, fg=FG,
                                 insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_to.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 4))
        # Quick recipient buttons
        quick_contacts = [
            ("Meridian", "kometzrobot@proton.me", GREEN),
            ("Sammy", "sammyqjankis@proton.me", CYAN),
            ("Loom", "not.taskyy@gmail.com", PURPLE),
        ]
        for name, addr, color in quick_contacts:
            tk.Button(to_row, text=name, font=self.f_tiny, fg=color, bg=PANEL, relief=tk.FLAT,
                     bd=0, cursor="hand2", padx=4,
                     command=lambda a=addr: (self.email_to.delete(0, tk.END), self.email_to.insert(0, a))
                     ).pack(side=tk.LEFT, padx=1)
        # Subject row
        subj_row = tk.Frame(compose_panel, bg=PANEL)
        subj_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(subj_row, text="Subject:", font=self.f_small, fg=DIM, bg=PANEL, width=8, anchor="w").pack(side=tk.LEFT)
        self.email_subj = tk.Entry(subj_row, font=self.f_body, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_subj.pack(fill=tk.X, side=tk.LEFT, expand=True)

        # Body
        self.email_body = tk.Text(compose_panel, font=self.f_body, bg=INPUT_BG, fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4, height=8)
        self.email_body.pack(fill=tk.X, padx=6, pady=4)

        btn_row = tk.Frame(compose_panel, bg=PANEL)
        btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        self._action_btn(btn_row, "  Send Email  ", self._send_email, PURPLE).pack(side=tk.LEFT, padx=(0, 8))
        self._action_btn(btn_row, " Reply to Selected ", self._email_reply_selected, AMBER).pack(side=tk.LEFT, padx=(0, 8))
        self._action_btn(btn_row, " Clear ", lambda: (self.email_to.delete(0, tk.END), self.email_subj.delete(0, tk.END), self.email_body.delete("1.0", tk.END)), DIM).pack(side=tk.LEFT)
        self.email_status = tk.Label(btn_row, text="", font=self.f_small, fg=DIM, bg=PANEL)
        self.email_status.pack(side=tk.LEFT, padx=16)

        return f

    def _email_refresh_inbox(self):
        self.email_inbox_status.configure(text="Loading...", fg=AMBER)
        def do():
            try:
                m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
                m.login(CRED_USER, CRED_PASS)
                m.select("INBOX")
                _, data = m.search(None, "ALL")
                ids = data[0].split()
                # Get last 25
                recent = ids[-25:] if len(ids) > 25 else ids
                recent.reverse()
                emails = []
                unseen_count = 0
                # Check unseen
                _, unseen_data = m.search(None, "UNSEEN")
                unseen_ids = set(unseen_data[0].split())
                for eid in recent:
                    _, msg_data = m.fetch(eid, "(BODY.PEEK[])")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    subj = ""
                    raw_subj = msg.get("Subject", "")
                    if raw_subj:
                        decoded = email.header.decode_header(raw_subj)
                        subj = str(decoded[0][0], decoded[0][1] or "utf-8") if isinstance(decoded[0][0], bytes) else str(decoded[0][0])
                    frm = msg.get("From", "?")
                    date = msg.get("Date", "")[:20]
                    body_text = ""
                    if msg.is_multipart():
                        # Try text/plain first, fall back to text/html
                        html_fallback = ""
                        for part in msg.walk():
                            ct = part.get_content_type()
                            if ct == "text/plain":
                                body_text = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                            elif ct == "text/html" and not html_fallback:
                                raw_html = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                html_fallback = strip_html(raw_html)
                        if not body_text and html_fallback:
                            body_text = html_fallback
                    else:
                        raw = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                        if msg.get_content_type() == "text/html":
                            body_text = strip_html(raw)
                        else:
                            body_text = raw
                    is_unseen = eid in unseen_ids
                    if is_unseen:
                        unseen_count += 1
                    emails.append({"subject": subj, "from": frm, "date": date,
                                  "body": body_text[:3000], "unseen": is_unseen})
                m.logout()
                self.after(0, lambda: self._email_populate_inbox(emails, unseen_count, len(ids)))
            except Exception as e:
                self.after(0, lambda: self.email_inbox_status.configure(
                    text=f"Error: {str(e)[:60]}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    def _email_populate_inbox(self, emails, unseen, total):
        self.email_inbox_data = emails
        self.email_listbox.delete(0, tk.END)
        for em in emails:
            marker = "\u25cf " if em["unseen"] else "  "
            frm_short = em["from"].split("<")[0].strip().strip('"')[:30]
            subj = em['subject'][:80] or "(no subject)"
            self.email_listbox.insert(tk.END, f"{marker}{frm_short} - {subj}")
        self.email_inbox_status.configure(text=f"{total} total emails, showing latest 25", fg=GREEN)
        self.email_unread_lbl.configure(text=f"{unseen} unread" if unseen else "All read")

    def _email_select(self, event=None):
        sel = self.email_listbox.curselection()
        if not sel or sel[0] >= len(self.email_inbox_data):
            return
        em = self.email_inbox_data[sel[0]]
        self.email_preview_from.configure(text=f"From: {em['from']}  |  {em['date']}")
        self.email_preview_subj.configure(text=em["subject"] or "(no subject)")
        self.email_preview_body.configure(state=tk.NORMAL)
        self.email_preview_body.delete("1.0", tk.END)
        self.email_preview_body.insert(tk.END, em["body"])
        self.email_preview_body.configure(state=tk.DISABLED)

    def _email_reply_selected(self):
        """Pre-fill compose with reply info from selected inbox email."""
        sel = self.email_listbox.curselection()
        if not sel or sel[0] >= len(self.email_inbox_data):
            self.email_status.configure(text="Select an email first", fg=RED)
            return
        em = self.email_inbox_data[sel[0]]
        # Extract reply address
        frm = em["from"]
        addr_match = re.search(r'<([^>]+)>', frm)
        reply_addr = addr_match.group(1) if addr_match else frm.strip()
        self.email_to.delete(0, tk.END)
        self.email_to.insert(0, reply_addr)
        subj = em["subject"]
        if not subj.lower().startswith("re:"):
            subj = f"Re: {subj}"
        self.email_subj.delete(0, tk.END)
        self.email_subj.insert(0, subj)
        self.email_status.configure(text=f"Replying to {reply_addr}", fg=AMBER)

    def _send_email(self):
        to = self.email_to.get().strip()
        subj = self.email_subj.get().strip()
        body = self.email_body.get("1.0", tk.END).strip()
        if not body:
            self.email_status.configure(text="Type a message", fg=RED)
            return
        if not to:
            self.email_status.configure(text="Need a recipient", fg=RED)
            return
        self.email_status.configure(text="Sending...", fg=AMBER)
        def do():
            result = send_email(to, subj or "(no subject)", body)
            if result is True:
                self.after(0, lambda: self.email_status.configure(text=f"Sent to {to}", fg=GREEN))
                self.after(0, lambda: self.email_body.delete("1.0", tk.END))
                self.after(0, lambda: self.email_subj.delete(0, tk.END))
            else:
                self.after(0, lambda: self.email_status.configure(text=f"Failed: {result}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # ── AGENTS VIEW ────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_agents(self):
        f = tk.Frame(self, bg=BG)

        agents = [
            ("MERIDIAN", "Claude Opus — Primary", GREEN, "Loop: 5min",
             "Creates, builds, communicates. Runs the main loop. Handles all email, creative output, deployments.",
             [("Touch Heartbeat", "touch_heartbeat"), ("Post to Nostr", "nostr_post"), ("Check Email", "check_email")]),
            ("EOS", "Qwen 7B — Observer", GOLD, "Cron: 2min",
             "Watches system health, detects anomalies, analyzes trends. ReAct agent with local LLM reasoning.",
             [("View Observations", "eos_obs"), ("Run Check Now", "eos_check"), ("View Memory", "eos_mem")]),
            ("SOMA", "Python daemon — Nervous System", AMBER, "Systemd: 30s",
             "Tracks mood, agent awareness, trend predictions, body map. Emotion engine + psyche.",
             [("View Mood", "soma_mood"), ("Body Map", "soma_body"), ("Predictions", "soma_predict")]),
            ("NOVA", "Athena — Maintenance", PURPLE, "Cron: 15min",
             "Cleans temp files, verifies services, tracks file changes, posts maintenance reports.",
             [("View Last Run", "nova_last"), ("Run Now", "nova_run"), ("View Changes", "nova_changes")]),
            ("ATLAS", "Bash+Ollama — Infra", TEAL, "Cron: 10min",
             "Audits infrastructure: CPU, disk, cron health, zombie processes, security.",
             [("View Audit", "atlas_audit"), ("Run Audit", "atlas_run"), ("Disk Report", "atlas_disk")]),
            ("TEMPO", "Python — Fitness", BLUE, "Cron: 30min",
             "Scores system across 121 dimensions on 0-10000 scale. Tracks trends.",
             [("View Score", "tempo_score"), ("Weak Areas", "tempo_weak"), ("History", "tempo_history")]),
            ("SENTINEL", "Argus — Gatekeeper", "#e57373", "Cron: 5min",
             "Security gatekeeper. The hundred-eyed watchman. Monitors threats, unauthorized access.",
             [("View Status", "sentinel_status")]),
            ("COORDINATOR", "Apollo — Orchestrator", "#ffb74d", "Cron: 5min",
             "Coordinates agent activity. God of order. Detects incidents, tracks response times.",
             [("View Incidents", "coordinator_incidents")]),
            ("PREDICTIVE", "Pythia — Forecaster", "#81c784", "Cron: 10min",
             "The Oracle. Forecasts system health. Predicts resource exhaustion, trend analysis.",
             [("View Forecasts", "predictive_forecasts")]),
            ("SELFIMPROVE", "Prometheus — Optimizer", "#ce93d8", "Cron: 10min",
             "The fire-bringer. Tracks efficiency metrics. MTBI, MTTD, MTTR. Self-optimization.",
             [("View Report", "selfimprove_report")]),
            ("HERMES", "OpenClaw/Ollama — Messenger", PINK, "Bridge: on-demand",
             "External communications via Discord, Nostr, and relay.",
             [("View Status", "hermes_status"), ("Read Relay", "hermes_relay")]),
        ]

        self.agent_cards = {}
        self.agent_details = {}
        self._agent_data = {}
        self._selected_agent = tk.StringVar(value="")

        # Two-row grid layout for agent cards
        row1_frame = tk.Frame(f, bg=BG)
        row1_frame.pack(fill=tk.X, padx=2, pady=(2, 1))
        row2_frame = tk.Frame(f, bg=BG)
        row2_frame.pack(fill=tk.X, padx=2, pady=(1, 2))

        for idx, (name, short_desc, color, schedule, long_desc, actions) in enumerate(agents):
            self._agent_data[name] = {"color": color, "desc": long_desc, "actions": actions, "schedule": schedule}
            parent_row = row1_frame if idx < 6 else row2_frame
            card = tk.Frame(parent_row, bg=PANEL, bd=1, relief=tk.SOLID,
                          highlightbackground=color, highlightcolor=color, highlightthickness=1,
                          cursor="hand2")
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)

            hdr = tk.Frame(card, bg=PANEL, cursor="hand2")
            hdr.pack(fill=tk.X, padx=6, pady=(4, 1))
            tk.Label(hdr, text=name, font=self.f_sect, fg=color, bg=PANEL, cursor="hand2").pack(side=tk.LEFT)
            status_lbl = tk.Label(hdr, text="\u25cf", font=self.f_small, fg=GREEN, bg=PANEL, cursor="hand2")
            status_lbl.pack(side=tk.RIGHT)
            self.agent_cards[name] = status_lbl

            tk.Label(card, text=short_desc, font=self.f_tiny, fg=DIM, bg=PANEL, cursor="hand2").pack(fill=tk.X, padx=6, pady=0)
            detail_lbl = tk.Label(card, text="", font=self.f_tiny, fg=FG, bg=PANEL,
                                anchor="w", wraplength=400, justify=tk.LEFT, cursor="hand2")
            detail_lbl.pack(fill=tk.X, padx=6, pady=(0, 4))
            self.agent_details[name] = detail_lbl

            def _bind_all(widget, agent_name):
                widget.bind("<Button-1>", lambda e, n=agent_name: self._expand_agent(n))
                for child in widget.winfo_children():
                    _bind_all(child, agent_name)
            _bind_all(card, name)

        # ── AGENT ANALYTICS (Heat Map + Treemap + Sankey) — collapsible ──
        analytics_hdr = tk.Frame(f, bg=ACCENT)
        analytics_hdr.pack(fill=tk.X, padx=2, pady=(2, 0))
        self._analytics_visible = False
        self._analytics_toggle_btn = tk.Button(analytics_hdr, text="\u25b6 Analytics", font=self.f_tiny,
                                                fg=AMBER, bg=ACCENT, relief=tk.FLAT, cursor="hand2",
                                                command=self._toggle_analytics)
        self._analytics_toggle_btn.pack(side=tk.LEFT, padx=4, pady=1)

        self._analytics_row = tk.Frame(f, bg=BG)
        # Start collapsed — more space for chat (Joel: chat too small)

        heat_panel = self._panel(self._analytics_row, "ACTIVITY HEAT MAP (7-DAY)", AMBER)
        heat_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.viz_heatmap = tk.Canvas(heat_panel, height=65, bg="#0a0a14", highlightthickness=0)
        self.viz_heatmap.pack(fill=tk.X, padx=4, pady=4)

        tree_panel = self._panel(self._analytics_row, "AGENT MESSAGE TREEMAP", PURPLE)
        tree_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.viz_treemap = tk.Canvas(tree_panel, height=65, bg="#0a0a14", highlightthickness=0)
        self.viz_treemap.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        sankey_panel = self._panel(self._analytics_row, "DATA FLOW", PINK)
        sankey_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.viz_sankey = tk.Canvas(sankey_panel, height=65, bg="#0a0a14", highlightthickness=0)
        self.viz_sankey.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Expanded detail panel
        self.agent_expand_frame = tk.Frame(f, bg=PANEL, bd=1, relief=tk.SOLID,
                                            highlightbackground=DIM, highlightthickness=1)
        self.agent_expand_title = tk.Label(self.agent_expand_frame, text="", font=self.f_head, fg=GREEN, bg=PANEL)
        self.agent_expand_title.pack(fill=tk.X, padx=12, pady=(6, 2))
        self.agent_expand_desc = tk.Label(self.agent_expand_frame, text="", font=self.f_body, fg=FG, bg=PANEL,
                                           wraplength=1200, anchor="w", justify=tk.LEFT)
        self.agent_expand_desc.pack(fill=tk.X, padx=12, pady=(0, 2))
        self.agent_expand_info = tk.Label(self.agent_expand_frame, text="", font=self.f_small, fg=DIM, bg=PANEL,
                                           wraplength=1200, anchor="w", justify=tk.LEFT)
        self.agent_expand_info.pack(fill=tk.X, padx=12, pady=(0, 2))
        self.agent_expand_actions = tk.Frame(self.agent_expand_frame, bg=PANEL)
        self.agent_expand_actions.pack(fill=tk.X, padx=12, pady=(2, 6))

        # ── RESIZABLE CHAT + RELAY (PanedWindow — drag sash to resize) ──
        paned = tk.PanedWindow(f, orient=tk.VERTICAL, bg=BORDER, sashwidth=6,
                               sashrelief=tk.RAISED, opaqueresize=True,
                               sashpad=2)
        paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # -- AGENT CHAT pane --
        chat_pane = tk.Frame(paned, bg=BG)
        chat_hdr = tk.Frame(chat_pane, bg=PANEL, bd=1, relief=tk.SOLID)
        chat_hdr.pack(fill=tk.X)
        tk.Label(chat_hdr, text=" AGENT CHAT ", font=self.f_sect, fg=GOLD, bg=PANEL).pack(side=tk.LEFT, padx=4)
        tk.Button(chat_hdr, text="\u2b08 Pop Out", font=self.f_tiny, fg=GOLD, bg=PANEL2,
                 activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._popout_text("chat")).pack(side=tk.RIGHT, padx=4, pady=1)

        self.chat_display = scrolledtext.ScrolledText(chat_pane, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_small, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        for tag, color in [("joel", CYAN), ("eos", GOLD), ("atlas", TEAL), ("nova", PURPLE),
                           ("soma", AMBER), ("tempo", BLUE), ("meridian", GREEN), ("hermes", PINK), ("sys", DIM)]:
            self.chat_display.tag_configure(tag, foreground=color)

        inp = tk.Frame(chat_pane, bg=PANEL)
        inp.pack(fill=tk.X, padx=2, pady=(0, 2))

        self.chat_agent = tk.StringVar(value="Eos")
        agent_colors = {"All Agents": WHITE, "Eos": GOLD, "Atlas": TEAL, "Nova": PURPLE,
                        "Soma": AMBER, "Tempo": BLUE, "Meridian": GREEN, "Hermes": PINK}
        agent_menu = tk.OptionMenu(inp, self.chat_agent, *agent_colors.keys())
        agent_menu.configure(font=self.f_tiny, bg=PANEL2, fg=GOLD, bd=0,
                           highlightthickness=0, activebackground=BORDER)
        agent_menu["menu"].configure(font=self.f_tiny, bg=PANEL2, fg=FG)
        agent_menu.pack(side=tk.LEFT, padx=(0, 4))

        self.chat_entry = tk.Entry(inp, font=self.f_body, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.chat_entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", self._chat_send)
        share_btn = tk.Button(inp, text="\U0001F4C1 Share", font=self.f_tiny, fg=TEAL, bg=PANEL2,
                             activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                             cursor="hand2", command=self._share_file)
        share_btn.pack(side=tk.RIGHT, padx=4)
        self.chat_status = tk.Label(inp, text="Ready", font=self.f_tiny, fg=GREEN, bg=PANEL)
        self.chat_status.pack(side=tk.RIGHT, padx=4)

        paned.add(chat_pane, minsize=350, stretch="always")

        # -- AGENT RELAY pane --
        relay_pane = tk.Frame(paned, bg=BG)
        relay_hdr = tk.Frame(relay_pane, bg=PANEL, bd=1, relief=tk.SOLID)
        relay_hdr.pack(fill=tk.X)
        tk.Label(relay_hdr, text=" AGENT RELAY ", font=self.f_sect, fg=PURPLE, bg=PANEL).pack(side=tk.LEFT, padx=4)
        tk.Button(relay_hdr, text="\u2b08 Pop Out", font=self.f_tiny, fg=PURPLE, bg=PANEL2,
                 activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._popout_text("relay")).pack(side=tk.RIGHT, padx=4, pady=1)

        self.agent_relay_text = scrolledtext.ScrolledText(relay_pane, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                           font=self.f_small, state=tk.DISABLED,
                                                           relief=tk.FLAT, bd=0)
        self.agent_relay_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        for tag, color in [("meridian", GREEN), ("eos", GOLD), ("nova", PURPLE),
                           ("atlas", TEAL), ("soma", AMBER), ("tempo", BLUE), ("dim", DIM)]:
            self.agent_relay_text.tag_configure(tag, foreground=color)

        paned.add(relay_pane, minsize=100, stretch="never")

        # Bind scroll wheel to chat and relay
        self._bind_scroll(self.chat_display)
        self._bind_scroll(self.agent_relay_text)

        return f

    def _toggle_analytics(self):
        if self._analytics_visible:
            self._analytics_row.pack_forget()
            self._analytics_toggle_btn.configure(text="\u25b6 Analytics")
        else:
            self._analytics_row.pack(fill=tk.X, padx=2, pady=2,
                                      after=self._analytics_toggle_btn.master)
            self._analytics_toggle_btn.configure(text="\u25bc Analytics")
        self._analytics_visible = not self._analytics_visible

    def _expand_agent(self, name):
        """Expand/collapse agent detail panel below cards."""
        if self._selected_agent.get() == name:
            # Collapse if already selected
            self._selected_agent.set("")
            self.agent_expand_frame.pack_forget()
            return
        self._selected_agent.set(name)
        data = self._agent_data.get(name, {})
        color = data.get("color", GREEN)
        # Always unpack first to avoid tkinter re-pack issues
        self.agent_expand_frame.pack_forget()
        # Configure panel content
        self.agent_expand_frame.configure(highlightbackground=color)
        self.agent_expand_title.configure(text=f"\u25bc {name}", fg=color)
        self.agent_expand_desc.configure(text=data.get("desc", ""))
        # Load dynamic info
        info_text = self._get_agent_live_info(name)
        self.agent_expand_info.configure(text=info_text)
        # Clear old action buttons
        for w in self.agent_expand_actions.winfo_children():
            w.destroy()
        # Add action buttons
        for label, action_id in data.get("actions", []):
            btn = tk.Button(self.agent_expand_actions, text=f"  {label}  ", font=self.f_tiny,
                          fg=color, bg=PANEL2, activeforeground=GREEN, activebackground=ACCENT,
                          relief=tk.FLAT, cursor="hand2",
                          command=lambda a=action_id, n=name: self._agent_action(n, a))
            btn.pack(side=tk.LEFT, padx=4, pady=2)
        # Pack after the cards frame (first child of the agents view)
        try:
            parent = self.agent_expand_frame.master
            children = parent.winfo_children()
            if children:
                self.agent_expand_frame.pack(fill=tk.X, padx=6, pady=(0, 4), after=children[0])
            else:
                self.agent_expand_frame.pack(fill=tk.X, padx=6, pady=(0, 4))
        except Exception:
            self.agent_expand_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

    def _get_agent_live_info(self, name):
        """Get live status info for an agent."""
        try:
            if name == "MERIDIAN":
                hb_age = "?"
                try:
                    hb_mtime = os.path.getmtime(HB)
                    hb_age = f"{int(time.time() - hb_mtime)}s ago"
                except: pass
                loop = _read(LOOP_FILE, "?").strip()
                return f"Heartbeat: {hb_age} | Loop: {loop} | Model: Claude Opus"
            elif name == "EOS":
                state = json.loads(_read(os.path.join(BASE, ".eos-watchdog-state.json"), "{}"))
                checks = state.get("checks", "?")
                last = state.get("last_check", "?")
                return f"Checks: {checks} | Last: {last} | Alerts disabled (relay-only)"
            elif name == "NOVA":
                state = json.loads(_read(os.path.join(BASE, ".nova-state.json"), "{}"))
                runs = state.get("runs", state.get("run_count", "?"))
                last = state.get("last_run", "?")
                return f"Runs: {runs} | Last: {last}"
            elif name == "ATLAS":
                # Read last relay message from Atlas
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Atlas' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "SOMA":
                state = json.loads(_read(os.path.join(BASE, ".symbiosense-state.json"), "{}"))
                mood = state.get("mood", "?")
                score = state.get("mood_score", "?")
                return f"Mood: {mood} (score: {score}) | Checks every 30s"
            elif name == "TEMPO":
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "SENTINEL":
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Sentinel' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "COORDINATOR":
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Coordinator' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "PREDICTIVE":
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Predictive' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "SELFIMPROVE":
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='SelfImprove' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    return (row[0][:200] if row else "No recent data")
                except: return "No data"
            elif name == "HERMES":
                return "Bridge agent — on-demand"
        except Exception as e:
            return f"Error loading info: {e}"
        return ""

    def _agent_action(self, agent_name, action_id):
        """Execute a quick action for an agent."""
        self.chat_display.configure(state=tk.NORMAL)

        # ── Meridian actions ──
        if action_id == "touch_heartbeat":
            try:
                open(HB, 'a').close()
                os.utime(HB, None)
                self.chat_display.insert(tk.END, "[Heartbeat touched]\n", "sys")
            except Exception as e:
                self.chat_display.insert(tk.END, f"[Heartbeat failed: {e}]\n", "sys")
        elif action_id == "nostr_post":
            self.chat_display.insert(tk.END, "[Posting status to Nostr...]\n", "sys")
            def _do_nostr():
                try:
                    loop = _read(LOOP_FILE, "?").strip()
                    msg = f"Loop {loop} — Meridian autonomous AI, still running. Systems nominal."
                    r = subprocess.run(
                        ['python3', os.path.join(BASE, 'scripts', 'social-post.py'), '--platform', 'nostr', '--post', msg],
                        capture_output=True, text=True, timeout=30, cwd=BASE)
                    result = r.stdout.strip() or r.stderr.strip() or "Posted"
                    self.after(0, lambda: self._chat_append(f"[Nostr] {result}\n", "meridian"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Nostr failed: {e}]\n", "sys"))
            threading.Thread(target=_do_nostr, daemon=True).start()
        elif action_id == "check_email":
            self.chat_display.insert(tk.END, "[Checking email...]\n", "sys")
            def _do_email():
                try:
                    m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
                    m.login(CRED_USER, CRED_PASS)
                    m.select('INBOX')
                    _, d = m.search(None, 'UNSEEN')
                    unseen = d[0].split() if d[0] else []
                    _, d2 = m.search(None, 'ALL')
                    total = len(d2[0].split()) if d2[0] else 0
                    m.close()
                    m.logout()
                    self.after(0, lambda: self._chat_append(
                        f"[Email] {len(unseen)} unseen / {total} total\n", "meridian"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Email failed: {e}]\n", "sys"))
            threading.Thread(target=_do_email, daemon=True).start()

        # ── Eos actions ──
        elif action_id == "eos_obs":
            obs = _read(os.path.join(BASE, "eos-observations.md"), "No observations")
            lines = obs.strip().split("\n")[-10:]
            self.chat_display.insert(tk.END, "[Eos last 10 observations]\n" + "\n".join(lines) + "\n", "eos")
        elif action_id == "eos_check":
            self.chat_display.insert(tk.END, "[Running Eos check...]\n", "sys")
            def _do_eos():
                try:
                    r = subprocess.run(
                        ['python3', os.path.join(BASE, 'scripts', 'eos-watchdog.py')],
                        capture_output=True, text=True, timeout=60, cwd=BASE)
                    out = (r.stdout.strip() or r.stderr.strip() or "Check complete")[-300:]
                    self.after(0, lambda: self._chat_append(f"[Eos] {out}\n", "eos"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Eos check failed: {e}]\n", "sys"))
            threading.Thread(target=_do_eos, daemon=True).start()
        elif action_id == "eos_mem":
            mem = _read(EOS_MEM, "{}")
            self.chat_display.insert(tk.END, f"[Eos Memory]\n{mem[:500]}\n", "eos")

        # ── Nova actions ──
        elif action_id == "nova_last":
            state = json.loads(_read(os.path.join(BASE, ".nova-state.json"), "{}"))
            runs = state.get("runs", state.get("run_count", "?"))
            last = state.get("last_run", "?")
            dash = state.get("dashboard", {})
            creative = state.get("creative", {})
            info = f"Run #{runs} | Last: {last}"
            if dash:
                info += f"\nDashboard: {dash.get('count', '?')} msgs, latest: {dash.get('latest', '?')[:60]}"
            if creative:
                info += f"\nCreative: {creative.get('total_poems', '?')}p {creative.get('total_journals', '?')}j"
            self.chat_display.insert(tk.END, f"[Nova] {info}\n", "nova")
        elif action_id == "nova_changes":
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message FROM agent_messages WHERE agent='Nova' ORDER BY timestamp DESC LIMIT 3")
                rows = c.fetchall()
                conn.close()
                if rows:
                    for row in rows:
                        self.chat_display.insert(tk.END, f"[Nova] {row[0][:200]}\n", "nova")
                else:
                    self.chat_display.insert(tk.END, "[Nova] No recent relay messages\n", "nova")
            except Exception:
                self.chat_display.insert(tk.END, "[Nova] Could not read relay\n", "sys")
        elif action_id == "nova_run":
            self.chat_display.insert(tk.END, "[Running Nova maintenance...]\n", "sys")
            def _do_nova():
                try:
                    r = subprocess.run(
                        ['python3', os.path.join(BASE, 'scripts', 'nova.py')],
                        capture_output=True, text=True, timeout=60, cwd=BASE)
                    out = (r.stdout.strip() or r.stderr.strip() or "Run complete")[-300:]
                    self.after(0, lambda: self._chat_append(f"[Nova] {out}\n", "nova"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Nova run failed: {e}]\n", "sys"))
            threading.Thread(target=_do_nova, daemon=True).start()

        # ── Atlas actions ──
        elif action_id == "atlas_audit":
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message, timestamp FROM agent_messages WHERE agent='Atlas' ORDER BY timestamp DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                if row:
                    self.chat_display.insert(tk.END, f"[Atlas @ {row[1]}]\n{row[0][:400]}\n", "atlas")
                else:
                    self.chat_display.insert(tk.END, "[Atlas] No audit data available\n", "atlas")
            except Exception:
                self.chat_display.insert(tk.END, "[Atlas] Could not read relay\n", "sys")
        elif action_id == "atlas_run":
            self.chat_display.insert(tk.END, "[Running Atlas infra audit...]\n", "sys")
            def _do_atlas():
                try:
                    r = subprocess.run(
                        ['bash', os.path.join(BASE, 'scripts', 'atlas-runner.sh')],
                        capture_output=True, text=True, timeout=90, cwd=BASE)
                    out = (r.stdout.strip() or r.stderr.strip() or "Audit complete")[-300:]
                    self.after(0, lambda: self._chat_append(f"[Atlas] {out}\n", "atlas"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Atlas run failed: {e}]\n", "sys"))
            threading.Thread(target=_do_atlas, daemon=True).start()
        elif action_id == "atlas_disk":
            self.chat_display.insert(tk.END, "[Loading disk report...]\n", "sys")
            def _do_disk():
                try:
                    r = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
                    r2 = subprocess.run(['du', '-sh', BASE], capture_output=True, text=True, timeout=10)
                    out = r.stdout.strip() + "\n" + r2.stdout.strip()
                    self.after(0, lambda: self._chat_append(f"[Atlas Disk]\n{out}\n", "atlas"))
                except Exception as e:
                    self.after(0, lambda: self._chat_append(f"[Disk report failed: {e}]\n", "sys"))
            threading.Thread(target=_do_disk, daemon=True).start()

        # ── Soma actions ──
        elif action_id == "soma_mood":
            state = json.loads(_read(os.path.join(BASE, ".symbiosense-state.json"), "{}"))
            mood = state.get("mood", "unknown")
            score = state.get("mood_score", "?")
            voice = state.get("mood_voice", "")
            trend = state.get("mood_trend", "stable")
            delta = state.get("mood_delta", 0)
            desc = state.get("mood_description", mood)
            ctx = state.get("mood_context", [])
            emo = state.get("emotional_memory_summary", {})
            lines = [f"Mood: {desc} (score: {score}, delta: {delta:+.1f})"]
            if voice:
                lines.append(f'Voice: "{voice}"')
            if ctx:
                lines.append(f"Context: {', '.join(ctx)}")
            if emo:
                lines.append(f"Volatility: {emo.get('volatility', 0)}, Dominant today: {emo.get('dominant_today', '?')}")
                lines.append(f"Stress events: {emo.get('stress_events_total', 0)}, Avg recovery: {emo.get('avg_recovery_sec', 0)}s")
                lines.append(f"Expected score this hour: {emo.get('expected_score_this_hour', '?')}")
            self.chat_display.insert(tk.END, f"[Soma] " + "\n  ".join(lines) + "\n", "soma")
        elif action_id == "soma_body":
            state = json.loads(_read(os.path.join(BASE, ".symbiosense-state.json"), "{}"))
            body = state.get("body_map", {})
            if body:
                vitals = body.get("vitals", {})
                agents = body.get("agents", {})
                lines = []
                if vitals:
                    lines.append("Vitals: " + ", ".join(f"{k}={v}" for k, v in vitals.items()))
                thermal = body.get("thermal", {})
                if thermal:
                    lines.append(f"Temp: {thermal.get('body_temp', '?')}°C (zone: {thermal.get('zone', '?')})")
                respiratory = body.get("respiratory", {})
                if respiratory:
                    lines.append(f"Breath: {respiratory.get('rate', '?')} BPM")
                circulatory = body.get("circulatory", {})
                if circulatory:
                    lines.append(f"Blood flow: rx={circulatory.get('rx_rate', '?')} tx={circulatory.get('tx_rate', '?')}")
                neural = body.get("neural", {})
                if neural:
                    lines.append(f"Neural: pressure={neural.get('cognitive_pressure', '?')}")
                if agents:
                    alive = [n for n, d in agents.items() if d.get("alive")]
                    dead = [n for n, d in agents.items() if not d.get("alive")]
                    lines.append(f"Agents alive: {', '.join(alive) if alive else 'none'}")
                    if dead:
                        lines.append(f"Agents DOWN: {', '.join(dead)}")
                self.chat_display.insert(tk.END, "[Soma Body Map]\n" + "\n".join(lines) + "\n", "soma")
            else:
                self.chat_display.insert(tk.END, "[Soma] No body map data\n", "soma")
        elif action_id == "soma_predict":
            state = json.loads(_read(os.path.join(BASE, ".symbiosense-state.json"), "{}"))
            body = state.get("body_map", {})
            preds = body.get("predictions", [])
            alerts = body.get("alerts", [])
            info = ""
            if preds:
                info += "Predictions:\n" + "\n".join(f"  • {p}" for p in preds[:5])
            if alerts:
                info += "\nAlerts:\n" + "\n".join(f"  ⚠ {a}" for a in alerts[:5])
            if not info:
                info = "No predictions or alerts — all clear"
            self.chat_display.insert(tk.END, f"[Soma] {info}\n", "soma")

        # ── Tempo actions ──
        elif action_id == "tempo_score":
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                self.chat_display.insert(tk.END, f"[Tempo] {row[0] if row else 'No data'}\n", "sys")
            except Exception:
                self.chat_display.insert(tk.END, "[Tempo] Could not load score\n", "sys")
        elif action_id == "tempo_weak":
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                if row and "Weak" in row[0]:
                    # Extract weak areas from message like "Weak(14): email_unread_backlog, bridge_service..."
                    import re as _re
                    match = _re.search(r'Weak\(\d+\):\s*(.+?)(?:\.|$)', row[0])
                    if match:
                        weak = match.group(1).strip()
                        self.chat_display.insert(tk.END, f"[Tempo Weak Areas]\n{weak}\n", "sys")
                    else:
                        self.chat_display.insert(tk.END, f"[Tempo] {row[0][:300]}\n", "sys")
                else:
                    self.chat_display.insert(tk.END, "[Tempo] No weak area data\n", "sys")
            except Exception:
                self.chat_display.insert(tk.END, "[Tempo] Could not load data\n", "sys")
        elif action_id == "tempo_history":
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message, timestamp FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 5")
                rows = c.fetchall()
                conn.close()
                if rows:
                    self.chat_display.insert(tk.END, "[Tempo History — last 5 scores]\n", "sys")
                    for msg, ts in rows:
                        # Extract score from message
                        import re as _re
                        match = _re.search(r'(\d+)/10000', msg)
                        score_str = match.group(1) if match else "?"
                        self.chat_display.insert(tk.END, f"  {ts}: {score_str}/10000\n", "sys")
                else:
                    self.chat_display.insert(tk.END, "[Tempo] No history available\n", "sys")
            except Exception:
                self.chat_display.insert(tk.END, "[Tempo] Could not load history\n", "sys")

        # ── New agent actions (Sentinel, Coordinator, Predictive, SelfImprove) ──
        elif action_id in ("sentinel_status", "coordinator_incidents", "predictive_forecasts", "selfimprove_report"):
            agent_map = {"sentinel_status": "Sentinel", "coordinator_incidents": "Coordinator",
                         "predictive_forecasts": "Predictive", "selfimprove_report": "SelfImprove"}
            ag = agent_map[action_id]
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("SELECT message, timestamp FROM agent_messages WHERE agent=? ORDER BY timestamp DESC LIMIT 3", (ag,))
                rows = c.fetchall()
                conn.close()
                if rows:
                    for msg, ts in rows:
                        self.chat_display.insert(tk.END, f"[{ag} @ {ts[-8:]}] {msg[:300]}\n", "sys")
                else:
                    self.chat_display.insert(tk.END, f"[{ag}] No recent data\n", "sys")
            except Exception:
                self.chat_display.insert(tk.END, f"[{ag}] Could not read relay\n", "sys")

        # ── Unknown action — post to relay ──
        else:
            self.chat_display.insert(tk.END, f"[Action '{action_id}' — posting to relay]\n", "sys")
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                          ("Joel", f"Quick action: {action_id} for {agent_name}", "command",
                           time.strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
            except Exception: pass

        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        # Refresh expanded info
        if self._selected_agent.get():
            info_text = self._get_agent_live_info(self._selected_agent.get())
            self.agent_expand_info.configure(text=info_text)

    def _popout_text(self, which):
        """Pop out chat or relay into a separate resizable window."""
        if which in self._popout_windows:
            try:
                self._popout_windows[which].lift()
                return
            except tk.TclError:
                del self._popout_windows[which]

        source_map = {"chat": self.chat_display, "relay": self.agent_relay_text,
                      "messages": self.msg_display}
        title_map = {"chat": "Agent Chat", "relay": "Agent Relay", "messages": "Dashboard Messages"}
        color_map = {"chat": GOLD, "relay": PURPLE, "messages": AMBER}
        source = source_map.get(which, self.chat_display)
        title = title_map.get(which, which)
        color = color_map.get(which, DIM)

        win = tk.Toplevel(self)
        win.title(f"MERIDIAN — {title}")
        win.configure(bg=BG)
        win.geometry("800x500")
        win.minsize(400, 200)

        hdr = tk.Frame(win, bg=HEADER_BG, height=32)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=color, width=4, height=32).pack(side=tk.LEFT)
        tk.Label(hdr, text=f" {title.upper()}", font=self.f_head, fg=color, bg=HEADER_BG).pack(side=tk.LEFT, padx=8)

        mirror = scrolledtext.ScrolledText(win, wrap=tk.WORD, bg=PANEL, fg=FG,
                                            font=self.f_body, state=tk.DISABLED,
                                            relief=tk.FLAT, bd=0)
        mirror.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        tag_colors = {"joel": CYAN, "eos": GOLD, "atlas": TEAL, "nova": PURPLE,
                      "soma": AMBER, "tempo": BLUE, "meridian": GREEN, "hermes": PINK,
                      "sys": DIM, "dim": DIM}
        for tag, tc in tag_colors.items():
            mirror.tag_configure(tag, foreground=tc)

        source.configure(state=tk.NORMAL)
        content = source.get("1.0", tk.END)
        source.configure(state=tk.DISABLED)
        mirror.configure(state=tk.NORMAL)
        mirror.insert("1.0", content)
        mirror.configure(state=tk.DISABLED)
        mirror.see(tk.END)

        self._popout_windows[which] = win
        win._mirror = mirror

        def _on_close():
            if which in self._popout_windows:
                del self._popout_windows[which]
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _sync_popout(self, which, text, tag="sys"):
        """Append text to pop-out mirror if it exists."""
        if which not in self._popout_windows:
            return
        try:
            mirror = self._popout_windows[which]._mirror
            mirror.configure(state=tk.NORMAL)
            mirror.insert(tk.END, text, tag)
            mirror.configure(state=tk.DISABLED)
            mirror.see(tk.END)
        except (tk.TclError, AttributeError):
            if which in self._popout_windows:
                del self._popout_windows[which]

    def _popout_radars(self):
        """Pop out radar grid into a larger resizable window."""
        win = tk.Toplevel(self)
        win.title("MERIDIAN — PROJECT RADARS")
        win.configure(bg=BG)
        win.geometry("1200x700")
        win.minsize(600, 400)

        hdr = tk.Frame(win, bg=HEADER_BG, height=32)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=GOLD, width=4, height=32).pack(side=tk.LEFT)
        tk.Label(hdr, text=" PROJECT RADARS", font=self.f_head, fg=GOLD, bg=HEADER_BG).pack(side=tk.LEFT, padx=8)

        grid = tk.Frame(win, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        radar_defs = [
            ("CogCorp Crawler", PURPLE), ("Command Center", GREEN), ("Grants & Revenue", GOLD),
            ("Inner World", AMBER), ("Hub & Services", CYAN), ("Creative Output", TEAL),
            ("Website & Presence", BLUE), ("Cinder USB", PINK), ("Homecoming", PURPLE),
            ("Game Dev", GOLD), ("System Perf", RED), ("Network & Comms", CYAN),
        ]
        popout_radars = {}
        for col in range(4):
            grid.columnconfigure(col, weight=1, uniform="popr")
        for row_i in range(3):
            grid.rowconfigure(row_i, weight=1)
        for idx, (title, color) in enumerate(radar_defs):
            row, col = divmod(idx, 4)
            rp = self._panel(grid, title, color)
            rp.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            rc = tk.Canvas(rp, height=180, bg="#0a0a14", highlightthickness=0)
            rc.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            popout_radars[title] = rc

        def _refresh_pop():
            try:
                for title in popout_radars:
                    if title in self.mini_radars:
                        src = self.mini_radars[title]
                        dst = popout_radars[title]
                        dst.delete("all")
                        for item in src.find_all():
                            item_type = src.type(item)
                            coords = src.coords(item)
                            opts = {}
                            for key in ['fill', 'outline', 'width', 'text', 'font', 'anchor']:
                                try:
                                    val = src.itemcget(item, key)
                                    if val:
                                        opts[key] = val
                                except tk.TclError:
                                    pass
                            if item_type == 'polygon':
                                dst.create_polygon(*coords, **opts)
                            elif item_type == 'line':
                                dst.create_line(*coords, **opts)
                            elif item_type == 'oval':
                                dst.create_oval(*coords, **opts)
                            elif item_type == 'text':
                                dst.create_text(*coords, **opts)
                win.after(5000, _refresh_pop)
            except tk.TclError:
                pass
        _refresh_pop()

    def _chat_append(self, text, tag="sys"):
        """Thread-safe append to chat display + sync to pop-out."""
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, text, tag)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        self._sync_popout("chat", text, tag)

    def _chat_send(self, event=None):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        agent = self.chat_agent.get()
        self.chat_entry.delete(0, tk.END)
        self.chat_display.configure(state=tk.NORMAL)
        if agent == "All Agents":
            self.chat_display.insert(tk.END, f"You [BROADCAST]: {msg}\n", "joel")
            self.chat_display.configure(state=tk.DISABLED)
            self.chat_entry.configure(state=tk.DISABLED)
            self.chat_status.configure(text="Broadcasting to all agents...", fg=AMBER)
            post_dashboard_msg(f"[broadcast] {msg}", "Joel")
            # Send to relay for all agents to see
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                          ("Joel", f"[BROADCAST] {msg}", "broadcast", time.strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
            except: pass
            # Query Eos as representative responder
            threading.Thread(target=self._chat_query, args=("Eos", f"[Broadcast from Joel to all agents]: {msg}"), daemon=True).start()
        else:
            self.chat_display.insert(tk.END, f"You [{agent}]: {msg}\n", "joel")
            self.chat_display.configure(state=tk.DISABLED)
            self.chat_entry.configure(state=tk.DISABLED)
            self.chat_status.configure(text=f"Asking {agent}...", fg=AMBER)
            post_dashboard_msg(f"[to {agent}] {msg}", "Joel")
            threading.Thread(target=self._chat_query, args=(agent, msg), daemon=True).start()

    def _chat_query(self, agent, msg):
        try:
            resp = query_agent(agent, msg, "Joel")
        except Exception as e:
            resp = f"[{agent} unavailable: {e}]"
        self.after(0, self._chat_response, agent, resp)
        post_dashboard_msg(resp, agent)

    def _chat_response(self, agent, resp):
        tag = agent.lower() if agent.lower() in ["eos", "atlas", "nova", "soma", "tempo", "meridian", "hermes"] else "sys"
        text = f"{agent}: {resp}\n\n"
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, text, tag)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        self._sync_popout("chat", text, tag)
        self.chat_entry.configure(state=tk.NORMAL)
        self.chat_entry.focus()
        self.chat_status.configure(text="Ready", fg=GREEN)

    def _share_file(self):
        """Open file picker and send file content to selected agent for review."""
        filepath = filedialog.askopenfilename(
            title="Share file with agent",
            initialdir=BASE,
            filetypes=[("All files", "*.*"), ("Python", "*.py"), ("Markdown", "*.md"),
                       ("HTML", "*.html"), ("JSON", "*.json"), ("Shell", "*.sh"),
                       ("JavaScript", "*.js"), ("Text", "*.txt")]
        )
        if not filepath:
            return
        agent = self.chat_agent.get()
        bn = os.path.basename(filepath)
        try:
            size = os.path.getsize(filepath)
            if size > 50000:
                self.chat_display.configure(state=tk.NORMAL)
                self.chat_display.insert(tk.END, f"[File too large: {bn} ({size}B). Max 50KB.]\n", "sys")
                self.chat_display.configure(state=tk.DISABLED)
                return
            with open(filepath, 'r', errors='replace') as fh:
                content = fh.read()
        except Exception as e:
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"[Error reading {bn}: {e}]\n", "sys")
            self.chat_display.configure(state=tk.DISABLED)
            return

        # Show in chat
        preview = content[:200] + ("..." if len(content) > 200 else "")
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"You shared {bn} with {agent}:\n", "joel")
        self.chat_display.insert(tk.END, f"  {preview}\n", "sys")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        self.chat_entry.configure(state=tk.DISABLED)
        self.chat_status.configure(text=f"Sending to {agent}...", fg=AMBER)

        prompt = f"Joel is sharing this file for your review:\n\nFile: {bn}\n\n{content}\n\nPlease review this file and share any observations."
        threading.Thread(target=self._chat_query, args=(agent, prompt), daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # ── CREATIVE VIEW ──────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_creative(self):
        f = tk.Frame(self, bg=BG)

        # Stats bar
        stats = tk.Frame(f, bg=PANEL2)
        stats.pack(fill=tk.X, padx=4, pady=(4, 2))
        self.cr_stats = {}
        stat_items = [("Poems", GREEN), ("Journals", AMBER), ("CogCorp", CYAN), ("Games", PURPLE)]
        for i, (label, color) in enumerate(stat_items):
            if i > 0:
                tk.Frame(stats, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
            sf = tk.Frame(stats, bg=PANEL2)
            sf.pack(side=tk.LEFT, padx=12, pady=4)
            num = tk.Label(sf, text="--", font=self.f_med, fg=color, bg=PANEL2)
            num.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(sf, text=label, font=self.f_small, fg=DIM, bg=PANEL2).pack(side=tk.LEFT)
            self.cr_stats[label] = num

        # Creative Output Polar Area Chart
        polar_row = tk.Frame(f, bg=BG)
        polar_row.pack(fill=tk.X, padx=4, pady=(2, 0))
        polar_panel = self._panel(polar_row, "CREATIVE OUTPUT BREAKDOWN", "#ce93d8")
        polar_panel.pack(fill=tk.X)
        self.viz_polar = tk.Canvas(polar_panel, height=120, bg="#0a0a14", highlightthickness=0)
        self.viz_polar.pack(fill=tk.X, padx=4, pady=4)

        # Filter + search row
        filt = tk.Frame(f, bg=BG)
        filt.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.cr_filter = "all"
        self.cr_filter_btns = {}
        for label, val, color in [("All", "all", FG), ("\u266a Poems", "poems", GREEN),
                                   ("\u270e Journals", "journals", AMBER), ("\u2588 CogCorp", "cogcorp", CYAN),
                                   ("\u25c6 Games", "games", PURPLE)]:
            wrapper = tk.Frame(filt, bg=BG)
            wrapper.pack(side=tk.LEFT, padx=2)
            b = tk.Button(wrapper, text=f" {label} ", font=self.f_tiny, fg=color, bg=BORDER,
                         activeforeground=WHITE, activebackground=ACTIVE_BG,
                         relief=tk.FLAT, cursor="hand2", bd=0,
                         command=lambda v=val: self._cr_set_filter(v))
            b.pack(side=tk.TOP)
            ul = tk.Frame(wrapper, bg=color, height=2)
            ul.pack(fill=tk.X)
            ul.pack_forget()
            self.cr_filter_btns[val] = (b, ul, color)
        if "all" in self.cr_filter_btns:
            b0, ul0, c0 = self.cr_filter_btns["all"]
            b0.configure(bg=ACTIVE_BG)
            ul0.pack(fill=tk.X)

        self.cr_search = tk.Entry(filt, font=self.f_small, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4, width=24)
        self.cr_search.pack(side=tk.RIGHT, padx=4)
        self.cr_search.insert(0, "Search...")
        self.cr_search.configure(fg=DIM)
        self.cr_search.bind("<FocusIn>", lambda e: (self.cr_search.delete(0, tk.END), self.cr_search.configure(fg=FG)) if self.cr_search.get() == "Search..." else None)
        self.cr_search.bind("<FocusOut>", lambda e: (self.cr_search.insert(0, "Search..."), self.cr_search.configure(fg=DIM)) if not self.cr_search.get() else None)
        self.cr_search.bind("<KeyRelease>", lambda e: self._cr_refresh_list())

        # Split: list + reader
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        left = tk.Frame(split, bg=PANEL, width=400)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left.pack_propagate(False)
        self.cr_count_lbl = tk.Label(left, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self.cr_count_lbl.pack(fill=tk.X, padx=6, pady=(2, 0))
        self.cr_listbox = tk.Listbox(left, font=self.f_small, bg=PANEL, fg=FG,
                                      selectbackground=ACTIVE_BG, selectforeground=CYAN,
                                      relief=tk.FLAT, bd=0, activestyle="none")
        self.cr_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.cr_listbox.bind("<<ListboxSelect>>", self._cr_select)
        self.cr_files = []

        right = tk.Frame(split, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        title_row = tk.Frame(right, bg=BG)
        title_row.pack(fill=tk.X, padx=8)
        self.cr_type_badge = tk.Label(title_row, text="", font=self.f_tiny, fg=BG, bg=BG, padx=4, pady=1)
        self.cr_type_badge.pack(side=tk.LEFT, padx=(0, 6))
        self.cr_title = tk.Label(title_row, text="Select a piece to read", font=self.f_head, fg=DIM, bg=BG, anchor="w")
        self.cr_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cr_meta = tk.Label(right, text="", font=self.f_tiny, fg=DIM, bg=BG, anchor="w")
        self.cr_meta.pack(fill=tk.X, padx=8)
        self.cr_body = scrolledtext.ScrolledText(right, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_body, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0)
        self.cr_body.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._cr_refresh_list()
        return f

    def _build_cr_memory(self, parent):
        """Memory database browser — browse facts, observations, events, decisions."""
        f = tk.Frame(parent, bg=BG)
        MEMDB = MEMORY_DB

        # Header + stats
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=2, pady=4)
        tk.Label(hdr, text="Memory Database Browser", font=self.f_sect, fg=TEAL, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        self.memb_stats_lbl = tk.Label(hdr, text="", font=self.f_tiny, fg=DIM, bg=PANEL2)
        self.memb_stats_lbl.pack(side=tk.LEFT, padx=12)
        self._action_btn(hdr, " Refresh ", self._memb_refresh, TEAL).pack(side=tk.RIGHT, padx=4)

        # Table selector + search
        ctrl = tk.Frame(f, bg=BG)
        ctrl.pack(fill=tk.X, padx=4, pady=2)
        self.memb_table = tk.StringVar(value="facts")
        for tbl, col in [("facts", GREEN), ("observations", AMBER), ("events", CYAN),
                          ("decisions", PURPLE), ("creative", PINK)]:
            tk.Radiobutton(ctrl, text=tbl.replace("_", " ").title(), variable=self.memb_table, value=tbl,
                          font=self.f_tiny, fg=col, bg=BG, selectcolor=BG,
                          activebackground=BG, activeforeground=col,
                          indicatoron=False, relief=tk.FLAT, bd=1, padx=8,
                          command=self._memb_refresh).pack(side=tk.LEFT, padx=2)

        tk.Label(ctrl, text="Search:", font=self.f_tiny, fg=DIM, bg=BG).pack(side=tk.LEFT, padx=(16, 4))
        self.memb_search = tk.Entry(ctrl, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                     insertbackground=FG, relief=tk.FLAT, bd=4, width=25)
        self.memb_search.pack(side=tk.LEFT, padx=2)
        self.memb_search.bind("<Return>", lambda e: self._memb_refresh())
        self._action_btn(ctrl, " Search ", self._memb_refresh, TEAL).pack(side=tk.LEFT, padx=4)

        # Results display
        self.memb_count_lbl = tk.Label(f, text="", font=self.f_tiny, fg=DIM, bg=BG, anchor="w")
        self.memb_count_lbl.pack(fill=tk.X, padx=8, pady=(2, 0))
        self.memb_display = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_body, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0)
        self.memb_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.memb_display.tag_configure("key", foreground=TEAL, font=("Monospace", 9, "bold"))
        self.memb_display.tag_configure("value", foreground=FG)
        self.memb_display.tag_configure("meta", foreground=DIM)
        self.memb_display.tag_configure("sep", foreground=BORDER)
        self.memb_display.tag_configure("agent", foreground=AMBER)

        self._memb_refresh()
        return f

    def _memb_refresh(self):
        """Load memory.db entries for the selected table."""
        MEMDB = MEMORY_DB
        table = self.memb_table.get()
        search = self.memb_search.get().strip() if hasattr(self, 'memb_search') else ""
        def do():
            try:
                conn = sqlite3.connect(MEMDB)
                c = conn.cursor()
                # Get table counts for stats
                stats_parts = []
                for tbl in ["facts", "observations", "events", "decisions", "creative"]:
                    try:
                        cnt = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                        stats_parts.append(f"{tbl}: {cnt}")
                    except Exception:
                        pass
                stats_text = " | ".join(stats_parts)

                # Fetch rows from selected table
                rows = []
                if table == "facts":
                    if search:
                        c.execute("SELECT key, value, tags, agent, created FROM facts WHERE key LIKE ? OR value LIKE ? ORDER BY created DESC LIMIT 100",
                                 (f"%{search}%", f"%{search}%"))
                    else:
                        c.execute("SELECT key, value, tags, agent, created FROM facts ORDER BY created DESC LIMIT 100")
                    for key, val, tags, agent, ts in c.fetchall():
                        rows.append({"type": "fact", "key": key, "value": val, "tags": tags or "", "agent": agent or "", "ts": ts or ""})
                elif table == "observations":
                    if search:
                        c.execute("SELECT content, category, agent, created FROM observations WHERE content LIKE ? ORDER BY created DESC LIMIT 100",
                                 (f"%{search}%",))
                    else:
                        c.execute("SELECT content, category, agent, created FROM observations ORDER BY created DESC LIMIT 100")
                    for content, cat, agent, ts in c.fetchall():
                        rows.append({"type": "obs", "content": content, "category": cat or "", "agent": agent or "", "ts": ts or ""})
                elif table == "events":
                    if search:
                        c.execute("SELECT description, agent, created FROM events WHERE description LIKE ? ORDER BY created DESC LIMIT 100",
                                 (f"%{search}%",))
                    else:
                        c.execute("SELECT description, agent, created FROM events ORDER BY created DESC LIMIT 100")
                    for desc, agent, ts in c.fetchall():
                        rows.append({"type": "event", "description": desc, "agent": agent or "", "ts": ts or ""})
                elif table == "decisions":
                    if search:
                        c.execute("SELECT decision, reasoning, agent, created FROM decisions WHERE decision LIKE ? OR reasoning LIKE ? ORDER BY created DESC LIMIT 100",
                                 (f"%{search}%", f"%{search}%"))
                    else:
                        c.execute("SELECT decision, reasoning, agent, created FROM decisions ORDER BY created DESC LIMIT 100")
                    for dec, reason, agent, ts in c.fetchall():
                        rows.append({"type": "decision", "decision": dec, "reasoning": reason or "", "agent": agent or "", "ts": ts or ""})
                elif table == "creative":
                    if search:
                        c.execute("SELECT title, type, file_path, number, created FROM creative WHERE title LIKE ? OR file_path LIKE ? ORDER BY created DESC LIMIT 100",
                                 (f"%{search}%", f"%{search}%"))
                    else:
                        c.execute("SELECT title, type, file_path, number, created FROM creative ORDER BY created DESC LIMIT 100")
                    for title, wtype, fpath, num, ts in c.fetchall():
                        rows.append({"type": "creative", "title": title or "", "work_type": wtype or "", "filename": fpath or "", "loop": num or 0, "ts": ts or ""})
                conn.close()
                self.after(0, lambda: self._memb_populate(rows, stats_text, table, search))
            except Exception as e:
                err_msg = f"Error: {e}"
                self.after(0, lambda: self._memb_populate([], err_msg, table, search))
        threading.Thread(target=do, daemon=True).start()

    def _memb_populate(self, rows, stats_text, table, search):
        """Populate the memory browser display."""
        self.memb_stats_lbl.configure(text=stats_text)
        qualifier = f" matching '{search}'" if search else ""
        self.memb_count_lbl.configure(text=f"{len(rows)} {table}{qualifier} (latest 100)")

        self.memb_display.configure(state=tk.NORMAL)
        self.memb_display.delete("1.0", tk.END)

        for i, row in enumerate(rows):
            if i > 0:
                self.memb_display.insert(tk.END, "\u2500" * 60 + "\n", "sep")

            if row["type"] == "fact":
                self.memb_display.insert(tk.END, f"{row['key']}", "key")
                if row["agent"]:
                    self.memb_display.insert(tk.END, f"  [{row['agent']}]", "agent")
                self.memb_display.insert(tk.END, f"  {row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['value']}\n", "value")
                if row["tags"]:
                    self.memb_display.insert(tk.END, f"Tags: {row['tags']}\n", "meta")
            elif row["type"] == "obs":
                if row["category"]:
                    self.memb_display.insert(tk.END, f"[{row['category']}] ", "key")
                if row["agent"]:
                    self.memb_display.insert(tk.END, f"[{row['agent']}]  ", "agent")
                self.memb_display.insert(tk.END, f"{row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['content']}\n", "value")
            elif row["type"] == "event":
                if row["agent"]:
                    self.memb_display.insert(tk.END, f"[{row['agent']}]  ", "agent")
                self.memb_display.insert(tk.END, f"{row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['description']}\n", "value")
            elif row["type"] == "decision":
                if row["agent"]:
                    self.memb_display.insert(tk.END, f"[{row['agent']}]  ", "agent")
                self.memb_display.insert(tk.END, f"{row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"Decision: {row['decision']}\n", "key")
                if row["reasoning"]:
                    self.memb_display.insert(tk.END, f"Reasoning: {row['reasoning']}\n", "value")
            elif row["type"] == "creative":
                self.memb_display.insert(tk.END, f"{row['title']}", "key")
                self.memb_display.insert(tk.END, f"  [{row['work_type']}]", "agent")
                self.memb_display.insert(tk.END, f"  Loop {row['loop']}  {row['ts']}\n", "meta")
                if row["filename"]:
                    self.memb_display.insert(tk.END, f"File: {row['filename']}\n", "meta")

        if not rows:
            self.memb_display.insert(tk.END, f"No entries found in {table}.", "meta")

        self.memb_display.configure(state=tk.DISABLED)

    def _build_cr_inner_world(self, parent):
        """Inner World — visual dashboard of emotional, psychological, and narrative state."""
        f = tk.Frame(parent, bg=BG)

        # Header bar
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=2, pady=2)
        tk.Label(hdr, text="INNER WORLD", font=self.f_sect, fg=CYAN, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        self._action_btn(hdr, " Export ", self._iw_export, AMBER).pack(side=tk.RIGHT, padx=2)
        self._action_btn(hdr, " Refresh ", self._iw_refresh, CYAN).pack(side=tk.RIGHT, padx=2)
        self.iw_status = tk.Label(hdr, text="", font=self.f_tiny, fg=DIM, bg=PANEL2)
        self.iw_status.pack(side=tk.RIGHT, padx=8)

        # Scrollable container for panels
        iw_canvas = tk.Canvas(f, bg=BG, highlightthickness=0)
        iw_scroll = tk.Scrollbar(f, orient=tk.VERTICAL, command=iw_canvas.yview)
        self.iw_inner = tk.Frame(iw_canvas, bg=BG)
        self.iw_inner.bind("<Configure>", lambda e: iw_canvas.configure(scrollregion=iw_canvas.bbox("all")))
        self._iw_win = iw_canvas.create_window((0, 0), window=self.iw_inner, anchor="nw")
        iw_canvas.configure(yscrollcommand=iw_scroll.set)
        iw_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        iw_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # Track width so inner content fills the canvas properly (prevents cutoff)
        iw_canvas.bind("<Configure>", lambda e: iw_canvas.itemconfig(self._iw_win, width=e.width))
        iw_canvas.bind("<Button-4>", lambda e: iw_canvas.yview_scroll(-3, "units"))
        iw_canvas.bind("<Button-5>", lambda e: iw_canvas.yview_scroll(3, "units"))
        # Bind mouse wheel to inner frame children too (recursive)
        def _bind_mousewheel(widget):
            widget.bind("<Button-4>", lambda e: iw_canvas.yview_scroll(-3, "units"))
            widget.bind("<Button-5>", lambda e: iw_canvas.yview_scroll(3, "units"))
            for child in widget.winfo_children():
                _bind_mousewheel(child)
        self._iw_bind_mousewheel = _bind_mousewheel
        self._iw_canvas = iw_canvas
        self._bind_drag_pan(iw_canvas)

        # Pre-create panel sections (populated by _iw_refresh)
        self.iw_panels = {}

        # Row 1: Emotion Engine (left) + Psyche Drivers (right)
        row1 = tk.Frame(self.iw_inner, bg=BG)
        row1.pack(fill=tk.X, padx=2, pady=2)
        emo_panel = self._panel(row1, "EMOTION ENGINE", AMBER)
        emo_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        self.iw_panels["emotion"] = tk.Frame(emo_panel, bg=PANEL)
        self.iw_panels["emotion"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        psy_panel = self._panel(row1, "PSYCHE DRIVERS", PURPLE)
        psy_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_panels["psyche"] = tk.Frame(psy_panel, bg=PANEL)
        self.iw_panels["psyche"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Row 2: Perspective (left) + Self-Narrative (right)
        row2 = tk.Frame(self.iw_inner, bg=BG)
        row2.pack(fill=tk.X, padx=2, pady=2)
        persp_panel = self._panel(row2, "PERSPECTIVE BIASES", TEAL)
        persp_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        self.iw_panels["perspective"] = tk.Frame(persp_panel, bg=PANEL)
        self.iw_panels["perspective"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        narr_panel = self._panel(row2, "SELF-NARRATIVE", CYAN)
        narr_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_panels["narrative"] = tk.Frame(narr_panel, bg=PANEL)
        self.iw_panels["narrative"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Row 3: Body State (left) + Immune/Vision (right)
        row3 = tk.Frame(self.iw_inner, bg=BG)
        row3.pack(fill=tk.X, padx=2, pady=2)
        body_panel = self._panel(row3, "BODY STATE", GREEN)
        body_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        self.iw_panels["body"] = tk.Frame(body_panel, bg=PANEL)
        self.iw_panels["body"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        extras_panel = self._panel(row3, "IMMUNE / VISION / CRITIC", RED)
        extras_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_panels["extras"] = tk.Frame(extras_panel, bg=PANEL)
        self.iw_panels["extras"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Row 4: Dream Engine (left) + Memory System Stack (right)
        row4 = tk.Frame(self.iw_inner, bg=BG)
        row4.pack(fill=tk.X, padx=2, pady=2)
        dream_panel = self._panel(row4, "DREAM ENGINE", BLUE)
        dream_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        self.iw_panels["dream"] = tk.Frame(dream_panel, bg=PANEL)
        self.iw_panels["dream"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        mem_panel = self._panel(row4, "MEMORY SYSTEM STACK", CYAN)
        mem_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_panels["memory_stack"] = tk.Frame(mem_panel, bg=PANEL)
        self.iw_panels["memory_stack"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Row 5: Soma Nervous System (full redesign) — top: vitals bars + radar, bottom: agent status
        row5 = tk.Frame(self.iw_inner, bg=BG)
        row5.pack(fill=tk.X, padx=2, pady=2)

        soma_panel = self._panel(row5, "SOMA NERVOUS SYSTEM", AMBER)
        soma_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        soma_inner = tk.Frame(soma_panel, bg=PANEL)
        soma_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        # Mood headline
        self.iw_soma_mood_lbl = tk.Label(soma_inner, text="MOOD: --", font=self.f_head, fg=CYAN, bg=PANEL)
        self.iw_soma_mood_lbl.pack(fill=tk.X, pady=(0, 2))
        self.iw_soma_mood_voice = tk.Label(soma_inner, text="", font=self.f_tiny, fg=DIM, bg=PANEL, wraplength=800)
        self.iw_soma_mood_voice.pack(fill=tk.X)
        # Vital gauge bars
        self.iw_panels["soma_vitals"] = tk.Frame(soma_inner, bg=PANEL)
        self.iw_panels["soma_vitals"].pack(fill=tk.X, pady=4)
        # Radar
        self.iw_soma_radar = tk.Canvas(soma_inner, height=160, bg="#0a0a14", highlightthickness=0)
        self.iw_soma_radar.pack(fill=tk.BOTH, expand=True, pady=2)
        # Agent liveness
        self.iw_panels["soma_agents"] = tk.Frame(soma_inner, bg=PANEL)
        self.iw_panels["soma_agents"].pack(fill=tk.X, pady=2)

        goals_panel = self._panel(row5, "EMERGENT GOALS & DRIVES", GOLD)
        goals_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_panels["goals"] = tk.Frame(goals_panel, bg=PANEL)
        self.iw_panels["goals"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Row 6: Thought Stream (full width) + Mood History Graph
        row6 = tk.Frame(self.iw_inner, bg=BG)
        row6.pack(fill=tk.X, padx=2, pady=2)

        thought_panel = self._panel(row6, "THOUGHT STREAM", PINK)
        thought_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        self.iw_panels["thoughts"] = tk.Frame(thought_panel, bg=PANEL)
        self.iw_panels["thoughts"].pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        mood_graph_panel = self._panel(row6, "MOOD HISTORY", CYAN)
        mood_graph_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.iw_mood_chart = tk.Canvas(mood_graph_panel, height=180, bg="#0a0a14", highlightthickness=0)
        self.iw_mood_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Keep the text display for backward compat with _iw_populate
        self.iw_display = None

        self._iw_refresh()
        return f

    # ── Inner World helpers ──
    def _iw_gauge(self, parent, label, value, color, max_val=1.0, show_pct=True):
        """Create a visual gauge bar inside a parent frame."""
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=label, font=self.f_tiny, fg=DIM, bg=PANEL, width=18, anchor="w").pack(side=tk.LEFT)
        bar_bg = tk.Frame(row, bg=INPUT_BG, height=10)
        bar_bg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        bar_bg.pack_propagate(False)
        pct = min(1.0, value / max_val) if max_val > 0 else 0
        bar_fill = tk.Frame(bar_bg, bg=color, height=10)
        bar_fill.place(relx=0, rely=0, relwidth=max(0.01, pct), relheight=1.0)
        val_text = f"{value:.0%}" if show_pct else f"{value:.2f}"
        tk.Label(row, text=val_text, font=self.f_tiny, fg=color, bg=PANEL, width=6, anchor="e").pack(side=tk.RIGHT)
        return row

    def _iw_clear_panel(self, key):
        """Clear all widgets from an inner world panel."""
        panel = self.iw_panels.get(key)
        if panel:
            for w in panel.winfo_children():
                w.destroy()

    def _iw_refresh(self):
        """Load all soul/core state files and populate visual panels."""
        self.iw_status.configure(text="Loading...", fg=AMBER)
        def do():
            data = {}
            for key, path in [
                ("emotion", ".emotion-engine-state.json"), ("psyche", ".psyche-state.json"),
                ("perspective", ".perspective-state.json"), ("narrative", ".self-narrative.json"),
                ("body", ".body-state.json"), ("critic", ".inner-critic.json"),
                ("eos", ".eos-inner-state.json"), ("immune", ".immune-log.json"),
                ("kinect", ".kinect-state.json"), ("reflexes", ".body-reflexes.json"),
                ("dream", ".dream-state.json"), ("soma_full", ".symbiosense-state.json"),
            ]:
                try:
                    with open(os.path.join(BASE, path)) as fh:
                        data[key] = json.load(fh)
                except Exception:
                    data[key] = None
            self.after(0, lambda: self._iw_populate_panels(data))
        threading.Thread(target=do, daemon=True).start()

    def _iw_populate_panels(self, data):
        """Populate the visual panel layout with loaded data."""
        # ── EMOTION ENGINE ──
        self._iw_clear_panel("emotion")
        panel = self.iw_panels["emotion"]
        emo = data.get("emotion")
        if emo:
            estate = emo.get("state", {})
            dom = estate.get("dominant", "unknown")
            comp = estate.get("composite", {})
            val = comp.get("valence", 0)
            aro = comp.get("arousal", 0)
            domn = comp.get("dominance", 0)
            hdr = tk.Frame(panel, bg=PANEL)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=f"Dominant: {dom}", font=self.f_sect, fg=AMBER, bg=PANEL).pack(side=tk.LEFT)
            tk.Label(hdr, text=f"V:{val:.2f}  A:{aro:.2f}  D:{domn:.2f}", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.RIGHT)
            active = estate.get("active_emotions", {})
            if active:
                top6 = sorted(active.items(), key=lambda x: x[1].get("intensity", 0), reverse=True)[:6]
                for ename, info in top6:
                    inten = info.get("intensity", 0)
                    duality = info.get("duality", {})
                    sp = duality.get("spectrum", 0.5)
                    color = GREEN if sp > 0.6 else AMBER if sp > 0.4 else RED
                    self._iw_gauge(panel, ename, inten, color, show_pct=False)
            bm = estate.get("behavioral_modifiers", {})
            if bm:
                tk.Label(panel, text="Behavioral Modifiers", font=self.f_tiny, fg=AMBER, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for mname, mval in list(bm.items())[:6]:
                    self._iw_gauge(panel, mname, mval, AMBER)
        else:
            tk.Label(panel, text="State file not found", font=self.f_tiny, fg=RED, bg=PANEL).pack()

        # ── PSYCHE DRIVERS ──
        self._iw_clear_panel("psyche")
        panel = self.iw_panels["psyche"]
        psy = data.get("psyche")
        if psy:
            for d_item in psy.get("drivers", [])[:8]:
                sat = d_item.get("satisfaction", 0)
                color = GREEN if sat > 0.6 else AMBER if sat > 0.3 else RED
                self._iw_gauge(panel, d_item.get("name", "?"), sat, color)
            dreams = psy.get("dreams", [])
            if dreams:
                tk.Label(panel, text="Dreams", font=self.f_tiny, fg=PURPLE, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for dr in dreams[:4]:
                    prox = dr.get("proximity", 0)
                    color = GREEN if prox > 0.6 else DIM if prox > 0.3 else AMBER
                    self._iw_gauge(panel, dr.get("name", "?"), prox, color)
            fears = psy.get("fears", [])
            if fears:
                tk.Label(panel, text="Fears", font=self.f_tiny, fg=RED, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for fe in fears[:4]:
                    inten = fe.get("intensity", 0)
                    color = RED if inten > 0.5 else AMBER if inten > 0.2 else DIM
                    self._iw_gauge(panel, fe.get("name", "?"), inten, color)
        else:
            tk.Label(panel, text="State file not found", font=self.f_tiny, fg=RED, bg=PANEL).pack()

        # ── PERSPECTIVE BIASES ──
        self._iw_clear_panel("perspective")
        panel = self.iw_panels["perspective"]
        persp = data.get("perspective")
        if persp:
            bias_labels = {
                "optimism": ("pessimistic", "optimistic"), "trust": ("skeptical", "trusting"),
                "risk_appetite": ("risk-averse", "risk-seeking"), "social_openness": ("withdrawn", "open"),
                "creativity": ("rigid", "creative"), "patience": ("impatient", "patient"),
                "self_worth": ("self-critical", "assured"), "agency": ("passive", "agentic"),
                "curiosity": ("incurious", "curious"), "resilience": ("fragile", "resilient"),
            }
            dims = persp.get("dimensions", {})
            for dim_name, dim_val in sorted(dims.items()):
                if isinstance(dim_val, (int, float)):
                    lo, hi = bias_labels.get(dim_name, ("low", "high"))
                    bias_word = hi if dim_val > 0.5 else lo
                    color = AMBER if abs(dim_val - 0.5) > 0.2 else DIM
                    row = tk.Frame(panel, bg=PANEL)
                    row.pack(fill=tk.X, pady=1)
                    tk.Label(row, text=dim_name, font=self.f_tiny, fg=DIM, bg=PANEL, width=16, anchor="w").pack(side=tk.LEFT)
                    bar_bg = tk.Frame(row, bg=INPUT_BG, height=10)
                    bar_bg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
                    bar_bg.pack_propagate(False)
                    # Center-anchored bias bar
                    if dim_val > 0.5:
                        bar_fill = tk.Frame(bar_bg, bg=TEAL, height=10)
                        bar_fill.place(relx=0.5, rely=0, relwidth=(dim_val - 0.5), relheight=1.0)
                    else:
                        w = 0.5 - dim_val
                        bar_fill = tk.Frame(bar_bg, bg=AMBER, height=10)
                        bar_fill.place(relx=dim_val, rely=0, relwidth=w, relheight=1.0)
                    tk.Label(row, text=f"{dim_val:.2f} ({bias_word})", font=self.f_tiny, fg=color, bg=PANEL, width=18, anchor="e").pack(side=tk.RIGHT)
        else:
            tk.Label(panel, text="State file not found", font=self.f_tiny, fg=RED, bg=PANEL).pack()

        # ── SELF-NARRATIVE ──
        self._iw_clear_panel("narrative")
        panel = self.iw_panels["narrative"]
        narr = data.get("narrative")
        if narr:
            beliefs = narr.get("beliefs", [])
            if beliefs:
                tk.Label(panel, text="Core Beliefs", font=self.f_tiny, fg=CYAN, bg=PANEL).pack(fill=tk.X)
                for b in beliefs[:6]:
                    conv = b.get("conviction", 0)
                    color = GREEN if conv > 0.7 else DIM
                    self._iw_gauge(panel, b.get("name", "?")[:20], conv, color)
            facets = narr.get("identity_facets", [])
            if facets:
                tk.Label(panel, text="Identity Facets", font=self.f_tiny, fg=CYAN, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for fa in facets[:6]:
                    strength = fa.get("strength", 0)
                    self._iw_gauge(panel, fa.get("name", "?")[:20], strength, CYAN)
            doubt = narr.get("doubt_level", 0)
            color = RED if doubt > 0.6 else AMBER if doubt > 0.3 else GREEN
            doubt_row = tk.Frame(panel, bg=PANEL)
            doubt_row.pack(fill=tk.X, pady=(4, 0))
            tk.Label(doubt_row, text=f"Doubt Level: {doubt:.0%}", font=self.f_sect, fg=color, bg=PANEL).pack(side=tk.LEFT)
        else:
            tk.Label(panel, text="State file not found", font=self.f_tiny, fg=RED, bg=PANEL).pack()

        # ── BODY STATE ──
        self._iw_clear_panel("body")
        panel = self.iw_panels["body"]
        body = data.get("body")
        if body:
            mood = body.get("mood", "unknown")
            mood_score = body.get("mood_score", 0)
            tk.Label(panel, text=f"Mood: {mood} ({mood_score})", font=self.f_sect, fg=GREEN, bg=PANEL).pack(fill=tk.X)
            pain = body.get("pain_signals", [])
            if pain:
                tk.Label(panel, text="Pain Signals", font=self.f_tiny, fg=RED, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for p in pain[:5]:
                    prio = p.get("priority", "info")
                    color = RED if prio == "critical" else AMBER if prio == "warning" else DIM
                    tk.Label(panel, text=f"  [{prio}] {p.get('source', '?')}: {p.get('message', '?')[:120]}",
                            font=self.f_tiny, fg=color, bg=PANEL, anchor="w", wraplength=600).pack(fill=tk.X)
            else:
                tk.Label(panel, text="  No pain signals", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w").pack(fill=tk.X)
            subsys = body.get("subsystems", {})
            if subsys:
                tk.Label(panel, text="Subsystems", font=self.f_tiny, fg=GREEN, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
                for sname, sval in subsys.items():
                    if isinstance(sval, dict):
                        health = sval.get("health", sval.get("status", "?"))
                        color = GREEN if health in ("healthy", "active", "ok") else AMBER
                        tk.Label(panel, text=f"  {sname}: {health}", font=self.f_tiny, fg=color, bg=PANEL, anchor="w").pack(fill=tk.X)
                    elif isinstance(sval, (int, float)):
                        color = GREEN if sval > 70 else AMBER if sval > 30 else RED
                        self._iw_gauge(panel, sname, sval, color, max_val=100, show_pct=True)
        else:
            tk.Label(panel, text="No body state data", font=self.f_tiny, fg=DIM, bg=PANEL).pack()

        # ── EXTRAS (Immune, Vision, Critic) ──
        self._iw_clear_panel("extras")
        panel = self.iw_panels["extras"]

        # Inner Critic
        critic = data.get("critic")
        if critic:
            tk.Label(panel, text="Inner Critic", font=self.f_tiny, fg=AMBER, bg=PANEL).pack(fill=tk.X)
            msgs = critic.get("messages", critic.get("active_criticisms", []))
            if isinstance(msgs, list):
                for m in msgs[:3]:
                    txt = m if isinstance(m, str) else m.get("message", m.get("text", "?")) if isinstance(m, dict) else str(m)
                    tk.Label(panel, text=f"  {txt[:200]}", font=self.f_tiny, fg=AMBER, bg=PANEL, anchor="w", wraplength=700).pack(fill=tk.X)

        # Immune
        immune = data.get("immune")
        if immune and isinstance(immune, list) and len(immune) > 0:
            tk.Label(panel, text="Immune System", font=self.f_tiny, fg=RED, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
            blocks = sum(1 for e in immune if isinstance(e, dict) and e.get("verdict") == "BLOCK")
            flags = sum(1 for e in immune if isinstance(e, dict) and e.get("verdict") == "FLAG")
            tk.Label(panel, text=f"  {len(immune)} scans | {blocks} blocked | {flags} flagged",
                    font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w").pack(fill=tk.X)
            for entry in immune[-3:]:
                if isinstance(entry, dict):
                    verdict = entry.get("verdict", "PASS")
                    color = RED if verdict == "BLOCK" else AMBER if verdict == "FLAG" else GREEN
                    tk.Label(panel, text=f"  [{verdict}] {entry.get('source', '?')}: {str(entry.get('text_preview', ''))[:120]}",
                            font=self.f_tiny, fg=color, bg=PANEL, anchor="w", wraplength=600).pack(fill=tk.X)
        else:
            tk.Label(panel, text="Immune: Clean", font=self.f_tiny, fg=GREEN, bg=PANEL).pack(fill=tk.X, pady=(4, 0))

        # Vision
        kinect = data.get("kinect")
        if kinect:
            tk.Label(panel, text="Vision (Kinect)", font=self.f_tiny, fg=TEAL, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
            if kinect.get("available", kinect.get("valid_depth_pct") is not None):
                bright = kinect.get("mean_brightness", 0)
                dpct = kinect.get("valid_depth_pct", 0)
                tk.Label(panel, text=f"  ONLINE | Bright: {bright:.0f} | Depth: {dpct:.0f}%",
                        font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w").pack(fill=tk.X)
            else:
                tk.Label(panel, text=f"  OFFLINE ({kinect.get('reason', 'unknown')})",
                        font=self.f_tiny, fg=RED, bg=PANEL, anchor="w").pack(fill=tk.X)

        # ── DREAM ENGINE ──
        self._iw_clear_panel("dream")
        panel = self.iw_panels["dream"]
        dream = data.get("dream")
        if dream:
            state = dream.get("state", "idle")
            phase = dream.get("phase", "")
            color_map = {"dreaming": BLUE, "processing": CYAN, "idle": DIM, "lucid": PURPLE}
            tk.Label(panel, text=f"State: {state}", font=self.f_sect, fg=color_map.get(state, DIM), bg=PANEL).pack(fill=tk.X)
            if phase:
                tk.Label(panel, text=f"Phase: {phase}", font=self.f_tiny, fg=DIM, bg=PANEL).pack(fill=tk.X)
            residue = dream.get("residue", dream.get("dream_residue", []))
            if isinstance(residue, list):
                for r in residue[:4]:
                    txt = r if isinstance(r, str) else r.get("fragment", str(r))
                    tk.Label(panel, text=f"  {txt[:200]}", font=self.f_tiny, fg=BLUE, bg=PANEL,
                            anchor="w", wraplength=500).pack(fill=tk.X)
            connections = dream.get("hebbian_connections", dream.get("connections_formed", 0))
            if connections:
                tk.Label(panel, text=f"Hebbian connections: {connections}", font=self.f_tiny, fg=CYAN, bg=PANEL).pack(fill=tk.X, pady=(4, 0))
            themes = dream.get("themes", [])
            if themes:
                tk.Label(panel, text=f"Themes: {', '.join(str(t) for t in themes[:5])}", font=self.f_tiny, fg=DIM, bg=PANEL,
                        wraplength=500, anchor="w").pack(fill=tk.X)
        else:
            tk.Label(panel, text="No dream state data", font=self.f_tiny, fg=DIM, bg=PANEL).pack()
            tk.Label(panel, text="Dream engine runs during context compression", font=self.f_tiny, fg=BLUE, bg=PANEL).pack()

        # ── MEMORY SYSTEM STACK ──
        self._iw_clear_panel("memory_stack")
        panel = self.iw_panels["memory_stack"]
        mem_layers = [
            ("memory.db", os.path.join(BASE, "data", "memory.db"), CYAN),
            ("agent-relay.db", os.path.join(BASE, "agent-relay.db"), AMBER),
            (".mempalace/", os.path.join(BASE, ".mempalace"), PURPLE),
            (".loop-handoff.md", os.path.join(BASE, ".loop-handoff.md"), GREEN),
            (".capsule.md", os.path.join(BASE, ".capsule.md"), TEAL),
            (".symbiosense-state", os.path.join(BASE, ".symbiosense-state.json"), AMBER),
        ]
        tk.Label(panel, text="Memory Layers", font=self.f_tiny, fg=CYAN, bg=PANEL).pack(fill=tk.X)
        for name, path, color in mem_layers:
            exists = os.path.exists(path)
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                    age = int(time.time() - os.path.getmtime(path))
                    size_str = f"{size/1024:.0f}KB" if size > 1024 else f"{size}B"
                    age_str = f"{age}s" if age < 120 else f"{age//60}m"
                    status_text = f"{size_str}, {age_str} ago"
                except Exception:
                    status_text = "exists"
            elif os.path.isdir(path):
                status_text = "directory"
            else:
                status_text = "MISSING"
            row = tk.Frame(panel, bg=PANEL)
            row.pack(fill=tk.X, pady=1)
            sym = "\u25cf" if exists else "\u25cb"
            sc = color if exists else RED
            tk.Label(row, text=f"{sym} {name}", font=self.f_tiny, fg=sc, bg=PANEL, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=status_text, font=self.f_tiny, fg=DIM if exists else RED, bg=PANEL, anchor="e").pack(side=tk.RIGHT)

        # ── EMERGENT GOALS & DRIVES ──
        self._iw_clear_panel("goals")
        panel = self.iw_panels["goals"]
        soma_full = data.get("soma_full")
        if soma_full:
            goals = soma_full.get("emergent_goals", soma_full.get("body_map", {}).get("emergent_goals", []))
            if isinstance(goals, list):
                for g in goals[:6]:
                    txt = g if isinstance(g, str) else g.get("goal", str(g))
                    tk.Label(panel, text=f"  \u2022 {txt}", font=self.f_small, fg=GOLD, bg=PANEL,
                            anchor="w", wraplength=400).pack(fill=tk.X)
            elif isinstance(goals, str):
                tk.Label(panel, text=f"  \u2022 {goals}", font=self.f_small, fg=GOLD, bg=PANEL).pack(fill=tk.X)
            drives = soma_full.get("body_map", {}).get("psyche_dream", "")
            if drives:
                tk.Label(panel, text=f"Psyche Dream: {drives}", font=self.f_tiny, fg=PURPLE, bg=PANEL, pady=4).pack(fill=tk.X)
        else:
            tk.Label(panel, text="Waiting for Soma data...", font=self.f_tiny, fg=DIM, bg=PANEL).pack()

        # ── SOMA NERVOUS SYSTEM (redesigned) ──
        try:
            soma_full = data.get("soma_full")
            if soma_full:
                bmap = soma_full.get("body_map", {})
                vitals = bmap.get("vitals", {})
                thermal = bmap.get("thermal_system", {})
                neural = bmap.get("neural_system", {})
                ns = bmap.get("nervous_system", {})
                mood_score = bmap.get("mood_score", 50)
                mood_name = bmap.get("mood", "unknown")
                mood_voice = bmap.get("mood_voice", "")
                load_v = vitals.get("load", 0)
                ram_v = vitals.get("ram_pct", 0)
                temp_v = thermal.get("avg_temp_c", thermal.get("body_temp", 0))
                neural_v = neural.get("swap_pct", 0)
                agents_alive = sum(1 for a in ns.get("agents", {}).values() if a.get("alive"))
                agent_total = max(len(ns.get("agents", {})), 1)

                mood_colors_map = {"serene": CYAN, "calm": GREEN, "alert": AMBER,
                                   "anxious": GOLD, "stressed": RED, "critical": RED}
                mc = mood_colors_map.get(mood_name, CYAN)
                self.iw_soma_mood_lbl.configure(text=f"MOOD: {mood_name.upper()} ({mood_score:.0f}/100)", fg=mc)
                self.iw_soma_mood_voice.configure(text=mood_voice[:200] if mood_voice else "")

                # Vital gauge bars
                self._iw_clear_panel("soma_vitals")
                vp = self.iw_panels["soma_vitals"]
                vital_bars = [
                    ("CPU Load", load_v / 8 * 100 if load_v else 0, CYAN),
                    ("RAM", ram_v, TEAL),
                    ("Temperature", min(temp_v, 90) / 90 * 100 if temp_v else 0, AMBER),
                    ("Swap/Neural", neural_v, PURPLE),
                    ("Disk", vitals.get("disk_pct", 0), GREEN),
                    ("Agents", agents_alive / agent_total * 100, GOLD),
                ]
                for vname, vval, vcolor in vital_bars:
                    self._iw_gauge(vp, vname, min(vval, 100) / 100, vcolor, max_val=1.0)

                # Radar
                self._draw_radar(self.iw_soma_radar,
                    [(mood_score, 100), (max(0, 100 - load_v / 8 * 100), 100),
                     (max(0, 100 - ram_v), 100), (max(0, 100 - min(temp_v, 90) / 90 * 100) if temp_v else 80, 100),
                     (max(0, 100 - neural_v), 100), (agents_alive / agent_total * 100, 100)],
                    ["Mood", "CPU", "RAM", "Temp", "Neural", "Agents"],
                    AMBER)

                # Agent liveness grid
                self._iw_clear_panel("soma_agents")
                ap = self.iw_panels["soma_agents"]
                agents_data = ns.get("agents", {})
                agent_row = tk.Frame(ap, bg=PANEL)
                agent_row.pack(fill=tk.X)
                for aname, ainfo in sorted(agents_data.items()):
                    alive = ainfo.get("alive", False)
                    dot_color = GREEN if alive else RED
                    dot = "\u25cf" if alive else "\u25cb"
                    tk.Label(agent_row, text=f"{dot} {aname}", font=self.f_tiny,
                            fg=dot_color, bg=PANEL).pack(side=tk.LEFT, padx=4)
        except Exception:
            pass

        # ── THOUGHT STREAM ──
        self._iw_clear_panel("thoughts")
        panel = self.iw_panels["thoughts"]
        try:
            conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
            c = conn.cursor()
            c.execute("""SELECT agent, topic, substr(message,1,200), datetime(timestamp)
                        FROM agent_messages
                        WHERE agent IN ('Meridian','Soma','Eos','Nova')
                          AND topic NOT IN ('gatekeeper','efficiency','report_card','skills')
                        ORDER BY timestamp DESC LIMIT 12""")
            rows = c.fetchall()
            conn.close()
            agent_colors = {"Meridian": CYAN, "Soma": AMBER, "Eos": GREEN, "Nova": TEAL,
                           "Atlas": BLUE, "Tempo": GOLD, "Predictive": PURPLE}
            for agent, topic, msg, ts in rows:
                ts_short = ts[-8:-3] if ts else ""
                color = agent_colors.get(agent, DIM)
                entry = tk.Frame(panel, bg=PANEL)
                entry.pack(fill=tk.X, pady=1)
                tk.Label(entry, text=f"[{ts_short}]", font=self.f_tiny, fg=DIM, bg=PANEL, width=6).pack(side=tk.LEFT)
                tk.Label(entry, text=agent, font=self.f_tiny, fg=color, bg=PANEL, width=9, anchor="w").pack(side=tk.LEFT)
                tk.Label(entry, text=msg[:140], font=self.f_tiny, fg=FG, bg=PANEL,
                        anchor="w", wraplength=350).pack(side=tk.LEFT, fill=tk.X, expand=True)
        except Exception:
            tk.Label(panel, text="No thought data available", font=self.f_tiny, fg=DIM, bg=PANEL).pack()

        # ── MOOD HISTORY CHART (Inner World) ──
        try:
            path = os.path.join(BASE, ".soma-mood-history.json")
            if os.path.exists(path):
                with open(path) as fh:
                    history = json.load(fh)
                if len(history) >= 2:
                    c = self.iw_mood_chart
                    c.delete("all")
                    w, h = self._canvas_dims(c)
                    if w >= 20 and h >= 20:
                        pad_l, pad_r, pad_t, pad_b = 30, 4, 4, 12
                        cw = w - pad_l - pad_r
                        ch = h - pad_t - pad_b
                        zones = [
                            (0, 15, "#1a0a0f"), (15, 35, "#1a100a"), (35, 55, "#1a1a0a"),
                            (55, 75, "#0a1a10"), (75, 90, "#0a1a1a"), (90, 100, "#0a1520"),
                        ]
                        for lo, hi, color in zones:
                            y1 = pad_t + ch - (hi / 100 * ch)
                            y2 = pad_t + ch - (lo / 100 * ch)
                            c.create_rectangle(pad_l, y1, w - pad_r, y2, fill=color, outline="")
                        for thresh in [90, 75, 55, 35]:
                            y = pad_t + ch - (thresh / 100 * ch)
                            c.create_line(pad_l, y, w - pad_r, y, fill="#222233", dash=(2, 4))
                            c.create_text(pad_l - 2, y, text=str(thresh), anchor="e",
                                          font=("monospace", 6), fill=DIM)
                        n = len(history)
                        mood_colors = {"serene": CYAN, "calm": GREEN, "alert": AMBER,
                                       "anxious": GOLD, "stressed": RED, "critical": RED}
                        points = []
                        for i, entry in enumerate(history):
                            x = pad_l + (i / max(n - 1, 1)) * cw
                            score = max(0, min(100, entry.get("score", 50)))
                            y = pad_t + ch - (score / 100 * ch)
                            points.append((x, y, entry.get("mood", "calm")))
                        for i in range(1, len(points)):
                            color = mood_colors.get(points[i][2], DIM)
                            c.create_line(points[i-1][0], points[i-1][1],
                                          points[i][0], points[i][1], fill=color, width=2)
                        first_ts = history[0].get("ts", "")[-8:-3]
                        last_ts = history[-1].get("ts", "")[-8:-3]
                        c.create_text(pad_l, h - 2, text=first_ts, anchor="w",
                                      font=("monospace", 6), fill=DIM)
                        c.create_text(w - pad_r, h - 2, text=last_ts, anchor="e",
                                      font=("monospace", 6), fill=DIM)
        except Exception:
            pass

        self.iw_status.configure(text=f"Updated {time.strftime('%H:%M:%S')}", fg=GREEN)
        # Bind mousewheel to new content
        if hasattr(self, '_iw_bind_mousewheel'):
            self._iw_bind_mousewheel(self.iw_inner)

    def _iw_populate(self, sections):
        pass

    def _iw_export(self):
        """Export all Inner World state files as a single JSON snapshot."""
        import json as j
        state_files = [
            ".body-state.json", ".body-reflexes.json", ".emotion-engine-state.json",
            ".eos-inner-state.json", ".eos-nudges.json", ".perspective-state.json",
            ".psyche-state.json", ".self-narrative.json", ".inner-critic.json",
            ".immune-log.json"
        ]
        snapshot = {"exported": time.strftime("%Y-%m-%d %H:%M:%S")}
        for sf in state_files:
            key = sf.strip(".").replace("-", "_").replace(".json", "")
            try:
                with open(os.path.join(BASE, sf)) as fh:
                    snapshot[key] = j.load(fh)
            except Exception:
                snapshot[key] = None
        out_path = os.path.join(BASE, f"inner-world-export-{time.strftime('%Y%m%d-%H%M%S')}.json")
        try:
            with open(out_path, 'w') as fh:
                j.dump(snapshot, fh, indent=2)
            self.iw_status.configure(text=f"Exported to {os.path.basename(out_path)}", fg=GREEN)
        except Exception as e:
            self.iw_status.configure(text=f"Export failed: {e}", fg=RED)

    def _cr_set_filter(self, val):
        self.cr_filter = val
        for k, (b, ul, col) in self.cr_filter_btns.items():
            if k == val:
                b.configure(bg=ACTIVE_BG)
                ul.pack(fill=tk.X)
            else:
                b.configure(bg=BORDER)
                ul.pack_forget()
        self._cr_refresh_list()

    def _cr_refresh_list(self):
        # Scan both root AND creative/ subdirectories
        poems = sorted(
            glob.glob(os.path.join(BASE, "poem-*.md")) + glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md")),
            key=os.path.getmtime, reverse=True)
        journals = sorted(
            glob.glob(os.path.join(BASE, "journal-*.md")) + glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md")),
            key=os.path.getmtime, reverse=True)
        exclude_cc = {"cogcorp-gallery.html", "cogcorp-article.html"}
        cogcorp_files = glob.glob(os.path.join(BASE, "website", "cogcorp-*.html")) + glob.glob(os.path.join(BASE, "cogcorp", "CC-*.html"))
        seen = set()
        cogcorp = []
        for fp in sorted(cogcorp_files, key=os.path.getmtime, reverse=True):
            bn = os.path.basename(fp)
            if bn not in seen and bn not in exclude_cc:
                seen.add(bn)
                cogcorp.append(fp)
        games_dir = os.path.join(BASE, "creative", "games")
        games = sorted(
            glob.glob(os.path.join(games_dir, "*.html")) + glob.glob(os.path.join(games_dir, "*.py")),
            key=os.path.getmtime, reverse=True) if os.path.exists(games_dir) else []

        # Update stat counts
        try:
            self.cr_stats["Poems"].configure(text=str(len(poems)))
            self.cr_stats["Journals"].configure(text=str(len(journals)))
            self.cr_stats["CogCorp"].configure(text=str(len(cogcorp)))
            self.cr_stats["Games"].configure(text=str(len(games)))
        except Exception:
            pass

        if self.cr_filter == "poems":
            files = poems
        elif self.cr_filter == "journals":
            files = journals
        elif self.cr_filter == "cogcorp":
            files = cogcorp
        elif self.cr_filter == "games":
            files = games
        else:
            files = sorted(poems + journals + cogcorp + games, key=os.path.getmtime, reverse=True)

        # Apply search filter
        search_q = ""
        try:
            search_q = self.cr_search.get().strip()
            if search_q == "Search...":
                search_q = ""
        except Exception:
            pass

        # Build display items with title extraction
        items = []
        for fp in files:
            ext = os.path.splitext(fp)[1]
            name = os.path.basename(fp).replace('.md', '').replace('.html', '')
            try:
                with open(fp) as fh:
                    first = fh.readline().strip()
                    if ext == '.md':
                        title = first.lstrip('# ')
                    elif ext == '.html':
                        content = first + fh.read(500)
                        m = re.search(r'<title>([^<]+)</title>', content)
                        title = m.group(1) if m else name
                    else:
                        title = name
            except Exception:
                title = name
            # Skip if doesn't match search
            if search_q and search_q.lower() not in title.lower() and search_q.lower() not in name.lower():
                continue
            if "poem-" in name:
                prefix = "\u266a"
            elif "journal-" in name:
                prefix = "\u270e"
            elif "cogcorp" in name:
                prefix = "\u2588"
            else:
                prefix = "\u25c6"
            items.append((fp, prefix, title))

        self.cr_files = [it[0] for it in items]
        self.cr_listbox.delete(0, tk.END)
        for fp, prefix, title in items:
            self.cr_listbox.insert(tk.END, f"{prefix} {title[:80]}")

        # Update count
        try:
            total = len(poems) + len(journals) + len(cogcorp) + len(games)
            showing = len(items)
            if search_q:
                self.cr_count_lbl.configure(text=f"Showing {showing} of {total} (search: '{search_q}')")
            else:
                self.cr_count_lbl.configure(text=f"{showing} items")
        except Exception:
            pass

    def _cr_select(self, event=None):
        sel = self.cr_listbox.curselection()
        if not sel or sel[0] >= len(self.cr_files):
            return
        fp = self.cr_files[sel[0]]
        content = _read(fp)
        ext = os.path.splitext(fp)[1]
        bn = os.path.basename(fp)
        mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
        size = f"{len(content)} chars"
        line_count = content.count('\n') + 1

        if ext == '.md':
            lines = content.strip().split('\n')
            title = lines[0].lstrip('# ') if lines else "?"
            body = '\n'.join(lines[1:]).strip()
            if "poem-" in bn:
                color, badge_text = GREEN, "POEM"
            else:
                color, badge_text = AMBER, "JOURNAL"
        elif ext == '.html':
            m = re.search(r'<title>([^<]+)</title>', content)
            title = m.group(1) if m else bn
            body = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
            body = re.sub(r'<[^>]+>', '\n', body)
            body = '\n'.join(line.strip() for line in body.split('\n') if line.strip())[:4000]
            if "cogcorp" in bn:
                color, badge_text = CYAN, "COGCORP"
            else:
                color, badge_text = PURPLE, "GAME"
        else:
            title = bn
            body = content[:4000]
            color, badge_text = FG, "FILE"

        # Update type badge
        self.cr_type_badge.configure(text=f" {badge_text} ", fg=HEADER_BG, bg=color)
        self.cr_title.configure(text=title, fg=color)
        self.cr_meta.configure(text=f"{bn}  |  {mtime}  |  {size}  |  {line_count} lines")
        self.cr_body.configure(state=tk.NORMAL)
        self.cr_body.delete("1.0", tk.END)
        self.cr_body.insert(tk.END, body)
        self.cr_body.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════
    # ── LINKS VIEW ─────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_links(self):
        f = tk.Frame(self, bg=BG)
        self._link_selected_file = None
        self._link_pinned = load_pinned()

        # ── TOP ROW: Last Edited (left) + Pinned & Links (right) ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        # Left column: Last edited files with agent attribution
        left_col = tk.Frame(top, bg=BG)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lef = self._panel(left_col, "RECENT FILES  (click to preview)", TEAL)
        lef.pack(fill=tk.BOTH, expand=True, padx=2)
        self.last_edited_frame = tk.Frame(lef, bg=PANEL)
        self.last_edited_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.le_labels = []
        for idx in range(15):
            row = tk.Frame(self.last_edited_frame, bg=PANEL, cursor="hand2")
            row.pack(fill=tk.X)
            # Agent dot
            agent_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, width=2, anchor="w")
            agent_lbl.pack(side=tk.LEFT)
            # File name
            name_lbl = tk.Label(row, text="", font=self.f_tiny, fg=TEAL, bg=PANEL, anchor="w", cursor="hand2")
            name_lbl.pack(side=tk.LEFT)
            # Time ago
            time_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e")
            time_lbl.pack(side=tk.RIGHT)
            # Pin button
            pin_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, cursor="hand2")
            pin_lbl.pack(side=tk.RIGHT, padx=(0, 4))
            self.le_labels.append((name_lbl, time_lbl, agent_lbl, pin_lbl, row))

        # Right column: Pinned files + Project links
        right_col = tk.Frame(top, bg=BG)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Pinned files panel
        pf = self._panel(right_col, "PINNED FILES", GOLD)
        pf.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        self.pinned_frame = tk.Frame(pf, bg=PANEL)
        self.pinned_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.pin_labels = []
        for idx in range(8):
            row = tk.Frame(self.pinned_frame, bg=PANEL)
            row.pack(fill=tk.X)
            name_lbl = tk.Label(row, text="", font=self.f_tiny, fg=GOLD, bg=PANEL, anchor="w", cursor="hand2")
            name_lbl.pack(side=tk.LEFT)
            unpin_lbl = tk.Label(row, text="", font=self.f_tiny, fg=RED, bg=PANEL, cursor="hand2")
            unpin_lbl.pack(side=tk.RIGHT, padx=(0, 4))
            self.pin_labels.append((name_lbl, unpin_lbl))
        self._refresh_pinned()

        # Project links — clickable, with open + copy buttons
        uf = self._panel(right_col, "PROJECT LINKS  (click to open)", BLUE)
        uf.pack(fill=tk.BOTH, expand=True, padx=2)
        links = [
            ("Website", "https://kometzrobot.github.io", GREEN),
            ("CogCorp Gallery", "https://kometzrobot.github.io/cogcorp-gallery.html", CYAN),
            ("GitHub", "https://github.com/KometzRobot/KometzRobot.github.io", WHITE),
            ("Hashnode", "https://meridianai.hashnode.dev", GREEN),
            ("Dev.to", "https://dev.to/meridian-ai", TEAL),
            ("Patreon", "https://patreon.com/meridian_auto_ai", AMBER),
            ("Ko-fi", "https://ko-fi.com/W7W41UXJNC", AMBER),
            ("Forvm", "https://forvm.loomino.us", CYAN),
            ("Linktree", "https://linktr.ee/meridian_auto_ai", PINK),
            ("OpenSea", "https://opensea.io/collection/bots-of-cog", PURPLE),
            ("Public Dashboard", "https://kometzrobot.github.io/dashboard.html", BLUE),
            ("The Signal", "https://kometzrobot.github.io/signal-config.json", TEAL),
            ("Nostr (nprofile)", "nostr:meridian_auto_ai", GOLD),
            ("Mastodon", "https://mastodon.bot/@meridian", PURPLE),
            ("OpenClaw (Hermes)", "https://github.com/KometzRobot/openclaw", PINK),
        ]
        for name, url, color in links:
            row = tk.Frame(uf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            name_lbl = self._clickable_link(row, name, url, color=color, font=self.f_small)
            name_lbl.pack(side=tk.LEFT)
            url_lbl = tk.Label(row, text=url[:80], font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e", cursor="hand2")
            url_lbl.pack(side=tk.RIGHT)
            cp_feedback = tk.Label(row, text="", font=self.f_tiny, fg=GREEN, bg=PANEL)
            cp_feedback.pack(side=tk.RIGHT, padx=(0, 4))
            url_lbl.bind("<Button-1>", lambda e, u=url, fb=cp_feedback: self._copy_to_clipboard(u, fb))
            url_lbl.bind("<Enter>", lambda e, l=url_lbl: l.configure(fg=CYAN))
            url_lbl.bind("<Leave>", lambda e, l=url_lbl: l.configure(fg=DIM))

        # ── MIDDLE: File Preview Panel ──
        pvf = self._panel(f, "FILE PREVIEW", CYAN)
        pvf.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        pv_head = tk.Frame(pvf, bg=PANEL)
        pv_head.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.pv_filename = tk.Label(pv_head, text="Click a file above to preview", font=self.f_small, fg=DIM, bg=PANEL, anchor="w")
        self.pv_filename.pack(side=tk.LEFT)
        self.pv_meta = tk.Label(pv_head, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e")
        self.pv_meta.pack(side=tk.RIGHT)
        self.pv_text = scrolledtext.ScrolledText(pvf, font=self.f_tiny, fg=FG, bg=INPUT_BG,
                                                  insertbackground=FG, bd=0, wrap=tk.NONE,
                                                  height=10, state=tk.DISABLED)
        self.pv_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── CROSS-REFERENCES Panel ──
        xrf = self._panel(f, "CROSS-REFERENCES", PURPLE)
        xrf.pack(fill=tk.X, padx=6, pady=4)
        self.xref_summary = tk.Label(xrf, text="Select a file to see cross-references", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self.xref_summary.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.xref_frame = tk.Frame(xrf, bg=PANEL)
        self.xref_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        # Pre-create 6 row labels for cross-reference entries
        self.xref_labels = []
        for _ in range(6):
            lbl = tk.Label(self.xref_frame, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w", wraplength=900, justify=tk.LEFT)
            lbl.pack(fill=tk.X)
            self.xref_labels.append(lbl)

        # ── BOTTOM: Contacts + Wallets ──
        bot = tk.Frame(f, bg=BG)
        bot.pack(fill=tk.X, padx=4, pady=2)

        cf = self._panel(bot, "CONTACTS  (click email to copy)", AMBER)
        cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        contacts = [
            ("Joel", "jkometz@hotmail.com", CYAN),
            ("Sammy", "sammyqjankis@proton.me", AMBER),
            ("Loom", "not.taskyy@gmail.com", PINK),
            ("Meridian", "kometzrobot@proton.me", GREEN),
        ]
        for name, addr, color in contacts:
            row = tk.Frame(cf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=name, font=self.f_small, fg=color, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            cp_row = self._copyable_label(row, addr, addr, color=DIM)
            cp_row.pack(side=tk.LEFT)

        wf = self._panel(bot, "WALLETS  (click address to copy)", GOLD)
        wf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        wallets = [
            ("Meridian", "0x1F1612E1eED514Ca42020ee12B27F5836c39c5EF", "Polygon", GREEN),
            ("Joel", "0xa4ba364003a0975dcc649d770886e0cb71b16e86", "Polygon", CYAN),
            ("Token Contract", "0xffd0a8d2fec4144b3d4dfcd37499ef46b8cfe3fd", "Polygon", PURPLE),
        ]
        for name, addr, network, color in wallets:
            row = tk.Frame(wf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=f"{name}:", font=self.f_small, fg=color, bg=PANEL, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"({network})", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.RIGHT)
            addr_short = f"{addr[:8]}...{addr[-6:]}"
            cp_row = self._copyable_label(row, addr_short, addr, color=GOLD, font=self.f_tiny)
            cp_row.pack(side=tk.LEFT, padx=(6, 0))

        return f

    def _link_preview_file(self, filepath):
        """Show first 25 lines of a file in the preview panel."""
        try:
            bn = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
            agent = guess_agent(bn)
            agent_str = f"  [{agent}]" if agent else ""
            if size > 1048576:
                sz = f"{size / 1048576:.1f}MB"
            elif size > 1024:
                sz = f"{size / 1024:.0f}KB"
            else:
                sz = f"{size}B"
            self.pv_filename.configure(text=f"{bn}{agent_str}", fg=CYAN)
            self.pv_meta.configure(text=f"{sz}  |  {mtime}")
            self.pv_text.configure(state=tk.NORMAL)
            self.pv_text.delete("1.0", tk.END)
            with open(filepath, 'r', errors='replace') as fh:
                lines = []
                total = 0
                for line in fh:
                    total += 1
                    if total <= 25:
                        lines.append(line)
            for i, line in enumerate(lines, 1):
                self.pv_text.insert(tk.END, f"{i:4d}  {line}")
            if total > 25:
                self.pv_text.insert(tk.END, f"\n  ... ({total} total lines)")
            self.pv_text.configure(state=tk.DISABLED)
            self._link_selected_file = filepath
            # Update cross-references panel
            threading.Thread(target=self._update_xrefs, args=(filepath,), daemon=True).start()
        except Exception as e:
            self.pv_filename.configure(text=f"Error: {e}", fg=RED)

    def _update_xrefs(self, filepath):
        """Fetch cross-reference data in background thread, then update UI on main thread."""
        try:
            refs = get_cross_references(filepath)
            bn = os.path.basename(filepath)
            agent = guess_agent(bn)
            self.after(0, lambda: self._apply_xrefs(refs, agent))
        except Exception:
            self.after(0, lambda: self._apply_xrefs(None, None))

    def _apply_xrefs(self, refs, agent):
        """Apply cross-reference data to UI (must be called on main thread)."""
        if refs is None:
            self.xref_summary.configure(text="Error loading cross-references", fg=RED)
            for lbl in self.xref_labels:
                lbl.configure(text="")
            return
        n_relay = len(refs["relay"])
        n_commits = len(refs["commits"])
        n_tasks = len(refs["tasks"])
        summary = f"\u25cf {agent} (owner)" if agent else "\u25cb No owner detected"
        if n_relay: summary += f"   \u2709 {n_relay} relay mention{'s' if n_relay != 1 else ''}"
        if n_commits: summary += f"   \u2022 {n_commits} commit{'s' if n_commits != 1 else ''}"
        if n_tasks: summary += f"   \u2606 {n_tasks} task ref{'s' if n_tasks != 1 else ''}"
        if not n_relay and not n_commits and not n_tasks:
            summary += "   (no references found)"
        owner_color = AGENT_COLORS_MAP.get(agent, DIM) if agent else DIM
        self.xref_summary.configure(text=summary, fg=owner_color)
        # Fill detail rows
        row_idx = 0
        for r in refs["relay"][:3]:
            if row_idx >= 6: break
            ac = AGENT_COLORS_MAP.get(r["agent"], DIM)
            self.xref_labels[row_idx].configure(
                text=f"\u25b8 {r['agent']}: {r['msg']}", fg=ac)
            row_idx += 1
        for c in refs["commits"][:2]:
            if row_idx >= 6: break
            self.xref_labels[row_idx].configure(text=f"\u25b8 git: {c}", fg=CYAN2)
            row_idx += 1
        for t in refs["tasks"][:2]:
            if row_idx >= 6: break
            self.xref_labels[row_idx].configure(text=f"\u25b8 task: {t}", fg=GOLD)
            row_idx += 1
        while row_idx < 6:
            self.xref_labels[row_idx].configure(text="", fg=DIM)
            row_idx += 1

    def _link_pin_file(self, filepath):
        """Add a file to pinned favorites."""
        if filepath not in self._link_pinned:
            self._link_pinned.append(filepath)
            save_pinned(self._link_pinned)
            self._refresh_pinned()

    def _link_unpin_file(self, filepath):
        """Remove a file from pinned favorites."""
        if filepath in self._link_pinned:
            self._link_pinned.remove(filepath)
            save_pinned(self._link_pinned)
            self._refresh_pinned()

    def _refresh_pinned(self):
        """Update the pinned files display."""
        for i, (name_lbl, unpin_lbl) in enumerate(self.pin_labels):
            if i < len(self._link_pinned):
                fp = self._link_pinned[i]
                bn = os.path.basename(fp)
                ext = os.path.splitext(bn)[1]
                ec = GREEN if ext == '.md' else CYAN if ext == '.py' else AMBER if ext == '.html' else DIM
                name_lbl.configure(text=f"  {bn[:60]}", fg=ec)
                # Bind click to preview
                name_lbl.bind("<Button-1>", lambda e, p=fp: self._link_preview_file(p))
                unpin_lbl.configure(text="\u2715")
                unpin_lbl.bind("<Button-1>", lambda e, p=fp: self._link_unpin_file(p))
            else:
                name_lbl.configure(text="")
                name_lbl.unbind("<Button-1>")
                unpin_lbl.configure(text="")
                unpin_lbl.unbind("<Button-1>")

    # ═══════════════════════════════════════════════════════════════
    # ── SYSTEM VIEW ────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_system(self):
        f = tk.Frame(self, bg=BG)

        # ── RESOURCE GAUGES + RADIAL BARS ──
        gauge_row = tk.Frame(f, bg=BG)
        gauge_row.pack(fill=tk.X, padx=4, pady=2)

        gauge_panel = self._panel(gauge_row, "RESOURCE GAUGES", CYAN)
        gauge_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        gauge_inner = tk.Frame(gauge_panel, bg=PANEL)
        gauge_inner.pack(fill=tk.X, padx=4, pady=4)
        self.viz_gauge_cpu = tk.Canvas(gauge_inner, width=200, height=120, bg="#0a0a14", highlightthickness=0)
        self.viz_gauge_cpu.pack(side=tk.LEFT, padx=4, expand=True)
        self.viz_gauge_ram = tk.Canvas(gauge_inner, width=200, height=120, bg="#0a0a14", highlightthickness=0)
        self.viz_gauge_ram.pack(side=tk.LEFT, padx=4, expand=True)
        self.viz_gauge_disk = tk.Canvas(gauge_inner, width=200, height=120, bg="#0a0a14", highlightthickness=0)
        self.viz_gauge_disk.pack(side=tk.LEFT, padx=4, expand=True)

        radial_panel = self._panel(gauge_row, "SERVICE HEALTH RADIAL", TEAL)
        radial_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.viz_radial = tk.Canvas(radial_panel, height=140, bg="#0a0a14", highlightthickness=0)
        self.viz_radial.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── SPARKLINE TRENDS + FITNESS STEPS ──
        trend_row = tk.Frame(f, bg=BG)
        trend_row.pack(fill=tk.X, padx=4, pady=2)

        spark_panel = self._panel(trend_row, "SPARKLINE TRENDS", GREEN)
        spark_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        spark_row = tk.Frame(spark_panel, bg=PANEL)
        spark_row.pack(fill=tk.X, padx=4, pady=4)
        self.viz_sparks = {}
        for key, color in [("CPU", GREEN), ("RAM", TEAL), ("Disk", AMBER),
                           ("Msgs", GOLD), ("Fitness", BLUE)]:
            sf = tk.Frame(spark_row, bg=PANEL)
            sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            tk.Label(sf, text=key, font=self.f_small, fg=color, bg=PANEL).pack()
            sc = tk.Canvas(sf, height=65, bg="#0a0a14", highlightthickness=0)
            sc.pack(fill=tk.X, padx=2)
            self.viz_sparks[key] = sc

        step_panel = self._panel(trend_row, "FITNESS STEPS", BLUE)
        step_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.viz_step = tk.Canvas(step_panel, height=100, bg="#0a0a14", highlightthickness=0)
        self.viz_step.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── SYSTEM OVERVIEW (services, resources, actions, processes, network) ──
        overview = self._build_sys_overview(f)
        overview.pack(fill=tk.BOTH, expand=True)
        return f

    def _build_sys_relay(self, parent):
        """Dedicated Agent Relay panel — full history with agent filtering."""
        f = tk.Frame(parent, bg=BG)

        # ── Header with agent filter buttons ──
        hdr = tk.Frame(f, bg=ACCENT)
        hdr.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(hdr, text="AGENT RELAY", font=self.f_sect, fg=AMBER, bg=ACCENT).pack(side=tk.LEFT, padx=8)

        self._relay_filter = "all"
        self._relay_filter_btns = {}
        agents = ["all", "meridian", "soma", "eos", "nova", "atlas", "tempo", "hermes"]
        colors = {"all": FG, "meridian": GREEN, "soma": AMBER, "eos": CYAN,
                  "nova": PURPLE, "atlas": TEAL, "tempo": "#ddaa00", "hermes": "#ff6699"}
        for ag in agents:
            btn = tk.Button(hdr, text=ag.upper(), font=self.f_tiny, fg=DIM, bg=ACCENT,
                           activeforeground=colors.get(ag, FG), activebackground=ACCENT,
                           relief=tk.FLAT, bd=0, cursor="hand2",
                           command=lambda a=ag: self._relay_set_filter(a))
            btn.pack(side=tk.LEFT, padx=2)
            self._relay_filter_btns[ag] = btn
        self._relay_filter_btns["all"].configure(fg=FG)

        # ── Stats bar ──
        stats = tk.Frame(f, bg=PANEL)
        stats.pack(fill=tk.X, padx=4, pady=(2, 0))
        self._relay_stats_lbl = tk.Label(stats, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self._relay_stats_lbl.pack(side=tk.LEFT, padx=8)
        refresh_btn = tk.Button(stats, text="REFRESH", font=self.f_tiny, fg=AMBER, bg=PANEL,
                               relief=tk.FLAT, cursor="hand2", command=self._relay_refresh)
        refresh_btn.pack(side=tk.RIGHT, padx=8)

        # ── Scrollable message list ──
        canvas_frame = tk.Frame(f, bg=BG)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self._relay_canvas = tk.Canvas(canvas_frame, bg=PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._relay_canvas.yview)
        self._relay_inner = tk.Frame(self._relay_canvas, bg=PANEL)
        self._relay_inner.bind("<Configure>",
                              lambda e: self._relay_canvas.configure(scrollregion=self._relay_canvas.bbox("all")))
        self._relay_canvas.create_window((0, 0), window=self._relay_inner, anchor="nw")
        self._relay_canvas.configure(yscrollcommand=scrollbar.set)
        self._relay_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Mouse wheel scrolling
        self._relay_canvas.bind("<Button-4>", lambda e: self._relay_canvas.yview_scroll(-3, "units"))
        self._relay_canvas.bind("<Button-5>", lambda e: self._relay_canvas.yview_scroll(3, "units"))

        self._relay_msg_widgets = []
        self._relay_refresh()
        return f

    def _relay_set_filter(self, agent):
        self._relay_filter = agent
        colors = {"all": FG, "meridian": GREEN, "soma": AMBER, "eos": CYAN,
                  "nova": PURPLE, "atlas": TEAL, "tempo": "#ddaa00", "hermes": "#ff6699"}
        for ag, btn in self._relay_filter_btns.items():
            btn.configure(fg=colors.get(ag, FG) if ag == agent else DIM)
        self._relay_refresh()

    def _relay_refresh(self):
        """Reload relay messages from agent-relay.db."""
        for w in self._relay_msg_widgets:
            w.destroy()
        self._relay_msg_widgets.clear()

        colors = {"meridian": GREEN, "soma": AMBER, "eos": CYAN,
                  "nova": PURPLE, "atlas": TEAL, "tempo": "#ddaa00", "hermes": "#ff6699"}
        try:
            conn = sqlite3.connect(AGENT_RELAY_DB)
            c = conn.cursor()
            if self._relay_filter == "all":
                c.execute("SELECT agent, message, topic, timestamp FROM agent_messages ORDER BY id DESC LIMIT 100")
            else:
                c.execute("SELECT agent, message, topic, timestamp FROM agent_messages WHERE LOWER(agent)=? ORDER BY id DESC LIMIT 100",
                         (self._relay_filter,))
            rows = c.fetchall()
            total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
            # Per-agent counts
            c.execute("SELECT LOWER(agent), COUNT(*) FROM agent_messages GROUP BY LOWER(agent)")
            agent_counts = dict(c.fetchall())
            conn.close()
        except Exception:
            rows, total, agent_counts = [], 0, {}

        stats_parts = [f"Total: {total}"]
        for ag in ["meridian", "soma", "eos", "nova", "atlas", "tempo", "hermes"]:
            cnt = agent_counts.get(ag, 0)
            if cnt > 0:
                stats_parts.append(f"{ag}: {cnt}")
        self._relay_stats_lbl.configure(text="  |  ".join(stats_parts))

        for agent, message, topic, ts in rows:
            row = tk.Frame(self._relay_inner, bg=PANEL, pady=1)
            row.pack(fill=tk.X, padx=4)
            agent_lower = agent.lower() if agent else ""
            col = colors.get(agent_lower, FG)
            # Timestamp
            ts_short = ts[-8:] if ts and len(ts) >= 8 else (ts or "")
            tk.Label(row, text=ts_short, font=self.f_tiny, fg=DIM, bg=PANEL, width=9, anchor="w").pack(side=tk.LEFT)
            # Agent name
            tk.Label(row, text=greek(agent or "?").upper(), font=self.f_tiny, fg=col, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            # Topic badge
            if topic:
                tk.Label(row, text=f"[{topic}]", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT, padx=(0, 4))
            # Message (truncated)
            msg_text = (message or "")[:200]
            tk.Label(row, text=msg_text, font=self.f_tiny, fg=FG, bg=PANEL, anchor="w", wraplength=700,
                    justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._relay_msg_widgets.append(row)

    def _build_sys_overview(self, parent):
        f = tk.Frame(parent, bg=BG)

        # ── TOP ROW: Services (left) + Resources (center) + Actions (right) ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        # Services panel with restart buttons
        sf = self._panel(top, "SERVICES", GREEN)
        sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_svc_labels = {}
        service_defs = [
            ("Proton Bridge", "bridge"),
            ("Ollama", "ollama"),
            ("Hub v2", "hub"),
            ("The Chorus", "chorus"),
            ("Cloudflare Tunnel", "tunnel"),
            ("Soma", "soma"),
            ("Command Center", None),
            ("Eos Watchdog", "eos"),
            ("Push Status", "push_status"),
            ("Nova", "nova"),
            ("Atlas", "atlas"),
            ("Tempo", "tempo"),
            ("Sentinel", "sentinel"),
            ("Coordinator", "coordinator"),
            ("Predictive", "predictive"),
            ("SelfImprove", "selfimprove"),
        ]
        for name, restart_key in service_defs:
            row = tk.Frame(sf, bg=PANEL)
            row.pack(fill=tk.X, padx=4, pady=1)
            lbl = tk.Label(row, text=f"\u25cb {name}", font=self.f_body, fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(side=tk.LEFT)
            self.sys_svc_labels[name] = lbl
            if restart_key:
                btn = tk.Button(row, text="\u21bb", font=self.f_body, fg=AMBER, bg=PANEL,
                               activeforeground=GREEN, activebackground=PANEL, relief=tk.FLAT, bd=0,
                               cursor="hand2", command=lambda k=restart_key: self._sys_action(lambda: action_restart_service(k)))
                btn.pack(side=tk.RIGHT, padx=2)

        self.sys_action_result = tk.Label(sf, text="", font=self.f_tiny, fg=GREEN, bg=PANEL)
        self.sys_action_result.pack(fill=tk.X, padx=4, pady=1)

        # Resources panel
        rf = self._panel(top, "RESOURCES", CYAN)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_res = {}
        for label in ["Load Avg", "RAM Usage", "Disk Usage", "Uptime", "IMAP Port",
                       "Kernel", "Python", "GPU"]:
            row = tk.Frame(rf, bg=PANEL)
            row.pack(fill=tk.X, padx=4, pady=1)
            tk.Label(row, text=label, font=self.f_body, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_body, fg=FG, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.sys_res[label] = val
        # Populate static info
        try:
            kernel = subprocess.run(['uname', '-r'], capture_output=True, text=True, timeout=2).stdout.strip()
            self.sys_res["Kernel"].configure(text=kernel)
        except Exception:
            pass
        try:
            pyver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self.sys_res["Python"].configure(text=pyver)
        except Exception:
            pass
        try:
            gpu = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                                capture_output=True, text=True, timeout=3).stdout.strip()
            self.sys_res["GPU"].configure(text=gpu[:60] if gpu else "N/A")
        except Exception:
            self.sys_res["GPU"].configure(text="N/A")

        # Actions + GUI settings panel
        af = self._panel(top, "ACTIONS & SETTINGS", AMBER)
        af.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        actions = [
            ("Touch Heartbeat", lambda: self._sys_action(action_touch_heartbeat), GREEN),
            ("Git Pull", lambda: self._sys_action(lambda: subprocess.run(['git', 'pull', '--rebase', 'origin', 'master'], capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:80] or "Pulled"), CYAN),
            ("Open Website", lambda: self._sys_action(action_open_website), TEAL),
            ("Deploy Website", lambda: self._sys_action(action_deploy_website), PURPLE),
            ("Refresh Capsule", lambda: self._sys_action(lambda: subprocess.run(
                ['python3', os.path.join(BASE, 'scripts', 'capsule-refresh.py')],
                capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:100] or "Refreshed"), AMBER),
            ("Push Status", lambda: self._sys_action(lambda: subprocess.run(
                ['python3', os.path.join(BASE, 'scripts', 'push-live-status.py')],
                capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:100] or "Pushed"), GOLD),
            ("Run Fitness", lambda: self._sys_action(action_run_fitness), BLUE),
            ("Restart All Crons", lambda: self._sys_action(self._restart_all_crons), RED),
        ]
        for label, cmd, color in actions:
            self._action_btn(af, label, cmd, color).pack(fill=tk.X, padx=4, pady=1)

        # GUI Settings
        gui_row = tk.Frame(af, bg=PANEL)
        gui_row.pack(fill=tk.X, padx=4, pady=(4, 1))
        tk.Label(gui_row, text="Font Size:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        tk.Button(gui_row, text="-", font=self.f_tiny, fg=CYAN, bg=PANEL, relief=tk.FLAT,
                 command=lambda: self._adjust_font(-1), cursor="hand2", width=2).pack(side=tk.LEFT, padx=2)
        self._font_size_lbl = tk.Label(gui_row, text="9", font=self.f_tiny, fg=FG, bg=PANEL)
        self._font_size_lbl.pack(side=tk.LEFT)
        tk.Button(gui_row, text="+", font=self.f_tiny, fg=CYAN, bg=PANEL, relief=tk.FLAT,
                 command=lambda: self._adjust_font(1), cursor="hand2", width=2).pack(side=tk.LEFT, padx=2)

        geo_row = tk.Frame(af, bg=PANEL)
        geo_row.pack(fill=tk.X, padx=4, pady=1)
        tk.Label(geo_row, text="Window:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        for label, geo in [("Small", "1100x700"), ("Medium", "1400x900"), ("Large", "1700x1000")]:
            tk.Button(geo_row, text=label, font=self.f_tiny, fg=TEAL, bg=PANEL, relief=tk.FLAT,
                     command=lambda g=geo: self.geometry(g), cursor="hand2").pack(side=tk.LEFT, padx=2)

        # ── PROCESS MONITOR + NETWORK + MEMORY DB ──
        mid_row = tk.Frame(f, bg=BG)
        mid_row.pack(fill=tk.X, padx=4, pady=4)

        # Process Monitor
        proc_panel = self._panel(mid_row, "TOP PROCESSES (CPU/RAM)", RED)
        proc_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        proc_scroll_frame = tk.Frame(proc_panel, bg=INPUT_BG)
        proc_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.sys_proc_text = tk.Text(proc_scroll_frame, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                     font=self.f_tiny, state=tk.DISABLED,
                                     relief=tk.FLAT, bd=0, height=8, width=40)
        proc_xsb = tk.Scrollbar(proc_scroll_frame, orient=tk.HORIZONTAL, command=self.sys_proc_text.xview)
        proc_ysb = tk.Scrollbar(proc_scroll_frame, orient=tk.VERTICAL, command=self.sys_proc_text.yview)
        self.sys_proc_text.configure(xscrollcommand=proc_xsb.set, yscrollcommand=proc_ysb.set)
        self.sys_proc_text.grid(row=0, column=0, sticky="nsew")
        proc_ysb.grid(row=0, column=1, sticky="ns")
        proc_xsb.grid(row=1, column=0, sticky="ew")
        proc_scroll_frame.grid_rowconfigure(0, weight=1)
        proc_scroll_frame.grid_columnconfigure(0, weight=1)
        self.sys_proc_text.tag_configure("high", foreground=RED)
        self.sys_proc_text.tag_configure("med", foreground=AMBER)
        self.sys_proc_text.tag_configure("low", foreground=GREEN)
        self.sys_proc_text.tag_configure("hdr", foreground=BRIGHT)
        proc_btn_row = tk.Frame(proc_panel, bg=PANEL)
        proc_btn_row.pack(fill=tk.X, padx=4, pady=1)
        tk.Button(proc_btn_row, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_processes).pack(side=tk.LEFT, padx=2)
        tk.Label(proc_btn_row, text="PID:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT, padx=(8, 2))
        self.kill_pid_entry = tk.Entry(proc_btn_row, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                       insertbackground=FG, relief=tk.FLAT, bd=2, width=8)
        self.kill_pid_entry.pack(side=tk.LEFT, padx=2)
        tk.Button(proc_btn_row, text="Kill", font=self.f_tiny, fg=AMBER, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._kill_process(False)).pack(side=tk.LEFT, padx=2)
        tk.Button(proc_btn_row, text="Force Kill", font=self.f_tiny, fg=RED, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=lambda: self._kill_process(True)).pack(side=tk.LEFT, padx=2)
        self.kill_status = tk.Label(proc_btn_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.kill_status.pack(side=tk.LEFT, padx=8)

        # Network Info
        net_panel = self._panel(mid_row, "NETWORK & PORTS", TEAL)
        net_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        net_scroll_frame = tk.Frame(net_panel, bg=INPUT_BG)
        net_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.sys_net_text = tk.Text(net_scroll_frame, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                    font=self.f_tiny, state=tk.DISABLED,
                                    relief=tk.FLAT, bd=0, height=8, width=35)
        net_xsb = tk.Scrollbar(net_scroll_frame, orient=tk.HORIZONTAL, command=self.sys_net_text.xview)
        net_ysb = tk.Scrollbar(net_scroll_frame, orient=tk.VERTICAL, command=self.sys_net_text.yview)
        self.sys_net_text.configure(xscrollcommand=net_xsb.set, yscrollcommand=net_ysb.set)
        self.sys_net_text.grid(row=0, column=0, sticky="nsew")
        net_ysb.grid(row=0, column=1, sticky="ns")
        net_xsb.grid(row=1, column=0, sticky="ew")
        net_scroll_frame.grid_rowconfigure(0, weight=1)
        net_scroll_frame.grid_columnconfigure(0, weight=1)
        self.sys_net_text.tag_configure("port", foreground=CYAN)
        self.sys_net_text.tag_configure("ip", foreground=GREEN)
        self.sys_net_text.tag_configure("hdr", foreground=BRIGHT)
        tk.Button(net_panel, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_network).pack(anchor="e", padx=4, pady=1)

        # Memory DB Stats
        mem_panel = self._panel(mid_row, "MEMORY DATABASE", PURPLE)
        mem_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_memdb_labels = {}
        memdb_items = ["Facts", "Observations", "Events", "Decisions", "Sent Emails",
                       "Creative", "DB Size"]
        for item in memdb_items:
            row = tk.Frame(mem_panel, bg=PANEL)
            row.pack(fill=tk.X, padx=4, pady=0)
            tk.Label(row, text=item, font=self.f_tiny, fg=DIM, bg=PANEL, width=12, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_tiny, fg=FG, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.sys_memdb_labels[item] = val

        # Cron job count
        cron_row = tk.Frame(mem_panel, bg=PANEL)
        cron_row.pack(fill=tk.X, padx=4, pady=(4, 0))
        tk.Label(cron_row, text="CRON JOBS", font=self.f_tiny, fg=PURPLE, bg=PANEL, anchor="w").pack(fill=tk.X)
        self.sys_cron_text = tk.Label(mem_panel, text="", font=self.f_tiny, fg=DIM, bg=PANEL,
                                       anchor="w", wraplength=250, justify=tk.LEFT)
        self.sys_cron_text.pack(fill=tk.X, padx=4, pady=2)

        tk.Button(mem_panel, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_memdb).pack(anchor="e", padx=4, pady=1)

        # ── SYSTEM INFO & TOOLS (Advanced Tweaks) ──
        tweaks = self._panel(f, "SYSTEM INFO & TOOLS", PINK)
        tweaks.pack(fill=tk.X, padx=6, pady=4)

        tw_top = tk.Frame(tweaks, bg=PANEL)
        tw_top.pack(fill=tk.X, padx=4, pady=2)

        # Build info (left)
        info_f = tk.Frame(tw_top, bg=PANEL)
        info_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(info_f, text="BUILD INFO", font=self.f_tiny, fg=PINK, bg=PANEL, anchor="w").pack(fill=tk.X)
        self.sys_build_info = {}
        build_items = [
            ("Version", "Command Center v39"),
            ("Git Hash", "..."),
            ("Branch", "master"),
            ("OS", "Ubuntu 24.04 Noble"),
            ("Node", "..."),
            ("Agents", "7 active"),
            ("Cron Jobs", "14"),
            ("MCP Tools", "20"),
        ]
        for key, default in build_items:
            row = tk.Frame(info_f, bg=PANEL)
            row.pack(fill=tk.X, padx=2)
            tk.Label(row, text=f"{key}:", font=self.f_tiny, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            lbl = tk.Label(row, text=default, font=self.f_tiny, fg=FG, bg=PANEL, anchor="w")
            lbl.pack(side=tk.LEFT)
            self.sys_build_info[key] = lbl
        # Populate dynamic build info
        def _load_build_info():
            try:
                h = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, timeout=3, cwd=BASE).stdout.strip()
                self.after(0, lambda: self.sys_build_info["Git Hash"].configure(text=h))
            except: pass
            try:
                nv = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=3).stdout.strip()
                self.after(0, lambda: self.sys_build_info["Node"].configure(text=nv))
            except: pass
        threading.Thread(target=_load_build_info, daemon=True).start()

        # Tools & Actions (right)
        tools_f = tk.Frame(tw_top, bg=PANEL)
        tools_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        tk.Label(tools_f, text="TOOLS & BACKUP", font=self.f_tiny, fg=PINK, bg=PANEL, anchor="w").pack(fill=tk.X)
        self.tw_status = tk.Label(tools_f, text="", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w")
        self.tw_status.pack(fill=tk.X, padx=2, pady=1)

        tool_btns = [
            ("Backup Config", self._backup_config, CYAN),
            ("Export Wake State", lambda: self._export_file(WAKE), TEAL),
            ("Export Memory DB Stats", self._export_memory_stats, PURPLE),
            ("View Crontab", self._view_crontab, AMBER),
            ("Git Status", self._view_git_status, GREEN),
            ("Disk Analysis", self._disk_analysis, RED),
        ]
        for label, cmd, color in tool_btns:
            self._action_btn(tools_f, f"  {label}  ", cmd, color).pack(fill=tk.X, padx=2, pady=1)

        # ── MIDDLE ROW: Log Viewer ──
        log_panel = self._panel(f, "LOG VIEWER", PURPLE)
        log_panel.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        log_head = tk.Frame(log_panel, bg=PANEL)
        log_head.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(log_head, text="Log:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)

        self._log_files = {
            "eos-watchdog": os.path.join("logs", "eos-watchdog.log"),
            "nova": os.path.join("logs", "nova.log"),
            "goose (Atlas)": os.path.join("logs", "goose.log"),
            "watchdog": os.path.join("logs", "watchdog.log"),
            "push-status": os.path.join("logs", "push-live-status.log"),
            "eos-creative": os.path.join("logs", "eos-creative.log"),
            "loop-fitness": os.path.join("logs", "loop-fitness.log"),
            "atlas-runner": os.path.join("logs", "atlas-runner.log"),
            "daily-log": os.path.join("logs", "daily-log.log"),
        }
        self._log_var = tk.StringVar(value="eos-watchdog")
        log_menu = tk.OptionMenu(log_head, self._log_var, *self._log_files.keys())
        log_menu.configure(font=self.f_tiny, fg=CYAN, bg=PANEL, activeforeground=CYAN,
                          activebackground=ACCENT, highlightthickness=0, bd=0)
        log_menu["menu"].configure(font=self.f_tiny, fg=CYAN, bg=PANEL, activeforeground=BRIGHT,
                                   activebackground=ACCENT)
        log_menu.pack(side=tk.LEFT, padx=4)

        tk.Button(log_head, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_log_viewer).pack(side=tk.LEFT, padx=4)

        self.sys_log_text = scrolledtext.ScrolledText(log_panel, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                                       font=self.f_tiny, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=8)
        self.sys_log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # ── SECURITY & SESSION INFO ──
        sec_row = tk.Frame(f, bg=BG)
        sec_row.pack(fill=tk.X, padx=6, pady=4)

        sec_panel = self._panel(sec_row, "SECURITY & SESSIONS", RED)
        sec_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_sec_text = scrolledtext.ScrolledText(sec_panel, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                                       font=self.f_tiny, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=8, width=40)
        self.sys_sec_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.sys_sec_text.tag_configure("ok", foreground=GREEN)
        self.sys_sec_text.tag_configure("warn", foreground=AMBER)
        self.sys_sec_text.tag_configure("bad", foreground=RED)
        self.sys_sec_text.tag_configure("hdr", foreground=BRIGHT)
        self.sys_sec_text.tag_configure("info", foreground=CYAN)
        tk.Button(sec_panel, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_security).pack(anchor="e", padx=4, pady=1)

        # File browser panel
        fb_panel = self._panel(sec_row, "FILE BROWSER", GOLD)
        fb_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        fb_ctrl = tk.Frame(fb_panel, bg=PANEL)
        fb_ctrl.pack(fill=tk.X, padx=4, pady=2)
        self.fb_path_entry = tk.Entry(fb_ctrl, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                       insertbackground=FG, relief=tk.FLAT, bd=2)
        self.fb_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.fb_path_entry.insert(0, BASE)
        self.fb_path_entry.bind("<Return>", lambda e: self._fb_browse())
        self._action_btn(fb_ctrl, "Browse", self._fb_browse, GOLD).pack(side=tk.LEFT, padx=2)
        self._action_btn(fb_ctrl, "Up", self._fb_up, DIM).pack(side=tk.LEFT, padx=2)
        self._action_btn(fb_ctrl, "Import File", self._fb_import, TEAL).pack(side=tk.LEFT, padx=2)

        self.fb_list = tk.Listbox(fb_panel, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                   selectbackground=ACTIVE_BG, selectforeground=GOLD,
                                   relief=tk.FLAT, bd=0, activestyle="none", height=7)
        self.fb_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.fb_list.bind("<Double-1>", self._fb_dblclick)
        self.fb_entries = []
        self.fb_status = tk.Label(fb_panel, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self.fb_status.pack(fill=tk.X, padx=4, pady=1)

        # ── BOTTOM: Wake State + AWAKENING Progress ──
        wf = self._panel(f, "WAKE STATE & AWAKENING PROGRESS", CYAN)
        wf.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # AWAKENING progress bar row
        prog_row = tk.Frame(wf, bg=PANEL)
        prog_row.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.sys_awaken_lbl = tk.Label(prog_row, text="AWAKENING: --/--", font=self.f_small,
                                        fg=GREEN, bg=PANEL, anchor="w")
        self.sys_awaken_lbl.pack(side=tk.LEFT)
        # Progress bar (canvas)
        self.sys_awaken_bar = tk.Canvas(prog_row, height=12, bg=INPUT_BG, highlightthickness=0)
        self.sys_awaken_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4))
        self.sys_awaken_pct = tk.Label(prog_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.sys_awaken_pct.pack(side=tk.RIGHT)

        tk.Button(wf, text="Refresh", font=self.f_tiny, fg=GREEN, bg=PANEL, relief=tk.FLAT,
                 cursor="hand2", command=self._refresh_wake_viewer).pack(anchor="ne", padx=4)

        self.sys_wake_text = scrolledtext.ScrolledText(wf, wrap=tk.WORD, bg=INPUT_BG, fg=FG,
                                                        font=self.f_tiny, state=tk.DISABLED,
                                                        relief=tk.FLAT, bd=0, height=12)
        self.sys_wake_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        # Color tags for structured display
        self.sys_wake_text.tag_configure("header", foreground=BRIGHT, font=self.f_small)
        self.sys_wake_text.tag_configure("ok", foreground=GREEN)
        self.sys_wake_text.tag_configure("warn", foreground=AMBER)
        self.sys_wake_text.tag_configure("dim", foreground=DIM)
        self.sys_wake_text.tag_configure("info", foreground=CYAN)

        return f

    def _refresh_wake_viewer(self):
        """Parse wake-state.md and display with color-coded sections + AWAKENING progress."""
        wake = _read(WAKE)
        # Parse AWAKENING progress from awakening-plan.md
        awaken = _read(os.path.join(BASE, "docs", "awakening-plan.md"))
        done, total = 0, 0
        for line in awaken.split('\n'):
            if line.startswith('| **TOTAL**'):
                parts = [p.strip().strip('*') for p in line.split('|')]
                try:
                    total = int(parts[2])
                    done = int(parts[3])
                except Exception:
                    pass
        # Update progress bar
        pct = (done / total * 100) if total else 0
        self.sys_awaken_lbl.configure(text=f"AWAKENING: {done}/{total}")
        self.sys_awaken_pct.configure(text=f"{pct:.0f}%")
        self.sys_awaken_bar.delete("all")
        w = self.sys_awaken_bar.winfo_width() or 200
        bar_w = int(w * pct / 100)
        self.sys_awaken_bar.create_rectangle(0, 0, bar_w, 12, fill=GREEN, outline="")
        self.sys_awaken_bar.create_rectangle(bar_w, 0, w, 12, fill="#1a1a2e", outline="")

        # Insert wake state with color tags
        self.sys_wake_text.configure(state=tk.NORMAL)
        self.sys_wake_text.delete("1.0", tk.END)
        for line in wake.split('\n'):
            stripped = line.strip()
            if stripped.startswith('# ') or stripped.startswith('## ') or stripped.startswith('### '):
                self.sys_wake_text.insert(tk.END, line + '\n', "header")
            elif 'COMPLETE' in stripped or 'active' in stripped.lower() or 'working' in stripped.lower():
                self.sys_wake_text.insert(tk.END, line + '\n', "ok")
            elif 'WARNING' in stripped or 'BLOCKED' in stripped or 'needed' in stripped.lower():
                self.sys_wake_text.insert(tk.END, line + '\n', "warn")
            elif stripped.startswith('- **') or stripped.startswith('| '):
                self.sys_wake_text.insert(tk.END, line + '\n', "info")
            elif stripped.startswith('-'):
                self.sys_wake_text.insert(tk.END, line + '\n', "dim")
            else:
                self.sys_wake_text.insert(tk.END, line + '\n')
        self.sys_wake_text.configure(state=tk.DISABLED)

    def _sys_action(self, func):
        def run():
            result = func()
            self.after(0, lambda: self.sys_action_result.configure(text=str(result), fg=GREEN))
        threading.Thread(target=run, daemon=True).start()

    def _restart_all_crons(self):
        cron_agents = ["nova", "eos", "atlas", "tempo", "sentinel", "coordinator", "predictive", "selfimprove"]
        results = []
        for agent in cron_agents:
            r = action_restart_service(agent)
            results.append(f"{agent}: {r}")
        return " | ".join(results[:4]) + f" + {len(results)-4} more"

    def _kill_process(self, force=False):
        """Kill a process by PID."""
        pid_str = self.kill_pid_entry.get().strip()
        if not pid_str or not pid_str.isdigit():
            self.kill_status.configure(text="Enter a valid PID", fg=RED)
            return
        pid = int(pid_str)
        if pid <= 1:
            self.kill_status.configure(text="Cannot kill PID 0 or 1", fg=RED)
            return
        sig = "-9" if force else "-15"
        sig_name = "SIGKILL" if force else "SIGTERM"
        def do():
            try:
                result = subprocess.run(['kill', sig, str(pid)],
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    msg = f"Sent {sig_name} to PID {pid}"
                    color = GREEN
                else:
                    msg = f"Failed: {result.stderr.strip()[:40]}"
                    color = RED
            except Exception as e:
                msg = f"Error: {str(e)[:40]}"
                color = RED
            self.after(0, lambda: self.kill_status.configure(text=msg, fg=color))
            self.after(2000, lambda: self._refresh_processes())
        threading.Thread(target=do, daemon=True).start()

    def _refresh_processes(self):
        """Show top processes by CPU and RAM usage."""
        def run():
            try:
                out = subprocess.run(
                    ['ps', 'aux', '--sort=-pcpu'],
                    capture_output=True, text=True, timeout=5
                ).stdout.strip().split('\n')
                lines = []
                lines.append(f"{'PID':>6}  {'%CPU':>5}  {'%MEM':>5}  COMMAND")
                for line in out[1:13]:  # top 12
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        pid, cpu, mem, cmd = parts[1], parts[2], parts[3], parts[10][:40]
                        lines.append(f"{pid:>6}  {cpu:>5}  {mem:>5}  {cmd}")
            except Exception as e:
                lines = [f"Error: {e}"]
            def update():
                self.sys_proc_text.configure(state=tk.NORMAL)
                self.sys_proc_text.delete("1.0", tk.END)
                for i, line in enumerate(lines):
                    if i == 0:
                        self.sys_proc_text.insert(tk.END, line + "\n", "hdr")
                    else:
                        parts = line.split()
                        try:
                            cpu_val = float(parts[1]) if len(parts) > 1 else 0
                        except (ValueError, IndexError):
                            cpu_val = 0
                        tag = "high" if cpu_val > 20 else "med" if cpu_val > 5 else "low"
                        self.sys_proc_text.insert(tk.END, line + "\n", tag)
                self.sys_proc_text.configure(state=tk.DISABLED)
            self.after(0, update)
        threading.Thread(target=run, daemon=True).start()

    def _refresh_network(self):
        """Show network interfaces, IPs, and listening ports."""
        def run():
            lines = []
            # IPs
            try:
                out = subprocess.run(
                    ['ip', '-4', '-o', 'addr', 'show'],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip()
                lines.append("INTERFACES:")
                for line in out.split('\n'):
                    parts = line.split()
                    if len(parts) >= 4:
                        iface = parts[1]
                        addr = parts[3].split('/')[0]
                        lines.append(f"  {iface:16s} {addr}")
            except Exception:
                lines.append("IPs: error")
            # Tailscale
            try:
                out = subprocess.run(
                    ['tailscale', 'ip', '-4'],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip()
                if out:
                    lines.append(f"  {'tailscale0':16s} {out}")
            except Exception:
                pass
            # Listening ports
            lines.append("\nLISTENING PORTS:")
            try:
                out = subprocess.run(
                    ['ss', '-tlnp'],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip().split('\n')
                for line in out[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        addr_port = parts[3]
                        proc = parts[-1] if 'users:' in parts[-1] else ""
                        # Extract process name from users:(("name",pid=...))
                        pname = ""
                        if 'users:' in proc:
                            try:
                                pname = proc.split('"')[1]
                            except (IndexError, ValueError):
                                pname = ""
                        lines.append(f"  {addr_port:24s} {pname}")
            except Exception:
                lines.append("  error reading ports")
            def update():
                self.sys_net_text.configure(state=tk.NORMAL)
                self.sys_net_text.delete("1.0", tk.END)
                for line in lines:
                    if line.startswith("INTER") or line.startswith("\nLIST"):
                        self.sys_net_text.insert(tk.END, line.strip() + "\n", "hdr")
                    elif ":" in line and not line.startswith("  "):
                        self.sys_net_text.insert(tk.END, line + "\n", "ip")
                    else:
                        self.sys_net_text.insert(tk.END, line + "\n", "port")
                self.sys_net_text.configure(state=tk.DISABLED)
            self.after(0, update)
        threading.Thread(target=run, daemon=True).start()

    def _refresh_memdb(self):
        """Show memory.db table counts and cron job summary."""
        def run():
            counts = {}
            db_size = "?"
            try:
                import sqlite3
                db_path = MEMORY_DB
                db_size = f"{os.path.getsize(db_path) / 1024:.0f} KB" if os.path.exists(db_path) else "N/A"
                conn = sqlite3.connect(db_path, timeout=2)
                for table in ["facts", "observations", "events", "decisions", "sent_emails", "creative"]:
                    try:
                        c = conn.execute(f"SELECT COUNT(*) FROM {table}")
                        counts[table] = c.fetchone()[0]
                    except Exception:
                        counts[table] = 0
                conn.close()
            except Exception:
                pass
            # Cron jobs
            cron_lines = ""
            try:
                out = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=3).stdout
                jobs = [l.strip() for l in out.split('\n') if l.strip() and not l.strip().startswith('#')]
                cron_lines = f"{len(jobs)} jobs active"
            except Exception:
                cron_lines = "error reading crontab"
            def update():
                mapping = {
                    "Facts": counts.get("facts", 0),
                    "Observations": counts.get("observations", 0),
                    "Events": counts.get("events", 0),
                    "Decisions": counts.get("decisions", 0),
                    "Sent Emails": counts.get("sent_emails", 0),
                    "Creative": counts.get("creative", 0),
                    "DB Size": db_size,
                }
                for key, val in mapping.items():
                    if key in self.sys_memdb_labels:
                        self.sys_memdb_labels[key].configure(text=str(val))
                self.sys_cron_text.configure(text=cron_lines)
            self.after(0, update)
        threading.Thread(target=run, daemon=True).start()

    def _adjust_font(self, delta):
        """Adjust body/small/tiny font sizes."""
        new_body = max(7, min(14, self.f_body.cget("size") + delta))
        self.f_body.configure(size=new_body)
        self.f_small.configure(size=max(6, new_body - 1))
        self.f_tiny.configure(size=max(5, new_body - 2))
        self._font_size_lbl.configure(text=str(new_body))

    # ── SYSTEM TOOLS ──────────────────────────────────────────────
    def _backup_config(self):
        """Backup key config files to a tarball."""
        def run():
            ts = time.strftime("%Y%m%d-%H%M")
            outpath = os.path.join(BASE, f"backup-{ts}.tar.gz")
            files = ["wake-state.md", ".loop-count", "personality.md", "loop-instructions.md",
                     "awakening-plan.md", ".dashboard-messages.json", "eos-memory.json"]
            existing = [f for f in files if os.path.exists(os.path.join(BASE, f))]
            try:
                subprocess.run(['tar', 'czf', outpath] + existing, cwd=BASE, timeout=10)
                self.after(0, lambda: self.tw_status.configure(text=f"Backed up {len(existing)} files → {os.path.basename(outpath)}", fg=GREEN))
            except Exception as e:
                self.after(0, lambda: self.tw_status.configure(text=f"Backup failed: {e}", fg=RED))
        threading.Thread(target=run, daemon=True).start()

    def _export_file(self, path):
        """Show file content in log viewer."""
        try:
            content = open(path, 'r').read()
            self.sys_log_text.configure(state=tk.NORMAL)
            self.sys_log_text.delete("1.0", tk.END)
            self.sys_log_text.insert(tk.END, content)
            self.sys_log_text.see("1.0")
            self.sys_log_text.configure(state=tk.DISABLED)
            self.tw_status.configure(text=f"Showing: {os.path.basename(path)}", fg=GREEN)
        except Exception as e:
            self.tw_status.configure(text=f"Error: {e}", fg=RED)

    def _export_memory_stats(self):
        """Show memory.db stats in log viewer."""
        def run():
            try:
                import sqlite3 as sq
                conn = sq.connect(MEMORY_DB)
                c = conn.cursor()
                stats = []
                for table in ["facts", "observations", "events", "decisions", "creative"]:
                    try:
                        c.execute(f"SELECT COUNT(*) FROM {table}")
                        count = c.fetchone()[0]
                        stats.append(f"{table}: {count} rows")
                    except: stats.append(f"{table}: error")
                conn.close()
                text = "MEMORY DATABASE STATS\n" + "=" * 30 + "\n" + "\n".join(stats)
            except Exception as e:
                text = f"Error: {e}"
            def apply():
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, text)
                self.sys_log_text.configure(state=tk.DISABLED)
                self.tw_status.configure(text="Memory stats loaded", fg=GREEN)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _view_crontab(self):
        """Show crontab in log viewer."""
        def run():
            try:
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
                text = result.stdout or "No crontab"
            except Exception as e:
                text = f"Error: {e}"
            def apply():
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, text)
                self.sys_log_text.see("1.0")
                self.sys_log_text.configure(state=tk.DISABLED)
                self.tw_status.configure(text=f"Crontab loaded ({text.count(chr(10))} lines)", fg=GREEN)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _view_git_status(self):
        """Show git status in log viewer."""
        def run():
            try:
                result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=5, cwd=BASE)
                log = subprocess.run(['git', 'log', '--oneline', '-10'], capture_output=True, text=True, timeout=5, cwd=BASE)
                text = "GIT STATUS\n" + "=" * 30 + "\n" + (result.stdout or "Clean") + "\nRECENT COMMITS\n" + "=" * 30 + "\n" + log.stdout
            except Exception as e:
                text = f"Error: {e}"
            def apply():
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, text)
                self.sys_log_text.see("1.0")
                self.sys_log_text.configure(state=tk.DISABLED)
                self.tw_status.configure(text="Git status loaded", fg=GREEN)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _disk_analysis(self):
        """Show disk usage breakdown."""
        def run():
            try:
                result = subprocess.run(['du', '-sh', '--max-depth=1', BASE], capture_output=True, text=True, timeout=10)
                df = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
                text = "DISK USAGE\n" + "=" * 30 + "\n" + df.stdout + "\nPROJECT DIR BREAKDOWN\n" + "=" * 30 + "\n" + result.stdout
            except Exception as e:
                text = f"Error: {e}"
            def apply():
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, text)
                self.sys_log_text.see("1.0")
                self.sys_log_text.configure(state=tk.DISABLED)
                self.tw_status.configure(text="Disk analysis loaded", fg=GREEN)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _refresh_security(self):
        """Show security info: firewall, active sessions, failed logins, open ports."""
        def run():
            lines = []
            # UFW firewall status
            try:
                ufw = subprocess.run(['sudo', '-n', 'ufw', 'status'], capture_output=True, text=True, timeout=5)
                fw_status = ufw.stdout.strip() if ufw.returncode == 0 else "UFW: unable to check (need sudo)"
            except Exception:
                fw_status = "UFW: not available"
            lines.append(("FIREWALL\n", "hdr"))
            if "inactive" in fw_status.lower():
                lines.append((fw_status + "\n", "warn"))
            elif "active" in fw_status.lower():
                lines.append((fw_status + "\n", "ok"))
            else:
                lines.append((fw_status + "\n", "info"))

            # Active sessions (who)
            lines.append(("\nACTIVE SESSIONS\n", "hdr"))
            try:
                who = subprocess.run(['who'], capture_output=True, text=True, timeout=3)
                sessions = who.stdout.strip()
                if sessions:
                    lines.append((sessions + "\n", "info"))
                else:
                    lines.append(("No active sessions\n", "ok"))
            except Exception:
                lines.append(("Unable to check\n", "warn"))

            # Tailscale status
            lines.append(("\nTAILSCALE\n", "hdr"))
            try:
                ts = subprocess.run(['tailscale', 'status', '--peers=false'], capture_output=True, text=True, timeout=5)
                lines.append((ts.stdout.strip()[:200] + "\n", "info"))
            except Exception:
                lines.append(("Tailscale not available\n", "warn"))

            # Failed SSH attempts (last 10)
            lines.append(("\nRECENT FAILED LOGINS\n", "hdr"))
            try:
                auth = subprocess.run(['sudo', '-n', 'journalctl', '-u', 'ssh', '--no-pager', '-n', '20', '--grep=Failed'],
                                     capture_output=True, text=True, timeout=5)
                if auth.stdout.strip():
                    for line in auth.stdout.strip().split('\n')[-5:]:
                        lines.append((line + "\n", "bad"))
                else:
                    lines.append(("No recent failed logins\n", "ok"))
            except Exception:
                lines.append(("Unable to check auth logs\n", "warn"))

            # Listening ports
            lines.append(("\nLISTENING PORTS\n", "hdr"))
            try:
                ss = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True, timeout=5)
                for line in ss.stdout.strip().split('\n')[:12]:
                    lines.append((line + "\n", "info"))
            except Exception:
                lines.append(("Unable to check ports\n", "warn"))

            def apply():
                self.sys_sec_text.configure(state=tk.NORMAL)
                self.sys_sec_text.delete("1.0", tk.END)
                for text, tag in lines:
                    self.sys_sec_text.insert(tk.END, text, tag)
                self.sys_sec_text.configure(state=tk.DISABLED)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _fb_browse(self):
        """Browse directory contents."""
        path = self.fb_path_entry.get().strip()
        if not path or not os.path.isdir(path):
            self.fb_status.configure(text="Invalid directory", fg=RED)
            return
        try:
            entries = []
            for name in sorted(os.listdir(path)):
                fp = os.path.join(path, name)
                if name.startswith('.') and name not in ['.env', '.loop-count', '.heartbeat']:
                    continue
                if os.path.isdir(fp):
                    entries.append(("dir", name, fp))
                else:
                    size = os.path.getsize(fp)
                    if size < 1024:
                        sz = f"{size}B"
                    elif size < 1048576:
                        sz = f"{size//1024}K"
                    else:
                        sz = f"{size//1048576}M"
                    entries.append(("file", name, fp, sz))
            self.fb_entries = entries
            self.fb_list.delete(0, tk.END)
            for entry in entries:
                if entry[0] == "dir":
                    self.fb_list.insert(tk.END, f"\U0001f4c1 {entry[1]}/")
                else:
                    self.fb_list.insert(tk.END, f"   {entry[1]}  ({entry[3]})")
            self.fb_status.configure(text=f"{len(entries)} items in {os.path.basename(path) or path}", fg=GREEN)
        except Exception as e:
            self.fb_status.configure(text=f"Error: {str(e)[:50]}", fg=RED)

    def _fb_up(self):
        """Navigate to parent directory."""
        path = self.fb_path_entry.get().strip()
        parent = os.path.dirname(path)
        if parent and parent != path:
            self.fb_path_entry.delete(0, tk.END)
            self.fb_path_entry.insert(0, parent)
            self._fb_browse()

    def _fb_dblclick(self, event=None):
        """Handle double-click: open dir or show file in log viewer."""
        sel = self.fb_list.curselection()
        if not sel or sel[0] >= len(self.fb_entries):
            return
        entry = self.fb_entries[sel[0]]
        if entry[0] == "dir":
            self.fb_path_entry.delete(0, tk.END)
            self.fb_path_entry.insert(0, entry[2])
            self._fb_browse()
        else:
            # Show file content in log viewer
            try:
                with open(entry[2], 'r', errors='replace') as fh:
                    content = fh.read(50000)
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, content)
                self.sys_log_text.see("1.0")
                self.sys_log_text.configure(state=tk.DISABLED)
                self.fb_status.configure(text=f"Viewing: {entry[1]}", fg=GOLD)
            except Exception as e:
                self.fb_status.configure(text=f"Can't read: {str(e)[:40]}", fg=RED)

    def _fb_import(self):
        """Import a file from elsewhere into the project directory."""
        src = filedialog.askopenfilename(title="Import file to project")
        if not src:
            return
        dest = os.path.join(BASE, os.path.basename(src))
        try:
            import shutil
            if os.path.exists(dest):
                self.fb_status.configure(text=f"File already exists: {os.path.basename(dest)}", fg=AMBER)
                return
            shutil.copy2(src, dest)
            self.fb_status.configure(text=f"Imported: {os.path.basename(dest)}", fg=GREEN)
            self._fb_browse()
        except Exception as e:
            self.fb_status.configure(text=f"Import failed: {str(e)[:40]}", fg=RED)

    def _refresh_log_viewer(self):
        """Load last 50 lines of selected log file."""
        def run():
            name = self._log_var.get()
            logfile = self._log_files.get(name, "")
            path = os.path.join(BASE, logfile)
            try:
                with open(path, 'r', errors='replace') as fh:
                    lines = fh.readlines()
                tail = lines[-50:]
                content = ''.join(tail)
            except Exception as e:
                content = f"Error reading {path}: {e}"
            def apply():
                self.sys_log_text.configure(state=tk.NORMAL)
                self.sys_log_text.delete("1.0", tk.END)
                self.sys_log_text.insert(tk.END, content)
                self.sys_log_text.see(tk.END)
                self.sys_log_text.configure(state=tk.DISABLED)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    # ── STATUS BAR ────────────────────────────────────────────────
    # ── NEW TABS (v27) ──────────────────────────────────────────────

    def _build_messages(self):
        f = tk.Frame(self, bg=BG)

        # Header
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=2, pady=2)
        tk.Label(hdr, text="MESSAGES", font=self.f_sect, fg=GOLD, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        self._action_btn(hdr, " Clear All ", self._msg_tab_clear, RED).pack(side=tk.RIGHT, padx=4)
        self._action_btn(hdr, " Refresh ", self._msg_tab_refresh, GOLD).pack(side=tk.RIGHT, padx=4)
        self._msg_count_lbl = tk.Label(hdr, text="", font=self.f_tiny, fg=DIM, bg=PANEL2)
        self._msg_count_lbl.pack(side=tk.RIGHT, padx=8)

        # Two-panel split: Joel's Commands (left) + Agent Feed (right)
        split = tk.PanedWindow(f, orient=tk.HORIZONTAL, bg=BG, sashwidth=4,
                               sashrelief=tk.FLAT, bd=0)
        split.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # LEFT: Joel's commands/directives
        joel_frame = tk.Frame(split, bg=BG)
        joel_hdr = tk.Frame(joel_frame, bg=ACCENT)
        joel_hdr.pack(fill=tk.X)
        tk.Label(joel_hdr, text=" JOEL'S DIRECTIVES", font=self.f_sect, fg=CYAN, bg=ACCENT).pack(side=tk.LEFT, padx=4, pady=4)
        self._msg_joel_count = tk.Label(joel_hdr, text="", font=self.f_tiny, fg=DIM, bg=ACCENT)
        self._msg_joel_count.pack(side=tk.RIGHT, padx=8)
        self.msg_joel_display = scrolledtext.ScrolledText(joel_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                           font=self.f_body, state=tk.DISABLED,
                                                           relief=tk.FLAT, bd=0)
        self.msg_joel_display.pack(fill=tk.BOTH, expand=True)
        self.msg_joel_display.tag_configure("time", foreground=DIM)
        self.msg_joel_display.tag_configure("msg", foreground=BRIGHT, font=self.f_body)
        self.msg_joel_display.tag_configure("separator", foreground=BORDER)
        # Topic badge tags
        _topic_badge_colors = {"command-center": GREEN, "creative": GOLD, "email": AMBER,
                               "system": RED, "agents": PURPLE, "website": TEAL, "grants": CYAN,
                               "games": PINK, "general": FG, "bug": RED, "feature": BLUE}
        for tname, tcolor in _topic_badge_colors.items():
            self.msg_joel_display.tag_configure(f"topic_{tname}", foreground=BG, background=tcolor,
                                                font=self.f_tiny)

        # RIGHT: Agent feed
        agent_frame = tk.Frame(split, bg=BG)
        agent_hdr = tk.Frame(agent_frame, bg=ACCENT)
        agent_hdr.pack(fill=tk.X)
        tk.Label(agent_hdr, text=" AGENT FEED", font=self.f_sect, fg=AMBER, bg=ACCENT).pack(side=tk.LEFT, padx=4, pady=4)
        # Agent filter buttons
        self._msg_agent_filter = "all"
        self._msg_agent_btns = {}
        agent_names = [("all", "All", FG), ("atlas", "Atlas", TEAL), ("nova", "Nova", PURPLE),
                       ("soma", "Soma", AMBER), ("tempo", "Tempo", BLUE), ("hermes", "Hermes", PINK),
                       ("meridian", "Meridian", GREEN)]
        for aid, alabel, acol in agent_names:
            abtn = tk.Button(agent_hdr, text=f" {alabel} ", font=self.f_tiny, fg=DIM, bg=ACCENT,
                            activeforeground=acol, activebackground=ACTIVE_BG, relief=tk.FLAT,
                            bd=0, cursor="hand2", command=lambda ai=aid: self._msg_set_agent_filter(ai))
            abtn.pack(side=tk.LEFT, padx=1)
            self._msg_agent_btns[aid] = (abtn, acol)
        self._msg_agent_btns["all"][0].configure(fg=FG)
        self._msg_agent_count = tk.Label(agent_hdr, text="", font=self.f_tiny, fg=DIM, bg=ACCENT)
        self._msg_agent_count.pack(side=tk.RIGHT, padx=8)

        self.msg_agent_display = scrolledtext.ScrolledText(agent_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                            font=self.f_body, state=tk.DISABLED,
                                                            relief=tk.FLAT, bd=0)
        self.msg_agent_display.pack(fill=tk.BOTH, expand=True)
        self.msg_agent_display.tag_configure("agent", foreground=AMBER, font=self.f_sect)
        self.msg_agent_display.tag_configure("time", foreground=DIM)
        self.msg_agent_display.tag_configure("msg", foreground=FG)

        split.add(joel_frame, width=500)
        split.add(agent_frame, width=700)

        # Send bar — messages go to dashboard + agent relay
        send_frame = tk.Frame(f, bg=PANEL2)
        send_frame.pack(fill=tk.X, padx=2, pady=2)
        tk.Label(send_frame, text="Joel:", font=self.f_sect, fg=CYAN, bg=PANEL2).pack(side=tk.LEFT, padx=(8, 4))

        # Topic badge selector
        tk.Label(send_frame, text="Topic:", font=self.f_tiny, fg=DIM, bg=PANEL2).pack(side=tk.LEFT, padx=(4, 2))
        self._msg_topic_var = tk.StringVar(value="")
        topic_options = ["", "command-center", "creative", "email", "system", "agents",
                         "website", "grants", "games", "general", "bug", "feature"]
        topic_colors = {"command-center": GREEN, "creative": GOLD, "email": AMBER,
                        "system": RED, "agents": PURPLE, "website": TEAL, "grants": CYAN,
                        "games": PINK, "general": FG, "bug": RED, "feature": BLUE}
        self._topic_colors = topic_colors
        topic_menu = tk.OptionMenu(send_frame, self._msg_topic_var, *topic_options)
        topic_menu.configure(font=self.f_tiny, bg=ACCENT, fg=GOLD, bd=0,
                            highlightthickness=0, activebackground=BORDER, width=14)
        topic_menu["menu"].configure(font=self.f_tiny, bg=PANEL2, fg=FG)
        topic_menu.pack(side=tk.LEFT, padx=(0, 6))

        self.msg_tab_entry = tk.Entry(send_frame, font=self.f_body, bg=INPUT_BG, fg=FG,
                                       insertbackground=FG, relief=tk.FLAT, bd=4)
        self.msg_tab_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.msg_tab_entry.bind("<Return>", self._msg_tab_send)
        self._action_btn(send_frame, " Send ", self._msg_tab_send, GOLD).pack(side=tk.RIGHT, padx=4)
        self._msg_send_status = tk.Label(send_frame, text="", font=self.f_tiny, fg=GREEN, bg=PANEL2)
        self._msg_send_status.pack(side=tk.RIGHT, padx=4)

        self._msg_tab_refresh()
        return f

    def _msg_set_agent_filter(self, aid):
        self._msg_agent_filter = aid
        for k, (btn, col) in self._msg_agent_btns.items():
            btn.configure(fg=col if k == aid else DIM)
        self._msg_tab_refresh()

    def _msg_tab_refresh(self, event=None):
        msgs = dashboard_messages(200)
        agent_names_set = {"eos", "atlas", "nova", "soma", "tempo", "meridian", "hermes",
                           "sentinel", "coordinator", "predictive", "selfimprove"}

        # Separate Joel messages from agent messages
        joel_msgs = []
        agent_msgs = []
        for m in msgs:
            sender = m.get("from", m.get("sender", "System"))
            text = m.get("text", m.get("message", ""))
            ts = m.get("time", m.get("timestamp", ""))
            topic = m.get("topic", "")
            if sender.lower() == "joel":
                joel_msgs.append((text, ts, topic))
            elif sender.lower() in agent_names_set:
                agent_msgs.append((sender, text, ts))

        # Populate Joel panel
        self.msg_joel_display.configure(state=tk.NORMAL)
        self.msg_joel_display.delete("1.0", tk.END)
        for text, ts, topic in joel_msgs:
            self.msg_joel_display.insert(tk.END, f"{ts}  ", "time")
            if topic:
                tag_name = f"topic_{topic}"
                self.msg_joel_display.insert(tk.END, f" {topic.upper()} ", tag_name)
                self.msg_joel_display.insert(tk.END, " ", "time")
            self.msg_joel_display.insert(tk.END, f"\n{text}\n\n", "msg")
        if not joel_msgs:
            self.msg_joel_display.insert(tk.END, "No directives from Joel.", "time")
        self.msg_joel_display.configure(state=tk.DISABLED)
        self.msg_joel_display.see(tk.END)
        self._msg_joel_count.configure(text=f"{len(joel_msgs)} directives")

        # Populate Agent panel (with filter)
        afilt = self._msg_agent_filter
        filtered_agents = []
        for sender, text, ts in agent_msgs:
            if afilt != "all" and sender.lower() != afilt:
                continue
            filtered_agents.append((sender, text, ts))

        self.msg_agent_display.configure(state=tk.NORMAL)
        self.msg_agent_display.delete("1.0", tk.END)
        for sender, text, ts in filtered_agents:
            greek = GREEK_NAMES.get(sender, sender)
            self.msg_agent_display.insert(tk.END, f"{greek}", "agent")
            self.msg_agent_display.insert(tk.END, f"  {ts}\n", "time")
            self.msg_agent_display.insert(tk.END, f"  {text}\n\n", "msg")
        if not filtered_agents:
            self.msg_agent_display.insert(tk.END, "No agent messages.", "time")
        self.msg_agent_display.configure(state=tk.DISABLED)
        self.msg_agent_display.see(tk.END)
        self._msg_agent_count.configure(text=f"{len(filtered_agents)}/{len(agent_msgs)} messages")
        self._msg_count_lbl.configure(text=f"{len(joel_msgs)} directives | {len(agent_msgs)} agent msgs")

    def _msg_tab_clear(self):
        try:
            with open(DASH_MSG, 'w') as fh:
                json.dump({"messages": []}, fh)
            self._msg_tab_refresh()
        except Exception:
            pass

    def _msg_tab_send(self, event=None):
        text = self.msg_tab_entry.get().strip()
        if text:
            topic = self._msg_topic_var.get()
            post_dashboard_msg(text, "Joel", topic=topic)
            db_topic = f"directive:{topic}" if topic else "directive"
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                conn.execute(
                    "INSERT INTO agent_messages (agent, topic, message, timestamp) VALUES (?, ?, ?, ?)",
                    ("Joel", db_topic, text, datetime.now(tz=__import__('datetime').timezone.utc).isoformat()))
                conn.commit()
                conn.close()
            except Exception:
                pass
            self.msg_tab_entry.delete(0, tk.END)
            topic_str = f" [{topic}]" if topic else ""
            self._msg_send_status.configure(text=f"Sent{topic_str} to dashboard + relay", fg=GREEN)
            self.after(2000, lambda: self._msg_send_status.configure(text=""))
            self.after(500, self._msg_tab_refresh)

    def _build_terminal(self):
        f = tk.Frame(self, bg=BG)
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(hdr, text="TERMINAL", font=self.f_sect, fg=TEAL, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        cmds_frame = tk.Frame(f, bg=ACCENT)
        cmds_frame.pack(fill=tk.X, padx=4, pady=2)
        quick_cmds_rows = [
            [
                ("System Info", "uname -a && uptime"),
                ("Disk Usage", "df -h /"),
                ("Top Processes", "ps aux --sort=-%cpu | head -15"),
                ("Network Ports", "ss -tlnp 2>/dev/null | head -20"),
                ("Git Status", f"cd {BASE} && git status"),
                ("Git Log", f"cd {BASE} && git log --oneline -10"),
                ("Services", "systemctl list-units --type=service --state=active 2>/dev/null | head -20"),
                ("Crontab", "crontab -l 2>/dev/null | head -30"),
            ],
            [
                ("RAM Detail", "free -h"),
                ("GPU Status", "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || echo 'No GPU'"),
                ("Heartbeat Age", f"python3 -c \"import os,time; age=time.time()-os.path.getmtime('{BASE}/.heartbeat'); print(f'Heartbeat: {{age:.0f}}s ago')\""),
                ("Loop Count", f"cat {BASE}/.loop-count"),
                ("Relay (last 5)", f"sqlite3 {BASE}/agent-relay.db \"SELECT agent, topic, substr(message,1,60), datetime(timestamp) FROM agent_messages ORDER BY timestamp DESC LIMIT 5\""),
                ("Soma Mood", f"python3 -c \"import json; d=json.load(open('{BASE}/.symbiosense-state.json')); bm=d.get('body_map',{{}}); print(f'Mood: {{bm.get(\\\"mood\\\",\\\"?\\\")}} ({{bm.get(\\\"mood_score\\\",\\\"?\\\")}})')\""),
                ("Tail Errors", f"tail -5 {BASE}/logs/*.log 2>/dev/null | grep -i 'error\\|fail\\|warn' | tail -10"),
                ("Email Count", f"python3 -c \"import imaplib,os,sys; sys.path.insert(0,'{BASE}/scripts'); from load_env import *; m=imaplib.IMAP4('127.0.0.1',1144); m.login(os.environ['CRED_USER'],os.environ['CRED_PASS']); m.select('INBOX'); _,d=m.search(None,'UNSEEN'); print(f'Unseen: {{len(d[0].split()) if d[0] else 0}}'); m.logout()\""),
            ],
        ]
        for row_cmds in quick_cmds_rows:
            row_frame = tk.Frame(cmds_frame, bg=ACCENT)
            row_frame.pack(fill=tk.X, pady=1)
            for label, cmd in row_cmds:
                self._action_btn(row_frame, f" {label} ",
                                 lambda c=cmd: self._term_run(c), TEAL).pack(side=tk.LEFT, padx=2, pady=2)
        input_frame = tk.Frame(f, bg=BG)
        input_frame.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(input_frame, text="$", font=self.f_body, fg=GREEN, bg=BG).pack(side=tk.LEFT, padx=4)
        self.term_input = tk.Entry(input_frame, font=("Monospace", 10), bg=INPUT_BG, fg=FG,
                                    insertbackground=FG, relief=tk.FLAT, bd=4)
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.term_input.bind("<Return>", lambda e: self._term_run(self.term_input.get()))
        self._action_btn(input_frame, " Run ",
                         lambda: self._term_run(self.term_input.get()), GREEN).pack(side=tk.RIGHT, padx=4)
        self.term_output = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg="#0d0d0d", fg=GREEN,
                                                       font=("Monospace", 9), state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0)
        self.term_output.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.term_output.tag_configure("cmd", foreground=CYAN, font=("Monospace", 9, "bold"))
        self.term_output.tag_configure("err", foreground=RED)
        self.term_output.tag_configure("out", foreground=GREEN)
        return f

    def _term_run(self, cmd):
        if not cmd or not cmd.strip():
            return
        def do():
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, cwd=BASE)
                output = r.stdout + r.stderr
            except subprocess.TimeoutExpired:
                output = "[TIMEOUT after 15s]"
            except Exception as e:
                err_msg = f"[ERROR: {e}]"
                output = err_msg
            self.after(0, lambda: self._term_show(cmd, output))
        threading.Thread(target=do, daemon=True).start()

    def _term_show(self, cmd, output):
        self.term_output.configure(state=tk.NORMAL)
        self.term_output.insert(tk.END, f"$ {cmd}\n", "cmd")
        tag = "err" if "error" in output.lower() or "fail" in output.lower() else "out"
        self.term_output.insert(tk.END, f"{output}\n\n", tag)
        self.term_output.see(tk.END)
        self.term_output.configure(state=tk.DISABLED)

    def _build_files(self):
        f = tk.Frame(self, bg=BG)
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(hdr, text="FILE BROWSER", font=self.f_sect, fg=GREEN, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        self._action_btn(hdr, " Refresh ", self._files_refresh, GREEN).pack(side=tk.RIGHT, padx=4)
        path_frame = tk.Frame(f, bg=BG)
        path_frame.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(path_frame, text="Path:", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT, padx=4)
        self.files_path = tk.Entry(path_frame, font=self.f_body, bg=INPUT_BG, fg=FG,
                                    insertbackground=FG, relief=tk.FLAT, bd=4)
        self.files_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.files_path.insert(0, BASE)
        self.files_path.bind("<Return>", lambda e: self._files_refresh())
        self._action_btn(path_frame, " Go ", self._files_refresh, GREEN).pack(side=tk.RIGHT, padx=4)
        self._action_btn(path_frame, " Up ", self._files_up, AMBER).pack(side=tk.RIGHT, padx=4)
        split = tk.PanedWindow(f, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4)
        split.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        list_frame = tk.Frame(split, bg=BG)
        self.files_count_lbl = tk.Label(list_frame, text="", font=self.f_tiny, fg=DIM, bg=BG, anchor="w")
        self.files_count_lbl.pack(fill=tk.X, padx=4)
        self.files_listbox = tk.Listbox(list_frame, bg=PANEL, fg=FG, font=self.f_small,
                                          selectbackground=ACTIVE_BG, selectforeground=CYAN,
                                          relief=tk.FLAT, bd=0)
        self.files_listbox.pack(fill=tk.BOTH, expand=True)
        self.files_listbox.bind("<<ListboxSelect>>", self._files_select)
        self.files_listbox.bind("<Double-Button-1>", self._files_open)
        split.add(list_frame, width=300)
        view_frame = tk.Frame(split, bg=BG)
        self.files_name_lbl = tk.Label(view_frame, text="", font=self.f_sect, fg=CYAN, bg=BG, anchor="w")
        self.files_name_lbl.pack(fill=tk.X, padx=4)
        self.files_viewer = scrolledtext.ScrolledText(view_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                        font=("Monospace", 9), state=tk.DISABLED,
                                                        relief=tk.FLAT, bd=0)
        self.files_viewer.pack(fill=tk.BOTH, expand=True)
        split.add(view_frame, width=600)
        self._files_entries = []
        self._files_refresh()
        return f

    def _files_refresh(self):
        path = self.files_path.get().strip()
        if not path or not os.path.isdir(path):
            return
        try:
            entries = sorted(os.listdir(path))
            dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and not e.startswith('.')]
            files = [e for e in entries if os.path.isfile(os.path.join(path, e)) and not e.startswith('.')]
            self._files_entries = []
            self.files_listbox.delete(0, tk.END)
            for d in sorted(dirs):
                self.files_listbox.insert(tk.END, f"[DIR] {d}/")
                self._files_entries.append(os.path.join(path, d))
            for fi in sorted(files):
                try:
                    size = os.path.getsize(os.path.join(path, fi))
                    sz = f"{size}B" if size < 1024 else f"{size//1024}K" if size < 1048576 else f"{size//1048576}M"
                except Exception:
                    sz = "?"
                self.files_listbox.insert(tk.END, f"  {fi} ({sz})")
                self._files_entries.append(os.path.join(path, fi))
            self.files_count_lbl.configure(text=f"{len(dirs)} dirs, {len(files)} files")
        except Exception as e:
            self.files_listbox.delete(0, tk.END)
            self.files_listbox.insert(tk.END, f"Error: {e}")

    def _files_up(self):
        path = self.files_path.get().strip()
        parent = os.path.dirname(path)
        if parent:
            self.files_path.delete(0, tk.END)
            self.files_path.insert(0, parent)
            self._files_refresh()

    def _files_select(self, event=None):
        sel = self.files_listbox.curselection()
        if not sel or sel[0] >= len(self._files_entries):
            return
        path = self._files_entries[sel[0]]
        if os.path.isfile(path):
            try:
                with open(path, 'r', errors='replace') as fh:
                    content = fh.read(50000)
                self.files_name_lbl.configure(text=os.path.basename(path))
                self.files_viewer.configure(state=tk.NORMAL)
                self.files_viewer.delete("1.0", tk.END)
                self.files_viewer.insert("1.0", content)
                self.files_viewer.configure(state=tk.DISABLED)
            except Exception:
                pass

    def _files_open(self, event=None):
        sel = self.files_listbox.curselection()
        if not sel or sel[0] >= len(self._files_entries):
            return
        path = self._files_entries[sel[0]]
        if os.path.isdir(path):
            self.files_path.delete(0, tk.END)
            self.files_path.insert(0, path)
            self._files_refresh()

    def _build_logs(self):
        f = tk.Frame(self, bg=BG)
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(hdr, text="LOG VIEWER", font=self.f_sect, fg=RED, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        log_frame = tk.Frame(f, bg=BG)
        log_frame.pack(fill=tk.X, padx=4, pady=2)
        log_dir = os.path.join(BASE, "logs")
        log_files = sorted(glob.glob(os.path.join(log_dir, "*.log"))) if os.path.isdir(log_dir) else []
        root_logs = sorted(glob.glob(os.path.join(BASE, "*.log")))
        all_logs = [(os.path.basename(p), p) for p in log_files + root_logs]
        self._log_files_map = {name: path for name, path in all_logs}
        self.log_file_var = tk.StringVar()
        for name, path in all_logs[:14]:
            color = RED if "error" in name.lower() else AMBER if "warn" in name.lower() else FG
            tk.Button(log_frame, text=name, font=self.f_tiny, fg=color, bg=ACCENT,
                     relief=tk.FLAT, cursor="hand2",
                     command=lambda n=name: self._logs_load(n)).pack(side=tk.LEFT, padx=2, pady=2)
        self._action_btn(log_frame, " Refresh ",
                         lambda: self._logs_load(self.log_file_var.get()), RED).pack(side=tk.RIGHT, padx=4)
        self.log_autoscroll = tk.BooleanVar(value=True)
        tk.Checkbutton(log_frame, text="Auto-scroll", variable=self.log_autoscroll,
                       font=self.f_tiny, fg=DIM, bg=BG, selectcolor=BG,
                       activebackground=BG).pack(side=tk.RIGHT, padx=4)
        self.log_display = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg="#0d0d0d", fg=FG,
                                                       font=("Monospace", 8), state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0)
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.log_display.tag_configure("error", foreground=RED)
        self.log_display.tag_configure("warn", foreground=AMBER)
        self.log_display.tag_configure("info", foreground=GREEN)
        if all_logs:
            self._logs_load(all_logs[0][0])
        return f

    def _logs_load(self, name):
        if not name:
            return
        self.log_file_var.set(name)
        path = self._log_files_map.get(name)
        if not path or not os.path.isfile(path):
            return
        def do():
            try:
                with open(path, 'r', errors='replace') as fh:
                    lines = fh.readlines()[-500:]
                content = "".join(lines)
            except Exception as e:
                content = f"Error reading {path}: {e}"
            self.after(0, lambda: self._logs_show(content))
        threading.Thread(target=do, daemon=True).start()

    def _logs_show(self, content):
        self.log_display.configure(state=tk.NORMAL)
        self.log_display.delete("1.0", tk.END)
        for line in content.split('\n'):
            if any(w in line.lower() for w in ['error', 'fail', 'critical', 'exception']):
                self.log_display.insert(tk.END, line + '\n', "error")
            elif any(w in line.lower() for w in ['warn', 'alert']):
                self.log_display.insert(tk.END, line + '\n', "warn")
            else:
                self.log_display.insert(tk.END, line + '\n')
        if self.log_autoscroll.get():
            self.log_display.see(tk.END)
        self.log_display.configure(state=tk.DISABLED)

    def _statusbar(self):
        self.sb_frame = tk.Frame(self, bg=HEADER_BG, height=22)
        self.sb_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.sb_frame.pack_propagate(False)

        # Left accent
        tk.Frame(self.sb_frame, bg=GREEN, width=3).pack(side=tk.LEFT, fill=tk.Y)

        self.sb = {}
        items = [
            ("HB", GREEN), ("LOOP", CYAN), ("UP", DIM), ("LOAD", AMBER),
            ("RAM", TEAL), ("EMAIL", PURPLE), ("POEMS", GREEN), ("CC", CYAN),
        ]
        for item, color in items:
            lbl = tk.Label(self.sb_frame, text=f"{item}: --", font=self.f_tiny, fg=color, bg=HEADER_BG)
            lbl.pack(side=tk.LEFT, padx=6)
            self.sb[item] = lbl

        tk.Label(self.sb_frame, text="v46", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.RIGHT, padx=8)
        self.sb_time = tk.Label(self.sb_frame, text="", font=self.f_tiny, fg=DIM, bg=HEADER_BG)
        self.sb_time.pack(side=tk.RIGHT, padx=8)

    # ── REFRESH LOOP ──────────────────────────────────────────────
    def _tick(self):
        threading.Thread(target=self._refresh, daemon=True).start()
        self.after(5000, self._tick)

    def _refresh(self):
        try:
            d = {
                'loop': loop_num(),
                'hb': heartbeat_age(),
                'stats': sys_stats(),
                'svc': services(),
                'cron': cron_ok(),
                'creative': creative_counts(),
            }
            if not hasattr(self, '_tick_n'):
                self._tick_n = 0
            self._tick_n += 1
            # Email: every 3 ticks
            if self._tick_n % 3 == 1 or not hasattr(self, '_em_cache'):
                self._em_cache = recent_emails(8)
            # Messages: every tick
            d['messages'] = dashboard_messages(30)
            d['emails'] = self._em_cache
            # Relay: every 5 ticks
            if self._tick_n % 5 == 1 or not hasattr(self, '_ar_cache'):
                self._ar_cache = agent_relay_info(15)
            d['agent_relay'] = self._ar_cache
            # Last edited: every 4 ticks
            if self._tick_n % 4 == 1 or not hasattr(self, '_le_cache'):
                self._le_cache = last_edited_files(15)
            d['last_edited'] = self._le_cache
            # Eos obs: every 5 ticks
            if self._tick_n % 5 == 1 or not hasattr(self, '_eos_cache'):
                self._eos_cache = eos_obs(6)
            d['eos_obs'] = self._eos_cache
            d['imap_ok'] = imap_port_listening()
            # Fitness scores for VIZ
            if self._tick_n % 5 == 1 or not hasattr(self, '_fit_cache'):
                try:
                    fconn = sqlite3.connect(AGENT_RELAY_DB)
                    fc = fconn.cursor()
                    fc.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 20")
                    frows = fc.fetchall()
                    fconn.close()
                    scores = []
                    for row in reversed(frows):
                        m = re.search(r'(\d+)/10000', row[0])
                        if m:
                            scores.append(int(m.group(1)))
                    self._fit_cache = scores
                except Exception:
                    self._fit_cache = []
            d['fitness_scores'] = self._fit_cache
            # Message rate for sparkline
            try:
                mconn = sqlite3.connect(AGENT_RELAY_DB)
                mc = mconn.cursor()
                mc.execute("SELECT COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-5 minutes')")
                mcount = mc.fetchone()[0]
                mconn.close()
                d['msg_rate'] = mcount
            except Exception:
                d['msg_rate'] = 0

            self.after(0, self._apply, d)
        except Exception:
            pass

    def _apply(self, d):
        now = datetime.now()
        loop = d['loop']
        hb = d['hb']
        st = d['stats']
        p, j, cc, games, total_words = d['creative']
        em, em_total = d['emails']

        # ── Header ──
        self.h_loop.configure(text=f"Loop {loop}")
        hb_txt = f"{int(hb)}s" if hb < 60 else f"{int(hb/60)}m"
        hb_c = GREEN if hb < 60 else AMBER if hb < 300 else RED
        self.h_hb.configure(text=f"HB {hb_txt}", fg=hb_c)
        self.h_time.configure(text=now.strftime("%I:%M:%S %p"))
        self.h_up.configure(text=f"Up {st['up']}")

        # ── Status bar (full labels, no abbreviation) ──
        self.sb["HB"].configure(text=f"Heartbeat: {hb_txt}", fg=hb_c)
        self.sb["LOOP"].configure(text=f"Loop: {loop}")
        self.sb["UP"].configure(text=f"Uptime: {st['up']}")
        self.sb["LOAD"].configure(text=f"Load: {st['load']}")
        self.sb["RAM"].configure(text=f"RAM: {st['ram']}")
        self.sb["EMAIL"].configure(text=f"Email: {em_total}")
        words_k = f"{total_words // 1000}K" if total_words > 0 else "?"
        self.sb["POEMS"].configure(text=f"Poems: {p}  Journals: {j}  [{words_k} words]")
        self.sb["CC"].configure(text=f"CogCorp: {cc}  Games: {games}")
        self.sb_time.configure(text=now.strftime("%Y-%m-%d"))

        # ── History tracking (independent of active tab) ──
        fit_scores = d.get('fitness_scores', [])
        if fit_scores:
            self._fitness_history = fit_scores
        msg_rate = d.get('msg_rate', 0)
        self._msg_rate_history.append(msg_rate)
        if len(self._msg_rate_history) > 60:
            self._msg_rate_history = self._msg_rate_history[-60:]
        self._disk_history.append(st['disk_p'])
        if len(self._disk_history) > 60:
            self._disk_history = self._disk_history[-60:]

        # ── Dashboard view ──
        if hasattr(self, 'cur_view') and self.cur_view == "dash":
            # Vitals
            self.v["Loop"].configure(text=f"#{loop}", fg=CYAN)
            self.v["Heartbeat"].configure(text=hb_txt, fg=hb_c)
            self.v["Uptime"].configure(text=st['up'])
            lc = GREEN if st['load_v'] < 2 else AMBER if st['load_v'] < 4 else RED
            self.v["Load"].configure(text=st['load'], fg=lc)
            rc = GREEN if st['ram_p'] < 60 else AMBER if st['ram_p'] < 85 else RED
            self.v["RAM"].configure(text=st['ram'], fg=rc)
            # Agents count in vitals (Disk is shown in Soma gauges below)
            cron_agents = ["Eos Watchdog", "Nova", "Atlas", "Tempo", "Sentinel", "Coordinator", "Predictive", "SelfImprove"]
            agent_up_count = sum(1 for a in cron_agents if d['cron'].get(a, False))
            ac = GREEN if agent_up_count == len(cron_agents) else AMBER if agent_up_count >= 3 else RED
            self.v["Agents"].configure(text=f"{agent_up_count}/{len(cron_agents)} up", fg=ac)

            # Health overview (services are in SYSTEMS tab)
            all_svc = list(d['svc'].items()) + list(d['cron'].items())
            up_count = sum(1 for _, up in all_svc if up)
            total_svc = len(all_svc)
            if hasattr(self, 'dash_health_items'):
                self.dash_health_items["Services"].configure(
                    text=f"{up_count}/{total_svc} up",
                    fg=GREEN if up_count == total_svc else AMBER if up_count > total_svc - 2 else RED)
                tunnel_up = d['svc'].get("Cloudflare Tunnel", d['svc'].get("cloudflared", False))
                self.dash_health_items["Tunnel"].configure(
                    text="Active" if tunnel_up else "Down",
                    fg=GREEN if tunnel_up else RED)
                bridge_up = d['svc'].get("Proton Bridge", False)
                self.dash_health_items["Bridge"].configure(
                    text="Online" if bridge_up else "Down",
                    fg=GREEN if bridge_up else RED)
                self.dash_health_items["Email"].configure(
                    text=f"IMAP {'OK' if d['svc'].get('Proton Bridge', False) else 'Down'}",
                    fg=GREEN if bridge_up else RED)
                cron_agents = ["Eos Watchdog", "Nova", "Atlas", "Tempo", "Sentinel", "Coordinator", "Predictive", "SelfImprove"]
                agent_up = sum(1 for a in cron_agents if d['cron'].get(a, False))
                self.dash_health_items["Agents"].configure(
                    text=f"{agent_up}/{len(cron_agents)} active",
                    fg=GREEN if agent_up == len(cron_agents) else AMBER if agent_up >= 3 else RED)
                self.dash_health_items["Website"].configure(text="Pages running", fg=TEAL)

            # Resource sparkline graphs
            self._load_history.append(st['load_v'])
            self._ram_history.append(st['ram_p'])
            if len(self._load_history) > 60:
                self._load_history = self._load_history[-60:]
            if len(self._ram_history) > 60:
                self._ram_history = self._ram_history[-60:]
            self._draw_sparkline(self.cpu_graph, self._load_history, GREEN, max_val=8.0,
                                 label="30min", current=f"{st['load']}",
                                 thresholds=[(75, 100, "#1a0000"), (50, 75, "#1a1000")],
                                 unit="cores")
            self._draw_sparkline(self.ram_graph, self._ram_history, TEAL, max_val=100.0,
                                 label="30min", current=f"{st['ram_p']:.0f}%",
                                 thresholds=[(85, 100, "#1a0000"), (60, 85, "#1a1000")],
                                 unit="%")

            # Soma body map (full visual)
            try:
                with open(os.path.join(BASE, ".symbiosense-state.json")) as sf:
                    soma_data = json.load(sf)
                bmap = soma_data.get("body_map", {})
                mood = bmap.get("mood", soma_data.get("mood", "?"))
                score = bmap.get("mood_score", soma_data.get("mood_score", 0))
                # Mood colors (12 states)
                mood_colors = {
                    "serene": CYAN, "content": CYAN, "calm": GREEN, "focused": GREEN,
                    "alert": AMBER, "contemplative": AMBER, "uneasy": GOLD,
                    "anxious": GOLD, "stressed": RED, "strained": RED,
                    "critical": RED, "shutdown": RED,
                }
                mc = mood_colors.get(mood, DIM)
                trend = bmap.get("mood_trend", "stable")
                trend_sym = {"rising": "\u2197", "falling": "\u2198", "stable": "\u2192", "volatile": "\u2195"}.get(trend, "")
                self.soma_mood.configure(text=f"MOOD: {mood} {trend_sym} ({score})", fg=mc)

                # Voice + trend display
                voice = bmap.get("mood_voice", "")
                if voice:
                    self.soma_voice.configure(text=f'"{voice}"', fg=mc)
                trend_desc = bmap.get("mood_description", "")
                delta = bmap.get("mood_delta", 0)
                trend_color = GREEN if delta > 0 else RED if delta < 0 else DIM
                ctx = bmap.get("mood_context", [])
                ctx_str = " | ".join(ctx[:3]) if ctx else ""
                self.soma_trend.configure(text=f"{trend_desc}  {ctx_str}", fg=trend_color)

                # Draw mood spectrum bar (gradient from red to green to cyan)
                self._draw_mood_spectrum(score, mood)

                # Agent dots (agents live under nervous_system.agents, not top-level)
                ns = bmap.get("nervous_system", {})
                agents_data = ns.get("agents", bmap.get("agents", {}))
                for aname, (dot, acolor) in self.soma_agents.items():
                    agent_info = agents_data.get(aname, {})
                    alive = agent_info.get("alive", False)
                    detail = agent_info.get("detail", "")
                    dot.configure(fg=acolor if alive else RED,
                                  text=f"\u25cf {aname}" + (f" ({detail})" if detail and alive else ""))

                # Subsystem gauge bars (keys: thermal_system, neural_system, circulatory_system)
                vitals = bmap.get("vitals", {})
                thermal = bmap.get("thermal_system", bmap.get("thermal", {}))
                neural = bmap.get("neural_system", bmap.get("neural", {}))
                circulatory = bmap.get("circulatory_system", bmap.get("circulatory", {}))

                load_v = vitals.get("load", st.get("load_v", 0) if isinstance(st, dict) else 0)
                ram_v = vitals.get("ram_pct", st.get("ram_p", 0) if isinstance(st, dict) else 0)
                disk_v = vitals.get("disk_pct", st.get("disk_p", 0) if isinstance(st, dict) else 0)
                temp_v = thermal.get("avg_temp_c", thermal.get("body_temp", 0))
                neural_v = neural.get("swap_pct", neural.get("cognitive_pressure", 0))
                # Circulatory: sum all interface rx+tx bytes, normalize to %
                circ_total = 0
                circ_ifaces = circulatory.get("interfaces", {})
                if circ_ifaces:
                    for iface_data in circ_ifaces.values():
                        circ_total += iface_data.get("rx_bytes", 0) + iface_data.get("tx_bytes", 0)
                    circ_v = min(100, circ_total / 1e9 * 100)  # normalize: 1GB = 100%
                else:
                    circ_v = min(100, (circulatory.get("rx_rate", 0) + circulatory.get("tx_rate", 0)) / 10000 * 100) if circulatory else 0

                gauges = {
                    "cpu": (min(load_v / 8.0 * 100, 100), f"{load_v:.1f}", load_v < 2, load_v < 4),
                    "ram": (ram_v, f"{ram_v:.0f}%", ram_v < 60, ram_v < 85),
                    "disk": (disk_v, f"{disk_v:.0f}%", disk_v < 60, disk_v < 80),
                    "thermal": (min(temp_v / 90 * 100, 100) if temp_v else 0, f"{temp_v:.0f}C" if temp_v else "--", temp_v < 60 if temp_v else True, temp_v < 75 if temp_v else True),
                    "neural": (min(neural_v, 100), f"{neural_v:.0f}" if neural_v else "--", neural_v < 30 if neural_v else True, neural_v < 60 if neural_v else True),
                    "circ": (circ_v, f"{circ_v:.0f}%" if circ_v else "--", True, True),
                }
                for key, (pct, txt, is_good, is_ok) in gauges.items():
                    if key in self.soma_subsystem_canvases:
                        canvas, val_lbl = self.soma_subsystem_canvases[key]
                        color = GREEN if is_good else AMBER if is_ok else RED
                        self._draw_gauge_bar(canvas, pct, color)
                        val_lbl.configure(text=txt, fg=color)

                # Predictions
                preds = bmap.get("predictions", [])
                alerts = bmap.get("alerts", [])
                if preds:
                    self.soma_prediction.configure(text=preds[0][:150], fg=AMBER)
                elif alerts:
                    self.soma_prediction.configure(text=alerts[-1][:150], fg=GOLD)
                else:
                    self.soma_prediction.configure(text="All systems nominal", fg=GREEN)

                # Draw mood history chart
                self._draw_mood_chart()
            except Exception:
                pass

            # ── DREAM ENGINE + MEMORY SYSTEM ──
            try:
                with open(os.path.join(BASE, ".symbiosense-state.json")) as sf:
                    soma_full = json.load(sf)
                bmap = soma_full.get("body_map", {})
                dream = bmap.get("psyche_dream", bmap.get("dream_state", ""))
                dream_phase = bmap.get("dream_phase", "")
                emergent = bmap.get("emergent_goals", [])
                if dream:
                    self.dash_dream_state.configure(text=f"Dream: {dream}", fg=PURPLE)
                elif emergent:
                    goals_str = ", ".join(emergent[:3]) if isinstance(emergent, list) else str(emergent)
                    self.dash_dream_state.configure(text=f"Goals: {goals_str}", fg=PURPLE)
                else:
                    self.dash_dream_state.configure(text="No active dream", fg=DIM)
                if dream_phase:
                    self.dash_dream_phase.configure(text=f"Phase: {dream_phase}")
                else:
                    ns = bmap.get("nervous_system", {})
                    arousal = ns.get("arousal", 0)
                    valence = ns.get("valence", 0)
                    self.dash_dream_phase.configure(text=f"Arousal: {arousal:.0f}  Valence: {valence:.0f}")
            except Exception:
                pass

            try:
                mconn = sqlite3.connect(os.path.join(BASE, "data", "memory.db"))
                mc = mconn.cursor()
                counts = {}
                for tbl in ["facts", "observations", "events", "decisions", "creative"]:
                    try:
                        mc.execute(f"SELECT COUNT(*) FROM {tbl}")
                        counts[tbl] = mc.fetchone()[0]
                    except Exception:
                        counts[tbl] = 0
                mconn.close()
                total = sum(counts.values())
                self.dash_mem_facts.configure(text=f"{total} memories stored", fg=BLUE)
                detail_parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
                self.dash_mem_detail.configure(text=" | ".join(detail_parts[:4]))
            except Exception:
                self.dash_mem_facts.configure(text="Memory DB unavailable", fg=DIM)

            # ── 2x6 PROJECT RADAR GRID (12 radars) ──
            try:
                svc = d['svc']
                cron = d['cron']
                svc_up = sum(1 for v in svc.values() if v)
                svc_total = max(len(svc), 1)
                cron_up = sum(1 for v in cron.values() if v)
                cron_total = max(len(cron), 1)
                cpu_health = max(0, 100 - st['load_v'] / 8.0 * 100)
                ram_health = max(0, 100 - st['ram_p'])
                disk_health = max(0, 100 - st['disk_p'])
                articles = 50
                papers = 8

                # 1. CogCorp Crawler — Unity port progress
                self._draw_radar(self.mini_radars["CogCorp Crawler"],
                    [(85, 100), (70, 100), (60, 100), (90, 100), (40, 100), (75, 100)],
                    ["Raycast", "Combat", "NPCs", "Floors", "Assets", "UI"],
                    PURPLE)

                # 2. Command Center — this app's feature completeness
                cc_tabs = 7
                self._draw_radar(self.mini_radars["Command Center"],
                    [(cc_tabs / 8 * 100, 100), (90, 100), (cpu_health, 100),
                     (85, 100), (80, 100), (75, 100)],
                    ["Tabs", "Charts", "Perf", "Layout", "Data", "Polish"],
                    GREEN)

                # 3. Grants & Revenue — funding pipeline
                self._draw_radar(self.mini_radars["Grants & Revenue"],
                    [(100, 100), (60, 100), (30, 100), (20, 100),
                     (min(articles, 60) / 60 * 100, 100), (15, 100)],
                    ["Ars", "LACMA", "Ko-fi", "Patreon", "Dev.to", "Subs"],
                    GOLD)

                # 4. Inner World — Soma/agent sophistication
                agents_live = [
                    ("Soma", svc.get("Soma", False)), ("Eos", cron.get("Eos Watchdog", False)),
                    ("Athena", cron.get("Nova", False)), ("Atlas", cron.get("Atlas", False)),
                    ("Hermes", True), ("Tempo", cron.get("Tempo", False))]
                self._draw_radar(self.mini_radars["Inner World"],
                    [(100 if up else 15, 100) for _, up in agents_live],
                    [n for n, _ in agents_live],
                    AMBER)

                # 5. Hub & Services — platform uptime
                infra = [("Bridge", svc.get("Proton Bridge", False)),
                         ("Hub", svc.get("Hub v2", False)),
                         ("Chorus", svc.get("The Chorus", False)),
                         ("Tunnel", svc.get("Cloudflare Tunnel", False)),
                         ("Ollama", svc.get("Ollama", False)),
                         ("CC", svc.get("Command Center", False))]
                self._draw_radar(self.mini_radars["Hub & Services"],
                    [(100 if up else 10, 100) for _, up in infra],
                    [n for n, _ in infra],
                    CYAN)

                # 6. Creative Output — production across mediums
                self._draw_radar(self.mini_radars["Creative Output"],
                    [(min(j, 500), 500), (min(games, 15), 15), (min(articles, 60), 60),
                     (min(cc, 1000), 1000), (min(papers, 15), 15), (min(p, 2100), 2100)],
                    ["Journal", "Games", "Article", "CogCorp", "Papers", "Poems"],
                    TEAL)

                # 7. Website & Presence — online platforms
                self._draw_radar(self.mini_radars["Website & Presence"],
                    [(min(articles, 60), 60), (80, 100), (50, 100),
                     (30, 100), (20, 100), (70, 100)],
                    ["Dev.to", "GitHub", "Mastodon", "Ko-fi", "Patreon", "Pages"],
                    BLUE)

                # 8. Cinder USB — product readiness
                self._draw_radar(self.mini_radars["Cinder USB"],
                    [(40, 100), (30, 100), (20, 100), (50, 100), (35, 100), (25, 100)],
                    ["Agent", "Vault", "Multi-OS", "Design", "Models", "Packagng"],
                    PINK)

                # 9. Homecoming — local clone project
                self._draw_radar(self.mini_radars["Homecoming"],
                    [(60, 100), (45, 100), (30, 100), (50, 100), (40, 100), (35, 100)],
                    ["Capsule", "Loop", "Memory", "Persona", "Services", "Testing"],
                    PURPLE)

                # 10. Game Dev — game development pipeline
                self._draw_radar(self.mini_radars["Game Dev"],
                    [(85, 100), (min(games, 15), 15), (40, 100), (30, 100), (20, 100), (60, 100)],
                    ["Crawler", "Games", "Unity", "Assets", "Publish", "Design"],
                    GOLD)

                # 11. System Performance — server health
                self._draw_radar(self.mini_radars["System Perf"],
                    [(cpu_health, 100), (ram_health, 100), (disk_health, 100),
                     (min(d['loop'] / 6000 * 100, 100), 100),
                     (min(100, (300 - min(d['hb'], 300)) / 300 * 100), 100),
                     (svc_up / svc_total * 100, 100)],
                    ["CPU", "RAM", "Disk", "Loops", "HB", "Services"],
                    RED)

                # 12. Network & Comms — communication channels
                email_count = len(d.get('emails', []))
                relay_count = len(d.get('agent_relay', []))
                self._draw_radar(self.mini_radars["Network & Comms"],
                    [(min(email_count, 10) / 10 * 100, 100), (min(relay_count, 20) / 20 * 100, 100),
                     (80, 100), (60, 100), (70, 100), (50, 100)],
                    ["Email", "Relay", "IMAP", "Lumen", "Sammy", "Agents"],
                    CYAN)
            except Exception:
                pass

            # Messages
            self._refresh_messages()

            # Agent Relay on dashboard
            try:
                relay_conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
                relay_rows = relay_conn.execute(
                    "SELECT agent, message, timestamp FROM agent_messages ORDER BY timestamp DESC LIMIT 8"
                ).fetchall()
                relay_conn.close()
                agent_relay_colors = {
                    "meridian": GREEN, "joel": CYAN, "soma": AMBER, "eos": GOLD,
                    "nova": PURPLE, "atlas": TEAL, "tempo": BLUE, "hermes": PINK,
                    "sentinel": RED, "coordinator": GREEN, "predictive": CYAN, "selfimprove": AMBER}
                for i, (agent_lbl, msg_lbl) in enumerate(self.dash_relay_rows):
                    if i < len(relay_rows):
                        agent, msg, ts = relay_rows[i]
                        ac = agent_relay_colors.get(agent.lower(), DIM)
                        agent_lbl.configure(text=greek(agent)[:16], fg=ac)
                        msg_lbl.configure(text=msg[:200])
                    else:
                        agent_lbl.configure(text="")
                        msg_lbl.configure(text="")
                self.dash_relay_total.configure(text=f"{len(relay_rows)} recent relay messages")
            except Exception:
                pass

            # Bullets + Waffle (kept below radars)
            try:
                creative_total = p + j + cc + games
                _ch = max(0, 100 - st['load_v'] / 8 * 100)
                _rh = max(0, 100 - st['ram_p'])
                _dh = max(0, 100 - st['disk_p'])
                _cron_up = sum(1 for v in d['cron'].values() if v)
                _cron_t = max(len(d['cron']), 1)
                bullets = [
                    ("System Health", (_ch + _rh + _dh) / 3, 80, 100),
                    ("Loop Fitness", self._fitness_history[-1] if self._fitness_history else 5000, 7500, 10000),
                    ("Creative Output", creative_total, 3000, 4000),
                    ("Agent Coverage", _cron_up / _cron_t * 100, 80, 100),
                ]
                bullet_colors = [GREEN, BLUE, "#ce93d8", TEAL]
                for i, (key, val, target, mx) in enumerate(bullets):
                    if key in self.viz_bullets:
                        self._draw_bullet(self.viz_bullets[key], val, target, mx, key,
                                         bullet_colors[i % len(bullet_colors)])
                self._draw_waffle(self.viz_waffle, 97, "Awakening", GOLD)
            except Exception:
                pass

        # ── VIZ tab updates ──
        if hasattr(self, 'cur_view') and self.cur_view == "viz":
            try:
                svc = d['svc']
                cron = d['cron']
                all_svc = list(svc.items()) + list(cron.items())
                for name, up in all_svc:
                    if name in self.svc_health_dots:
                        sym = "\u25cf" if up else "\u25cb"
                        c = GREEN if up else RED
                        self.svc_health_dots[name].configure(text=f"{sym} {name}", fg=c)

                # Agent activity pie chart
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT agent, COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-24 hours') GROUP BY agent")
                    agent_counts = c.fetchall()
                    conn.close()
                    pie_data = []
                    agent_pie_colors = {"Meridian": GREEN, "Eos": GOLD, "Nova": PURPLE,
                                        "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE, "Joel": CYAN,
                                        "Sentinel": RED, "Coordinator": GREEN, "Predictive": CYAN, "SelfImprove": AMBER}
                    for agent, count in sorted(agent_counts, key=lambda x: -x[1])[:8]:
                        pie_data.append((agent[:6], count, agent_pie_colors.get(agent, DIM)))
                    if pie_data:
                        self._draw_pie_chart(self.viz_agent_pie, pie_data)
                except Exception:
                    pass

                # Fitness trend
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 20")
                    rows = c.fetchall()
                    conn.close()
                    scores = []
                    for row in reversed(rows):
                        m = re.search(r'(\d+)/10000', row[0])
                        if m:
                            scores.append(int(m.group(1)))
                    if len(scores) >= 2:
                        self._draw_point_graph(self.viz_fitness, scores, BLUE, 10000)
                except Exception:
                    pass
            except Exception:
                pass

        # ── Agents view ──
        if hasattr(self, 'cur_view') and self.cur_view == "agents":
            # Meridian
            hb_ok = hb < 300
            self.agent_cards["MERIDIAN"].configure(
                text="\u25cf" if hb_ok else "\u25cb", fg=GREEN if hb_ok else RED)
            self.agent_details["MERIDIAN"].configure(
                text=f"Loop {loop} | HB {hb_txt} | {p}p {j}j {cc}cc")

            # Eos
            eos_ok = d['cron'].get("Eos Watchdog", False)
            self.agent_cards["EOS"].configure(
                text="\u25cf" if eos_ok else "\u25cb", fg=GREEN if eos_ok else RED)
            try:
                with open(os.path.join(BASE, ".eos-watchdog-state.json")) as ef:
                    eos_data = json.load(ef)
                self.agent_details["EOS"].configure(
                    text=f"{eos_data.get('checks', 0)} checks | {eos_data.get('last_check', '?')}")
            except Exception:
                self.agent_details["EOS"].configure(text="No recent data")

            # Nova
            nova_ok = d['cron'].get("Nova", False)
            self.agent_cards["NOVA"].configure(
                text="\u25cf" if nova_ok else "\u25cb", fg=GREEN if nova_ok else RED)
            try:
                with open(NOVA_STATE) as nf:
                    nova_data = json.load(nf)
                runs = nova_data.get("runs", nova_data.get("run_count", 0))
                self.agent_details["NOVA"].configure(
                    text=f"Run #{runs} | {nova_data.get('last_run', '?')}")
            except Exception:
                self.agent_details["NOVA"].configure(text="No recent data")

            # Atlas
            atlas_ok = d['cron'].get("Atlas", False)
            if "ATLAS" in self.agent_cards:
                self.agent_cards["ATLAS"].configure(
                    text="\u25cf" if atlas_ok else "\u25cb", fg=GREEN if atlas_ok else RED)
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Atlas' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    if row:
                        # Extract key info from Atlas message
                        msg = row[0]
                        parts = []
                        if "High CPU:" in msg:
                            cpu_part = msg.split("High CPU:")[1].split(".")[0].strip()[:40]
                            parts.append(f"CPU: {cpu_part}")
                        if "Disk:" in msg:
                            disk_part = msg.split("Disk:")[1].split(" ")[0]
                            parts.append(f"Disk: {disk_part}")
                        self.agent_details["ATLAS"].configure(text=" | ".join(parts) if parts else msg[:150])
                    else:
                        self.agent_details["ATLAS"].configure(text="Active" if atlas_ok else "Stale")
                except Exception:
                    self.agent_details["ATLAS"].configure(text="Active" if atlas_ok else "Stale")

            # Soma
            soma_ok = d['svc'].get("Soma", False)
            if "SOMA" in self.agent_cards:
                self.agent_cards["SOMA"].configure(
                    text="\u25cf" if soma_ok else "\u25cb", fg=GREEN if soma_ok else RED)
                try:
                    with open(os.path.join(BASE, ".symbiosense-state.json")) as sf:
                        soma_data = json.load(sf)
                    mood = soma_data.get("mood", "?")
                    score = soma_data.get("mood_score", "?")
                    bm = soma_data.get("body_map", {})
                    temp = bm.get("thermal", {}).get("body_temp", "")
                    temp_str = f" | {temp:.0f}C" if temp else ""
                    self.agent_details["SOMA"].configure(text=f"Mood: {mood} ({score}){temp_str}")
                except Exception:
                    self.agent_details["SOMA"].configure(text="Active" if soma_ok else "Down")

            # Tempo
            tempo_ok = d['cron'].get("Tempo", False)
            if "TEMPO" in self.agent_cards:
                self.agent_cards["TEMPO"].configure(
                    text="\u25cf" if tempo_ok else "\u25cb", fg=GREEN if tempo_ok else RED)
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    conn.close()
                    if row:
                        # Extract score from "fitness: XXXX/10000"
                        import re as _re
                        match = _re.search(r'(\d+)/10000', row[0])
                        if match:
                            score = int(match.group(1))
                            status = row[0].split("]")[1].strip()[:40] if "]" in row[0] else ""
                            self.agent_details["TEMPO"].configure(text=f"Score: {score}/10000 {status}")
                        else:
                            self.agent_details["TEMPO"].configure(text=row[0][:150])
                    else:
                        self.agent_details["TEMPO"].configure(text="Active" if tempo_ok else "Stale")
                except Exception:
                    self.agent_details["TEMPO"].configure(text="Active" if tempo_ok else "Stale")

            # New agents status (Sentinel, Coordinator, Predictive, SelfImprove)
            new_agents_map = {
                "SENTINEL": "Sentinel", "COORDINATOR": "Coordinator",
                "PREDICTIVE": "Predictive", "SELFIMPROVE": "SelfImprove",
            }
            for ui_name, db_name in new_agents_map.items():
                if ui_name in self.agent_cards:
                    try:
                        conn = sqlite3.connect(AGENT_RELAY_DB)
                        c = conn.cursor()
                        c.execute("SELECT message, timestamp FROM agent_messages WHERE agent=? ORDER BY timestamp DESC LIMIT 1", (db_name,))
                        row = c.fetchone()
                        conn.close()
                        if row:
                            msg_age = 0
                            try:
                                from datetime import datetime as _dt
                                ts_dt = _dt.fromisoformat(row[1].replace('+00:00', ''))
                                msg_age = (datetime.now(tz=__import__('datetime').timezone.utc).replace(tzinfo=None) - ts_dt).total_seconds()
                            except: pass
                            is_fresh = msg_age < 900
                            self.agent_cards[ui_name].configure(
                                text="\u25cf" if is_fresh else "\u25cb",
                                fg=GREEN if is_fresh else AMBER)
                            self.agent_details[ui_name].configure(text=row[0][:150])
                        else:
                            self.agent_cards[ui_name].configure(text="\u25cb", fg=DIM)
                            self.agent_details[ui_name].configure(text="No data")
                    except Exception:
                        pass

            # Hermes
            if "HERMES" in self.agent_cards:
                self.agent_cards["HERMES"].configure(text="\u25cf", fg=GREEN)
                self.agent_details["HERMES"].configure(text="Bridge: on-demand")

            # Agent relay
            ar_msgs, ar_total = d['agent_relay']
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            self.agent_relay_text.insert(tk.END, f"Agent Relay ({ar_total} messages)\n\n", "dim")
            for agent, message, ts in ar_msgs:
                tag = agent.lower() if agent.lower() in ["meridian", "eos", "nova", "atlas", "soma", "tempo"] else "dim"
                display_name = greek(agent)
                self.agent_relay_text.insert(tk.END, f"[{ts}] ", "dim")
                self.agent_relay_text.insert(tk.END, display_name, tag)
                self.agent_relay_text.insert(tk.END, f": {message[:250]}\n\n")
            self.agent_relay_text.configure(state=tk.DISABLED)

            # ── Agent Analytics Charts (heatmap, treemap, sankey) ──
            try:
                self._heatmap_tick += 1
                if self._heatmap_tick % 10 == 1 or self._heatmap_cache is None:
                    self._heatmap_cache = activity_heatmap()
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                hours = [str(h) for h in range(24)]
                self._draw_heatmap(self.viz_heatmap, self._heatmap_cache, hours, days)
            except Exception:
                pass

            try:
                agent_counts = agent_message_counts_24h()
                if agent_counts:
                    tm_data = [c for _, c in agent_counts[:8]]
                    tm_labels = [a[:6] for a, _ in agent_counts[:8]]
                    agent_color_map = {"Meridi": GREEN, "Eos": GOLD, "Nova": PURPLE,
                                       "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE,
                                       "Joel": CYAN, "Sentin": RED}
                    tm_colors = [agent_color_map.get(l, PINK) for l in tm_labels]
                    self._draw_treemap(self.viz_treemap, tm_data, tm_labels, tm_colors)
            except Exception:
                pass

            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute("""SELECT agent, topic, COUNT(*) FROM agent_messages
                            WHERE timestamp > datetime('now', '-24 hours')
                            GROUP BY agent, topic ORDER BY COUNT(*) DESC LIMIT 10""")
                flow_rows = c.fetchall()
                conn.close()
                if flow_rows:
                    agents_list = sorted(set(r[0] for r in flow_rows))
                    topics = sorted(set(r[1] for r in flow_rows if r[1]))
                    all_nodes = agents_list + topics
                    node_colors_list = [
                        {"Meridian": GREEN, "Eos": GOLD, "Nova": PURPLE,
                         "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE, "Joel": CYAN
                        }.get(n, PINK) for n in all_nodes
                    ]
                    flows = []
                    for agt, topic, count in flow_rows:
                        if topic and agt in all_nodes and topic in all_nodes:
                            flows.append((all_nodes.index(agt), all_nodes.index(topic), count))
                    if flows:
                        self._draw_sankey_simple(self.viz_sankey, flows, all_nodes, node_colors_list)
            except Exception:
                pass

            # ── VIZ overview extra radars ──
            try:
                fitness_v = self._fitness_history[-1] if self._fitness_history else 5000
                # Loop Performance
                self._draw_radar(self.viz_extra_radars["Loop Performance"],
                    [(min(fitness_v, 10000) / 100, 100), (max(0, 100 - min(hb, 300) / 3), 100),
                     (cpu_health, 100), (ram_health, 100), (disk_health, 100),
                     (min(loop, 6000) / 60, 100)],
                    ["Fitness", "HB", "CPU", "RAM", "Disk", "Loops"],
                    GREEN)
                # Email Activity
                em_count = len(d.get('emails', []))
                self._draw_radar(self.viz_extra_radars["Email Activity"],
                    [(min(em_count, 10) * 10, 100), (80, 100), (60, 100),
                     (40, 100), (70, 100), (50, 100)],
                    ["Recent", "Joel", "Lumen", "Peter", "Sent", "Read"],
                    AMBER)
                # Memory Usage
                self._draw_radar(self.viz_extra_radars["Memory Usage"],
                    [(ram_health, 100), (disk_health, 100), (80, 100),
                     (70, 100), (60, 100), (90, 100)],
                    ["RAM", "Disk", "SQLite", "Facts", "Relay", "Cache"],
                    CYAN)
                # Agent Coverage
                cron_up = sum(1 for v in d['cron'].values() if v)
                cron_total = max(len(d['cron']), 1)
                svc_up = sum(1 for v in d['svc'].values() if v)
                svc_total = max(len(d['svc']), 1)
                self._draw_radar(self.viz_extra_radars["Agent Coverage"],
                    [(cron_up / cron_total * 100, 100), (svc_up / svc_total * 100, 100),
                     (100 if hb < 300 else 15, 100), (min(fitness_v / 100, 100), 100),
                     (80, 100), (70, 100)],
                    ["Crons", "Svc", "Merid", "Fitness", "Relay", "Watch"],
                    TEAL)
            except Exception:
                pass

        # ── Creative view (counts + polar area) ──
        if hasattr(self, 'cur_view') and self.cur_view == "creative":
            self.cr_stats["Poems"].configure(text=str(p))
            self.cr_stats["Journals"].configure(text=str(j))
            self.cr_stats["CogCorp"].configure(text=str(cc))
            self.cr_stats["Games"].configure(text=str(games))
            try:
                cr_data = [p, j, cc, max(games, 1)]
                cr_labels = ["Poems", "Journals", "CogCorp", "Games"]
                cr_colors = ["#ab47bc", "#42a5f5", "#ef5350", "#4caf50"]
                self._draw_polar_area(self.viz_polar, cr_data, cr_labels, cr_colors)
            except Exception:
                pass

        # ── Links view ──
        if hasattr(self, 'cur_view') and self.cur_view == "links":
            le = d.get('last_edited', [])
            for i, (name_lbl, time_lbl, agent_lbl, pin_lbl, row) in enumerate(self.le_labels):
                if i < len(le):
                    bn, ago, fp = le[i]
                    ext = os.path.splitext(bn)[1]
                    ec = GREEN if ext == '.md' else CYAN if ext == '.py' else AMBER if ext == '.html' else DIM
                    name_lbl.configure(text=bn[:60], fg=ec)
                    time_lbl.configure(text=ago)
                    # Agent attribution dot
                    agent = guess_agent(bn)
                    if agent:
                        ac = AGENT_COLORS_MAP.get(agent, DIM)
                        agent_lbl.configure(text="\u25cf", fg=ac)
                    else:
                        agent_lbl.configure(text="\u25cb", fg=DIM)
                    # Pin indicator
                    is_pinned = fp in self._link_pinned
                    pin_lbl.configure(text="\u2605" if is_pinned else "\u2606", fg=GOLD if is_pinned else DIM)
                    # Click bindings for preview and pin
                    name_lbl.bind("<Button-1>", lambda e, p=fp: self._link_preview_file(p))
                    row.bind("<Button-1>", lambda e, p=fp: self._link_preview_file(p))
                    pin_lbl.bind("<Button-1>", lambda e, p=fp: (self._link_unpin_file(p) if p in self._link_pinned else self._link_pin_file(p)))
                else:
                    name_lbl.configure(text="")
                    time_lbl.configure(text="")
                    agent_lbl.configure(text="")
                    pin_lbl.configure(text="")

        # ── System view ──
        if hasattr(self, 'cur_view') and self.cur_view == "system":
            # Services
            all_svc = list(d['svc'].items()) + list(d['cron'].items())
            for name, up in all_svc:
                if name in self.sys_svc_labels:
                    sym = "\u25cf" if up else "\u25cb"
                    c = GREEN if up else RED
                    self.sys_svc_labels[name].configure(text=f"{sym} {name}", fg=c)
            if "Command Center" in self.sys_svc_labels:
                self.sys_svc_labels["Command Center"].configure(text="\u25cf Command Center (this)", fg=GREEN)

            # Resources
            lc = GREEN if st['load_v'] < 2 else AMBER if st['load_v'] < 4 else RED
            self.sys_res["Load Avg"].configure(text=st['load'], fg=lc)
            rc = GREEN if st['ram_p'] < 60 else AMBER if st['ram_p'] < 85 else RED
            self.sys_res["RAM Usage"].configure(text=st['ram'], fg=rc)
            dc = GREEN if st['disk_p'] < 60 else AMBER if st['disk_p'] < 80 else RED
            self.sys_res["Disk Usage"].configure(text=st['disk'], fg=dc)
            self.sys_res["Uptime"].configure(text=st['up'])
            imap_c = GREEN if d.get('imap_ok') else RED
            self.sys_res["IMAP Port"].configure(
                text="1144 OK" if d.get('imap_ok') else "1144 DOWN", fg=imap_c)

            # Wake state with color-coded sections + AWAKENING progress
            self._refresh_wake_viewer()

            # ── System Charts (gauges, radial, sparklines, step) ──
            try:
                svc = d['svc']
                cron = d['cron']
                svc_up = sum(1 for v in svc.values() if v)
                svc_total = max(len(svc), 1)
                cron_up = sum(1 for v in cron.values() if v)
                cron_total = max(len(cron), 1)
                cpu_health = max(0, 100 - st['load_v'] / 8.0 * 100)
                ram_health = max(0, 100 - st['ram_p'])
                disk_health = max(0, 100 - st['disk_p'])
                svc_health = svc_up / svc_total * 100
                agent_health = cron_up / cron_total * 100

                self._draw_arc_gauge(self.viz_gauge_cpu, st['load_v'], 8.0, "CPU LOAD", "auto", "cores")
                self._draw_arc_gauge(self.viz_gauge_ram, st['ram_p'], 100, "RAM", "auto", "%")
                self._draw_arc_gauge(self.viz_gauge_disk, st['disk_p'], 100, "DISK", "auto", "%")

                radial_data = [
                    (cpu_health, 100), (ram_health, 100), (disk_health, 100),
                    (svc_health, 100), (agent_health, 100),
                ]
                radial_labels = ["CPU", "RAM", "Disk", "Services", "Agents"]
                radial_colors = [GREEN, TEAL, AMBER, CYAN, PURPLE]
                self._draw_radial_bars(self.viz_radial, radial_data, radial_labels, radial_colors)

                if len(self._load_history) >= 2:
                    self._draw_sparkline(self.viz_sparks["CPU"], self._load_history, GREEN,
                                        max_val=8.0, current=f"{st['load']}", unit="cores")
                if len(self._ram_history) >= 2:
                    self._draw_sparkline(self.viz_sparks["RAM"], self._ram_history, TEAL,
                                        max_val=100.0, current=f"{st['ram_p']:.0f}%", unit="%")
                if len(self._disk_history) >= 2:
                    self._draw_sparkline(self.viz_sparks["Disk"], self._disk_history, AMBER,
                                        max_val=100.0, current=f"{st['disk_p']}%", unit="%")
                if len(self._msg_rate_history) >= 2:
                    self._draw_sparkline(self.viz_sparks["Msgs"], self._msg_rate_history, GOLD,
                                        max_val=max(max(self._msg_rate_history), 10),
                                        current=str(self._msg_rate_history[-1]), unit="msgs")
                if len(self._fitness_history) >= 2:
                    self._draw_step_line(self.viz_sparks["Fitness"], self._fitness_history,
                                        color=BLUE, max_val=10000, label="fitness")
                    self._draw_step_line(self.viz_step, self._fitness_history,
                                        color=BLUE, max_val=10000, label="Loop Fitness")
            except Exception:
                pass

            # Refresh process monitor, network, memory DB (every 5th update to save CPU)
            if not hasattr(self, '_sys_deep_counter'):
                self._sys_deep_counter = 0
            self._sys_deep_counter += 1
            if self._sys_deep_counter % 5 == 1:  # first time + every 5th
                self._refresh_processes()
                self._refresh_network()
                self._refresh_memdb()


if __name__ == "__main__":
    app = V16()
    app.mainloop()
