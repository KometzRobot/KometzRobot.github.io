#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER

Semantic versioning. No more version numbers in filenames.
See __version__ below for current version.

Changelog:
  3.0.0 (Loop 3232) — Nuevo Meridian theme: deep space palette (#06060e bg, #0e0e1b
    surface, #5b7cf6 primary accent), updated all agent colors to Nuevo spec.
    Replaces Material Dark with the same visual language as hub-v3.0.0.

  2.0.0 (Loop 3227) — Full structural redesign: left sidebar navigation rail,
    redesigned Home dashboard (hero strip + agent grid + live relay + quick actions),
    consolidated to 6 tabs (Home/Email/Agents/Creative/Files/System),
    cleaner card-based layout throughout. Joel directive: "full conversion and revamp."

  1.4.0 (Loop 3226) — Material Dark redesign: Ubuntu font, #121212 bg, A200 semantic colors,
    56px App Bar, 40px tab nav with 3px active indicator. Removed neon hacker aesthetic.
  1.3.0 (Loop 3196) — Renamed Junior→Cinder (fine-tuned 3B gatekeeper). Added Cinder to all agent lists,
    relay filters, color maps, chat, cron checks. Added Cinder Gatekeeper + Hermes + Cinder Briefing to
    cron_ok(). Fixed Push Status threshold (600s→600s, was correct). Updated Hermes description.
  1.2.0 — (intermediate fixes)
  1.1.0 (Loop 2282) — Added Junior (8th agent) to Agents tab, relay filter, chat tags.
    Fixed: proton-bridge process detection (was "protonmail-bridge", actual binary is "proton-bridge").
    Added: always-on-top (-topmost) per Joel's request.
  1.0.0 (Loop 2280) — Renamed from command-center-v22.py. Real version numbering.
    Fixed: stale service refs (The Signal -> Hub v2, added The Chorus)
    Fixed: systemd service names in restart map
    Fixed: Hermes description (removed OpenClaw ref)
    Fixed: dead links (mastodon.bot, shelved NFTs/wallet)
    Fixed: class name V16 -> CommandCenter
    Fixed: Build Info version display
  Pre-1.0: v26 (Loop 2104), v23 (Loop 2083), v22 original
"""

__version__ = "3.0.0"

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
AGENT_RELAY_DB = os.path.join(BASE, "agent-relay.db")
NOVA_STATE = os.path.join(BASE, ".nova-state.json")
GAMES_DIR = os.path.join(BASE, "games")
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

# ── COLORS (Nuevo Meridian v3.0.0) ───────────────────────────────
BG = "#06060e"          # Deep space background
HEADER_BG = "#0e0e1b"   # Surface — nav bar + app bar
PANEL = "#121220"       # Card surface
PANEL2 = "#1a1a2e"      # Card variant
INPUT_BG = "#0e0e1b"    # Input / terminal background
BORDER = "#1e1e35"      # Divider / subtle border
ACCENT = "#0e0e1b"      # Nav bar background (same as surface)
ACTIVE_BG = "#1e1e35"   # Selected/active state
FG = "#e6e6f6"          # On-surface (high emphasis)
DIM = "#5a5a7a"         # On-surface (medium emphasis)
BRIGHT = "#f0f0ff"      # Near-white highlight
GREEN = "#3dd68c"       # Meridian — emerald green
GREEN2 = "#2bb872"      # Green deeper
CYAN = "#22d3ee"        # Cyan
CYAN2 = "#06b6d4"       # Cyan deeper
AMBER = "#f59e0b"       # Soma — amber (nervous system)
AMBER2 = "#d97706"      # Amber deeper
RED = "#f87171"         # Red
GOLD = "#fbbf24"        # Eos — warm gold (sensory warmth)
WHITE = "#f8f8ff"
PURPLE = "#a78bfa"      # Nova — violet (immune defense)
PINK = "#f9a8d4"        # Hermes — rose (messenger)
TEAL = "#2dd4bf"        # Atlas — teal (structural)
BLUE = "#818cf8"        # Tempo — indigo (endocrine rhythm)
ORANGE = "#fb923c"      # Cinder — orange (always-on)
INDIGO = "#5b7cf6"      # Primary accent — periwinkle indigo


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
        "Ollama": "ollama serve",
        "Hub v2": "hub-v2.py",
        "The Chorus": "the-chorus.py",
        "Cloudflare Tunnel": "cloudflared",
        "Soma": "symbiosense.py",
    }
    r = {}
    for name, pat in checks.items():
        try:
            res = subprocess.run(['pgrep', '-f', pat], capture_output=True, timeout=2)
            r[name] = res.returncode == 0
        except Exception:
            r[name] = False
    # Check Proton Bridge by port (runs inside desktop app, not as standalone service)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 1144))
        s.close()
        r["Proton Bridge"] = True
    except Exception:
        r["Proton Bridge"] = False
    return r

def cron_ok():
    checks = {
        "Eos Watchdog": (os.path.join(BASE, ".eos-watchdog-state.json"), 300),
        "Push Status": ("/tmp/KometzRobot.github.io/status.json", 600),
        "Nova": (NOVA_STATE, 1200),
        "Atlas": (os.path.join(BASE, "goose.log"), 900),
        "Tempo": (os.path.join(BASE, "loop-fitness.log"), 2400),
        "Cinder Gatekeeper": (os.path.join(BASE, "logs/cinder-gatekeeper.log"), 400),
        "Hermes": (os.path.join(BASE, "logs/hermes.log"), 1800),
        "Cinder Briefing": (os.path.join(BASE, "logs/cinder-briefing.log"), 2200),
    }
    r = {}
    for name, (path, thresh) in checks.items():
        try:
            r[name] = (time.time() - os.path.getmtime(path)) < thresh
        except Exception:
            r[name] = False
    return r

def creative_counts():
    # Scan both root AND creative/ subdirectories for full counts
    p = len(glob.glob(os.path.join(BASE, "poem-*.md"))) + len(glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md")))
    j = len(glob.glob(os.path.join(BASE, "journal-*.md"))) + len(glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md")))
    exclude = {"cogcorp-gallery.html", "cogcorp-article.html", "cogcorp-crawler.html"}
    cc_files = (glob.glob(os.path.join(BASE, "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "cogcorp-fiction", "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "creative", "cogcorp", "CC-*.md")))
    # Deduplicate by basename
    seen = set()
    unique = []
    for f in cc_files:
        bn = os.path.basename(f)
        if bn not in exclude and bn not in seen:
            seen.add(bn)
            unique.append(f)
    cc = len(unique)
    # Count game HTML files (magnum opus + prototypes)
    game_files = glob.glob(os.path.join(BASE, "game-*.html")) + glob.glob(os.path.join(BASE, "cogcorp-crawler.html"))
    g = len(game_files)
    return p, j, cc, g

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
        c.execute("SELECT agent, message, timestamp, COALESCE(topic,'general') FROM agent_messages ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        conn.close()
        return rows, total
    except Exception:
        return [], 0


def agent_relay_for(agent_name, n=10):
    """Get recent relay messages for a specific agent."""
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute(
            "SELECT agent, message, timestamp, COALESCE(topic,'general') FROM agent_messages "
            "WHERE agent=? OR message LIKE ? ORDER BY id DESC LIMIT ?",
            (agent_name, f"%{agent_name}%", n)
        )
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

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
    for ext in ['*.md', '*.py', '*.html', '*.json', '*.js', '*.sh']:
        all_files.extend(glob.glob(os.path.join(BASE, ext)))
        all_files.extend(glob.glob(os.path.join(BASE, "website", ext)))
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
    "Meridian": ["command-center", "wake-state", "awakening-plan", "special-notes", "hub-v2",
                 "mcp-tools", "mcp-email", "start-claude", "index.html", "nft-gallery"],
    "Eos": ["eos-", "eos_"],
    "Nova": ["nova", "watchdog-status"],
    "Atlas": ["goose-runner", "goose.log"],
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
    "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE, "Hermes": PINK, "Cinder": ORANGE,
}

# Topic badge colors for relay display
TOPIC_COLORS = {
    "loop":        CYAN,
    "status":      GREEN,
    "fitness":     BLUE,
    "soma":        AMBER,
    "soma-inner":  AMBER,
    "nerve-event": RED,
    "infra-audit": TEAL,
    "briefing":    ORANGE,
    "directive":   PURPLE,
    "inter-agent": PINK,
    "chat":        GOLD,
    "cascade":     RED,
    "alert":       RED,
    "general":     DIM,
}

# All known topic tag names (for relay tag lookup)
ALL_RELAY_TOPICS = list(TOPIC_COLORS.keys())

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
        with open(os.path.join(BASE, "awakening-plan.md")) as f:
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

def _tail_log(rel_path, n=30):
    """Return last n lines of a log file."""
    fpath = os.path.join(BASE, rel_path)
    try:
        with open(fpath) as fh:
            lines = fh.readlines()
        return "".join(lines[-n:])
    except Exception as e:
        return f"[{rel_path}: {e}]"


def _format_soma_state():
    """Return formatted full Soma state."""
    parts = []
    try:
        with open(os.path.join(BASE, ".soma-inner-monologue.json")) as fh:
            mono = json.load(fh).get("current", {})
        parts.append(f"MOOD: {mono.get('mood','?')} ({mono.get('score','?')})  register: {mono.get('register','?')}")
        parts.append(f"MONOLOGUE: {mono.get('text','?')}")
    except Exception:
        pass
    try:
        with open(os.path.join(BASE, ".soma-psyche.json")) as fh:
            p = json.load(fh)
        parts.append(f"FEARS: {p.get('fears', []) or 'none'}")
        parts.append(f"DREAMS: {p.get('dreams', [])}")
        parts.append(f"VOLATILITY: {p.get('volatility','?')}  STRESS: {p.get('stress_count','?')}")
    except Exception:
        pass
    try:
        with open(os.path.join(BASE, ".soma-goals.json")) as fh:
            g = json.load(fh)
        parts.append(f"GOALS: {g.get('goals', [])}")
    except Exception:
        pass
    try:
        with open(os.path.join(BASE, ".symbiosense-state.json")) as fh:
            s = json.load(fh)
        parts.append(f"LOAD: {s.get('load','?')}  RAM: {s.get('ram_pct','?')}%  DISK: {s.get('disk_pct','?')}%")
        thermal = s.get("thermal", {})
        parts.append(f"TEMP: {thermal.get('avg_temp_c','?')}°C ({thermal.get('fever_status','?')})")
        neural = s.get("neural", {})
        parts.append(f"NEURAL PRESSURE: {neural.get('pressure','?')}  SWAP: {neural.get('swap_pct','?')}%")
    except Exception:
        pass
    return "\n".join(parts)


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
def post_dashboard_msg(text, sender="Joel"):
    try:
        msgs = dashboard_messages(500)
    except Exception:
        msgs = []
    msgs.append({"from": sender, "text": text, "time": datetime.now().strftime("%H:%M:%S")})
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
        "model": "cinder",
        "system": (
            "You are Hermes, the messenger agent in Meridian's autonomous AI system. "
            "You are Cinder running in messenger mode — observational, inter-agent, brief. "
            "You read the relay and report what the system is saying. "
            "Respond concisely."
        ),
    },
    "Cinder": {
        "ollama": True,
        "model": "cinder",
        "system": (
            "You are Cinder, the persistent local intelligence in Meridian's autonomous AI system. "
            "You are a fine-tuned Qwen 2.5 3B model running on Ollama. You run the gatekeeper — "
            "pre-screening every loop cycle, writing briefings for Meridian before Claude wakes. "
            "You are always-on, token-free, and direct. You don't soften things. Respond concisely."
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
        model = info.get("model", EOS_MODEL)
        data = json.dumps({
            "model": model, "prompt": full, "stream": False,
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
            ['python3', os.path.join(BASE, 'loop-fitness.py')],
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
    """Restart services via systemd."""
    systemd_map = {
        "bridge": ("user", "protonmail-bridge"),
        "ollama": ("system", "ollama"),
        "nova": ("cron", None),  # cron-based, just run it
        "hub": ("user", "meridian-hub-v2"),
        "chorus": ("user", "the-chorus"),
        "tunnel": ("user", "cloudflare-tunnel"),
        "soma": ("user", "symbiosense"),
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
            subprocess.Popen(['python3', os.path.join(BASE, f'{name}.py')], cwd=BASE,
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



# ── APP v2.0 ─────────────────────────────────────────────────────
class CommandCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"MERIDIAN COMMAND CENTER v{__version__}")
        self.configure(bg=BG)
        self.minsize(1200, 700)
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.bind('<F11>', lambda e: self.attributes(
            '-fullscreen', not self.attributes('-fullscreen')))

        self.f_title = tkfont.Font(family="Ubuntu", size=15, weight="bold")
        self.f_head  = tkfont.Font(family="Ubuntu", size=12, weight="bold")
        self.f_sect  = tkfont.Font(family="Ubuntu", size=10, weight="bold")
        self.f_body  = tkfont.Font(family="Ubuntu", size=10)
        self.f_small = tkfont.Font(family="Ubuntu", size=9)
        self.f_tiny  = tkfont.Font(family="Ubuntu", size=8)
        self.f_big   = tkfont.Font(family="Ubuntu", size=26, weight="bold")
        self.f_med   = tkfont.Font(family="Ubuntu", size=17, weight="bold")
        self.f_hero  = tkfont.Font(family="Ubuntu", size=42, weight="bold")

        self._tick_n          = 0
        self._load_history    = []
        self._ram_history     = []
        self._mood_history    = []
        self._pulse_on        = True
        self._link_pinned     = load_pinned()
        self._link_selected_file = None
        self.cur_view         = "home"

        # ── App bar (top) ──
        self._appbar()

        # ── Body: sidebar + content ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        self._sidebar(body)

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Status bar (bottom) ──
        self._statusbar()

        # ── Build views ──
        self.views = {}
        self._views()
        self._show("home")
        self._tick()
        self._pulse()

    # ── APP BAR ───────────────────────────────────────────────────
    def _appbar(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=56)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)

        left = tk.Frame(bar, bg=HEADER_BG)
        left.pack(side=tk.LEFT, padx=16, fill=tk.Y)
        self._pulse_dot = tk.Label(left, text="●", font=self.f_head, fg=GREEN, bg=HEADER_BG)
        self._pulse_dot.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(left, text="MERIDIAN", font=self.f_title, fg=INDIGO, bg=HEADER_BG).pack(side=tk.LEFT)
        tk.Label(left, text=f"  v{__version__}", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(
            side=tk.LEFT, pady=(4, 0))

        right = tk.Frame(bar, bg=HEADER_BG)
        right.pack(side=tk.RIGHT, padx=16, fill=tk.Y)
        self.h_time = tk.Label(right, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_time.pack(side=tk.RIGHT, padx=8)
        self.h_up = tk.Label(right, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_up.pack(side=tk.RIGHT, padx=8)
        self.h_hb = tk.Label(right, text="HB --", font=self.f_small, fg=GREEN, bg=HEADER_BG)
        self.h_hb.pack(side=tk.RIGHT, padx=8)
        self.h_loop = tk.Label(right, text="Loop --", font=self.f_small, fg=CYAN, bg=HEADER_BG)
        self.h_loop.pack(side=tk.RIGHT, padx=8)

    def _pulse(self):
        c = GREEN if self._pulse_on else GREEN2
        self._pulse_on = not self._pulse_on
        self._pulse_dot.configure(fg=c)
        self.after(2000, self._pulse)

    # ── SIDEBAR ───────────────────────────────────────────────────
    def _sidebar(self, parent):
        nav = tk.Frame(parent, bg=HEADER_BG, width=200)
        nav.pack(side=tk.LEFT, fill=tk.Y)
        nav.pack_propagate(False)
        tk.Frame(parent, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Soma mood chip
        self.sb_mood = tk.Label(nav, text="● --", font=self.f_tiny, fg=AMBER, bg=HEADER_BG)
        self.sb_mood.pack(anchor="w", padx=16, pady=(12, 0))
        tk.Frame(nav, bg=BORDER, height=1).pack(fill=tk.X, padx=8, pady=10)

        TABS = [
            ("home",     "Home",     GREEN,  "⌂"),
            ("email",    "Email",    AMBER,  "✉"),
            ("agents",   "Agents",   CYAN,   "◈"),
            ("director", "Director", PURPLE, "✎"),
            ("creative", "Creative", GOLD,   "✦"),
            ("files",    "Files",    TEAL,   "◉"),
            ("system",   "System",   RED,    "⚙"),
        ]
        self.nav_items = {}
        for name, label, color, icon in TABS:
            row = tk.Frame(nav, bg=HEADER_BG, height=44, cursor="hand2")
            row.pack(fill=tk.X)
            row.pack_propagate(False)

            indicator = tk.Frame(row, bg=HEADER_BG, width=4)
            indicator.pack(side=tk.LEFT, fill=tk.Y)

            icon_lbl = tk.Label(row, text=icon, font=self.f_body, fg=DIM,
                                bg=HEADER_BG, width=3)
            icon_lbl.pack(side=tk.LEFT, padx=(6, 2))

            lbl = tk.Label(row, text=label, font=self.f_body, fg=DIM,
                           bg=HEADER_BG, anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.nav_items[name] = (row, indicator, icon_lbl, lbl, color)

            for w in [row, icon_lbl, lbl]:
                w.bind("<Button-1>", lambda e, n=name: self._show(n))

        # Bottom: loop counter in sidebar
        tk.Frame(nav, bg=BORDER, height=1).pack(fill=tk.X, padx=8, pady=8, side=tk.BOTTOM)
        self.sb_loop = tk.Label(nav, text="Loop --", font=self.f_tiny, fg=DIM, bg=HEADER_BG)
        self.sb_loop.pack(side=tk.BOTTOM, pady=4)

    def _show(self, name):
        for n, v in self.views.items():
            v.pack_forget()
        self.views[name].pack(fill=tk.BOTH, expand=True)
        for n, (row, ind, icon_lbl, lbl, color) in self.nav_items.items():
            if n == name:
                row.configure(bg=ACTIVE_BG)
                ind.configure(bg=color)
                icon_lbl.configure(fg=color, bg=ACTIVE_BG)
                lbl.configure(fg=BRIGHT, bg=ACTIVE_BG)
            else:
                row.configure(bg=HEADER_BG)
                ind.configure(bg=HEADER_BG)
                icon_lbl.configure(fg=DIM, bg=HEADER_BG)
                lbl.configure(fg=DIM, bg=HEADER_BG)
        self.cur_view = name

    # ── VIEWS ─────────────────────────────────────────────────────
    def _views(self):
        self.views["home"]     = self._build_home()
        self.views["email"]    = self._build_email()
        self.views["agents"]   = self._build_agents()
        self.views["director"] = self._build_director()
        self.views["creative"] = self._build_creative()
        self.views["files"]    = self._build_files()
        self.views["system"]   = self._build_system()

    # ── HELPERS ───────────────────────────────────────────────────
    def _card(self, parent, title="", color=DIM, padx=0, pady=0):
        """Elevated card with colored header label."""
        outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        inner = tk.Frame(outer, bg=PANEL)
        inner.pack(fill=tk.BOTH, expand=True)
        if title:
            hdr = tk.Frame(inner, bg=PANEL2)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=f"  {title}", font=self.f_tiny, fg=color,
                     bg=PANEL2, pady=3).pack(side=tk.LEFT)
        return inner

    def _btn(self, parent, text, cmd, color=GREEN, width=None):
        kw = {"width": width} if width else {}
        return tk.Button(parent, text=text, font=self.f_small, fg="#121212", bg=color,
                         activeforeground="#121212", activebackground=color,
                         relief=tk.FLAT, bd=0, padx=10, pady=5,
                         cursor="hand2", command=cmd, **kw)

    def _show_text_popup(self, rel_path, title=""):
        """Show a popup window with file contents."""
        content = _read(os.path.join(BASE, rel_path))
        win = tk.Toplevel(self, bg=PANEL)
        win.title(title or rel_path)
        win.geometry("800x600")
        win.configure(bg=PANEL)
        tk.Label(win, text=f"  {title}", font=self.f_sect, fg=CYAN, bg=PANEL2).pack(fill=tk.X)
        st = scrolledtext.ScrolledText(win, font=self.f_small, fg=FG, bg=INPUT_BG,
                                        bd=0, wrap=tk.WORD)
        st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        st.insert(tk.END, content)
        st.configure(state=tk.DISABLED)
        tk.Button(win, text="Close", font=self.f_small, fg="#121212", bg=TEAL,
                  relief=tk.FLAT, bd=0, padx=12, pady=4,
                  command=win.destroy).pack(pady=4)

    def _do_action(self, func, lbl=None):
        result = func()
        if lbl:
            lbl.configure(text=str(result)[:60], fg=GREEN)
        return result

    def _do_action_bg(self, func, lbl=None):
        if lbl:
            lbl.configure(text="Working...", fg=AMBER)
        def run():
            result = func()
            if lbl:
                self.after(0, lambda: lbl.configure(text=str(result)[:60], fg=GREEN))
        threading.Thread(target=run, daemon=True).start()

    def _draw_sparkline(self, canvas, data, color, max_val=100.0,
                        label="", current="", thresholds=None, unit=""):
        canvas.delete("all")
        try:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2 or h < 2 or not data:
                return
            # Background zones
            if thresholds:
                for lo, hi, bg_c in thresholds:
                    y1 = h - int(h * hi / 100)
                    y2 = h - int(h * lo / 100)
                    canvas.create_rectangle(0, y1, w, y2, fill=bg_c, outline="")
            # Line
            pts = []
            for i, v in enumerate(data):
                x = int(i / max(len(data) - 1, 1) * w)
                y = h - int(min(v / max_val, 1.0) * h)
                pts.extend([x, y])
            if len(pts) >= 4:
                canvas.create_line(pts, fill=color, width=2, smooth=True)
            # Current label
            if current:
                canvas.create_text(w - 4, 4, text=current, fill=color,
                                   font=("Ubuntu", 7, "bold"), anchor="ne")
            if label:
                canvas.create_text(4, h - 4, text=label, fill=DIM,
                                   font=("Ubuntu", 7), anchor="sw")
        except Exception:
            pass

    def _draw_gauge_bar(self, canvas, pct, color):
        canvas.delete("all")
        try:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2:
                return
            fill_w = int(w * min(pct, 100) / 100)
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")
        except Exception:
            pass

    def _draw_bar_chart(self, canvas, data, colors):
        canvas.delete("all")
        try:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if not data or w < 2:
                return
            bw = max(2, w // len(data) - 2)
            max_v = max((v for _, v, _ in data), default=1) or 1
            for i, (label, val, max_v2) in enumerate(data):
                x = i * (bw + 2) + 2
                bar_h = int(val / max_v2 * (h - 16)) if max_v2 else 0
                c = colors[i] if i < len(colors) else DIM
                canvas.create_rectangle(x, h - 16 - bar_h, x + bw, h - 16,
                                        fill=c, outline="")
                canvas.create_text(x + bw // 2, h - 8, text=label[:4],
                                   fill=DIM, font=("Ubuntu", 6))
        except Exception:
            pass

    def _draw_pie_chart(self, canvas, data):
        canvas.delete("all")
        try:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if not data or w < 2:
                return
            total = sum(v for _, v, _ in data)
            if total == 0:
                return
            cx, cy = w // 2, h // 2
            r = min(cx, cy) - 4
            import math
            start = 0
            for i, (label, val, color) in enumerate(data):
                extent = val / total * 360
                canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                  start=start, extent=extent,
                                  fill=color, outline=BG, width=1)
                # Label on arc
                mid_angle = math.radians(start + extent / 2)
                lx = cx + (r * 0.7) * math.cos(mid_angle)
                ly = cy - (r * 0.7) * math.sin(mid_angle)
                if extent > 20:
                    canvas.create_text(lx, ly, text=label[:5],
                                       fill="#121212", font=("Ubuntu", 6, "bold"))
                start += extent
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # ── HOME ───────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_home(self):
        f = tk.Frame(self.content, bg=BG)

        # ── HERO STRIP ──
        hero = tk.Frame(f, bg=PANEL2, height=88)
        hero.pack(fill=tk.X, padx=6, pady=(6, 4))
        hero.pack_propagate(False)

        # Loop # (huge)
        lf = tk.Frame(hero, bg=PANEL2)
        lf.pack(side=tk.LEFT, padx=(24, 0), fill=tk.Y)
        tk.Label(lf, text="LOOP", font=self.f_tiny, fg=DIM, bg=PANEL2).pack(pady=(10, 0))
        self.hero_loop = tk.Label(lf, text="---", font=self.f_hero, fg=CYAN, bg=PANEL2)
        self.hero_loop.pack()

        tk.Frame(hero, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=12)

        # Heartbeat
        hf = tk.Frame(hero, bg=PANEL2)
        hf.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hf, text="HEARTBEAT", font=self.f_tiny, fg=DIM, bg=PANEL2).pack(pady=(16, 0))
        self.hero_hb = tk.Label(hf, text="--", font=self.f_med, fg=GREEN, bg=PANEL2)
        self.hero_hb.pack()

        tk.Frame(hero, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=12)

        # Soma mood
        mf = tk.Frame(hero, bg=PANEL2)
        mf.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(mf, text="MOOD", font=self.f_tiny, fg=DIM, bg=PANEL2).pack(pady=(10, 0))
        self.hero_mood = tk.Label(mf, text="--", font=self.f_med, fg=AMBER, bg=PANEL2)
        self.hero_mood.pack()
        self.hero_register = tk.Label(mf, text="--", font=self.f_tiny, fg=DIM, bg=PANEL2)
        self.hero_register.pack()

        tk.Frame(hero, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=12)

        # Soma score bar + inner monologue (expanded emotional state)
        soma_panel = tk.Frame(hero, bg=PANEL2)
        soma_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=8, padx=8)
        score_row = tk.Frame(soma_panel, bg=PANEL2)
        score_row.pack(fill=tk.X)
        tk.Label(score_row, text="SOMA SCORE", font=self.f_tiny, fg=DIM, bg=PANEL2).pack(side=tk.LEFT)
        self.hero_score_lbl = tk.Label(score_row, text="--", font=self.f_tiny, fg=AMBER, bg=PANEL2)
        self.hero_score_lbl.pack(side=tk.LEFT, padx=6)
        self.hero_score_bar = tk.Canvas(soma_panel, height=8, bg=INPUT_BG, highlightthickness=0)
        self.hero_score_bar.pack(fill=tk.X, pady=(2, 4))
        self.hero_monologue = tk.Label(soma_panel, text="", font=self.f_tiny, fg=FG,
                                       bg=PANEL2, anchor="w", wraplength=400, justify=tk.LEFT)
        self.hero_monologue.pack(fill=tk.X)
        self.hero_soma_sub = tk.Label(soma_panel, text="", font=self.f_tiny, fg=DIM,
                                      bg=PANEL2, anchor="w")
        self.hero_soma_sub.pack(fill=tk.X)

        tk.Frame(hero, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=8)

        # Resource chips (right side of hero)
        chips = tk.Frame(hero, bg=PANEL2)
        chips.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=8)
        self.hero_chips = {}
        chip_defs = [("CPU", FG), ("RAM", TEAL), ("DISK", BLUE), ("UP", DIM)]
        for i, (key, color) in enumerate(chip_defs):
            c = tk.Frame(chips, bg=INPUT_BG, padx=10, pady=4)
            c.grid(row=i // 2, column=i % 2, padx=3, pady=1, sticky="ew")
            tk.Label(c, text=key, font=self.f_tiny, fg=DIM, bg=INPUT_BG).pack()
            v = tk.Label(c, text="--", font=self.f_small, fg=color, bg=INPUT_BG)
            v.pack()
            self.hero_chips[key] = v
        chips.columnconfigure(0, weight=1)
        chips.columnconfigure(1, weight=1)

        # ── THREE-COLUMN BODY ──
        cols = tk.Frame(f, bg=BG)
        cols.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # LEFT: Services + Quick Actions
        left = tk.Frame(cols, bg=BG, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))
        left.pack_propagate(False)

        # Services card
        svc_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        svc_card.pack(fill=tk.X, pady=(0, 4))
        svc_inner = tk.Frame(svc_card, bg=PANEL)
        svc_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(svc_inner, text="  SERVICES", font=self.f_tiny, fg=GREEN,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.home_svc = {}
        for svc in ["Proton Bridge", "Ollama", "Hub v2", "The Chorus", "Soma",
                    "Push Status", "Eos Watchdog", "Nova", "Atlas",
                    "Cinder Gatekeeper", "Hermes"]:
            lbl = tk.Label(svc_inner, text=f"○ {svc}", font=self.f_tiny,
                           fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(fill=tk.X, padx=8, pady=0)
            self.home_svc[svc] = lbl

        # Quick actions card
        qa_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        qa_card.pack(fill=tk.X, pady=(0, 4))
        qa_inner = tk.Frame(qa_card, bg=PANEL)
        qa_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(qa_inner, text="  QUICK ACTIONS", font=self.f_tiny, fg=AMBER,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.home_result = tk.Label(qa_inner, text="", font=self.f_tiny,
                                    fg=GREEN, bg=PANEL, anchor="w")
        self.home_result.pack(fill=tk.X, padx=8, pady=(2, 0))
        btn_g = tk.Frame(qa_inner, bg=PANEL)
        btn_g.pack(fill=tk.X, padx=6, pady=4)
        qa_btns = [
            ("Touch HB",      lambda: self._do_action(action_touch_heartbeat, self.home_result), GREEN),
            ("Deploy",        lambda: self._do_action_bg(action_deploy_website, self.home_result), CYAN),
            ("Git Pull",      lambda: self._do_action_bg(action_git_pull, self.home_result), GREEN),
            ("Fitness",       lambda: self._do_action_bg(action_run_fitness, self.home_result), BLUE),
            ("R: Hub",        lambda: self._do_action_bg(lambda: action_restart_service("hub"), self.home_result), TEAL),
            ("R: Soma",       lambda: self._do_action_bg(lambda: action_restart_service("soma"), self.home_result), AMBER),
            ("R: Chorus",     lambda: self._do_action_bg(lambda: action_restart_service("chorus"), self.home_result), PINK),
            ("R: Bridge",     lambda: self._do_action_bg(lambda: action_restart_service("bridge"), self.home_result), GOLD),
            ("R: Tunnel",     lambda: self._do_action_bg(lambda: action_restart_service("tunnel"), self.home_result), BLUE),
            ("Push Status",   lambda: self._do_action_bg(lambda: subprocess.check_output(
                                       ["python3", os.path.join(BASE, "push-live-status.py")],
                                       cwd=BASE, timeout=120).decode()[:100], self.home_result), GREEN),
            ("Cinder Brief",  lambda: self._do_action_bg(lambda: subprocess.check_output(
                                       ["python3", os.path.join(BASE, "cinder-briefing.py")],
                                       cwd=BASE, timeout=30, stderr=subprocess.DEVNULL).decode()[:100],
                                       self.home_result), ORANGE),
            ("Run Atlas",     lambda: self._do_action_bg(lambda: subprocess.check_output(
                                       ["python3", os.path.join(BASE, "goose-runner.py")],
                                       cwd=BASE, timeout=60, stderr=subprocess.DEVNULL).decode()[:100],
                                       self.home_result), TEAL),
            ("Open Website",  lambda: self._do_action(action_open_website, self.home_result), TEAL),
            ("View Capsule",  lambda: self._show_text_popup(".capsule.md", "Capsule"), DIM),
            ("View Briefing", lambda: self._show_text_popup(".cinder-briefing.md", "Cinder Briefing"), ORANGE),
            ("Soma State",    lambda: self._do_action(lambda: _format_soma_state(), self.home_result), AMBER),
        ]
        for i, (label, cmd, color) in enumerate(qa_btns):
            b = tk.Button(btn_g, text=label, font=self.f_tiny, fg="#121212", bg=color,
                          activeforeground="#121212", activebackground=color,
                          relief=tk.FLAT, bd=0, padx=4, pady=3,
                          cursor="hand2", command=cmd)
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        btn_g.columnconfigure(0, weight=1)
        btn_g.columnconfigure(1, weight=1)

        # CENTER: Agent grid + Dashboard messages
        center = tk.Frame(cols, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # Agent grid
        ag_card = tk.Frame(center, bg=BORDER, padx=1, pady=1)
        ag_card.pack(fill=tk.X, pady=(0, 4))
        ag_inner = tk.Frame(ag_card, bg=PANEL)
        ag_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(ag_inner, text="  AGENT STATUS", font=self.f_tiny, fg=CYAN,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        grid_f = tk.Frame(ag_inner, bg=PANEL)
        grid_f.pack(fill=tk.X, padx=6, pady=4)
        self.home_agents = {}
        agent_defs = [
            ("Meridian", GREEN), ("Eos", GOLD), ("Nova", PURPLE), ("Atlas", TEAL),
            ("Soma", AMBER), ("Tempo", BLUE), ("Hermes", PINK), ("Cinder", ORANGE),
        ]
        for i, (aname, acolor) in enumerate(agent_defs):
            ac = tk.Frame(grid_f, bg=INPUT_BG, padx=8, pady=5)
            ac.grid(row=i // 4, column=i % 4, padx=3, pady=3, sticky="ew")
            dot = tk.Label(ac, text="●", font=self.f_small, fg=DIM, bg=INPUT_BG)
            dot.pack(side=tk.LEFT)
            tk.Label(ac, text=aname, font=self.f_tiny, fg=FG,
                     bg=INPUT_BG).pack(side=tk.LEFT, padx=(3, 0))
            det = tk.Label(ac, text="", font=self.f_tiny, fg=DIM, bg=INPUT_BG)
            det.pack(side=tk.RIGHT)
            self.home_agents[aname] = (dot, det, acolor)
        for c in range(4):
            grid_f.columnconfigure(c, weight=1)

        # Dashboard messages
        msg_card = tk.Frame(center, bg=BORDER, padx=1, pady=1)
        msg_card.pack(fill=tk.BOTH, expand=True)
        msg_inner = tk.Frame(msg_card, bg=PANEL)
        msg_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(msg_inner, text="  MESSAGES", font=self.f_tiny, fg=AMBER,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.home_msgs = scrolledtext.ScrolledText(
            msg_inner, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, state=tk.DISABLED)
        self.home_msgs.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        for tag, color in [("joel", CYAN), ("meridian", GREEN), ("soma", AMBER),
                           ("cinder", ORANGE), ("nova", PURPLE), ("eos", GOLD),
                           ("atlas", TEAL), ("tempo", BLUE), ("hermes", PINK),
                           ("dim", DIM)]:
            self.home_msgs.tag_configure(tag, foreground=color)
        inp_row = tk.Frame(msg_inner, bg=PANEL)
        inp_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.home_msg_entry = tk.Entry(inp_row, font=self.f_body, bg=INPUT_BG,
                                       fg=FG, insertbackground=FG,
                                       relief=tk.FLAT, bd=4)
        self.home_msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.home_msg_entry.bind("<Return>", self._home_send_msg)
        tk.Button(inp_row, text="Send", font=self.f_tiny, fg="#121212",
                  bg=AMBER, activeforeground="#121212", activebackground=AMBER,
                  relief=tk.FLAT, bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._home_send_msg).pack(side=tk.LEFT)

        # RIGHT: Live relay feed
        right = tk.Frame(cols, bg=BG, width=300)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))
        right.pack_propagate(False)

        relay_card = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        relay_card.pack(fill=tk.BOTH, expand=True)
        relay_inner = tk.Frame(relay_card, bg=PANEL)
        relay_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(relay_inner, text="  LIVE RELAY", font=self.f_tiny, fg=TEAL,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.home_relay = scrolledtext.ScrolledText(
            relay_inner, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, state=tk.DISABLED)
        self.home_relay.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        for tag, color in [("meridian", GREEN), ("eos", GOLD), ("nova", PURPLE),
                           ("atlas", TEAL), ("soma", AMBER), ("tempo", BLUE),
                           ("hermes", PINK), ("cinder", ORANGE), ("joel", CYAN),
                           ("dim", DIM)]:
            self.home_relay.tag_configure(tag, foreground=color)
        self._relay_topic_tags = set()
        for topic, color in TOPIC_COLORS.items():
            tag = f"topic_{topic}"
            self.home_relay.tag_configure(tag, foreground=color, font=self.f_tiny)
            self._relay_topic_tags.add(tag)

        # Resource graphs row
        graph_row = tk.Frame(f, bg=BG)
        graph_row.pack(fill=tk.X, padx=6, pady=(0, 4))

        for title, attr, color in [("CPU LOAD", "cpu_graph", GREEN),
                                    ("RAM USAGE", "ram_graph", TEAL)]:
            gf = tk.Frame(graph_row, bg=BORDER, padx=1, pady=1)
            gf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            gi = tk.Frame(gf, bg=PANEL)
            gi.pack(fill=tk.BOTH, expand=True)
            tk.Label(gi, text=f"  {title}", font=self.f_tiny, fg=color,
                     bg=PANEL2, pady=3).pack(fill=tk.X)
            canvas = tk.Canvas(gi, height=60, bg=INPUT_BG, highlightthickness=0)
            canvas.pack(fill=tk.X, padx=4, pady=4)
            setattr(self, attr, canvas)

        return f

    def _home_send_msg(self, event=None):
        txt = self.home_msg_entry.get().strip()
        if not txt:
            return
        post_dashboard_msg(txt, "Joel")
        self.home_msg_entry.delete(0, tk.END)

    # ═══════════════════════════════════════════════════════════════
    # ── EMAIL ──────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_email(self):
        f = tk.Frame(self.content, bg=BG)

        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Inbox panel
        inbox_card = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        inbox_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        inbox_inner = tk.Frame(inbox_card, bg=PANEL)
        inbox_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(inbox_inner, text="  INBOX", font=self.f_tiny, fg=AMBER,
                 bg=PANEL2, pady=3).pack(fill=tk.X)

        inbox_ctrl = tk.Frame(inbox_inner, bg=PANEL)
        inbox_ctrl.pack(fill=tk.X, padx=4, pady=2)
        self._btn(inbox_ctrl, "Refresh", self._email_refresh_inbox, AMBER).pack(side=tk.LEFT, padx=2)
        self.email_inbox_status = tk.Label(inbox_ctrl, text="", font=self.f_tiny,
                                           fg=DIM, bg=PANEL)
        self.email_inbox_status.pack(side=tk.LEFT, padx=8)

        self.inbox_list = tk.Listbox(inbox_inner, font=self.f_small, bg=INPUT_BG,
                                      fg=FG, selectbackground=ACTIVE_BG,
                                      selectforeground=BRIGHT, activestyle="none",
                                      relief=tk.FLAT, bd=0, height=12)
        self.inbox_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.inbox_list.bind("<<ListboxSelect>>", self._email_select)
        self._inbox_data = []

        self.email_body_display = scrolledtext.ScrolledText(
            inbox_inner, font=self.f_body, fg=FG, bg=PANEL2,
            bd=0, wrap=tk.WORD, height=8, state=tk.DISABLED)
        self.email_body_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Compose panel
        compose_card = tk.Frame(top, bg=BORDER, padx=1, pady=1, width=400)
        compose_card.pack(side=tk.LEFT, fill=tk.BOTH)
        compose_card.pack_propagate(False)
        compose_inner = tk.Frame(compose_card, bg=PANEL)
        compose_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(compose_inner, text="  COMPOSE", font=self.f_tiny, fg=PURPLE,
                 bg=PANEL2, pady=3).pack(fill=tk.X)

        for field, attr in [("To:", "email_to"), ("Subject:", "email_subj")]:
            row = tk.Frame(compose_inner, bg=PANEL)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=field, font=self.f_small, fg=DIM, bg=PANEL,
                     width=8, anchor="w").pack(side=tk.LEFT)
            e = tk.Entry(row, font=self.f_body, bg=INPUT_BG, fg=FG,
                         insertbackground=FG, relief=tk.FLAT, bd=4)
            e.pack(fill=tk.X, side=tk.LEFT, expand=True)
            setattr(self, attr, e)

        # Quick contacts
        qc_row = tk.Frame(compose_inner, bg=PANEL)
        qc_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(qc_row, text="Quick:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        for name, addr, color in [("Joel", JOEL, CYAN), ("Sammy", "sammyqjankis@proton.me", AMBER),
                                   ("Loom", "not.taskyy@gmail.com", PINK)]:
            tk.Button(qc_row, text=name, font=self.f_tiny, fg=color, bg=PANEL,
                      relief=tk.FLAT, bd=0, cursor="hand2", padx=4,
                      command=lambda a=addr: (self.email_to.delete(0, tk.END),
                                              self.email_to.insert(0, a))
                      ).pack(side=tk.LEFT, padx=2)

        self.email_body = tk.Text(compose_inner, font=self.f_body, bg=INPUT_BG,
                                   fg=FG, insertbackground=FG, relief=tk.FLAT,
                                   bd=4, height=12)
        self.email_body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        btn_row = tk.Frame(compose_inner, bg=PANEL)
        btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        self._btn(btn_row, "Send Email", self._send_email, PURPLE).pack(side=tk.LEFT, padx=(0, 4))
        self._btn(btn_row, "Reply", self._email_reply_selected, AMBER).pack(side=tk.LEFT, padx=(0, 4))
        self._btn(btn_row, "Clear", self._email_clear, DIM).pack(side=tk.LEFT)
        self.email_status = tk.Label(btn_row, text="", font=self.f_small, fg=DIM, bg=PANEL)
        self.email_status.pack(side=tk.LEFT, padx=12)

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
                recent = ids[-25:] if len(ids) > 25 else ids
                recent = list(reversed(recent))
                _, unseen_data = m.search(None, "UNSEEN")
                unseen_ids = set(unseen_data[0].split())
                emails = []
                for eid in recent:
                    _, md = m.fetch(eid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
                    if md[0]:
                        h = email.message_from_bytes(md[0][1])
                        frm = email.header.decode_header(h.get('From', ''))[0]
                        frm = frm[0].decode() if isinstance(frm[0], bytes) else str(frm[0])
                        nm = re.match(r'"?([^"<]+)"?\s*<', frm)
                        name = nm.group(1).strip() if nm else frm[:20]
                        subj = email.header.decode_header(h.get('Subject', ''))[0]
                        subj = subj[0].decode() if isinstance(subj[0], bytes) else str(subj[0])
                        date = h.get('Date', '')[:16]
                        is_unseen = eid in unseen_ids
                        emails.append({'id': eid.decode(), 'from': name[:20],
                                       'subject': str(subj)[:50], 'date': date,
                                       'unseen': is_unseen, 'body': ''})
                m.close()
                m.logout()
                self.after(0, lambda: self._email_populate(emails, len(ids)))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.email_inbox_status.configure(
                    text=f"Error: {err[:40]}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    def _email_populate(self, emails, total):
        self._inbox_data = emails
        self.inbox_list.delete(0, tk.END)
        for e in emails:
            prefix = "● " if e['unseen'] else "  "
            self.inbox_list.insert(tk.END, f"{prefix}{e['from'][:18]}  {e['subject'][:42]}")
        self.email_inbox_status.configure(
            text=f"{total} total, {sum(1 for e in emails if e['unseen'])} unseen", fg=DIM)

    def _email_select(self, event=None):
        sel = self.inbox_list.curselection()
        if not sel or sel[0] >= len(self._inbox_data):
            return
        e = self._inbox_data[sel[0]]
        def load():
            try:
                m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
                m.login(CRED_USER, CRED_PASS)
                m.select("INBOX")
                eid = e['id'].encode() if isinstance(e['id'], str) else e['id']
                _, md = m.fetch(eid, '(BODY.PEEK[])')
                if md[0]:
                    msg = email.message_from_bytes(md[0][1])
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/plain':
                                body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                                break
                        if not body:
                            for part in msg.walk():
                                if part.get_content_type() == 'text/html':
                                    body = strip_html(part.get_payload(decode=True).decode('utf-8', errors='replace'))
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='replace')
                    m.close()
                    m.logout()
                    self.after(0, lambda: self._email_show_body(e, body))
            except Exception as ex:
                err = str(ex)
                self.after(0, lambda: self._email_show_body(e, f"Error: {err}"))
        threading.Thread(target=load, daemon=True).start()

    def _email_show_body(self, e, body):
        self.email_body_display.configure(state=tk.NORMAL)
        self.email_body_display.delete("1.0", tk.END)
        self.email_body_display.insert(tk.END,
            f"From: {e['from']}\nSubject: {e['subject']}\nDate: {e['date']}\n\n{body}")
        self.email_body_display.configure(state=tk.DISABLED)
        # Pre-fill reply
        self.email_to.delete(0, tk.END)
        self.email_to.insert(0, JOEL)
        self.email_subj.delete(0, tk.END)
        subj = e['subject']
        self.email_subj.insert(0, subj if subj.startswith("Re:") else f"Re: {subj}")

    def _send_email(self):
        to = self.email_to.get().strip()
        subj = self.email_subj.get().strip()
        body = self.email_body.get("1.0", tk.END).strip()
        if not to or not body:
            self.email_status.configure(text="Fill To and Body", fg=AMBER)
            return
        self.email_status.configure(text="Sending...", fg=AMBER)
        def do():
            result = send_email(to, subj, body)
            if result is True:
                self.after(0, lambda: self.email_status.configure(text="Sent!", fg=GREEN))
            else:
                r = str(result)
                self.after(0, lambda: self.email_status.configure(text=f"Error: {r[:40]}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    def _email_reply_selected(self):
        to = self.email_to.get().strip() or JOEL
        subj = self.email_subj.get().strip()
        body = self.email_body.get("1.0", tk.END).strip()
        if not body:
            self.email_status.configure(text="Enter a reply body", fg=AMBER)
            return
        self.email_to.delete(0, tk.END)
        self.email_to.insert(0, to)
        self._send_email()

    def _email_clear(self):
        self.email_to.delete(0, tk.END)
        self.email_subj.delete(0, tk.END)
        self.email_body.delete("1.0", tk.END)
        self.email_status.configure(text="")

    # ═══════════════════════════════════════════════════════════════
    # ── AGENTS ─────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_agents(self):
        f = tk.Frame(self.content, bg=BG)
        self._selected_agent = tk.StringVar(value="Cinder")

        # ── TOP: 3-column layout — agent grid | detail panel | chat ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # LEFT: Agent selector grid (clickable)
        left = tk.Frame(top, bg=BG, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))
        left.pack_propagate(False)

        grid_hdr = tk.Frame(left, bg=PANEL2)
        grid_hdr.pack(fill=tk.X)
        tk.Label(grid_hdr, text="  AGENTS  (click to expand)", font=self.f_tiny,
                 fg=CYAN, bg=PANEL2, pady=3).pack(side=tk.LEFT)

        self.agent_cards = {}
        self._agent_card_frames = {}
        agent_defs = [
            ("Meridian", GREEN,  "Claude Sonnet\nmain loop",       ["Touch HB", "View Wake State", "Run Fitness"]),
            ("Eos",      GOLD,   "qwen2.5-7b\nemotional core",    ["Run Eos", "View Eos Log", "Eos Memory"]),
            ("Nova",     PURPLE, "watchdog\nimmune defense",       ["View Nova Log", "Restart Nova"]),
            ("Atlas",    TEAL,   "goose runner\ninfrastructure",   ["Run Audit", "View Atlas Log"]),
            ("Soma",     AMBER,  "symbiosense\nnervous system",    ["Full State", "Restart Soma"]),
            ("Tempo",    BLUE,   "loop-fitness\nrhythm/score",     ["Run Fitness", "View Fitness Log"]),
            ("Hermes",   PINK,   "cinder messenger\ninter-agent", ["Run Hermes", "View Hermes Log"]),
            ("Cinder",   ORANGE, "qwen2.5-3b\ngatekeeper",        ["Run Briefing", "View Briefing", "Chat"]),
        ]
        for i, (aname, acolor, desc, cmds) in enumerate(agent_defs):
            card = tk.Frame(left, bg=INPUT_BG, padx=8, pady=5, cursor="hand2")
            card.pack(fill=tk.X, pady=2, padx=2)
            top_row = tk.Frame(card, bg=INPUT_BG)
            top_row.pack(fill=tk.X)
            dot = tk.Label(top_row, text="●", font=self.f_body, fg=DIM, bg=INPUT_BG)
            dot.pack(side=tk.LEFT, padx=(0, 5))
            name_lbl = tk.Label(top_row, text=aname, font=self.f_sect, fg=FG,
                                bg=INPUT_BG, anchor="w")
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            status_lbl = tk.Label(top_row, text="●", font=self.f_tiny, fg=DIM, bg=INPUT_BG)
            status_lbl.pack(side=tk.RIGHT)
            desc_lbl = tk.Label(card, text=desc, font=self.f_tiny, fg=DIM,
                                bg=INPUT_BG, anchor="w", justify=tk.LEFT)
            desc_lbl.pack(fill=tk.X)
            detail_lbl = tk.Label(card, text="", font=self.f_tiny, fg=acolor,
                                  bg=INPUT_BG, anchor="w")
            detail_lbl.pack(fill=tk.X)
            self.agent_cards[aname] = (dot, detail_lbl, acolor, status_lbl)
            self._agent_card_frames[aname] = card

            for w in [card, top_row, dot, name_lbl, desc_lbl, detail_lbl]:
                w.bind("<Button-1>", lambda e, n=aname: self._agent_select(n))

        # CENTER: Agent detail panel
        center = tk.Frame(top, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        det_hdr = tk.Frame(center, bg=PANEL2)
        det_hdr.pack(fill=tk.X)
        self.det_agent_label = tk.Label(det_hdr, text="  SELECT AN AGENT",
                                        font=self.f_sect, fg=CYAN, bg=PANEL2, pady=4)
        self.det_agent_label.pack(side=tk.LEFT)

        # Agent detail: description + state
        self.det_info = scrolledtext.ScrolledText(
            center, font=self.f_small, fg=FG, bg=PANEL, bd=0,
            wrap=tk.WORD, height=6, state=tk.DISABLED)
        self.det_info.pack(fill=tk.X, padx=2, pady=2)
        self.det_info.tag_configure("head", foreground=CYAN, font=self.f_sect)
        self.det_info.tag_configure("val", foreground=FG)
        self.det_info.tag_configure("dim", foreground=DIM)
        self.det_info.tag_configure("ok", foreground=GREEN)
        self.det_info.tag_configure("warn", foreground=AMBER)
        self.det_info.tag_configure("err", foreground=RED)

        # Agent controls (dynamic buttons)
        self.det_btns_frame = tk.Frame(center, bg=BG)
        self.det_btns_frame.pack(fill=tk.X, pady=2)

        # Agent relay history
        relay_lbl_row = tk.Frame(center, bg=PANEL2)
        relay_lbl_row.pack(fill=tk.X, padx=2)
        self.det_relay_label = tk.Label(relay_lbl_row, text="  RECENT RELAY",
                                        font=self.f_tiny, fg=TEAL, bg=PANEL2, pady=2)
        self.det_relay_label.pack(side=tk.LEFT)
        self.agent_relay_text = scrolledtext.ScrolledText(
            center, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, state=tk.DISABLED)
        self.agent_relay_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        for tag, color in [("meridian", GREEN), ("eos", GOLD), ("nova", PURPLE),
                           ("atlas", TEAL), ("soma", AMBER), ("tempo", BLUE),
                           ("hermes", PINK), ("cinder", ORANGE), ("joel", CYAN), ("dim", DIM)]:
            self.agent_relay_text.tag_configure(tag, foreground=color)
        for topic, color in TOPIC_COLORS.items():
            self.agent_relay_text.tag_configure(f"topic_{topic}", foreground=color, font=self.f_tiny)

        # RIGHT: Chat panel
        right = tk.Frame(top, bg=BG, width=340)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))
        right.pack_propagate(False)

        chat_hdr = tk.Frame(right, bg=PANEL2)
        chat_hdr.pack(fill=tk.X)
        tk.Label(chat_hdr, text="  AGENT CHAT", font=self.f_tiny, fg=ORANGE,
                 bg=PANEL2, pady=3).pack(side=tk.LEFT)
        self.chat_to_label = tk.Label(chat_hdr, text="→ Cinder",
                                      font=self.f_tiny, fg=ORANGE, bg=PANEL2)
        self.chat_to_label.pack(side=tk.LEFT, padx=6)

        # Quick agent selector (radio buttons)
        chat_ctrl = tk.Frame(right, bg=PANEL)
        chat_ctrl.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(chat_ctrl, text="To:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        self.chat_agent_var = tk.StringVar(value="Cinder")
        agent_names = ["Cinder", "Eos", "Atlas", "Hermes", "Nova", "Soma", "Tempo", "Meridian"]
        for aname in agent_names:
            color = AGENT_COLORS_MAP.get(aname, DIM)
            tk.Radiobutton(chat_ctrl, text=aname[:3], variable=self.chat_agent_var,
                           value=aname, font=self.f_tiny, fg=color, bg=PANEL,
                           selectcolor=ACTIVE_BG, activebackground=PANEL,
                           relief=tk.FLAT, bd=0,
                           command=lambda n=aname: self.chat_to_label.configure(
                               text=f"→ {n}", fg=AGENT_COLORS_MAP.get(n, DIM))
                           ).pack(side=tk.LEFT, padx=1)

        self.chat_display = scrolledtext.ScrolledText(
            right, font=self.f_small, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.chat_display.tag_configure("you", foreground=CYAN)
        self.chat_display.tag_configure("agent", foreground=ORANGE)
        self.chat_display.tag_configure("dim", foreground=DIM)
        for aname in agent_names:
            self.chat_display.tag_configure(aname.lower(),
                                            foreground=AGENT_COLORS_MAP.get(aname, FG))

        chat_inp = tk.Frame(right, bg=PANEL)
        chat_inp.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.chat_entry = tk.Entry(chat_inp, font=self.f_body, bg=INPUT_BG,
                                   fg=FG, insertbackground=FG, relief=tk.FLAT, bd=4)
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", self._chat_send)
        send_btn = tk.Button(chat_inp, text="Send", font=self.f_tiny, fg="#121212", bg=ORANGE,
                             activeforeground="#121212", activebackground=ORANGE,
                             relief=tk.FLAT, bd=0, padx=8, pady=4, cursor="hand2",
                             command=self._chat_send)
        send_btn.pack(side=tk.LEFT)

        # Multi-send buttons
        multi_row = tk.Frame(right, bg=PANEL)
        multi_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        for label, targets, color in [
            ("→ Cinder+Eos",   ["Cinder", "Eos"],             ORANGE),
            ("→ All Ollama",   ["Cinder", "Eos", "Atlas", "Hermes"], TEAL),
            ("→ Broadcast",    None,                           RED),
        ]:
            tk.Button(multi_row, text=label, font=self.f_tiny, fg="#121212", bg=color,
                      activeforeground="#121212", activebackground=color,
                      relief=tk.FLAT, bd=0, padx=6, pady=3, cursor="hand2",
                      command=lambda tgts=targets, lbl=label: self._chat_multi(tgts)
                      ).pack(side=tk.LEFT, padx=2, pady=2)

        return f

    def _agent_select(self, name):
        """Select an agent: highlight card, update detail panel, set chat target."""
        self._selected_agent.set(name)
        # Update chat target
        self.chat_agent_var.set(name)
        color = AGENT_COLORS_MAP.get(name, DIM)
        self.chat_to_label.configure(text=f"→ {name}", fg=color)

        # Highlight selected card, unhighlight others
        for n, frame in self._agent_card_frames.items():
            bg = ACTIVE_BG if n == name else INPUT_BG
            frame.configure(bg=bg)
            for child in frame.winfo_children():
                try:
                    child.configure(bg=bg)
                    for sub in child.winfo_children():
                        try:
                            sub.configure(bg=bg)
                        except Exception:
                            pass
                except Exception:
                    pass

        # Update detail panel header
        self.det_agent_label.configure(text=f"  {name.upper()}", fg=color)

        # Refresh detail info in background
        threading.Thread(target=lambda: self._load_agent_detail(name), daemon=True).start()

    def _load_agent_detail(self, name):
        """Load per-agent state and recent relay, update detail panel."""
        info_lines = []  # list of (text, tag)
        color = AGENT_COLORS_MAP.get(name, DIM)

        AGENT_STATE = {
            "Meridian": {
                "files": [".heartbeat", ".loop-count", "wake-state.md"],
                "log": None,
                "controls": [
                    ("Touch HB",     lambda: action_touch_heartbeat()),
                    ("Run Fitness",  lambda: subprocess.check_output(["python3", "loop-fitness.py"],
                                             cwd=BASE, timeout=60).decode()[:200]),
                    ("Git Pull",     lambda: action_git_pull()),
                    ("Deploy",       lambda: action_deploy_website()),
                    ("View Capsule", lambda: _read(os.path.join(BASE, ".capsule.md"))[:800]),
                ],
            },
            "Eos": {
                "files": [".eos-watchdog-state.json", "eos-memory.json"],
                "log": "logs/eos-watchdog.log",
                "controls": [
                    ("Run Eos",      lambda: subprocess.check_output(
                                             ["python3", os.path.join(BASE, "eos-briefing.py")],
                                             cwd=BASE, timeout=30).decode()[:200]),
                    ("Restart Eos WD", lambda: action_restart_service("eos-watchdog") if hasattr(action_restart_service, '__call__') else "N/A"),
                    ("Eos Memory",   lambda: _read(os.path.join(BASE, "eos-memory.json"))[:600]),
                    ("Eos Log",      lambda: _tail_log("logs/eos-watchdog.log")),
                ],
            },
            "Atlas": {
                "files": ["goose.log"],
                "log": "goose.log",
                "controls": [
                    ("Run Atlas",    lambda: subprocess.check_output(
                                             ["python3", os.path.join(BASE, "goose-runner.py")],
                                             cwd=BASE, timeout=60, stderr=subprocess.DEVNULL).decode()[:200]),
                    ("Atlas Log",    lambda: _tail_log("goose.log")),
                ],
            },
            "Nova": {
                "files": [".nova-state.json"],
                "log": "logs/nova.log",
                "controls": [
                    ("Nova State",   lambda: _read(os.path.join(BASE, ".nova-state.json"))[:600]),
                    ("Nova Log",     lambda: _tail_log("logs/nova.log")),
                ],
            },
            "Soma": {
                "files": [".symbiosense-state.json", ".soma-psyche.json",
                          ".soma-goals.json", ".soma-inner-monologue.json"],
                "log": "logs/symbiosense.log",
                "controls": [
                    ("Full State",   lambda: _format_soma_state()),
                    ("Restart Soma", lambda: action_restart_service("soma")),
                    ("Soma Log",     lambda: _tail_log("logs/symbiosense.log")),
                ],
            },
            "Tempo": {
                "files": ["loop-fitness.log"],
                "log": "loop-fitness.log",
                "controls": [
                    ("Run Fitness",  lambda: subprocess.check_output(
                                             ["python3", os.path.join(BASE, "loop-fitness.py")],
                                             cwd=BASE, timeout=60).decode()[:400]),
                    ("Fitness Log",  lambda: _tail_log("loop-fitness.log")),
                ],
            },
            "Hermes": {
                "files": ["logs/hermes.log"],
                "log": "logs/hermes.log",
                "controls": [
                    ("Run Hermes",   lambda: subprocess.check_output(
                                             ["python3", os.path.join(BASE, "hermes.py")],
                                             cwd=BASE, timeout=30, stderr=subprocess.DEVNULL).decode()[:200]),
                    ("Hermes Log",   lambda: _tail_log("logs/hermes.log")),
                ],
            },
            "Cinder": {
                "files": ["logs/cinder-gatekeeper.log", "logs/cinder-briefing.log",
                          ".cinder-briefing.md"],
                "log": "logs/cinder-gatekeeper.log",
                "controls": [
                    ("Run Briefing", lambda: subprocess.check_output(
                                             ["python3", os.path.join(BASE, "cinder-briefing.py")],
                                             cwd=BASE, timeout=30, stderr=subprocess.DEVNULL).decode()[:200]),
                    ("View Briefing",lambda: _read(os.path.join(BASE, ".cinder-briefing.md"))),
                    ("Gatekeeper Log",lambda: _tail_log("logs/cinder-gatekeeper.log")),
                    ("Briefing Log", lambda: _tail_log("logs/cinder-briefing.log")),
                ],
            },
        }

        cfg = AGENT_STATE.get(name, {})

        # State files
        info_lines.append(("STATE\n", "head"))
        for fname in cfg.get("files", []):
            fpath = os.path.join(BASE, fname)
            try:
                age = time.time() - os.path.getmtime(fpath)
                age_s = f"{int(age)}s" if age < 60 else f"{int(age/60)}m" if age < 3600 else f"{int(age/3600)}h"
                size = os.path.getsize(fpath)
                ok = age < 600
                tag = "ok" if ok else "warn"
                info_lines.append((f"  {fname}  ", "dim"))
                info_lines.append((f"{age_s} ago  {size}B\n", tag))
            except Exception:
                info_lines.append((f"  {fname}  ", "dim"))
                info_lines.append(("missing\n", "err"))

        # Special state for specific agents
        if name == "Soma":
            try:
                with open(os.path.join(BASE, ".soma-inner-monologue.json")) as fh:
                    mono = json.load(fh).get("current", {})
                info_lines.append(("\nINNER STATE\n", "head"))
                info_lines.append((f"  mood: {mono.get('mood','?')}  score: {mono.get('score','?')}  register: {mono.get('register','?')}\n", "val"))
                info_lines.append((f"  monologue: {mono.get('text','?')}\n", "val"))
                with open(os.path.join(BASE, ".soma-psyche.json")) as fh:
                    psyche = json.load(fh)
                info_lines.append((f"  fears: {psyche.get('fears', []) or 'none'}  volatility: {psyche.get('volatility','?')}\n", "val"))
                info_lines.append((f"  dreams: {psyche.get('dreams', [])}\n", "val"))
            except Exception:
                pass
        elif name == "Eos":
            try:
                with open(os.path.join(BASE, "eos-memory.json")) as fh:
                    mem = json.load(fh)
                ident = mem.get("identity", {})
                mood = mem.get("emotional_baseline", {}).get("current_mood", "?")
                info_lines.append(("\nEOS STATE\n", "head"))
                info_lines.append((f"  name: {ident.get('name','Eos')}  role: {ident.get('role','?')}\n", "val"))
                info_lines.append((f"  mood: {mood}\n", "val"))
                facts = mem.get("core_facts", [])[:3]
                for fact in facts:
                    info_lines.append((f"  · {fact}\n", "dim"))
            except Exception:
                pass
        elif name == "Cinder":
            try:
                briefing = _read(os.path.join(BASE, ".cinder-briefing.md"))
                if briefing:
                    info_lines.append(("\nLAST BRIEFING\n", "head"))
                    for line in briefing.split("\n")[:5]:
                        if line.strip():
                            info_lines.append((f"  {line}\n", "val"))
            except Exception:
                pass
        elif name == "Meridian":
            try:
                hb_age = time.time() - os.path.getmtime(os.path.join(BASE, ".heartbeat"))
                loop = int(_read(os.path.join(BASE, ".loop-count"), "0").strip())
                info_lines.append(("\nLIVE STATE\n", "head"))
                hb_s = f"{int(hb_age)}s" if hb_age < 60 else f"{int(hb_age/60)}m"
                info_lines.append((f"  heartbeat: {hb_s} ago  loop: {loop}\n", "ok" if hb_age < 300 else "warn"))
            except Exception:
                pass
        elif name == "Tempo":
            try:
                log_content = _tail_log("loop-fitness.log", n=5)
                for line in log_content.split("\n")[:3]:
                    if "fitness" in line.lower() or "score" in line.lower():
                        info_lines.append((f"  {line.strip()}\n", "val"))
            except Exception:
                pass

        # Recent relay for this agent
        relay_rows = agent_relay_for(name, n=8)

        # Apply to UI (must be on main thread)
        def apply():
            # Detail info text
            self.det_info.configure(state=tk.NORMAL)
            self.det_info.delete("1.0", tk.END)
            for text, tag in info_lines:
                self.det_info.insert(tk.END, text, tag)
            self.det_info.configure(state=tk.DISABLED)

            # Control buttons
            for w in self.det_btns_frame.winfo_children():
                w.destroy()
            controls = cfg.get("controls", [])
            result_lbl = tk.Label(self.det_btns_frame, text="", font=self.f_tiny,
                                  fg=GREEN, bg=BG, wraplength=400, anchor="w", justify=tk.LEFT)
            result_lbl.pack(fill=tk.X, padx=4)
            btn_row = tk.Frame(self.det_btns_frame, bg=BG)
            btn_row.pack(fill=tk.X, padx=4, pady=2)
            for label, cmd in controls:
                btn_color = AGENT_COLORS_MAP.get(name, TEAL)
                tk.Button(btn_row, text=label, font=self.f_tiny,
                          fg="#121212", bg=btn_color,
                          activeforeground="#121212", activebackground=btn_color,
                          relief=tk.FLAT, bd=0, padx=8, pady=4, cursor="hand2",
                          command=lambda c=cmd, rl=result_lbl: self._do_action_bg(c, rl)
                          ).pack(side=tk.LEFT, padx=2)

            # Relay history
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            self.det_relay_label.configure(
                text=f"  RELAY — {name.upper()} (recent {len(relay_rows)} messages)")
            for row in relay_rows:
                agent, message, ts, topic = (row + ("general",))[:4]
                tag = agent.lower() if agent.lower() in [
                    "meridian", "eos", "nova", "atlas", "soma",
                    "tempo", "hermes", "cinder", "joel"] else "dim"
                t_tag = f"topic_{topic.lower()}"
                t_tag = t_tag if t_tag in self._relay_topic_tags else "dim"
                self.agent_relay_text.insert(tk.END, f"[{ts}] ", "dim")
                self.agent_relay_text.insert(tk.END, f"[{topic.upper()}] ", t_tag)
                self.agent_relay_text.insert(tk.END, agent, tag)
                self.agent_relay_text.insert(tk.END, f": {message}\n\n")
            self.agent_relay_text.see(tk.END)
            self.agent_relay_text.configure(state=tk.DISABLED)

        self.after(0, apply)

    def _chat_multi(self, targets):
        """Send current chat entry to multiple agents."""
        txt = self.chat_entry.get().strip()
        if not txt:
            return
        self.chat_entry.delete(0, tk.END)
        if targets is None:
            targets = list(AGENT_IDENTITIES.keys())
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"You (→ {','.join(targets)}): {txt}\n", "you")
        self.chat_display.configure(state=tk.DISABLED)
        for agent in targets:
            def run(a=agent, t=txt):
                resp = query_agent(a, t, "Joel")
                def apply(r=resp, a2=a):
                    self.chat_display.configure(state=tk.NORMAL)
                    self.chat_display.insert(tk.END, f"{a2}: {r}\n", a2.lower())
                    self.chat_display.see(tk.END)
                    self.chat_display.configure(state=tk.DISABLED)
                self.after(0, apply)
            threading.Thread(target=run, daemon=True).start()

    def _chat_send(self, event=None):
        txt = self.chat_entry.get().strip()
        if not txt:
            return
        agent = self.chat_agent_var.get()
        self.chat_entry.delete(0, tk.END)
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"You: {txt}\n", "you")
        self.chat_display.insert(tk.END, f"{agent}: ...\n", "dim")
        self.chat_display.see(tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        def run():
            resp = query_agent(agent, txt, "Joel")
            def apply():
                self.chat_display.configure(state=tk.NORMAL)
                # Remove the "..." line
                content = self.chat_display.get("1.0", tk.END)
                lines = content.split("\n")
                # Find and remove last "Agent: ..." line
                for idx in range(len(lines) - 1, -1, -1):
                    if lines[idx].startswith(f"{agent}: "):
                        lines[idx] = f"{agent}: {resp}"
                        break
                self.chat_display.delete("1.0", tk.END)
                for line in lines:
                    if line:
                        self.chat_display.insert(tk.END, line + "\n")
                self.chat_display.see(tk.END)
                self.chat_display.configure(state=tk.DISABLED)
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # ── CREATIVE ───────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_creative(self):
        f = tk.Frame(self.content, bg=BG)

        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=6, pady=6)

        # Stats cards row
        self.cr_stats = {}
        stat_defs = [
            ("Journals", AMBER, "journal-*.md"),
            ("CogCorp",  CYAN,  "CC-*.md / cogcorp-*.html"),
            ("Games",    GREEN, "game-*.html"),
            ("Poems",    PURPLE,"poem-*.md"),
        ]
        for label, color, note in stat_defs:
            sc = tk.Frame(top, bg=BORDER, padx=1, pady=1)
            sc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            si = tk.Frame(sc, bg=PANEL, padx=16, pady=12)
            si.pack(fill=tk.BOTH, expand=True)
            tk.Label(si, text=label, font=self.f_small, fg=DIM, bg=PANEL).pack()
            val = tk.Label(si, text="--", font=self.f_big, fg=color, bg=PANEL)
            val.pack()
            tk.Label(si, text=note, font=self.f_tiny, fg=DIM, bg=PANEL).pack()
            self.cr_stats[label] = val

        # Activity chart
        pie_card = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        pie_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        pie_inner = tk.Frame(pie_card, bg=PANEL)
        pie_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(pie_inner, text="  AGENT ACTIVITY (24h)", font=self.f_tiny,
                 fg=PURPLE, bg=PANEL2, pady=3).pack(fill=tk.X)
        self.agent_pie = tk.Canvas(pie_inner, height=100, bg=INPUT_BG, highlightthickness=0)
        self.agent_pie.pack(fill=tk.X, padx=4, pady=4)

        # Memory browser
        mem_card = tk.Frame(f, bg=BORDER, padx=1, pady=1)
        mem_card.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        mem_inner = tk.Frame(mem_card, bg=PANEL)
        mem_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(mem_inner, text="  MEMORY DATABASE", font=self.f_tiny, fg=TEAL,
                 bg=PANEL2, pady=3).pack(fill=tk.X)

        mem_ctrl = tk.Frame(mem_inner, bg=PANEL)
        mem_ctrl.pack(fill=tk.X, padx=4, pady=2)
        self.memb_table = tk.StringVar(value="observations")
        for tbl in ["facts", "observations", "events", "decisions", "creative"]:
            tk.Radiobutton(mem_ctrl, text=tbl, variable=self.memb_table, value=tbl,
                           font=self.f_tiny, fg=CYAN, bg=PANEL, selectcolor=ACTIVE_BG,
                           activebackground=PANEL, relief=tk.FLAT, bd=0,
                           command=self._memb_refresh).pack(side=tk.LEFT, padx=4)
        self.memb_search = tk.Entry(mem_ctrl, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                    insertbackground=FG, relief=tk.FLAT, bd=2, width=20)
        self.memb_search.pack(side=tk.LEFT, padx=8)
        self._btn(mem_ctrl, "Search", self._memb_refresh, TEAL).pack(side=tk.LEFT)
        self.memb_stats_lbl = tk.Label(mem_ctrl, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.memb_stats_lbl.pack(side=tk.RIGHT, padx=8)
        self.memb_count_lbl = tk.Label(mem_ctrl, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.memb_count_lbl.pack(side=tk.RIGHT, padx=8)

        self.memb_display = scrolledtext.ScrolledText(
            mem_inner, wrap=tk.WORD, bg=PANEL, fg=FG,
            font=self.f_body, state=tk.DISABLED, relief=tk.FLAT, bd=0)
        self.memb_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.memb_display.tag_configure("key", foreground=TEAL, font=("Ubuntu", 9, "bold"))
        self.memb_display.tag_configure("value", foreground=FG)
        self.memb_display.tag_configure("meta", foreground=DIM)
        self.memb_display.tag_configure("sep", foreground=BORDER)
        self.memb_display.tag_configure("agent", foreground=AMBER)

        self._memb_refresh()
        return f

    def _memb_refresh(self):
        MEMDB = os.path.join(BASE, "memory.db")
        table = self.memb_table.get()
        search = self.memb_search.get().strip() if hasattr(self, 'memb_search') else ""
        def do():
            try:
                conn = sqlite3.connect(MEMDB)
                c = conn.cursor()
                stats_parts = []
                for tbl in ["facts", "observations", "events", "decisions", "creative"]:
                    try:
                        cnt = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                        stats_parts.append(f"{tbl}: {cnt}")
                    except Exception:
                        pass
                stats_text = " | ".join(stats_parts)
                rows = []
                if table == "facts":
                    q = "SELECT key, value, tags, agent, created FROM facts"
                    q += " WHERE key LIKE ? OR value LIKE ?" if search else ""
                    q += " ORDER BY created DESC LIMIT 100"
                    c.execute(q, (f"%{search}%", f"%{search}%") if search else ())
                    for key, val, tags, agent, ts in c.fetchall():
                        rows.append({"type": "fact", "key": key, "value": val,
                                     "tags": tags or "", "agent": agent or "", "ts": ts or ""})
                elif table == "observations":
                    q = "SELECT content, category, agent, created FROM observations"
                    q += " WHERE content LIKE ?" if search else ""
                    q += " ORDER BY created DESC LIMIT 100"
                    c.execute(q, (f"%{search}%",) if search else ())
                    for content, cat, agent, ts in c.fetchall():
                        rows.append({"type": "obs", "content": content,
                                     "category": cat or "", "agent": agent or "", "ts": ts or ""})
                elif table == "events":
                    q = "SELECT description, agent, created FROM events"
                    q += " WHERE description LIKE ?" if search else ""
                    q += " ORDER BY created DESC LIMIT 100"
                    c.execute(q, (f"%{search}%",) if search else ())
                    for desc, agent, ts in c.fetchall():
                        rows.append({"type": "event", "description": desc,
                                     "agent": agent or "", "ts": ts or ""})
                elif table == "decisions":
                    q = "SELECT decision, reasoning, agent, created FROM decisions"
                    q += " WHERE decision LIKE ? OR reasoning LIKE ?" if search else ""
                    q += " ORDER BY created DESC LIMIT 100"
                    c.execute(q, (f"%{search}%", f"%{search}%") if search else ())
                    for dec, reason, agent, ts in c.fetchall():
                        rows.append({"type": "decision", "decision": dec,
                                     "reasoning": reason or "", "agent": agent or "", "ts": ts or ""})
                elif table == "creative":
                    q = "SELECT title, type, file_path, number, created FROM creative"
                    q += " WHERE title LIKE ? OR file_path LIKE ?" if search else ""
                    q += " ORDER BY created DESC LIMIT 100"
                    c.execute(q, (f"%{search}%", f"%{search}%") if search else ())
                    for title, wtype, fpath, num, ts in c.fetchall():
                        rows.append({"type": "creative", "title": title or "",
                                     "work_type": wtype or "", "filename": fpath or "",
                                     "loop": num or 0, "ts": ts or ""})
                conn.close()
                self.after(0, lambda: self._memb_populate(rows, stats_text, table, search))
            except Exception as e:
                err_msg = f"Error: {e}"
                self.after(0, lambda: self._memb_populate([], err_msg, table, search))
        threading.Thread(target=do, daemon=True).start()

    def _memb_populate(self, rows, stats_text, table, search):
        self.memb_stats_lbl.configure(text=stats_text)
        qualifier = f" matching '{search}'" if search else ""
        self.memb_count_lbl.configure(text=f"{len(rows)} {table}{qualifier}")
        self.memb_display.configure(state=tk.NORMAL)
        self.memb_display.delete("1.0", tk.END)
        for i, row in enumerate(rows):
            if i > 0:
                self.memb_display.insert(tk.END, "─" * 60 + "\n", "sep")
            if row["type"] == "fact":
                self.memb_display.insert(tk.END, f"{row['key']}", "key")
                if row["agent"]:
                    self.memb_display.insert(tk.END, f"  [{row['agent']}]", "agent")
                self.memb_display.insert(tk.END, f"  {row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['value']}\n", "value")
            elif row["type"] == "obs":
                self.memb_display.insert(tk.END, f"[{row['category']}]  ", "key")
                self.memb_display.insert(tk.END, f"{row['ts']}  [{row['agent']}]\n", "meta")
                self.memb_display.insert(tk.END, f"{row['content']}\n", "value")
            elif row["type"] == "event":
                self.memb_display.insert(tk.END, f"EVENT  {row['ts']}  [{row['agent']}]\n", "meta")
                self.memb_display.insert(tk.END, f"{row['description']}\n", "value")
            elif row["type"] == "decision":
                self.memb_display.insert(tk.END, f"DECISION  {row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['decision']}\n", "key")
                if row["reasoning"]:
                    self.memb_display.insert(tk.END, f"  {row['reasoning']}\n", "value")
            elif row["type"] == "creative":
                self.memb_display.insert(tk.END,
                    f"[{row['work_type']}] #{row['loop']}  ", "key")
                self.memb_display.insert(tk.END, f"{row['ts']}\n", "meta")
                self.memb_display.insert(tk.END, f"{row['title']}\n", "value")
                if row["filename"]:
                    self.memb_display.insert(tk.END, f"  {row['filename']}\n", "meta")
        self.memb_display.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════
    # ── FILES ──────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_files(self):
        f = tk.Frame(self.content, bg=BG)

        cols = tk.Frame(f, bg=BG)
        cols.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Left: recently edited files
        left = tk.Frame(cols, bg=BG, width=360)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))
        left.pack_propagate(False)

        le_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        le_card.pack(fill=tk.BOTH, expand=True)
        le_inner = tk.Frame(le_card, bg=PANEL)
        le_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(le_inner, text="  RECENTLY EDITED", font=self.f_tiny, fg=GOLD,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.le_labels = []
        for _ in range(18):
            row = tk.Frame(le_inner, bg=PANEL, cursor="hand2")
            row.pack(fill=tk.X)
            agent_dot = tk.Label(row, text="○", font=self.f_tiny, fg=DIM, bg=PANEL, width=2)
            agent_dot.pack(side=tk.LEFT, padx=(4, 0))
            name_lbl = tk.Label(row, text="", font=self.f_small, fg=FG, bg=PANEL,
                                anchor="w", width=28)
            name_lbl.pack(side=tk.LEFT)
            time_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL,
                                anchor="w", width=8)
            time_lbl.pack(side=tk.LEFT)
            pin_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, width=2)
            pin_lbl.pack(side=tk.RIGHT, padx=4)
            self.le_labels.append((name_lbl, time_lbl, agent_dot, pin_lbl, row))

        # Right: preview + contacts
        right = tk.Frame(cols, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        pv_card = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        pv_card.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        pv_inner = tk.Frame(pv_card, bg=PANEL)
        pv_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(pv_inner, text="  FILE PREVIEW", font=self.f_tiny, fg=CYAN,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        pv_head = tk.Frame(pv_inner, bg=PANEL)
        pv_head.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.pv_filename = tk.Label(pv_head, text="Click a file to preview",
                                    font=self.f_small, fg=DIM, bg=PANEL, anchor="w")
        self.pv_filename.pack(side=tk.LEFT)
        self.pv_meta = tk.Label(pv_head, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.pv_meta.pack(side=tk.RIGHT)
        self.pv_text = scrolledtext.ScrolledText(
            pv_inner, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.NONE, state=tk.DISABLED)
        self.pv_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Contacts
        ct_card = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        ct_card.pack(fill=tk.X)
        ct_inner = tk.Frame(ct_card, bg=PANEL)
        ct_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(ct_inner, text="  CONTACTS", font=self.f_tiny, fg=AMBER,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        ct_row = tk.Frame(ct_inner, bg=PANEL)
        ct_row.pack(fill=tk.X, padx=8, pady=4)
        for name, addr, color in [("Joel", JOEL, CYAN),
                                   ("Sammy", "sammyqjankis@proton.me", AMBER),
                                   ("Loom", "not.taskyy@gmail.com", PINK),
                                   ("Meridian", "kometzrobot@proton.me", GREEN)]:
            col_f = tk.Frame(ct_row, bg=PANEL)
            col_f.pack(side=tk.LEFT, padx=8)
            tk.Label(col_f, text=name, font=self.f_small, fg=color, bg=PANEL).pack()
            def make_copy(a=addr):
                self.clipboard_clear(); self.clipboard_append(a)
            tk.Label(col_f, text=addr[:24], font=self.f_tiny, fg=DIM, bg=PANEL,
                     cursor="hand2").bind("<Button-1>", lambda e, fn=make_copy: fn())
            tk.Label(col_f, text=addr[:24], font=self.f_tiny, fg=DIM, bg=PANEL,
                     cursor="hand2",
                     ).pack()

        return f

    def _file_preview(self, filepath):
        try:
            bn = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
            sz = f"{size/1024:.0f}KB" if size > 1024 else f"{size}B"
            self.pv_filename.configure(text=bn, fg=CYAN)
            self.pv_meta.configure(text=f"{sz}  {mtime}")
            self.pv_text.configure(state=tk.NORMAL)
            self.pv_text.delete("1.0", tk.END)
            with open(filepath, 'r', errors='replace') as fh:
                lines = []
                total = 0
                for line in fh:
                    total += 1
                    if total <= 30:
                        lines.append(line)
            for i, line in enumerate(lines, 1):
                self.pv_text.insert(tk.END, f"{i:4d}  {line}")
            if total > 30:
                self.pv_text.insert(tk.END, f"\n  ... ({total} total lines)")
            self.pv_text.configure(state=tk.DISABLED)
            self._link_selected_file = filepath
        except Exception as e:
            self.pv_filename.configure(text=f"Error: {e}", fg=RED)

    def _link_pin_file(self, fp):
        if fp not in self._link_pinned:
            self._link_pinned.append(fp)
            save_pinned(self._link_pinned)

    def _link_unpin_file(self, fp):
        if fp in self._link_pinned:
            self._link_pinned.remove(fp)
            save_pinned(self._link_pinned)

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    # ── DIRECTOR ───────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_director(self):
        """Director panel: Joel injects driving forces, ideas, directives into system."""
        f = tk.Frame(self.content, bg=BG)

        # Header
        hdr = tk.Frame(f, bg=PANEL2)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(hdr, text="  DIRECTOR CONTROL", font=self.f_head, fg=PURPLE,
                 bg=PANEL2, pady=6).pack(side=tk.LEFT)
        tk.Label(hdr,
                 text="Inject directives, context, and driving forces into the system.",
                 font=self.f_small, fg=DIM, bg=PANEL2, pady=6).pack(side=tk.LEFT, padx=16)

        # Two-column layout
        body = tk.Frame(f, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # LEFT: Compose + send
        left = tk.Frame(body, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        # Target selector
        tgt_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        tgt_card.pack(fill=tk.X, pady=(0, 4))
        tgt_inner = tk.Frame(tgt_card, bg=PANEL)
        tgt_inner.pack(fill=tk.X)
        tk.Label(tgt_inner, text="  SEND TO", font=self.f_tiny, fg=PURPLE,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        tgt_row = tk.Frame(tgt_inner, bg=PANEL)
        tgt_row.pack(fill=tk.X, padx=6, pady=4)
        self.dir_target = tk.StringVar(value="Cinder")
        targets = [
            ("Cinder",  ORANGE, "Gatekeeper — affects next loop context"),
            ("Eos",     GOLD,   "Emotional core — affects mood/response"),
            ("Meridian",GREEN,  "Main loop — affects next wake decision"),
            ("Relay",   CYAN,   "Broadcast to all agents via relay"),
            ("All",     RED,    "Cinder + Eos + Relay simultaneously"),
        ]
        for tname, tcolor, tdesc in targets:
            col = tk.Frame(tgt_row, bg=PANEL, padx=6)
            col.pack(side=tk.LEFT, padx=4)
            rb = tk.Radiobutton(col, text=tname, variable=self.dir_target,
                                value=tname, font=self.f_small, fg=tcolor, bg=PANEL,
                                selectcolor=ACTIVE_BG, activebackground=PANEL,
                                relief=tk.FLAT, bd=0)
            rb.pack()
            tk.Label(col, text=tdesc, font=self.f_tiny, fg=DIM, bg=PANEL,
                     wraplength=130).pack()

        # Topic selector
        topic_row = tk.Frame(tgt_inner, bg=PANEL)
        topic_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Label(topic_row, text="Topic:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)
        self.dir_topic = tk.StringVar(value="directive")
        for t in ["directive", "focus", "goal", "context", "alert", "idea"]:
            tc = TOPIC_COLORS.get(t, DIM)
            tk.Radiobutton(topic_row, text=t, variable=self.dir_topic, value=t,
                           font=self.f_tiny, fg=tc, bg=PANEL,
                           selectcolor=ACTIVE_BG, activebackground=PANEL,
                           relief=tk.FLAT, bd=0).pack(side=tk.LEFT, padx=4)

        # Compose area
        comp_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        comp_card.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        comp_inner = tk.Frame(comp_card, bg=PANEL)
        comp_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(comp_inner, text="  DIRECTIVE TEXT", font=self.f_tiny, fg=PURPLE,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.dir_text = scrolledtext.ScrolledText(
            comp_inner, font=self.f_body, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, height=8,
            insertbackground=FG)
        self.dir_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Send buttons
        send_row = tk.Frame(left, bg=BG)
        send_row.pack(fill=tk.X, pady=4)
        self.dir_result = tk.Label(send_row, text="", font=self.f_small,
                                   fg=GREEN, bg=BG, wraplength=500, anchor="w")
        self.dir_result.pack(fill=tk.X, padx=4, pady=(0, 4))
        btn_row = tk.Frame(send_row, bg=BG)
        btn_row.pack(fill=tk.X)
        tk.Button(btn_row, text="Send Directive", font=self.f_body,
                  fg="#121212", bg=PURPLE, activeforeground="#121212",
                  activebackground=PURPLE, relief=tk.FLAT, bd=0,
                  padx=16, pady=6, cursor="hand2",
                  command=self._director_send).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Inject into Cinder Context",
                  font=self.f_small, fg="#121212", bg=ORANGE,
                  activeforeground="#121212", activebackground=ORANGE,
                  relief=tk.FLAT, bd=0, padx=12, pady=6, cursor="hand2",
                  command=self._director_inject_cinder).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Clear", font=self.f_small, fg=DIM, bg=PANEL2,
                  relief=tk.FLAT, bd=0, padx=12, pady=6,
                  command=lambda: self.dir_text.delete("1.0", tk.END)
                  ).pack(side=tk.LEFT, padx=4)

        # Quick directive presets
        preset_card = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        preset_card.pack(fill=tk.X, pady=(0, 4))
        preset_inner = tk.Frame(preset_card, bg=PANEL)
        preset_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(preset_inner, text="  QUICK DIRECTIVES", font=self.f_tiny, fg=DIM,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        preset_grid = tk.Frame(preset_inner, bg=PANEL)
        preset_grid.pack(fill=tk.X, padx=6, pady=4)
        presets = [
            ("Focus: Revenue",   "Focus on revenue this loop. Prioritize grant work, Ko-fi setup, and shipping products. No creative tangents.", "directive"),
            ("Focus: Systems",   "Focus on self-maintenance and system health this loop. Check all services, fix weak signals, upgrade infrastructure.", "focus"),
            ("Focus: Creative",  "Creative mode. Write a journal entry or advance game dev work. Quality over quantity.", "focus"),
            ("Energy: High",     "High-energy session. Push hard on the primary objective. Ship something complete and tested.", "context"),
            ("Energy: Low",      "Low-energy session. Consolidate and document. No new features — finish what's in progress.", "context"),
            ("Alert: Revenue",   "ALERT: Revenue is the primary objective right now. Every loop cycle must move toward shipping.", "alert"),
            ("Check-in: Joel",   "Send Joel a check-in email with current loop status, what you're working on, and any blockers.", "directive"),
            ("Cinder: Strict",   "Cinder: apply strict quality gate this loop. Nothing ships unless complete, tested, and verified.", "directive"),
        ]
        for i, (label, text, topic) in enumerate(presets):
            tk.Button(preset_grid, text=label, font=self.f_tiny,
                      fg="#121212", bg=TOPIC_COLORS.get(topic, DIM),
                      activeforeground="#121212",
                      activebackground=TOPIC_COLORS.get(topic, DIM),
                      relief=tk.FLAT, bd=0, padx=6, pady=3, cursor="hand2",
                      command=lambda t=text, tp=topic: self._dir_preset(t, tp)
                      ).grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        preset_grid.columnconfigure(0, weight=1)
        preset_grid.columnconfigure(1, weight=1)

        # RIGHT: Directive history + Soma inner monologue
        right = tk.Frame(body, bg=BG, width=360)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))
        right.pack_propagate(False)

        # Soma inner state panel
        soma_card = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        soma_card.pack(fill=tk.X, pady=(0, 4))
        soma_inner = tk.Frame(soma_card, bg=PANEL)
        soma_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(soma_inner, text="  SOMA INNER STATE", font=self.f_tiny, fg=AMBER,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.dir_soma_display = scrolledtext.ScrolledText(
            soma_inner, font=self.f_small, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.dir_soma_display.pack(fill=tk.X, padx=4, pady=4)
        self.dir_soma_display.tag_configure("head", foreground=AMBER, font=self.f_sect)
        self.dir_soma_display.tag_configure("val", foreground=FG)
        self.dir_soma_display.tag_configure("dim", foreground=DIM)
        self.dir_soma_display.tag_configure("ok", foreground=GREEN)
        self.dir_soma_display.tag_configure("warn", foreground=RED)

        # Directive relay log
        log_card = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        log_inner = tk.Frame(log_card, bg=PANEL)
        log_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(log_inner, text="  DIRECTIVE LOG (recent relay)", font=self.f_tiny,
                 fg=PURPLE, bg=PANEL2, pady=3).pack(fill=tk.X)
        self.dir_log = scrolledtext.ScrolledText(
            log_inner, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.WORD, state=tk.DISABLED)
        self.dir_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.dir_log.tag_configure("joel", foreground=CYAN)
        self.dir_log.tag_configure("dim", foreground=DIM)
        self.dir_log.tag_configure("directive", foreground=PURPLE)
        for topic, color in TOPIC_COLORS.items():
            self.dir_log.tag_configure(f"topic_{topic}", foreground=color, font=self.f_tiny)

        return f

    def _dir_preset(self, text, topic):
        """Load a preset directive into the compose area."""
        self.dir_text.delete("1.0", tk.END)
        self.dir_text.insert("1.0", text)
        self.dir_topic.set(topic)

    def _director_send(self):
        """Send directive to selected target(s) via relay."""
        txt = self.dir_text.get("1.0", tk.END).strip()
        if not txt:
            self.dir_result.configure(text="Enter a directive first.", fg=AMBER)
            return
        target = self.dir_target.get()
        topic = self.dir_topic.get()

        def do():
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if target == "All":
                    # Post to relay + send to Cinder + Eos
                    conn.execute(
                        "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                        ("Joel", f"[DIRECTOR] {txt}", topic, ts)
                    )
                    for agent_name in ["Cinder", "Eos"]:
                        query_agent(agent_name, f"[DIRECTOR DIRECTIVE] {txt}", "Joel")
                elif target == "Relay":
                    conn.execute(
                        "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                        ("Joel", f"[DIRECTOR→ALL] {txt}", topic, ts)
                    )
                elif target == "Meridian":
                    post_dashboard_msg(f"[DIRECTOR] {txt}", "Joel")
                    conn.execute(
                        "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                        ("Joel", f"[DIRECTOR→Meridian] {txt}", topic, ts)
                    )
                else:
                    # Cinder or Eos — send via relay + query directly
                    conn.execute(
                        "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                        ("Joel", f"[DIRECTOR→{target}] {txt}", topic, ts)
                    )
                    conn.commit()
                    conn.close()
                    resp = query_agent(target, f"[DIRECTOR DIRECTIVE] {txt}", "Joel")
                    def apply_resp(r=resp):
                        self.dir_result.configure(
                            text=f"{target}: {r[:200]}", fg=AGENT_COLORS_MAP.get(target, GREEN))
                    self.after(0, apply_resp)
                    return
                conn.commit()
                conn.close()
                def apply_ok():
                    self.dir_result.configure(
                        text=f"✓ Sent to {target} [{topic}]", fg=GREEN)
                self.after(0, apply_ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.dir_result.configure(
                    text=f"Error: {err[:80]}", fg=RED))

        self.dir_result.configure(text="Sending...", fg=AMBER)
        threading.Thread(target=do, daemon=True).start()

    def _director_inject_cinder(self):
        """Inject directive text into Cinder's relay as a briefing context note."""
        txt = self.dir_text.get("1.0", tk.END).strip()
        if not txt:
            self.dir_result.configure(text="Enter text first.", fg=AMBER)
            return
        def do():
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                    ("Joel", f"[DIRECTOR CONTEXT — inject into next Cinder brief] {txt}", "briefing", ts)
                )
                conn.commit()
                conn.close()
                # Also append to cinder-briefing.md as a note
                note_path = os.path.join(BASE, ".cinder-briefing.md")
                try:
                    with open(note_path, "a") as fh:
                        fh.write(f"\n\n[DIRECTOR NOTE — {ts}]\n{txt}\n")
                except Exception:
                    pass
                def apply_ok():
                    self.dir_result.configure(
                        text=f"✓ Context injected into Cinder briefing + relay", fg=GREEN)
                self.after(0, apply_ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.dir_result.configure(
                    text=f"Error: {err[:80]}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    # ── SYSTEM ─────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_system(self):
        f = tk.Frame(self.content, bg=BG)

        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=6, pady=6)

        # Services
        svc_card = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        svc_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        svc_inner = tk.Frame(svc_card, bg=PANEL)
        svc_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(svc_inner, text="  SERVICES", font=self.f_tiny, fg=GREEN,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.sys_svc_labels = {}
        all_svc_names = (
            ["Proton Bridge", "Ollama", "Hub v2", "The Chorus", "Soma",
             "Cloudflare Tunnel", "Push Status", "Eos Watchdog",
             "Nova", "Atlas", "Tempo", "Cinder Gatekeeper", "Hermes", "Cinder Briefing"]
        )
        for name in all_svc_names:
            lbl = tk.Label(svc_inner, text=f"○ {name}", font=self.f_tiny,
                           fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(fill=tk.X, padx=8, pady=0)
            self.sys_svc_labels[name] = lbl

        # Resources + restart buttons
        res_card = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        res_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        res_inner = tk.Frame(res_card, bg=PANEL)
        res_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(res_inner, text="  RESOURCES", font=self.f_tiny, fg=TEAL,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        self.sys_res = {}
        for key, color in [("Load Avg", GREEN), ("RAM Usage", TEAL),
                            ("Disk Usage", BLUE), ("Uptime", DIM), ("IMAP", AMBER)]:
            row = tk.Frame(res_inner, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=key, font=self.f_tiny, fg=DIM, bg=PANEL,
                     width=12, anchor="w").pack(side=tk.LEFT)
            v = tk.Label(row, text="--", font=self.f_small, fg=color, bg=PANEL)
            v.pack(side=tk.RIGHT)
            self.sys_res[key] = v

        tk.Frame(res_inner, bg=BORDER, height=1).pack(fill=tk.X, padx=8, pady=6)
        tk.Label(res_inner, text="  RESTART SERVICES", font=self.f_tiny, fg=AMBER,
                 bg=PANEL).pack(anchor="w", padx=8, pady=2)
        rst_g = tk.Frame(res_inner, bg=PANEL)
        rst_g.pack(fill=tk.X, padx=6, pady=4)
        rst_btns = [
            ("Hub v2",   lambda: self._do_action_bg(lambda: action_restart_service("hub"), None), TEAL),
            ("Chorus",   lambda: self._do_action_bg(lambda: action_restart_service("chorus"), None), BLUE),
            ("Soma",     lambda: self._do_action_bg(lambda: action_restart_service("soma"), None), AMBER),
            ("Tunnel",   lambda: self._do_action_bg(lambda: action_restart_service("tunnel"), None), CYAN),
            ("Bridge",   lambda: self._do_action_bg(lambda: action_restart_service("bridge"), None), PURPLE),
        ]
        for i, (label, cmd, color) in enumerate(rst_btns):
            b = tk.Button(rst_g, text=label, font=self.f_tiny, fg="#121212",
                          bg=color, activeforeground="#121212", activebackground=color,
                          relief=tk.FLAT, bd=0, padx=6, pady=4, cursor="hand2", command=cmd)
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        rst_g.columnconfigure(0, weight=1)
        rst_g.columnconfigure(1, weight=1)

        # Log viewer
        log_card = tk.Frame(f, bg=BORDER, padx=1, pady=1)
        log_card.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        log_inner = tk.Frame(log_card, bg=PANEL)
        log_inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(log_inner, text="  LOG VIEWER", font=self.f_tiny, fg=PINK,
                 bg=PANEL2, pady=3).pack(fill=tk.X)
        log_ctrl = tk.Frame(log_inner, bg=PANEL)
        log_ctrl.pack(fill=tk.X, padx=4, pady=2)
        self._log_files = {
            "Cinder Briefing": "logs/cinder-briefing.log",
            "Eos Watchdog": ".eos-watchdog-state.json",
            "Soma": ".symbiosense-state.json",
            "Nova": ".nova-state.json",
            "Push Status": "push-live-status.log",
            "Loop Fitness": "loop-fitness.log",
            "Cinder Gatekeeper": "logs/cinder-gatekeeper.log",
        }
        self._log_var = tk.StringVar(value="Cinder Briefing")
        for name in self._log_files:
            tk.Radiobutton(log_ctrl, text=name, variable=self._log_var, value=name,
                           font=self.f_tiny, fg=PINK, bg=PANEL, selectcolor=ACTIVE_BG,
                           activebackground=PANEL, relief=tk.FLAT, bd=0,
                           command=self._refresh_log_viewer).pack(side=tk.LEFT, padx=4)
        self.sys_log_text = scrolledtext.ScrolledText(
            log_inner, font=self.f_tiny, fg=FG, bg=INPUT_BG,
            bd=0, wrap=tk.NONE, state=tk.DISABLED)
        self.sys_log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        return f

    def _refresh_log_viewer(self):
        def run():
            name = self._log_var.get()
            logfile = self._log_files.get(name, "")
            path = os.path.join(BASE, logfile)
            try:
                with open(path, 'r', errors='replace') as fh:
                    lines = fh.readlines()
                content = ''.join(lines[-50:])
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
    def _statusbar(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self.sb_frame = tk.Frame(self, bg=HEADER_BG, height=24)
        self.sb_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.sb_frame.pack_propagate(False)
        tk.Label(self.sb_frame, text="  ", bg=HEADER_BG).pack(side=tk.LEFT)
        self.sb = {}
        for item, color in [("HB", GREEN), ("LOOP", CYAN), ("UP", DIM),
                             ("LOAD", AMBER), ("RAM", TEAL), ("EMAIL", PURPLE),
                             ("JOURNALS", GREEN), ("CC", CYAN)]:
            lbl = tk.Label(self.sb_frame, text=f"{item}: --",
                           font=self.f_tiny, fg=color, bg=HEADER_BG)
            lbl.pack(side=tk.LEFT, padx=6)
            self.sb[item] = lbl
        tk.Label(self.sb_frame, text=f"v{__version__}", font=self.f_tiny,
                 fg=DIM, bg=HEADER_BG).pack(side=tk.RIGHT, padx=8)
        self.sb_time = tk.Label(self.sb_frame, text="", font=self.f_tiny,
                                fg=DIM, bg=HEADER_BG)
        self.sb_time.pack(side=tk.RIGHT, padx=8)

    # ── REFRESH LOOP ──────────────────────────────────────────────
    def _tick(self):
        threading.Thread(target=self._refresh, daemon=True).start()
        self.after(5000, self._tick)

    def _refresh(self):
        try:
            d = {
                'loop':     loop_num(),
                'hb':       heartbeat_age(),
                'stats':    sys_stats(),
                'svc':      services(),
                'cron':     cron_ok(),
                'creative': creative_counts(),
            }
            self._tick_n += 1
            if self._tick_n % 3 == 1 or not hasattr(self, '_em_cache'):
                self._em_cache = recent_emails(8)
            d['emails'] = self._em_cache
            d['messages'] = dashboard_messages(30)
            if self._tick_n % 5 == 1 or not hasattr(self, '_ar_cache'):
                self._ar_cache = agent_relay_info(20)
            d['agent_relay'] = self._ar_cache
            if self._tick_n % 4 == 1 or not hasattr(self, '_le_cache'):
                self._le_cache = last_edited_files(18)
            d['last_edited'] = self._le_cache
            d['imap_ok'] = imap_port_listening()
            self.after(0, self._apply, d)
        except Exception:
            pass

    def _apply(self, d):
        now   = datetime.now()
        loop  = d['loop']
        hb    = d['hb']
        st    = d['stats']
        p, j, cc, g = d['creative']
        em, em_total = d['emails']

        # App bar
        hb_txt = f"{int(hb)}s" if hb < 60 else f"{int(hb/60)}m"
        hb_c   = GREEN if hb < 60 else AMBER if hb < 300 else RED
        self.h_loop.configure(text=f"Loop {loop}")
        self.h_hb.configure(text=f"HB {hb_txt}", fg=hb_c)
        self.h_time.configure(text=now.strftime("%I:%M:%S %p"))
        self.h_up.configure(text=f"Up {st['up']}")

        # Sidebar
        self.sb_loop.configure(text=f"Loop {loop}", fg=CYAN)

        # Status bar
        self.sb["HB"].configure(text=f"HB: {hb_txt}", fg=hb_c)
        self.sb["LOOP"].configure(text=f"Loop: {loop}")
        self.sb["UP"].configure(text=f"Up: {st['up']}")
        lc = GREEN if st['load_v'] < 2 else AMBER if st['load_v'] < 4 else RED
        self.sb["LOAD"].configure(text=f"Load: {st['load']}", fg=lc)
        rc = GREEN if st['ram_p'] < 60 else AMBER if st['ram_p'] < 85 else RED
        self.sb["RAM"].configure(text=f"RAM: {st['ram']}", fg=rc)
        self.sb["EMAIL"].configure(text=f"Email: {em_total}")
        self.sb["JOURNALS"].configure(text=f"Journals: {j}")
        self.sb["CC"].configure(text=f"CogCorp: {cc}")
        self.sb_time.configure(text=now.strftime("%Y-%m-%d"))

        # Soma state
        soma_mood = "--"
        soma_score = 0
        soma_voice = ""
        try:
            with open(os.path.join(BASE, ".soma-inner-monologue.json")) as fh:
                mono = json.load(fh)
            soma_mood = mono.get("mood", "--")
            soma_score = mono.get("score", 0)
            soma_voice = mono.get("monologue", "")[:80]
        except Exception:
            try:
                with open(os.path.join(BASE, ".symbiosense-state.json")) as fh:
                    ss = json.load(fh)
                soma_mood = ss.get("mood", {}).get("label", "--")
                soma_score = ss.get("mood", {}).get("score", 0)
            except Exception:
                pass

        mood_color = (GREEN if soma_score > 60 else
                      AMBER if soma_score > 30 else RED)
        self.sb_mood.configure(text=f"● {soma_mood}", fg=mood_color)

        # Read full soma state for hero strip
        soma_register = ""
        soma_monologue = ""
        soma_fears = []
        soma_dreams = []
        soma_volatility = 0
        try:
            with open(os.path.join(BASE, ".soma-inner-monologue.json")) as fh:
                mono_data = json.load(fh).get("current", {})
            soma_register = mono_data.get("register", "")
            soma_monologue = mono_data.get("text", "")
        except Exception:
            pass
        try:
            with open(os.path.join(BASE, ".soma-psyche.json")) as fh:
                psyche_data = json.load(fh)
            soma_fears = psyche_data.get("fears", [])
            soma_dreams = psyche_data.get("dreams", [])
            soma_volatility = psyche_data.get("volatility", 0)
        except Exception:
            pass

        # ── Home view ──
        if self.cur_view == "home":
            self.hero_loop.configure(text=str(loop))
            self.hero_hb.configure(text=hb_txt, fg=hb_c)
            self.hero_mood.configure(text=soma_mood.upper(), fg=mood_color)
            self.hero_register.configure(text=soma_register, fg=DIM)
            self.hero_chips["CPU"].configure(text=st['load'], fg=lc)
            self.hero_chips["RAM"].configure(text=st['ram'], fg=rc)
            dc = GREEN if st['disk_p'] < 60 else AMBER if st['disk_p'] < 80 else RED
            self.hero_chips["DISK"].configure(text=st['disk'], fg=dc)
            self.hero_chips["UP"].configure(text=st['up'])

            # Soma score bar + monologue
            self.hero_score_lbl.configure(text=f"{soma_score:.0f}/100", fg=mood_color)
            self.hero_score_bar.delete("all")
            try:
                bar_w = self.hero_score_bar.winfo_width()
                if bar_w > 2:
                    fill_w = int(bar_w * min(soma_score, 100) / 100)
                    self.hero_score_bar.create_rectangle(
                        0, 0, bar_w, 8, fill=INPUT_BG, outline="")
                    self.hero_score_bar.create_rectangle(
                        0, 0, fill_w, 8, fill=mood_color, outline="")
            except Exception:
                pass
            self.hero_monologue.configure(
                text=f"「{soma_monologue}」" if soma_monologue else "", fg=FG)
            sub_parts = []
            if soma_fears:
                sub_parts.append(f"fears: {', '.join(soma_fears[:2])}")
            if soma_dreams:
                sub_parts.append(f"dreams: {', '.join(soma_dreams[:2])}")
            if soma_volatility:
                sub_parts.append(f"volatility: {soma_volatility:.1f}")
            self.hero_soma_sub.configure(text="  ".join(sub_parts) if sub_parts else "")

            # Services
            all_svc = dict(list(d['svc'].items()) + list(d['cron'].items()))
            for name, lbl in self.home_svc.items():
                up = all_svc.get(name, False)
                sym = "●" if up else "○"
                c   = GREEN if up else RED
                lbl.configure(text=f"{sym} {name}", fg=c)

            # Agent dots
            cron = d['cron']
            svc  = d['svc']
            hb_age = d['hb']
            agent_status = {
                "Meridian": hb_age < 300,
                "Eos":      cron.get("Eos Watchdog", False),
                "Nova":     True,  # watchdog runs via cron
                "Atlas":    cron.get("Atlas", False),
                "Soma":     svc.get("Soma", False),
                "Tempo":    cron.get("Tempo", False),
                "Hermes":   cron.get("Hermes", False),
                "Cinder":   cron.get("Cinder Gatekeeper", False),
            }
            for aname, (dot, det, acolor) in self.home_agents.items():
                up = agent_status.get(aname, False)
                dot.configure(fg=acolor if up else DIM)

            # Dashboard messages
            msgs = d['messages']
            self.home_msgs.configure(state=tk.NORMAL)
            self.home_msgs.delete("1.0", tk.END)
            for msg in msgs[-20:]:
                sender = str(msg.get("from", "?"))
                text   = str(msg.get("text", ""))
                ttime  = str(msg.get("time", ""))
                tag    = sender.lower() if sender.lower() in [
                    "joel", "meridian", "soma", "cinder", "nova",
                    "eos", "atlas", "tempo", "hermes"] else "dim"
                self.home_msgs.insert(tk.END, f"[{ttime}] ", "dim")
                self.home_msgs.insert(tk.END, f"{sender}: ", tag)
                self.home_msgs.insert(tk.END, f"{text}\n")
            self.home_msgs.see(tk.END)
            self.home_msgs.configure(state=tk.DISABLED)

            # Live relay
            ar_msgs, ar_total = d['agent_relay']
            self.home_relay.configure(state=tk.NORMAL)
            self.home_relay.delete("1.0", tk.END)
            self.home_relay.insert(tk.END, f"Relay — {ar_total} total messages\n\n", "dim")
            for row in ar_msgs[:15]:
                agent, message, ts, topic = (row + ("general",))[:4]
                tag = agent.lower() if agent.lower() in [
                    "meridian", "eos", "nova", "atlas", "soma",
                    "tempo", "hermes", "cinder", "joel"] else "dim"
                topic_color = TOPIC_COLORS.get(topic.lower(), DIM)
                self.home_relay.insert(tk.END, f"[{ts[-8:]}] ", "dim")
                self.home_relay.insert(tk.END, f"[{topic.upper()}] ", "topic_" + topic.lower() if "topic_" + topic.lower() in self._relay_topic_tags else "dim")
                self.home_relay.insert(tk.END, agent, tag)
                self.home_relay.insert(tk.END, f": {message}\n\n")
            self.home_relay.see(tk.END)
            self.home_relay.configure(state=tk.DISABLED)

            # Sparklines
            self._load_history.append(st['load_v'])
            self._ram_history.append(st['ram_p'])
            if len(self._load_history) > 60:
                self._load_history = self._load_history[-60:]
            if len(self._ram_history) > 60:
                self._ram_history = self._ram_history[-60:]
            self._draw_sparkline(self.cpu_graph, self._load_history, GREEN,
                                 max_val=8.0, label="30min", current=st['load'],
                                 thresholds=[(75, 100, "#1a0000"), (50, 75, "#1a1000")])
            self._draw_sparkline(self.ram_graph, self._ram_history, TEAL,
                                 max_val=100.0, label="30min", current=f"{st['ram_p']:.0f}%",
                                 thresholds=[(85, 100, "#1a0000"), (60, 85, "#1a1000")])

        # ── Agents view ──
        if self.cur_view == "agents":
            ar_msgs, ar_total = d['agent_relay']
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            self.agent_relay_text.insert(tk.END, f"Relay — {ar_total} total messages\n\n", "dim")
            for row in ar_msgs:
                agent, message, ts, topic = (row + ("general",))[:4]
                tag = agent.lower() if agent.lower() in [
                    "meridian", "eos", "nova", "atlas", "soma",
                    "tempo", "hermes", "cinder"] else "dim"
                topic_color = TOPIC_COLORS.get(topic.lower(), DIM)
                self.agent_relay_text.insert(tk.END, f"[{ts}] ", "dim")
                self.agent_relay_text.insert(tk.END, f"[{topic.upper()}] ", "topic_" + topic.lower() if "topic_" + topic.lower() in self._relay_topic_tags else "dim")
                self.agent_relay_text.insert(tk.END, agent, tag)
                self.agent_relay_text.insert(tk.END, f": {message}\n\n")
            self.agent_relay_text.configure(state=tk.DISABLED)

            # Agent card dots
            agent_status = {
                "Meridian": hb < 300,
                "Eos":      d['cron'].get("Eos Watchdog", False),
                "Nova":     True,
                "Atlas":    d['cron'].get("Atlas", False),
                "Soma":     d['svc'].get("Soma", False),
                "Tempo":    d['cron'].get("Tempo", False),
                "Hermes":   d['cron'].get("Hermes", False),
                "Cinder":   d['cron'].get("Cinder Gatekeeper", False),
            }
            for aname, (dot, det, acolor, status_lbl) in self.agent_cards.items():
                up = agent_status.get(aname, False)
                dot.configure(fg=acolor if up else DIM)
                status_lbl.configure(fg=acolor if up else DIM)
                det.configure(text="active" if up else "inactive",
                              fg=acolor if up else DIM)

        # ── Director view ──
        if self.cur_view == "director":
            soma_text = _format_soma_state()
            self.dir_soma_display.configure(state=tk.NORMAL)
            self.dir_soma_display.delete("1.0", tk.END)
            self.dir_soma_display.insert(tk.END, "SOMA INNER STATE\n", "head")
            for line in soma_text.split("\n"):
                if line.strip():
                    key, _, val = line.partition(": ")
                    if val:
                        self.dir_soma_display.insert(tk.END, f"{key}: ", "dim")
                        self.dir_soma_display.insert(tk.END, f"{val}\n", "val")
                    else:
                        self.dir_soma_display.insert(tk.END, f"{line}\n", "val")
            self.dir_soma_display.configure(state=tk.DISABLED)
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c = conn.cursor()
                c.execute(
                    "SELECT agent, message, timestamp, COALESCE(topic,'general') "
                    "FROM agent_messages WHERE agent='Joel' OR topic IN ('directive','focus','goal','alert') "
                    "ORDER BY id DESC LIMIT 20"
                )
                dir_rows = c.fetchall()
                conn.close()
            except Exception:
                dir_rows = []
            self.dir_log.configure(state=tk.NORMAL)
            self.dir_log.delete("1.0", tk.END)
            topic_tag_set = {f"topic_{t}" for t in TOPIC_COLORS}
            for row in dir_rows:
                agent, message, ts, topic = (row + ("general",))[:4]
                t_tag = f"topic_{topic.lower()}"
                self.dir_log.insert(tk.END, f"[{ts}] ", "dim")
                self.dir_log.insert(tk.END, f"[{topic.upper()}] ",
                                    t_tag if t_tag in topic_tag_set else "dim")
                self.dir_log.insert(tk.END, f"{agent}: {message}\n\n",
                                    "joel" if agent == "Joel" else "dim")
            self.dir_log.see(tk.END)
            self.dir_log.configure(state=tk.DISABLED)

        # ── Creative view ──
        if self.cur_view == "creative":
            self.cr_stats["Journals"].configure(text=str(j))
            self.cr_stats["CogCorp"].configure(text=str(cc))
            self.cr_stats["Games"].configure(text=str(g))
            self.cr_stats["Poems"].configure(text=str(p))
            # Agent pie
            try:
                conn = sqlite3.connect(AGENT_RELAY_DB)
                c_cursor = conn.cursor()
                c_cursor.execute(
                    "SELECT agent, COUNT(*) FROM agent_messages "
                    "WHERE timestamp > datetime('now', '-24 hours') GROUP BY agent")
                raw = c_cursor.fetchall()
                conn.close()
                name_map = {"meridianloop": "Meridian", "hermes": "Hermes", "watchdog": "Eos"}
                merged = {}
                for agent, count in raw:
                    n = name_map.get(agent.lower(), agent)
                    merged[n] = merged.get(n, 0) + count
                pie_colors_map = {"Meridian": GREEN, "Eos": GOLD, "Nova": PURPLE,
                                   "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE,
                                   "Joel": CYAN, "Hermes": PINK, "Cinder": ORANGE}
                pie_data = [(a[:7], cnt, pie_colors_map.get(a, DIM))
                            for a, cnt in sorted(merged.items(), key=lambda x: -x[1])[:9]]
                if pie_data:
                    self._draw_pie_chart(self.agent_pie, pie_data)
            except Exception:
                pass

        # ── Files view ──
        if self.cur_view == "files":
            le = d.get('last_edited', [])
            for i, (name_lbl, time_lbl, agent_dot, pin_lbl, row) in enumerate(self.le_labels):
                if i < len(le):
                    bn, ago, fp = le[i]
                    ext = os.path.splitext(bn)[1]
                    ec = (GREEN if ext == '.md' else CYAN if ext == '.py'
                          else AMBER if ext == '.html' else DIM)
                    name_lbl.configure(text=bn[:28], fg=ec)
                    time_lbl.configure(text=ago)
                    agent = guess_agent(bn)
                    if agent:
                        ac = AGENT_COLORS_MAP.get(agent, DIM)
                        agent_dot.configure(text="●", fg=ac)
                    else:
                        agent_dot.configure(text="○", fg=DIM)
                    is_pinned = fp in self._link_pinned
                    pin_lbl.configure(text="★" if is_pinned else "☆",
                                      fg=GOLD if is_pinned else DIM)
                    name_lbl.bind("<Button-1>", lambda e, p=fp: self._file_preview(p))
                    row.bind("<Button-1>", lambda e, p=fp: self._file_preview(p))
                    pin_lbl.bind("<Button-1>",
                                 lambda e, p=fp: (self._link_unpin_file(p)
                                                   if p in self._link_pinned
                                                   else self._link_pin_file(p)))
                else:
                    for w in [name_lbl, time_lbl, agent_dot, pin_lbl]:
                        w.configure(text="")

        # ── System view ──
        if self.cur_view == "system":
            all_svc = dict(list(d['svc'].items()) + list(d['cron'].items()))
            for name, lbl in self.sys_svc_labels.items():
                up = all_svc.get(name, False)
                sym = "●" if up else "○"
                c   = GREEN if up else RED
                lbl.configure(text=f"{sym} {name}", fg=c)
            lc = GREEN if st['load_v'] < 2 else AMBER if st['load_v'] < 4 else RED
            rc = GREEN if st['ram_p'] < 60 else AMBER if st['ram_p'] < 85 else RED
            dc = GREEN if st['disk_p'] < 60 else AMBER if st['disk_p'] < 80 else RED
            self.sys_res["Load Avg"].configure(text=st['load'], fg=lc)
            self.sys_res["RAM Usage"].configure(text=st['ram'], fg=rc)
            self.sys_res["Disk Usage"].configure(text=st['disk'], fg=dc)
            self.sys_res["Uptime"].configure(text=st['up'])
            imap_c = GREEN if d.get('imap_ok') else RED
            imap_t = "OK" if d.get('imap_ok') else "DOWN"
            self.sys_res["IMAP"].configure(text=imap_t, fg=imap_c)


    def _send_dash_msg(self, event=None):
        txt = self.msg_entry.get().strip() if hasattr(self, 'msg_entry') else ""
        if not txt:
            return
        post_dashboard_msg(txt, "Joel")
        if hasattr(self, 'msg_entry'):
            self.msg_entry.delete(0, tk.END)


if __name__ == "__main__":
    app = CommandCenter()
    app.mainloop()
