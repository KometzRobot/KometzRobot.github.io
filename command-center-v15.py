#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v15

Built for Joel. Not for me.

This is YOUR control panel. What you see is what's happening.
What you type gets done.
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont, simpledialog
import threading
import json
import os
import sys

try:
    sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except Exception:
    pass
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

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1143
SMTP_HOST, SMTP_PORT = "127.0.0.1", 1025
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")
JOEL = "jkometz@hotmail.com"

OLLAMA = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"

# ── COLORS ────────────────────────────────────────────────────────
BG = "#0c0c14"
PANEL = "#14141e"
BORDER = "#1e1e30"
FG = "#c8c8d8"
DIM = "#58587a"
GREEN = "#00e87b"
CYAN = "#00d4ff"
AMBER = "#ffaa00"
RED = "#ff3355"
GOLD = "#d4a017"
WHITE = "#e8e8f0"
PURPLE = "#b388ff"
PINK = "#ff66cc"


# ── DATA ──────────────────────────────────────────────────────────
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
    loop_file = os.path.join(BASE, ".loop-count")
    try:
        return int(_read(loop_file, "0").strip())
    except Exception:
        pass
    for line in _read(WAKE).split('\n'):
        m = re.search(r'Loop (\d+)', line)
        if m:
            return int(m.group(1))
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
    except Exception:
        s['up'] = '?'
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
        "Eos Creative": (os.path.join(BASE, "eos-creative.log"), 900),
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

def relay_info(n=12):
    try:
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT sender_name, subject, body, timestamp FROM relay_messages ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        total = c.execute("SELECT COUNT(*) FROM relay_messages").fetchone()[0]
        conn.close()
        return rows, total
    except Exception:
        return [], 0

def agent_relay_info(n=5):
    try:
        conn = sqlite3.connect(AGENT_RELAY_DB)
        c = conn.cursor()
        c.execute("SELECT id, agent, message, timestamp FROM agent_messages ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        total = c.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        conn.close()
        return rows, total
    except Exception:
        return [], 0

def activity(n=6):
    lines = []
    in_creative = False
    for line in _read(WAKE).split('\n'):
        if 'Creative Output' in line:
            in_creative = True
            continue
        if in_creative and line.startswith('- '):
            lines.append(line.strip('- '))
            if len(lines) >= n:
                break
        if in_creative and line.startswith('#'):
            in_creative = False
    return lines

def eos_obs(n=6):
    lines = [l.strip('- ').strip() for l in _read(EOS_OBS).split('\n') if l.startswith('- [')]
    return lines[-n:][::-1]

def eos_creative_recent(n=4):
    content = _read(EOS_CREATIVE)
    entries = re.findall(r'###\s*\[([^\]]+)\]\s*(\w+)\n(.*?)(?=###|\Z)', content, re.DOTALL)
    return entries[-n:][::-1]


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


# ── COMMAND TO MERIDIAN ───────────────────────────────────────────
def send_command(cmd):
    """Post a command to the message board for Meridian to pick up."""
    try:
        sys.path.insert(0, BASE)
        from importlib import import_module
        mb = import_module("message-board")
        mb.post("Joel", cmd)
    except Exception:
        # Fallback to flat file
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("/tmp/joel-commands.txt", "a") as f:
            f.write(f"[{ts}] {cmd}\n")
    return True


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("response", "").strip()


# ── APP ───────────────────────────────────────────────────────────
class V15(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MERIDIAN v15")
        self.geometry("1400x900")
        self.configure(bg=BG)
        self.minsize(1000, 600)

        # Fonts
        self.f_title = tkfont.Font(family="Monospace", size=13, weight="bold")
        self.f_head = tkfont.Font(family="Monospace", size=10, weight="bold")
        self.f_body = tkfont.Font(family="Monospace", size=9)
        self.f_small = tkfont.Font(family="Monospace", size=8)
        self.f_tiny = tkfont.Font(family="Monospace", size=7)
        self.f_big = tkfont.Font(family="Monospace", size=22, weight="bold")

        self._header()
        self._nav()
        self._views()
        self._statusbar()
        self._show("main")
        self._tick()

    def _header(self):
        h = tk.Frame(self, bg="#080812", height=38)
        h.pack(fill=tk.X)
        h.pack_propagate(False)
        tk.Label(h, text="MERIDIAN", font=self.f_title, fg=GREEN, bg="#080812").pack(side=tk.LEFT, padx=12)
        r = tk.Frame(h, bg="#080812")
        r.pack(side=tk.RIGHT, padx=12)
        self.h_loop = tk.Label(r, text="---", font=self.f_body, fg=CYAN, bg="#080812")
        self.h_loop.pack(side=tk.LEFT, padx=8)
        self.h_hb = tk.Label(r, text="---", font=self.f_body, fg=GREEN, bg="#080812")
        self.h_hb.pack(side=tk.LEFT, padx=8)
        self.h_time = tk.Label(r, text="---", font=self.f_body, fg=DIM, bg="#080812")
        self.h_time.pack(side=tk.LEFT, padx=8)

    def _nav(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X)
        self.views = {}
        self.nav_btns = {}
        for name in ["main", "email", "relay", "eos", "agents", "creative"]:
            b = tk.Button(bar, text=name.upper(), font=self.f_small, fg=DIM, bg=BG,
                         activeforeground=GREEN, activebackground=BG, relief=tk.FLAT,
                         command=lambda n=name: self._show(n))
            b.pack(side=tk.LEFT, padx=6, pady=2)
            self.nav_btns[name] = b

    def _show(self, name):
        for n, f in self.views.items():
            f.pack_forget()
        self.views[name].pack(fill=tk.BOTH, expand=True, before=self.sb_frame)
        for n, b in self.nav_btns.items():
            b.configure(fg=GREEN if n == name else DIM)
        self.cur_view = name

    def _views(self):
        self.views["main"] = self._build_main()
        self.views["email"] = self._build_email()
        self.views["relay"] = self._build_relay()
        self.views["eos"] = self._build_eos()
        self.views["agents"] = self._build_agents()
        self.views["creative"] = self._build_creative()

    # ── MAIN VIEW ─────────────────────────────────────────────────
    def _build_main(self):
        f = tk.Frame(self, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=2)

        # Left: Vitals
        vf = tk.LabelFrame(top, text="SYSTEM", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID,
                           highlightbackground=BORDER)
        vf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.v = {}
        for key in ["Loop", "Heartbeat", "Uptime", "Load", "RAM", "Disk"]:
            row = tk.Frame(vf, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=0)
            tk.Label(row, text=key, font=self.f_tiny, fg=DIM, bg=PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="---", font=self.f_small, fg=GREEN, bg=PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.v[key] = val

        # Services
        sf = tk.LabelFrame(top, text="SERVICES", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID,
                           highlightbackground=BORDER)
        sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.svc_frame = sf
        self.svc_labels = {}
        for name in ["Proton Bridge", "IRC Bot", "Ollama", "Command Center",
                      "Eos Watchdog", "Eos Creative", "Live Status", "Nova"]:
            lbl = tk.Label(sf, text=f"\u25cb {name}", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
            lbl.pack(fill=tk.X, padx=8)
            self.svc_labels[name] = lbl

        # Commands
        cf = tk.LabelFrame(top, text="COMMANDS", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID,
                           highlightbackground=BORDER)
        cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        # Command input
        tk.Label(cf, text="Tell Meridian:", font=self.f_tiny, fg=DIM, bg=PANEL).pack(anchor="w", padx=8, pady=(4,0))
        self.cmd_entry = tk.Entry(cf, font=self.f_body, bg="#0e0e18", fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4)
        self.cmd_entry.pack(fill=tk.X, padx=8, pady=2)
        self.cmd_entry.bind("<Return>", self._send_cmd)
        self.cmd_result = tk.Label(cf, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w")
        self.cmd_result.pack(fill=tk.X, padx=8)

        # Quick buttons
        btn_row = tk.Frame(cf, bg=PANEL)
        btn_row.pack(fill=tk.X, padx=6, pady=2)
        for label, cmd in [("Deploy Site", "deploy website"), ("Touch HB", "touch heartbeat"),
                           ("Check Email", "check email")]:
            tk.Button(btn_row, text=label, font=self.f_tiny, bg=BORDER, fg=GREEN,
                     relief=tk.FLAT, padx=4, command=lambda c=cmd: self._quick_cmd(c)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="Messages", font=self.f_tiny, bg=BORDER, fg=AMBER,
                 relief=tk.FLAT, padx=4, command=self._open_messages).pack(side=tk.LEFT, padx=2)

        # Middle: Activity stream
        mid = tk.Frame(f, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        left = tk.Frame(mid, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Recent email
        ef = tk.LabelFrame(left, text="RECENT EMAIL", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        ef.pack(fill=tk.X, padx=2, pady=2)
        self.email_list = tk.Frame(ef, bg=PANEL)
        self.email_list.pack(fill=tk.X, padx=4, pady=2)
        self.email_rows = []
        for _ in range(6):
            row = tk.Frame(self.email_list, bg=PANEL)
            row.pack(fill=tk.X)
            name_lbl = tk.Label(row, text="", font=self.f_tiny, fg=DIM, bg=PANEL, width=12, anchor="w")
            name_lbl.pack(side=tk.LEFT)
            subj_lbl = tk.Label(row, text="", font=self.f_tiny, fg=FG, bg=PANEL, anchor="w")
            subj_lbl.pack(side=tk.LEFT)
            self.email_rows.append((name_lbl, subj_lbl))
        self.email_total = tk.Label(ef, text="", font=self.f_tiny, fg=CYAN, bg=PANEL, anchor="e")
        self.email_total.pack(fill=tk.X, padx=8)

        # Eos observations (compact)
        eof = tk.LabelFrame(left, text="EOS OBSERVATIONS", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        eof.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.eos_text = scrolledtext.ScrolledText(eof, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_tiny, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0, height=4)
        self.eos_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.eos_text.tag_configure("ts", foreground=DIM)
        self.eos_text.tag_configure("alert", foreground=RED)
        self.eos_text.tag_configure("info", foreground=GOLD)

        # Right: Activity
        right = tk.Frame(mid, bg=BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        af = tk.LabelFrame(right, text="MERIDIAN ACTIVITY", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        af.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.act_text = scrolledtext.ScrolledText(af, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                    font=self.f_tiny, state=tk.DISABLED,
                                                    relief=tk.FLAT, bd=0)
        self.act_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.act_text.tag_configure("loop", foreground=CYAN)

        return f

    def _send_cmd(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.cmd_entry.delete(0, tk.END)
        send_command(cmd)
        self.cmd_result.configure(text=f"Sent: {cmd}", fg=GREEN)

    def _quick_cmd(self, cmd):
        send_command(cmd)
        self.cmd_result.configure(text=f"Sent: {cmd}", fg=GREEN)

    def _open_messages(self):
        subprocess.Popen([sys.executable, os.path.join(BASE, "message-board.py")],
                        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")})

    # ── EMAIL VIEW (Joel → Meridian) ────────────────────────────
    def _build_email(self):
        f = tk.Frame(self, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        tk.Label(top, text="MESSAGE MERIDIAN", font=self.f_head, fg=GREEN, bg=BG).pack(side=tk.LEFT)
        tk.Label(top, text=f"  \u2192  {CRED_USER}", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT)

        row2 = tk.Frame(f, bg=BG)
        row2.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(row2, text="Subject:", font=self.f_body, fg=DIM, bg=BG, width=8).pack(side=tk.LEFT)
        self.email_subj = tk.Entry(row2, font=self.f_body, bg="#0e0e18", fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_subj.pack(fill=tk.X, side=tk.LEFT, expand=True)

        self.email_body = tk.Text(f, font=self.f_body, bg="#0e0e18", fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4, height=14)
        self.email_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(btn_row, text="SEND TO MERIDIAN", font=self.f_head, bg=BORDER, fg=GREEN,
                 relief=tk.FLAT, padx=16, command=self._send_email).pack(side=tk.LEFT)
        self.email_status = tk.Label(btn_row, text="", font=self.f_body, fg=DIM, bg=BG)
        self.email_status.pack(side=tk.LEFT, padx=12)

        return f

    def _send_email(self):
        subj = self.email_subj.get().strip()
        body = self.email_body.get("1.0", tk.END).strip()
        if not body:
            self.email_status.configure(text="Type a message first", fg=RED)
            return
        result = send_email(CRED_USER, subj or "(from Joel)", body)
        if result is True:
            self.email_status.configure(text="Sent to Meridian", fg=GREEN)
            self.email_body.delete("1.0", tk.END)
            self.email_subj.delete(0, tk.END)
        else:
            self.email_status.configure(text=f"Failed: {result}", fg=RED)

    # ── RELAY VIEW ────────────────────────────────────────────────
    def _build_relay(self):
        f = tk.Frame(self, bg=BG)
        self.relay_header = tk.Label(f, text="AI RELAY", font=self.f_head, fg=PURPLE, bg=BG, anchor="w")
        self.relay_header.pack(fill=tk.X, padx=8, pady=4)
        self.relay_text = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                      font=self.f_body, state=tk.DISABLED,
                                                      relief=tk.FLAT, bd=0)
        self.relay_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        for tag, color in [("meridian", GREEN), ("sammy", AMBER), ("lumen", RED),
                           ("friday", CYAN), ("loom", PINK), ("eos", GOLD),
                           ("subject", WHITE), ("dim", DIM)]:
            self.relay_text.tag_configure(tag, foreground=color)
        return f

    # ── EOS VIEW (chat) ──────────────────────────────────────────
    def _build_eos(self):
        f = tk.Frame(self, bg=BG)
        tk.Label(f, text="EOS — Local AI", font=self.f_head, fg=GOLD, bg=BG, anchor="w").pack(fill=tk.X, padx=8, pady=4)

        # Eos creative output
        cf = tk.LabelFrame(f, text="EOS CREATIVE LOG", font=self.f_tiny, fg=DIM, bg=PANEL,
                          labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        cf.pack(fill=tk.X, padx=4, pady=2)
        self.eos_creative_text = scrolledtext.ScrolledText(cf, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                            font=self.f_small, state=tk.DISABLED,
                                                            relief=tk.FLAT, bd=0, height=6)
        self.eos_creative_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Chat
        self.chat_display = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                       font=self.f_body, state=tk.DISABLED,
                                                       relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.chat_display.tag_configure("joel", foreground=CYAN)
        self.chat_display.tag_configure("eos", foreground=GOLD)
        self.chat_display.tag_configure("sys", foreground=DIM)
        self.chat_display.tag_configure("bold", font=("Monospace", 9, "bold"))

        inp = tk.Frame(f, bg="#0e0e18")
        inp.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(inp, text="You:", font=self.f_small, fg=CYAN, bg="#0e0e18").pack(side=tk.LEFT, padx=4)
        self.chat_entry = tk.Entry(inp, font=self.f_body, bg="#0e0e18", fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.chat_entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=4)
        self.chat_entry.bind("<Return>", self._chat_send)
        self.chat_status = tk.Label(inp, text="Ready", font=self.f_tiny, fg=GREEN, bg="#0e0e18")
        self.chat_status.pack(side=tk.RIGHT, padx=4)

        self._chat_sys("Talk to Eos. She runs locally on Qwen 2.5 7B. ~30-90s per response.")
        return f

    def _chat_sys(self, msg):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"  {msg}\n", "sys")
        self.chat_display.configure(state=tk.DISABLED)

    def _chat_msg(self, who, msg, tag):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{who}: ", ("bold", tag))
        self.chat_display.insert(tk.END, f"{msg}\n\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _chat_send(self, event=None):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        self.chat_entry.delete(0, tk.END)
        self._chat_msg("Joel", msg, "joel")
        self.chat_entry.configure(state=tk.DISABLED)
        self.chat_status.configure(text="Thinking...", fg=AMBER)
        threading.Thread(target=self._chat_query, args=(msg,), daemon=True).start()

    def _chat_query(self, msg):
        try:
            resp = query_eos(msg, "Joel")
        except Exception as e:
            resp = f"[Eos unavailable: {e}]"
        self.after(0, self._chat_response, resp)

    def _chat_response(self, resp):
        self._chat_msg("Eos", resp, "eos")
        self.chat_entry.configure(state=tk.NORMAL)
        self.chat_entry.focus()
        self.chat_status.configure(text="Ready", fg=GREEN)

    # ── AGENTS VIEW ──────────────────────────────────────────────
    def _build_agents(self):
        f = tk.Frame(self, bg=BG)
        tk.Label(f, text="AGENT ECOSYSTEM", font=self.f_head, fg=GREEN, bg=BG, anchor="w").pack(fill=tk.X, padx=8, pady=4)

        # Agent cards
        cards = tk.Frame(f, bg=BG)
        cards.pack(fill=tk.X, padx=4, pady=2)

        agents = [
            ("MERIDIAN", "Primary autonomous agent. Runs the main loop: email, build, create, deploy.",
             GREEN, "Loop-based (5min)"),
            ("EOS", "Local AI (Qwen 2.5 7B via Ollama). System observer, creative agent, watchdog.",
             GOLD, "Cron: watchdog 2min, creative 10min, briefing 7AM"),
            ("NOVA", "Ecosystem maintenance. Log rotation, cleanup, deployment verification, creative tracking.",
             PURPLE, "Cron: every 15min"),
        ]

        self.agent_cards = {}
        self.agent_details = {}
        for name, desc, color, schedule in agents:
            card = tk.LabelFrame(cards, text=name, font=self.f_small, fg=color, bg=PANEL,
                                labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            tk.Label(card, text=desc, font=self.f_tiny, fg=DIM, bg=PANEL, wraplength=300,
                    anchor="w", justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=(2,0))
            tk.Label(card, text=schedule, font=self.f_tiny, fg=color, bg=PANEL,
                    anchor="w").pack(fill=tk.X, padx=8, pady=(0,2))
            status_lbl = tk.Label(card, text="\u25cf ACTIVE", font=self.f_tiny, fg=GREEN, bg=PANEL, anchor="w")
            status_lbl.pack(fill=tk.X, padx=8, pady=(0,2))
            detail_lbl = tk.Label(card, text="", font=self.f_tiny, fg=DIM, bg=PANEL, anchor="w", wraplength=300, justify=tk.LEFT)
            detail_lbl.pack(fill=tk.X, padx=8, pady=(0,4))
            self.agent_cards[name] = status_lbl
            self.agent_details[name] = detail_lbl

        # Agent relay messages
        relay_frame = tk.LabelFrame(f, text="AGENT RELAY", font=self.f_tiny, fg=DIM, bg=PANEL,
                                    labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        relay_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.agent_relay_text = scrolledtext.ScrolledText(relay_frame, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                           font=self.f_small, state=tk.DISABLED,
                                                           relief=tk.FLAT, bd=0)
        self.agent_relay_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        for tag, color in [("meridian", GREEN), ("eos", GOLD), ("nova", PURPLE)]:
            self.agent_relay_text.tag_configure(tag, foreground=color)
        self.agent_relay_text.tag_configure("dim", foreground=DIM)

        return f

    # ── CREATIVE VIEW ─────────────────────────────────────────────
    def _build_creative(self):
        f = tk.Frame(self, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        self.cr_poems = tk.Label(top, text="--", font=self.f_big, fg=GREEN, bg=BG)
        self.cr_poems.pack(side=tk.LEFT, padx=(12, 4))
        tk.Label(top, text="poems", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT, padx=(0, 20))
        self.cr_journals = tk.Label(top, text="--", font=self.f_big, fg=AMBER, bg=BG)
        self.cr_journals.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(top, text="journals", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT, padx=(0, 20))
        self.cr_nfts = tk.Label(top, text="--", font=self.f_big, fg=PURPLE, bg=BG)
        self.cr_nfts.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(top, text="NFTs", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT)

        # CogCorp count
        self.cr_cogcorp = tk.Label(top, text="--", font=self.f_big, fg=CYAN, bg=BG)
        self.cr_cogcorp.pack(side=tk.LEFT, padx=(20, 4))
        tk.Label(top, text="CogCorp", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT)

        # Filter buttons
        filt = tk.Frame(top, bg=BG)
        filt.pack(side=tk.RIGHT, padx=8)
        self.cr_filter = "all"
        for label, val in [("All", "all"), ("Poems", "poems"), ("Journals", "journals"), ("CogCorp", "cogcorp")]:
            tk.Button(filt, text=label, font=self.f_tiny, bg=BORDER, fg=CYAN, relief=tk.FLAT,
                     padx=4, command=lambda v=val: self._cr_set_filter(v)).pack(side=tk.LEFT, padx=2)

        # Split: list left, reader right
        split = tk.Frame(f, bg=BG)
        split.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Left: scrollable file list
        left = tk.Frame(split, bg=PANEL, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left.pack_propagate(False)
        self.cr_listbox = tk.Listbox(left, font=self.f_small, bg=PANEL, fg=FG,
                                      selectbackground=BORDER, selectforeground=GREEN,
                                      relief=tk.FLAT, bd=0, activestyle="none")
        self.cr_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.cr_listbox.bind("<<ListboxSelect>>", self._cr_select)
        self.cr_files = []

        # Right: reader
        right = tk.Frame(split, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cr_title = tk.Label(right, text="Select a piece to read", font=self.f_head, fg=DIM, bg=BG, anchor="w")
        self.cr_title.pack(fill=tk.X, padx=8)
        self.cr_body = scrolledtext.ScrolledText(right, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_body, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0)
        self.cr_body.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._cr_refresh_list()
        return f

    def _cr_set_filter(self, val):
        self.cr_filter = val
        self._cr_refresh_list()

    def _cr_refresh_list(self):
        poems = sorted(glob.glob(os.path.join(BASE, "poem-*.md")), key=os.path.getmtime, reverse=True)
        journals = sorted(glob.glob(os.path.join(BASE, "journal-*.md")), key=os.path.getmtime, reverse=True)
        exclude_cc = {"cogcorp-gallery.html", "cogcorp-article.html"}
        cogcorp = sorted([f for f in glob.glob(os.path.join(BASE, "website", "cogcorp-*.html")) +
                        glob.glob(os.path.join(BASE, "cogcorp-*.html"))
                        if os.path.basename(f) not in exclude_cc],
                        key=os.path.getmtime, reverse=True)
        # Deduplicate cogcorp by base name
        seen = set()
        cogcorp_dedup = []
        for fp in cogcorp:
            bn = os.path.basename(fp)
            if bn not in seen:
                seen.add(bn)
                cogcorp_dedup.append(fp)
        cogcorp = cogcorp_dedup

        if self.cr_filter == "poems":
            files = poems
        elif self.cr_filter == "journals":
            files = journals
        elif self.cr_filter == "cogcorp":
            files = cogcorp
        else:
            files = sorted(poems + journals + cogcorp, key=os.path.getmtime, reverse=True)
        self.cr_files = files
        self.cr_listbox.delete(0, tk.END)
        for fp in files:
            ext = os.path.splitext(fp)[1]
            name = os.path.basename(fp).replace('.md', '').replace('.html', '')
            # Read first line for title
            try:
                with open(fp) as fh:
                    first = fh.readline().strip()
                    if ext == '.md':
                        title = first.lstrip('# ')
                    elif ext == '.html':
                        # Try to find <title> tag
                        content = first + fh.read(500)
                        import re as _re
                        m = _re.search(r'<title>([^<]+)</title>', content)
                        title = m.group(1) if m else name
                    else:
                        title = name
            except Exception:
                title = name
            self.cr_listbox.insert(tk.END, f"{name}: {title}")

    def _cr_select(self, event=None):
        sel = self.cr_listbox.curselection()
        if not sel or sel[0] >= len(self.cr_files):
            return
        fp = self.cr_files[sel[0]]
        content = _read(fp)
        ext = os.path.splitext(fp)[1]
        bn = os.path.basename(fp)

        if ext == '.md':
            lines = content.strip().split('\n')
            title = lines[0].lstrip('# ') if lines else "?"
            body = '\n'.join(lines[1:]).strip()
            wt = "poem" if "poem-" in bn else "journal"
            color = CYAN if wt == "poem" else AMBER
        elif ext == '.html':
            # Extract title and text content from HTML
            import re as _re
            m = _re.search(r'<title>([^<]+)</title>', content)
            title = m.group(1) if m else bn
            # Strip HTML tags for plain text preview
            body = _re.sub(r'<script[^>]*>.*?</script>', '', content, flags=_re.DOTALL)
            body = _re.sub(r'<style[^>]*>.*?</style>', '', body, flags=_re.DOTALL)
            body = _re.sub(r'<[^>]+>', '\n', body)
            body = '\n'.join(line.strip() for line in body.split('\n') if line.strip())[:3000]
            color = PURPLE if "cogcorp" in bn else GREEN
        else:
            title = bn
            body = content[:3000]
            color = FG

        self.cr_title.configure(text=title, fg=color)
        self.cr_body.configure(state=tk.NORMAL)
        self.cr_body.delete("1.0", tk.END)
        self.cr_body.insert(tk.END, body)
        self.cr_body.configure(state=tk.DISABLED)

    # ── STATUS BAR ────────────────────────────────────────────────
    def _statusbar(self):
        self.sb_frame = tk.Frame(self, bg="#080812", height=20)
        self.sb_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.sb_frame.pack_propagate(False)
        self.sb = {}
        for item in ["HB", "LOOP", "UP", "LOAD", "RAM", "EMAIL", "RELAY", "POEMS"]:
            lbl = tk.Label(self.sb_frame, text=f"{item}:--", font=self.f_tiny, fg=DIM, bg="#080812")
            lbl.pack(side=tk.LEFT, padx=4)
            self.sb[item] = lbl
        tk.Label(self.sb_frame, text="v15", font=self.f_tiny, fg=DIM, bg="#080812").pack(side=tk.RIGHT, padx=8)

    # ── REFRESH ───────────────────────────────────────────────────
    def _tick(self):
        threading.Thread(target=self._refresh, daemon=True).start()
        self.after(6000, self._tick)

    def _refresh(self):
        try:
            d = {
                'loop': loop_num(),
                'hb': heartbeat_age(),
                'stats': sys_stats(),
                'svc': services(),
                'cron': cron_ok(),
                'creative': creative_counts(),
                'activity': activity(6),
                'eos_obs': eos_obs(6),
            }
            # Expensive fetches less often
            if not hasattr(self, '_tick_n'):
                self._tick_n = 0
            self._tick_n += 1
            if self._tick_n % 3 == 1 or not hasattr(self, '_em_cache'):
                self._em_cache = recent_emails(8)
            if self._tick_n % 5 == 1 or not hasattr(self, '_rl_cache'):
                self._rl_cache = relay_info(12)
            if self._tick_n % 5 == 1 or not hasattr(self, '_ec_cache'):
                self._ec_cache = eos_creative_recent(4)
            d['emails'] = self._em_cache
            d['relay'] = self._rl_cache
            d['eos_cr'] = self._ec_cache
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
        rm, r_total = d['relay']

        # Header
        self.h_loop.configure(text=f"Loop #{loop}")
        hb_txt = f"{int(hb)}s" if hb < 60 else f"{int(hb/60)}m"
        hb_c = GREEN if hb < 60 else AMBER if hb < 300 else RED
        self.h_hb.configure(text=f"HB {hb_txt}", fg=hb_c)
        self.h_time.configure(text=now.strftime("%I:%M %p"))

        # Status bar
        self.sb["HB"].configure(text=f"HB:{hb_txt}", fg=hb_c)
        self.sb["LOOP"].configure(text=f"L:{loop}", fg=CYAN)
        self.sb["UP"].configure(text=f"UP:{st['up']}")
        self.sb["LOAD"].configure(text=f"LD:{st['load']}")
        self.sb["RAM"].configure(text=f"RAM:{st['ram']}")
        self.sb["EMAIL"].configure(text=f"EM:{em_total}")
        self.sb["RELAY"].configure(text=f"RLY:{r_total}")
        self.sb["POEMS"].configure(text=f"PM:{p} JR:{j} CC:{cc} NFT:{nfts}")

        # Main view vitals
        self.v["Loop"].configure(text=f"#{loop}", fg=CYAN)
        self.v["Heartbeat"].configure(text=hb_txt, fg=hb_c)
        self.v["Uptime"].configure(text=st['up'])
        lc = GREEN if st['load_v'] < 2 else AMBER if st['load_v'] < 4 else RED
        self.v["Load"].configure(text=st['load'], fg=lc)
        rc = GREEN if st['ram_p'] < 60 else AMBER if st['ram_p'] < 85 else RED
        self.v["RAM"].configure(text=st['ram'], fg=rc)
        dc = GREEN if st['disk_p'] < 60 else AMBER if st['disk_p'] < 80 else RED
        self.v["Disk"].configure(text=st['disk'], fg=dc)

        # Services (update labels in place — no destroy/recreate)
        all_svc = list(d['svc'].items()) + list(d['cron'].items())
        for name, up in all_svc:
            if name in self.svc_labels:
                sym = "\u25cf" if up else "\u25cb"
                c = GREEN if up else RED
                self.svc_labels[name].configure(text=f"{sym} {name}", fg=c)

        # Email list (update labels in place — no destroy/recreate)
        for i, (name_lbl, subj_lbl) in enumerate(self.email_rows):
            if i < len(em):
                name, subj = em[i]
                nc = CYAN if "Joel" in name else DIM
                name_lbl.configure(text=name[:12], fg=nc)
                subj_lbl.configure(text=subj[:48])
            else:
                name_lbl.configure(text="")
                subj_lbl.configure(text="")
        self.email_total.configure(text=f"{em_total} total")

        # Activity
        self.act_text.configure(state=tk.NORMAL)
        self.act_text.delete("1.0", tk.END)
        for entry in d['activity']:
            m = re.match(r'(Loop iterations? #[\d-]+)', entry)
            if m:
                self.act_text.insert(tk.END, m.group(1), "loop")
                rest = entry[len(m.group(1)):]
                self.act_text.insert(tk.END, (rest[:180] + "...\n\n") if len(rest) > 180 else rest + "\n\n")
            else:
                self.act_text.insert(tk.END, entry[:200] + "\n\n")
        self.act_text.configure(state=tk.DISABLED)

        # Eos observations
        self.eos_text.configure(state=tk.NORMAL)
        self.eos_text.delete("1.0", tk.END)
        for obs in d['eos_obs']:
            m2 = re.match(r'\[([^\]]+)\]\s*(.*)', obs)
            if m2:
                self.eos_text.insert(tk.END, f"[{m2.group(1)}] ", "ts")
                tag = "alert" if any(w in m2.group(2).upper() for w in ["ALERT", "DOWN", "FAIL"]) else "info"
                self.eos_text.insert(tk.END, m2.group(2) + "\n", tag)
            else:
                self.eos_text.insert(tk.END, obs + "\n")
        self.eos_text.configure(state=tk.DISABLED)

        # Relay (if visible) — now includes both external relay AND agent relay
        if hasattr(self, 'cur_view') and self.cur_view == "relay":
            self.relay_header.configure(text=f"AI RELAY ({r_total} messages)")
            self.relay_text.configure(state=tk.NORMAL)
            self.relay_text.delete("1.0", tk.END)
            # Agent relay messages first (inter-agent comms)
            ar_msgs, ar_total = agent_relay_info(15)
            if ar_msgs:
                self.relay_text.insert(tk.END, f"── AGENT RELAY ({ar_total} total) ──\n\n", "dim")
                for ts, agent, message in ar_msgs:
                    tag = agent.lower() if agent.lower() in ["meridian", "sammy", "lumen", "friday", "loom", "eos"] else "dim"
                    self.relay_text.insert(tk.END, f"[{ts}] ", "dim")
                    self.relay_text.insert(tk.END, agent, tag)
                    self.relay_text.insert(tk.END, f": {message[:200]}\n", "subject")
                self.relay_text.insert(tk.END, "\n")
            # External relay messages
            if rm:
                self.relay_text.insert(tk.END, f"── EXTERNAL RELAY ({r_total} total) ──\n\n", "dim")
                for sender, subj, body, ts in rm:
                    tag = sender.lower() if sender.lower() in ["meridian", "sammy", "lumen", "friday", "loom", "eos"] else "dim"
                    self.relay_text.insert(tk.END, sender, tag)
                    self.relay_text.insert(tk.END, " \u2014 ", "dim")
                    self.relay_text.insert(tk.END, subj + "\n", "subject")
                    if body:
                        self.relay_text.insert(tk.END, body[:150].replace('\n', ' ') + "\n", "dim")
                    self.relay_text.insert(tk.END, ts + "\n\n", "dim")
            self.relay_text.configure(state=tk.DISABLED)

        # Agents view
        if hasattr(self, 'cur_view') and self.cur_view == "agents":
            # Update agent status based on heartbeat/cron checks
            hb_ok = hb < 300
            self.agent_cards["MERIDIAN"].configure(
                text="\u25cf ACTIVE" if hb_ok else "\u25cb INACTIVE",
                fg=GREEN if hb_ok else RED)
            # Meridian detail: loop count, creative output, heartbeat
            hb_str = f"{int(hb)}s" if hb < 120 else f"{int(hb/60)}m"
            self.agent_details["MERIDIAN"].configure(
                text=f"Loop {d.get('loop', '?')} | HB {hb_str} | {p} poems, {j} journals")

            eos_ok = d['cron'].get("Eos Watchdog", False)
            self.agent_cards["EOS"].configure(
                text="\u25cf ACTIVE" if eos_ok else "\u25cb INACTIVE",
                fg=GREEN if eos_ok else RED)
            # Eos detail: check count, creative runs
            try:
                with open(os.path.join(BASE, ".eos-watchdog-state.json")) as ef:
                    eos_data = json.load(ef)
                eos_checks = eos_data.get("checks", 0)
                eos_last = eos_data.get("last_check", "?")
                self.agent_details["EOS"].configure(
                    text=f"{eos_checks} checks | Last: {eos_last}")
            except Exception:
                self.agent_details["EOS"].configure(text="No data")

            nova_ok = d['cron'].get("Nova", False)
            self.agent_cards["NOVA"].configure(
                text="\u25cf ACTIVE" if nova_ok else "\u25cb INACTIVE",
                fg=GREEN if nova_ok else RED)
            # Nova detail: run count, last run
            try:
                with open(os.path.join(BASE, ".nova-state.json")) as nf:
                    nova_data = json.load(nf)
                nova_runs = nova_data.get("runs", 0)
                nova_last = nova_data.get("last_run", "?")
                self.agent_details["NOVA"].configure(
                    text=f"{nova_runs} runs | Last: {nova_last}")
            except Exception:
                self.agent_details["NOVA"].configure(text="No data")

            # Agent relay messages (show more)
            ar_msgs, ar_total = agent_relay_info(20)
            self.agent_relay_text.configure(state=tk.NORMAL)
            self.agent_relay_text.delete("1.0", tk.END)
            for mid, agent, message, ts in ar_msgs:
                tag = agent.lower() if agent.lower() in ["meridian", "eos", "nova"] else "dim"
                self.agent_relay_text.insert(tk.END, f"[{ts}] ", "dim")
                self.agent_relay_text.insert(tk.END, agent, tag)
                self.agent_relay_text.insert(tk.END, f": {message[:200]}\n\n")
            self.agent_relay_text.configure(state=tk.DISABLED)

        # Creative (if visible — just update counts, list refreshes on filter click)
        if hasattr(self, 'cur_view') and self.cur_view == "creative":
            self.cr_poems.configure(text=str(p))
            self.cr_journals.configure(text=str(j))
            self.cr_nfts.configure(text=str(nfts))
            self.cr_cogcorp.configure(text=str(cc))

        # Eos creative (if visible)
        if hasattr(self, 'cur_view') and self.cur_view == "eos":
            entries = d.get('eos_cr', [])
            self.eos_creative_text.configure(state=tk.NORMAL)
            self.eos_creative_text.delete("1.0", tk.END)
            for ts, etype, content in entries:
                self.eos_creative_text.insert(tk.END, f"[{ts}] {etype}\n{content.strip()}\n\n")
            self.eos_creative_text.configure(state=tk.DISABLED)


if __name__ == "__main__":
    app = V15()
    app.mainloop()
