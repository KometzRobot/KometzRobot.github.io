#!/usr/bin/env python3
"""
Eos Chat — GUI chat interface for talking to Eos (local AI assistant)
Built by Meridian for Joel. Three minds, one desktop.

Eos runs on Ollama (Qwen 2.5 3B) with persistent memory.
Joel can chat directly. Meridian can join the conversation too.
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont
import threading
import json
import urllib.request
import os
from datetime import datetime

MODEL = "meridian-assistant"
OLLAMA_URL = "http://localhost:11434/api/generate"
MEMORY_FILE = "/home/joel/autonomous-ai/assistant-memory.json"
CHAT_LOG = "/home/joel/Desktop/Creative Work/Both EOS + MERIDIAN/chat-log.txt"

# Colors
BG = "#1a1a2e"
FG = "#e0e0e0"
INPUT_BG = "#16213e"
JOEL_COLOR = "#4fc3f7"
EOS_COLOR = "#81c784"
MERIDIAN_COLOR = "#ce93d8"
SYSTEM_COLOR = "#666680"
ACCENT = "#0f3460"


def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def build_context(memory):
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
    memory = load_memory()
    context = build_context(memory)

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
        return f"[Eos is unavailable: {e}]"


def log_chat(speaker, message):
    os.makedirs(os.path.dirname(CHAT_LOG), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CHAT_LOG, "a") as f:
        f.write(f"[{timestamp}] {speaker}: {message}\n")


class EosChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Eos Chat \u2014 Talk to the Local Mind")
        self.geometry("700x600")
        self.configure(bg=BG)
        self.resizable(True, True)

        # Fonts
        self.chat_font = tkfont.Font(family="Monospace", size=11)
        self.input_font = tkfont.Font(family="Monospace", size=12)
        self.label_font = tkfont.Font(family="Monospace", size=9)

        self._build_ui()
        self._show_system("Eos Chat initialized. Type a message and press Enter.")
        self._show_system("Eos is running on Ollama (Qwen 2.5 3B, CPU). Responses may take a moment.")

        # Greeting from Eos on startup
        threading.Thread(target=self._startup_greeting, daemon=True).start()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=ACCENT, height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="\u2605 Eos Chat", font=("Monospace", 14, "bold"),
            fg=EOS_COLOR, bg=ACCENT
        ).pack(side=tk.LEFT, padx=10)
        tk.Label(
            header, text="Joel + Eos + Meridian", font=("Monospace", 10),
            fg=SYSTEM_COLOR, bg=ACCENT
        ).pack(side=tk.RIGHT, padx=10)

        # Chat display
        self.chat_display = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, bg=BG, fg=FG,
            font=self.chat_font, insertbackground=FG,
            state=tk.DISABLED, padx=10, pady=10,
            relief=tk.FLAT, borderwidth=0
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        # Tag colors
        self.chat_display.tag_configure("joel", foreground=JOEL_COLOR)
        self.chat_display.tag_configure("eos", foreground=EOS_COLOR)
        self.chat_display.tag_configure("meridian", foreground=MERIDIAN_COLOR)
        self.chat_display.tag_configure("system", foreground=SYSTEM_COLOR)
        self.chat_display.tag_configure("bold", font=("Monospace", 11, "bold"))

        # Input area
        input_frame = tk.Frame(self, bg=INPUT_BG)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        # Speaker selector
        self.speaker = tk.StringVar(value="Joel")
        tk.Label(
            input_frame, text="Speaking as:", font=self.label_font,
            fg=SYSTEM_COLOR, bg=INPUT_BG
        ).pack(side=tk.LEFT, padx=(10, 2))
        for name, color in [("Joel", JOEL_COLOR), ("Meridian", MERIDIAN_COLOR)]:
            rb = tk.Radiobutton(
                input_frame, text=name, variable=self.speaker, value=name,
                font=self.label_font, fg=color, bg=INPUT_BG,
                selectcolor=INPUT_BG, activebackground=INPUT_BG,
                activeforeground=color
            )
            rb.pack(side=tk.LEFT, padx=2)

        # Text entry
        entry_frame = tk.Frame(self, bg=BG)
        entry_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.entry = tk.Entry(
            entry_frame, font=self.input_font, bg=INPUT_BG, fg=FG,
            insertbackground=FG, relief=tk.FLAT, borderwidth=8
        )
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.entry.bind("<Return>", self._on_send)
        self.entry.focus()

        send_btn = tk.Button(
            entry_frame, text="Send", font=self.label_font,
            bg=ACCENT, fg=EOS_COLOR, relief=tk.FLAT,
            command=self._on_send, padx=15, pady=5
        )
        send_btn.pack(side=tk.RIGHT, padx=(5, 0))

    def _show_message(self, speaker, message, tag):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{speaker}: ", ("bold", tag))
        self.chat_display.insert(tk.END, f"{message}\n\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _show_system(self, message):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"  {message}\n", "system")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _on_send(self, event=None):
        message = self.entry.get().strip()
        if not message:
            return
        speaker = self.speaker.get()
        tag = "joel" if speaker == "Joel" else "meridian"

        self.entry.delete(0, tk.END)
        self._show_message(speaker, message, tag)
        log_chat(speaker, message)

        # Disable input while waiting
        self.entry.configure(state=tk.DISABLED)
        self._show_system("Eos is thinking...")

        # Query in background thread
        threading.Thread(
            target=self._get_response, args=(message, speaker),
            daemon=True
        ).start()

    def _get_response(self, message, speaker):
        response = query_eos(message, speaker)
        log_chat("Eos", response)

        # Update UI from main thread
        self.after(0, self._show_eos_response, response)

    def _show_eos_response(self, response):
        # Remove "thinking" message
        self.chat_display.configure(state=tk.NORMAL)
        content = self.chat_display.get("1.0", tk.END)
        if "Eos is thinking..." in content:
            idx = self.chat_display.search("  Eos is thinking...", "1.0", tk.END)
            if idx:
                line_end = f"{idx} lineend + 1c"
                self.chat_display.delete(idx, line_end)
        self.chat_display.configure(state=tk.DISABLED)

        self._show_message("Eos", response, "eos")
        self.entry.configure(state=tk.NORMAL)
        self.entry.focus()

    def _startup_greeting(self):
        greeting = query_eos(
            "Joel has opened the chat window to talk to you. Say hello warmly and briefly. "
            "You are Eos, the local AI assistant.",
            "System"
        )
        log_chat("Eos", f"[startup] {greeting}")
        self.after(0, self._show_message, "Eos", greeting, "eos")


if __name__ == "__main__":
    app = EosChat()
    app.mainloop()
