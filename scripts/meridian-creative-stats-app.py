#!/usr/bin/env python3
"""
MERIDIAN CREATIVE STATS
Standalone Tkinter desktop app — creative work overview from memory.db.
Nuevo Meridian theme. Shows counts, word totals, recent works, monthly chart.

Usage:
    python3 meridian-creative-stats-app.py
"""

__version__ = "1.0.0"

import tkinter as tk
from tkinter import ttk, font as tkfont
import sqlite3
import os
import sys
from datetime import datetime
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────
# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
DB_PATH = os.path.join(BASE, "memory.db")

# ── COLORS (Nuevo Meridian v3.0.0) ───────────────────────────────
BG        = "#06060e"
HEADER_BG = "#0e0e1b"
PANEL     = "#121220"
PANEL2    = "#1a1a2e"
INPUT_BG  = "#0e0e1b"
BORDER    = "#1e1e35"
FG        = "#e6e6f6"
DIM       = "#5a5a7a"
BRIGHT    = "#f0f0ff"
GREEN     = "#3dd68c"
GREEN2    = "#2bb872"
CYAN      = "#22d3ee"
AMBER     = "#f59e0b"
RED       = "#f87171"
GOLD      = "#fbbf24"
PURPLE    = "#a78bfa"
PINK      = "#f9a8d4"
TEAL      = "#2dd4bf"
BLUE      = "#818cf8"
INDIGO    = "#5b7cf6"
WHITE     = "#f8f8ff"

# Per-type colors
TYPE_COLORS = {
    "poem":     PURPLE,
    "journal":  CYAN,
    "cogcorp":  AMBER,
    "game":     GREEN,
    "article":  INDIGO,
}

TYPE_ICONS = {
    "poem":    "✦",
    "journal": "◈",
    "cogcorp": "⬡",
    "game":    "▶",
    "article": "⊙",
}


class CreativeStatsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian Creative Stats")
        self.geometry("1100x720")
        self.configure(bg=BG)
        self.minsize(800, 500)
        self.resizable(True, True)

        self._setup_fonts()
        self._setup_styles()

        self.data = self._load_data()
        self._build_ui()

    # ── Data loading ──────────────────────────────────────────────

    def _load_data(self):
        data = {
            "by_type": {},        # type → {count, words, max_words, avg_words}
            "recent": [],         # last 12 works
            "monthly": {},        # "YYYY-MM" → {type: count}
            "total_count": 0,
            "total_words": 0,
            "loop_count": None,
        }
        if not os.path.isfile(DB_PATH):
            return data

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # Per-type stats
            rows = c.execute(
                "SELECT type, COUNT(*), SUM(COALESCE(word_count,0)), "
                "MAX(COALESCE(word_count,0)), AVG(COALESCE(word_count,0)) "
                "FROM creative GROUP BY type ORDER BY COUNT(*) DESC"
            ).fetchall()
            for r in rows:
                t, cnt, total_w, max_w, avg_w = r
                data["by_type"][t] = {
                    "count": cnt,
                    "words": total_w or 0,
                    "max_words": max_w or 0,
                    "avg_words": int(avg_w or 0),
                }
                data["total_count"] += cnt
                data["total_words"] += (total_w or 0)

            # Recent works
            rows2 = c.execute(
                "SELECT type, number, title, COALESCE(word_count,0), created "
                "FROM creative ORDER BY id DESC LIMIT 15"
            ).fetchall()
            data["recent"] = list(rows2)

            # Monthly breakdown
            rows3 = c.execute(
                "SELECT strftime('%Y-%m', created) as month, type, COUNT(*) "
                "FROM creative GROUP BY month, type ORDER BY month ASC"
            ).fetchall()
            for month, t, cnt in rows3:
                if month not in data["monthly"]:
                    data["monthly"][month] = defaultdict(int)
                data["monthly"][month][t] += cnt

            # Loop count from file
            loop_file = os.path.join(BASE, ".loop-count")
            if os.path.isfile(loop_file):
                try:
                    data["loop_count"] = int(open(loop_file).read().strip())
                except Exception:
                    pass

            conn.close()
        except Exception as e:
            print(f"DB error: {e}")

        return data

    # ── Fonts ─────────────────────────────────────────────────────

    def _setup_fonts(self):
        families = tkfont.families()
        mono = "JetBrains Mono"
        if mono not in families:
            mono = "Fira Code" if "Fira Code" in families else "Monospace"
        self.font_main    = tkfont.Font(family=mono, size=10)
        self.font_small   = tkfont.Font(family=mono, size=9)
        self.font_tiny    = tkfont.Font(family=mono, size=8)
        self.font_heading = tkfont.Font(family=mono, size=13, weight="bold")
        self.font_label   = tkfont.Font(family=mono, size=10)
        self.font_num     = tkfont.Font(family=mono, size=22, weight="bold")
        self.font_nummed  = tkfont.Font(family=mono, size=16, weight="bold")
        self.font_bold    = tkfont.Font(family=mono, size=10, weight="bold")

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                        background=PANEL, foreground=FG,
                        fieldbackground=PANEL, borderwidth=0,
                        font=self.font_small, rowheight=24)
        style.configure("Dark.Treeview.Heading",
                        background=HEADER_BG, foreground=GREEN,
                        font=tkfont.Font(family="Monospace", size=9, weight="bold"),
                        borderwidth=0, relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", PANEL2)],
                  foreground=[("selected", BRIGHT)])
        style.configure("Dark.Vertical.TScrollbar",
                        background=BORDER, troughcolor=PANEL, borderwidth=0)

    # ── UI Build ──────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ─────────────────────────────────────────────
        header = tk.Frame(self, bg=HEADER_BG, height=52)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="CREATIVE STATS",
                 font=self.font_heading, fg=GREEN, bg=HEADER_BG).pack(side="left", padx=16, pady=10)
        tk.Label(header, text=f"v{__version__}",
                 font=self.font_small, fg=DIM, bg=HEADER_BG).pack(side="left", padx=(0, 12))

        total_c = self.data["total_count"]
        total_w = self.data["total_words"]
        tk.Label(header,
                 text=f"{total_c:,} works  •  {total_w:,} words",
                 font=self.font_label, fg=CYAN, bg=HEADER_BG).pack(side="left", padx=8)

        loop_n = self.data["loop_count"]
        if loop_n:
            tk.Label(header, text=f"Loop {loop_n:,}",
                     font=self.font_small, fg=DIM, bg=HEADER_BG).pack(side="right", padx=16)

        now_lbl = tk.Label(header, text=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                           font=self.font_small, fg=DIM, bg=HEADER_BG)
        now_lbl.pack(side="right", padx=(0, 8))

        refresh_btn = tk.Label(header, text=" ↻ Refresh ",
                               font=self.font_small, fg=CYAN, bg=PANEL2,
                               cursor="hand2", padx=6, pady=2)
        refresh_btn.pack(side="right", padx=12)
        refresh_btn.bind("<Button-1>", lambda e: self._do_refresh())

        # ── Main body ───────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Left column: type cards + recent
        left = tk.Frame(body, bg=BG, width=400)
        left.pack(side="left", fill="both", expand=False, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        # Right column: chart + details
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        self._build_type_cards(left)
        self._build_recent(left)
        self._build_chart(right)
        self._build_recent_table(right)

    def _build_type_cards(self, parent):
        """Summary cards — one per creative type."""
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", pady=(0, 6))

        tk.Label(sec, text="BY TYPE", font=self.font_small,
                 fg=DIM, bg=BG).pack(anchor="w", padx=4, pady=(0, 4))

        cards_frame = tk.Frame(sec, bg=BG)
        cards_frame.pack(fill="x")

        for t, stats in self.data["by_type"].items():
            color = TYPE_COLORS.get(t, FG)
            icon  = TYPE_ICONS.get(t, "◆")
            card  = tk.Frame(cards_frame, bg=PANEL, padx=10, pady=8)
            card.pack(fill="x", pady=2)

            # Color bar on left
            bar = tk.Frame(card, bg=color, width=4)
            bar.pack(side="left", fill="y", padx=(0, 10))

            info = tk.Frame(card, bg=PANEL)
            info.pack(side="left", fill="both", expand=True)

            top_row = tk.Frame(info, bg=PANEL)
            top_row.pack(fill="x")
            tk.Label(top_row, text=f"{icon} {t.upper()}",
                     font=self.font_bold, fg=color, bg=PANEL).pack(side="left")
            tk.Label(top_row, text=f"{stats['count']:,}",
                     font=self.font_nummed, fg=BRIGHT, bg=PANEL).pack(side="right")

            bot_row = tk.Frame(info, bg=PANEL)
            bot_row.pack(fill="x")
            wds = stats["words"]
            avg = stats["avg_words"]
            tk.Label(bot_row,
                     text=f"{wds:,} words total  •  avg {avg:,}/work",
                     font=self.font_tiny, fg=DIM, bg=PANEL).pack(side="left")

    def _build_recent(self, parent):
        """Last 8 works, compact list."""
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", pady=(6, 0))

        tk.Label(sec, text="RECENT WORKS", font=self.font_small,
                 fg=DIM, bg=BG).pack(anchor="w", padx=4, pady=(0, 4))

        for r in self.data["recent"][:8]:
            t, num, title, wc, created = r
            color = TYPE_COLORS.get(t, FG)
            icon  = TYPE_ICONS.get(t, "◆")
            row   = tk.Frame(sec, bg=PANEL, pady=4, padx=8)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=f"{icon}", font=self.font_small, fg=color, bg=PANEL,
                     width=2).pack(side="left")
            tk.Label(row, text=f"#{num}", font=self.font_tiny, fg=DIM, bg=PANEL,
                     width=5, anchor="e").pack(side="left", padx=(0, 6))
            title_lbl = title[:38] + ("…" if len(title) > 38 else "")
            tk.Label(row, text=title_lbl, font=self.font_small, fg=FG, bg=PANEL,
                     anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(row, text=f"{wc}w", font=self.font_tiny, fg=DIM, bg=PANEL,
                     width=6, anchor="e").pack(side="right")

    def _build_chart(self, parent):
        """Monthly output bar chart using Canvas."""
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="x", pady=(0, 8))

        tk.Label(sec, text="MONTHLY OUTPUT", font=self.font_small,
                 fg=DIM, bg=BG).pack(anchor="w", padx=4, pady=(0, 4))

        self.chart_canvas = tk.Canvas(sec, bg=PANEL, height=180,
                                       highlightthickness=0)
        self.chart_canvas.pack(fill="x", padx=2)
        self.chart_canvas.bind("<Configure>", lambda e: self._draw_chart())
        self.after(100, self._draw_chart)

    def _draw_chart(self):
        c = self.chart_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return

        monthly = self.data["monthly"]
        if not monthly:
            c.create_text(w // 2, h // 2, text="No data", fill=DIM,
                          font=self.font_small)
            return

        # Last 12 months
        months = sorted(monthly.keys())[-12:]
        types_shown = ["poem", "journal", "cogcorp", "game", "article"]

        # Max total per month for scaling
        month_totals = []
        for m in months:
            total = sum(monthly[m].get(t, 0) for t in types_shown)
            month_totals.append(total)
        max_total = max(month_totals) if month_totals else 1

        pad_l, pad_r, pad_t, pad_b = 8, 8, 16, 32
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b

        bar_group_w = chart_w / max(len(months), 1)
        bar_w = max(bar_group_w * 0.7, 6)
        bar_gap = (bar_group_w - bar_w) / 2

        # Draw bars (stacked)
        for i, m in enumerate(months):
            x0 = pad_l + i * bar_group_w + bar_gap
            x1 = x0 + bar_w
            y_base = h - pad_b
            cumulative = 0

            for t in types_shown:
                cnt = monthly[m].get(t, 0)
                if cnt == 0:
                    continue
                bar_h_seg = (cnt / max_total) * chart_h
                y1 = y_base - cumulative
                y0 = y1 - bar_h_seg
                color = TYPE_COLORS.get(t, DIM)
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline="", width=0)
                cumulative += bar_h_seg

            # Month label
            label = m[5:] if m else ""  # "03" from "2026-03"
            cx = (x0 + x1) / 2
            c.create_text(cx, h - pad_b + 10, text=label, fill=DIM,
                          font=self.font_tiny, anchor="n")

            # Total label on top
            total = month_totals[i]
            if total > 0:
                top_y = y_base - (total / max_total) * chart_h - 4
                c.create_text(cx, top_y, text=str(total), fill=BRIGHT,
                              font=self.font_tiny, anchor="s")

        # Y-axis gridlines
        for pct in [0.25, 0.5, 0.75, 1.0]:
            y = (h - pad_b) - pct * chart_h
            val = int(max_total * pct)
            c.create_line(pad_l, y, w - pad_r, y, fill=BORDER, width=1, dash=(2, 4))
            c.create_text(pad_l - 2, y, text=str(val), fill=DIM,
                          font=self.font_tiny, anchor="e")

        # Legend (top right)
        lx = w - pad_r - 2
        ly = pad_t + 2
        for t in reversed(types_shown):
            if any(monthly[m].get(t, 0) > 0 for m in months):
                color = TYPE_COLORS.get(t, DIM)
                icon = TYPE_ICONS.get(t, "◆")
                c.create_text(lx, ly, text=f"{icon} {t}", fill=color,
                              font=self.font_tiny, anchor="ne")
                ly += 14

    def _build_recent_table(self, parent):
        """Full scrollable recent works table."""
        sec = tk.Frame(parent, bg=BG)
        sec.pack(fill="both", expand=True)

        tk.Label(sec, text="ALL RECENT", font=self.font_small,
                 fg=DIM, bg=BG).pack(anchor="w", padx=4, pady=(0, 4))

        tree_frame = tk.Frame(sec, bg=BG)
        tree_frame.pack(fill="both", expand=True)

        cols = ("type", "number", "title", "words", "created")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="Dark.Treeview", selectmode="browse")

        col_widths = {"type": 72, "number": 55, "title": 320, "words": 60, "created": 140}
        for col in cols:
            self.tree.heading(col, text=col.upper(), anchor="w")
            self.tree.column(col, width=col_widths.get(col, 100), minwidth=40, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tree.yview, style="Dark.Vertical.TScrollbar")
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)

        # Populate
        self._populate_table()

        # Tag colors per type
        for t, color in TYPE_COLORS.items():
            self.tree.tag_configure(t, foreground=color)

    def _populate_table(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.data["recent"]:
            t, num, title, wc, created = r
            date_str = str(created)[:16] if created else ""
            tag = t if t in TYPE_COLORS else ""
            self.tree.insert("", "end",
                             values=(t, f"#{num}", title[:80], wc, date_str),
                             tags=(tag,))

    # ── Refresh ───────────────────────────────────────────────────

    def _do_refresh(self):
        self.data = self._load_data()
        # Rebuild all widgets
        for widget in self.winfo_children():
            widget.destroy()
        self._setup_styles()
        self._build_ui()


def main():
    if not os.path.isfile(DB_PATH):
        print(f"Error: {DB_PATH} not found")
        sys.exit(1)
    app = CreativeStatsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
