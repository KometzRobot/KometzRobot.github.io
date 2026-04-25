#!/usr/bin/env python3
"""
Sentinel Gatekeeper v2.0 — Intelligent loop pre-screener with handoff integration.

Replaces cinder-gatekeeper.py. Runs every 20 seconds via cron (timestamps 12,32,52).
Decides whether to escalate to Claude or hold with Sentinel (local Cinder model).

Enhancements over v1:
  - Checks context flags from agents (Eos, Soma, etc.)
  - Generates handoff + briefing before escalation
  - Better logging

Decision logic:
  - ESCALATE to Claude if: new email, new Joel dashboard message,
    system alert, stale heartbeat, context flags with priority >= 2,
    or max interval reached (1 hour)
  - HOLD with Sentinel if: no new work detected

Usage:
    python3 sentinel-gatekeeper.py            # Normal check cycle
    python3 sentinel-gatekeeper.py --force    # Force escalate to Claude
    python3 sentinel-gatekeeper.py --status   # Show last decision

By Joel Kometz & Meridian, Loop 4445
"""

import argparse
import json
import os
import re
import requests
import sqlite3
import subprocess
import sys
import time

OLLAMA_API = "http://localhost:11434/api/generate"


def ollama_generate(model, prompt, timeout=30):
    """Call Ollama HTTP API directly — returns clean text without ANSI artifacts."""
    try:
        resp = requests.post(OLLAMA_API, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception:
        return None


def strip_ansi(text):
    """Remove ANSI escape sequences from Ollama streaming output (legacy fallback)."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]|\[\d*[A-Za-z]', '', text)
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
GATE_STATE = os.path.join(BASE, ".gatekeeper-state.json")

# How old (seconds) can the heartbeat be before it's stale?
# Sentinel runs every 2 min — stale after 5 min means Claude missed 2+ cycles
HEARTBEAT_STALE_THRESHOLD = 300

# Contacts whose emails always escalate
ESCALATE_SENDERS = [
    "jkometz@hotmail.com",      # Joel
    "sammyqjankis@proton.me",   # Sammy
    "not.taskyy@gmail.com",     # Loom
    "bbaltgailis@gmail.com",    # Brett
    "lumen@lumenloop.work",     # Lumen
    "g.mcnamar@hotmail.com",    # Glenna (Joel's mother)
]

# Cron interval in seconds — used to check for "new" messages
CRON_INTERVAL = 120  # 2 minutes (sentinel is now primary loop manager)

# ═══════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════

def load_state():
    """Load gatekeeper state from last run."""
    try:
        with open(GATE_STATE) as f:
            return json.load(f)
    except Exception:
        return {
            "last_run": 0,
            "last_email_id": 0,
            "last_msg_count": 0,
            "last_decision": "init",
            "cycles_held_by_sentinel": 0,
            "cycles_escalated_to_claude": 0,
        }


def save_state(state):
    """Save gatekeeper state."""
    state["last_run"] = int(time.time())
    with open(GATE_STATE, "w") as f:
        json.dump(state, f, indent=2)


# ═══════════════════════════════════════════
# CHECKS
# ═══════════════════════════════════════════

def check_heartbeat():
    """Is the heartbeat stale?"""
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT)
        return age > HEARTBEAT_STALE_THRESHOLD, f"heartbeat {int(age)}s old"
    except Exception:
        return True, "heartbeat file missing"


def check_new_emails(last_email_id):
    """Are there new emails from important contacts?"""
    try:
        import imaplib
        import email.header

        # Load .env for IMAP credentials
        env = {}
        env_path = os.path.join(BASE, ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")

        host = env.get("IMAP_HOST", "127.0.0.1")
        port = int(env.get("IMAP_PORT", "1144"))
        user = env.get("IMAP_USER", "kometzrobot@proton.me")
        password = env.get("CRED_PASS", "")
        if not password:
            return False, "no imap credentials", last_email_id

        imap = imaplib.IMAP4(host, port)
        imap.login(user, password)
        imap.select("INBOX")

        # Search for unseen messages
        typ, data = imap.search(None, "UNSEEN")
        imap.logout()

        if typ != "OK" or not data[0]:
            return False, "no new emails", last_email_id

        ids = data[0].split()
        if not ids:
            return False, "no new emails", last_email_id

        # New emails found — escalate
        return True, f"{len(ids)} new email(s)", int(ids[-1])

    except Exception as e:
        return False, f"email check failed: {e}", last_email_id


def check_dashboard(last_msg_count):
    """Are there new Joel messages on the dashboard?"""
    try:
        with open(DASH_FILE) as f:
            data = json.load(f)
        msgs = data.get("messages", [])
        joel_msgs = [m for m in msgs if m.get("from", "").lower() == "joel"]
        new_count = len(joel_msgs)
        if new_count > last_msg_count:
            return True, f"{new_count - last_msg_count} new Joel message(s)", new_count
        return False, "no new dashboard messages", last_msg_count
    except Exception as e:
        return False, f"dashboard check failed: {e}", last_msg_count


def check_system_health():
    """Are there critical system issues?"""
    alerts = []

    # Load average
    try:
        with open("/proc/loadavg") as f:
            load = float(f.read().split()[0])
        if load > 8.0:
            alerts.append(f"high load: {load:.1f}")
    except Exception:
        pass

    # Key services
    import socket
    for port, service in [(8090, "hub"), (8091, "chorus"), (1144, "bridge")]:
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
        except Exception:
            alerts.append(f"{service} port {port} unreachable")

    # Duplicate Meridian instance check (match 'claude' binary name exactly)
    try:
        result = subprocess.run(
            ["pgrep", "-c", "^claude$"],
            capture_output=True, text=True, timeout=3
        )
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        if count > 1:
            alerts.append(f"DUAL INSTANCE: {count} Claude loops running")
    except Exception:
        pass

    if alerts:
        return True, "system alerts: " + ", ".join(alerts)
    return False, "system healthy"


# ═══════════════════════════════════════════
# CINDER ACTIONS (cheap, local)
# ═══════════════════════════════════════════

def touch_heartbeat():
    """Signal alive without Claude."""
    Path(HEARTBEAT).touch()


def sentinel_status_note(state):
    """Have Sentinel write a brief status note to relay (uses local Ollama model)."""
    cycles_since_claude = state.get("cycles_held_by_sentinel", state.get("cycles_handled_by_cinder", 0))
    prompt = (
        f"You are Sentinel, the gatekeeper maintaining the system between Claude loops. "
        f"It has been {cycles_since_claude} cycles since Claude ran. "
        f"Write a ONE-LINE status note for the agent relay. Keep it brief and factual. "
        f"No preamble, just the note."
    )
    try:
        cleaned = ollama_generate("cinder", prompt, timeout=30) or ""
        note = cleaned.splitlines()[0][:200] if cleaned else "Gatekeeper holding."

        # Write to relay
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        db.execute("""CREATE TABLE IF NOT EXISTS agent_messages
            (id INTEGER PRIMARY KEY, agent TEXT, message TEXT, topic TEXT, timestamp TEXT)""")
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
            ("Sentinel", note, "gatekeeper", datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        db.close()
    except Exception as e:
        pass  # Non-critical — Sentinel's note is nice-to-have


def escalate_to_claude():
    """Trigger the Claude watchdog to start a new loop."""
    watchdog = os.path.join(BASE, "watchdog.sh")
    if os.path.exists(watchdog):
        try:
            subprocess.Popen(
                ["bash", watchdog],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception as e:
            print(f"[gatekeeper] watchdog trigger failed: {e}")
            return False
    return False


# ═══════════════════════════════════════════
# MAIN DECISION LOGIC
# ═══════════════════════════════════════════

def gate_check(force=False):
    """Run the gatekeeper check. Returns (escalate: bool, reason: str)."""
    state = load_state()
    reasons = []
    should_escalate = False

    if force:
        return True, "forced escalation", state

    # 1. Heartbeat stale?
    stale, msg = check_heartbeat()
    if stale:
        should_escalate = True
        reasons.append(msg)

    # 2. New emails?
    new_email, msg, new_last_id = check_new_emails(state.get("last_email_id", 0))
    state["last_email_id"] = new_last_id
    if new_email:
        should_escalate = True
        reasons.append(msg)

    # 3. New dashboard messages?
    new_dash, msg, new_msg_count = check_dashboard(state.get("last_msg_count", 0))
    state["last_msg_count"] = new_msg_count
    if new_dash:
        should_escalate = True
        reasons.append(msg)

    # 4. System health issues?
    health_issue, msg = check_system_health()
    if health_issue:
        should_escalate = True
        reasons.append(msg)

    # 5. Been too long since Claude ran? (max 1 hour without Claude)
    last_claude = state.get("last_claude_run", 0)
    if time.time() - last_claude > 3600:
        should_escalate = True
        reasons.append("1h max interval reached")

    # 6. Agent context flags (Eos, Soma, etc. flagged something important)
    try:
        from context_flag import flag as _  # just verify import works
        flags_file = os.path.join(BASE, ".context-flags.json")
        if os.path.exists(flags_file):
            with open(flags_file) as f:
                flags = json.load(f)
            urgent_flags = [f for f in flags if isinstance(f, dict) and f.get("priority", 0) >= 2]
            if urgent_flags:
                should_escalate = True
                flag_summary = "; ".join(f"{fl.get('agent','?')}: {fl.get('message','')[:50]}" for fl in urgent_flags[:3])
                reasons.append(f"agent flags: {flag_summary}")
    except Exception:
        pass

    reason_str = "; ".join(reasons) if reasons else "routine maintenance"
    return should_escalate, reason_str, state


def run(force=False, status_only=False):
    """Main entry point."""
    state = load_state()

    if status_only:
        print(f"Last run: {datetime.fromtimestamp(state.get('last_run', 0)).isoformat()}")
        print(f"Last decision: {state.get('last_decision', 'unknown')}")
        print(f"Sentinel cycles: {state.get('cycles_held_by_sentinel', state.get('cycles_handled_by_cinder', 0))}")
        print(f"Claude escalations: {state.get('cycles_escalated_to_claude', 0)}")
        return

    should_escalate, reason, state = gate_check(force)
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    if should_escalate:
        print(f"[{ts}] ESCALATE → Claude — {reason}")
        state["last_decision"] = f"escalate: {reason}"
        state["last_claude_run"] = int(time.time())
        state["cycles_escalated_to_claude"] = state.get("cycles_escalated_to_claude", 0) + 1
        save_state(state)
        # Pre-escalation: write handoff + briefing so next Claude has context
        try:
            subprocess.run(
                ["python3", os.path.join(BASE, "loop-handoff.py"), "write"],
                capture_output=True, timeout=15
            )
        except Exception:
            pass
        try:
            subprocess.run(
                ["python3", os.path.join(BASE, "sentinel-briefing.py"), "--brief"],
                capture_output=True, timeout=30
            )
        except Exception:
            pass
        escalate_to_claude()
    else:
        print(f"[{ts}] HOLD → Sentinel — {reason}")
        state["last_decision"] = f"hold: {reason}"
        state["cycles_held_by_sentinel"] = state.get("cycles_held_by_sentinel", state.get("cycles_handled_by_cinder", 0)) + 1
        save_state(state)
        touch_heartbeat()
        # Write Sentinel status note every 3rd cycle
        sentinel_cycles = state.get("cycles_held_by_sentinel", state.get("cycles_handled_by_cinder", 0))
        if sentinel_cycles % 3 == 0:
            sentinel_status_note(state)
        # Dream during hold — every 60th cycle (~20 min at 20s intervals)
        # This is REM sleep: consolidate memories, form new connections
        if sentinel_cycles % 60 == 0 and sentinel_cycles > 0:
            try:
                subprocess.run(
                    ["python3", os.path.join(BASE, "dream-engine.py")],
                    capture_output=True, timeout=60
                )
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel Gatekeeper — Intelligent loop pre-screener")
    parser.add_argument("--force", action="store_true", help="Force escalation to Claude")
    parser.add_argument("--status", action="store_true", help="Show last decision and stats")
    args = parser.parse_args()
    run(force=args.force, status_only=args.status)
