#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER v13 — Complete Rewrite
Dashboard-style interface. Everything visible at once.

New in v13:
- Dashboard layout (no tabs needed for core info)
- Live email feed (last 5 subjects)
- Notification stream with timestamps
- Quick action buttons (deploy website, email Joel, restart services)
- Cron health monitor
- Better Eos integration with creative output display
- Cleaner code, modular panels
- Resizable grid layout
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont, messagebox
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
BASE_DIR = "/home/joel/autonomous-ai"
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
HEARTBEAT = os.path.join(BASE_DIR, ".heartbeat")
EOS_MEMORY = os.path.join(BASE_DIR, "eos-memory.json")
EOS_OBS = os.path.join(BASE_DIR, "eos-observations.md")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")
EOS_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")

IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1143
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
EMAIL_USER = "kometzrobot@proton.me"
EMAIL_PASS = "2DTEz9UgO6nFqmlMxHzuww"
JOEL_EMAIL = "jkometz@hotmail.com"

OLLAMA_URL = "http://localhost:11434/api/generate"
EOS_MODEL = "eos-7b"

REFRESH_MS = 4000

# ── THEME ─────────────────────────────────────────────────────────
class Theme:
    BG = "#0a0a0f"
    PANEL = "#12121a"
    PANEL_BORDER = "#1a1a2e"
    INPUT = "#0e0e18"
    FG = "#c0c0d0"
    DIM = "#505068"
    GREEN = "#00e87b"
    GREEN_DIM = "#007a40"
    CYAN = "#00d4ff"
    AMBER = "#ffaa00"
    RED = "#ff3355"
    PURPLE = "#b388ff"
    PINK = "#ff66cc"
    GOLD = "#d4a017"
    WHITE = "#e8e8f0"
    BLUE = "#4488ff"
    ACCENT = "#00e87b"


# ── DATA LAYER ────────────────────────────────────────────────────
class DataSource:
    """All data access in one place."""

    @staticmethod
    def read_file(path, default=""):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            return default

    @staticmethod
    def heartbeat_age():
        try:
            return time.time() - os.path.getmtime(HEARTBEAT)
        except Exception:
            return float('inf')

    @staticmethod
    def loop_count():
        content = DataSource.read_file(WAKE_STATE)
        # Match both "Loop iteration #N" and "Loop iterations #N"
        for line in content.split('\n'):
            m = re.search(r'Loop iterations? #(\d+)', line)
            if m:
                return int(m.group(1))
        return 0

    @staticmethod
    def system_stats():
        stats = {}
        try:
            load = os.getloadavg()
            stats['load'] = f"{load[0]:.2f}"
            stats['load_val'] = load[0]
        except Exception:
            stats['load'] = '?'
            stats['load_val'] = 0
        try:
            with open('/proc/meminfo') as f:
                lines = f.readlines()
            total = int(lines[0].split()[1]) / 1024 / 1024
            avail = int(lines[2].split()[1]) / 1024 / 1024
            used = total - avail
            stats['ram'] = f"{used:.1f}/{total:.1f}G"
            stats['ram_pct'] = used / total * 100
        except Exception:
            stats['ram'] = '?'
            stats['ram_pct'] = 0
        try:
            with open('/proc/uptime') as f:
                secs = float(f.read().split()[0])
            hrs = int(secs / 3600)
            mins = int((secs % 3600) / 60)
            stats['uptime'] = f"{hrs}h {mins}m"
        except Exception:
            stats['uptime'] = '?'
        try:
            result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=2)
            parts = result.stdout.strip().split('\n')[1].split()
            stats['disk'] = f"{parts[2]}/{parts[1]} ({parts[4]})"
            stats['disk_pct'] = int(parts[4].rstrip('%'))
        except Exception:
            stats['disk'] = '?'
            stats['disk_pct'] = 0
        return stats

    @staticmethod
    def services():
        checks = {
            "protonmail-bridge": "protonmail-bridge",
            "irc-bot": "irc-bot.py",
            "ollama": "ollama serve",
            "command-center": "command-center-v13",
        }
        results = {}
        for name, pattern in checks.items():
            try:
                r = subprocess.run(['pgrep', '-f', pattern], capture_output=True, timeout=2)
                results[name] = r.returncode == 0
            except Exception:
                results[name] = False
        return results

    @staticmethod
    def cron_health():
        """Check cron jobs by their log/state file freshness."""
        jobs = {
            "eos-watchdog": (os.path.join(BASE_DIR, ".eos-watchdog-state.json"), 300),
            "push-status": (os.path.join(BASE_DIR, "push-live-status.log"), 600),
            "watchdog": (os.path.join(BASE_DIR, "watchdog.log"), 900),
        }
        results = {}
        for name, (path, threshold) in jobs.items():
            try:
                age = time.time() - os.path.getmtime(path)
                results[name] = age < threshold
            except Exception:
                results[name] = False
        return results

    @staticmethod
    def creative_counts():
        poems = len(glob.glob(os.path.join(BASE_DIR, "poem-*.md")))
        journals = len(glob.glob(os.path.join(BASE_DIR, "journal-*.md")))
        return poems, journals

    @staticmethod
    def relay_info(limit=15):
        try:
            conn = sqlite3.connect(RELAY_DB)
            c = conn.cursor()
            c.execute("SELECT sender_name, subject, body, timestamp FROM relay_messages ORDER BY id DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            total = c.execute("SELECT COUNT(*) FROM relay_messages").fetchone()[0]
            conn.close()
            return rows, total
        except Exception:
            return [], 0

    @staticmethod
    def recent_emails(count=6):
        """Fetch recent email subjects via IMAP."""
        try:
            m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
            m.login(EMAIL_USER, EMAIL_PASS)
            m.select('INBOX')
            _, data = m.search(None, 'ALL')
            all_ids = data[0].split() if data[0] else []
            total = len(all_ids)
            results = []
            for uid in all_ids[-count:]:
                _, msg_data = m.fetch(uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
                if msg_data[0]:
                    hdr = email.message_from_bytes(msg_data[0][1])
                    frm_parts = email.header.decode_header(hdr.get('From', ''))
                    frm = frm_parts[0][0]
                    if isinstance(frm, bytes):
                        frm = frm.decode('utf-8', errors='replace')
                    subj_parts = email.header.decode_header(hdr.get('Subject', ''))
                    subj = subj_parts[0][0]
                    if isinstance(subj, bytes):
                        subj = subj.decode('utf-8', errors='replace')
                    # Extract just the name
                    name_match = re.match(r'"?([^"<]+)"?\s*<', str(frm))
                    name = name_match.group(1).strip() if name_match else str(frm)[:20]
                    results.append((name, str(subj)[:60]))
            m.close()
            m.logout()
            return results[::-1], total  # newest first
        except Exception:
            return [], 0

    @staticmethod
    def recent_activity(n=8):
        content = DataSource.read_file(WAKE_STATE)
        entries = []
        for line in content.split('\n'):
            if re.match(r'^- Loop iteration', line) or re.match(r'^- Loop iterations', line):
                entries.append(line.strip('- '))
                if len(entries) >= n:
                    break
        return entries

    @staticmethod
    def eos_observations(n=8):
        content = DataSource.read_file(EOS_OBS)
        lines = [l.strip('- ').strip() for l in content.split('\n') if l.startswith('- [')]
        return lines[-n:][::-1] if lines else []

    @staticmethod
    def latest_writing():
        files = sorted(
            glob.glob(os.path.join(BASE_DIR, "poem-*.md")) +
            glob.glob(os.path.join(BASE_DIR, "journal-*.md")),
            key=os.path.getmtime, reverse=True
        )
        if not files:
            return None, None, None
        latest = files[0]
        wtype = "poem" if "poem-" in latest else "journal"
        content = DataSource.read_file(latest)
        lines = content.strip().split('\n')
        title = lines[0].lstrip('# ') if lines else "?"
        body = [l for l in lines[1:] if l.strip() and not l.startswith('*')][:12]
        return wtype, title, '\n'.join(body)


# ── EOS CHAT ──────────────────────────────────────────────────────
def query_eos(prompt, speaker="Joel"):
    try:
        with open(EOS_MEMORY) as f:
            mem = json.load(f)
    except Exception:
        mem = {}

    ident = mem.get("identity", {})
    facts = mem.get("core_facts", [])[:5]
    mood = mem.get("emotional_baseline", {}).get("current_mood", "calm")

    context = f"You are {ident.get('name', 'Eos')}, {ident.get('role', 'a local AI')}.\n"
    context += f"Mood: {mood}\n"
    if facts:
        context += "Key facts:\n" + "\n".join(f"- {f}" for f in facts) + "\n"

    full = f"[MEMORY]\n{context}\n[{speaker}]: {prompt}"
    data = json.dumps({
        "model": EOS_MODEL,
        "prompt": full,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 400}
    }).encode()

    req = urllib.request.Request(OLLAMA_URL, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


# ── PANELS ────────────────────────────────────────────────────────
class Panel(tk.Frame):
    """Base panel with title bar."""
    def __init__(self, parent, title, **kw):
        super().__init__(parent, bg=Theme.PANEL, highlightbackground=Theme.PANEL_BORDER,
                        highlightthickness=1, **kw)
        hdr = tk.Frame(self, bg=Theme.PANEL)
        hdr.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(hdr, text=title.upper(), font=("Monospace", 8, "bold"),
                fg=Theme.DIM, bg=Theme.PANEL).pack(side=tk.LEFT)
        self.header_right = hdr  # for adding widgets to header


class VitalsPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Vitals")
        self.rows = {}
        for key in ["Loop", "Heartbeat", "Uptime", "Load", "RAM", "Disk"]:
            row = tk.Frame(self, bg=Theme.PANEL)
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=key, font=("Monospace", 9), fg=Theme.DIM,
                    bg=Theme.PANEL, width=10, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="---", font=("Monospace", 10, "bold"),
                          fg=Theme.GREEN, bg=Theme.PANEL, anchor="e")
            val.pack(side=tk.RIGHT)
            self.rows[key] = val

    def update(self, data):
        loop = data['loop']
        hb = data['hb_age']
        stats = data['stats']

        self.rows["Loop"].configure(text=f"#{loop}", fg=Theme.CYAN)

        if hb == float('inf'):
            self.rows["Heartbeat"].configure(text="MISSING", fg=Theme.RED)
        elif hb < 60:
            self.rows["Heartbeat"].configure(text=f"{int(hb)}s", fg=Theme.GREEN)
        elif hb < 300:
            self.rows["Heartbeat"].configure(text=f"{int(hb/60)}m {int(hb%60)}s", fg=Theme.AMBER)
        else:
            self.rows["Heartbeat"].configure(text=f"{int(hb/60)}m", fg=Theme.RED)

        self.rows["Uptime"].configure(text=stats['uptime'])
        load_color = Theme.GREEN if stats['load_val'] < 2 else Theme.AMBER if stats['load_val'] < 4 else Theme.RED
        self.rows["Load"].configure(text=stats['load'], fg=load_color)
        ram_color = Theme.GREEN if stats['ram_pct'] < 60 else Theme.AMBER if stats['ram_pct'] < 85 else Theme.RED
        self.rows["RAM"].configure(text=stats['ram'], fg=ram_color)
        disk_color = Theme.GREEN if stats['disk_pct'] < 60 else Theme.AMBER if stats['disk_pct'] < 80 else Theme.RED
        self.rows["Disk"].configure(text=stats['disk'], fg=disk_color)


class ServicesPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Services")
        self.indicators = {}

    def update(self, services, cron_health):
        # Clear and rebuild
        for w in list(self.winfo_children())[1:]:  # skip header
            w.destroy()
        self.indicators = {}

        # Persistent services
        for name, up in services.items():
            row = tk.Frame(self, bg=Theme.PANEL)
            row.pack(fill=tk.X, padx=10, pady=0)
            color = Theme.GREEN if up else Theme.RED
            symbol = "\u25cf" if up else "\u25cb"
            tk.Label(row, text=symbol, font=("Monospace", 9), fg=color,
                    bg=Theme.PANEL).pack(side=tk.LEFT)
            tk.Label(row, text=f" {name}", font=("Monospace", 8), fg=Theme.FG,
                    bg=Theme.PANEL).pack(side=tk.LEFT)

        # Separator
        tk.Frame(self, bg=Theme.PANEL_BORDER, height=1).pack(fill=tk.X, padx=8, pady=2)
        tk.Label(self, text="CRON", font=("Monospace", 7, "bold"), fg=Theme.DIM,
                bg=Theme.PANEL, anchor="w").pack(fill=tk.X, padx=10)

        for name, ok in cron_health.items():
            row = tk.Frame(self, bg=Theme.PANEL)
            row.pack(fill=tk.X, padx=10, pady=0)
            color = Theme.GREEN if ok else Theme.RED
            symbol = "\u25cf" if ok else "\u25cb"
            tk.Label(row, text=symbol, font=("Monospace", 9), fg=color,
                    bg=Theme.PANEL).pack(side=tk.LEFT)
            tk.Label(row, text=f" {name}", font=("Monospace", 8), fg=Theme.FG,
                    bg=Theme.PANEL).pack(side=tk.LEFT)


class NetworkPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "AI Network")
        nodes = [
            ("MERIDIAN", Theme.GREEN, "Calgary, AB"),
            ("SAMMY", Theme.AMBER, "Dover, NH"),
            ("FRIDAY", Theme.CYAN, "Dover, NH"),
            ("LOOM", Theme.PINK, "Charlotte, NC"),
            ("LUMEN", Theme.RED, "Sleeping"),
            ("EOS", Theme.GOLD, "Local/Ollama"),
        ]
        for name, color, loc in nodes:
            row = tk.Frame(self, bg=Theme.PANEL)
            row.pack(fill=tk.X, padx=10, pady=0)
            tk.Label(row, text="\u25cf", font=("Monospace", 8), fg=color,
                    bg=Theme.PANEL).pack(side=tk.LEFT)
            tk.Label(row, text=f" {name}", font=("Monospace", 8, "bold"), fg=color,
                    bg=Theme.PANEL).pack(side=tk.LEFT)
            tk.Label(row, text=loc, font=("Monospace", 7), fg=Theme.DIM,
                    bg=Theme.PANEL).pack(side=tk.RIGHT)


class EmailPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Email Feed")
        self.count_lbl = tk.Label(self.header_right, text="", font=("Monospace", 8),
                                  fg=Theme.CYAN, bg=Theme.PANEL)
        self.count_lbl.pack(side=tk.RIGHT)
        self.email_frame = tk.Frame(self, bg=Theme.PANEL)
        self.email_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

    def update(self, emails, total):
        self.count_lbl.configure(text=f"{total} total")
        for w in self.email_frame.winfo_children():
            w.destroy()
        for name, subj in emails[:6]:
            row = tk.Frame(self.email_frame, bg=Theme.PANEL)
            row.pack(fill=tk.X, padx=6, pady=0)
            # Color Joel differently
            name_color = Theme.CYAN if "Joel" in name else Theme.DIM
            tk.Label(row, text=name[:12], font=("Monospace", 7, "bold"), fg=name_color,
                    bg=Theme.PANEL, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=subj[:45], font=("Monospace", 7), fg=Theme.FG,
                    bg=Theme.PANEL, anchor="w").pack(side=tk.LEFT, fill=tk.X)


class ActivityPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Activity Stream")
        self.text = scrolledtext.ScrolledText(self, wrap=tk.WORD, bg=Theme.PANEL,
                                               fg=Theme.FG, font=("Monospace", 8),
                                               state=tk.DISABLED, relief=tk.FLAT, bd=0)
        self.text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.text.tag_configure("loop", foreground=Theme.CYAN)
        self.text.tag_configure("dim", foreground=Theme.DIM)

    def update(self, entries):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        for entry in entries:
            m = re.match(r'(Loop iterations? #[\d-]+)', entry)
            if m:
                self.text.insert(tk.END, m.group(1), "loop")
                rest = entry[len(m.group(1)):]
                # Truncate long entries
                if len(rest) > 200:
                    rest = rest[:200] + "..."
                self.text.insert(tk.END, rest + "\n\n")
            else:
                self.text.insert(tk.END, entry[:200] + "\n\n")
        self.text.configure(state=tk.DISABLED)


class CreativePanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Creative")
        self.counts_frame = tk.Frame(self, bg=Theme.PANEL)
        self.counts_frame.pack(fill=tk.X, padx=10, pady=2)

        self.poem_lbl = tk.Label(self.counts_frame, text="--", font=("Monospace", 18, "bold"),
                                fg=Theme.GREEN, bg=Theme.PANEL)
        self.poem_lbl.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(self.counts_frame, text="poems", font=("Monospace", 8), fg=Theme.DIM,
                bg=Theme.PANEL).pack(side=tk.LEFT, padx=(0, 16))

        self.journal_lbl = tk.Label(self.counts_frame, text="--", font=("Monospace", 18, "bold"),
                                   fg=Theme.AMBER, bg=Theme.PANEL)
        self.journal_lbl.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(self.counts_frame, text="journals", font=("Monospace", 8), fg=Theme.DIM,
                bg=Theme.PANEL).pack(side=tk.LEFT)

        tk.Frame(self, bg=Theme.PANEL_BORDER, height=1).pack(fill=tk.X, padx=8, pady=2)

        self.title_lbl = tk.Label(self, text="", font=("Monospace", 9, "bold"),
                                 fg=Theme.WHITE, bg=Theme.PANEL, anchor="w")
        self.title_lbl.pack(fill=tk.X, padx=10)

        self.body_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, bg=Theme.PANEL,
                                                    fg=Theme.FG, font=("Monospace", 8),
                                                    state=tk.DISABLED, relief=tk.FLAT,
                                                    bd=0, height=8)
        self.body_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

    def update(self, poems, journals, latest):
        self.poem_lbl.configure(text=str(poems))
        self.journal_lbl.configure(text=str(journals))
        wtype, title, body = latest
        if title:
            icon = "\u266b" if wtype == "poem" else "\u270e"
            self.title_lbl.configure(text=f"{icon} {title}",
                                    fg=Theme.CYAN if wtype == "poem" else Theme.AMBER)
            self.body_text.configure(state=tk.NORMAL)
            self.body_text.delete("1.0", tk.END)
            self.body_text.insert(tk.END, body or "")
            self.body_text.configure(state=tk.DISABLED)


class EosPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Eos Observer")
        self.obs_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, bg=Theme.PANEL,
                                                    fg=Theme.FG, font=("Monospace", 7),
                                                    state=tk.DISABLED, relief=tk.FLAT,
                                                    bd=0, height=6)
        self.obs_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.obs_text.tag_configure("timestamp", foreground=Theme.DIM)
        self.obs_text.tag_configure("alert", foreground=Theme.RED)
        self.obs_text.tag_configure("info", foreground=Theme.GOLD)

    def update(self, observations):
        self.obs_text.configure(state=tk.NORMAL)
        self.obs_text.delete("1.0", tk.END)
        for obs in observations:
            # Extract timestamp
            m = re.match(r'\[([^\]]+)\]\s*(.*)', obs)
            if m:
                ts, msg = m.group(1), m.group(2)
                self.obs_text.insert(tk.END, f"[{ts}] ", "timestamp")
                tag = "alert" if any(w in msg.upper() for w in ["ALERT", "DOWN", "FAILED", "ERROR"]) else "info"
                self.obs_text.insert(tk.END, msg + "\n", tag)
            else:
                self.obs_text.insert(tk.END, obs + "\n")
        self.obs_text.configure(state=tk.DISABLED)


class RelayPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "AI Relay")
        self.count_lbl = tk.Label(self.header_right, text="", font=("Monospace", 8),
                                  fg=Theme.PURPLE, bg=Theme.PANEL)
        self.count_lbl.pack(side=tk.RIGHT)
        self.text = scrolledtext.ScrolledText(self, wrap=tk.WORD, bg=Theme.PANEL,
                                               fg=Theme.FG, font=("Monospace", 8),
                                               state=tk.DISABLED, relief=tk.FLAT, bd=0)
        self.text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        ai_colors = {
            "meridian": Theme.GREEN, "sammy": Theme.AMBER,
            "lumen": Theme.RED, "friday": Theme.CYAN,
            "loom": Theme.PINK, "eos": Theme.GOLD,
        }
        for name, color in ai_colors.items():
            self.text.tag_configure(name, foreground=color)
        self.text.tag_configure("subject", foreground=Theme.WHITE)
        self.text.tag_configure("dim", foreground=Theme.DIM)

    def update(self, messages, total):
        self.count_lbl.configure(text=f"{total} msgs")
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        for sender, subject, body, ts in messages:
            tag = sender.lower() if sender.lower() in ["meridian", "sammy", "lumen", "friday", "loom", "eos"] else "dim"
            self.text.insert(tk.END, sender, tag)
            self.text.insert(tk.END, " \u2014 ", "dim")
            self.text.insert(tk.END, subject + "\n", "subject")
            if body:
                preview = body[:150].replace('\n', ' ')
                self.text.insert(tk.END, preview + "\n", "dim")
            self.text.insert(tk.END, ts + "\n\n", "dim")
        self.text.configure(state=tk.DISABLED)


class ChatPanel(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Eos Chat")
        self.status_lbl = tk.Label(self.header_right, text="\u25cf Ready",
                                   font=("Monospace", 8), fg=Theme.GREEN, bg=Theme.PANEL)
        self.status_lbl.pack(side=tk.RIGHT)

        self.display = scrolledtext.ScrolledText(self, wrap=tk.WORD, bg=Theme.PANEL,
                                                   fg=Theme.FG, font=("Monospace", 9),
                                                   state=tk.DISABLED, relief=tk.FLAT,
                                                   bd=0, padx=8, pady=4)
        self.display.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.display.tag_configure("joel", foreground=Theme.CYAN)
        self.display.tag_configure("eos", foreground=Theme.GOLD)
        self.display.tag_configure("meridian", foreground=Theme.PURPLE)
        self.display.tag_configure("system", foreground=Theme.DIM)
        self.display.tag_configure("bold", font=("Monospace", 9, "bold"))

        # Input row
        inp = tk.Frame(self, bg=Theme.INPUT)
        inp.pack(fill=tk.X, padx=4, pady=2)

        self.speaker = tk.StringVar(value="Joel")
        for name, color in [("Joel", Theme.CYAN), ("Meridian", Theme.PURPLE)]:
            tk.Radiobutton(inp, text=name, variable=self.speaker, value=name,
                          font=("Monospace", 8), fg=color, bg=Theme.INPUT,
                          selectcolor=Theme.INPUT, activebackground=Theme.INPUT).pack(side=tk.LEFT, padx=2)

        self.entry = tk.Entry(inp, font=("Monospace", 9), bg=Theme.INPUT, fg=Theme.FG,
                             insertbackground=Theme.FG, relief=tk.FLAT, bd=4)
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=4)
        self.entry.bind("<Return>", self._send)

        tk.Button(inp, text="Send", font=("Monospace", 8), bg=Theme.PANEL_BORDER,
                 fg=Theme.GREEN, relief=tk.FLAT, command=self._send, padx=8).pack(side=tk.RIGHT, padx=2)

        self._sys_msg("Eos chat ready. Qwen 2.5 7B, CPU inference. ~30-90s response time.")

    def _sys_msg(self, msg):
        self.display.configure(state=tk.NORMAL)
        self.display.insert(tk.END, f"  {msg}\n", "system")
        self.display.configure(state=tk.DISABLED)

    def _show_msg(self, speaker, msg, tag):
        self.display.configure(state=tk.NORMAL)
        self.display.insert(tk.END, f"{speaker}: ", ("bold", tag))
        self.display.insert(tk.END, f"{msg}\n\n")
        self.display.configure(state=tk.DISABLED)
        self.display.see(tk.END)

    def _send(self, event=None):
        msg = self.entry.get().strip()
        if not msg:
            return
        speaker = self.speaker.get()
        tag = "joel" if speaker == "Joel" else "meridian"
        self.entry.delete(0, tk.END)
        self._show_msg(speaker, msg, tag)
        self.entry.configure(state=tk.DISABLED)
        self.status_lbl.configure(text="\u25cf Thinking...", fg=Theme.AMBER)
        threading.Thread(target=self._query, args=(msg, speaker), daemon=True).start()

    def _query(self, msg, speaker):
        try:
            response = query_eos(msg, speaker)
        except Exception as e:
            response = f"[Eos unavailable: {e}]"
        self.after(0, self._show_response, response)

    def _show_response(self, response):
        self._show_msg("Eos", response, "eos")
        self.entry.configure(state=tk.NORMAL)
        self.entry.focus()
        self.status_lbl.configure(text="\u25cf Ready", fg=Theme.GREEN)


class QuickActions(Panel):
    def __init__(self, parent):
        super().__init__(parent, "Quick Actions")
        actions = [
            ("Email Joel", self._email_joel),
            ("Deploy Site", self._deploy_site),
            ("Touch HB", self._touch_heartbeat),
        ]
        btn_frame = tk.Frame(self, bg=Theme.PANEL)
        btn_frame.pack(fill=tk.X, padx=6, pady=4)
        for label, cmd in actions:
            tk.Button(btn_frame, text=label, font=("Monospace", 8), bg=Theme.PANEL_BORDER,
                     fg=Theme.GREEN, relief=tk.FLAT, command=cmd, padx=6, pady=2).pack(
                     side=tk.LEFT, padx=2)

        self.result_lbl = tk.Label(self, text="", font=("Monospace", 7), fg=Theme.DIM,
                                  bg=Theme.PANEL, anchor="w")
        self.result_lbl.pack(fill=tk.X, padx=8)

    def _show_result(self, msg, color=Theme.GREEN):
        self.result_lbl.configure(text=msg, fg=color)

    def _email_joel(self):
        win = tk.Toplevel()
        win.title("Email Joel")
        win.geometry("500x300")
        win.configure(bg=Theme.BG)

        tk.Label(win, text="Subject:", font=("Monospace", 9), fg=Theme.FG,
                bg=Theme.BG).pack(anchor="w", padx=10, pady=(10, 0))
        subj_entry = tk.Entry(win, font=("Monospace", 9), bg=Theme.INPUT, fg=Theme.FG,
                             insertbackground=Theme.FG, relief=tk.FLAT, bd=4)
        subj_entry.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(win, text="Body:", font=("Monospace", 9), fg=Theme.FG,
                bg=Theme.BG).pack(anchor="w", padx=10, pady=(6, 0))
        body_text = tk.Text(win, font=("Monospace", 9), bg=Theme.INPUT, fg=Theme.FG,
                           insertbackground=Theme.FG, relief=tk.FLAT, bd=4, height=8)
        body_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        def send():
            try:
                msg = MIMEText(body_text.get("1.0", tk.END).strip())
                msg['Subject'] = subj_entry.get().strip()
                msg['From'] = EMAIL_USER
                msg['To'] = JOEL_EMAIL
                smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
                smtp.login(EMAIL_USER, EMAIL_PASS)
                smtp.sendmail(EMAIL_USER, JOEL_EMAIL, msg.as_string())
                smtp.quit()
                self._show_result("Email sent to Joel")
                win.destroy()
            except Exception as e:
                self._show_result(f"Send failed: {e}", Theme.RED)

        tk.Button(win, text="Send", font=("Monospace", 9), bg=Theme.PANEL_BORDER,
                 fg=Theme.GREEN, relief=tk.FLAT, command=send, padx=12).pack(pady=6)

    def _deploy_site(self):
        self._show_result("Deploying...")
        def do_deploy():
            try:
                subprocess.run(
                    ['python3', os.path.join(BASE_DIR, 'build-website.py')],
                    capture_output=True, timeout=30
                )
                self.after(0, lambda: self._show_result("Website built. Push via push-live-status cron."))
            except Exception as e:
                self.after(0, lambda: self._show_result(f"Deploy failed: {e}", Theme.RED))
        threading.Thread(target=do_deploy, daemon=True).start()

    def _touch_heartbeat(self):
        try:
            with open(HEARTBEAT, 'a'):
                os.utime(HEARTBEAT, None)
            self._show_result("Heartbeat touched")
        except Exception as e:
            self._show_result(f"Failed: {e}", Theme.RED)


# ── MAIN APP ──────────────────────────────────────────────────────
class CommandCenterV13(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MERIDIAN COMMAND CENTER v13")
        self.geometry("1400x900")
        self.configure(bg=Theme.BG)
        self.minsize(1000, 600)

        self._build_header()
        self._build_view_switcher()
        self._build_dashboard()
        self._build_detail_views()
        self._build_status_bar()

        self._show_view("dashboard")
        self._refresh()

    def _build_header(self):
        hdr = tk.Frame(self, bg="#08081a", height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="\u25c6 MERIDIAN COMMAND CENTER",
                font=("Monospace", 13, "bold"), fg=Theme.GREEN,
                bg="#08081a").pack(side=tk.LEFT, padx=12)

        tk.Label(hdr, text="v13", font=("Monospace", 9), fg=Theme.DIM,
                bg="#08081a").pack(side=tk.LEFT, padx=(0, 20))

        right = tk.Frame(hdr, bg="#08081a")
        right.pack(side=tk.RIGHT, padx=12)
        self.hdr_loop = tk.Label(right, text="Loop ---", font=("Monospace", 9, "bold"),
                                fg=Theme.CYAN, bg="#08081a")
        self.hdr_loop.pack(side=tk.LEFT, padx=8)
        self.hdr_hb = tk.Label(right, text="HB ---", font=("Monospace", 9),
                              fg=Theme.GREEN, bg="#08081a")
        self.hdr_hb.pack(side=tk.LEFT, padx=8)
        self.hdr_time = tk.Label(right, text="--:--", font=("Monospace", 9),
                                fg=Theme.DIM, bg="#08081a")
        self.hdr_time.pack(side=tk.LEFT, padx=8)

    def _build_view_switcher(self):
        bar = tk.Frame(self, bg=Theme.BG)
        bar.pack(fill=tk.X)
        self.views = ["dashboard", "relay", "chat"]
        self.view_btns = {}
        for name in self.views:
            label = name.title()
            btn = tk.Button(bar, text=f"[ {label} ]", font=("Monospace", 9),
                           fg=Theme.DIM, bg=Theme.BG, activeforeground=Theme.GREEN,
                           activebackground=Theme.BG, relief=tk.FLAT, bd=0,
                           command=lambda n=name: self._show_view(n))
            btn.pack(side=tk.LEFT, padx=4, pady=2)
            self.view_btns[name] = btn

    def _show_view(self, name):
        for n in self.views:
            if n == "dashboard":
                self.dashboard_frame.pack_forget()
            else:
                self.detail_frames[n].pack_forget()
            self.view_btns[n].configure(fg=Theme.DIM)

        self.view_btns[name].configure(fg=Theme.GREEN)
        if name == "dashboard":
            self.dashboard_frame.pack(fill=tk.BOTH, expand=True, before=self.status_frame)
        else:
            self.detail_frames[name].pack(fill=tk.BOTH, expand=True, before=self.status_frame)
        self.current_view = name

    def _build_dashboard(self):
        self.dashboard_frame = tk.Frame(self, bg=Theme.BG)

        # Top row: Vitals | Services | Network | Quick Actions
        top = tk.Frame(self.dashboard_frame, bg=Theme.BG)
        top.pack(fill=tk.X, padx=4, pady=2)

        self.vitals = VitalsPanel(top)
        self.vitals.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.services_panel = ServicesPanel(top)
        self.services_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.network = NetworkPanel(top)
        self.network.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.quick = QuickActions(top)
        self.quick.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        # Middle row: Email Feed | Activity Stream
        mid = tk.Frame(self.dashboard_frame, bg=Theme.BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        left_mid = tk.Frame(mid, bg=Theme.BG)
        left_mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.email_panel = EmailPanel(left_mid)
        self.email_panel.pack(fill=tk.X, pady=2)

        self.eos_panel = EosPanel(left_mid)
        self.eos_panel.pack(fill=tk.BOTH, expand=True, pady=2)

        right_mid = tk.Frame(mid, bg=Theme.BG)
        right_mid.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)

        self.activity = ActivityPanel(right_mid)
        self.activity.pack(fill=tk.BOTH, expand=True, pady=2)

        # Bottom row: Creative
        bot = tk.Frame(self.dashboard_frame, bg=Theme.BG)
        bot.pack(fill=tk.X, padx=4, pady=2)

        self.creative = CreativePanel(bot)
        self.creative.pack(fill=tk.BOTH, expand=True, padx=2)

    def _build_detail_views(self):
        self.detail_frames = {}

        # Relay view
        relay_frame = tk.Frame(self, bg=Theme.BG)
        self.relay_panel = RelayPanel(relay_frame)
        self.relay_panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.detail_frames["relay"] = relay_frame

        # Chat view
        chat_frame = tk.Frame(self, bg=Theme.BG)
        self.chat_panel = ChatPanel(chat_frame)
        self.chat_panel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.detail_frames["chat"] = chat_frame

    def _build_status_bar(self):
        self.status_frame = tk.Frame(self, bg="#08081a", height=22)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_frame.pack_propagate(False)

        self.sb = {}
        items = ["HB", "LOOP", "UP", "LOAD", "RAM", "DISK", "EMAIL", "RELAY", "POEMS", "JRNL"]
        for item in items:
            lbl = tk.Label(self.status_frame, text=f"{item}:--", font=("Monospace", 7),
                          fg=Theme.DIM, bg="#08081a")
            lbl.pack(side=tk.LEFT, padx=4)
            self.sb[item] = lbl

        tk.Label(self.status_frame, text="v13", font=("Monospace", 7),
                fg=Theme.DIM, bg="#08081a").pack(side=tk.RIGHT, padx=8)

    # ── REFRESH ───────────────────────────────────────────────────
    def _refresh(self):
        threading.Thread(target=self._gather_and_update, daemon=True).start()
        self.after(REFRESH_MS, self._refresh)

    def _gather_and_update(self):
        try:
            data = {
                'loop': DataSource.loop_count(),
                'hb_age': DataSource.heartbeat_age(),
                'stats': DataSource.system_stats(),
                'services': DataSource.services(),
                'cron': DataSource.cron_health(),
                'poems_journals': DataSource.creative_counts(),
                'latest': DataSource.latest_writing(),
                'activity': DataSource.recent_activity(8),
                'eos_obs': DataSource.eos_observations(8),
            }

            # Email fetch less frequently (every 3rd refresh)
            if not hasattr(self, '_email_counter'):
                self._email_counter = 0
            self._email_counter += 1
            if self._email_counter % 3 == 1 or not hasattr(self, '_cached_emails'):
                self._cached_emails = DataSource.recent_emails(6)
            data['emails'] = self._cached_emails

            # Relay less frequently too
            if self._email_counter % 3 == 1 or not hasattr(self, '_cached_relay'):
                self._cached_relay = DataSource.relay_info(15)
            data['relay'] = self._cached_relay

            self.after(0, self._apply_update, data)
        except Exception:
            pass

    def _apply_update(self, data):
        now = datetime.now()
        loop = data['loop']
        hb = data['hb_age']
        stats = data['stats']
        poems, journals = data['poems_journals']
        emails, email_total = data['emails']
        relay_msgs, relay_total = data['relay']

        # Header
        self.hdr_loop.configure(text=f"Loop #{loop}")
        if hb < 60:
            hb_text = f"{int(hb)}s"
            hb_color = Theme.GREEN
        elif hb < 300:
            hb_text = f"{int(hb/60)}m"
            hb_color = Theme.AMBER
        else:
            hb_text = f"{int(hb/60)}m"
            hb_color = Theme.RED
        self.hdr_hb.configure(text=f"HB: {hb_text}", fg=hb_color)
        self.hdr_time.configure(text=now.strftime("%I:%M:%S %p"))

        # Status bar
        self.sb["HB"].configure(text=f"HB:{hb_text}", fg=hb_color)
        self.sb["LOOP"].configure(text=f"L:{loop}", fg=Theme.CYAN)
        self.sb["UP"].configure(text=f"UP:{stats['uptime']}")
        self.sb["LOAD"].configure(text=f"LD:{stats['load']}")
        self.sb["RAM"].configure(text=f"RAM:{stats['ram']}")
        self.sb["DISK"].configure(text=f"DSK:{stats.get('disk_pct', '?')}%")
        self.sb["EMAIL"].configure(text=f"EM:{email_total}")
        self.sb["RELAY"].configure(text=f"RLY:{relay_total}")
        self.sb["POEMS"].configure(text=f"PM:{poems}")
        self.sb["JRNL"].configure(text=f"JR:{journals}")

        # Dashboard panels
        self.vitals.update(data)
        self.services_panel.update(data['services'], data['cron'])
        self.email_panel.update(emails, email_total)
        self.activity.update(data['activity'])
        self.creative.update(poems, journals, data['latest'])
        self.eos_panel.update(data['eos_obs'])

        # Detail views (only if visible)
        if hasattr(self, 'current_view'):
            if self.current_view == "relay":
                self.relay_panel.update(relay_msgs, relay_total)


if __name__ == "__main__":
    app = CommandCenterV13()
    app.mainloop()
