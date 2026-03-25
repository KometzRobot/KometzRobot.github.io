#!/usr/bin/env python3
"""
MERIDIAN JOURNAL VIEWER
Standalone desktop app — browse all journals in creative/journals/
Search, word count, date, full-text preview.
Nuevo Meridian v3.0.0 theme.

Usage: python3 meridian-journals-app.py
"""

__version__ = "1.0.0"

import tkinter as tk
from tkinter import ttk, font as tkfont, scrolledtext
import os
import re
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
JOURNALS_DIR = os.path.join(BASE, "creative", "journals")
REFRESH_MS  = 30000  # Re-scan every 30s

# ── COLORS (Nuevo Meridian v3.0.0) ──────────────────────────────────
BG        = "#06060e"
HEADER_BG = "#0e0e1b"
PANEL     = "#121220"
PANEL2    = "#1a1a2e"
INPUT_BG  = "#0e0e1b"
BORDER    = "#1e1e35"
ACTIVE_BG = "#1e1e35"
FG        = "#e6e6f6"
DIM       = "#5a5a7a"
BRIGHT    = "#f0f0ff"
GREEN     = "#3dd68c"
CYAN      = "#22d3ee"
AMBER     = "#f59e0b"
RED       = "#f87171"
GOLD      = "#fbbf24"
PURPLE    = "#a78bfa"
INDIGO    = "#5b7cf6"
TEAL      = "#2dd4bf"


def scan_journals():
    """Scan journals directory and return sorted list of (num, filename, path, date_str, wc, title)."""
    entries = []
    if not os.path.isdir(JOURNALS_DIR):
        return entries

    for fname in os.listdir(JOURNALS_DIR):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(JOURNALS_DIR, fname)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Extract number from filename
            m = re.match(r"journal-(\d+)", fname)
            num = int(m.group(1)) if m else 0

            # Extract title from first # heading
            title_m = re.search(r"^#\s+(.+?)(?:\s*—.*)?$", content, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else fname.replace(".md", "")

            # Extract date string
            date_m = re.search(r"\*([A-Z][a-z]+ \d+, \d{4})", content)
            date_str = date_m.group(1) if date_m else ""

            # Try to get mtime if no date found
            if not date_str:
                mtime = os.path.getmtime(path)
                date_str = datetime.fromtimestamp(mtime).strftime("%b %d, %Y")

            # Word count (approximate)
            words = len(re.findall(r"\b\w+\b", content))

            entries.append((num, fname, path, date_str, words, title, content))
        except Exception:
            continue

    # Sort by number descending (newest first)
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries


class JournalViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Meridian Journals v{__version__}")
        self.configure(bg=BG)
        self.geometry("1200x750")
        self.minsize(800, 500)

        self._journals = []
        self._filtered = []
        self._selected_path = None
        self._refresh_timer = None

        self._fonts()
        self._build_ui()
        self._load()
        self._schedule_refresh()

    def _fonts(self):
        self.f_title = tkfont.Font(family="Ubuntu", size=13, weight="bold")
        self.f_head  = tkfont.Font(family="Ubuntu", size=11, weight="bold")
        self.f_body  = tkfont.Font(family="Ubuntu", size=10)
        self.f_small = tkfont.Font(family="Ubuntu", size=9)
        self.f_mono  = tkfont.Font(family="Ubuntu Mono", size=10)
        self.f_tiny  = tkfont.Font(family="Ubuntu", size=8)

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=HEADER_BG, height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)

        left = tk.Frame(hdr, bg=HEADER_BG)
        left.pack(side=tk.LEFT, padx=16, fill=tk.Y)
        tk.Label(left, text="JOURNALS", font=self.f_title, fg=INDIGO, bg=HEADER_BG).pack(
            side=tk.LEFT, pady=10)
        self.h_count = tk.Label(left, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_count.pack(side=tk.LEFT, padx=12, pady=10)

        right = tk.Frame(hdr, bg=HEADER_BG)
        right.pack(side=tk.RIGHT, padx=16, fill=tk.Y)
        self.h_wc = tk.Label(right, text="", font=self.f_small, fg=DIM, bg=HEADER_BG)
        self.h_wc.pack(side=tk.RIGHT, pady=10)

        # ── Search bar ──────────────────────────────────────────────
        search_row = tk.Frame(self, bg=HEADER_BG, height=38)
        search_row.pack(fill=tk.X)
        search_row.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)

        tk.Label(search_row, text="  🔍", font=self.f_small, fg=DIM, bg=HEADER_BG).pack(
            side=tk.LEFT, padx=(8, 2), pady=8)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        search_entry = tk.Entry(search_row, textvariable=self.search_var,
                                font=self.f_body, bg=INPUT_BG, fg=FG,
                                insertbackground=INDIGO, relief=tk.FLAT,
                                highlightthickness=1, highlightcolor=INDIGO,
                                highlightbackground=BORDER)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)

        # Clear button
        tk.Button(search_row, text="✕", font=self.f_tiny, fg=DIM, bg=HEADER_BG,
                  activeforeground=FG, activebackground=HEADER_BG,
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=lambda: self.search_var.set("")).pack(
            side=tk.LEFT, padx=(0, 12), pady=8)

        # ── Main split: list (left) + preview (right) ───────────────
        pane = tk.Frame(self, bg=BG)
        pane.pack(fill=tk.BOTH, expand=True)

        # Left: journal list
        list_frame = tk.Frame(pane, bg=PANEL, width=420)
        list_frame.pack(side=tk.LEFT, fill=tk.Y)
        list_frame.pack_propagate(False)
        tk.Frame(pane, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Treeview for journal list
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("J.Treeview",
                         background=PANEL, foreground=FG,
                         fieldbackground=PANEL, rowheight=44,
                         borderwidth=0, relief="flat",
                         font=("Ubuntu", 10))
        style.configure("J.Treeview.Heading",
                         background=PANEL2, foreground=DIM,
                         relief="flat", font=("Ubuntu", 8, "bold"))
        style.map("J.Treeview",
                  background=[("selected", ACTIVE_BG)],
                  foreground=[("selected", BRIGHT)])

        self.tree = ttk.Treeview(list_frame, style="J.Treeview",
                                  columns=("num", "title", "date", "wc"),
                                  show="headings", selectmode="browse")
        self.tree.heading("num",   text="#",      anchor="e")
        self.tree.heading("title", text="TITLE",  anchor="w")
        self.tree.heading("date",  text="DATE",   anchor="w")
        self.tree.heading("wc",    text="WORDS",  anchor="e")
        self.tree.column("num",   width=50,  minwidth=40,  anchor="e")
        self.tree.column("title", width=200, minwidth=120, anchor="w")
        self.tree.column("date",  width=100, minwidth=80,  anchor="w")
        self.tree.column("wc",    width=60,  minwidth=50,  anchor="e")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: preview pane
        right_frame = tk.Frame(pane, bg=BG)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Preview header
        prev_hdr = tk.Frame(right_frame, bg=PANEL2, height=44)
        prev_hdr.pack(fill=tk.X)
        prev_hdr.pack_propagate(False)
        self.prev_title = tk.Label(prev_hdr, text="Select a journal",
                                   font=self.f_head, fg=BRIGHT, bg=PANEL2,
                                   anchor="w")
        self.prev_title.pack(side=tk.LEFT, padx=16, pady=10)
        self.prev_meta = tk.Label(prev_hdr, text="",
                                  font=self.f_tiny, fg=DIM, bg=PANEL2,
                                  anchor="e")
        self.prev_meta.pack(side=tk.RIGHT, padx=16, pady=10)
        tk.Frame(right_frame, bg=BORDER, height=1).pack(fill=tk.X)

        # Preview text
        self.preview = scrolledtext.ScrolledText(
            right_frame, font=self.f_mono, bg=PANEL, fg=FG,
            insertbackground=INDIGO, relief=tk.FLAT, wrap=tk.WORD,
            padx=20, pady=16, state="disabled",
            selectbackground=ACTIVE_BG, selectforeground=BRIGHT,
            highlightthickness=0)
        self.preview.pack(fill=tk.BOTH, expand=True)

        # ── Status bar ───────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)
        sb = tk.Frame(self, bg=HEADER_BG, height=24)
        sb.pack(fill=tk.X)
        sb.pack_propagate(False)
        self.status = tk.Label(sb, text="", font=self.f_tiny, fg=DIM, bg=HEADER_BG,
                               anchor="w")
        self.status.pack(side=tk.LEFT, padx=12)
        tk.Label(sb, text=f"v{__version__}", font=self.f_tiny, fg=DIM,
                 bg=HEADER_BG).pack(side=tk.RIGHT, padx=12)

    # ── Data ────────────────────────────────────────────────────────

    def _load(self):
        self._journals = scan_journals()
        self._filter()
        total_wc = sum(j[4] for j in self._journals)
        self.h_count.configure(text=f"{len(self._journals)} journals")
        self.h_wc.configure(text=f"{total_wc:,} total words")
        self.status.configure(text=f"Scanned {JOURNALS_DIR}")

    def _filter(self):
        q = self.search_var.get().strip().lower()
        if q:
            self._filtered = [j for j in self._journals
                               if q in j[5].lower() or q in j[6].lower()
                               or q in j[3].lower()]
        else:
            self._filtered = list(self._journals)

        self.tree.delete(*self.tree.get_children())
        for num, fname, path, date_str, wc, title, _ in self._filtered:
            label = title[:38] + "…" if len(title) > 38 else title
            self.tree.insert("", "end", iid=path,
                             values=(num or "—", label, date_str, f"{wc:,}"))

        count = len(self._filtered)
        total = len(self._journals)
        if q:
            self.h_count.configure(text=f"{count} / {total} journals")
        else:
            self.h_count.configure(text=f"{total} journals")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        path = sel[0]  # iid is the path
        # Find journal entry
        entry = next((j for j in self._filtered if j[2] == path), None)
        if not entry:
            return

        num, fname, _, date_str, wc, title, content = entry
        self.prev_title.configure(text=title[:80])
        self.prev_meta.configure(text=f"#{num}  ·  {date_str}  ·  {wc:,} words")

        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", content)
        self.preview.configure(state="disabled")
        self.preview.yview_moveto(0)

    def _schedule_refresh(self):
        self._load()
        self._refresh_timer = self.after(REFRESH_MS, self._schedule_refresh)

    def destroy(self):
        if self._refresh_timer:
            self.after_cancel(self._refresh_timer)
        super().destroy()


def main():
    app = JournalViewer()
    app.mainloop()


if __name__ == "__main__":
    main()
