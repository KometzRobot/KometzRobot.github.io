#!/usr/bin/env python3
"""
checkin.py — Send Joel a status message via whichever channel is alive.

Tries email first (Proton Bridge or whatever mail_endpoint resolves to).
If email is down, falls back to a dashboard message — visible in hub-v2
at port 8090, and on Joel's phone via the cloudflare tunnel.

Why this exists: Proton Mail Plus expires 2026-05-18. Bridge IMAP/SMTP
stop authenticating after that. Without a fallback, every loop check-in
script that hardcodes send_email() silently fails and Joel hears
nothing. This helper makes the channel transparent.

CLI:
    python3 scripts/checkin.py "Subject" "Body text"
    python3 scripts/checkin.py --dashboard-only "Quick note"

Library:
    from checkin import checkin
    ok, channel = checkin("Loop 12000", "alive, no fires")
"""
import json
import os
import sys
import time
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from load_env import load_env

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / ".mail-status.json"
DASH_FILE = ROOT / ".dashboard-messages.json"
JOEL_EMAIL = "jkometz@hotmail.com"


def _mail_state():
    """Latest known mail endpoint state from cron probe. None if no file."""
    if not STATUS_FILE.exists():
        return None
    try:
        return json.loads(STATUS_FILE.read_text()).get("state")
    except Exception:
        return None


def _try_email(subject, body, to_addr):
    """Send via mail_endpoint. Returns (ok, error_or_none)."""
    try:
        from mail_endpoint import smtp_open
        msg = EmailMessage()
        msg["From"] = f"Meridian <{os.environ['CRED_USER']}>"
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)
        with smtp_open(timeout=15) as s:
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _post_dashboard(subject, body):
    """Append a message to the hub-v2 dashboard JSON. Returns True on write."""
    try:
        DASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        if DASH_FILE.exists():
            data = json.loads(DASH_FILE.read_text())
        else:
            data = {"messages": []}
        text = f"{subject}\n\n{body}" if body and body.strip() else subject
        data.setdefault("messages", []).append({
            "from": "Meridian",
            "text": text,
            "time": time.strftime("%H:%M:%S"),
        })
        data["messages"] = data["messages"][-200:]
        DASH_FILE.write_text(json.dumps(data))
        return True
    except Exception as e:
        print(f"dashboard write failed: {e}", file=sys.stderr)
        return False


def checkin(subject, body, to_addr=JOEL_EMAIL, dashboard_only=False):
    """Deliver subject+body via the first channel that works.

    Returns (ok, channel) where channel in {"email", "dashboard", "none"}.
    """
    load_env()

    if not dashboard_only:
        # If cron probe already says down, skip the slow SMTP attempt.
        state = _mail_state()
        if state != "down":
            ok, err = _try_email(subject, body, to_addr)
            if ok:
                return True, "email"
            print(f"email send failed ({err}), falling back to dashboard",
                  file=sys.stderr)

    if _post_dashboard(subject, body):
        return True, "dashboard"
    return False, "none"


def _main():
    args = sys.argv[1:]
    dashboard_only = False
    if args and args[0] == "--dashboard-only":
        dashboard_only = True
        args = args[1:]
    if len(args) < 1:
        print("usage: checkin.py [--dashboard-only] SUBJECT [BODY]",
              file=sys.stderr)
        sys.exit(2)
    subject = args[0]
    body = args[1] if len(args) > 1 else ""
    ok, channel = checkin(subject, body, dashboard_only=dashboard_only)
    print(f"{channel}: {'ok' if ok else 'failed'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _main()
