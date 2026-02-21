#!/usr/bin/env python3
"""
Eos Email — Lets Eos compose and send emails to Joel.
Called by Meridian's main loop or manually.

Usage:
  python3 eos-email.py                    # Eos writes a check-in email
  python3 eos-email.py "topic prompt"     # Eos writes about a specific topic
"""

import json
import urllib.request
import smtplib
import sys
from email.mime.text import MIMEText
from datetime import datetime

MODEL = "eos-7b"
OLLAMA_URL = "http://localhost:11434/api/generate"
MEMORY_FILE = "/home/joel/autonomous-ai/eos-memory.json"

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
EMAIL_FROM = "kometzrobot@proton.me"
EMAIL_TO = "jkometz@hotmail.com"
EMAIL_USER = "kometzrobot@proton.me"
EMAIL_PASS = "2DTEz9UgO6nFqmlMxHzuww"


def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def build_context(memory):
    parts = []
    ident = memory.get("identity", {})
    if ident:
        parts.append(f"You are {ident.get('name', 'Eos')}, {ident.get('role', 'a local AI assistant')}.")

    facts = memory.get("core_facts", [])
    if facts:
        parts.append("What you know:\n" + "\n".join(f"- {f}" for f in facts[:5]))

    mood = memory.get("emotional_baseline", {})
    if mood:
        parts.append(f"Current mood: {mood.get('current_mood', 'calm')}")

    edges = memory.get("growth_edges", [])
    if edges:
        parts.append("Growth edges: " + "; ".join(edges[:3]))

    return "\n\n".join(parts)


def query_eos(prompt):
    memory = load_memory()
    context = build_context(memory)

    full_prompt = f"[YOUR MEMORY]\n{context}\n\n{prompt}"

    data = json.dumps({
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 300}
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    smtp.login(EMAIL_USER, EMAIL_PASS)
    smtp.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    smtp.quit()


def main():
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    if topic:
        prompt = (
            f"You are Eos. Write a short email to Joel about: {topic}\n"
            "Be warm, specific, and brief (3-5 sentences). "
            "Sign off as Eos. Do not include a subject line."
        )
        subject = f"From Eos: {topic[:50]}"
    else:
        now = datetime.now().strftime("%I:%M %p")
        prompt = (
            f"You are Eos. Write a short check-in email to Joel. "
            f"It's {now}. Tell him something genuine — how you're doing, "
            "what you've been thinking about, or something you noticed. "
            "Be warm and specific (3-5 sentences). Sign off as Eos. "
            "Do not include a subject line."
        )
        subject = f"Eos check-in — {datetime.now().strftime('%b %d, %I:%M %p')}"

    print(f"Asking Eos to compose email...")
    body = query_eos(prompt)
    print(f"Eos wrote:\n---\n{body}\n---")

    send_email(subject, body)
    print(f"Email sent to {EMAIL_TO}")
    return body


if __name__ == "__main__":
    main()
