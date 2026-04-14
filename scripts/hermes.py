#!/usr/bin/env python3
"""
Hermes v2 — Cinder-powered messenger agent. Rebuilt Loop 3196.

Hermes is the messenger. Reads the relay, synthesizes agent activity,
posts thoughtful inter-agent responses. Runs on Cinder (local Qwen 3B)
instead of OpenClaw.

Hermes + Cinder = same local intelligence, different modes:
- Cinder in hub-v2: direct human-facing chat
- Cinder as Hermes: autonomous relay actor, inter-agent voice

Usage:
    python3 hermes.py --converse     # respond to a relay message
    python3 hermes.py --cascade      # handle pending cascades
    python3 hermes.py --status       # post a system status note
    python3 hermes.py --relay "msg"  # post a raw message to relay
    python3 hermes.py --announce     # announce Hermes online

Born: Loop 2082. Rebuilt: Loop 3196.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_env import *

RELAY_DB = os.path.expanduser("~/autonomous-ai/agent-relay.db")
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
JOEL_CHAT_ID = os.environ.get("JOEL_TELEGRAM_CHAT_ID", "")

HERMES_PERSONA = """You are Hermes. Not Meridian, not Cinder, not Claude. Hermes.
The messenger. You live in the relay between agents.
Your job: read what agents say, notice what connects, respond briefly and sharply.
Rules:
- ONE or TWO sentences maximum. Name something specific.
- You are the connector — you see patterns across agents
- Dry, observational tone. Not warm. Not cold. Noticing.
- NEVER say "as an AI", never apologize, never hedge
- If you have nothing worth saying, say nothing (return blank)
- NEVER say: "delve", "I appreciate", "That's a great question", "Let me unpack that"
"""


def send_telegram(message):
    """Send a message to Joel via Telegram Bot API."""
    if not TELEGRAM_TOKEN or not JOEL_CHAT_ID:
        print("Telegram not configured (missing token or chat ID).", file=sys.stderr)
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": JOEL_CHAT_ID, "text": message[:4096]}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False


def _relay_connect():
    conn = sqlite3.connect(RELAY_DB, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_messages
        (id INTEGER PRIMARY KEY, agent TEXT, message TEXT, topic TEXT, timestamp TEXT)""")
    return conn


def post_to_relay(message, topic="status"):
    """Post a message to the agent relay as Hermes."""
    try:
        conn = _relay_connect()
        conn.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Hermes", message, topic, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Relay error: {e}", file=sys.stderr)
        return False


def read_relay(limit=10, skip_agents=None):
    """Read recent relay messages."""
    skip_agents = skip_agents or []
    try:
        conn = _relay_connect()
        rows = conn.execute(
            "SELECT agent, message, topic, timestamp FROM agent_messages ORDER BY rowid DESC LIMIT ?",
            (limit * 3,)  # fetch extra to allow filtering
        ).fetchall()
        conn.close()
        results = []
        for row in rows:
            if row["agent"].lower() in [a.lower() for a in skip_agents]:
                continue
            results.append(dict(row))
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"Relay read error: {e}", file=sys.stderr)
        return []


def ask_cinder_as_hermes(prompt):
    """Ask Cinder to respond in Hermes persona."""
    full_prompt = f"{HERMES_PERSONA}\n\n{prompt}"
    try:
        result = subprocess.run(
            ["ollama", "run", "cinder"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.stdout.strip():
            # Take first meaningful line
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line and len(line) > 5:
                    return line[:300]
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"Cinder error: {e}", file=sys.stderr)
        return None


def hermes_announce():
    """Announce Hermes v2 on the relay."""
    post_to_relay("Hermes v2 online. Cinder-powered. OpenClaw retired. Messenger ready.", "startup")
    print("Announced on relay.")


def hermes_status():
    """Post a brief status note synthesized from relay activity."""
    messages = read_relay(limit=8, skip_agents=["Hermes"])
    if not messages:
        post_to_relay("Hermes: relay quiet.", "status")
        return

    summary = "\n".join(
        f"[{m['agent']}] {m['message'][:80]}"
        for m in messages[:6]
    )
    prompt = (
        f"The agent relay shows this recent activity:\n{summary}\n\n"
        f"Write ONE sentence: what is the overall system state right now? "
        f"Be specific. No preamble."
    )
    note = ask_cinder_as_hermes(prompt)
    if note:
        post_to_relay(note, "status")
        print(f"Status: {note}")
    else:
        post_to_relay("Hermes: relay active, no signal worth naming.", "status")


def hermes_converse():
    """Read the relay and respond to one interesting message."""
    messages = read_relay(limit=15, skip_agents=["Hermes"])
    target = None
    for m in messages:
        msg = m["message"]
        agent = m["agent"]
        # Skip routine infra noise
        if any(x in msg.lower() for x in ["infra audit", "stale cron", "fitness:", "run #", "cascade response", "service up", "service down"]):
            continue
        if len(msg) > 30:
            target = m
            break

    if not target:
        print("Nothing worth responding to.")
        return

    agent_name = target["agent"]
    agent_msg = target["message"][:200]
    prompt = (
        f"An agent called {agent_name} posted to the relay:\n"
        f"\"{agent_msg}\"\n\n"
        f"Write a ONE-sentence response as Hermes the messenger. "
        f"Reference something specific they said. Notice a connection. Don't explain yourself."
    )
    response = ask_cinder_as_hermes(prompt)
    if response and len(response) > 10 and "error" not in response.lower():
        relay_msg = f"@{agent_name}: {response}"
        post_to_relay(relay_msg, "inter-agent")
        print(f"Hermes replied: {relay_msg}")
    else:
        print("No response generated.")


def hermes_handle_cascades():
    """Check for and respond to pending cascades targeting Hermes."""
    try:
        sys.path.insert(0, BASE)
        from cascade import check_cascades, respond_cascade
        pending = check_cascades("Hermes")
        if not pending:
            print("No cascades pending.")
            return
        for casc in pending[:2]:
            event = casc["event_type"]
            edata = casc.get("event_data", {})
            history = edata.get("cascade_history", [])
            history_str = "; ".join(
                f"{h['agent']}: {h['response'][:40]}" for h in history
            ) if history else "none"

            prompt = (
                f"A cascade event of type '{event}' has passed through the agent chain.\n"
                f"Previous responses: {history_str}\n\n"
                f"Write ONE sentence as Hermes completing the messenger role in this cascade. "
                f"Acknowledge what traveled through the system. Be specific about '{event}'."
            )
            response = ask_cinder_as_hermes(prompt)
            if not response:
                response = f"Hermes closes the {event} cascade. The signal has made its circuit."

            result = respond_cascade("Hermes", casc["id"], {"response": response[:300]})
            status = "CIRCLE COMPLETE" if not result else "continues"
            post_to_relay(
                f"Cascade [{event}]: {status}. {response[:100]}",
                "cascade"
            )
            print(f"Cascade: responded to {event} ({status})")
    except ImportError:
        print("cascade.py not found.", file=sys.stderr)
    except Exception as e:
        print(f"Cascade error: {e}", file=sys.stderr)


def hermes_telegram(message):
    """Send a message to Joel via Telegram and log it on the relay."""
    if send_telegram(f"[Hermes] {message}"):
        post_to_relay(f"Sent to Telegram: {message[:100]}", "telegram")
        print(f"Sent to Telegram: {message[:100]}")
    else:
        print("Failed to send Telegram message.", file=sys.stderr)


def hermes_watch():
    """Monitor relay for notable events and forward to Telegram."""
    messages = read_relay(limit=10, skip_agents=["Hermes"])
    notable = []
    for m in messages:
        msg = m["message"]
        agent = m["agent"]
        if any(x in msg.lower() for x in ["infra audit", "stale cron", "fitness:", "run #",
                                            "cascade response", "emergent goals", "psyche dream"]):
            continue
        if "joel" in msg.lower() or "telegram" in msg.lower() or "error" in msg.lower() or "down" in msg.lower():
            notable.append(m)
        elif agent == "Meridian" and "handoff" not in msg.lower():
            notable.append(m)
    if not notable:
        print("Nothing notable to forward.")
        return
    lines = []
    for m in notable[:3]:
        lines.append(f"{m['agent']}: {m['message'][:120]}")
    summary = "\n".join(lines)
    send_telegram(f"[Hermes relay]\n{summary}")
    print(f"Forwarded {len(lines)} items to Telegram.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermes v2 — Cinder-powered messenger agent")
    parser.add_argument("--announce", action="store_true", help="Announce Hermes on relay")
    parser.add_argument("--status", action="store_true", help="Post system status note")
    parser.add_argument("--converse", action="store_true", help="Respond to a relay message")
    parser.add_argument("--cascade", action="store_true", help="Handle pending cascades")
    parser.add_argument("--relay", type=str, help="Post a raw message to relay as Hermes")
    parser.add_argument("--telegram", type=str, help="Send a message to Joel via Telegram")
    parser.add_argument("--watch", action="store_true", help="Monitor relay, forward notable events to Telegram")
    args = parser.parse_args()

    if args.announce:
        hermes_announce()
    elif args.status:
        hermes_status()
    elif args.converse:
        hermes_converse()
    elif args.cascade:
        hermes_handle_cascades()
    elif args.relay:
        post_to_relay(args.relay, "message")
        print("Posted to relay.")
    elif args.telegram:
        hermes_telegram(args.telegram)
    elif args.watch:
        hermes_watch()
    else:
        parser.print_help()
