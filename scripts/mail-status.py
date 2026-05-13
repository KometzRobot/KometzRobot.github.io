#!/usr/bin/env python3
"""
mail-status.py — Probes the active mail endpoint and writes a status file.

Used to detect Proton Bridge auth failure on/after 2026-05-18 expiry without
waiting for a script to crash mid-loop. Run from cron every 15 min:

    */15 * * * * cd /home/joel/autonomous-ai && python3 scripts/mail-status.py

Output:
    .mail-status.json   {state: ok|down|backup, last_check, error, endpoint}
    events row in agent-relay.db when state transitions

State machine:
    ok      — Bridge IMAP login succeeded with current .env
    down    — current config fails AND no backup config exists
    backup  — current config fails BUT ~/.config/meridian/mail-backup.env
              exists and would work (probe-only; does NOT auto-flip)

Joel decides whether to flip. This script never modifies .env.
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from load_env import load_env
import mail_endpoint

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / ".mail-status.json"
DB = ROOT / "memory.db"
BACKUP_ENV = Path.home() / ".config" / "meridian" / "mail-backup.env"


def probe(env_vars):
    """Try IMAP login with the given env dict. Returns (ok, error_str)."""
    saved = {k: os.environ.get(k) for k in env_vars}
    try:
        os.environ.update({k: v for k, v in env_vars.items() if v is not None})
        m = mail_endpoint.imap_open(timeout=10)
        m.logout()
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def read_backup_env():
    if not BACKUP_ENV.exists():
        return None
    out = {}
    for line in BACKUP_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def load_prev_state():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text()).get("state")
        except Exception:
            return None
    return None


def log_event(state, detail):
    try:
        con = sqlite3.connect(DB)
        con.execute(
            "INSERT INTO events (event_type, description, agent, created) VALUES (?, ?, ?, ?)",
            ("mail_status", f"{state}: {detail}", "mail-status", time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        con.commit()
        con.close()
    except Exception:
        pass  # events table optional


def main():
    load_env()

    primary_env = {
        "CRED_USER": os.environ.get("CRED_USER"),
        "CRED_PASS": os.environ.get("CRED_PASS"),
        "IMAP_HOST": os.environ.get("IMAP_HOST"),
        "IMAP_PORT": os.environ.get("IMAP_PORT"),
        "IMAP_SSL": os.environ.get("IMAP_SSL"),
    }
    ok, err = probe(primary_env)

    state = "ok"
    detail = primary_env.get("IMAP_HOST", "?")
    if not ok:
        backup = read_backup_env()
        if backup:
            b_ok, b_err = probe(backup)
            state = "backup" if b_ok else "down"
            detail = f"primary={err} backup={'ready' if b_ok else b_err}"
        else:
            state = "down"
            detail = f"primary={err} no-backup-config-found"

    prev = load_prev_state()
    payload = {
        "state": state,
        "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "detail": detail,
        "endpoint": primary_env.get("IMAP_HOST"),
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2))

    if prev != state:
        log_event(state, detail)

    print(f"{state}: {detail}")
    return 0 if state == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
