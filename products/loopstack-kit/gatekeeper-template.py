#!/usr/bin/env python3
"""
LoopStack Gatekeeper Template
Pre-screens incoming signals before they reach your main agent.

Run as a cron job every 10-20 minutes. Reads raw inputs (email,
dashboard messages, system alerts) and decides what to escalate.

Customize the RULES dict and escalation logic for your agent.
"""

import json
import os
import sqlite3
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
RELAY_DB = os.path.join(BASE, "agent-relay.db")

# Define your triage rules
RULES = {
    "escalate_keywords": ["urgent", "broken", "crash", "error", "help"],
    "hold_keywords": ["newsletter", "digest", "notification"],
    "max_hold_cycles": 3,  # escalate after 3 cycles of holding
}


def check_relay():
    """Read recent relay messages and triage them."""
    if not os.path.exists(RELAY_DB):
        return []

    conn = sqlite3.connect(RELAY_DB)
    rows = conn.execute(
        "SELECT agent, topic, message, timestamp FROM agent_messages "
        "ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()
    conn.close()

    escalations = []
    for agent, topic, message, ts in rows:
        msg_lower = message.lower()

        # Check for escalation keywords
        if any(kw in msg_lower for kw in RULES["escalate_keywords"]):
            escalations.append({
                "source": agent,
                "topic": topic,
                "message": message[:200],
                "reason": "keyword_match",
                "timestamp": ts
            })

    return escalations


def write_briefing(escalations):
    """Write a briefing file for the main agent."""
    briefing_path = os.path.join(BASE, ".gatekeeper-briefing.md")

    with open(briefing_path, "w") as f:
        f.write(f"# Gatekeeper Briefing — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        if not escalations:
            f.write("No escalations. All clear.\n")
        else:
            f.write(f"## {len(escalations)} Escalation(s)\n\n")
            for e in escalations:
                f.write(f"- **{e['source']}** [{e['topic']}]: {e['message']}\n")
                f.write(f"  Reason: {e['reason']} | {e['timestamp']}\n\n")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Briefing written: {len(escalations)} escalation(s)")


if __name__ == "__main__":
    escalations = check_relay()
    write_briefing(escalations)
