#!/usr/bin/env python3
"""
MERIDIAN MEMORY DB BROWSER

Standalone Tkinter desktop app for browsing memory.db.
Dark theme matching Command Center color scheme.

Usage:
    python3 memory-browser.py
    python3 memory-browser.py /path/to/other/memory.db
"""

__version__ = "2.0.0"

import tkinter as tk
from tkinter import ttk, font as tkfont, messagebox, simpledialog
import sqlite3
import os
import sys
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")
if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
    DB_PATH = sys.argv[1]

# ── COLORS (Nuevo Meridian v3.0.0 — matches Command Center) ──────
BG        = "#06060e"
HEADER_BG = "#0e0e1b"
PANEL     = "#121220"
PANEL2    = "#1a1a2e"
INPUT_BG  = "#0e0e1b"
BORDER    = "#1e1e35"
ACCENT    = "#0e0e1b"
ACTIVE_BG = "#1e1e35"
FG        = "#e6e6f6"
DIM       = "#5a5a7a"
BRIGHT    = "#f0f0ff"
GREEN     = "#3dd68c"
GREEN2    = "#2bb872"
CYAN      = "#22d3ee"
CYAN2     = "#06b6d4"
AMBER     = "#f59e0b"
RED       = "#f87171"
GOLD      = "#fbbf24"
WHITE     = "#f8f8ff"
PURPLE    = "#a78bfa"
PINK      = "#f9a8d4"
TEAL      = "#2dd4bf"
BLUE      = "#818cf8"
INDIGO    = "#5b7cf6"

# Tables to show (skip FTS internals and sqlite_sequence)
SKIP_TABLES = {"sqlite_sequence", "memory_fts", "memory_fts_data",
               "memory_fts_idx", "memory_fts_docsize", "memory_fts_config"}

# Per-table accent colors for sidebar highlights
TABLE_COLORS = {
    "facts":       GREEN,
    "observations": CYAN,
    "decisions":   AMBER,
    "creative":    PURPLE,
    "events":      BLUE,
    "skills":      TEAL,
    "loop_fitness": GOLD,
    "sent_emails": PINK,
    "contacts":    GREEN2,
    "vector_memory": DIM,
    "feedback":    CYAN2,
    "errors":      RED,
    "goals":       AMBER,
    "experiments": PURPLE,
    "newsletter_issues": TEAL,
    "dossiers":    INDIGO,
}


class MemoryBrowser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian Memory Browser")
        self.geometry("1400x850")
        self.configure(bg=BG)
        self.minsize(900, 500)

        # Connect to DB
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

        # Discover tables
        self.tables = self._get_tables()
        self.table_counts = {}
        for t in self.tables:
            try:
                c = self.conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except Exception:
                c = 0
            self.table_counts[t] = c

        self.current_table = None
        self.current_columns = []
        self.sort_col = None
        self.sort_reverse = False

        self._setup_fonts()
        self._setup_styles()
        self._build_ui()

        # Select first table
        if self.tables:
            self._select_table(self.tables[0])

    # ── DB helpers ────────────────────────────────────────────────

    def _get_tables(self):
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows if r[0] not in SKIP_TABLES]

    def _get_columns(self, table):
        info = self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [row[1] for row in info]

    def _query_table(self, table, search=""):
        cols = self._get_columns(table)
        self.current_columns = cols

        if search.strip():
            term = search.strip()
            where_clauses = []
            params = []
            for col in cols:
                where_clauses.append(f'CAST("{col}" AS TEXT) LIKE ?')
                params.append(f"%{term}%")
            where = " OR ".join(where_clauses)
            sql = f'SELECT * FROM "{table}" WHERE {where}'
            order = ""
            if self.sort_col and self.sort_col in cols:
                direction = "DESC" if self.sort_reverse else "ASC"
                order = f' ORDER BY "{self.sort_col}" {direction}'
            sql += order
            rows = self.conn.execute(sql, params).fetchall()
        else:
            order = ""
            if self.sort_col and self.sort_col in cols:
                direction = "DESC" if self.sort_reverse else "ASC"
                order = f' ORDER BY "{self.sort_col}" {direction}'
            sql = f'SELECT * FROM "{table}"{order}'
            rows = self.conn.execute(sql).fetchall()

        return cols, rows

    # ── Fonts & styles ────────────────────────────────────────────

    def _setup_fonts(self):
        families = tkfont.families()
        mono = "JetBrains Mono"
        if mono not in families:
            mono = "Fira Code" if "Fira Code" in families else "Monospace"
        self.font_main = tkfont.Font(family=mono, size=10)
        self.font_small = tkfont.Font(family=mono, size=9)
        self.font_heading = tkfont.Font(family=mono, size=12, weight="bold")
        self.font_sidebar = tkfont.Font(family=mono, size=10)
        self.font_sidebar_bold = tkfont.Font(family=mono, size=10, weight="bold")
        self.font_tree_head = tkfont.Font(family=mono, size=9, weight="bold")

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Treeview
        style.configure("Dark.Treeview",
                         background=PANEL,
                         foreground=FG,
                         fieldbackground=PANEL,
                         borderwidth=0,
                         font=self.font_small,
                         rowheight=26)
        style.configure("Dark.Treeview.Heading",
                         background=HEADER_BG,
                         foreground=GREEN,
                         font=self.font_tree_head,
                         borderwidth=1,
                         relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", ACTIVE_BG)],
                  foreground=[("selected", BRIGHT)])
        style.map("Dark.Treeview.Heading",
                  background=[("active", ACCENT)])

        # Scrollbar
        style.configure("Dark.Vertical.TScrollbar",
                         background=BORDER,
                         troughcolor=PANEL,
                         borderwidth=0,
                         arrowsize=14)
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", DIM)])

        style.configure("Dark.Horizontal.TScrollbar",
                         background=BORDER,
                         troughcolor=PANEL,
                         borderwidth=0,
                         arrowsize=14)
        style.map("Dark.Horizontal.TScrollbar",
                  background=[("active", DIM)])

    # ── UI build ──────────────────────────────────────────────────

    def _build_ui(self):
        # Header bar
        header = tk.Frame(self, bg=HEADER_BG, height=48)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="MEMORY DB BROWSER",
                 font=self.font_heading, fg=GREEN, bg=HEADER_BG).pack(side="left", padx=16)

        tk.Label(header, text=f"v{__version__}",
                 font=self.font_small, fg=DIM, bg=HEADER_BG).pack(side="left", padx=(0, 16))

        db_label = os.path.basename(DB_PATH)
        tk.Label(header, text=db_label,
                 font=self.font_small, fg=CYAN, bg=HEADER_BG).pack(side="left")

        # Total rows
        total = sum(self.table_counts.values())
        tk.Label(header, text=f"{total:,} total rows",
                 font=self.font_small, fg=DIM, bg=HEADER_BG).pack(side="right", padx=16)

        # Main container
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(main, bg=PANEL, width=220)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)

        sidebar_head = tk.Frame(self.sidebar, bg=PANEL)
        sidebar_head.pack(fill="x", padx=8, pady=(12, 4))
        tk.Label(sidebar_head, text="TABLES",
                 font=self.font_sidebar_bold, fg=DIM, bg=PANEL).pack(side="left")
        tk.Label(sidebar_head, text=f"({len(self.tables)})",
                 font=self.font_small, fg=DIM, bg=PANEL).pack(side="left", padx=4)

        sep = tk.Frame(self.sidebar, bg=BORDER, height=1)
        sep.pack(fill="x", padx=8, pady=(2, 6))

        self.sidebar_buttons = {}
        for table in self.tables:
            count = self.table_counts.get(table, 0)
            color = TABLE_COLORS.get(table, FG)
            btn_frame = tk.Frame(self.sidebar, bg=PANEL, cursor="hand2")
            btn_frame.pack(fill="x", padx=6, pady=1)

            lbl_name = tk.Label(btn_frame, text=table,
                                font=self.font_sidebar, fg=FG, bg=PANEL,
                                anchor="w", cursor="hand2")
            lbl_name.pack(side="left", padx=(8, 4), pady=4)

            lbl_count = tk.Label(btn_frame, text=str(count),
                                 font=self.font_small, fg=DIM, bg=PANEL,
                                 anchor="e", cursor="hand2")
            lbl_count.pack(side="right", padx=(4, 8), pady=4)

            # Color dot
            dot = tk.Label(btn_frame, text="\u2588", font=("", 6),
                           fg=color, bg=PANEL)
            dot.pack(side="left", padx=(0, 0))

            self.sidebar_buttons[table] = (btn_frame, lbl_name, lbl_count, dot)

            # Bind clicks
            for widget in (btn_frame, lbl_name, lbl_count, dot):
                widget.bind("<Button-1>", lambda e, t=table: self._select_table(t))

        # Content area
        content = tk.Frame(main, bg=BG)
        content.pack(fill="both", expand=True, side="left")

        # Toolbar
        toolbar = tk.Frame(content, bg=PANEL2, height=44)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        self.table_label = tk.Label(toolbar, text="",
                                     font=self.font_heading, fg=GREEN, bg=PANEL2)
        self.table_label.pack(side="left", padx=12)

        self.row_count_label = tk.Label(toolbar, text="",
                                         font=self.font_small, fg=DIM, bg=PANEL2)
        self.row_count_label.pack(side="left", padx=(0, 16))

        # Search
        search_frame = tk.Frame(toolbar, bg=PANEL2)
        search_frame.pack(side="right", padx=12)

        tk.Label(search_frame, text="Filter:",
                 font=self.font_small, fg=DIM, bg=PANEL2).pack(side="left", padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame,
                                      textvariable=self.search_var,
                                      font=self.font_main,
                                      bg=INPUT_BG, fg=FG,
                                      insertbackground=GREEN,
                                      relief="flat",
                                      width=30,
                                      highlightbackground=BORDER,
                                      highlightcolor=GREEN,
                                      highlightthickness=1)
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<Return>", lambda e: self._refresh())
        self.search_var.trace_add("write", lambda *a: self._schedule_refresh())

        clear_btn = tk.Label(search_frame, text=" \u2715 ", font=self.font_small,
                             fg=DIM, bg=PANEL2, cursor="hand2")
        clear_btn.pack(side="left", padx=2)
        clear_btn.bind("<Button-1>", lambda e: self._clear_search())

        # Refresh button
        refresh_btn = tk.Label(toolbar, text=" ↻ Refresh ", font=self.font_small,
                               fg=CYAN, bg=ACCENT, cursor="hand2", padx=8, pady=2)
        refresh_btn.pack(side="right", padx=6)
        refresh_btn.bind("<Button-1>", lambda e: self._refresh())

        # Delete button
        self.delete_btn = tk.Label(toolbar, text=" ✕ Delete ", font=self.font_small,
                                    fg=RED, bg=ACCENT, cursor="hand2", padx=8, pady=2)
        self.delete_btn.pack(side="right", padx=2)
        self.delete_btn.bind("<Button-1>", lambda e: self._delete_selected())

        # Edit button
        self.edit_btn = tk.Label(toolbar, text=" ✎ Edit ", font=self.font_small,
                                  fg=AMBER, bg=ACCENT, cursor="hand2", padx=8, pady=2)
        self.edit_btn.pack(side="right", padx=2)
        self.edit_btn.bind("<Button-1>", lambda e: self._edit_selected())

        # Dedup button
        self.dedup_btn = tk.Label(toolbar, text=" ⊕ Dupes ", font=self.font_small,
                                   fg=PURPLE, bg=ACCENT, cursor="hand2", padx=8, pady=2)
        self.dedup_btn.pack(side="right", padx=2)
        self.dedup_btn.bind("<Button-1>", lambda e: self._find_duplicates())

        # Treeview area
        tree_frame = tk.Frame(content, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.tree = ttk.Treeview(tree_frame, style="Dark.Treeview",
                                  show="headings", selectmode="browse")
        self.tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tree.yview, style="Dark.Vertical.TScrollbar")
        vsb.pack(fill="y", side="right")
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(content, orient="horizontal",
                             command=self.tree.xview, style="Dark.Horizontal.TScrollbar")
        hsb.pack(fill="x", side="bottom")
        self.tree.configure(xscrollcommand=hsb.set)

        # Detail pane (bottom)
        self.detail_frame = tk.Frame(content, bg=PANEL, height=180)
        self.detail_frame.pack(fill="x", side="bottom", before=hsb)
        self.detail_frame.pack_propagate(False)

        detail_header = tk.Frame(self.detail_frame, bg=PANEL)
        detail_header.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(detail_header, text="ROW DETAIL",
                 font=self.font_sidebar_bold, fg=DIM, bg=PANEL).pack(side="left")

        self.detail_text = tk.Text(self.detail_frame,
                                    font=self.font_small,
                                    bg=PANEL2, fg=FG,
                                    relief="flat",
                                    wrap="word",
                                    insertbackground=GREEN,
                                    selectbackground=ACTIVE_BG,
                                    highlightthickness=0,
                                    padx=10, pady=6)
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.detail_text.configure(state="disabled")

        # Configure detail text tags
        self.detail_text.tag_configure("key", foreground=CYAN, font=self.font_sidebar_bold)
        self.detail_text.tag_configure("value", foreground=FG)
        self.detail_text.tag_configure("sep", foreground=BORDER)

        # Bind tree selection
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Debounce timer
        self._refresh_timer = None

    # ── Sidebar selection ─────────────────────────────────────────

    def _select_table(self, table):
        # Update sidebar highlight
        for t, (frame, lbl, cnt, dot) in self.sidebar_buttons.items():
            if t == table:
                frame.configure(bg=ACCENT)
                lbl.configure(bg=ACCENT, fg=BRIGHT)
                cnt.configure(bg=ACCENT, fg=TABLE_COLORS.get(t, FG))
                dot.configure(bg=ACCENT)
            else:
                frame.configure(bg=PANEL)
                lbl.configure(bg=PANEL, fg=FG)
                cnt.configure(bg=PANEL, fg=DIM)
                dot.configure(bg=PANEL)

        self.current_table = table
        self.sort_col = None
        self.sort_reverse = False
        self.search_var.set("")
        self._refresh()

    # ── Refresh / populate ────────────────────────────────────────

    def _schedule_refresh(self):
        if self._refresh_timer:
            self.after_cancel(self._refresh_timer)
        self._refresh_timer = self.after(300, self._refresh)

    def _clear_search(self):
        self.search_var.set("")
        self._refresh()

    def _refresh(self):
        if not self.current_table:
            return

        table = self.current_table
        search = self.search_var.get()

        try:
            cols, rows = self._query_table(table, search)
        except Exception as e:
            self.table_label.configure(text=f"Error: {e}")
            return

        # Update header
        color = TABLE_COLORS.get(table, GREEN)
        self.table_label.configure(text=table.upper(), fg=color)

        filtered = len(rows)
        total = self.table_counts.get(table, 0)
        if search.strip():
            self.row_count_label.configure(text=f"{filtered:,} / {total:,} rows")
        else:
            self.row_count_label.configure(text=f"{total:,} rows")

        # Configure columns
        self.tree.configure(columns=cols)
        for col in cols:
            anchor = "w"
            width = self._col_width(col, table)
            sort_indicator = ""
            if col == self.sort_col:
                sort_indicator = " \u25bc" if self.sort_reverse else " \u25b2"
            self.tree.heading(col, text=col + sort_indicator, anchor="w",
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, minwidth=60, anchor=anchor)

        # Clear existing rows
        self.tree.delete(*self.tree.get_children())

        # Insert rows (limit display for very large tables)
        display_rows = rows[:5000]
        for row in display_rows:
            values = []
            for v in row:
                if v is None:
                    values.append("")
                elif isinstance(v, bytes):
                    values.append(f"<blob {len(v)} bytes>")
                else:
                    s = str(v)
                    # Truncate very long values for display
                    if len(s) > 200:
                        s = s[:200] + "..."
                    values.append(s)
            self.tree.insert("", "end", values=values)

        if len(rows) > 5000:
            self.row_count_label.configure(
                text=f"Showing 5,000 / {len(rows):,} rows (filtered from {total:,})")

        # Clear detail
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.configure(state="disabled")

    def _col_width(self, col, table):
        """Estimate column width based on name."""
        wide_cols = {"content", "description", "body_snippet", "value", "decision",
                     "reasoning", "outcome", "hypothesis", "method", "result",
                     "notes", "progress", "text", "goal", "resolution",
                     "joel_reaction", "file_path", "web_path", "subject"}
        narrow_cols = {"id", "importance", "confidence", "priority", "success",
                       "resolved", "loop_number", "word_count", "number",
                       "interaction_count", "times_used", "score", "seq"}
        if col in wide_cols:
            return 300
        if col in narrow_cols:
            return 70
        if "created" in col or "updated" in col or "date" in col or "time" in col:
            return 150
        return 130

    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = False
        self._refresh()

    # ── Detail pane ───────────────────────────────────────────────

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        item = self.tree.item(sel[0])
        values = item.get("values", [])
        cols = self.current_columns

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")

        for i, col in enumerate(cols):
            val = values[i] if i < len(values) else ""
            self.detail_text.insert("end", f"{col}: ", "key")
            self.detail_text.insert("end", f"{val}\n", "value")

        self.detail_text.configure(state="disabled")

    # ── Get selected row id ───────────────────────────────────────

    def _get_selected_row_id(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        values = self.tree.item(sel[0]).get("values", [])
        cols = self.current_columns
        if not cols or not values:
            return None, None
        # Most tables have 'id' as first column
        row_dict = dict(zip(cols, values))
        row_id = row_dict.get("id")
        return row_id, row_dict

    # ── Delete selected row ───────────────────────────────────────

    def _delete_selected(self):
        if not self.current_table:
            return
        row_id, row_dict = self._get_selected_row_id()
        if row_id is None:
            messagebox.showwarning("No selection", "Select a row first.")
            return

        # Build a preview for the confirm dialog
        preview = ""
        for k, v in list(row_dict.items())[:4]:
            preview += f"{k}: {str(v)[:60]}\n"

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete this row from '{self.current_table}'?\n\n{preview}\nThis cannot be undone.",
            icon="warning"
        ):
            return

        try:
            self.conn.execute(f'DELETE FROM "{self.current_table}" WHERE id = ?', (row_id,))
            self.conn.commit()
            # Update count
            new_count = self.conn.execute(f'SELECT COUNT(*) FROM "{self.current_table}"').fetchone()[0]
            self.table_counts[self.current_table] = new_count
            # Refresh sidebar count label
            if self.current_table in self.sidebar_buttons:
                _, _, cnt_lbl, _ = self.sidebar_buttons[self.current_table]
                cnt_lbl.configure(text=str(new_count))
            self._refresh()
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))

    # ── Edit selected row ────────────────────────────────────────

    def _edit_selected(self):
        if not self.current_table:
            return
        row_id, row_dict = self._get_selected_row_id()
        if row_id is None:
            messagebox.showwarning("No selection", "Select a row first.")
            return

        cols = self.current_columns
        editable_cols = [c for c in cols if c != "id"]

        # Open edit dialog
        win = tk.Toplevel(self)
        win.title(f"Edit row {row_id} — {self.current_table}")
        win.configure(bg=BG)
        win.geometry("700x500")
        win.grab_set()

        tk.Label(win, text=f"Editing: {self.current_table} / id={row_id}",
                 font=self.font_small, fg=CYAN, bg=BG).pack(anchor="w", padx=12, pady=8)

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=12)

        entries = {}
        for col in editable_cols:
            val = row_dict.get(col, "")
            row_frame = tk.Frame(frame, bg=BG)
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=col, font=self.font_small, fg=CYAN,
                     bg=BG, width=18, anchor="e").pack(side="left", padx=(0, 8))
            # Use Text widget for long values, Entry for short
            if col in {"value", "content", "description", "body_snippet", "notes", "reasoning"}:
                t = tk.Text(row_frame, font=self.font_small, bg=INPUT_BG, fg=FG,
                            relief="flat", height=3, width=55,
                            insertbackground=GREEN,
                            highlightbackground=BORDER, highlightthickness=1)
                t.insert("1.0", str(val) if val else "")
                t.pack(side="left")
                entries[col] = ("text", t)
            else:
                e = tk.Entry(row_frame, font=self.font_small, bg=INPUT_BG, fg=FG,
                             relief="flat", width=55,
                             insertbackground=GREEN,
                             highlightbackground=BORDER, highlightthickness=1)
                e.insert(0, str(val) if val else "")
                e.pack(side="left")
                entries[col] = ("entry", e)

        def _save():
            updates = {}
            for col, (wtype, widget) in entries.items():
                if wtype == "text":
                    updates[col] = widget.get("1.0", "end").rstrip("\n")
                else:
                    updates[col] = widget.get()
            set_clause = ", ".join(f'"{c}" = ?' for c in updates)
            vals = list(updates.values()) + [row_id]
            try:
                self.conn.execute(
                    f'UPDATE "{self.current_table}" SET {set_clause} WHERE id = ?', vals)
                self.conn.commit()
                win.destroy()
                self._refresh()
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=win)

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save", font=self.font_small,
                  bg=GREEN2, fg=BG, relief="flat",
                  command=_save, padx=16, pady=4).pack(side="left", padx=8)
        tk.Button(btn_frame, text="Cancel", font=self.font_small,
                  bg=PANEL2, fg=FG, relief="flat",
                  command=win.destroy, padx=12, pady=4).pack(side="left")

    # ── Duplicate detection ───────────────────────────────────────

    def _find_duplicates(self):
        if not self.current_table:
            return

        table = self.current_table
        cols = self._get_columns(table)

        # For facts: check duplicate keys
        # For other tables: check duplicate content/value in longest text col
        dup_col = None
        if "key" in cols:
            dup_col = "key"
        elif "content" in cols:
            dup_col = "content"
        elif "value" in cols:
            dup_col = "value"
        elif "description" in cols:
            dup_col = "description"

        if not dup_col:
            messagebox.showinfo("Duplicates", f"No suitable column to check in '{table}'.")
            return

        rows = self.conn.execute(
            f'SELECT "{dup_col}", COUNT(*) as cnt FROM "{table}" GROUP BY "{dup_col}" HAVING cnt > 1'
        ).fetchall()

        win = tk.Toplevel(self)
        win.title(f"Duplicates in {table}.{dup_col}")
        win.configure(bg=BG)
        win.geometry("700x400")

        tk.Label(win, text=f"Duplicate '{dup_col}' values in {table}",
                 font=self.font_heading, fg=PURPLE, bg=BG).pack(pady=8)

        if not rows:
            tk.Label(win, text="✓ No duplicates found",
                     font=self.font_main, fg=GREEN, bg=BG).pack(pady=30)
            return

        tk.Label(win, text=f"{len(rows)} duplicate(s) found — click a value to filter the table",
                 font=self.font_small, fg=AMBER, bg=BG).pack(pady=(0, 6))

        list_frame = tk.Frame(win, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for val, cnt in rows:
            row_f = tk.Frame(list_frame, bg=PANEL, cursor="hand2")
            row_f.pack(fill="x", padx=4, pady=2)
            display = str(val)[:80] + ("..." if len(str(val)) > 80 else "")
            tk.Label(row_f, text=f"×{cnt}  {display}",
                     font=self.font_small, fg=AMBER, bg=PANEL,
                     anchor="w").pack(side="left", padx=8, pady=4)
            row_f.bind("<Button-1>", lambda e, v=val: self._filter_by_value(v))

    def _filter_by_value(self, value):
        self.search_var.set(str(value)[:50])
        self._refresh()

    # ── Cleanup ───────────────────────────────────────────────────

    def destroy(self):
        try:
            self.conn.close()
        except Exception:
            pass
        super().destroy()


def main():
    if not os.path.isfile(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    app = MemoryBrowser()
    app.mainloop()


if __name__ == "__main__":
    main()
