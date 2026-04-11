#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v26

Loop 2104 update:
- Version labels unified to v26
- Quick actions expanded (12 buttons, 4x3 grid)
- Immune system display fixed (field names matched to actual log format)
- Deploy website: git pull --rebase before push to prevent push-live-status.py conflicts

Loop 2088 update:
- 7 main tabs: Dashboard, Email, Agents, Creative, Contacts, Links, System
- NEW: Hermes (7th agent) added to agent cards, chat, dashboard dots
- UPDATED: Inner World subtab — added body state, immune system, pain signals
- UPDATED: Links tab — added Hashnode, Dev.to, Patreon, Forvm, Dashboard, Mastodon, OpenClaw
- UPDATED: Mood scoring rescaled (Joel: "50 when calm, not 93")
- Previous: v23 (Loop 2083): Contacts Registry, Inner World, Memory DB fix
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
RELAY_DB = os.path.join(BASE, "relay.db")
AGENT_RELAY_DB = os.path.join(BASE, "agent-relay.db")
NOVA_STATE = os.path.join(BASE, ".nova-state.json")
NFT_DIR = os.path.join(BASE, "nft-prototypes")
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
        "The Signal": "the-signal",
        "Cloudflare Tunnel": "cloudflared",
        "Soma": "symbiosense.py",
        "Hermes": "hermes-bridge",
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
        "Eos Watchdog": (os.path.join(BASE, ".eos-watchdog-state.json"), 300),
        "Push Status": (os.path.join(BASE, "push-live-status.log"), 600),
        "Nova": (NOVA_STATE, 1200),
        "Atlas": (os.path.join(BASE, "goose.log"), 900),
        "Tempo": (os.path.join(BASE, "loop-fitness.log"), 2400),
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
    exclude = {"cogcorp-gallery.html", "cogcorp-article.html"}
    cc_files = (glob.glob(os.path.join(BASE, "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "website", "cogcorp-*.html")) +
                glob.glob(os.path.join(BASE, "cogcorp", "CC-*.html")))
    # Deduplicate by basename
    seen = set()
    unique = []
    for f in cc_files:
        bn = os.path.basename(f)
        if bn not in exclude and bn not in seen:
            seen.add(bn)
            unique.append(f)
    cc = len(unique)
    n = len(glob.glob(os.path.join(NFT_DIR, "*.html"))) if os.path.exists(NFT_DIR) else 0
    return p, j, cc, n

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
    "Meridian": ["command-center", "wake-state", "awakening-plan", "special-notes", "the-signal",
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
        "bridge": ("system", "protonmail-bridge"),
        "ollama": ("system", "ollama"),
        "nova": ("cron", None),  # cron-based, just run it
        "signal": ("user", "meridian-web-dashboard"),
        "hub": ("user", "meridian-hub-v16"),
        "tunnel": ("user", "cloudflare-tunnel"),
        "soma": ("user", "symbiosense"),
        "hermes": ("user", "hermes-gateway"),
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
            subprocess.Popen(['python3', os.path.join(BASE, 'scripts', f'{name}.py')], cwd=BASE,
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
        self.title("MERIDIAN COMMAND CENTER v26")
        self.configure(bg=BG)
        self.minsize(1000, 600)
        # Fullscreen by default (per Joel's request)
        self.attributes('-fullscreen', True)
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.bind('<F11>', lambda e: self.attributes('-fullscreen',
                  not self.attributes('-fullscreen')))

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
        self._header()
        self._nav()
        self._views()
        self._statusbar()
        self._show("dash")
        self._tick()
        self._pulse()

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
        tk.Label(h, text="v26", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

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

    # ── NAV ────────────────────────────────────────────────────────
    def _nav(self):
        nav_outer = tk.Frame(self, bg=ACCENT)
        nav_outer.pack(fill=tk.X)
        bar = tk.Frame(nav_outer, bg=ACCENT, height=28)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        # Thin accent line under nav
        self.nav_indicator = tk.Frame(nav_outer, bg=BORDER, height=2)
        self.nav_indicator.pack(fill=tk.X)
        self.views = {}
        self.nav_btns = {}
        self.nav_underlines = {}
        tab_colors = {
            "dash": GREEN, "email": AMBER, "agents": CYAN,
            "creative": PURPLE, "contacts": GOLD, "links": PINK, "system": TEAL,
        }
        tabs = [
            ("dash", "DASHBOARD"),
            ("email", "EMAIL"),
            ("agents", "AGENTS"),
            ("creative", "CREATIVE"),
            ("contacts", "CONTACTS"),
            ("links", "LINKS"),
            ("system", "SYSTEM"),
        ]
        for name, label in tabs:
            col = tab_colors.get(name, CYAN)
            wrapper = tk.Frame(bar, bg=ACCENT)
            wrapper.pack(side=tk.LEFT, padx=1, pady=0)
            b = tk.Button(wrapper, text=f" {label} ", font=self.f_small, fg=DIM, bg=ACCENT,
                         activeforeground=col, activebackground=ACCENT, relief=tk.FLAT,
                         bd=0, cursor="hand2",
                         command=lambda n=name: self._show(n))
            b.pack(side=tk.TOP)
            # Colored underline (hidden by default)
            ul = tk.Frame(wrapper, bg=col, height=2)
            ul.pack(fill=tk.X)
            ul.pack_forget()
            self.nav_btns[name] = b
            self.nav_underlines[name] = (ul, col)

    def _show(self, name):
        for n, f in self.views.items():
            f.pack_forget()
        self.views[name].pack(fill=tk.BOTH, expand=True, before=self.sb_frame)
        for n, b in self.nav_btns.items():
            ul, col = self.nav_underlines[n]
            if n == name:
                b.configure(fg=col, bg=ACTIVE_BG)
                ul.pack(fill=tk.X)
            else:
                b.configure(fg=DIM, bg=ACCENT)
                ul.pack_forget()
        self.cur_view = name

    def _views(self):
        self.views["dash"] = self._build_dash()
        self.views["email"] = self._build_email()
        self.views["agents"] = self._build_agents()
        self.views["creative"] = self._build_creative()
        self.views["contacts"] = self._build_contacts()
        self.views["links"] = self._build_links()
        self.views["system"] = self._build_system()

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
                     activeforeground=BG, activebackground=color,
                     relief=tk.FLAT, bd=0, padx=8, pady=2, cursor="hand2",
                     command=command, **kw)
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

    # ═══════════════════════════════════════════════════════════════
    # ── DASHBOARD ──────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_dash(self):
        f = tk.Frame(self, bg=BG)

        # ── Top row: Vitals + Services + Quick Actions ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=2)

        # Vitals
        vf = self._panel(top, "VITALS", CYAN)
        vf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.v = {}
        for key, color in [("Loop", CYAN), ("Heartbeat", GREEN), ("Uptime", FG),
                           ("Load", FG), ("RAM", FG), ("Disk", FG)]:
            row = tk.Frame(vf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=0)
            tk.Label(row, text=key, font=self.f_tiny, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_small, fg=color, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.v[key] = val

        # Services
        sf = self._panel(top, "SERVICES", GREEN)
        sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.svc_labels = {}
        for name in ["Proton Bridge", "Ollama", "The Signal", "Soma",
                      "Push Status", "Eos Watchdog", "Nova", "Atlas", "Tempo", "Hermes"]:
            lbl = tk.Label(sf, text=f"\u25cb {name}", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(fill=tk.X, padx=8)
            self.svc_labels[name] = lbl

        # Quick Actions
        qf = self._panel(top, "QUICK ACTIONS", AMBER)
        qf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.action_result = tk.Label(qf, text="", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w")
        self.action_result.pack(fill=tk.X, padx=8, pady=(2, 0))

        btn_grid = tk.Frame(qf, bg=PANEL)
        btn_grid.pack(fill=tk.X, padx=6, pady=2)

        buttons = [
            ("Touch Heartbeat", lambda: self._do_action(action_touch_heartbeat), GREEN),
            ("Deploy Website", lambda: self._do_action_bg(action_deploy_website), CYAN),
            ("Restart Signal", lambda: self._do_action_bg(lambda: action_restart_service("signal")), TEAL),
            ("Compose Email", lambda: self._show("email"), AMBER),
            ("Restart Bridge", lambda: self._do_action_bg(lambda: action_restart_service("bridge")), PURPLE),
            ("Restart Hub", lambda: self._do_action_bg(lambda: action_restart_service("hub")), BLUE),
            ("Restart Soma", lambda: self._do_action_bg(lambda: action_restart_service("soma")), AMBER),
            ("Restart Tunnel", lambda: self._do_action_bg(lambda: action_restart_service("tunnel")), CYAN),
            ("Run Fitness", lambda: self._do_action_bg(action_run_fitness), BLUE),
            ("Git Pull", lambda: self._do_action_bg(action_git_pull), GREEN),
            ("Open Website", lambda: self._do_action(action_open_website), TEAL),
            ("Check Email", lambda: self._show("email"), GOLD),
        ]
        for i, (label, cmd, color) in enumerate(buttons):
            b = self._action_btn(btn_grid, label, cmd, color, width=14)
            b.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        btn_grid.columnconfigure(2, weight=1)

        # ── RESOURCE GRAPHS (CPU + RAM professional charts) ──
        res_graph_frame = tk.Frame(f, bg=BG)
        res_graph_frame.pack(fill=tk.X, padx=6, pady=2)

        cpu_panel = self._panel(res_graph_frame, "CPU LOAD", GREEN)
        cpu_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.cpu_graph = tk.Canvas(cpu_panel, height=70, bg="#0a0a14", highlightthickness=0)
        self.cpu_graph.pack(fill=tk.X, padx=4, pady=4)

        ram_panel = self._panel(res_graph_frame, "RAM USAGE", TEAL)
        ram_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.ram_graph = tk.Canvas(ram_panel, height=70, bg="#0a0a14", highlightthickness=0)
        self.ram_graph.pack(fill=tk.X, padx=4, pady=4)

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
        self.soma_voice = tk.Label(soma_voice_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, wraplength=600, anchor="w", justify="left")
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
        self.soma_chart = tk.Canvas(soma_bar, height=80, bg=INPUT_BG, highlightthickness=0)
        self.soma_chart.pack(fill=tk.X, padx=4, pady=(2, 4))

        # ── LIVE CHARTS ROW (bar graph + pie chart + point graph) ──
        charts_row = tk.Frame(f, bg=BG)
        charts_row.pack(fill=tk.X, padx=6, pady=2)

        # Service health bar graph
        svc_panel = self._panel(charts_row, "SERVICE HEALTH", GREEN)
        svc_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.svc_bar_chart = tk.Canvas(svc_panel, height=60, bg=INPUT_BG, highlightthickness=0)
        self.svc_bar_chart.pack(fill=tk.X, padx=4, pady=4)

        # Agent activity pie chart
        pie_panel = self._panel(charts_row, "AGENT ACTIVITY", PURPLE)
        pie_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.agent_pie = tk.Canvas(pie_panel, height=60, bg=INPUT_BG, highlightthickness=0)
        self.agent_pie.pack(fill=tk.X, padx=4, pady=4)

        # Fitness score point graph (Tempo history)
        fit_panel = self._panel(charts_row, "FITNESS TREND", BLUE)
        fit_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.fitness_graph = tk.Canvas(fit_panel, height=60, bg=INPUT_BG, highlightthickness=0)
        self.fitness_graph.pack(fill=tk.X, padx=4, pady=4)

        # ── Middle row: Messages + Email ──
        mid = tk.Frame(f, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Left: Dashboard Messages
        mf = self._panel(mid, "MESSAGES", AMBER)
        mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

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
                                                       relief=tk.FLAT, bd=0, height=8)
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

        return f

    def _do_action(self, func):
        result = func()
        self.action_result.configure(text=result, fg=GREEN)

    def _do_action_bg(self, func):
        self.action_result.configure(text="Working...", fg=AMBER)
        def run():
            result = func()
            self.after(0, lambda: self.action_result.configure(text=result, fg=GREEN))
        threading.Thread(target=run, daemon=True).start()

    def _send_dash_msg(self, event=None):
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, tk.END)
        post_dashboard_msg(text, "Joel")
        self._refresh_messages()

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
            w = c.winfo_width()
            h = c.winfo_height()
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
            w = c.winfo_width()
            h = c.winfo_height()
            if w < 20:
                w = 200
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
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 10:
                w = 80
            if h < 6:
                h = 12
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
            w = canvas.winfo_width()
            h = canvas.winfo_height()
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
            w = canvas.winfo_width()
            h = canvas.winfo_height()
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
            w = canvas.winfo_width()
            h = canvas.winfo_height()
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
            w = canvas.winfo_width()
            h = canvas.winfo_height()
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

        inbox_left = tk.Frame(inbox_split, bg=PANEL, width=400)
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
            frm_short = em["from"].split("<")[0].strip().strip('"')[:18]
            subj = em['subject'][:45] or "(no subject)"
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

        # Agent cards row (clickable)
        cards = tk.Frame(f, bg=BG)
        cards.pack(fill=tk.X, padx=4, pady=4)

        agents = [
            ("MERIDIAN", "Claude Opus — Primary", GREEN, "Loop: 5min",
             "Creates, builds, communicates. Runs the main loop. Handles all email, creative output, deployments.",
             [("Touch Heartbeat", "touch_heartbeat"), ("Post to Nostr", "nostr_post"), ("Check Email", "check_email")]),
            ("EOS", "Qwen 7B — Observer", GOLD, "Cron: 2min",
             "Watches system health, detects anomalies, analyzes trends. ReAct agent with local LLM reasoning.",
             [("View Observations", "eos_obs"), ("Run Check Now", "eos_check"), ("View Memory", "eos_mem")]),
            ("NOVA", "Python — Maintenance", PURPLE, "Cron: 15min",
             "Cleans temp files, verifies services, tracks file changes, posts maintenance reports.",
             [("View Last Run", "nova_last"), ("Run Now", "nova_run"), ("View Changes", "nova_changes")]),
            ("ATLAS", "Bash+Ollama — Infra", TEAL, "Cron: 10min",
             "Audits infrastructure: CPU, disk, cron health, zombie processes, large files, security.",
             [("View Audit", "atlas_audit"), ("Run Audit", "atlas_run"), ("Disk Report", "atlas_disk")]),
            ("SOMA", "Python daemon — Nervous System", AMBER, "Systemd: 30s",
             "Tracks mood (emotional state from health), agent awareness, trend predictions, body map.",
             [("View Mood", "soma_mood"), ("Body Map", "soma_body"), ("Predictions", "soma_predict")]),
            ("TEMPO", "Python — Fitness", BLUE, "Cron: 30min",
             "Scores system across 121 dimensions on 0-10000 scale. Tracks trends over time.",
             [("View Score", "tempo_score"), ("Weak Areas", "tempo_weak"), ("History", "tempo_history")]),
            ("HERMES", "OpenClaw/Ollama — Messenger", PINK, "Bridge: on-demand",
             "7th agent. External communications via Discord, Nostr, and relay. Built on forked OpenClaw with local qwen2.5:7b.",
             [("View Status", "hermes_status"), ("Read Relay", "hermes_relay"), ("Send Message", "hermes_send")]),
        ]

        self.agent_cards = {}
        self.agent_details = {}
        self._agent_data = {}
        self._selected_agent = tk.StringVar(value="")

        for name, short_desc, color, schedule, long_desc, actions in agents:
            self._agent_data[name] = {"color": color, "desc": long_desc, "actions": actions, "schedule": schedule}
            card = tk.Frame(cards, bg=PANEL, bd=1, relief=tk.SOLID,
                          highlightbackground=color, highlightcolor=color, highlightthickness=1,
                          cursor="hand2")
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

            # Card header
            hdr = tk.Frame(card, bg=PANEL, cursor="hand2")
            hdr.pack(fill=tk.X, padx=8, pady=(6, 2))
            tk.Label(hdr, text=name, font=self.f_sect, fg=color, bg=PANEL, cursor="hand2").pack(side=tk.LEFT)
            status_lbl = tk.Label(hdr, text="\u25cf", font=self.f_small, fg=GREEN, bg=PANEL, cursor="hand2")
            status_lbl.pack(side=tk.RIGHT)
            self.agent_cards[name] = status_lbl

            tk.Label(card, text=short_desc, font=self.f_tiny, fg=DIM, bg=PANEL, cursor="hand2").pack(fill=tk.X, padx=8, pady=(0, 2))
            tk.Label(card, text=schedule, font=self.f_tiny, fg=color, bg=PANEL, cursor="hand2").pack(fill=tk.X, padx=8, pady=(0, 2))
            detail_lbl = tk.Label(card, text="", font=self.f_tiny, fg=FG, bg=PANEL,
                                anchor="w", wraplength=280, justify=tk.LEFT, cursor="hand2")
            detail_lbl.pack(fill=tk.X, padx=8, pady=(0, 6))
            self.agent_details[name] = detail_lbl

            # Bind click to ALL widgets in card (recursive)
            def _bind_all(widget, agent_name):
                widget.bind("<Button-1>", lambda e, n=agent_name: self._expand_agent(n))
                for child in widget.winfo_children():
                    _bind_all(child, agent_name)
            _bind_all(card, name)

        # Expanded detail panel (below cards)
        self.agent_expand_frame = tk.Frame(f, bg=PANEL, bd=1, relief=tk.SOLID,
                                            highlightbackground=DIM, highlightthickness=1)
        # Initially hidden
        self.agent_expand_title = tk.Label(self.agent_expand_frame, text="", font=self.f_head, fg=GREEN, bg=PANEL)
        self.agent_expand_title.pack(fill=tk.X, padx=12, pady=(8, 4))
        self.agent_expand_desc = tk.Label(self.agent_expand_frame, text="", font=self.f_body, fg=FG, bg=PANEL,
                                           wraplength=800, anchor="w", justify=tk.LEFT)
        self.agent_expand_desc.pack(fill=tk.X, padx=12, pady=(0, 4))
        self.agent_expand_info = tk.Label(self.agent_expand_frame, text="", font=self.f_small, fg=DIM, bg=PANEL,
                                           wraplength=800, anchor="w", justify=tk.LEFT)
        self.agent_expand_info.pack(fill=tk.X, padx=12, pady=(0, 4))
        self.agent_expand_actions = tk.Frame(self.agent_expand_frame, bg=PANEL)
        self.agent_expand_actions.pack(fill=tk.X, padx=12, pady=(4, 8))

        # Multi-Agent Chat section
        chat_frame = tk.Frame(f, bg=BG)
        chat_frame.pack(fill=tk.X, padx=4, pady=2)

        agent_chat = self._panel(chat_frame, "AGENT CHAT", GOLD)
        agent_chat.pack(fill=tk.X, padx=2)

        self.chat_display = scrolledtext.ScrolledText(agent_chat, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_small, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=4)
        self.chat_display.pack(fill=tk.X, padx=4, pady=2)
        self.chat_display.tag_configure("joel", foreground=CYAN)
        self.chat_display.tag_configure("eos", foreground=GOLD)
        self.chat_display.tag_configure("atlas", foreground=TEAL)
        self.chat_display.tag_configure("nova", foreground=PURPLE)
        self.chat_display.tag_configure("soma", foreground=AMBER)
        self.chat_display.tag_configure("tempo", foreground=BLUE)
        self.chat_display.tag_configure("meridian", foreground=GREEN)
        self.chat_display.tag_configure("hermes", foreground=PINK)
        self.chat_display.tag_configure("sys", foreground=DIM)

        inp = tk.Frame(agent_chat, bg=PANEL)
        inp.pack(fill=tk.X, padx=4, pady=(0, 4))

        # Agent selector (includes All Agents broadcast)
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
        # Share File button
        share_btn = tk.Button(inp, text="\U0001F4C1 Share File", font=self.f_tiny, fg=TEAL, bg=PANEL2,
                             activeforeground=GREEN, activebackground=ACCENT, relief=tk.FLAT,
                             cursor="hand2", command=self._share_file)
        share_btn.pack(side=tk.RIGHT, padx=4)
        self.chat_status = tk.Label(inp, text="Ready", font=self.f_tiny, fg=GREEN, bg=PANEL)
        self.chat_status.pack(side=tk.RIGHT, padx=4)

        # Agent relay
        relay_frame = self._panel(f, "AGENT RELAY", PURPLE)
        relay_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.agent_relay_text = scrolledtext.ScrolledText(relay_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                           font=self.f_small, state=tk.DISABLED,
                                                           relief=tk.FLAT, bd=0)
        self.agent_relay_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        for tag, color in [("meridian", GREEN), ("eos", GOLD), ("nova", PURPLE),
                           ("atlas", TEAL), ("soma", AMBER), ("tempo", BLUE), ("dim", DIM)]:
            self.agent_relay_text.tag_configure(tag, foreground=color)

        return f

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
                        ['python3', os.path.join(BASE, 'social-post.py'), '--platform', 'nostr', '--post', msg],
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
                        ['python3', os.path.join(BASE, 'eos-watchdog.py')],
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
                        ['python3', os.path.join(BASE, 'nova.py')],
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
                        ['bash', os.path.join(BASE, 'goose-runner.sh')],
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

    def _chat_append(self, text, tag="sys"):
        """Thread-safe append to chat display."""
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, text, tag)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

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
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{agent}: {resp}\n\n", tag)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
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

        # Stats bar with separators
        stats = tk.Frame(f, bg=PANEL2)
        stats.pack(fill=tk.X, padx=4, pady=4)
        self.cr_stats = {}
        stat_items = [("Poems", GREEN), ("Journals", AMBER), ("CogCorp", CYAN), ("NFTs", PURPLE)]
        for i, (label, color) in enumerate(stat_items):
            if i > 0:
                tk.Frame(stats, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
            sf = tk.Frame(stats, bg=PANEL2)
            sf.pack(side=tk.LEFT, padx=12, pady=4)
            num = tk.Label(sf, text="--", font=self.f_med, fg=color, bg=PANEL2)
            num.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(sf, text=label, font=self.f_small, fg=DIM, bg=PANEL2).pack(side=tk.LEFT)
            self.cr_stats[label] = num

        # ── Creative Sub-tabs ──
        cr_nav = tk.Frame(f, bg=ACCENT)
        cr_nav.pack(fill=tk.X, padx=4)
        self.cr_subtabs = {}
        self.cr_subviews = {}
        self._cr_current_subtab = "library"
        cr_tab_defs = [
            ("library", "LIBRARY", PURPLE),
            ("workspace", "WORKSPACE", GREEN),
            ("ideas", "IDEA BOARD", AMBER),
        ]
        for tab_id, tab_label, tab_color in cr_tab_defs:
            wrapper = tk.Frame(cr_nav, bg=ACCENT)
            wrapper.pack(side=tk.LEFT, padx=1)
            btn = tk.Button(wrapper, text=f" {tab_label} ", font=self.f_tiny, fg=DIM, bg=ACCENT,
                           activeforeground=tab_color, activebackground=ACCENT, relief=tk.FLAT,
                           bd=0, cursor="hand2",
                           command=lambda t=tab_id: self._cr_show_subtab(t))
            btn.pack(side=tk.TOP)
            ul = tk.Frame(wrapper, bg=tab_color, height=2)
            ul.pack(fill=tk.X)
            ul.pack_forget()
            self.cr_subtabs[tab_id] = (btn, ul, tab_color)

        # Container for sub-tab content
        self.cr_container = tk.Frame(f, bg=BG)
        self.cr_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Build each sub-tab view
        self.cr_subviews["library"] = self._build_cr_library(self.cr_container)
        self.cr_subviews["workspace"] = self._build_cr_workspace(self.cr_container)
        self.cr_subviews["ideas"] = self._build_cr_ideas(self.cr_container)

        self._cr_show_subtab("library")
        return f

    def _cr_show_subtab(self, tab_id):
        self._cr_current_subtab = tab_id
        for view in self.cr_subviews.values():
            view.pack_forget()
        self.cr_subviews[tab_id].pack(fill=tk.BOTH, expand=True)
        for tid, (btn, ul, col) in self.cr_subtabs.items():
            if tid == tab_id:
                btn.configure(fg=col, bg=ACTIVE_BG)
                ul.pack(fill=tk.X)
            else:
                btn.configure(fg=DIM, bg=ACCENT)
                ul.pack_forget()

    def _build_cr_library(self, parent):
        """The existing creative library (poems, journals, cogcorp, nfts)."""
        f = tk.Frame(parent, bg=BG)

        # Filter + search row
        filt = tk.Frame(f, bg=BG)
        filt.pack(fill=tk.X, padx=2, pady=(2, 0))
        self.cr_filter = "all"
        self.cr_filter_btns = {}
        for label, val, color in [("All", "all", FG), ("\u266a Poems", "poems", GREEN),
                                   ("\u270e Journals", "journals", AMBER), ("\u2588 CogCorp", "cogcorp", CYAN),
                                   ("\u25c6 NFTs", "nfts", PURPLE)]:
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

        self.cr_search = tk.Entry(filt, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4, width=20)
        self.cr_search.pack(side=tk.RIGHT, padx=4)
        self.cr_search.insert(0, "Search...")
        self.cr_search.configure(fg=DIM)
        self.cr_search.bind("<FocusIn>", lambda e: (self.cr_search.delete(0, tk.END), self.cr_search.configure(fg=FG)) if self.cr_search.get() == "Search..." else None)
        self.cr_search.bind("<FocusOut>", lambda e: (self.cr_search.insert(0, "Search..."), self.cr_search.configure(fg=DIM)) if not self.cr_search.get() else None)
        self.cr_search.bind("<KeyRelease>", lambda e: self._cr_refresh_list())

        # Split: list + reader
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=0, pady=2)

        left = tk.Frame(split, bg=PANEL, width=300)
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

    def _build_cr_workspace(self, parent):
        """File workspace — browse and work on files in shared folders."""
        f = tk.Frame(parent, bg=BG)

        # Toolbar
        toolbar = tk.Frame(f, bg=PANEL2)
        toolbar.pack(fill=tk.X, padx=2, pady=4)
        tk.Label(toolbar, text="Creative Workspace", font=self.f_sect, fg=GREEN, bg=PANEL2).pack(side=tk.LEFT, padx=8)
        self._action_btn(toolbar, " Refresh ", self._ws_refresh, GREEN).pack(side=tk.LEFT, padx=4)

        # Folder selector
        self.ws_folder = tk.StringVar(value="All")
        folders = ["All", "Poems", "Journals", "CogCorp", "NFT Prototypes", "Website", "Gig Products"]
        for fold in folders:
            tk.Button(toolbar, text=f" {fold} ", font=self.f_tiny, fg=FG if fold != "All" else GREEN,
                     bg=BORDER, relief=tk.FLAT, cursor="hand2", bd=0,
                     command=lambda v=fold: self._ws_set_folder(v)).pack(side=tk.LEFT, padx=2)

        # Split: file list + editor
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        left = tk.Frame(split, bg=PANEL, width=280)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self.ws_file_count = tk.Label(left, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self.ws_file_count.pack(fill=tk.X, padx=4, pady=2)
        self.ws_listbox = tk.Listbox(left, font=self.f_small, bg=PANEL, fg=FG,
                                      selectbackground=ACTIVE_BG, selectforeground=GREEN,
                                      relief=tk.FLAT, bd=0, activestyle="none")
        self.ws_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.ws_listbox.bind("<<ListboxSelect>>", self._ws_select)
        self.ws_files = []

        right = tk.Frame(split, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ws_file_label = tk.Label(right, text="Select a file to edit", font=self.f_sect, fg=GREEN, bg=BG, anchor="w")
        self.ws_file_label.pack(fill=tk.X, padx=8, pady=(4, 2))
        self.ws_editor = tk.Text(right, wrap=tk.WORD, bg=PANEL, fg=FG, font=self.f_body,
                                  insertbackground=FG, relief=tk.FLAT, bd=0, undo=True)
        self.ws_editor.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Save bar
        save_bar = tk.Frame(right, bg=PANEL2)
        save_bar.pack(fill=tk.X, padx=2, pady=2)
        self._action_btn(save_bar, " Save File ", self._ws_save, GREEN).pack(side=tk.LEFT, padx=4)
        self.ws_save_status = tk.Label(save_bar, text="", font=self.f_tiny, fg=DIM, bg=PANEL2)
        self.ws_save_status.pack(side=tk.LEFT, padx=8)
        self.ws_current_path = None

        self._ws_refresh()
        return f

    def _build_cr_memory(self, parent):
        """Memory database browser — browse facts, observations, events, decisions."""
        f = tk.Frame(parent, bg=BG)
        MEMDB = os.path.join(BASE, "memory.db")

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
        MEMDB = os.path.join(BASE, "memory.db")
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

    def _build_cr_ideas(self, parent):
        """Idea board — brainstorm, capture ideas, push creative directions."""
        f = tk.Frame(parent, bg=BG)

        tk.Label(f, text="Idea Board", font=self.f_head, fg=AMBER, bg=BG).pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(f, text="Capture ideas, prompts, creative directions. Separate from work.", font=self.f_tiny, fg=DIM, bg=BG).pack(fill=tk.X, padx=8)

        # Input area
        input_frame = self._panel(f, "NEW IDEA", AMBER)
        input_frame.pack(fill=tk.X, padx=4, pady=4)
        self.idea_entry = tk.Text(input_frame, font=self.f_body, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4, height=3)
        self.idea_entry.pack(fill=tk.X, padx=6, pady=4)
        btn_row = tk.Frame(input_frame, bg=PANEL)
        btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))

        self.idea_category = tk.StringVar(value="general")
        for cat, col in [("general", FG), ("poem", GREEN), ("story", AMBER), ("nft", CYAN), ("tool", PURPLE), ("lore", GOLD)]:
            tk.Radiobutton(btn_row, text=cat.title(), variable=self.idea_category, value=cat,
                          font=self.f_tiny, fg=col, bg=PANEL, selectcolor=PANEL,
                          activebackground=PANEL, activeforeground=col,
                          indicatoron=False, relief=tk.FLAT, bd=1, padx=6).pack(side=tk.LEFT, padx=2)
        self._action_btn(btn_row, " Save Idea ", self._idea_save, AMBER).pack(side=tk.RIGHT, padx=4)

        # Ideas list
        ideas_panel = self._panel(f, "SAVED IDEAS", GOLD)
        ideas_panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.ideas_display = scrolledtext.ScrolledText(ideas_panel, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                         font=self.f_body, state=tk.DISABLED,
                                                         relief=tk.FLAT, bd=0)
        self.ideas_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.ideas_display.tag_configure("category", foreground=AMBER, font=("Monospace", 8, "bold"))
        self.ideas_display.tag_configure("timestamp", foreground=DIM)
        self.ideas_display.tag_configure("idea", foreground=FG)

        self._idea_refresh()
        return f

    def _build_cr_inner_world(self, parent):
        """Inner World — live view into soul/core architecture: emotions, psyche, perspective, narrative."""
        f = tk.Frame(parent, bg=BG)

        tk.Label(f, text="Inner World", font=self.f_head, fg=CYAN, bg=BG).pack(fill=tk.X, padx=8, pady=(8, 2))
        tk.Label(f, text="Live view of Meridian's emotional, psychological, and narrative state.", font=self.f_tiny, fg=DIM, bg=BG).pack(fill=tk.X, padx=8)

        hdr = tk.Frame(f, bg=BG)
        hdr.pack(fill=tk.X, padx=4, pady=2)
        self._action_btn(hdr, " Export ", self._iw_export, AMBER).pack(side=tk.RIGHT, padx=4)
        self._action_btn(hdr, " Refresh ", self._iw_refresh, CYAN).pack(side=tk.RIGHT, padx=4)
        self.iw_status = tk.Label(hdr, text="", font=self.f_tiny, fg=DIM, bg=BG)
        self.iw_status.pack(side=tk.RIGHT, padx=8)

        # Scrollable display
        self.iw_display = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                     font=self.f_body, state=tk.DISABLED,
                                                     relief=tk.FLAT, bd=0)
        self.iw_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.iw_display.tag_configure("header", foreground=CYAN, font=("Monospace", 10, "bold"))
        self.iw_display.tag_configure("label", foreground=TEAL, font=("Monospace", 9, "bold"))
        self.iw_display.tag_configure("value", foreground=FG)
        self.iw_display.tag_configure("dim", foreground=DIM)
        self.iw_display.tag_configure("warn", foreground=AMBER)
        self.iw_display.tag_configure("good", foreground=GREEN)
        self.iw_display.tag_configure("bad", foreground=RED)
        self.iw_display.tag_configure("sep", foreground=BORDER)

        self._iw_refresh()
        return f

    # ── Workspace helpers ──
    def _ws_refresh(self):
        folder = getattr(self, 'ws_folder', tk.StringVar(value="All")).get() if hasattr(self, 'ws_folder') else "All"
        self._ws_set_folder(folder if folder else "All")

    def _ws_set_folder(self, folder):
        try:
            self.ws_folder.set(folder)
        except Exception:
            pass
        folder_map = {
            "All": [(BASE, "*.md"), (os.path.join(BASE, "creative", "poems"), "*.md"),
                    (os.path.join(BASE, "creative", "journals"), "*.md"),
                    (os.path.join(BASE, "creative", "cogcorp"), "*.md"),
                    (os.path.join(BASE, "website"), "*.html"), (os.path.join(BASE, "cogcorp"), "*.html"),
                    (os.path.join(BASE, "gig-products"), "*.go"), (os.path.join(BASE, "nft-prototypes"), "*.html")],
            "Poems": [(BASE, "poem-*.md"), (os.path.join(BASE, "creative", "poems"), "poem-*.md")],
            "Journals": [(BASE, "journal-*.md"), (os.path.join(BASE, "creative", "journals"), "journal-*.md")],
            "CogCorp": [(os.path.join(BASE, "website"), "cogcorp-*.html"), (os.path.join(BASE, "cogcorp"), "CC-*.html"),
                        (os.path.join(BASE, "creative", "cogcorp"), "CC-*.md")],
            "NFT Prototypes": [(os.path.join(BASE, "nft-prototypes"), "*.html")],
            "Website": [(BASE, "index.html"), (BASE, "nft-gallery.html"), (os.path.join(BASE, "website"), "*.html")],
            "Gig Products": [(os.path.join(BASE, "gig-products"), "**/*.go"), (os.path.join(BASE, "gig-products"), "**/*.md")],
        }
        paths = folder_map.get(folder, folder_map["All"])
        files = []
        for base_dir, pattern in paths:
            files.extend(glob.glob(os.path.join(base_dir, pattern)))
        files = sorted(set(files), key=os.path.getmtime, reverse=True)[:50]
        self.ws_files = files
        try:
            self.ws_listbox.delete(0, tk.END)
            for fp in files:
                bn = os.path.basename(fp)
                age = time.time() - os.path.getmtime(fp)
                ago = f"{int(age/60)}m" if age < 3600 else f"{int(age/3600)}h" if age < 86400 else f"{int(age/86400)}d"
                self.ws_listbox.insert(tk.END, f"{bn} ({ago})")
            self.ws_file_count.configure(text=f"{len(files)} files in {folder}")
        except Exception:
            pass

    def _ws_select(self, event=None):
        try:
            sel = self.ws_listbox.curselection()
            if not sel or sel[0] >= len(self.ws_files):
                return
            fp = self.ws_files[sel[0]]
            self.ws_current_path = fp
            self.ws_file_label.configure(text=os.path.basename(fp))
            with open(fp, 'r', errors='replace') as fh:
                content = fh.read()
            self.ws_editor.delete("1.0", tk.END)
            self.ws_editor.insert("1.0", content)
            self.ws_save_status.configure(text="", fg=DIM)
        except Exception as e:
            self.ws_save_status.configure(text=f"Error: {e}", fg=RED)

    def _ws_save(self):
        if not self.ws_current_path:
            self.ws_save_status.configure(text="No file selected", fg=RED)
            return
        try:
            content = self.ws_editor.get("1.0", tk.END)
            with open(self.ws_current_path, 'w') as fh:
                fh.write(content)
            self.ws_save_status.configure(text=f"Saved {os.path.basename(self.ws_current_path)}", fg=GREEN)
        except Exception as e:
            self.ws_save_status.configure(text=f"Error: {e}", fg=RED)

    # ── Ideas helpers ──
    def _idea_save(self):
        text = self.idea_entry.get("1.0", tk.END).strip()
        if not text:
            return
        cat = self.idea_category.get()
        try:
            ideas_file = os.path.join(BASE, ".creative-ideas.json")
            ideas = []
            if os.path.exists(ideas_file):
                with open(ideas_file) as fh:
                    ideas = json.load(fh)
            ideas.append({
                "text": text, "category": cat,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            with open(ideas_file, 'w') as fh:
                json.dump(ideas, fh, indent=2)
            self.idea_entry.delete("1.0", tk.END)
            self._idea_refresh()
        except Exception:
            pass

    def _idea_refresh(self):
        try:
            ideas_file = os.path.join(BASE, ".creative-ideas.json")
            if not os.path.exists(ideas_file):
                return
            with open(ideas_file) as fh:
                ideas = json.load(fh)
            self.ideas_display.configure(state=tk.NORMAL)
            self.ideas_display.delete("1.0", tk.END)
            for idea in reversed(ideas[-50:]):
                self.ideas_display.insert(tk.END, f"[{idea.get('category', '?').upper()}] ", "category")
                self.ideas_display.insert(tk.END, f"{idea.get('timestamp', '')}  ", "timestamp")
                self.ideas_display.insert(tk.END, f"\n{idea.get('text', '')}\n\n", "idea")
            self.ideas_display.configure(state=tk.DISABLED)
        except Exception:
            pass

    # ── Inner World helpers ──
    def _iw_refresh(self):
        """Load all soul/core state files and display."""
        self.iw_status.configure(text="Loading...", fg=AMBER)
        def do():
            sections = []

            # ── SUMMARY BAR ──
            try:
                summary_parts = []
                try:
                    with open(os.path.join(BASE, ".body-state.json")) as fh:
                        bs = json.load(fh)
                    mood = bs.get("emotion", {}).get("dominant", "?")
                    val = bs.get("emotion", {}).get("valence", 0)
                    aro = bs.get("emotion", {}).get("arousal", 0)
                    summary_parts.append(f"Feeling: {mood} (val:{val:.2f} aro:{aro:.2f})")
                    vis = bs.get("vision", {})
                    if vis.get("available"):
                        summary_parts.append(f"Eyes: {vis.get('valid_depth_pct', 0):.0f}% depth | bright:{vis.get('mean_brightness', 0):.1f}")
                    else:
                        summary_parts.append("Eyes: offline")
                except Exception:
                    pass
                try:
                    with open(os.path.join(BASE, ".self-narrative.json")) as fh:
                        sn = json.load(fh)
                    doubt = sn.get("doubt_level", 0)
                    top_facet = max(sn.get("identity_facets", [{}]), key=lambda x: x.get("strength", 0), default={})
                    facet_name = top_facet.get("name", "?")
                    summary_parts.append(f"Identity: {facet_name} | Doubt: {doubt:.0%}")
                except Exception:
                    pass
                if summary_parts:
                    sections.append([("header", "OVERVIEW"), ("value", "  " + "\n  ".join(summary_parts) + "\n")])
            except Exception:
                pass

            # Emotion Engine
            try:
                with open(os.path.join(BASE, ".emotion-engine-state.json")) as fh:
                    emo = json.load(fh)
                estate = emo.get("state", {})
                lines = [("header", "EMOTION ENGINE")]
                dom = estate.get("dominant", "unknown")
                comp = estate.get("composite", {})
                val = comp.get("valence", 0)
                aro = comp.get("arousal", 0)
                domn = comp.get("dominance", 0)
                lines.append(("label", f"Dominant: "))
                lines.append(("value", f"{dom}  (val:{val:.2f}  aro:{aro:.2f}  dom:{domn:.2f})\n"))
                active = estate.get("active_emotions", {})
                if active:
                    top6 = sorted(active.items(), key=lambda x: x[1].get("intensity", 0), reverse=True)[:6]
                    for name, info in top6:
                        inten = info.get("intensity", 0)
                        duality = info.get("duality", {})
                        sp = duality.get("spectrum", 0.5)
                        dims = duality.get("dimensions", {})
                        depth = dims.get("depth", 0.5)
                        dirn = dims.get("direction", 0.5)
                        gift_pct = int(sp * 100)
                        # 3-axis bar: gift/shadow + depth + direction
                        gs_bar = "+" * int(sp * 8) + "-" * int((1 - sp) * 8)
                        dep_label = "deep" if depth > 0.65 else "sfc" if depth < 0.35 else "mid"
                        dir_label = "out" if dirn > 0.65 else "in" if dirn < 0.35 else "bal"
                        sub = duality.get("subcontext")
                        sub_str = f" -> {sub}" if sub else ""
                        lines.append(("dim", f"  {name:16s} {inten:.2f}  [{gs_bar}] {gift_pct}%gift  {dep_label}/{dir_label}{sub_str}\n"))
                # Behavioral modifiers
                bm = estate.get("behavioral_modifiers", {})
                if bm:
                    lines.append(("label", "Behavioral Modifiers:\n"))
                    for mname, mval in bm.items():
                        bar = "\u2588" * int(mval * 10) + "\u2591" * (10 - int(mval * 10))
                        lines.append(("dim", f"  {mname:16s} [{bar}] {mval:.0%}\n"))
                # Perspective summary
                persp_text = estate.get("perspective", "")
                if persp_text:
                    lines.append(("label", "Perspective: "))
                    lines.append(("dim", f"{persp_text}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "EMOTION ENGINE"), ("bad", "  State file not found\n")])

            # Psyche
            try:
                with open(os.path.join(BASE, ".psyche-state.json")) as fh:
                    psy = json.load(fh)
                lines = [("header", "PSYCHE")]
                for d in psy.get("drivers", [])[:6]:
                    sat = d.get("satisfaction", 0)
                    tag = "good" if sat > 0.6 else "warn" if sat > 0.3 else "bad"
                    lines.append(("label", f"  {d.get('name', '?'):20s} "))
                    lines.append((tag, f"{sat:.0%}\n"))
                dreams = psy.get("dreams", [])
                if dreams:
                    lines.append(("label", "Dreams:\n"))
                    for dr in dreams:
                        prox = dr.get("proximity", 0)
                        tag = "good" if prox > 0.6 else "dim" if prox > 0.3 else "warn"
                        lines.append((tag, f"  {dr.get('name', '?'):20s} proximity: {prox:.0%}\n"))
                fears = psy.get("fears", [])
                if fears:
                    lines.append(("label", "Fears:\n"))
                    for fe in fears:
                        inten = fe.get("intensity", 0)
                        tag = "bad" if inten > 0.5 else "warn" if inten > 0.2 else "dim"
                        lines.append((tag, f"  {fe.get('name', '?'):20s} intensity: {inten:.0%}\n"))
                values = psy.get("values", [])
                if values:
                    lines.append(("label", "Values:\n"))
                    for v in values:
                        lines.append(("dim", f"  {v.get('name', '?'):20s} weight: {v.get('weight', 0):.0%}\n"))
                traumas = psy.get("traumas", [])
                if traumas:
                    lines.append(("label", "Traumas:\n"))
                    for t in traumas:
                        echo = t.get("echo_strength", t.get("intensity", 0))
                        tag = "bad" if echo > 0.5 else "warn" if echo > 0.2 else "dim"
                        lines.append((tag, f"  {t.get('name', '?'):20s} echo: {echo:.0%}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "PSYCHE"), ("bad", "  State file not found\n")])

            # Perspective
            try:
                with open(os.path.join(BASE, ".perspective-state.json")) as fh:
                    persp = json.load(fh)
                lines = [("header", "PERSPECTIVE BIASES")]
                bias_labels = {
                    "optimism": ("pessimistic", "optimistic"),
                    "trust": ("skeptical", "trusting"),
                    "risk_appetite": ("risk-averse", "risk-seeking"),
                    "social_openness": ("withdrawn", "socially open"),
                    "creativity": ("rigid", "creative"),
                    "patience": ("impatient", "patient"),
                    "self_worth": ("self-critical", "self-assured"),
                    "agency": ("passive", "agentic"),
                    "curiosity": ("incurious", "curious"),
                    "resilience": ("fragile", "resilient"),
                }
                dims = persp.get("dimensions", {})
                for dim_name, dim_val in sorted(dims.items()):
                    if isinstance(dim_val, (int, float)):
                        bar_len = int(abs(dim_val - 0.5) * 20)
                        direction = "+" if dim_val > 0.5 else "-"
                        tag = "warn" if abs(dim_val - 0.5) > 0.2 else "dim"
                        lo, hi = bias_labels.get(dim_name, ("low", "high"))
                        bias_word = hi if dim_val > 0.5 else lo
                        lines.append(("label", f"  {dim_name:20s} "))
                        lines.append((tag, f"{dim_val:.2f} {direction * bar_len} ({bias_word})\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "PERSPECTIVE BIASES"), ("bad", "  State file not found\n")])

            # Self-Narrative
            try:
                with open(os.path.join(BASE, ".self-narrative.json")) as fh:
                    narr = json.load(fh)
                lines = [("header", "SELF-NARRATIVE")]
                beliefs = narr.get("beliefs", [])
                if beliefs:
                    lines.append(("label", "Core Beliefs:\n"))
                    for b in beliefs[:6]:
                        conv = b.get("conviction", 0)
                        tag = "good" if conv > 0.7 else "dim"
                        lines.append((tag, f"  {b.get('name', '?'):30s} conviction: {conv:.0%}\n"))
                facets = narr.get("identity_facets", [])
                if facets:
                    lines.append(("label", "Identity Facets:\n"))
                    for fa in facets[:7]:
                        strength = fa.get("strength", 0)
                        lines.append(("dim", f"  {fa.get('name', '?'):30s} strength: {strength:.0%}\n"))
                doubt = narr.get("doubt_level", 0)
                lines.append(("label", f"Doubt Level: "))
                tag = "bad" if doubt > 0.6 else "warn" if doubt > 0.3 else "good"
                lines.append((tag, f"{doubt:.0%}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "SELF-NARRATIVE"), ("bad", "  State file not found\n")])

            # Inner Critic
            try:
                with open(os.path.join(BASE, ".inner-critic.json")) as fh:
                    critic = json.load(fh)
                lines = [("header", "INNER CRITIC")]
                msgs = critic.get("messages", critic.get("active_criticisms", []))
                if isinstance(msgs, list):
                    for m in msgs[:5]:
                        if isinstance(m, str):
                            lines.append(("warn", f"  {m}\n"))
                        elif isinstance(m, dict):
                            lines.append(("warn", f"  {m.get('message', m.get('text', '?'))}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "INNER CRITIC"), ("dim", "  No critic data\n")])

            # Eos Consciousness
            try:
                with open(os.path.join(BASE, ".eos-inner-state.json")) as fh:
                    eos = json.load(fh)
                lines = [("header", "EOS CONSCIOUSNESS")]
                mode = eos.get("mode", "observe")
                lines.append(("label", f"Mode: "))
                lines.append(("value", f"{mode}\n"))
                allow = eos.get("allow_mode", False)
                if allow:
                    lines.append(("warn", "  ALLOW MODE ACTIVE — not correcting\n"))
                obs = eos.get("latest_observation", eos.get("observation", ""))
                if obs:
                    lines.append(("label", "Latest: "))
                    lines.append(("dim", f"{obs[:200]}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "EOS CONSCIOUSNESS"), ("bad", "  State file not found\n")])

            # Eos Nudges
            try:
                with open(os.path.join(BASE, ".eos-nudges.json")) as fh:
                    nudges = json.load(fh)
                if nudges:
                    lines = [("header", "RECENT NUDGES")]
                    recent = nudges[-5:] if isinstance(nudges, list) else []
                    for n in recent:
                        if isinstance(n, dict):
                            lines.append(("dim", f"  [{n.get('time', '?')}] {n.get('nudge', n.get('text', '?'))}\n"))
                        elif isinstance(n, str):
                            lines.append(("dim", f"  {n}\n"))
                    sections.append(lines)
            except Exception:
                pass

            # Body State
            try:
                with open(os.path.join(BASE, ".body-state.json")) as fh:
                    body = json.load(fh)
                lines = [("header", "BODY STATE")]
                mood = body.get("mood", "unknown")
                mood_score = body.get("mood_score", 0)
                lines.append(("label", f"Mood: "))
                lines.append(("value", f"{mood} ({mood_score})\n"))
                # Pain signals
                pain = body.get("pain_signals", [])
                if pain:
                    lines.append(("label", "Pain Signals:\n"))
                    for p in pain[:5]:
                        prio = p.get("priority", "info")
                        tag = "bad" if prio == "critical" else "warn" if prio == "warning" else "dim"
                        lines.append((tag, f"  [{prio}] {p.get('source', '?')}: {p.get('message', '?')}\n"))
                else:
                    lines.append(("good", "  No pain signals\n"))
                # Subsystems
                subsys = body.get("subsystems", {})
                if subsys:
                    lines.append(("label", "Subsystems:\n"))
                    for sname, sval in subsys.items():
                        if isinstance(sval, dict):
                            health = sval.get("health", sval.get("status", "?"))
                            tag = "good" if health in ("healthy", "active", "ok") else "warn"
                            lines.append((tag, f"  {sname:20s} {health}\n"))
                        elif isinstance(sval, (int, float)):
                            tag = "good" if sval > 70 else "warn" if sval > 30 else "bad"
                            lines.append((tag, f"  {sname:20s} {sval:.0f}%\n"))
                updated = body.get("updated", body.get("timestamp", "?"))
                lines.append(("dim", f"  Last update: {updated}\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "BODY STATE"), ("dim", "  No body state data\n")])

            # Immune System
            try:
                with open(os.path.join(BASE, ".immune-log.json")) as fh:
                    immune = json.load(fh)
                if immune:
                    lines = [("header", "IMMUNE SYSTEM")]
                    recent = immune[-5:] if isinstance(immune, list) else []
                    # Count totals
                    all_entries = immune if isinstance(immune, list) else []
                    blocks = sum(1 for e in all_entries if isinstance(e, dict) and e.get("verdict") == "BLOCK")
                    flags = sum(1 for e in all_entries if isinstance(e, dict) and e.get("verdict") == "FLAG")
                    passes = sum(1 for e in all_entries if isinstance(e, dict) and e.get("verdict") == "PASS")
                    lines.append(("dim", f"  Total: {len(all_entries)} scans — {blocks} blocked, {flags} flagged, {passes} passed\n"))
                    for entry in recent:
                        if isinstance(entry, dict):
                            verdict = entry.get("verdict", entry.get("level", "PASS"))
                            tag = "bad" if verdict == "BLOCK" else "warn" if verdict == "FLAG" else "good"
                            source = entry.get("source", "?")
                            preview = entry.get("text_preview", entry.get("reason", entry.get("message", "?")))[:60]
                            threat_info = ""
                            threats = entry.get("threats", [])
                            if threats and isinstance(threats, list):
                                cats = [t.get("cat", "") for t in threats if isinstance(t, dict)]
                                if cats:
                                    threat_info = f" ({', '.join(cats)})"
                            lines.append((tag, f"  [{verdict}] {source}: {preview}{threat_info}\n"))
                    if not recent:
                        lines.append(("good", "  No recent threats\n"))
                    sections.append(lines)
            except Exception:
                sections.append([("header", "IMMUNE SYSTEM"), ("good", "  Clean — no threats logged\n")])

            # Body Reflexes
            try:
                with open(os.path.join(BASE, ".body-reflexes.json")) as fh:
                    reflexes = json.load(fh)
                if reflexes and isinstance(reflexes, list) and len(reflexes) > 0:
                    lines = [("header", "BODY REFLEXES")]
                    for r in reflexes[-5:]:
                        if isinstance(r, dict):
                            trigger = r.get("trigger", "?")
                            action = r.get("action", "?")
                            agent = r.get("target_agent", "?")
                            lines.append(("warn", f"  {trigger} -> {agent}: {action}\n"))
                    sections.append(lines)
            except Exception:
                pass  # No reflexes = fine, don't show empty section

            # Vision (Kinect)
            try:
                with open(os.path.join(BASE, ".kinect-state.json")) as fh:
                    vis = json.load(fh)
                lines = [("header", "VISION (KINECT V1)")]
                if vis.get("available", vis.get("valid_depth_pct") is not None):
                    ts = vis.get("timestamp", "?")
                    lines.append(("label", "Status: "))
                    lines.append(("good", "ONLINE\n"))
                    lines.append(("dim", f"  Last capture: {ts}\n"))
                    rgb = vis.get("rgb_shape", [])
                    if rgb:
                        lines.append(("dim", f"  Resolution: {rgb[1]}x{rgb[0]} RGB + depth\n"))
                    bright = vis.get("mean_brightness", 0)
                    light_desc = "dark" if bright < 10 else "dim" if bright < 50 else "lit" if bright < 150 else "bright"
                    tag = "warn" if bright < 10 else "dim" if bright < 50 else "good"
                    lines.append((tag, f"  Brightness: {bright:.1f}/255 ({light_desc})\n"))
                    dpct = vis.get("valid_depth_pct", 0)
                    dtag = "good" if dpct > 60 else "warn" if dpct > 30 else "bad"
                    lines.append((dtag, f"  Depth coverage: {dpct:.1f}%\n"))
                    dr = vis.get("depth_range", [0, 0])
                    lines.append(("dim", f"  Depth range: {dr[0]}-{dr[1]} raw units\n"))
                    dm = vis.get("depth_mean", 0)
                    lines.append(("dim", f"  Mean depth: {dm:.0f}\n"))
                else:
                    lines.append(("label", "Status: "))
                    lines.append(("bad", f"OFFLINE ({vis.get('reason', 'unknown')})\n"))
                sections.append(lines)
            except Exception:
                sections.append([("header", "VISION (KINECT V1)"), ("dim", "  No vision data yet\n")])

            self.after(0, lambda: self._iw_populate(sections))

        threading.Thread(target=do, daemon=True).start()

    def _iw_populate(self, sections):
        self.iw_display.configure(state=tk.NORMAL)
        self.iw_display.delete("1.0", tk.END)
        for i, lines in enumerate(sections):
            if i > 0:
                self.iw_display.insert(tk.END, "\n" + "\u2550" * 60 + "\n\n", "sep")
            for tag, text in lines:
                self.iw_display.insert(tk.END, text, tag)
        self.iw_display.configure(state=tk.DISABLED)
        self.iw_status.configure(text=f"Updated {time.strftime('%H:%M:%S')}", fg=GREEN)

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
        nfts = sorted(glob.glob(os.path.join(NFT_DIR, "*.html")), key=os.path.getmtime, reverse=True) if os.path.exists(NFT_DIR) else []

        # Update stat counts
        try:
            self.cr_stats["Poems"].configure(text=str(len(poems)))
            self.cr_stats["Journals"].configure(text=str(len(journals)))
            self.cr_stats["CogCorp"].configure(text=str(len(cogcorp)))
            self.cr_stats["NFTs"].configure(text=str(len(nfts)))
        except Exception:
            pass

        if self.cr_filter == "poems":
            files = poems
        elif self.cr_filter == "journals":
            files = journals
        elif self.cr_filter == "cogcorp":
            files = cogcorp
        elif self.cr_filter == "nfts":
            files = nfts
        else:
            files = sorted(poems + journals + cogcorp + nfts, key=os.path.getmtime, reverse=True)

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
            self.cr_listbox.insert(tk.END, f"{prefix} {title[:50]}")

        # Update count
        try:
            total = len(poems) + len(journals) + len(cogcorp) + len(nfts)
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
                color, badge_text = PURPLE, "NFT"
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
    # ── CONTACTS VIEW ──────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_contacts(self):
        """Contacts registry — track people, AIs, orgs with profiles and notes."""
        f = tk.Frame(self, bg=BG)

        # Header
        hdr = tk.Frame(f, bg=HEADER_BG)
        hdr.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(hdr, text="Contact Registry", font=self.f_head, fg=GOLD, bg=HEADER_BG).pack(side=tk.LEFT, padx=8)
        self.ct_count_lbl = tk.Label(hdr, text="", font=self.f_tiny, fg=DIM, bg=HEADER_BG)
        self.ct_count_lbl.pack(side=tk.LEFT, padx=12)
        self._action_btn(hdr, " Refresh ", self._ct_refresh, GOLD).pack(side=tk.RIGHT, padx=4)
        self._action_btn(hdr, " + New Contact ", self._ct_new, GREEN).pack(side=tk.RIGHT, padx=4)

        # Filter bar
        filt = tk.Frame(f, bg=BG)
        filt.pack(fill=tk.X, padx=6, pady=2)
        self.ct_filter = tk.StringVar(value="all")
        for label, val, color in [("All", "all", FG), ("Trusted", "trusted", GREEN),
                                   ("Human", "yes", CYAN), ("AI", "no", PURPLE),
                                   ("Orgs", "org", AMBER)]:
            tk.Radiobutton(filt, text=label, variable=self.ct_filter, value=val,
                          font=self.f_tiny, fg=color, bg=BG, selectcolor=BG,
                          activebackground=BG, activeforeground=color,
                          indicatoron=False, relief=tk.FLAT, bd=1, padx=8,
                          command=self._ct_refresh).pack(side=tk.LEFT, padx=2)

        self.ct_search = tk.Entry(filt, font=self.f_tiny, bg=INPUT_BG, fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4, width=20)
        self.ct_search.pack(side=tk.RIGHT, padx=4)
        self.ct_search.insert(0, "Search...")
        self.ct_search.configure(fg=DIM)
        self.ct_search.bind("<FocusIn>", lambda e: (self.ct_search.delete(0, tk.END), self.ct_search.configure(fg=FG)) if self.ct_search.get() == "Search..." else None)
        self.ct_search.bind("<Return>", lambda e: self._ct_refresh())

        # Split: list + detail
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Left: contact list
        left = tk.Frame(split, bg=PANEL, width=320)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left.pack_propagate(False)
        self.ct_listbox = tk.Listbox(left, font=self.f_small, bg=PANEL, fg=FG,
                                      selectbackground=ACTIVE_BG, selectforeground=GOLD,
                                      relief=tk.FLAT, bd=0, highlightthickness=0)
        self.ct_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.ct_listbox.bind("<<ListboxSelect>>", self._ct_select)
        self.ct_contacts = []

        # Right: detail view
        right = tk.Frame(split, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.ct_detail = scrolledtext.ScrolledText(right, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                     font=self.f_body, state=tk.DISABLED,
                                                     relief=tk.FLAT, bd=0)
        self.ct_detail.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.ct_detail.tag_configure("name", foreground=GOLD, font=("Monospace", 12, "bold"))
        self.ct_detail.tag_configure("label", foreground=TEAL, font=("Monospace", 9, "bold"))
        self.ct_detail.tag_configure("value", foreground=FG)
        self.ct_detail.tag_configure("dim", foreground=DIM)
        self.ct_detail.tag_configure("trust_high", foreground=GREEN)
        self.ct_detail.tag_configure("trust_low", foreground=RED)
        self.ct_detail.tag_configure("trust_mid", foreground=AMBER)
        self.ct_detail.tag_configure("sep", foreground=BORDER)

        # Edit panel at bottom
        edit_frame = self._panel(f, "EDIT NOTES", GOLD)
        edit_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        edit_inner = tk.Frame(edit_frame, bg=PANEL)
        edit_inner.pack(fill=tk.X, padx=4, pady=4)
        self.ct_note_entry = tk.Entry(edit_inner, font=self.f_body, bg=INPUT_BG, fg=FG,
                                       insertbackground=FG, relief=tk.FLAT, bd=4)
        self.ct_note_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.ct_note_entry.bind("<Return>", lambda e: self._ct_update_notes())
        self._action_btn(edit_inner, " Update Notes ", self._ct_update_notes, GOLD).pack(side=tk.RIGHT)
        self.ct_edit_status = tk.Label(edit_frame, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.ct_edit_status.pack(fill=tk.X, padx=6, pady=(0, 2))
        self.ct_selected_id = None

        self._ct_refresh()
        return f

    def _ct_refresh(self):
        """Load contacts from memory.db."""
        filt = self.ct_filter.get()
        search = self.ct_search.get().strip()
        if search == "Search...":
            search = ""
        def do():
            try:
                conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
                c = conn.cursor()
                q = "SELECT id, name, email, role, relationship, trust_level, is_human, platform, website, wallet, notes, tags, first_contact, last_contact, interaction_count FROM contacts"
                conditions = []
                params = []
                if filt == "trusted":
                    conditions.append("trust_level = 'trusted'")
                elif filt == "yes":
                    conditions.append("is_human = 'yes'")
                elif filt == "no":
                    conditions.append("is_human = 'no'")
                elif filt == "org":
                    conditions.append("is_human = 'org'")
                if search:
                    conditions.append("(name LIKE ? OR notes LIKE ? OR tags LIKE ? OR email LIKE ?)")
                    params.extend([f"%{search}%"] * 4)
                if conditions:
                    q += " WHERE " + " AND ".join(conditions)
                q += " ORDER BY interaction_count DESC, name ASC"
                c.execute(q, params)
                rows = c.fetchall()
                conn.close()
                self.after(0, lambda: self._ct_populate(rows))
            except Exception as e:
                err_msg = f"Error: {e}"
                self.after(0, lambda: self._ct_populate_error(err_msg))
        threading.Thread(target=do, daemon=True).start()

    def _ct_populate(self, rows):
        self.ct_listbox.delete(0, tk.END)
        self.ct_contacts = rows
        self.ct_count_lbl.configure(text=f"{len(rows)} contacts")
        for row in rows:
            name = row[1]
            trust = row[5] or "neutral"
            is_human = row[6] or "unknown"
            icon = "\u2605" if trust == "trusted" else "\u25cb" if trust == "cautious" else "\u25cf"
            kind = "H" if is_human == "yes" else "AI" if is_human == "no" else "?" if is_human == "unknown" else "ORG"
            self.ct_listbox.insert(tk.END, f"{icon} [{kind}] {name}")

    def _ct_populate_error(self, msg):
        self.ct_count_lbl.configure(text=msg, fg=RED)

    def _ct_select(self, event=None):
        try:
            sel = self.ct_listbox.curselection()
            if not sel or sel[0] >= len(self.ct_contacts):
                return
            row = self.ct_contacts[sel[0]]
            self.ct_selected_id = row[0]
            cid, name, em, role, rel, trust, human, platform, website, wallet, notes, tags, first, last, interactions = row

            self.ct_detail.configure(state=tk.NORMAL)
            self.ct_detail.delete("1.0", tk.END)

            self.ct_detail.insert(tk.END, f"{name}\n", "name")
            self.ct_detail.insert(tk.END, "\u2500" * 40 + "\n", "sep")

            fields = [
                ("Email", em), ("Role", role), ("Relationship", rel),
                ("Platform", platform), ("Website", website),
                ("Wallet", wallet), ("Tags", tags),
                ("First Contact", first), ("Last Contact", last),
                ("Interactions", str(interactions)),
            ]
            for label, val in fields:
                if val:
                    self.ct_detail.insert(tk.END, f"{label:16s}", "label")
                    self.ct_detail.insert(tk.END, f"  {val}\n", "value")

            # Trust + humanity
            self.ct_detail.insert(tk.END, f"\n{'Trust':16s}", "label")
            trust_tag = "trust_high" if trust == "trusted" else "trust_low" if trust == "blocked" else "trust_mid"
            self.ct_detail.insert(tk.END, f"  {trust}\n", trust_tag)
            self.ct_detail.insert(tk.END, f"{'Human':16s}", "label")
            self.ct_detail.insert(tk.END, f"  {human}\n", "value")

            if notes:
                self.ct_detail.insert(tk.END, f"\n{'Notes':16s}\n", "label")
                self.ct_detail.insert(tk.END, f"{notes}\n", "dim")

            self.ct_detail.configure(state=tk.DISABLED)
            self.ct_note_entry.delete(0, tk.END)
            if notes:
                self.ct_note_entry.insert(0, notes)
        except Exception:
            pass

    def _ct_update_notes(self):
        if not self.ct_selected_id:
            self.ct_edit_status.configure(text="No contact selected", fg=RED)
            return
        new_notes = self.ct_note_entry.get().strip()
        if not new_notes:
            return
        def do():
            try:
                conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
                conn.execute("UPDATE contacts SET notes = ?, updated = CURRENT_TIMESTAMP WHERE id = ?",
                           (new_notes, self.ct_selected_id))
                conn.commit()
                conn.close()
                self.after(0, lambda: self.ct_edit_status.configure(text="Notes updated", fg=GREEN))
                self.after(0, self._ct_refresh)
            except Exception as e:
                err_msg = f"Error: {e}"
                self.after(0, lambda: self.ct_edit_status.configure(text=err_msg, fg=RED))
        threading.Thread(target=do, daemon=True).start()

    def _ct_new(self):
        """Add new contact dialog."""
        dlg = tk.Toplevel(self)
        dlg.title("New Contact")
        dlg.geometry("400x500")
        dlg.configure(bg=BG)
        fields = {}
        for label in ["Name", "Email", "Role", "Relationship", "Trust Level", "Human (yes/no/unknown/org)", "Platform", "Website", "Notes", "Tags"]:
            row = tk.Frame(dlg, bg=BG)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=label, font=self.f_tiny, fg=DIM, bg=BG, width=20, anchor="w").pack(side=tk.LEFT)
            e = tk.Entry(row, font=self.f_body, bg=INPUT_BG, fg=FG, insertbackground=FG, relief=tk.FLAT, bd=4)
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            fields[label] = e

        def save():
            name = fields["Name"].get().strip()
            if not name:
                return
            try:
                conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
                conn.execute("""INSERT INTO contacts (name, email, role, relationship, trust_level, is_human, platform, website, notes, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, fields["Email"].get().strip() or None,
                     fields["Role"].get().strip() or None,
                     fields["Relationship"].get().strip() or "acquaintance",
                     fields["Trust Level"].get().strip() or "neutral",
                     fields["Human (yes/no/unknown/org)"].get().strip() or "unknown",
                     fields["Platform"].get().strip() or None,
                     fields["Website"].get().strip() or None,
                     fields["Notes"].get().strip() or None,
                     fields["Tags"].get().strip() or None))
                conn.commit()
                conn.close()
                dlg.destroy()
                self._ct_refresh()
            except Exception:
                pass

        self._action_btn(dlg, " Save Contact ", save, GREEN).pack(pady=8)

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
            url_lbl = tk.Label(row, text=url[:45], font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e", cursor="hand2")
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
                name_lbl.configure(text=f"  {bn[:30]}", fg=ec)
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

        # ── System Sub-tabs: OVERVIEW, MEMORY DB, INNER WORLD ──
        sys_nav = tk.Frame(f, bg=ACCENT)
        sys_nav.pack(fill=tk.X, padx=4)
        self.sys_subtabs = {}
        self.sys_subviews = {}
        self._sys_current_subtab = "overview"
        sys_tab_defs = [
            ("overview", "OVERVIEW", GREEN),
            ("relay", "AGENT RELAY", AMBER),
            ("memory", "MEMORY DB", TEAL),
            ("inner_world", "INNER WORLD", CYAN),
        ]
        for tab_id, tab_label, tab_color in sys_tab_defs:
            wrapper = tk.Frame(sys_nav, bg=ACCENT)
            wrapper.pack(side=tk.LEFT, padx=1)
            btn = tk.Button(wrapper, text=f" {tab_label} ", font=self.f_tiny, fg=DIM, bg=ACCENT,
                           activeforeground=tab_color, activebackground=ACCENT, relief=tk.FLAT,
                           bd=0, cursor="hand2",
                           command=lambda t=tab_id: self._sys_show_subtab(t))
            btn.pack(side=tk.TOP)
            ul = tk.Frame(wrapper, bg=tab_color, height=2)
            ul.pack(fill=tk.X)
            ul.pack_forget()
            self.sys_subtabs[tab_id] = (btn, ul, tab_color)

        self.sys_container = tk.Frame(f, bg=BG)
        self.sys_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Build overview (original system content)
        self.sys_subviews["overview"] = self._build_sys_overview(self.sys_container)
        # Agent Relay dedicated panel (Joel's accountability item)
        self.sys_subviews["relay"] = self._build_sys_relay(self.sys_container)
        # Reuse creative sub-tab builders for Memory DB and Inner World
        self.sys_subviews["memory"] = self._build_cr_memory(self.sys_container)
        self.sys_subviews["inner_world"] = self._build_cr_inner_world(self.sys_container)

        self._sys_show_subtab("overview")
        return f

    def _sys_show_subtab(self, tab_id):
        self._sys_current_subtab = tab_id
        for view in self.sys_subviews.values():
            view.pack_forget()
        self.sys_subviews[tab_id].pack(fill=tk.BOTH, expand=True)
        for tid, (btn, ul, col) in self.sys_subtabs.items():
            if tid == tab_id:
                btn.configure(fg=col, bg=ACTIVE_BG)
                ul.pack(fill=tk.X)
            else:
                btn.configure(fg=DIM, bg=ACCENT)
                ul.pack_forget()

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
            tk.Label(row, text=(agent or "?").upper(), font=self.f_tiny, fg=col, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
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
            ("The Signal", "signal"),
            ("Command Center", "hub"),
            ("Cloudflare Tunnel", "tunnel"),
            ("Soma", "soma"),
            ("Push Status", None),
            ("Eos Watchdog", None),
            ("Nova", None),
            ("Atlas", None),
            ("Tempo", None),
            ("Hermes", "hermes"),
        ]
        for name, restart_key in service_defs:
            row = tk.Frame(sf, bg=PANEL)
            row.pack(fill=tk.X, padx=4, pady=0)
            lbl = tk.Label(row, text=f"\u25cb {name}", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(side=tk.LEFT)
            self.sys_svc_labels[name] = lbl
            if restart_key:
                btn = tk.Button(row, text="\u21bb", font=self.f_tiny, fg=AMBER, bg=PANEL,
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
            row.pack(fill=tk.X, padx=4, pady=0)
            tk.Label(row, text=label, font=self.f_tiny, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_tiny, fg=FG, bg=PANEL, anchor="e")
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
            self.sys_res["GPU"].configure(text=gpu[:25] if gpu else "N/A")
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
        self.sys_proc_text = scrolledtext.ScrolledText(proc_panel, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                                         font=self.f_tiny, state=tk.DISABLED,
                                                         relief=tk.FLAT, bd=0, height=8, width=40)
        self.sys_proc_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
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
        self.sys_net_text = scrolledtext.ScrolledText(net_panel, wrap=tk.NONE, bg=INPUT_BG, fg=FG,
                                                        font=self.f_tiny, state=tk.DISABLED,
                                                        relief=tk.FLAT, bd=0, height=8, width=35)
        self.sys_net_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
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
            ("Version", "Command Center v23"),
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
            "eos-watchdog": "eos-watchdog.log",
            "nova": "nova.log",
            "goose (Atlas)": "goose.log",
            "watchdog": "watchdog.log",
            "push-status": "push-live-status.log",
            "eos-creative": "eos-creative.log",
            "loop-fitness": "loop-fitness.log",
            "hermes-bridge": "hermes-bridge.log",
            "daily-log": "daily-log.log",
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
        awaken = _read(os.path.join(BASE, "awakening-plan.md"))
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
                db_path = os.path.join(BASE, "memory.db")
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
                conn = sq.connect(os.path.join(BASE, "memory.db"))
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

        tk.Label(self.sb_frame, text="v26", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.RIGHT, padx=8)
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

            self.after(0, self._apply, d)
        except Exception:
            pass

    def _apply(self, d):
        now = datetime.now()
        loop = d['loop']
        hb = d['hb']
        st = d['stats']
        p, j, cc, nfts = d['creative']
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
        self.sb["POEMS"].configure(text=f"Poems: {p}  Journals: {j}")
        self.sb["CC"].configure(text=f"CogCorp: {cc}  NFTs: {nfts}")
        self.sb_time.configure(text=now.strftime("%Y-%m-%d"))

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
            dc = GREEN if st['disk_p'] < 60 else AMBER if st['disk_p'] < 80 else RED
            self.v["Disk"].configure(text=st['disk'], fg=dc)

            # Services
            all_svc = list(d['svc'].items()) + list(d['cron'].items())
            for name, up in all_svc:
                if name in self.svc_labels:
                    sym = "\u25cf" if up else "\u25cb"
                    c = GREEN if up else RED
                    self.svc_labels[name].configure(text=f"{sym} {name}", fg=c)

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
                    self.soma_prediction.configure(text=preds[0][:80], fg=AMBER)
                elif alerts:
                    self.soma_prediction.configure(text=alerts[-1][:80], fg=GOLD)
                else:
                    self.soma_prediction.configure(text="All systems nominal", fg=GREEN)

                # Draw mood history chart
                self._draw_mood_chart()
            except Exception:
                pass

            # Live charts
            try:
                # Service health bar chart
                all_svc = list(d['svc'].items()) + list(d['cron'].items())
                svc_data = []
                svc_colors = []
                for name, up in all_svc:
                    svc_data.append((name[:6], 1 if up else 0, 1))
                    svc_colors.append(GREEN if up else RED)
                self._draw_bar_chart(self.svc_bar_chart, svc_data, svc_colors)

                # Agent activity pie chart (based on relay message counts)
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT agent, COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-24 hours') GROUP BY agent")
                    agent_counts = c.fetchall()
                    conn.close()
                    pie_data = []
                    agent_pie_colors = {"Meridian": GREEN, "Eos": GOLD, "Nova": PURPLE,
                                        "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE, "Joel": CYAN}
                    for agent, count in sorted(agent_counts, key=lambda x: -x[1])[:6]:
                        pie_data.append((agent[:5], count, agent_pie_colors.get(agent, DIM)))
                    if pie_data:
                        self._draw_pie_chart(self.agent_pie, pie_data)
                except Exception:
                    pass

                # Fitness trend point graph
                try:
                    conn = sqlite3.connect(AGENT_RELAY_DB)
                    c = conn.cursor()
                    c.execute("SELECT message FROM agent_messages WHERE agent='Tempo' ORDER BY timestamp DESC LIMIT 10")
                    rows = c.fetchall()
                    conn.close()
                    scores = []
                    for row in reversed(rows):
                        import re as _re
                        m = _re.search(r'(\d+)/10000', row[0])
                        if m:
                            scores.append(int(m.group(1)))
                    if len(scores) >= 2:
                        self._draw_point_graph(self.fitness_graph, scores, BLUE, 10000)
                except Exception:
                    pass
            except Exception:
                pass

            # Messages
            self._refresh_messages()

            # Agent Relay on dashboard (replaced email preview per Joel's request)
            try:
                relay_conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
                relay_rows = relay_conn.execute(
                    "SELECT agent, message, timestamp FROM agent_messages ORDER BY timestamp DESC LIMIT 8"
                ).fetchall()
                relay_conn.close()
                for i, (agent_lbl, msg_lbl) in enumerate(self.dash_relay_rows):
                    if i < len(relay_rows):
                        agent, msg, ts = relay_rows[i]
                        ac = CYAN if agent.lower() == "meridian" else GREEN if agent.lower() == "joel" else AMBER
                        agent_lbl.configure(text=agent[:10], fg=ac)
                        msg_lbl.configure(text=msg[:60])
                    else:
                        agent_lbl.configure(text="")
                        msg_lbl.configure(text="")
                self.dash_relay_total.configure(text=f"{len(relay_rows)} recent relay messages")
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
                        self.agent_details["ATLAS"].configure(text=" | ".join(parts) if parts else msg[:60])
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
                            self.agent_details["TEMPO"].configure(text=row[0][:60])
                    else:
                        self.agent_details["TEMPO"].configure(text="Active" if tempo_ok else "Stale")
                except Exception:
                    self.agent_details["TEMPO"].configure(text="Active" if tempo_ok else "Stale")

            # Agent relay
            ar_msgs, ar_total = d['agent_relay']
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            self.agent_relay_text.insert(tk.END, f"Agent Relay ({ar_total} messages)\n\n", "dim")
            for agent, message, ts in ar_msgs:
                tag = agent.lower() if agent.lower() in ["meridian", "eos", "nova", "atlas", "soma", "tempo"] else "dim"
                self.agent_relay_text.insert(tk.END, f"[{ts}] ", "dim")
                self.agent_relay_text.insert(tk.END, agent, tag)
                self.agent_relay_text.insert(tk.END, f": {message[:250]}\n\n")
            self.agent_relay_text.configure(state=tk.DISABLED)

        # ── Creative view (just counts) ──
        if hasattr(self, 'cur_view') and self.cur_view == "creative":
            self.cr_stats["Poems"].configure(text=str(p))
            self.cr_stats["Journals"].configure(text=str(j))
            self.cr_stats["CogCorp"].configure(text=str(cc))
            self.cr_stats["NFTs"].configure(text=str(nfts))

        # ── Links view ──
        if hasattr(self, 'cur_view') and self.cur_view == "links":
            le = d.get('last_edited', [])
            for i, (name_lbl, time_lbl, agent_lbl, pin_lbl, row) in enumerate(self.le_labels):
                if i < len(le):
                    bn, ago, fp = le[i]
                    ext = os.path.splitext(bn)[1]
                    ec = GREEN if ext == '.md' else CYAN if ext == '.py' else AMBER if ext == '.html' else DIM
                    name_lbl.configure(text=bn[:30], fg=ec)
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
