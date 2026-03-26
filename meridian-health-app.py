#!/usr/bin/env python3
"""
MERIDIAN SYSTEM HEALTH
Standalone desktop app — live system status, services, relay activity.

Usage: python3 meridian-health-app.py
"""

__version__ = "1.0.0"

import tkinter as tk
from tkinter import ttk
import os
import sqlite3
import subprocess
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
RELAY_DB = os.path.join(BASE, "agent-relay.db")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
FITNESS_LOG = os.path.join(BASE, "logs", "loop-fitness.log")

# ── PALETTE ──────────────────────────────────────────────────────────
BG        = "#0a0a12"
PANEL     = "#12121c"
HEADER_BG = "#06060e"
BORDER    = "#1e1e2e"
TEXT      = "#e2e8f0"
DIM       = "#64748b"
ACCENT    = "#64B5F6"
GREEN     = "#34d399"
YELLOW    = "#fbbf24"
RED       = "#f87171"
ORANGE    = "#fb923c"

SERVICES = [
    ("meridian-hub-v2",  "Hub v2 (port 8090)"),
    ("command-center",   "Command Center"),
    ("soma",             "Soma (nervous system)"),
    ("the-chorus",       "The Chorus (port 8091)"),
]


def load_env():
    env = {}
    for p in [".env"]:
        fp = os.path.join(BASE, p)
        if os.path.exists(fp):
            with open(fp) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_service_status(service_name):
    try:
        r = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=3
        )
        status = r.stdout.strip()
        if status == "active":
            return "UP", GREEN
        elif status == "inactive":
            return "DOWN", RED
        else:
            return status.upper(), YELLOW
    except Exception:
        return "?", DIM


def get_system_stats():
    stats = {}
    # Load average
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        stats["load1"] = float(parts[0])
        stats["load5"] = float(parts[1])
    except Exception:
        stats["load1"] = stats["load5"] = 0.0

    # RAM
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 1)
        free = mem.get("MemAvailable", 0)
        used_pct = round((1 - free / total) * 100, 1)
        stats["ram_pct"] = used_pct
        stats["ram_free_gb"] = round(free / 1024 / 1024, 1)
        stats["ram_total_gb"] = round(total / 1024 / 1024, 1)
    except Exception:
        stats["ram_pct"] = stats["ram_free_gb"] = stats["ram_total_gb"] = 0

    # Disk
    try:
        r = subprocess.run(
            ["df", "-h", "/home"],
            capture_output=True, text=True, timeout=3
        )
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            stats["disk_used"] = parts[2]
            stats["disk_total"] = parts[1]
            stats["disk_pct"] = int(parts[4].rstrip("%"))
        else:
            stats["disk_used"] = stats["disk_total"] = "?"
            stats["disk_pct"] = 0
    except Exception:
        stats["disk_used"] = stats["disk_total"] = "?"
        stats["disk_pct"] = 0

    return stats


def get_heartbeat_age():
    try:
        mtime = os.path.getmtime(HEARTBEAT)
        age = int(time.time() - mtime)
        return age
    except Exception:
        return -1


def get_loop_count():
    lc_file = os.path.join(BASE, ".loop-count")
    try:
        return int(Path(lc_file).read_text().strip())
    except Exception:
        return 0


def get_fitness():
    try:
        conn = sqlite3.connect(RELAY_DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT message FROM agent_messages WHERE agent='Tempo' "
            "ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            msg = row[0]
            # Parse "Loop 3235 fitness: 8177/10000 [STABLE]"
            if "fitness:" in msg:
                parts = msg.split("fitness:")
                score_part = parts[1].strip().split()[0]
                return score_part
    except Exception:
        pass
    return "?"


def get_relay_recent(count=6):
    msgs = []
    try:
        conn = sqlite3.connect(RELAY_DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT agent, message, timestamp FROM agent_messages "
            "WHERE agent NOT IN ('HomecomingLocal') "
            "ORDER BY timestamp DESC LIMIT ?", (count,)
        )
        for row in cur.fetchall():
            ts_str = str(row[2])[:16]
            msgs.append((row[0], row[1][:80], ts_str))
        conn.close()
    except Exception:
        pass
    return msgs


class HealthApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Meridian — System Health")
        self.root.configure(bg=BG)
        self.root.geometry("820x620")
        self.root.minsize(680, 520)

        self._build_ui()
        self._refresh()
        self._schedule_refresh()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=HEADER_BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="MERIDIAN  SYSTEM HEALTH", bg=HEADER_BG,
                 fg=TEXT, font=("Courier", 13, "bold")).pack(side="left", padx=16)
        self.ts_label = tk.Label(hdr, text="", bg=HEADER_BG, fg=DIM,
                                 font=("Courier", 10))
        self.ts_label.pack(side="right", padx=16)

        # Main body
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # Left column: services + stats
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._section(left, "SERVICES")
        self.svc_frames = {}
        for svc_id, svc_label in SERVICES:
            row = tk.Frame(left, bg=PANEL, pady=4, padx=10, relief="flat")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=svc_label, bg=PANEL, fg=TEXT,
                     font=("Courier", 10), width=24, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="...", bg=PANEL, fg=DIM,
                           font=("Courier", 10, "bold"), width=8)
            lbl.pack(side="right")
            self.svc_frames[svc_id] = lbl

        self._section(left, "SYSTEM")
        stats_panel = tk.Frame(left, bg=PANEL, pady=6, padx=10)
        stats_panel.pack(fill="x", pady=2)

        self.load_lbl   = self._stat_row(stats_panel, "Load (1/5m)")
        self.ram_lbl    = self._stat_row(stats_panel, "RAM used")
        self.disk_lbl   = self._stat_row(stats_panel, "Disk /home")
        self.hb_lbl     = self._stat_row(stats_panel, "Heartbeat")
        self.loop_lbl   = self._stat_row(stats_panel, "Loop count")
        self.fit_lbl    = self._stat_row(stats_panel, "Fitness")

        # Right column: relay
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self._section(right, "RELAY  (recent)")
        self.relay_panel = tk.Frame(right, bg=PANEL, pady=4, padx=10)
        self.relay_panel.pack(fill="both", expand=True, pady=2)

        self.relay_text = tk.Text(
            self.relay_panel, bg=PANEL, fg=TEXT,
            font=("Courier", 9), wrap="word",
            relief="flat", bd=0, state="disabled",
            insertbackground=ACCENT
        )
        self.relay_text.pack(fill="both", expand=True)
        self.relay_text.tag_config("agent", foreground=ACCENT)
        self.relay_text.tag_config("ts", foreground=DIM)
        self.relay_text.tag_config("msg", foreground=TEXT)

        # Footer
        footer = tk.Frame(self.root, bg=HEADER_BG, pady=5)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, text="Auto-refresh 30s  •  v" + __version__,
                 bg=HEADER_BG, fg=DIM, font=("Courier", 9)).pack(side="left", padx=12)
        tk.Button(footer, text="Refresh Now", bg=PANEL, fg=ACCENT,
                  font=("Courier", 9), relief="flat", cursor="hand2",
                  command=self._refresh).pack(side="right", padx=12)

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=BG, fg=DIM,
                 font=("Courier", 9, "bold")).pack(anchor="w", pady=(8, 2))

    def _stat_row(self, parent, label):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=label, bg=PANEL, fg=DIM,
                 font=("Courier", 9), width=14, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="...", bg=PANEL, fg=TEXT,
                       font=("Courier", 9, "bold"), anchor="w")
        lbl.pack(side="left", padx=6)
        return lbl

    def _refresh(self):
        ts = datetime.now().strftime("%H:%M:%S")
        self.ts_label.config(text=ts)

        # Services
        for svc_id, _ in SERVICES:
            status, color = get_service_status(svc_id)
            self.svc_frames[svc_id].config(text=status, fg=color)

        # Stats
        stats = get_system_stats()
        load_color = RED if stats["load1"] > 2.0 else (YELLOW if stats["load1"] > 1.0 else GREEN)
        self.load_lbl.config(text=f"{stats['load1']} / {stats['load5']}", fg=load_color)

        ram_color = RED if stats["ram_pct"] > 90 else (YELLOW if stats["ram_pct"] > 75 else GREEN)
        self.ram_lbl.config(text=f"{stats['ram_pct']}%  ({stats['ram_free_gb']}GB free)", fg=ram_color)

        disk_color = RED if stats["disk_pct"] > 85 else (YELLOW if stats["disk_pct"] > 70 else GREEN)
        self.disk_lbl.config(
            text=f"{stats['disk_pct']}%  ({stats['disk_used']} / {stats['disk_total']})",
            fg=disk_color
        )

        hb_age = get_heartbeat_age()
        if hb_age < 0:
            hb_text, hb_color = "missing", RED
        elif hb_age < 360:
            hb_text, hb_color = f"{hb_age}s ago", GREEN
        elif hb_age < 600:
            hb_text, hb_color = f"{hb_age}s ago", YELLOW
        else:
            hb_text, hb_color = f"{hb_age}s ago — STALE", RED
        self.hb_lbl.config(text=hb_text, fg=hb_color)

        loop_n = get_loop_count()
        self.loop_lbl.config(text=str(loop_n), fg=TEXT)

        fitness = get_fitness()
        fit_color = GREEN if "/" in fitness and int(fitness.split("/")[0]) > 8000 else YELLOW
        self.fit_lbl.config(text=fitness, fg=fit_color)

        # Relay
        relay_msgs = get_relay_recent(8)
        self.relay_text.config(state="normal")
        self.relay_text.delete("1.0", "end")
        for agent, msg, ts_str in relay_msgs:
            self.relay_text.insert("end", f"[{ts_str}] ", "ts")
            self.relay_text.insert("end", f"{agent}\n", "agent")
            self.relay_text.insert("end", f"{msg[:90]}\n\n", "msg")
        self.relay_text.config(state="disabled")

    def _schedule_refresh(self):
        self.root.after(30000, self._do_refresh)

    def _do_refresh(self):
        threading.Thread(target=self._refresh, daemon=True).start()
        self._schedule_refresh()


def main():
    root = tk.Tk()
    app = HealthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
