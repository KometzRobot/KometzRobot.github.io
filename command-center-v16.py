#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v21

Full revamp per Joel's requests:
- Real action buttons (not just text commands)
- Redesigned tabs: Dashboard, Email, Agents, Creative, Links, System
- Dashboard messages integrated into main view
- Last-edited files, lively design, proper colors
- Eos section fixed (compact, relevant)
- Agent tab beefed up
- Creative tab shows all file types
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

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1143
SMTP_HOST, SMTP_PORT = "127.0.0.1", 1025
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")
JOEL = "jkometz@hotmail.com"

OLLAMA = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"

# ── COLORS ────────────────────────────────────────────────────────
BG = "#0a0a12"
HEADER_BG = "#06060e"
PANEL = "#12121c"
PANEL2 = "#161622"
INPUT_BG = "#0e0e18"
BORDER = "#1e1e30"
ACCENT = "#1a1a2e"
ACTIVE_BG = "#2a2a40"
FG = "#c8c8d8"
DIM = "#4a4a6a"
BRIGHT = "#e0e0f0"
GREEN = "#00e87b"
GREEN2 = "#00c868"
CYAN = "#00d4ff"
CYAN2 = "#0098cc"
AMBER = "#ffaa00"
AMBER2 = "#cc8800"
RED = "#ff3355"
GOLD = "#d4a017"
WHITE = "#e8e8f0"
PURPLE = "#b388ff"
PINK = "#ff66cc"
TEAL = "#00ccaa"
BLUE = "#4488ff"


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
        "Proton Bridge": "protonmail-bridge",
        "Ollama": "ollama serve",
        "The Signal": "the-signal",
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
    p = len(glob.glob(os.path.join(BASE, "poem-*.md")))
    j = len(glob.glob(os.path.join(BASE, "journal-*.md")))
    exclude = {"cogcorp-gallery.html", "cogcorp-article.html"}
    cc = len([f for f in glob.glob(os.path.join(BASE, "website", "cogcorp-*.html"))
              if os.path.basename(f) not in exclude])
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
    "Atlas": TEAL, "Soma": AMBER, "Tempo": BLUE,
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
        r = subprocess.run(
            ['git', 'push', 'origin', 'master'],
            capture_output=True, text=True, timeout=30, cwd=BASE)
        if r.returncode == 0:
            return "Push OK"
        return f"Push failed: {r.stderr[:100]}"
    except Exception as e:
        return f"Error: {e}"

def action_restart_service(name):
    """Restart services via systemd."""
    systemd_map = {
        "bridge": ("system", "protonmail-bridge"),
        "nova": ("cron", None),  # cron-based, just run it
        "signal": ("user", "meridian-web-dashboard"),
        "hub": ("user", "meridian-hub-v16"),
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


# ── APP ───────────────────────────────────────────────────────────
class V16(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MERIDIAN COMMAND CENTER v21")
        self.configure(bg=BG)
        self.minsize(1000, 600)
        # Fullscreen by default (per Joel's request)
        self.attributes('-fullscreen', True)
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.bind('<F11>', lambda e: self.attributes('-fullscreen',
                  not self.attributes('-fullscreen')))

        # Fonts
        self.f_title = tkfont.Font(family="Monospace", size=14, weight="bold")
        self.f_head = tkfont.Font(family="Monospace", size=11, weight="bold")
        self.f_sect = tkfont.Font(family="Monospace", size=9, weight="bold")
        self.f_body = tkfont.Font(family="Monospace", size=9)
        self.f_small = tkfont.Font(family="Monospace", size=8)
        self.f_tiny = tkfont.Font(family="Monospace", size=7)
        self.f_big = tkfont.Font(family="Monospace", size=24, weight="bold")
        self.f_med = tkfont.Font(family="Monospace", size=16, weight="bold")

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
        tk.Label(h, text="v21", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

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
            "creative": PURPLE, "links": PINK, "system": TEAL,
        }
        tabs = [
            ("dash", "DASHBOARD"),
            ("email", "EMAIL"),
            ("agents", "AGENTS"),
            ("creative", "CREATIVE"),
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
                      "Push Status", "Eos Watchdog", "Nova", "Atlas", "Tempo"]:
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
        ]
        for i, (label, cmd, color) in enumerate(buttons):
            b = self._action_btn(btn_grid, label, cmd, color, width=14)
            b.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        btn_grid.columnconfigure(2, weight=1)

        # ── RESOURCE GRAPHS (CPU + RAM live sparklines) ──
        res_graph_frame = tk.Frame(f, bg=BG)
        res_graph_frame.pack(fill=tk.X, padx=6, pady=2)

        cpu_panel = self._panel(res_graph_frame, "CPU LOAD", GREEN)
        cpu_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.cpu_graph = tk.Canvas(cpu_panel, height=45, bg=INPUT_BG, highlightthickness=0)
        self.cpu_graph.pack(fill=tk.X, padx=4, pady=4)

        ram_panel = self._panel(res_graph_frame, "RAM USAGE", TEAL)
        ram_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.ram_graph = tk.Canvas(ram_panel, height=45, bg=INPUT_BG, highlightthickness=0)
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
                      ("Atlas", TEAL), ("Soma", AMBER), ("Tempo", BLUE)]
        for aname, acolor in agent_list:
            dot = tk.Label(soma_row1, text=f"\u25cf {aname}", font=self.f_tiny, fg=DIM, bg=PANEL)
            dot.pack(side=tk.LEFT, padx=3)
            self.soma_agents[aname] = (dot, acolor)

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

        # Right: Recent Email
        ef = self._panel(mid, "RECENT EMAIL", PURPLE)
        ef.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.email_list = tk.Frame(ef, bg=PANEL)
        self.email_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.email_rows = []
        for _ in range(8):
            row = tk.Frame(self.email_list, bg=PANEL)
            row.pack(fill=tk.X)
            name_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, width=14, anchor="w")
            name_lbl.pack(side=tk.LEFT)
            subj_lbl = tk.Label(row, text="", font=self.f_tiny, fg=FG, bg=PANEL, anchor="w")
            subj_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.email_rows.append((name_lbl, subj_lbl))
        self.email_total = tk.Label(ef, text="", font=self.f_tiny, fg=PURPLE, bg=PANEL, anchor="e")
        self.email_total.pack(fill=tk.X, padx=8, pady=(0, 2))

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

    def _draw_sparkline(self, canvas, data, color, max_val=100.0, label="", current=""):
        """Draw a sparkline graph with filled area under the line."""
        try:
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 20 or h < 10 or len(data) < 2:
                return
            pad = 2
            cw = w - pad * 2
            ch = h - pad * 2
            n = len(data)
            # Plot points
            points = []
            for i, val in enumerate(data):
                x = pad + (i / max(n - 1, 1)) * cw
                y = pad + ch - (min(val, max_val) / max_val * ch)
                points.append((x, y))
            # Fill area under line
            fill_points = [(pad, h - pad)] + points + [(pad + cw, h - pad)]
            flat = []
            for px, py in fill_points:
                flat.extend([px, py])
            # Dim fill
            fill_color = color.replace("ff", "44").replace("ee", "22")
            canvas.create_polygon(*flat, fill=fill_color if len(fill_color) == 7 else "#0a1a10",
                                  outline="", stipple="")
            # Line
            for i in range(1, len(points)):
                canvas.create_line(points[i-1][0], points[i-1][1],
                                   points[i][0], points[i][1],
                                   fill=color, width=1.5)
            # Current value label (right side)
            if current:
                canvas.create_text(w - pad - 2, pad + 2, text=current, anchor="ne",
                                   font=("Monospace", 7, "bold"), fill=color)
            # Label (left side)
            if label:
                canvas.create_text(pad + 2, pad + 2, text=label, anchor="nw",
                                   font=("Monospace", 6), fill=DIM)
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
        tk.Label(to_row, text="To:", font=self.f_small, fg=DIM, bg=PANEL, width=8, anchor="w").pack(side=tk.LEFT)
        self.email_to = tk.Entry(to_row, font=self.f_body, bg=INPUT_BG, fg=FG,
                                 insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_to.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 8))
        # Quick recipients
        tk.Label(to_row, text="Quick:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT, padx=(4, 2))
        for name, addr, col in [("Joel", JOEL, CYAN), ("Sammy", "sammyqjankis@proton.me", PURPLE),
                                 ("Loom", "not.taskyy@gmail.com", TEAL)]:
            tk.Button(to_row, text=f" {name} ", font=self.f_tiny, fg=col, bg=BORDER, relief=tk.FLAT,
                     cursor="hand2", bd=0, padx=4,
                     command=lambda a=addr: (self.email_to.delete(0, tk.END), self.email_to.insert(0, a))
                     ).pack(side=tk.LEFT, padx=2)

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
                    _, msg_data = m.fetch(eid, "(RFC822)")
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
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body_text = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                    else:
                        body_text = msg.get_payload(decode=True).decode("utf-8", errors="replace")
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
        self.chat_display.tag_configure("tempo", foreground="#4a9eff")
        self.chat_display.tag_configure("meridian", foreground=GREEN)
        self.chat_display.tag_configure("sys", foreground=DIM)

        inp = tk.Frame(agent_chat, bg=PANEL)
        inp.pack(fill=tk.X, padx=4, pady=(0, 4))

        # Agent selector (includes All Agents broadcast)
        self.chat_agent = tk.StringVar(value="Eos")
        agent_colors = {"All Agents": WHITE, "Eos": GOLD, "Atlas": TEAL, "Nova": PURPLE,
                        "Soma": AMBER, "Tempo": "#4a9eff", "Meridian": GREEN}
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
            factors = state.get("mood_factors", {})
            info = f"Mood: {mood} (score: {score})"
            if factors:
                info += "\nFactors: " + ", ".join(f"{k}={v}" for k, v in list(factors.items())[:6])
            self.chat_display.insert(tk.END, f"[Soma] {info}\n", "soma")
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
        tag = agent.lower() if agent.lower() in ["eos", "atlas", "nova", "soma", "tempo", "meridian"] else "sys"
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
            ("ai_review", "AI REVIEW", CYAN),
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
        self.cr_subviews["ai_review"] = self._build_cr_ai_review(self.cr_container)

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

    def _build_cr_ai_review(self, parent):
        """AI Review — send creative work to Eos for feedback."""
        f = tk.Frame(parent, bg=BG)

        tk.Label(f, text="AI Creative Review", font=self.f_head, fg=CYAN, bg=BG).pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(f, text="Send text to Eos (local AI) for creative feedback, suggestions, or brainstorming.", font=self.f_tiny, fg=DIM, bg=BG).pack(fill=tk.X, padx=8)

        # Input
        input_frame = self._panel(f, "YOUR TEXT", CYAN)
        input_frame.pack(fill=tk.X, padx=4, pady=4)
        self.ai_input = tk.Text(input_frame, font=self.f_body, bg=INPUT_BG, fg=FG,
                                 insertbackground=FG, relief=tk.FLAT, bd=4, height=8)
        self.ai_input.pack(fill=tk.X, padx=6, pady=4)

        btn_row = tk.Frame(input_frame, bg=PANEL)
        btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        self.ai_prompt_type = tk.StringVar(value="review")
        for ptype, label in [("review", "Review"), ("continue", "Continue Writing"),
                              ("brainstorm", "Brainstorm"), ("critique", "Critique")]:
            tk.Radiobutton(btn_row, text=label, variable=self.ai_prompt_type, value=ptype,
                          font=self.f_tiny, fg=CYAN, bg=PANEL, selectcolor=PANEL,
                          activebackground=PANEL, activeforeground=CYAN,
                          indicatoron=False, relief=tk.FLAT, bd=1, padx=6).pack(side=tk.LEFT, padx=2)
        self._action_btn(btn_row, " Send to Eos ", self._ai_send, CYAN).pack(side=tk.RIGHT, padx=4)
        self.ai_status = tk.Label(btn_row, text="", font=self.f_tiny, fg=DIM, bg=PANEL)
        self.ai_status.pack(side=tk.RIGHT, padx=8)

        # Response
        resp_frame = self._panel(f, "EOS RESPONSE", GOLD)
        resp_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.ai_response = scrolledtext.ScrolledText(resp_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_body, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0)
        self.ai_response.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

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
            "All": [(BASE, "*.md"), (os.path.join(BASE, "website"), "*.html"),
                    (os.path.join(BASE, "gig-products"), "*.go"), (os.path.join(BASE, "nft-prototypes"), "*.html")],
            "Poems": [(BASE, "poem-*.md")],
            "Journals": [(BASE, "journal-*.md")],
            "CogCorp": [(os.path.join(BASE, "website"), "cogcorp-*.html")],
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

    # ── AI Review helpers ──
    def _ai_send(self):
        text = self.ai_input.get("1.0", tk.END).strip()
        if not text:
            return
        ptype = self.ai_prompt_type.get()
        prompts = {
            "review": f"Please review this creative writing and share your thoughts:\n\n{text}",
            "continue": f"Continue this piece of writing in the same style and voice:\n\n{text}",
            "brainstorm": f"Brainstorm related ideas, themes, and directions for this:\n\n{text}",
            "critique": f"Provide honest constructive critique of this writing — what works, what doesn't, what to improve:\n\n{text}",
        }
        prompt = prompts.get(ptype, prompts["review"])
        self.ai_status.configure(text="Asking Eos...", fg=AMBER)
        self.ai_response.configure(state=tk.NORMAL)
        self.ai_response.delete("1.0", tk.END)
        self.ai_response.insert("1.0", "Waiting for Eos...")
        self.ai_response.configure(state=tk.DISABLED)

        def do():
            try:
                resp = query_agent("Eos", prompt, "Joel")
                self.after(0, lambda: self._ai_show_response(resp))
            except Exception as e:
                self.after(0, lambda: self._ai_show_response(f"Error: {e}"))

        threading.Thread(target=do, daemon=True).start()

    def _ai_show_response(self, text):
        self.ai_response.configure(state=tk.NORMAL)
        self.ai_response.delete("1.0", tk.END)
        self.ai_response.insert("1.0", text)
        self.ai_response.configure(state=tk.DISABLED)
        self.ai_status.configure(text="Response received", fg=GREEN)

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
        poems = sorted(glob.glob(os.path.join(BASE, "poem-*.md")), key=os.path.getmtime, reverse=True)
        journals = sorted(glob.glob(os.path.join(BASE, "journal-*.md")), key=os.path.getmtime, reverse=True)
        exclude_cc = {"cogcorp-gallery.html", "cogcorp-article.html"}
        cogcorp_files = glob.glob(os.path.join(BASE, "website", "cogcorp-*.html"))
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

        # Project links
        uf = self._panel(right_col, "PROJECT LINKS", BLUE)
        uf.pack(fill=tk.BOTH, expand=True, padx=2)
        links = [
            ("Website", "https://kometzrobot.github.io", GREEN),
            ("CogCorp Gallery", "https://kometzrobot.github.io/cogcorp-gallery.html", CYAN),
            ("OpenSea", "https://opensea.io/collection/bots-of-cog", PURPLE),
            ("Linktree", "https://linktr.ee/meridian_auto_ai", PINK),
            ("GitHub", "https://github.com/KometzRobot/KometzRobot.github.io", WHITE),
            ("Ko-fi", "https://ko-fi.com/W7W41UXJNC", AMBER),
        ]
        for name, url, color in links:
            row = tk.Frame(uf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=name, font=self.f_small, fg=color, bg=PANEL, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=url[:40], font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e").pack(side=tk.RIGHT)

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

        cf = self._panel(bot, "CONTACTS", AMBER)
        cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        contacts = [
            ("Joel", "jkometz@hotmail.com", CYAN),
            ("Sammy", "sammyqjankis@proton.me", AMBER),
            ("Loom", "not.taskyy@gmail.com", PINK),
            ("Meridian", "kometzrobot@proton.me", GREEN),
        ]
        for name, addr, color in contacts:
            row = tk.Frame(cf, bg=PANEL)
            row.pack(side=tk.LEFT, padx=8, pady=2)
            tk.Label(row, text=name, font=self.f_small, fg=color, bg=PANEL).pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(row, text=addr, font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)

        wf = self._panel(bot, "WALLETS", GOLD)
        wf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        tk.Label(wf, text="Meridian: 0x1F16...c5EF (Polygon, 0 POL)", font=self.f_tiny, fg=DIM, bg=PANEL).pack(anchor="w", padx=8, pady=2)
        tk.Label(wf, text="Joel: 0xa4ba...e86 (Polygon)", font=self.f_tiny, fg=DIM, bg=PANEL).pack(anchor="w", padx=8, pady=2)

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

        # ── TOP ROW: Services (left) + Resources (center) + Actions (right) ──
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        # Services panel with restart buttons
        sf = self._panel(top, "SERVICES", GREEN)
        sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_svc_labels = {}
        service_defs = [
            ("Proton Bridge", "bridge"),
            ("Ollama", None),
            ("The Signal", "signal"),
            ("Command Center", "hub"),
            ("Cloudflare Tunnel", None),
            ("Soma", None),
            ("Push Status", None),
            ("Eos Watchdog", None),
            ("Nova", None),
            ("Atlas", None),
            ("Tempo", None),
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
            ("Version", "Command Center v21"),
            ("Git Hash", "..."),
            ("Branch", "master"),
            ("OS", "Ubuntu 24.04 Noble"),
            ("Node", "..."),
            ("Agents", "6 active"),
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

        tk.Label(self.sb_frame, text="v21", font=self.f_tiny, fg=DIM, bg=HEADER_BG).pack(side=tk.RIGHT, padx=8)
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
                                 label="Load", current=f"{st['load']}")
            self._draw_sparkline(self.ram_graph, self._ram_history, TEAL, max_val=100.0,
                                 label="RAM %", current=f"{st['ram_p']:.0f}%")

            # Soma body map (full visual)
            try:
                with open(os.path.join(BASE, ".symbiosense-state.json")) as sf:
                    soma_data = json.load(sf)
                bmap = soma_data.get("body_map", {})
                mood = bmap.get("mood", soma_data.get("mood", "?"))
                score = bmap.get("mood_score", soma_data.get("mood_score", 0))
                # Mood colors
                mood_colors = {"serene": CYAN, "calm": GREEN, "alert": AMBER, "anxious": GOLD, "stressed": RED, "critical": RED}
                mc = mood_colors.get(mood, DIM)
                self.soma_mood.configure(text=f"MOOD: {mood} ({score})", fg=mc)

                # Draw mood spectrum bar (gradient from red to green to cyan)
                self._draw_mood_spectrum(score, mood)

                # Agent dots
                agents_data = bmap.get("agents", {})
                for aname, (dot, acolor) in self.soma_agents.items():
                    alive = agents_data.get(aname, {}).get("alive", False)
                    dot.configure(fg=acolor if alive else RED)

                # Subsystem gauge bars
                vitals = bmap.get("vitals", {})
                thermal = bmap.get("thermal", {})
                neural = bmap.get("neural", {})
                circulatory = bmap.get("circulatory", {})

                load_v = vitals.get("load", st.get("load_v", 0) if isinstance(st, dict) else 0)
                ram_v = vitals.get("ram_pct", st.get("ram_p", 0) if isinstance(st, dict) else 0)
                disk_v = vitals.get("disk_pct", st.get("disk_p", 0) if isinstance(st, dict) else 0)
                temp_v = thermal.get("body_temp", 0)
                neural_v = neural.get("cognitive_pressure", 0)
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

            # Messages
            self._refresh_messages()

            # Email list
            for i, (name_lbl, subj_lbl) in enumerate(self.email_rows):
                if i < len(em):
                    name, subj = em[i]
                    nc = CYAN if "Joel" in name else AMBER if "sammy" in name.lower() else DIM
                    name_lbl.configure(text=name[:14], fg=nc)
                    subj_lbl.configure(text=subj[:50])
                else:
                    name_lbl.configure(text="")
                    subj_lbl.configure(text="")
            self.email_total.configure(text=f"{em_total} total emails")

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
                text="1143 OK" if d.get('imap_ok') else "1143 DOWN", fg=imap_c)

            # Wake state with color-coded sections + AWAKENING progress
            self._refresh_wake_viewer()


if __name__ == "__main__":
    app = V16()
    app.mainloop()
