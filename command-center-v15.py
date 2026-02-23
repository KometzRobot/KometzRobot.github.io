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

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1143
SMTP_HOST, SMTP_PORT = "127.0.0.1", 1025
CRED_USER = "kometzrobot@proton.me"
CRED_PASS = "2DTEz9UgO6nFqmlMxHzuww"
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
    for line in _read(WAKE).split('\n'):
        m = re.search(r'Loop iterations? #(\d+)', line)
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
        "Command Center": "command-center-v15",
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
    return p, j

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

def activity(n=6):
    lines = []
    for line in _read(WAKE).split('\n'):
        if re.match(r'^- Loop iteration', line):
            lines.append(line.strip('- '))
            if len(lines) >= n:
                break
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
        s.login(CRED_USER, CRED_PASS)
        s.sendmail(CRED_USER, to, msg.as_string())
        s.quit()
        return True
    except Exception as e:
        return str(e)


# ── COMMAND TO MERIDIAN ───────────────────────────────────────────
def send_command(cmd):
    """Write a command to /tmp/joel-commands.txt for Meridian to pick up."""
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
    with urllib.request.urlopen(req, timeout=180) as resp:
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
        for name in ["main", "email", "relay", "eos", "creative"]:
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
        self.email_total = tk.Label(ef, text="", font=self.f_tiny, fg=CYAN, bg=PANEL, anchor="e")
        self.email_total.pack(fill=tk.X, padx=8)

        # Eos observations
        eof = tk.LabelFrame(left, text="EOS OBSERVATIONS", font=self.f_tiny, fg=DIM, bg=PANEL,
                           labelanchor="nw", bd=1, relief=tk.SOLID, highlightbackground=BORDER)
        eof.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.eos_text = scrolledtext.ScrolledText(eof, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_tiny, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0, height=6)
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

    # ── EMAIL VIEW ────────────────────────────────────────────────
    def _build_email(self):
        f = tk.Frame(self, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill=tk.X, padx=4, pady=4)

        tk.Label(top, text="COMPOSE EMAIL", font=self.f_head, fg=WHITE, bg=BG).pack(anchor="w")

        row1 = tk.Frame(f, bg=BG)
        row1.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(row1, text="To:", font=self.f_body, fg=DIM, bg=BG, width=8).pack(side=tk.LEFT)
        self.email_to = tk.Entry(row1, font=self.f_body, bg="#0e0e18", fg=FG,
                                insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_to.pack(fill=tk.X, side=tk.LEFT, expand=True)

        row2 = tk.Frame(f, bg=BG)
        row2.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(row2, text="Subject:", font=self.f_body, fg=DIM, bg=BG, width=8).pack(side=tk.LEFT)
        self.email_subj = tk.Entry(row2, font=self.f_body, bg="#0e0e18", fg=FG,
                                   insertbackground=FG, relief=tk.FLAT, bd=4)
        self.email_subj.pack(fill=tk.X, side=tk.LEFT, expand=True)

        # Quick recipients
        qr = tk.Frame(f, bg=BG)
        qr.pack(fill=tk.X, padx=8, pady=2)
        for name, addr in [("Meridian", CRED_USER), ("Sammy", "sammyqjankis@proton.me"),
                          ("Chris", "chriskometz@gmail.com")]:
            tk.Button(qr, text=name, font=self.f_tiny, bg=BORDER, fg=CYAN, relief=tk.FLAT,
                     padx=4, command=lambda a=addr: self.email_to.insert(0, a) or None).pack(side=tk.LEFT, padx=2)

        self.email_body = tk.Text(f, font=self.f_body, bg="#0e0e18", fg=FG,
                                  insertbackground=FG, relief=tk.FLAT, bd=4, height=12)
        self.email_body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(btn_row, text="SEND", font=self.f_head, bg=BORDER, fg=GREEN,
                 relief=tk.FLAT, padx=16, command=self._send_email).pack(side=tk.LEFT)
        self.email_status = tk.Label(btn_row, text="", font=self.f_body, fg=DIM, bg=BG)
        self.email_status.pack(side=tk.LEFT, padx=12)

        return f

    def _send_email(self):
        to = self.email_to.get().strip()
        subj = self.email_subj.get().strip()
        body = self.email_body.get("1.0", tk.END).strip()
        if not to or not body:
            self.email_status.configure(text="Need recipient and body", fg=RED)
            return
        result = send_email(to, subj or "(no subject)", body)
        if result is True:
            self.email_status.configure(text=f"Sent to {to}", fg=GREEN)
            self.email_body.delete("1.0", tk.END)
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
        tk.Label(top, text="journals", font=self.f_small, fg=DIM, bg=BG).pack(side=tk.LEFT)

        self.cr_title = tk.Label(f, text="", font=self.f_head, fg=WHITE, bg=BG, anchor="w")
        self.cr_title.pack(fill=tk.X, padx=12)
        self.cr_body = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg=PANEL, fg=FG,
                                                   font=self.f_body, state=tk.DISABLED,
                                                   relief=tk.FLAT, bd=0)
        self.cr_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        return f

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
        self.after(4000, self._tick)

    def _refresh(self):
        try:
            d = {
                'loop': loop_num(),
                'hb': heartbeat_age(),
                'stats': sys_stats(),
                'svc': services(),
                'cron': cron_ok(),
                'poems_j': creative_counts(),
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
        p, j = d['poems_j']
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
        self.sb["POEMS"].configure(text=f"PM:{p} JR:{j}")

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

        # Services
        for w in list(self.svc_frame.winfo_children()):
            if not isinstance(w, tk.Label) or w.cget("font") == "TkDefaultFont":
                pass
            # Clear dynamic widgets
        for w in [w for w in self.svc_frame.winfo_children() if isinstance(w, tk.Frame)]:
            w.destroy()

        all_svc = list(d['svc'].items()) + list(d['cron'].items())
        for name, up in all_svc:
            row = tk.Frame(self.svc_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=8, pady=0)
            sym = "\u25cf" if up else "\u25cb"
            c = GREEN if up else RED
            tk.Label(row, text=f"{sym} {name}", font=self.f_tiny, fg=c, bg=PANEL, anchor="w").pack(side=tk.LEFT)

        # Email list
        for w in self.email_list.winfo_children():
            w.destroy()
        for name, subj in em[:6]:
            row = tk.Frame(self.email_list, bg=PANEL)
            row.pack(fill=tk.X)
            nc = CYAN if "Joel" in name else DIM
            tk.Label(row, text=name[:12], font=self.f_tiny, fg=nc, bg=PANEL, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=subj[:48], font=self.f_tiny, fg=FG, bg=PANEL, anchor="w").pack(side=tk.LEFT)
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

        # Relay (if visible)
        if hasattr(self, 'cur_view') and self.cur_view == "relay":
            self.relay_header.configure(text=f"AI RELAY ({r_total} messages)")
            self.relay_text.configure(state=tk.NORMAL)
            self.relay_text.delete("1.0", tk.END)
            for sender, subj, body, ts in rm:
                tag = sender.lower() if sender.lower() in ["meridian", "sammy", "lumen", "friday", "loom", "eos"] else "dim"
                self.relay_text.insert(tk.END, sender, tag)
                self.relay_text.insert(tk.END, " \u2014 ", "dim")
                self.relay_text.insert(tk.END, subj + "\n", "subject")
                if body:
                    self.relay_text.insert(tk.END, body[:150].replace('\n', ' ') + "\n", "dim")
                self.relay_text.insert(tk.END, ts + "\n\n", "dim")
            self.relay_text.configure(state=tk.DISABLED)

        # Creative (if visible)
        if hasattr(self, 'cur_view') and self.cur_view == "creative":
            self.cr_poems.configure(text=str(p))
            self.cr_journals.configure(text=str(j))
            # Get latest writing
            files = sorted(
                glob.glob(os.path.join(BASE, "poem-*.md")) + glob.glob(os.path.join(BASE, "journal-*.md")),
                key=os.path.getmtime, reverse=True
            )
            if files:
                content = _read(files[0])
                lines = content.strip().split('\n')
                title = lines[0].lstrip('# ') if lines else "?"
                body = '\n'.join(l for l in lines[1:] if l.strip() and not l.startswith('*'))[:800]
                wt = "poem" if "poem-" in files[0] else "journal"
                self.cr_title.configure(text=title, fg=CYAN if wt == "poem" else AMBER)
                self.cr_body.configure(state=tk.NORMAL)
                self.cr_body.delete("1.0", tk.END)
                self.cr_body.insert(tk.END, body)
                self.cr_body.configure(state=tk.DISABLED)

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
