#!/usr/bin/env python3
"""
context_flag.py — Lightweight flag utility for agents.

Any agent (Eos, Soma, Nova, etc.) can import this to flag important
observations for the next Meridian handoff.

Usage from Python:
    from context_flag import flag
    flag("Eos", "Proton Bridge crashed 3 times in 1 hour", priority=3)

Usage from CLI:
    python3 context_flag.py Soma "Disk usage at 90%" 2

Priority levels:
    1 = informational (FYI)
    2 = attention needed (should check)
    3 = urgent (act immediately)
"""

import json
import os
import time
from datetime import datetime

FLAGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".context-flags.json")
MAX_FLAGS = 20
MAX_PER_AGENT = 5


def flag(agent, message, priority=1):
    """Add a context flag for the next Meridian handoff.

    Returns True if flag was added, False if rejected (duplicate/limit).
    """
    agent = str(agent)[:30]
    message = str(message)[:300]
    priority = max(1, min(3, int(priority)))

    try:
        flags = []
        if os.path.exists(FLAGS_FILE):
            with open(FLAGS_FILE) as f:
                data = json.load(f)
            if isinstance(data, list):
                flags = data

        # Reject duplicate (same agent + same first 50 chars)
        msg_prefix = message[:50]
        for existing in flags:
            if existing.get("agent") == agent and existing.get("message", "")[:50] == msg_prefix:
                return False

        # Enforce per-agent limit
        agent_flags = [f for f in flags if f.get("agent") == agent]
        if len(agent_flags) >= MAX_PER_AGENT:
            # Remove oldest from this agent
            for i, f in enumerate(flags):
                if f.get("agent") == agent:
                    flags.pop(i)
                    break

        flags.append({
            "agent": agent,
            "message": message,
            "priority": priority,
            "ts": time.time(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

        # Global cap
        flags = flags[-MAX_FLAGS:]

        with open(FLAGS_FILE, "w") as f:
            json.dump(flags, f, indent=2)
        return True

    except (json.JSONDecodeError, TypeError, ValueError):
        # Corrupt file — reset
        try:
            with open(FLAGS_FILE, "w") as f:
                json.dump([], f)
        except Exception:
            pass
        return False
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 context_flag.py <agent> <message> [priority 1-3]")
        print("Example: python3 context_flag.py Eos 'Bridge down, restarted twice' 2")
        exit(1)

    agent = sys.argv[1]
    message = sys.argv[2]
    priority = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    if flag(agent, message, priority):
        print(f"Flagged: [{agent}] {message[:80]} (priority {priority})")
    else:
        print("Rejected (duplicate or error).")
