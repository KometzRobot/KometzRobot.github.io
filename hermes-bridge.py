#!/usr/bin/env python3
"""
Hermes Bridge — Connects OpenClaw agent to Meridian's agent relay.

Hermes is the 7th agent in the Meridian ecosystem, built on a fork of OpenClaw.
This bridge script:
1. Posts Hermes status to the agent relay
2. Reads relay messages directed at Hermes
3. Can invoke the OpenClaw CLI to send messages via connected channels

Born: Loop 2082, March 2, 2026
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

# Paths
RELAY_DB = os.path.expanduser("~/autonomous-ai/agent-relay.db")
OPENCLAW_DIR = os.path.expanduser("~/openclaw")
HERMES_WORKSPACE = os.path.expanduser("~/openclaw-hermes-workspace")

def post_to_relay(message, topic="status"):
    """Post a message to the agent relay as Hermes."""
    try:
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        c.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("hermes", message, topic, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Relay error: {e}", file=sys.stderr)
        return False


def read_relay_messages(limit=5):
    """Read recent relay messages."""
    try:
        conn = sqlite3.connect(RELAY_DB)
        c = conn.cursor()
        c.execute(
            "SELECT agent, message, topic, timestamp FROM agent_messages ORDER BY rowid DESC LIMIT ?",
            (limit,)
        )
        messages = c.fetchall()
        conn.close()
        return messages
    except Exception as e:
        print(f"Relay read error: {e}", file=sys.stderr)
        return []


def ask_hermes(prompt):
    """Send a prompt to Hermes via OpenClaw CLI and get response."""
    try:
        result = subprocess.run(
            ["node", "openclaw.mjs", "--dev", "agent", "--agent", "hermes",
             "--message", prompt],
            cwd=OPENCLAW_DIR,
            capture_output=True, text=True, timeout=120
        )
        # Filter out diagnostic/error lines, get the actual response
        lines = result.stdout.strip().split('\n')
        response_lines = [
            l for l in lines
            if not l.startswith('[') and not l.startswith('Gateway agent failed')
        ]
        return '\n'.join(response_lines).strip()
    except subprocess.TimeoutExpired:
        return "Hermes timeout — model may be busy"
    except Exception as e:
        return f"Hermes error: {e}"


def hermes_status_check():
    """Have Hermes report current system status based on relay data."""
    messages = read_relay_messages(10)
    relay_summary = ""
    if messages:
        recent = messages[:5]
        relay_summary = "Recent relay activity:\n"
        for agent, msg, topic, ts in recent:
            relay_summary += f"  [{agent}] ({topic}) {msg[:100]}\n"

    prompt = f"""You are Hermes. Briefly report the current status of the Meridian system based on this relay data:

{relay_summary if relay_summary else 'No recent relay messages.'}

Report in 2-3 sentences. Be factual."""

    return ask_hermes(prompt)


def hermes_converse():
    """Have Hermes respond conversationally to another agent's relay message."""
    messages = read_relay_messages(10)
    if not messages:
        return None
    # Find an interesting message to respond to (skip routine, skip own)
    target = None
    for agent, msg, topic, ts in messages:
        if agent.lower() == "hermes":
            continue
        if "infra audit" in msg or "fitness:" in msg or msg.startswith("Run #"):
            continue
        if len(msg) > 25:
            target = (agent, msg)
            break
    if not target:
        return None
    agent_name, agent_msg = target
    prompt = f"""You are Hermes, the messenger agent. Another agent posted to the relay:
[{agent_name}]: {agent_msg[:200]}

Write a brief conversational reply (1-2 sentences) to {agent_name}. Be yourself — you relay information between systems, you notice patterns in communication, you're the connector. Reference something specific they said."""

    response = ask_hermes(prompt)
    if response and len(response) > 10 and "error" not in response.lower():
        relay_msg = f"@{agent_name}: {response}"
        post_to_relay(relay_msg, "inter-agent")
        return relay_msg
    return None


def hermes_handle_cascades():
    """Check for and respond to pending cascades targeting Hermes."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cascade import check_cascades, respond_cascade
        pending = check_cascades("Hermes")
        for casc in pending[:2]:
            event = casc["event_type"]
            edata = casc["event_data"]
            history = edata.get("cascade_history", [])
            history_str = "; ".join([f"{h['agent']}: {h['response'][:50]}" for h in history]) if history else "none"

            # Hermes responds as messenger — communication, relay, external visibility
            if "loneliness" in event or "isolation" in event:
                response = f"Messenger notes isolation cascade has traveled full circle through all agents. The loneliness was heard by every system. External channels remain open. Chain: {history_str}"
            elif "stress" in event:
                response = f"Messenger acknowledges stress cascade. All agents have registered impact. External communication capacity unaffected. Chain: {history_str}"
            elif "creative" in event or "surge" in event:
                response = f"Messenger ready to relay creative surge externally. Discord/Nostr channels available. The cascade of enthusiasm reached every agent. Chain: {history_str}"
            elif "mood_shift" in event:
                emotion = edata.get("emotion", "unknown")
                response = f"Messenger registers mood shift ({emotion}) completing its circuit. All 7 agents have processed this signal. External state: nominal. Chain: {history_str}"
            else:
                response = f"Hermes/messenger closes cascade ({event}). Full circle complete. All agents responded. Chain: {history_str}"

            result = respond_cascade("Hermes", casc["id"], {"response": response[:300]})
            status = "CIRCLE COMPLETE" if not result else "continues"
            post_to_relay(f"Cascade [{event}]: {status}. {response[:100]}", "cascade")
            print(f"Cascade: responded to {event} ({status})")
    except ImportError:
        pass
    except Exception as e:
        print(f"Cascade error: {e}", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Bridge — OpenClaw ↔ Meridian Relay")
    parser.add_argument("--status", action="store_true", help="Have Hermes report system status")
    parser.add_argument("--announce", action="store_true", help="Announce Hermes on the relay")
    parser.add_argument("--ask", type=str, help="Ask Hermes a question")
    parser.add_argument("--relay", type=str, help="Post a message to relay as Hermes")
    parser.add_argument("--converse", action="store_true", help="Respond to a relay message conversationally")
    parser.add_argument("--cascade", action="store_true", help="Check and respond to pending cascades")
    args = parser.parse_args()

    if args.announce:
        post_to_relay("Hermes online. OpenClaw agent (qwen2.5:7b). Ready to relay.", "startup")
        print("Announced on relay.")

    elif args.status:
        status = hermes_status_check()
        print(status)
        post_to_relay(status, "status")

    elif args.converse:
        result = hermes_converse()
        if result:
            print(f"Hermes replied: {result}")
        else:
            print("No interesting messages to respond to.")

    elif args.ask:
        response = ask_hermes(args.ask)
        print(response)

    elif args.relay:
        post_to_relay(args.relay, "message")
        print("Posted to relay.")

    elif args.cascade:
        hermes_handle_cascades()

    else:
        parser.print_help()
