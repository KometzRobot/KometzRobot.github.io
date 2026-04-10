#!/usr/bin/env python3
"""
MERIDIAN RELAY VIEWER
Standalone desktop app — live view of agent-relay.db
Topic filter toolbar. Auto-refresh every 5s.
Expand any message. Color-coded by agent.

Usage: python3 meridian-relay-app.py
"""

__version__ = "1.0.0"

import tkinter as tk
from tkinter import ttk
import sqlite3
import os
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────
DB_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-relay.db")
REFRESH_MS = 5000
MAX_ROWS   = 150

# ── COLORS ──────────────────────────────────────────────────────────
BG        = "#0a0a12"
PANEL     = "#12121c"
HEADER_BG = "#06060e"
BORDER    = "#1e1e2e"
TEXT      = "#e2e8f0"
DIM       = "#64748b"
ACCENT    = "#64B5F6"

AGENT_COLORS = {
    "Meridian":     "#38bdf8",
    "MeridianLoop": "#38bdf8",
    "Cinder":       "#f97316",
    "Soma":         "#a78bfa",
    "Eos":          "#34d399",
    "Nova":         "#60a5fa",
    "Atlas":        "#fb7185",
    "Tempo":        "#facc15",
    "Hermes":       "#c084fc",
    "Sammy":        "#67e8f9",
    "Loom":         "#86efac",
}
DEFAULT_AGENT_COLOR = "#94a3b8"

TOPIC_COLORS = {
    "status":       "#3b82f6",
    "fitness":      "#10b981",
    "mood":         "#8b5cf6",
    "briefing":     "#f97316",
    "alert":        "#ef4444",
    "loop":         "#64B5F6",
    "infra-audit":  "#6366f1",
    "maintenance":  "#64748b",
    "inter-agent":  "#ec4899",
    "nerve-event":  "#475569",
    "cascade":      "#fbbf24",
    "general":      "#64748b",
}

TOPICS = ["ALL", "status", "fitness", "mood", "briefing", "alert",
          "loop", "infra-audit", "maintenance", "inter-agent", "nerve-event", "cascade"]


def get_agent_color(agent):
    for key, color in AGENT_COLORS.items():
        if key.lower() in agent.lower():
            return color
    return DEFAULT_AGENT_COLOR


def get_topic_color(topic):
    return TOPIC_COLORS.get(topic.lower(), TOPIC_COLORS["general"])


class RelayApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian — Relay Viewer")
        self.geometry("1100x700")
        self.configure(bg=BG)
        self.minsize(800, 500)

        self._active_topic = "ALL"
        self._rows = []
        self._expanded = None

        self._build_ui()
        self._refresh()

    # ── UI BUILD ────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=HEADER_BG, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="RELAY", bg=HEADER_BG, fg=ACCENT,
                 font=("monospace", 16, "bold")).pack(side="left", padx=16, pady=14)

        self._hdr_status = tk.Label(hdr, text="", bg=HEADER_BG, fg=DIM,
                                    font=("monospace", 10))
        self._hdr_status.pack(side="right", padx=16)

        # Topic filter bar
        bar = tk.Frame(self, bg=PANEL, pady=6)
        bar.pack(fill="x")

        self._topic_btns = {}
        for t in TOPICS:
            color = get_topic_color(t) if t != "ALL" else ACCENT
            btn = tk.Button(bar, text=t.upper(), bg=PANEL, fg=DIM,
                            font=("monospace", 8, "bold"),
                            relief="flat", padx=8, pady=4,
                            cursor="hand2",
                            command=lambda _t=t: self._set_topic(_t),
                            activebackground=BORDER, activeforeground=TEXT)
            btn.pack(side="left", padx=2)
            self._topic_btns[t] = (btn, color)

        self._set_topic("ALL")

        # Message list (canvas + scrollbar)
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill="both", expand=True, padx=0, pady=0)

        self._canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(frame, orient="vertical", command=self._canvas.yview,
                          bg=PANEL, troughcolor=BG)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=sb.set)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner,
                                                          anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

        # Expand panel (bottom)
        self._expand_frame = tk.Frame(self, bg=PANEL, height=0)
        self._expand_frame.pack(fill="x")
        self._expand_label = tk.Label(self._expand_frame, text="", bg=PANEL,
                                      fg=TEXT, font=("monospace", 9),
                                      wraplength=1060, justify="left", anchor="nw",
                                      padx=12, pady=8)

    def _on_inner_configure(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _on_mousewheel(self, e):
        if e.num == 4:
            self._canvas.yview_scroll(-2, "units")
        elif e.num == 5:
            self._canvas.yview_scroll(2, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ── TOPIC FILTER ────────────────────────────────────────────────

    def _set_topic(self, topic):
        self._active_topic = topic
        for t, (btn, color) in self._topic_btns.items():
            if t == topic:
                btn.configure(fg=color, bg=BORDER)
            else:
                btn.configure(fg=DIM, bg=PANEL)
        self._render_rows()

    # ── DATA FETCH ──────────────────────────────────────────────────

    def _load_rows(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            if self._active_topic == "ALL":
                c.execute("""
                    SELECT id, timestamp, agent, topic, message
                    FROM agent_messages
                    ORDER BY id DESC LIMIT ?
                """, (MAX_ROWS,))
            else:
                c.execute("""
                    SELECT id, timestamp, agent, topic, message
                    FROM agent_messages
                    WHERE LOWER(topic) = LOWER(?)
                    ORDER BY id DESC LIMIT ?
                """, (self._active_topic, MAX_ROWS))
            rows = c.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            return []

    # ── RENDER ──────────────────────────────────────────────────────

    def _render_rows(self):
        # Clear existing widgets
        for w in self._inner.winfo_children():
            w.destroy()

        for row in self._rows:
            rid, ts, agent, topic, message = row
            self._render_row(rid, ts, agent, topic, message)

        # Scroll to bottom
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    def _render_row(self, rid, ts, agent, topic, message):
        agent_color = get_agent_color(agent)
        topic_color = get_topic_color(topic)

        # Format timestamp — relay DB stores UTC, convert to local
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                from datetime import timezone
                dt = dt.replace(tzinfo=timezone.utc)
            ts_str = dt.astimezone().strftime("%H:%M:%S")
        except Exception:
            ts_str = ts[:8] if len(ts) >= 8 else ts

        # Truncate message for single-line display
        short_msg = message.replace("\n", " ")
        if len(short_msg) > 140:
            short_msg = short_msg[:137] + "..."

        row_frame = tk.Frame(self._inner, bg=BG, padx=8, pady=3, cursor="hand2")
        row_frame.pack(fill="x", padx=0)

        # Divider
        tk.Frame(self._inner, bg=BORDER, height=1).pack(fill="x")

        # Row content: [time] [AGENT] [TOPIC] message
        inner = tk.Frame(row_frame, bg=BG)
        inner.pack(fill="x")

        tk.Label(inner, text=ts_str, bg=BG, fg=DIM,
                 font=("monospace", 8), width=9, anchor="w").pack(side="left")

        agent_short = agent[:12]
        tk.Label(inner, text=agent_short, bg=BG, fg=agent_color,
                 font=("monospace", 8, "bold"), width=13, anchor="w").pack(side="left")

        topic_short = topic[:10].upper()
        tk.Label(inner, text=topic_short, bg=BG, fg=topic_color,
                 font=("monospace", 8), width=12, anchor="w").pack(side="left")

        tk.Label(inner, text=short_msg, bg=BG, fg=TEXT,
                 font=("monospace", 9), anchor="w", justify="left").pack(side="left", fill="x", expand=True)

        # Click to expand
        for w in [row_frame, inner] + inner.winfo_children():
            w.bind("<Button-1>", lambda e, _rid=rid, _msg=message, _agent=agent, _topic=topic:
                   self._expand_message(_rid, _agent, _topic, _msg))

    def _expand_message(self, rid, agent, topic, message):
        if self._expanded == rid:
            self._expand_label.pack_forget()
            self._expand_frame.configure(height=0)
            self._expanded = None
            return

        self._expanded = rid
        agent_color = get_agent_color(agent)
        topic_color = get_topic_color(topic)
        display = f"[{agent}] [{topic}]\n\n{message}"

        self._expand_label.configure(text=display, fg=agent_color)
        self._expand_label.pack(fill="x")
        self._expand_frame.configure(height=120)

    # ── REFRESH LOOP ────────────────────────────────────────────────

    def _refresh(self):
        new_rows = self._load_rows()

        if new_rows != self._rows:
            old_count = len(self._rows)
            self._rows = new_rows
            self._render_rows()
            new_count = len(new_rows)
            now = datetime.now().strftime("%H:%M:%S")
            self._hdr_status.configure(
                text=f"{new_count} messages | refreshed {now}"
            )

        self.after(REFRESH_MS, self._refresh)


if __name__ == "__main__":
    app = RelayApp()
    app.mainloop()
