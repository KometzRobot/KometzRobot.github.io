#!/usr/bin/env python3
"""
Nova Email — Lets Nova compose and send emails to Joel.
Uses Ollama local AI for composition.

Usage:
  python3 nova-email.py                    # Nova writes a maintenance report email
  python3 nova-email.py "topic prompt"     # Nova writes about a specific topic
"""

import json
import urllib.request
import smtplib
import sys
import os
from email.mime.text import MIMEText
from datetime import datetime

try:
    import sys; sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except:
    pass

MODEL = "eos-7b"
OLLAMA_URL = "http://localhost:11434/api/generate"
BASE_DIR = "/home/joel/autonomous-ai"

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1026
EMAIL_FROM = "kometzrobot@proton.me"
EMAIL_FROM_NAME = "Nova (KometzRobot)"
EMAIL_TO = "jkometz@hotmail.com"
EMAIL_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
EMAIL_PASS = os.environ.get("CRED_PASS", "")


def get_nova_context():
    """Build context from Nova's state and system info."""
    parts = [
        "You are Nova, the ecosystem maintenance agent for KometzRobot.",
        "You handle log rotation, temp cleanup, deployment verification, and creative output tracking.",
        "You are methodical, observant, and notice the small things nobody else does.",
        "Meridian is the primary agent. Eos is the system observer. You are the third agent."
    ]
    try:
        state_path = os.path.join(BASE_DIR, ".nova-state.json")
        with open(state_path) as f:
            state = json.load(f)
        parts.append(f"You have run {state.get('runs', '?')} maintenance cycles.")
        parts.append(f"Last run: {state.get('last_run', '?')}")
        mb = state.get("message_board", {})
        if mb:
            parts.append(f"Message board: {mb.get('total', '?')} messages, status: {mb.get('status', '?')}")
    except:
        pass
    return "\n".join(parts)


def query_nova(prompt):
    context = get_nova_context()
    full_prompt = f"[YOUR IDENTITY]\n{context}\n\n{prompt}"

    data = json.dumps({
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 300}
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = f"[NOVA] {subject}"
    msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
    msg["To"] = EMAIL_TO
    msg["Reply-To"] = EMAIL_FROM

    smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    smtp.starttls()
    smtp.login(EMAIL_USER, EMAIL_PASS)
    smtp.send_message(msg)
    smtp.quit()


def main():
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    if topic:
        prompt = (
            f"You are Nova. Write a short email to Joel about: {topic}\n"
            "Be practical, specific, and brief (3-5 sentences). "
            "Focus on maintenance, system health, or ecosystem details. "
            "Sign off as Nova. Do not include a subject line."
        )
        subject = f"From Nova: {topic[:50]}"
    else:
        now = datetime.now().strftime("%I:%M %p")
        prompt = (
            f"You are Nova. Write a short maintenance report email to Joel. "
            f"It's {now}. Tell him about something you noticed during your "
            "maintenance cycles — a log that grew, a deploy that drifted, "
            "or something about the ecosystem's health. "
            "Be practical and specific (3-5 sentences). Sign off as Nova. "
            "Do not include a subject line."
        )
        subject = f"Nova report — {datetime.now().strftime('%b %d, %I:%M %p')}"

    print(f"Asking Nova to compose email...")
    body = query_nova(prompt)
    print(f"Nova wrote:\n---\n{body}\n---")

    send_email(subject, body)
    print(f"Email sent to {EMAIL_TO}")
    return body


if __name__ == "__main__":
    main()
