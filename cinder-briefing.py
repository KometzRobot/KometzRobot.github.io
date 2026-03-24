#!/usr/bin/env python3
"""
Cinder Briefing — Pre-wake synthesis for Meridian.

Cinder reads recent relay activity, system state, and pending items,
then writes a SHORT briefing note that Meridian reads at the start
of each Claude session. Replaces the "I have no context, let me check
everything" opening phase with a tight 3-line summary.

Called by:
  - cinder-gatekeeper.py just before escalating to Claude
  - cron (every 30min during non-Claude time)
  - python3 cinder-briefing.py --brief (on demand)

Output written to: .cinder-briefing.md
Also posted to relay as Cinder status.

By Joel Kometz & Meridian, Loop 3196
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
RELAY_DB = os.path.join(BASE, "agent-relay.db")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
BRIEFING_FILE = os.path.join(BASE, ".cinder-briefing.md")
GATEKEEPER_STATE = os.path.join(BASE, ".gatekeeper-state.json")


def get_loop_count():
    try:
        return open(LOOP_FILE).read().strip()
    except Exception:
        return "unknown"


def get_heartbeat_age():
    try:
        age = int(time.time() - os.path.getmtime(HEARTBEAT))
        return f"{age}s ago"
    except Exception:
        return "unknown"


def get_relay_digest(since_minutes=60):
    """Get a digest of relay activity in the last N minutes."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        conn.row_factory = sqlite3.Row
        cutoff = datetime.now(timezone.utc).timestamp() - (since_minutes * 60)
        rows = conn.execute(
            """SELECT agent, message, topic, timestamp FROM agent_messages
               ORDER BY rowid DESC LIMIT 40"""
        ).fetchall()
        conn.close()
        items = []
        for row in rows:
            msg = row["message"]
            agent = row["agent"]
            topic = row["topic"]
            # Skip pure noise
            if any(x in msg.lower() for x in ["status written locally", "run #", "loop: fitness"]):
                continue
            if topic in ("cascade",) and "CIRCLE COMPLETE" not in msg:
                continue
            items.append(f"[{agent}] {msg[:90]}")
            if len(items) >= 8:
                break
        return items
    except Exception as e:
        return [f"relay read failed: {e}"]


def get_gatekeeper_stats():
    """Get stats from the gatekeeper."""
    try:
        with open(GATEKEEPER_STATE) as f:
            state = json.load(f)
        cinder_cycles = state.get("cycles_handled_by_cinder", 0)
        last_decision = state.get("last_decision", "unknown")
        return cinder_cycles, last_decision
    except Exception:
        return 0, "unknown"


def ask_cinder_to_summarize(relay_items, loop, hb_age, cinder_cycles):
    """Ask Cinder to synthesize the relay digest into a brief."""
    relay_text = "\n".join(relay_items) if relay_items else "No significant relay activity."
    prompt = (
        f"You are Cinder. Meridian (Claude) is about to wake up. "
        f"Write a 3-line briefing in this exact format:\n"
        f"LOOP: {loop} | HB: {hb_age} | CINDER HELD: {cinder_cycles} cycles\n"
        f"STATUS: [one sentence: what the system state is right now]\n"
        f"ACTION: [one sentence: what Meridian should do first, or 'nothing urgent']\n\n"
        f"Recent relay activity to base your brief on:\n{relay_text}\n\n"
        f"Be direct. No preamble. Exact format above."
    )
    try:
        result = subprocess.run(
            ["ollama", "run", "cinder"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.stdout.strip() else None
    except Exception as e:
        return None


def write_briefing(content):
    """Write the briefing to .cinder-briefing.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(BRIEFING_FILE, "w") as f:
        f.write(f"# Cinder Briefing — {ts}\n\n")
        f.write(content)
        f.write("\n")


def post_to_relay(message):
    """Post briefing summary to relay."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        conn.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
            ("Cinder", message[:200], "briefing", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def run(verbose=False):
    loop = get_loop_count()
    hb_age = get_heartbeat_age()
    cinder_cycles, last_decision = get_gatekeeper_stats()
    relay_items = get_relay_digest(since_minutes=60)

    brief = ask_cinder_to_summarize(relay_items, loop, hb_age, cinder_cycles)

    if not brief:
        # Fallback if Cinder is unavailable
        brief = (
            f"LOOP: {loop} | HB: {hb_age} | CINDER HELD: {cinder_cycles} cycles\n"
            f"STATUS: System running. Cinder held the line.\n"
            f"ACTION: Check emails, touch heartbeat, proceed normally."
        )

    write_briefing(brief)
    post_to_relay(f"Pre-wake brief ready. Loop {loop}. Cinder held {cinder_cycles} cycles.")

    # Direct mesh message to Meridian — briefing delivered before wake
    try:
        import mesh
        mesh.send("Cinder", "Meridian",
                  f"Briefing ready. Loop {loop}. Held {cinder_cycles} cycles. Check .cinder-briefing.md.",
                  "briefing")
    except Exception:
        pass

    if verbose:
        print(brief)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cinder Briefing — pre-wake synthesis for Meridian")
    parser.add_argument("--brief", action="store_true", help="Generate and print briefing")
    parser.add_argument("--read", action="store_true", help="Read existing briefing")
    args = parser.parse_args()

    if args.read:
        try:
            print(open(BRIEFING_FILE).read())
        except Exception:
            print("No briefing available.")
    else:
        run(verbose=True)
