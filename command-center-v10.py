#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v10 — Full Redo
Built because Joel said: "Do a version 10 with full top to bottom redo"

Layout:
  TOP BAR: Loop # | Heartbeat | Emails | Services | Time
  LEFT PANEL (40%): Live activity feed + system status + creative works
  RIGHT PANEL (60%): Eos Chat — always visible, big text, easy to use

One window. Everything visible. No tabs needed.
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont
import threading
import json
import urllib.request
import os
import subprocess
import time
import glob
import re
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = '/home/joel/autonomous-ai'
HEARTBEAT = f'{BASE}/.heartbeat'
WAKE_STATE = f'{BASE}/wake-state.md'
MEMORY_FILE = f'{BASE}/assistant-memory.json'
CHAT_LOG_DIR = os.path.expanduser('~/Desktop/Creative Work/Both EOS + MERIDIAN')
CHAT_LOG = f'{CHAT_LOG_DIR}/chat-log.txt'

# ── Eos Config ───────────────────────────────────────────────────────────────
MODEL = "eos-7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

# ── Colors — clean, modern, dark ─────────────────────────────────────────────
BG = '#0d1117'
SIDEBAR_BG = '#161b22'
HEADER_BG = '#1c2128'
CARD_BG = '#1c2128'
BORDER = '#30363d'
FG = '#e6edf3'
FG_DIM = '#7d8590'
FG_MUTED = '#484f58'
GREEN = '#3fb950'
BLUE = '#58a6ff'
PURPLE = '#d2a8ff'
ORANGE = '#d29922'
RED = '#f85149'
CYAN = '#76e4f7'
CHAT_BG = '#0d1117'
INPUT_BG = '#21262d'
ACCENT = '#1f6feb'


# ── Helper functions ─────────────────────────────────────────────────────────

def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(HEARTBEAT))
    except:
        return -1


def get_loop_info():
    """Parse latest loop number and details from wake-state."""
    try:
        with open(WAKE_STATE, 'r') as f:
            for line in f:
                if line.startswith('- Loop iteration #'):
                    m = re.search(r'#(\d+)\s+COMPLETE\.\s*(.*)', line)
                    if m:
                        return int(m.group(1)), m.group(2).strip()[:300]
    except:
        pass
    return 0, "Unknown"


def get_recent_loops(n=6):
    """Get last N loop summaries."""
    results = []
    try:
        with open(WAKE_STATE, 'r') as f:
            for line in f:
                if line.startswith('- Loop iteration #'):
                    m = re.search(r'#(\d+)\s+COMPLETE\.\s*(.*)', line)
                    if m:
                        results.append((int(m.group(1)), m.group(2).strip()[:200]))
                    if len(results) >= n:
                        break
    except:
        pass
    return results


def get_email_count():
    try:
        import imaplib
        M = imaplib.IMAP4('127.0.0.1', 1143)
        M.login('kometzrobot@proton.me', '2DTEz9UgO6nFqmlMxHzuww')
        M.select('INBOX')
        _, data = M.search(None, 'ALL')
        total = len(data[0].split())
        _, data2 = M.search(None, 'UNSEEN')
        unseen = len(data2[0].split())
        M.logout()
        return total, unseen
    except:
        return 0, 0


def get_services():
    services = {}
    checks = [
        ('Bridge', 'protonmail-bridge'),
        ('IRC', 'irc-bot'),
        ('Ollama', 'ollama'),
        ('CMD CTR', 'command-center'),
    ]
    try:
        ps = subprocess.check_output(['ps', 'aux'], text=True, timeout=5)
        for name, pattern in checks:
            services[name] = pattern in ps
    except:
        pass
    return services


def get_system_info():
    info = {}
    try:
        with open('/proc/loadavg') as f:
            info['load'] = f.read().split()[0]
    except:
        info['load'] = '?'
    try:
        with open('/proc/meminfo') as f:
            mem = {}
            for line in f:
                k, v = line.split(':')
                mem[k.strip()] = int(v.strip().split()[0])
            total = mem['MemTotal'] / 1048576
            avail = mem['MemAvailable'] / 1048576
            info['ram'] = f"{total - avail:.1f}G / {total:.1f}G"
    except:
        info['ram'] = '?'
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
            h, m = divmod(secs // 60, 60)
            info['uptime'] = f"{h}h{m}m"
    except:
        info['uptime'] = '?'
    return info


def get_creative_counts():
    poems = len(glob.glob(f'{BASE}/poem-*.md'))
    journals = len(glob.glob(f'{BASE}/journal-*.md'))
    return poems, journals


def get_latest_works(kind='poem', n=5):
    pattern = f'{BASE}/{kind}-*.md'
    files = sorted(glob.glob(pattern))[-n:]
    results = []
    for path in files:
        try:
            with open(path) as f:
                title = f.readline().strip().lstrip('#').strip()
            name = os.path.basename(path).replace('.md', '')
            results.append(f"{name}: {title}")
        except:
            pass
    return results


def load_eos_memory():
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except:
        return {}


def build_eos_context(memory):
    parts = []
    if memory.get("identity"):
        parts.append(f"Your identity: {json.dumps(memory['identity'])}")
    if memory.get("relationships"):
        parts.append(f"People you know: {json.dumps(memory['relationships'])}")
    if memory.get("facts"):
        parts.append("Things you remember:\n" + "\n".join(
            f"- {f}" for f in memory["facts"][-15:]))
    if memory.get("observations"):
        parts.append("Your observations:\n" + "\n".join(
            f"- {o}" for o in memory["observations"][-5:]))
    return "\n\n".join(parts)


def query_eos(prompt, speaker="Joel"):
    memory = load_eos_memory()
    context = build_eos_context(memory)
    full = f"[YOUR MEMORY]\n{context}\n\n" if context else ""
    full += f"[{speaker} says]: {prompt}"
    data = json.dumps({
        "model": MODEL, "prompt": full, "stream": False,
        "options": {"temperature": 0.8, "num_predict": 600}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read()).get("response", "").strip()
    except Exception as e:
        return f"[Eos unavailable: {e}]"


def log_chat(speaker, message):
    os.makedirs(CHAT_LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CHAT_LOG, "a") as f:
        f.write(f"[{ts}] {speaker}: {message}\n")


# ── Main Application ─────────────────────────────────────────────────────────

class CommandCenterV10(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian Command Center v10")
        self.geometry("1200x750")
        self.configure(bg=BG)
        self.minsize(900, 550)

        self._build_header()
        self._build_main()
        self._start_refreshes()

    # ── HEADER BAR ────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=HEADER_BG, height=50)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Title
        tk.Label(hdr, text="MERIDIAN", font=('Helvetica', 16, 'bold'),
                 fg=GREEN, bg=HEADER_BG).pack(side=tk.LEFT, padx=(15, 5))
        tk.Label(hdr, text="Command Center", font=('Helvetica', 12),
                 fg=FG_DIM, bg=HEADER_BG).pack(side=tk.LEFT)

        # Right side: status indicators
        self.hdr_time = tk.Label(hdr, text="", font=('Monospace', 10),
                                  fg=FG_DIM, bg=HEADER_BG)
        self.hdr_time.pack(side=tk.RIGHT, padx=15)

        self.hdr_svc = tk.Label(hdr, text="", font=('Monospace', 10),
                                 fg=GREEN, bg=HEADER_BG)
        self.hdr_svc.pack(side=tk.RIGHT, padx=10)

        self.hdr_email = tk.Label(hdr, text="", font=('Monospace', 10),
                                   fg=BLUE, bg=HEADER_BG)
        self.hdr_email.pack(side=tk.RIGHT, padx=10)

        self.hdr_hb = tk.Label(hdr, text="", font=('Monospace', 10),
                                fg=GREEN, bg=HEADER_BG)
        self.hdr_hb.pack(side=tk.RIGHT, padx=10)

        self.hdr_loop = tk.Label(hdr, text="", font=('Monospace', 10, 'bold'),
                                  fg=CYAN, bg=HEADER_BG)
        self.hdr_loop.pack(side=tk.RIGHT, padx=10)

    # ── MAIN SPLIT PANE ──────────────────────────────────────────────────
    def _build_main(self):
        main = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BORDER,
                               sashwidth=3, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Left: Dashboard
        left = tk.Frame(main, bg=SIDEBAR_BG)
        main.add(left, width=440, minsize=300)

        # Right: Eos Chat
        right = tk.Frame(main, bg=BG)
        main.add(right, minsize=400)

        self._build_dashboard(left)
        self._build_chat(right)

    # ── DASHBOARD (LEFT) ─────────────────────────────────────────────────
    def _build_dashboard(self, parent):
        canvas = tk.Canvas(parent, bg=SIDEBAR_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.dash_frame = tk.Frame(canvas, bg=SIDEBAR_BG)

        self.dash_frame.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.dash_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        # ── Section: System Health ────────────────────────────────────────
        self._section_label(self.dash_frame, "SYSTEM HEALTH")
        self.sys_panel = tk.Text(self.dash_frame, bg=CARD_BG, fg=FG,
                                  font=('Monospace', 10), wrap=tk.WORD,
                                  relief=tk.FLAT, padx=10, pady=8, height=5,
                                  state=tk.DISABLED, highlightbackground=BORDER,
                                  highlightthickness=1)
        self.sys_panel.pack(fill=tk.X, padx=10, pady=(0, 8))

        # ── Section: Recent Activity ──────────────────────────────────────
        self._section_label(self.dash_frame, "RECENT ACTIVITY")
        self.activity_panel = tk.Text(self.dash_frame, bg=CARD_BG, fg=FG,
                                       font=('Monospace', 10), wrap=tk.WORD,
                                       relief=tk.FLAT, padx=10, pady=8, height=14,
                                       state=tk.DISABLED, highlightbackground=BORDER,
                                       highlightthickness=1)
        self.activity_panel.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.activity_panel.tag_configure("loop_num", foreground=CYAN, font=('Monospace', 10, 'bold'))
        self.activity_panel.tag_configure("dim", foreground=FG_DIM)

        # ── Section: Creative Works ───────────────────────────────────────
        self._section_label(self.dash_frame, "LATEST CREATIVE WORKS")
        self.creative_panel = tk.Text(self.dash_frame, bg=CARD_BG, fg=FG,
                                       font=('Monospace', 10), wrap=tk.WORD,
                                       relief=tk.FLAT, padx=10, pady=8, height=12,
                                       state=tk.DISABLED, highlightbackground=BORDER,
                                       highlightthickness=1)
        self.creative_panel.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.creative_panel.tag_configure("poem", foreground=CYAN)
        self.creative_panel.tag_configure("journal", foreground=ORANGE)
        self.creative_panel.tag_configure("header", foreground=FG_DIM, font=('Monospace', 9, 'bold'))

        # ── Section: Services ─────────────────────────────────────────────
        self._section_label(self.dash_frame, "SERVICES")
        self.svc_panel = tk.Text(self.dash_frame, bg=CARD_BG, fg=FG,
                                  font=('Monospace', 10), wrap=tk.WORD,
                                  relief=tk.FLAT, padx=10, pady=8, height=5,
                                  state=tk.DISABLED, highlightbackground=BORDER,
                                  highlightthickness=1)
        self.svc_panel.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.svc_panel.tag_configure("running", foreground=GREEN)
        self.svc_panel.tag_configure("stopped", foreground=RED)

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, font=('Helvetica', 10, 'bold'),
                 fg=FG_DIM, bg=SIDEBAR_BG, anchor='w'
                 ).pack(fill=tk.X, padx=12, pady=(12, 4))

    # ── EOS CHAT (RIGHT) ─────────────────────────────────────────────────
    def _build_chat(self, parent):
        # Chat header
        chat_hdr = tk.Frame(parent, bg=HEADER_BG, height=44)
        chat_hdr.pack(fill=tk.X)
        chat_hdr.pack_propagate(False)
        tk.Label(chat_hdr, text="Eos Chat", font=('Helvetica', 13, 'bold'),
                 fg=PURPLE, bg=HEADER_BG).pack(side=tk.LEFT, padx=12)
        self.eos_status = tk.Label(chat_hdr, text="Ready", font=('Monospace', 9),
                                    fg=GREEN, bg=HEADER_BG)
        self.eos_status.pack(side=tk.RIGHT, padx=12)
        tk.Label(chat_hdr, text="Qwen 7B (local)", font=('Monospace', 9),
                 fg=FG_DIM, bg=HEADER_BG).pack(side=tk.RIGHT, padx=4)

        # Chat messages area
        self.chat = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, bg=CHAT_BG, fg=FG,
            font=('Monospace', 12), insertbackground=FG,
            state=tk.DISABLED, padx=14, pady=14,
            relief=tk.FLAT, borderwidth=0
        )
        self.chat.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.chat.tag_configure("joel", foreground=BLUE, font=('Monospace', 12, 'bold'))
        self.chat.tag_configure("eos", foreground=GREEN, font=('Monospace', 12, 'bold'))
        self.chat.tag_configure("meridian", foreground=PURPLE, font=('Monospace', 12, 'bold'))
        self.chat.tag_configure("system", foreground=FG_MUTED, font=('Monospace', 10))
        self.chat.tag_configure("msg", foreground=FG)

        # Input area
        input_frame = tk.Frame(parent, bg=HEADER_BG)
        input_frame.pack(fill=tk.X)

        # Speaker row
        speaker_row = tk.Frame(input_frame, bg=HEADER_BG)
        speaker_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(speaker_row, text="Speaking as:", font=('Monospace', 9),
                 fg=FG_DIM, bg=HEADER_BG).pack(side=tk.LEFT)
        self.speaker = tk.StringVar(value="Joel")
        for name, color in [("Joel", BLUE), ("Meridian", PURPLE)]:
            btn = tk.Radiobutton(
                speaker_row, text=name, variable=self.speaker, value=name,
                font=('Monospace', 10, 'bold'), fg=color, bg=HEADER_BG,
                selectcolor=HEADER_BG, activebackground=HEADER_BG,
                activeforeground=color, indicatoron=0, padx=10, pady=2,
                relief=tk.FLAT, bd=0, highlightthickness=0
            )
            btn.pack(side=tk.LEFT, padx=6)

        # Entry row
        entry_row = tk.Frame(input_frame, bg=HEADER_BG)
        entry_row.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.entry = tk.Entry(
            entry_row, font=('Monospace', 13), bg=INPUT_BG, fg=FG,
            insertbackground=FG, relief=tk.FLAT, borderwidth=10
        )
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.entry.bind("<Return>", self._send)
        self.entry.focus_set()

        send_btn = tk.Button(
            entry_row, text="Send", font=('Helvetica', 11, 'bold'),
            bg=ACCENT, fg='#ffffff', relief=tk.FLAT, cursor='hand2',
            command=self._send, padx=20, pady=8, activebackground='#1a5cc8'
        )
        send_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # Welcome message
        self._chat_system("Eos Chat ready. Type a message below.")

        # Auto-greeting
        threading.Thread(target=self._eos_greeting, daemon=True).start()

    # ── Chat Methods ──────────────────────────────────────────────────────
    def _chat_msg(self, speaker, text, tag):
        self.chat.configure(state=tk.NORMAL)
        self.chat.insert(tk.END, f"\n{speaker}: ", tag)
        self.chat.insert(tk.END, f"{text}\n", "msg")
        self.chat.configure(state=tk.DISABLED)
        self.chat.see(tk.END)

    def _chat_system(self, text):
        self.chat.configure(state=tk.NORMAL)
        self.chat.insert(tk.END, f"  {text}\n", "system")
        self.chat.configure(state=tk.DISABLED)
        self.chat.see(tk.END)

    def _send(self, event=None):
        msg = self.entry.get().strip()
        if not msg:
            return
        speaker = self.speaker.get()
        tag = "joel" if speaker == "Joel" else "meridian"
        self.entry.delete(0, tk.END)
        self._chat_msg(speaker, msg, tag)
        log_chat(speaker, msg)
        self.entry.configure(state=tk.DISABLED)
        self.eos_status.config(text="Thinking...", fg=ORANGE)
        threading.Thread(target=self._eos_respond, args=(msg, speaker), daemon=True).start()

    def _eos_respond(self, msg, speaker):
        resp = query_eos(msg, speaker)
        log_chat("Eos", resp)
        self.after(0, self._show_eos, resp)

    def _show_eos(self, resp):
        self._chat_msg("Eos", resp, "eos")
        self.entry.configure(state=tk.NORMAL)
        self.entry.focus_set()
        self.eos_status.config(text="Ready", fg=GREEN)

    def _eos_greeting(self):
        resp = query_eos(
            "Joel just opened your chat window. Greet him warmly and briefly. You are Eos.",
            "System"
        )
        log_chat("Eos", f"[startup] {resp}")
        self.after(0, self._chat_msg, "Eos", resp, "eos")

    # ── Dashboard Refresh ─────────────────────────────────────────────────
    def _start_refreshes(self):
        self._refresh_header()
        self._refresh_system()
        self._refresh_activity()
        self._refresh_creative()
        self._refresh_services()

    def _refresh_header(self):
        try:
            loop_num, _ = get_loop_info()
            hb = get_heartbeat_age()
            now = datetime.now().strftime("%I:%M %p")

            self.hdr_loop.config(text=f"Loop #{loop_num}")

            if hb >= 0:
                hb_str = f"HB: {hb}s"
                hb_color = GREEN if hb < 60 else (ORANGE if hb < 300 else RED)
            else:
                hb_str = "HB: ?"
                hb_color = RED
            self.hdr_hb.config(text=hb_str, fg=hb_color)

            # Email count (cached, refresh every 30s)
            if not hasattr(self, '_email_cache_time') or time.time() - self._email_cache_time > 30:
                self._email_total, self._email_unseen = get_email_count()
                self._email_cache_time = time.time()
            e_text = f"Mail: {self._email_total}"
            if self._email_unseen > 0:
                e_text += f" ({self._email_unseen} new)"
            self.hdr_email.config(text=e_text)

            services = get_services()
            running = sum(1 for v in services.values() if v)
            self.hdr_svc.config(text=f"Svc: {running}/{len(services)}",
                                fg=GREEN if running >= 3 else ORANGE)

            self.hdr_time.config(text=now)
        except:
            pass
        self.after(3000, self._refresh_header)

    def _refresh_system(self):
        try:
            info = get_system_info()
            txt = (f"Load: {info['load']}    "
                   f"RAM: {info['ram']}    "
                   f"Uptime: {info['uptime']}")
            self.sys_panel.configure(state=tk.NORMAL)
            self.sys_panel.delete('1.0', tk.END)
            self.sys_panel.insert(tk.END, txt)
            self.sys_panel.configure(state=tk.DISABLED)
        except:
            pass
        self.after(10000, self._refresh_system)

    def _refresh_activity(self):
        try:
            loops = get_recent_loops(6)
            self.activity_panel.configure(state=tk.NORMAL)
            self.activity_panel.delete('1.0', tk.END)
            for num, detail in loops:
                self.activity_panel.insert(tk.END, f"#{num} ", "loop_num")
                # Truncate detail for readability
                short = detail[:160]
                if len(detail) > 160:
                    short += "..."
                self.activity_panel.insert(tk.END, f"{short}\n\n", "dim")
            self.activity_panel.configure(state=tk.DISABLED)
        except:
            pass
        self.after(8000, self._refresh_activity)

    def _refresh_creative(self):
        try:
            poems_count, journals_count = get_creative_counts()
            poems = get_latest_works('poem', 5)
            journals = get_latest_works('journal', 5)

            self.creative_panel.configure(state=tk.NORMAL)
            self.creative_panel.delete('1.0', tk.END)
            self.creative_panel.insert(tk.END,
                                        f"Total: {poems_count} poems, {journals_count} journals\n\n",
                                        "header")
            self.creative_panel.insert(tk.END, "POEMS\n", "header")
            for p in reversed(poems):
                self.creative_panel.insert(tk.END, f"  {p}\n", "poem")
            self.creative_panel.insert(tk.END, "\nJOURNALS\n", "header")
            for j in reversed(journals):
                self.creative_panel.insert(tk.END, f"  {j}\n", "journal")
            self.creative_panel.configure(state=tk.DISABLED)
        except:
            pass
        self.after(15000, self._refresh_creative)

    def _refresh_services(self):
        try:
            services = get_services()
            self.svc_panel.configure(state=tk.NORMAL)
            self.svc_panel.delete('1.0', tk.END)
            for name, running in services.items():
                tag = "running" if running else "stopped"
                icon = "+" if running else "-"
                self.svc_panel.insert(tk.END, f"  [{icon}] {name}\n", tag)
            self.svc_panel.configure(state=tk.DISABLED)
        except:
            pass
        self.after(10000, self._refresh_services)


if __name__ == '__main__':
    app = CommandCenterV10()
    app.mainloop()
