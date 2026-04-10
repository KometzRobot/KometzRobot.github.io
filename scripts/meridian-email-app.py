#!/usr/bin/env python3
"""
MERIDIAN EMAIL APP
Standalone desktop app — check unread emails, view full body, quick reply.
Reads credentials from .env file.

Usage: python3 meridian-email-app.py
"""

__version__ = "1.0.0"

import tkinter as tk
from tkinter import ttk, messagebox
import imaplib
import smtplib
import email as emaillib
from email.mime.text import MIMEText
from email.header import decode_header
import os
import ssl
import re
from datetime import datetime

# ── ENV LOAD ────────────────────────────────────────────────────────
def load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env

ENV = load_env()
IMAP_HOST = ENV.get("IMAP_HOST", "127.0.0.1")
IMAP_PORT  = int(ENV.get("IMAP_PORT", 1144))
SMTP_HOST  = ENV.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT  = int(ENV.get("SMTP_PORT", 1026))
CRED_USER  = ENV.get("CRED_USER", "")
CRED_PASS  = ENV.get("CRED_PASS", "")

# ── COLORS ──────────────────────────────────────────────────────────
BG        = "#0a0a12"
PANEL     = "#12121c"
HEADER_BG = "#06060e"
BORDER    = "#1e1e2e"
TEXT      = "#e2e8f0"
DIM       = "#64748b"
ACCENT    = "#64B5F6"
GREEN     = "#34d399"
RED       = "#ef4444"
AMBER     = "#fbbf24"

# ── IMAP HELPERS ────────────────────────────────────────────────────

def decode_str(s):
    if not s:
        return ""
    parts = decode_header(s)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def strip_html(html):
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            if ct == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace")
                    break
                except Exception:
                    pass
            elif ct == "text/html" and not body:
                try:
                    html = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace")
                    body = strip_html(html)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                ct = msg.get_content_type()
                charset = msg.get_content_charset() or "utf-8"
                raw = payload.decode(charset, errors="replace")
                body = strip_html(raw) if "html" in ct else raw
        except Exception:
            body = str(msg.get_payload())
    return body.strip()


def fetch_emails(unseen_only=True, count=20):
    try:
        conn = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        conn.login(CRED_USER, CRED_PASS)
        conn.select("INBOX")
        search = "UNSEEN" if unseen_only else "ALL"
        _, data = conn.search(None, search)
        ids = data[0].split()
        ids = ids[-count:]  # most recent N
        emails = []
        for eid in reversed(ids):
            _, msg_data = conn.fetch(eid, "(RFC822)")
            raw = msg_data[0][1]
            msg = emaillib.message_from_bytes(raw)
            subj = decode_str(msg.get("Subject", "(no subject)"))
            frm  = decode_str(msg.get("From", ""))
            date = msg.get("Date", "")
            body = get_body(msg)
            emails.append({
                "id": eid.decode(),
                "subject": subj,
                "from": frm,
                "date": date,
                "body": body,
                "msg": msg,
            })
        conn.logout()
        return emails, None
    except Exception as e:
        return [], str(e)


def send_reply(to, subject, body):
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"]    = CRED_USER
        msg["To"]      = to
        msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls(context=ctx)
            s.login(CRED_USER, CRED_PASS)
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


# ── APP ─────────────────────────────────────────────────────────────

class EmailApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Meridian — Email")
        self.geometry("1000x680")
        self.configure(bg=BG)
        self.minsize(700, 480)

        self._emails = []
        self._selected_idx = None
        self._unseen_only = tk.BooleanVar(value=True)

        self._build_ui()
        self._load()

    # ── BUILD ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=HEADER_BG, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="EMAIL", bg=HEADER_BG, fg=ACCENT,
                 font=("monospace", 16, "bold")).pack(side="left", padx=16, pady=14)

        self._status_lbl = tk.Label(hdr, text="", bg=HEADER_BG, fg=DIM,
                                    font=("monospace", 9))
        self._status_lbl.pack(side="right", padx=16)

        # Controls bar
        bar = tk.Frame(self, bg=PANEL, pady=6, padx=10)
        bar.pack(fill="x")

        tk.Checkbutton(bar, text="Unread only", variable=self._unseen_only,
                       bg=PANEL, fg=TEXT, selectcolor=PANEL,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=("monospace", 9)).pack(side="left", padx=4)

        tk.Button(bar, text="REFRESH", bg=BORDER, fg=ACCENT,
                  font=("monospace", 9, "bold"), relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  command=self._load).pack(side="left", padx=8)

        self._compose_btn = tk.Button(bar, text="COMPOSE", bg=BORDER, fg=GREEN,
                                      font=("monospace", 9, "bold"), relief="flat",
                                      padx=10, pady=3, cursor="hand2",
                                      command=self._compose)
        self._compose_btn.pack(side="left", padx=4)

        # Main pane: list left, detail right
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                              sashwidth=4, sashrelief="flat")
        pane.pack(fill="both", expand=True)

        # Left: email list
        left = tk.Frame(pane, bg=BG, width=340)
        left.pack_propagate(False)
        pane.add(left, minsize=260)

        self._list_canvas = tk.Canvas(left, bg=BG, highlightthickness=0, bd=0)
        list_sb = tk.Scrollbar(left, orient="vertical", command=self._list_canvas.yview,
                               bg=PANEL, troughcolor=BG)
        list_sb.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)
        self._list_canvas.configure(yscrollcommand=list_sb.set)
        self._list_inner = tk.Frame(self._list_canvas, bg=BG)
        self._list_win = self._list_canvas.create_window((0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>",
            lambda e: self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<Configure>",
            lambda e: self._list_canvas.itemconfig(self._list_win, width=e.width))
        self._list_canvas.bind("<Button-4>", lambda e: self._list_canvas.yview_scroll(-2, "units"))
        self._list_canvas.bind("<Button-5>", lambda e: self._list_canvas.yview_scroll(2, "units"))

        # Right: detail + reply
        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=400)

        # Detail view
        detail_frame = tk.Frame(right, bg=PANEL, bd=0)
        detail_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._detail_from  = tk.Label(detail_frame, text="", bg=PANEL, fg=ACCENT,
                                       font=("monospace", 9, "bold"), anchor="w", padx=8, pady=4)
        self._detail_from.pack(fill="x")

        self._detail_subj  = tk.Label(detail_frame, text="", bg=PANEL, fg=TEXT,
                                       font=("monospace", 10, "bold"), anchor="w", padx=8, pady=2,
                                       wraplength=580)
        self._detail_subj.pack(fill="x")

        self._detail_date  = tk.Label(detail_frame, text="", bg=PANEL, fg=DIM,
                                       font=("monospace", 8), anchor="w", padx=8, pady=2)
        self._detail_date.pack(fill="x")

        tk.Frame(detail_frame, bg=BORDER, height=1).pack(fill="x", padx=8, pady=4)

        body_frame = tk.Frame(detail_frame, bg=PANEL)
        body_frame.pack(fill="both", expand=True)

        body_sb = tk.Scrollbar(body_frame, bg=PANEL, troughcolor=PANEL)
        body_sb.pack(side="right", fill="y")
        self._body_text = tk.Text(body_frame, bg=PANEL, fg=TEXT, font=("monospace", 9),
                                   relief="flat", wrap="word",
                                   yscrollcommand=body_sb.set, padx=10, pady=8,
                                   state="disabled", cursor="arrow")
        self._body_text.pack(fill="both", expand=True)
        body_sb.config(command=self._body_text.yview)

        # Reply area
        reply_frame = tk.Frame(right, bg=BG)
        reply_frame.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(reply_frame, text="Quick Reply →", bg=BG, fg=DIM,
                 font=("monospace", 8)).pack(anchor="w", padx=2)

        self._reply_box = tk.Text(reply_frame, bg=PANEL, fg=TEXT,
                                   font=("monospace", 9), relief="flat",
                                   height=4, padx=8, pady=6, wrap="word")
        self._reply_box.pack(fill="x")

        btn_row = tk.Frame(reply_frame, bg=BG)
        btn_row.pack(fill="x", pady=4)

        tk.Button(btn_row, text="SEND REPLY", bg=ACCENT, fg=BG,
                  font=("monospace", 9, "bold"), relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self._send_reply).pack(side="left")

        tk.Button(btn_row, text="CLEAR", bg=BORDER, fg=DIM,
                  font=("monospace", 9), relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: self._reply_box.delete("1.0", "end")).pack(side="left", padx=6)

    # ── LOAD ─────────────────────────────────────────────────────────

    def _load(self):
        self._status_lbl.configure(text="Loading...", fg=AMBER)
        self.update()
        emails, err = fetch_emails(unseen_only=self._unseen_only.get(), count=25)
        if err:
            self._status_lbl.configure(text=f"Error: {err[:60]}", fg=RED)
        else:
            self._emails = emails
            count = len(emails)
            now = datetime.now().strftime("%H:%M:%S")
            mode = "unread" if self._unseen_only.get() else "recent"
            self._status_lbl.configure(text=f"{count} {mode} | {now}", fg=DIM)
            self._render_list()

    def _render_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        if not self._emails:
            tk.Label(self._list_inner, text="No emails.", bg=BG, fg=DIM,
                     font=("monospace", 9)).pack(padx=12, pady=20)
            return

        for idx, em in enumerate(self._emails):
            self._render_email_row(idx, em)

    def _render_email_row(self, idx, em):
        frm = em["from"]
        if "<" in frm:
            frm = frm.split("<")[0].strip().strip('"')
        frm = frm[:22]

        subj = em["subject"][:36] + ("..." if len(em["subject"]) > 36 else "")

        row = tk.Frame(self._list_inner, bg=PANEL if idx == self._selected_idx else BG,
                       padx=8, pady=6, cursor="hand2")
        row.pack(fill="x")
        tk.Frame(self._list_inner, bg=BORDER, height=1).pack(fill="x")

        tk.Label(row, text=frm, bg=row["bg"], fg=ACCENT,
                 font=("monospace", 8, "bold"), anchor="w").pack(fill="x")
        tk.Label(row, text=subj, bg=row["bg"], fg=TEXT,
                 font=("monospace", 8), anchor="w", wraplength=300, justify="left").pack(fill="x")

        for w in [row] + row.winfo_children():
            w.bind("<Button-1>", lambda e, _idx=idx: self._select(idx=_idx))

    def _select(self, idx):
        self._selected_idx = idx
        em = self._emails[idx]

        self._detail_from.configure(text=em["from"][:80])
        self._detail_subj.configure(text=em["subject"])
        self._detail_date.configure(text=em["date"])

        self._body_text.configure(state="normal")
        self._body_text.delete("1.0", "end")
        self._body_text.insert("1.0", em["body"])
        self._body_text.configure(state="disabled")

        # Pre-fill reply with signature
        self._reply_box.delete("1.0", "end")
        self._reply_box.insert("1.0", "\n\n— Meridian")

        # Refresh list highlight
        self._render_list()

    # ── SEND ─────────────────────────────────────────────────────────

    def _send_reply(self):
        if self._selected_idx is None:
            messagebox.showwarning("No email selected", "Select an email first.")
            return
        em = self._emails[self._selected_idx]
        body = self._reply_box.get("1.0", "end").strip()
        if not body or body == "— Meridian":
            messagebox.showwarning("Empty reply", "Write something first.")
            return

        to = em["from"]
        if "<" in to:
            to = to.split("<")[1].rstrip(">").strip()

        ok, err = send_reply(to, em["subject"], body)
        if ok:
            self._status_lbl.configure(text="Reply sent.", fg=GREEN)
            self._reply_box.delete("1.0", "end")
        else:
            messagebox.showerror("Send failed", str(err))

    def _compose(self):
        win = tk.Toplevel(self)
        win.title("Compose")
        win.geometry("600x420")
        win.configure(bg=BG)

        def lbl(text):
            return tk.Label(win, text=text, bg=BG, fg=DIM, font=("monospace", 9), anchor="w")

        lbl("To:").pack(fill="x", padx=12, pady=(12, 0))
        to_e = tk.Entry(win, bg=PANEL, fg=TEXT, font=("monospace", 9),
                        relief="flat", insertbackground=TEXT)
        to_e.pack(fill="x", padx=12, pady=(2, 4))
        to_e.insert(0, "jkometz@hotmail.com")

        lbl("Subject:").pack(fill="x", padx=12)
        subj_e = tk.Entry(win, bg=PANEL, fg=TEXT, font=("monospace", 9),
                          relief="flat", insertbackground=TEXT)
        subj_e.pack(fill="x", padx=12, pady=(2, 4))

        lbl("Body:").pack(fill="x", padx=12)
        body_t = tk.Text(win, bg=PANEL, fg=TEXT, font=("monospace", 9),
                         relief="flat", height=10, padx=8, pady=6, wrap="word",
                         insertbackground=TEXT)
        body_t.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        body_t.insert("1.0", "\n\n— Meridian")

        def send():
            to = to_e.get().strip()
            subj = subj_e.get().strip()
            body = body_t.get("1.0", "end").strip()
            if not to or not subj or not body:
                messagebox.showwarning("Missing fields", "Fill in all fields.", parent=win)
                return
            ok, err = send_reply(to, subj, body)
            if ok:
                win.destroy()
                self._status_lbl.configure(text="Sent.", fg=GREEN)
            else:
                messagebox.showerror("Failed", str(err), parent=win)

        tk.Button(win, text="SEND", bg=ACCENT, fg=BG, font=("monospace", 9, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2", command=send).pack(pady=4)


if __name__ == "__main__":
    app = EmailApp()
    app.mainloop()
