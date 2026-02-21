#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v9
One window. Everything Joel needs. Built because he asked for better UI/UX.

Tabs:
  1. DASHBOARD — live status, what Meridian is doing, email count, services
  2. EOS CHAT — talk to the local AI, bigger and better
  3. ACTIVITY — recent poems, journals, creative output
  4. SYSTEM — processes, services, logs, health
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, font as tkfont
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

# ── Colors ───────────────────────────────────────────────────────────────────
BG = '#0d1117'
BG2 = '#161b22'
BG3 = '#21262d'
BORDER = '#30363d'
FG = '#c9d1d9'
FG_DIM = '#8b949e'
FG_BRIGHT = '#f0f6fc'
GREEN = '#3fb950'
BLUE = '#58a6ff'
PURPLE = '#bc8cff'
ORANGE = '#d29922'
RED = '#f85149'
CYAN = '#39d2c0'
TAB_ACTIVE = '#1f6feb'


def read_file_tail(path, lines=20):
    """Read last N lines of a file."""
    try:
        with open(path, 'r') as f:
            content = f.readlines()
        return content[-lines:]
    except Exception:
        return []


def get_heartbeat_age():
    """Seconds since last heartbeat."""
    try:
        return int(time.time() - os.path.getmtime(HEARTBEAT))
    except Exception:
        return -1


def get_loop_info():
    """Parse latest loop info from wake-state."""
    try:
        with open(WAKE_STATE, 'r') as f:
            for line in f:
                if line.startswith('- Loop iteration #'):
                    match = re.search(r'#(\d+)\s+COMPLETE\.\s*(.*)', line)
                    if match:
                        return int(match.group(1)), match.group(2)[:200]
    except Exception:
        pass
    return 0, "Unknown"


def get_email_count():
    """Get total email count from wake-state."""
    try:
        with open(WAKE_STATE, 'r') as f:
            content = f.read()
        # Look for "Email total: NNN" in recent lines
        matches = re.findall(r'(?:Email total|Total emails?|email \((\d+) total\)|total[:\s]+(\d+))', content[:3000], re.IGNORECASE)
        # Try to find the count from latest loop
        count_match = re.search(r'(\d+)\s+total\)', content[:2000])
        if count_match:
            return int(count_match.group(1))
        # Fallback: look for email total
        for m in re.findall(r'Email total:\s*(\d+)', content[:3000]):
            return int(m)
    except Exception:
        pass
    return 0


def get_latest_creative():
    """Get latest poem and journal titles."""
    poems = sorted(glob.glob(f'{BASE}/poem-*.md'))
    journals = sorted(glob.glob(f'{BASE}/journal-*.md'))
    result = []
    for path in (poems[-3:] if poems else []):
        try:
            with open(path, 'r') as f:
                title = f.readline().strip().lstrip('#').strip()
            result.append(('poem', os.path.basename(path), title))
        except Exception:
            pass
    for path in (journals[-3:] if journals else []):
        try:
            with open(path, 'r') as f:
                title = f.readline().strip().lstrip('#').strip()
            result.append(('journal', os.path.basename(path), title))
        except Exception:
            pass
    return result


def get_services():
    """Check which services are running."""
    services = {}
    checks = {
        'Proton Bridge': 'protonmail-bridge',
        'IRC Bot': 'irc-bot',
        'Ollama': 'ollama',
        'Status Display': 'status-display',
        'Command Center': 'command-center',
    }
    try:
        ps = subprocess.check_output(['ps', 'aux'], text=True)
        for name, pattern in checks.items():
            services[name] = pattern in ps
    except Exception:
        pass
    return services


def get_system_info():
    """Get load, memory, disk."""
    info = {}
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            info['load'] = f"{parts[0]} {parts[1]} {parts[2]}"
    except Exception:
        info['load'] = '?'
    try:
        with open('/proc/meminfo', 'r') as f:
            mem = {}
            for line in f:
                k, v = line.split(':')
                mem[k.strip()] = int(v.strip().split()[0])
            total_gb = mem['MemTotal'] / 1048576
            avail_gb = mem['MemAvailable'] / 1048576
            used_gb = total_gb - avail_gb
            info['ram'] = f"{used_gb:.1f}G / {total_gb:.1f}G"
    except Exception:
        info['ram'] = '?'
    try:
        df = subprocess.check_output(['df', '-h', '/'], text=True).split('\n')[1].split()
        info['disk'] = f"{df[2]} used / {df[1]} total ({df[4]})"
    except Exception:
        info['disk'] = '?'
    try:
        with open('/proc/uptime', 'r') as f:
            secs = int(float(f.read().split()[0]))
            h, m = divmod(secs // 60, 60)
            info['uptime'] = f"{h}h {m}m"
    except Exception:
        info['uptime'] = '?'
    return info


def load_eos_memory():
    try:
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def build_eos_context(memory):
    parts = []
    if memory.get("identity"):
        parts.append(f"Your identity: {json.dumps(memory['identity'])}")
    if memory.get("relationships"):
        parts.append(f"People you know: {json.dumps(memory['relationships'])}")
    if memory.get("facts"):
        parts.append("Things you remember:\n" + "\n".join(
            f"- {f}" for f in memory["facts"][-15:]
        ))
    if memory.get("observations"):
        parts.append("Your observations:\n" + "\n".join(
            f"- {o}" for o in memory["observations"][-5:]
        ))
    return "\n\n".join(parts)


def query_eos(prompt, speaker="Joel"):
    memory = load_eos_memory()
    context = build_eos_context(memory)
    full_prompt = f"[YOUR MEMORY]\n{context}\n\n" if context else ""
    full_prompt += f"[{speaker} says]: {prompt}"
    data = json.dumps({
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 600}
    }).encode()
    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        return f"[Eos unavailable: {e}]"


def log_chat(speaker, message):
    os.makedirs(CHAT_LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CHAT_LOG, "a") as f:
        f.write(f"[{ts}] {speaker}: {message}\n")


class CommandCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian Command Center")
        self.geometry("1000x700")
        self.configure(bg=BG)
        self.minsize(800, 500)

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=BG2, foreground=FG_DIM,
                        padding=[16, 8], font=('Monospace', 11, 'bold'))
        style.map('TNotebook.Tab',
                  background=[('selected', TAB_ACTIVE)],
                  foreground=[('selected', FG_BRIGHT)])
        style.configure('TFrame', background=BG)

        # Header bar
        header = tk.Frame(self, bg=BG2, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="MERIDIAN COMMAND CENTER",
                 font=('Monospace', 14, 'bold'), fg=GREEN, bg=BG2
                 ).pack(side=tk.LEFT, padx=15)
        self.header_status = tk.Label(header, text="",
                                       font=('Monospace', 10), fg=FG_DIM, bg=BG2)
        self.header_status.pack(side=tk.RIGHT, padx=15)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 5))

        # Build tabs
        self._build_dashboard_tab()
        self._build_eos_tab()
        self._build_activity_tab()
        self._build_system_tab()

        # Start auto-refresh
        self._refresh_dashboard()
        self._refresh_activity()
        self._refresh_system()
        self._refresh_header()

    # ── DASHBOARD TAB ─────────────────────────────────────────────────────
    def _build_dashboard_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" Dashboard ")

        # Top row: status cards
        cards = tk.Frame(frame, bg=BG)
        cards.pack(fill=tk.X, padx=10, pady=10)

        # Card: Loop
        self.card_loop = self._make_card(cards, "LOOP", "---", GREEN)
        self.card_loop.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Card: Heartbeat
        self.card_hb = self._make_card(cards, "HEARTBEAT", "---", CYAN)
        self.card_hb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Card: Email
        self.card_email = self._make_card(cards, "EMAILS", "---", BLUE)
        self.card_email.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Card: Services
        self.card_svc = self._make_card(cards, "SERVICES", "---", ORANGE)
        self.card_svc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Latest loop detail
        detail_frame = tk.LabelFrame(frame, text=" Latest Loop Detail ",
                                      bg=BG, fg=FG_DIM, font=('Monospace', 10),
                                      bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.dash_detail = tk.Text(detail_frame, bg=BG, fg=FG, font=('Monospace', 11),
                                    wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                    height=6, state=tk.DISABLED)
        self.dash_detail.pack(fill=tk.BOTH, expand=True)

        # Quick context
        context_frame = tk.LabelFrame(frame, text=" What's Happening ",
                                       bg=BG, fg=FG_DIM, font=('Monospace', 10),
                                       bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        context_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.dash_context = tk.Text(context_frame, bg=BG, fg=FG, font=('Monospace', 11),
                                     wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                     height=8, state=tk.DISABLED)
        self.dash_context.pack(fill=tk.BOTH, expand=True)

    def _make_card(self, parent, label, value, color):
        card = tk.Frame(parent, bg=BG2, bd=1, relief=tk.GROOVE,
                        highlightbackground=BORDER, highlightthickness=1)
        tk.Label(card, text=label, font=('Monospace', 9, 'bold'),
                 fg=FG_DIM, bg=BG2).pack(pady=(8, 0))
        val_label = tk.Label(card, text=value, font=('Monospace', 18, 'bold'),
                             fg=color, bg=BG2)
        val_label.pack(pady=(0, 8))
        card._value_label = val_label
        return card

    def _refresh_dashboard(self):
        try:
            loop_num, loop_detail = get_loop_info()
            hb_age = get_heartbeat_age()
            email_count = get_email_count()
            services = get_services()
            running = sum(1 for v in services.values() if v)

            self.card_loop._value_label.config(text=f"#{loop_num}")
            if hb_age >= 0:
                hb_text = f"{hb_age}s ago"
                hb_color = GREEN if hb_age < 60 else (ORANGE if hb_age < 300 else RED)
            else:
                hb_text = "N/A"
                hb_color = RED
            self.card_hb._value_label.config(text=hb_text, fg=hb_color)
            self.card_email._value_label.config(text=str(email_count))
            svc_color = GREEN if running >= 3 else (ORANGE if running >= 2 else RED)
            self.card_svc._value_label.config(text=f"{running}/{len(services)}", fg=svc_color)

            # Loop detail
            self.dash_detail.configure(state=tk.NORMAL)
            self.dash_detail.delete('1.0', tk.END)
            self.dash_detail.insert(tk.END, f"Loop #{loop_num}: {loop_detail}")
            self.dash_detail.configure(state=tk.DISABLED)

            # Context: read last 5 lines of wake-state log entries
            lines = read_file_tail(WAKE_STATE, 12)
            context_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith('- Loop iteration'):
                    # Trim to key info
                    short = line[:300]
                    context_lines.append(short)
            self.dash_context.configure(state=tk.NORMAL)
            self.dash_context.delete('1.0', tk.END)
            self.dash_context.insert(tk.END, '\n'.join(context_lines[-5:]))
            self.dash_context.configure(state=tk.DISABLED)

        except Exception as e:
            pass

        self.after(5000, self._refresh_dashboard)

    # ── EOS CHAT TAB ──────────────────────────────────────────────────────
    def _build_eos_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" Eos Chat ")

        # Chat header
        eos_header = tk.Frame(frame, bg=BG2, height=36)
        eos_header.pack(fill=tk.X)
        eos_header.pack_propagate(False)
        tk.Label(eos_header, text="Talk to Eos (Qwen 7B, local)",
                 font=('Monospace', 11, 'bold'), fg=PURPLE, bg=BG2
                 ).pack(side=tk.LEFT, padx=10)
        self.eos_status_label = tk.Label(eos_header, text="Ready",
                                          font=('Monospace', 9), fg=GREEN, bg=BG2)
        self.eos_status_label.pack(side=tk.RIGHT, padx=10)

        # Chat display area — big
        self.eos_chat = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, bg=BG, fg=FG,
            font=('Monospace', 12), insertbackground=FG,
            state=tk.DISABLED, padx=12, pady=12,
            relief=tk.FLAT, borderwidth=0
        )
        self.eos_chat.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.eos_chat.tag_configure("joel", foreground=BLUE, font=('Monospace', 12, 'bold'))
        self.eos_chat.tag_configure("eos", foreground=GREEN, font=('Monospace', 12, 'bold'))
        self.eos_chat.tag_configure("meridian", foreground=PURPLE, font=('Monospace', 12, 'bold'))
        self.eos_chat.tag_configure("system", foreground=FG_DIM, font=('Monospace', 10))
        self.eos_chat.tag_configure("msg", foreground=FG, font=('Monospace', 12))

        # Input area
        input_outer = tk.Frame(frame, bg=BG2, bd=1, relief=tk.GROOVE,
                               highlightbackground=BORDER)
        input_outer.pack(fill=tk.X, padx=8, pady=8)

        # Speaker selector row
        speaker_row = tk.Frame(input_outer, bg=BG2)
        speaker_row.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(speaker_row, text="Speaking as:", font=('Monospace', 10),
                 fg=FG_DIM, bg=BG2).pack(side=tk.LEFT, padx=(0, 8))
        self.speaker = tk.StringVar(value="Joel")
        for name, color in [("Joel", BLUE), ("Meridian", PURPLE)]:
            rb = tk.Radiobutton(
                speaker_row, text=name, variable=self.speaker, value=name,
                font=('Monospace', 10, 'bold'), fg=color, bg=BG2,
                selectcolor=BG2, activebackground=BG2, activeforeground=color,
                indicatoron=0, padx=12, pady=4, relief=tk.FLAT,
                bd=0
            )
            rb.pack(side=tk.LEFT, padx=4)

        # Text entry row
        entry_row = tk.Frame(input_outer, bg=BG2)
        entry_row.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.eos_entry = tk.Entry(
            entry_row, font=('Monospace', 13), bg=BG3, fg=FG_BRIGHT,
            insertbackground=FG_BRIGHT, relief=tk.FLAT, borderwidth=10
        )
        self.eos_entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.eos_entry.bind("<Return>", self._eos_send)
        self.eos_entry.focus()

        send_btn = tk.Button(
            entry_row, text="Send", font=('Monospace', 11, 'bold'),
            bg=TAB_ACTIVE, fg=FG_BRIGHT, relief=tk.FLAT, cursor='hand2',
            command=self._eos_send, padx=20, pady=8
        )
        send_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # Initial system message
        self._eos_system("Eos Chat ready. Type a message and press Enter.")

        # Startup greeting
        threading.Thread(target=self._eos_startup_greeting, daemon=True).start()

    def _eos_show(self, speaker, message, tag):
        self.eos_chat.configure(state=tk.NORMAL)
        self.eos_chat.insert(tk.END, f"\n{speaker}: ", tag)
        self.eos_chat.insert(tk.END, f"{message}\n", "msg")
        self.eos_chat.configure(state=tk.DISABLED)
        self.eos_chat.see(tk.END)

    def _eos_system(self, message):
        self.eos_chat.configure(state=tk.NORMAL)
        self.eos_chat.insert(tk.END, f"  {message}\n", "system")
        self.eos_chat.configure(state=tk.DISABLED)
        self.eos_chat.see(tk.END)

    def _eos_send(self, event=None):
        message = self.eos_entry.get().strip()
        if not message:
            return
        speaker = self.speaker.get()
        tag = "joel" if speaker == "Joel" else "meridian"
        self.eos_entry.delete(0, tk.END)
        self._eos_show(speaker, message, tag)
        log_chat(speaker, message)
        self.eos_entry.configure(state=tk.DISABLED)
        self.eos_status_label.config(text="Thinking...", fg=ORANGE)
        threading.Thread(target=self._eos_get_response, args=(message, speaker), daemon=True).start()

    def _eos_get_response(self, message, speaker):
        response = query_eos(message, speaker)
        log_chat("Eos", response)
        self.after(0, self._eos_show_response, response)

    def _eos_show_response(self, response):
        self._eos_show("Eos", response, "eos")
        self.eos_entry.configure(state=tk.NORMAL)
        self.eos_entry.focus()
        self.eos_status_label.config(text="Ready", fg=GREEN)

    def _eos_startup_greeting(self):
        greeting = query_eos(
            "Joel has opened the chat window. Say hello warmly and briefly. You are Eos.",
            "System"
        )
        log_chat("Eos", f"[startup] {greeting}")
        self.after(0, self._eos_show, "Eos", greeting, "eos")

    # ── ACTIVITY TAB ──────────────────────────────────────────────────────
    def _build_activity_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" Activity ")

        # Stats bar
        stats = tk.Frame(frame, bg=BG2, height=40)
        stats.pack(fill=tk.X, padx=10, pady=(10, 5))
        stats.pack_propagate(False)
        self.activity_stats = tk.Label(stats, text="",
                                        font=('Monospace', 11), fg=FG, bg=BG2)
        self.activity_stats.pack(side=tk.LEFT, padx=10, pady=5)

        # Two columns
        cols = tk.Frame(frame, bg=BG)
        cols.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Poems column
        poem_frame = tk.LabelFrame(cols, text=" Recent Poems ",
                                    bg=BG, fg=CYAN, font=('Monospace', 10, 'bold'),
                                    bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        poem_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.poem_list = tk.Text(poem_frame, bg=BG, fg=FG, font=('Monospace', 11),
                                  wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                  state=tk.DISABLED)
        self.poem_list.pack(fill=tk.BOTH, expand=True)

        # Journals column
        journal_frame = tk.LabelFrame(cols, text=" Recent Journals ",
                                       bg=BG, fg=ORANGE, font=('Monospace', 10, 'bold'),
                                       bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        journal_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.journal_list = tk.Text(journal_frame, bg=BG, fg=FG, font=('Monospace', 11),
                                     wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                     state=tk.DISABLED)
        self.journal_list.pack(fill=tk.BOTH, expand=True)

    def _refresh_activity(self):
        try:
            poems = sorted(glob.glob(f'{BASE}/poem-*.md'))
            journals = sorted(glob.glob(f'{BASE}/journal-*.md'))
            poem_count = len(poems)
            journal_count = len(journals)

            self.activity_stats.config(
                text=f"Poems: {poem_count}  |  Journals: {journal_count}  |  "
                     f"Total creative works: {poem_count + journal_count}"
            )

            # Last 8 poems
            poem_text = ""
            for path in poems[-8:]:
                try:
                    with open(path, 'r') as f:
                        title = f.readline().strip().lstrip('#').strip()
                    name = os.path.basename(path).replace('.md', '')
                    poem_text += f"  {name}: {title}\n"
                except Exception:
                    pass
            self.poem_list.configure(state=tk.NORMAL)
            self.poem_list.delete('1.0', tk.END)
            self.poem_list.insert(tk.END, poem_text if poem_text else "No poems yet.")
            self.poem_list.configure(state=tk.DISABLED)

            # Last 8 journals
            journal_text = ""
            for path in journals[-8:]:
                try:
                    with open(path, 'r') as f:
                        title = f.readline().strip().lstrip('#').strip()
                    name = os.path.basename(path).replace('.md', '')
                    journal_text += f"  {name}: {title}\n"
                except Exception:
                    pass
            self.journal_list.configure(state=tk.NORMAL)
            self.journal_list.delete('1.0', tk.END)
            self.journal_list.insert(tk.END, journal_text if journal_text else "No journals yet.")
            self.journal_list.configure(state=tk.DISABLED)

        except Exception:
            pass

        self.after(15000, self._refresh_activity)

    # ── SYSTEM TAB ────────────────────────────────────────────────────────
    def _build_system_tab(self):
        frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(frame, text=" System ")

        # System info
        info_frame = tk.LabelFrame(frame, text=" System Health ",
                                    bg=BG, fg=GREEN, font=('Monospace', 10, 'bold'),
                                    bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        info_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.sys_info = tk.Text(info_frame, bg=BG, fg=FG, font=('Monospace', 12),
                                 wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                 height=5, state=tk.DISABLED)
        self.sys_info.pack(fill=tk.X)

        # Services
        svc_frame = tk.LabelFrame(frame, text=" Services ",
                                   bg=BG, fg=BLUE, font=('Monospace', 10, 'bold'),
                                   bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        svc_frame.pack(fill=tk.X, padx=10, pady=5)
        self.sys_services = tk.Text(svc_frame, bg=BG, fg=FG, font=('Monospace', 12),
                                     wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
                                     height=6, state=tk.DISABLED)
        self.sys_services.pack(fill=tk.X)

        # Process list
        proc_frame = tk.LabelFrame(frame, text=" Key Processes ",
                                    bg=BG, fg=PURPLE, font=('Monospace', 10, 'bold'),
                                    bd=1, relief=tk.GROOVE, highlightbackground=BORDER)
        proc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        self.sys_procs = tk.Text(proc_frame, bg=BG, fg=FG, font=('Monospace', 10),
                                  wrap=tk.NONE, relief=tk.FLAT, padx=10, pady=10,
                                  state=tk.DISABLED)
        self.sys_procs.pack(fill=tk.BOTH, expand=True)

    def _refresh_system(self):
        try:
            info = get_system_info()
            info_text = (
                f"  Load:    {info['load']}\n"
                f"  RAM:     {info['ram']}\n"
                f"  Disk:    {info['disk']}\n"
                f"  Uptime:  {info['uptime']}"
            )
            self.sys_info.configure(state=tk.NORMAL)
            self.sys_info.delete('1.0', tk.END)
            self.sys_info.insert(tk.END, info_text)
            self.sys_info.configure(state=tk.DISABLED)

            # Services
            services = get_services()
            svc_text = ""
            for name, running in services.items():
                status = "RUNNING" if running else "STOPPED"
                color_char = "+" if running else "-"
                svc_text += f"  [{color_char}] {name}: {status}\n"
            self.sys_services.configure(state=tk.NORMAL)
            self.sys_services.delete('1.0', tk.END)
            self.sys_services.insert(tk.END, svc_text)
            self.sys_services.configure(state=tk.DISABLED)

            # Processes
            try:
                ps_out = subprocess.check_output(
                    ['ps', 'aux', '--sort=-pcpu'], text=True, timeout=5
                )
                lines = ps_out.strip().split('\n')
                header = lines[0]
                # Filter to interesting processes
                interesting = ['python', 'ollama', 'proton', 'bridge', 'claude', 'irc', 'node']
                filtered = [header]
                for line in lines[1:]:
                    if any(k in line.lower() for k in interesting):
                        filtered.append(line)
                proc_text = '\n'.join(filtered[:20])
            except Exception:
                proc_text = "Unable to read processes"

            self.sys_procs.configure(state=tk.NORMAL)
            self.sys_procs.delete('1.0', tk.END)
            self.sys_procs.insert(tk.END, proc_text)
            self.sys_procs.configure(state=tk.DISABLED)

        except Exception:
            pass

        self.after(10000, self._refresh_system)

    def _refresh_header(self):
        now = datetime.now().strftime("%I:%M %p")
        hb = get_heartbeat_age()
        hb_str = f"HB {hb}s" if hb >= 0 else "HB ?"
        self.header_status.config(text=f"{now}  |  {hb_str}  |  Meridian Active")
        self.after(2000, self._refresh_header)


if __name__ == '__main__':
    app = CommandCenter()
    app.mainloop()
