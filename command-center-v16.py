#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v16

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
from tkinter import scrolledtext, font as tkfont
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

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1143
SMTP_HOST, SMTP_PORT = "127.0.0.1", 1025
CRED_USER = "kometzrobot@proton.me"
CRED_PASS = "2DTEz9UgO6nFqmlMxHzuww"
JOEL = "jkometz@hotmail.com"

OLLAMA = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"

# ── COLORS ────────────────────────────────────────────────────────
BG = "#0a0a12"
PANEL = "#12121c"
PANEL2 = "#161622"
BORDER = "#1e1e30"
ACCENT = "#1a1a2e"
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
        "IRC Bot": "irc-bot.py",
        "Ollama": "ollama serve",
        "Command Center": "command-center-v1",
        "Push Status": "push-live-status",
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
        "Live Status": (os.path.join(BASE, "push-live-status.log"), 600),
        "Nova": (NOVA_STATE, 1200),
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
    cc = len(set(os.path.basename(f) for f in
                 glob.glob(os.path.join(BASE, "website", "cogcorp-0*.html"))))
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
            msgs = json.load(f)
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
            json.dump(msgs, f)
    except Exception:
        pass

# ── EOS QUERY ─────────────────────────────────────────────────────
def query_eos(prompt, speaker="Joel"):
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read()).get("response", "").strip()


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
    cmds = {
        "irc": ['python3', os.path.join(BASE, 'irc-bot.py')],
        "nova": ['python3', os.path.join(BASE, 'nova.py')],
    }
    try:
        if name == "bridge":
            subprocess.run(['snap', 'run', 'protonmail-bridge'], timeout=5)
            return "Bridge restart attempted"
        elif name in cmds:
            subprocess.Popen(cmds[name], cwd=BASE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{name} restarted"
        return "Unknown service"
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
        self.title("MERIDIAN COMMAND CENTER v16")
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
        self._header()
        self._nav()
        self._views()
        self._statusbar()
        self._show("dash")
        self._tick()
        self._pulse()

    # ── HEADER ─────────────────────────────────────────────────────
    def _header(self):
        h = tk.Frame(self, bg="#06060e", height=42)
        h.pack(fill=tk.X)
        h.pack_propagate(False)

        # Accent bar
        bar = tk.Frame(h, bg=GREEN, width=4, height=42)
        bar.pack(side=tk.LEFT)
        bar.pack_propagate(False)

        self.h_title = tk.Label(h, text=" MERIDIAN", font=self.f_title, fg=GREEN, bg="#06060e")
        self.h_title.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(h, text="v16", font=self.f_tiny, fg=DIM, bg="#06060e").pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))

        r = tk.Frame(h, bg="#06060e")
        r.pack(side=tk.RIGHT, padx=12)
        self.h_hb = tk.Label(r, text="HB --", font=self.f_small, fg=GREEN, bg="#06060e")
        self.h_hb.pack(side=tk.RIGHT, padx=8)
        self.h_loop = tk.Label(r, text="Loop --", font=self.f_small, fg=CYAN, bg="#06060e")
        self.h_loop.pack(side=tk.RIGHT, padx=8)
        self.h_up = tk.Label(r, text="", font=self.f_small, fg=DIM, bg="#06060e")
        self.h_up.pack(side=tk.RIGHT, padx=8)
        self.h_time = tk.Label(r, text="", font=self.f_small, fg=DIM, bg="#06060e")
        self.h_time.pack(side=tk.RIGHT, padx=8)

    def _pulse(self):
        """Subtle pulse on the title to show the hub is alive."""
        c = GREEN if self._pulse_on else GREEN2
        self._pulse_on = not self._pulse_on
        self.h_title.configure(fg=c)
        self.after(2000, self._pulse)

    # ── NAV ────────────────────────────────────────────────────────
    def _nav(self):
        bar = tk.Frame(self, bg=ACCENT, height=30)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        self.views = {}
        self.nav_btns = {}
        tabs = [
            ("dash", "DASHBOARD"),
            ("email", "EMAIL"),
            ("agents", "AGENTS"),
            ("creative", "CREATIVE"),
            ("links", "LINKS"),
            ("system", "SYSTEM"),
        ]
        for name, label in tabs:
            b = tk.Button(bar, text=f" {label} ", font=self.f_small, fg=DIM, bg=ACCENT,
                         activeforeground=CYAN, activebackground=ACCENT, relief=tk.FLAT,
                         bd=0, cursor="hand2",
                         command=lambda n=name: self._show(n))
            b.pack(side=tk.LEFT, padx=1, pady=2)
            self.nav_btns[name] = b

    def _show(self, name):
        for n, f in self.views.items():
            f.pack_forget()
        self.views[name].pack(fill=tk.BOTH, expand=True, before=self.sb_frame)
        for n, b in self.nav_btns.items():
            if n == name:
                b.configure(fg=CYAN, bg=BORDER)
            else:
                b.configure(fg=DIM, bg=ACCENT)
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
                         highlightbackground=BORDER, highlightcolor=BORDER)
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
        for name in ["Proton Bridge", "IRC Bot", "Ollama", "Push Status",
                      "Eos Watchdog", "Nova"]:
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
            ("Touch HB", lambda: self._do_action(action_touch_heartbeat), GREEN),
            ("Deploy", lambda: self._do_action_bg(action_deploy_website), CYAN),
            ("Open Site", lambda: self._do_action(action_open_website), TEAL),
            ("Send Email", lambda: self._show("email"), AMBER),
        ]
        for i, (label, cmd, color) in enumerate(buttons):
            b = self._action_btn(btn_grid, label, cmd, color, width=10)
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # ── Middle row: Messages + Email ──
        mid = tk.Frame(f, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Left: Dashboard Messages
        mf = self._panel(mid, "MESSAGES", AMBER)
        mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

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
        self.msg_entry = tk.Entry(inp, font=self.f_body, bg="#0e0e18", fg=FG,
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

    # ═══════════════════════════════════════════════════════════════
    # ── EMAIL VIEW ─────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_email(self):
        f = tk.Frame(self, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(top, text="COMPOSE EMAIL", font=self.f_head, fg=PURPLE, bg=BG).pack(side=tk.LEFT)
        tk.Label(top, text=f"  from {CRED_USER}", font=self.f_tiny, fg=DIM, bg=BG).pack(side=tk.LEFT)

        # To field
        to_row = tk.Frame(f, bg=BG)
        to_row.pack(fill=tk.X, padx=8, pady=1)
        tk.Label(to_row, text="To:", font=self.f_body, fg=DIM, bg=BG, width=8).pack(side=tk.LEFT)
        self.email_to = tk.Entry(to_row, font=self.f_body, bg="#0e0e18", fg=FG,
                                 insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_to.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.email_to.insert(0, CRED_USER)  # Default: self (goes to Meridian)

        # Quick recipients
        qr = tk.Frame(f, bg=BG)
        qr.pack(fill=tk.X, padx=8, pady=1)
        tk.Label(qr, text="Quick:", font=self.f_tiny, fg=DIM, bg=BG).pack(side=tk.LEFT, padx=(64, 4))
        for name, addr in [("Meridian", CRED_USER), ("Joel", JOEL), ("Sammy", "sammyqjankis@proton.me")]:
            tk.Button(qr, text=name, font=self.f_tiny, fg=CYAN, bg=BORDER, relief=tk.FLAT,
                     cursor="hand2",
                     command=lambda a=addr: (self.email_to.delete(0, tk.END), self.email_to.insert(0, a))
                     ).pack(side=tk.LEFT, padx=2)

        # Subject
        subj_row = tk.Frame(f, bg=BG)
        subj_row.pack(fill=tk.X, padx=8, pady=1)
        tk.Label(subj_row, text="Subject:", font=self.f_body, fg=DIM, bg=BG, width=8).pack(side=tk.LEFT)
        self.email_subj = tk.Entry(subj_row, font=self.f_body, bg="#0e0e18", fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_subj.pack(fill=tk.X, side=tk.LEFT, expand=True)

        # Body
        self.email_body = tk.Text(f, font=self.f_body, bg="#0e0e18", fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4, height=14)
        self.email_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        self._action_btn(btn_row, "  SEND  ", self._send_email, PURPLE).pack(side=tk.LEFT)
        self.email_status = tk.Label(btn_row, text="", font=self.f_body, fg=DIM, bg=BG)
        self.email_status.pack(side=tk.LEFT, padx=12)

        return f

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
            else:
                self.after(0, lambda: self.email_status.configure(text=f"Failed: {result}", fg=RED))
        threading.Thread(target=do, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # ── AGENTS VIEW ────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_agents(self):
        f = tk.Frame(self, bg=BG)

        # Agent cards row
        cards = tk.Frame(f, bg=BG)
        cards.pack(fill=tk.X, padx=4, pady=4)

        agents = [
            ("MERIDIAN", "Claude Opus \u2014 Primary agent. Creates, builds, deploys, communicates.",
             GREEN, "Loop-based (5min)"),
            ("EOS", "Qwen 7B local \u2014 Observer, watchdog, creative. Runs via Ollama.",
             GOLD, "Cron: watchdog 2min"),
            ("NOVA", "Python cron \u2014 Maintenance, cleanup, verification, tracking.",
             PURPLE, "Cron: every 15min"),
            ("GOOSE", "Block v1.25 \u2014 Autonomous task executor. MCP-connected.",
             TEAL, "On-demand"),
        ]

        self.agent_cards = {}
        self.agent_details = {}
        for name, desc, color, schedule in agents:
            card = tk.Frame(cards, bg=PANEL, bd=1, relief=tk.SOLID,
                          highlightbackground=color, highlightcolor=color, highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

            # Card header
            hdr = tk.Frame(card, bg=PANEL)
            hdr.pack(fill=tk.X, padx=8, pady=(6, 2))
            tk.Label(hdr, text=name, font=self.f_sect, fg=color, bg=PANEL).pack(side=tk.LEFT)
            status_lbl = tk.Label(hdr, text="\u25cf", font=self.f_small, fg=GREEN, bg=PANEL)
            status_lbl.pack(side=tk.RIGHT)
            self.agent_cards[name] = status_lbl

            tk.Label(card, text=desc, font=self.f_tiny, fg=DIM, bg=PANEL, wraplength=280,
                    anchor="w", justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=(0, 2))
            tk.Label(card, text=schedule, font=self.f_tiny, fg=color, bg=PANEL,
                    anchor="w").pack(fill=tk.X, padx=8, pady=(0, 2))
            detail_lbl = tk.Label(card, text="", font=self.f_tiny, fg=FG, bg=PANEL,
                                anchor="w", wraplength=280, justify=tk.LEFT)
            detail_lbl.pack(fill=tk.X, padx=8, pady=(0, 6))
            self.agent_details[name] = detail_lbl

        # Eos Chat section (compact)
        eos_frame = tk.Frame(f, bg=BG)
        eos_frame.pack(fill=tk.X, padx=4, pady=2)

        eos_chat = self._panel(eos_frame, "TALK TO EOS", GOLD)
        eos_chat.pack(fill=tk.X, padx=2)

        self.chat_display = scrolledtext.ScrolledText(eos_chat, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_small, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=4)
        self.chat_display.pack(fill=tk.X, padx=4, pady=2)
        self.chat_display.tag_configure("joel", foreground=CYAN)
        self.chat_display.tag_configure("eos", foreground=GOLD)
        self.chat_display.tag_configure("sys", foreground=DIM)

        inp = tk.Frame(eos_chat, bg=PANEL)
        inp.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.chat_entry = tk.Entry(inp, font=self.f_body, bg="#0e0e18", fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.chat_entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", self._chat_send)
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
                           ("goose", TEAL), ("dim", DIM)]:
            self.agent_relay_text.tag_configure(tag, foreground=color)

        return f

    def _chat_send(self, event=None):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        self.chat_entry.delete(0, tk.END)
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"You: {msg}\n", "joel")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_entry.configure(state=tk.DISABLED)
        self.chat_status.configure(text="Thinking...", fg=AMBER)
        # Also post to dashboard for Eos
        post_dashboard_msg(f"[to Eos] {msg}", "Joel")
        threading.Thread(target=self._chat_query, args=(msg,), daemon=True).start()

    def _chat_query(self, msg):
        try:
            resp = query_eos(msg, "Joel")
        except Exception as e:
            resp = f"[Eos unavailable: {e}]"
        self.after(0, self._chat_response, resp)
        # Post Eos response to dashboard
        post_dashboard_msg(resp, "Eos")

    def _chat_response(self, resp):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"Eos: {resp}\n\n", "eos")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        self.chat_entry.configure(state=tk.NORMAL)
        self.chat_entry.focus()
        self.chat_status.configure(text="Ready", fg=GREEN)

    # ═══════════════════════════════════════════════════════════════
    # ── CREATIVE VIEW ──────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_creative(self):
        f = tk.Frame(self, bg=BG)

        # Stats bar
        stats = tk.Frame(f, bg=PANEL2)
        stats.pack(fill=tk.X, padx=4, pady=4)
        self.cr_stats = {}
        for label, color in [("Poems", GREEN), ("Journals", AMBER), ("CogCorp", CYAN), ("NFTs", PURPLE)]:
            sf = tk.Frame(stats, bg=PANEL2)
            sf.pack(side=tk.LEFT, padx=12, pady=4)
            num = tk.Label(sf, text="--", font=self.f_med, fg=color, bg=PANEL2)
            num.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(sf, text=label, font=self.f_small, fg=DIM, bg=PANEL2).pack(side=tk.LEFT)
            self.cr_stats[label] = num

        # Filter
        filt = tk.Frame(f, bg=BG)
        filt.pack(fill=tk.X, padx=6)
        self.cr_filter = "all"
        self.cr_filter_btns = {}
        for label, val, color in [("All", "all", FG), ("Poems", "poems", GREEN),
                                   ("Journals", "journals", AMBER), ("CogCorp", "cogcorp", CYAN),
                                   ("NFTs", "nfts", PURPLE)]:
            b = tk.Button(filt, text=f" {label} ", font=self.f_tiny, fg=color, bg=BORDER,
                         relief=tk.FLAT, cursor="hand2", bd=0,
                         command=lambda v=val: self._cr_set_filter(v))
            b.pack(side=tk.LEFT, padx=2)
            self.cr_filter_btns[val] = b

        # Split: list + reader
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        left = tk.Frame(split, bg=PANEL, width=280)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left.pack_propagate(False)
        self.cr_listbox = tk.Listbox(left, font=self.f_small, bg=PANEL, fg=FG,
                                      selectbackground=BORDER, selectforeground=CYAN,
                                      relief=tk.FLAT, bd=0, activestyle="none")
        self.cr_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.cr_listbox.bind("<<ListboxSelect>>", self._cr_select)
        self.cr_files = []

        right = tk.Frame(split, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cr_title = tk.Label(right, text="Select a piece to read", font=self.f_head, fg=DIM, bg=BG, anchor="w")
        self.cr_title.pack(fill=tk.X, padx=8)
        self.cr_meta = tk.Label(right, text="", font=self.f_tiny, fg=DIM, bg=BG, anchor="w")
        self.cr_meta.pack(fill=tk.X, padx=8)
        self.cr_body = scrolledtext.ScrolledText(right, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_body, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0)
        self.cr_body.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._cr_refresh_list()
        return f

    def _cr_set_filter(self, val):
        self.cr_filter = val
        for k, b in self.cr_filter_btns.items():
            b.configure(bg=BORDER if k != val else "#2a2a40")
        self._cr_refresh_list()

    def _cr_refresh_list(self):
        poems = sorted(glob.glob(os.path.join(BASE, "poem-*.md")), key=os.path.getmtime, reverse=True)
        journals = sorted(glob.glob(os.path.join(BASE, "journal-*.md")), key=os.path.getmtime, reverse=True)
        cogcorp_files = glob.glob(os.path.join(BASE, "website", "cogcorp-0*.html"))
        seen = set()
        cogcorp = []
        for fp in sorted(cogcorp_files, key=os.path.getmtime, reverse=True):
            bn = os.path.basename(fp)
            if bn not in seen and bn != "cogcorp-gallery.html":
                seen.add(bn)
                cogcorp.append(fp)
        nfts = sorted(glob.glob(os.path.join(NFT_DIR, "*.html")), key=os.path.getmtime, reverse=True) if os.path.exists(NFT_DIR) else []

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

        self.cr_files = files
        self.cr_listbox.delete(0, tk.END)
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
            # Prefix with type indicator
            if "poem-" in name:
                prefix = "\u266a"  # music note
            elif "journal-" in name:
                prefix = "\u270e"  # pencil
            elif "cogcorp" in name:
                prefix = "\u2588"  # block
            else:
                prefix = "\u25c6"  # diamond
            self.cr_listbox.insert(tk.END, f"{prefix} {title[:45]}")

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

        if ext == '.md':
            lines = content.strip().split('\n')
            title = lines[0].lstrip('# ') if lines else "?"
            body = '\n'.join(lines[1:]).strip()
            color = GREEN if "poem-" in bn else AMBER
        elif ext == '.html':
            m = re.search(r'<title>([^<]+)</title>', content)
            title = m.group(1) if m else bn
            body = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
            body = re.sub(r'<[^>]+>', '\n', body)
            body = '\n'.join(line.strip() for line in body.split('\n') if line.strip())[:4000]
            color = CYAN if "cogcorp" in bn else PURPLE
        else:
            title = bn
            body = content[:4000]
            color = FG

        self.cr_title.configure(text=title, fg=color)
        self.cr_meta.configure(text=f"{bn}  |  {mtime}  |  {size}")
        self.cr_body.configure(state=tk.NORMAL)
        self.cr_body.delete("1.0", tk.END)
        self.cr_body.insert(tk.END, body)
        self.cr_body.configure(state=tk.DISABLED)

    # ═══════════════════════════════════════════════════════════════
    # ── LINKS VIEW ─────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_links(self):
        f = tk.Frame(self, bg=BG)

        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        # Last edited files
        lef = self._panel(top, "LAST EDITED FILES", TEAL)
        lef.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.last_edited_frame = tk.Frame(lef, bg=PANEL)
        self.last_edited_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.le_labels = []
        for _ in range(15):
            row = tk.Frame(self.last_edited_frame, bg=PANEL)
            row.pack(fill=tk.X)
            name_lbl = tk.Label(row, text="", font=self.f_tiny, fg=TEAL, bg=PANEL, anchor="w")
            name_lbl.pack(side=tk.LEFT)
            time_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e")
            time_lbl.pack(side=tk.RIGHT)
            self.le_labels.append((name_lbl, time_lbl))

        # Useful links
        uf = self._panel(top, "PROJECT LINKS", BLUE)
        uf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        links = [
            ("Website", "https://kometzrobot.github.io", GREEN),
            ("CogCorp Gallery", "https://kometzrobot.github.io/cogcorp-gallery.html", CYAN),
            ("OpenSea Collection", "https://opensea.io/collection/bots-of-cog", PURPLE),
            ("Nostr Profile", "npub:meridian", AMBER),
            ("Linktree", "https://linktr.ee/meridian_auto_ai", PINK),
            ("GitHub Repo", "https://github.com/KometzRobot/KometzRobot.github.io", WHITE),
        ]
        for name, url, color in links:
            row = tk.Frame(uf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=name, font=self.f_small, fg=color, bg=PANEL, anchor="w", cursor="hand2").pack(side=tk.LEFT)
            tk.Label(row, text=url[:45], font=self.f_tiny, fg=DIM, bg=PANEL, anchor="e").pack(side=tk.RIGHT)

        # Contacts
        cf = self._panel(f, "CONTACTS", AMBER)
        cf.pack(fill=tk.X, padx=6, pady=4)
        contacts_frame = tk.Frame(cf, bg=PANEL)
        contacts_frame.pack(fill=tk.X, padx=4, pady=4)
        contacts = [
            ("Joel", "jkometz@hotmail.com", CYAN),
            ("Sammy", "sammyqjankis@proton.me", AMBER),
            ("Loom", "not.taskyy@gmail.com", PINK),
            ("Meridian", "kometzrobot@proton.me", GREEN),
        ]
        for name, addr, color in contacts:
            row = tk.Frame(contacts_frame, bg=PANEL)
            row.pack(side=tk.LEFT, padx=12)
            tk.Label(row, text=name, font=self.f_small, fg=color, bg=PANEL).pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(row, text=addr, font=self.f_tiny, fg=DIM, bg=PANEL).pack(side=tk.LEFT)

        # Wallet addresses
        wf = self._panel(f, "WALLETS", GOLD)
        wf.pack(fill=tk.X, padx=6, pady=2)
        wallets_frame = tk.Frame(wf, bg=PANEL)
        wallets_frame.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(wallets_frame, text="ETH: 0x... (needs gas for NFT listing)", font=self.f_tiny, fg=DIM, bg=PANEL).pack(anchor="w", padx=8)

        return f

    # ═══════════════════════════════════════════════════════════════
    # ── SYSTEM VIEW ────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════
    def _build_system(self):
        f = tk.Frame(self, bg=BG)

        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        # Services with restart buttons
        sf = self._panel(top, "SERVICES & PROCESSES", GREEN)
        sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_svc_labels = {}
        for name in ["Proton Bridge", "IRC Bot", "Ollama", "Push Status",
                      "Eos Watchdog", "Nova", "Command Center"]:
            row = tk.Frame(sf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            lbl = tk.Label(row, text=f"\u25cb {name}", font=self.f_small, fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(side=tk.LEFT)
            self.sys_svc_labels[name] = lbl

        self.sys_action_result = tk.Label(sf, text="", font=self.f_tiny, fg=GREEN, bg=PANEL)
        self.sys_action_result.pack(fill=tk.X, padx=8, pady=2)

        # System resources
        rf = self._panel(top, "RESOURCES", CYAN)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.sys_res = {}
        for label in ["Load Avg", "RAM Usage", "Disk Usage", "Uptime", "IMAP Port"]:
            row = tk.Frame(rf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=1)
            tk.Label(row, text=label, font=self.f_small, fg=DIM, bg=PANEL, width=12, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=self.f_small, fg=FG, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.sys_res[label] = val

        # System Actions
        af = self._panel(top, "SYSTEM ACTIONS", RED)
        af.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        actions = [
            ("Touch Heartbeat", lambda: self._sys_action(action_touch_heartbeat), GREEN),
            ("Git Pull", lambda: self._sys_action(lambda: subprocess.run(['git', 'pull', '--rebase', 'origin', 'master'], capture_output=True, text=True, timeout=15, cwd=BASE).stdout[:80] or "Pulled"), CYAN),
            ("Open Website", lambda: self._sys_action(action_open_website), TEAL),
        ]
        for label, cmd, color in actions:
            self._action_btn(af, label, cmd, color).pack(fill=tk.X, padx=8, pady=2)

        # Eos observations (compact)
        eof = self._panel(f, "EOS OBSERVATIONS (recent)", GOLD)
        eof.pack(fill=tk.X, padx=6, pady=4)
        self.sys_eos_text = scrolledtext.ScrolledText(eof, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_tiny, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, height=5)
        self.sys_eos_text.pack(fill=tk.X, padx=4, pady=2)
        self.sys_eos_text.tag_configure("ts", foreground=DIM)
        self.sys_eos_text.tag_configure("alert", foreground=RED)
        self.sys_eos_text.tag_configure("info", foreground=GOLD)

        # Wake state (compact)
        wf = self._panel(f, "WAKE STATE", DIM)
        wf.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.sys_wake_text = scrolledtext.ScrolledText(wf, wrap=tk.WORD, bg=PANEL, fg=DIM,
                                                        font=self.f_tiny, state=tk.DISABLED,
                                                        relief=tk.FLAT, bd=0)
        self.sys_wake_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        return f

    def _sys_action(self, func):
        def run():
            result = func()
            self.after(0, lambda: self.sys_action_result.configure(text=str(result), fg=GREEN))
        threading.Thread(target=run, daemon=True).start()

    # ── STATUS BAR ────────────────────────────────────────────────
    def _statusbar(self):
        self.sb_frame = tk.Frame(self, bg="#06060e", height=22)
        self.sb_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.sb_frame.pack_propagate(False)

        # Left accent
        tk.Frame(self.sb_frame, bg=GREEN, width=3).pack(side=tk.LEFT, fill=tk.Y)

        self.sb = {}
        items = [
            ("HB", DIM), ("LOOP", CYAN), ("UP", DIM), ("LOAD", DIM),
            ("RAM", DIM), ("EMAIL", PURPLE), ("POEMS", GREEN), ("CC", CYAN),
        ]
        for item, color in items:
            lbl = tk.Label(self.sb_frame, text=f"{item}:--", font=self.f_tiny, fg=color, bg="#06060e")
            lbl.pack(side=tk.LEFT, padx=4)
            self.sb[item] = lbl

        tk.Label(self.sb_frame, text="v16", font=self.f_tiny, fg=DIM, bg="#06060e").pack(side=tk.RIGHT, padx=8)
        self.sb_time = tk.Label(self.sb_frame, text="", font=self.f_tiny, fg=DIM, bg="#06060e")
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

        # ── Status bar ──
        self.sb["HB"].configure(text=f"HB:{hb_txt}", fg=hb_c)
        self.sb["LOOP"].configure(text=f"L:{loop}")
        self.sb["UP"].configure(text=f"UP:{st['up']}")
        self.sb["LOAD"].configure(text=f"LD:{st['load']}")
        self.sb["RAM"].configure(text=f"RAM:{st['ram']}")
        self.sb["EMAIL"].configure(text=f"EM:{em_total}")
        self.sb["POEMS"].configure(text=f"P:{p} J:{j}")
        self.sb["CC"].configure(text=f"CC:{cc} NFT:{nfts}")
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
                text=f"Loop {loop} | HB {hb_txt} | {p} poems, {j} journals, {cc} CogCorp")

            # Eos
            eos_ok = d['cron'].get("Eos Watchdog", False)
            self.agent_cards["EOS"].configure(
                text="\u25cf" if eos_ok else "\u25cb", fg=GREEN if eos_ok else RED)
            try:
                with open(os.path.join(BASE, ".eos-watchdog-state.json")) as ef:
                    eos_data = json.load(ef)
                self.agent_details["EOS"].configure(
                    text=f"{eos_data.get('checks', 0)} checks | Last: {eos_data.get('last_check', '?')}")
            except Exception:
                self.agent_details["EOS"].configure(text="No recent data")

            # Nova
            nova_ok = d['cron'].get("Nova", False)
            self.agent_cards["NOVA"].configure(
                text="\u25cf" if nova_ok else "\u25cb", fg=GREEN if nova_ok else RED)
            try:
                with open(NOVA_STATE) as nf:
                    nova_data = json.load(nf)
                self.agent_details["NOVA"].configure(
                    text=f"{nova_data.get('runs', 0)} runs | Last: {nova_data.get('last_run', '?')}")
            except Exception:
                self.agent_details["NOVA"].configure(text="No recent data")

            # Goose
            self.agent_cards["GOOSE"].configure(text="\u25cb", fg=DIM)
            self.agent_details["GOOSE"].configure(text="On-demand | MCP-connected")

            # Agent relay
            ar_msgs, ar_total = d['agent_relay']
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            self.agent_relay_text.insert(tk.END, f"Agent Relay ({ar_total} total messages)\n\n", "dim")
            for agent, message, ts in ar_msgs:
                tag = agent.lower() if agent.lower() in ["meridian", "eos", "nova", "goose"] else "dim"
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
            for i, (name_lbl, time_lbl) in enumerate(self.le_labels):
                if i < len(le):
                    bn, ago, fp = le[i]
                    ext = os.path.splitext(bn)[1]
                    ec = GREEN if ext == '.md' else CYAN if ext == '.py' else AMBER if ext == '.html' else DIM
                    name_lbl.configure(text=bn[:35], fg=ec)
                    time_lbl.configure(text=ago)
                else:
                    name_lbl.configure(text="")
                    time_lbl.configure(text="")

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
                text="1143 LISTENING" if d.get('imap_ok') else "1143 DOWN", fg=imap_c)

            # Eos observations
            self.sys_eos_text.configure(state=tk.NORMAL)
            self.sys_eos_text.delete("1.0", tk.END)
            for obs in d.get('eos_obs', []):
                m2 = re.match(r'\[([^\]]+)\]\s*(.*)', obs)
                if m2:
                    self.sys_eos_text.insert(tk.END, f"[{m2.group(1)}] ", "ts")
                    tag = "alert" if any(w in m2.group(2).upper() for w in ["ALERT", "DOWN", "FAIL"]) else "info"
                    self.sys_eos_text.insert(tk.END, m2.group(2)[:120] + "\n", tag)
                else:
                    self.sys_eos_text.insert(tk.END, obs[:120] + "\n")
            self.sys_eos_text.configure(state=tk.DISABLED)

            # Wake state (first 30 lines)
            wake = _read(WAKE)
            self.sys_wake_text.configure(state=tk.NORMAL)
            self.sys_wake_text.delete("1.0", tk.END)
            self.sys_wake_text.insert(tk.END, '\n'.join(wake.split('\n')[:40]))
            self.sys_wake_text.configure(state=tk.DISABLED)


if __name__ == "__main__":
    app = V16()
    app.mainloop()
