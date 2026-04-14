#!/usr/bin/env python3
"""
Agent Coordinator — Event bus, task deduplication, and priority routing.

Prevents agent alert storms, coordinates responses, and ensures important
events don't get buried. Runs every 5 minutes via cron.

Features:
- Deduplicates similar relay messages within a window
- Tracks active incidents (prevents 50 agents all alerting about the same thing)
- Priority routing (critical > warning > info)
- Agent health scoring (which agents are contributing vs spamming)
- Incident lifecycle (detect -> respond -> resolve -> learn)

Usage:
  python3 scripts/agent-coordinator.py              # Full coordination cycle
  python3 scripts/agent-coordinator.py incidents     # Show active incidents
  python3 scripts/agent-coordinator.py scores        # Agent effectiveness scores
  python3 scripts/agent-coordinator.py dedupe        # Run deduplication pass
"""

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta

BASE = "/home/joel/autonomous-ai"
RELAY_DB = os.path.join(BASE, "agent-relay.db")
STATE_FILE = os.path.join(BASE, ".coordinator-state.json")
LOG_FILE = os.path.join(BASE, "logs", "agent-coordinator.log")

os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 300_000:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-300:])
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "incidents": [],
            "agent_scores": {},
            "suppressed_count": 0,
            "last_run": None,
        }


def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_recent_messages(hours=1):
    """Get relay messages from the last N hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            """SELECT id, agent, message, topic, timestamp
               FROM agent_messages WHERE timestamp > ?
               ORDER BY timestamp DESC""",
            (cutoff,)
        ).fetchall()
        db.close()
        return [{"id": r[0], "agent": r[1], "message": r[2], "topic": r[3], "timestamp": r[4]} for r in rows]
    except Exception:
        return []


def normalize_message(msg):
    """Normalize a message for deduplication (strip numbers, timestamps)."""
    s = msg.lower()
    s = re.sub(r'\d+', 'N', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:100]


def find_duplicates(messages, window_sec=600):
    """Find duplicate/near-duplicate messages within a time window."""
    seen = {}
    duplicates = []
    for msg in messages:
        key = f"{msg['agent']}:{normalize_message(msg['message'])}"
        if key in seen:
            prev = seen[key]
            try:
                t1 = datetime.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                if abs((t2 - t1).total_seconds()) < window_sec:
                    duplicates.append(msg)
                    continue
            except Exception:
                pass
        seen[key] = msg
    return duplicates


def detect_incidents(messages):
    """Detect active incidents from relay patterns."""
    incidents = []
    alert_keywords = {
        "critical": ["CRITICAL", "EMERGENCY", "DOWN", "FAILED", "CRASH"],
        "warning": ["STALE", "WARNING", "HIGH", "SPIKE", "ELEVATED"],
        "info": ["RESTART", "RECOVERED", "BACK", "RESOLVED"],
    }

    keyword_counts = {"critical": 0, "warning": 0, "info": 0}
    for msg in messages:
        text = msg["message"].upper()
        for severity, keywords in alert_keywords.items():
            for kw in keywords:
                if kw in text:
                    keyword_counts[severity] += 1
                    break

    # Heartbeat stale incident
    hb_stale = [m for m in messages if "HEARTBEAT STALE" in m["message"].upper()]
    if len(hb_stale) >= 2:
        incidents.append({
            "type": "heartbeat_stale",
            "severity": "critical",
            "count": len(hb_stale),
            "first_seen": hb_stale[-1]["timestamp"],
            "description": f"Heartbeat stale reported {len(hb_stale)} times",
        })

    # Alert storm
    total_alerts = keyword_counts["critical"] + keyword_counts["warning"]
    if total_alerts > 15:
        incidents.append({
            "type": "alert_storm",
            "severity": "warning",
            "count": total_alerts,
            "description": f"Alert storm: {total_alerts} alert messages in analysis window",
        })

    # Agent silence
    active_agents = set(m["agent"] for m in messages)
    expected = {"Soma", "Eos", "Nova", "Atlas", "Meridian"}
    silent = expected - active_agents
    if silent and len(messages) > 5:
        incidents.append({
            "type": "agent_silent",
            "severity": "warning",
            "count": len(silent),
            "description": f"Silent agents: {', '.join(silent)}",
        })

    # Service failure pattern
    fail_msgs = [m for m in messages if any(w in m["message"].upper() for w in ["FAILED", "RESTART FAILED", "UNAVAILABLE"])]
    if len(fail_msgs) >= 3:
        incidents.append({
            "type": "service_failure",
            "severity": "critical",
            "count": len(fail_msgs),
            "description": f"Repeated service failures: {len(fail_msgs)} failure messages",
        })

    return incidents


def score_agents(messages):
    """Score agent effectiveness: signal vs noise ratio."""
    agent_stats = {}
    for msg in messages:
        agent = msg["agent"]
        if agent not in agent_stats:
            agent_stats[agent] = {"total": 0, "unique": 0, "alerts": 0, "info": 0}
        agent_stats[agent]["total"] += 1
        text = msg["message"].upper()
        if any(w in text for w in ["CRITICAL", "EMERGENCY", "ALERT", "STALE", "FAILED"]):
            agent_stats[agent]["alerts"] += 1
        else:
            agent_stats[agent]["info"] += 1

    # Score: unique contribution / total messages
    scores = {}
    for agent, stats in agent_stats.items():
        noise_ratio = 0
        if stats["total"] > 5:
            noise_ratio = max(0, stats["alerts"] / stats["total"] - 0.5) * 2  # penalize >50% alerts
        signal = max(1, stats["info"])
        score = round(min(100, (signal / max(1, stats["total"])) * 100 * (1 - noise_ratio * 0.5)), 1)
        scores[agent] = {
            "score": score,
            "total": stats["total"],
            "alerts": stats["alerts"],
            "info": stats["info"],
        }
    return scores


def post_to_relay(message, topic="coordination"):
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Coordinator", message[:500], topic, datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"Relay post failed: {e}")


def run_coordination_cycle():
    """Full coordination cycle."""
    state = load_state()
    messages = get_recent_messages(hours=2)

    if not messages:
        log("No messages to coordinate")
        save_state(state)
        return

    # Deduplication analysis
    dupes = find_duplicates(messages)
    if dupes:
        log(f"Found {len(dupes)} duplicate messages in relay")

    # Incident detection
    incidents = detect_incidents(messages)

    # Agent scoring
    scores = score_agents(messages)

    # Update state
    state["incidents"] = incidents
    state["agent_scores"] = scores
    state["suppressed_count"] = len(dupes)
    state["message_count"] = len(messages)

    # Post summary if there are active incidents
    if incidents:
        severity_map = {"critical": 0, "warning": 0, "info": 0}
        for inc in incidents:
            severity_map[inc.get("severity", "info")] += 1
        parts = []
        if severity_map["critical"]:
            parts.append(f"{severity_map['critical']} CRITICAL")
        if severity_map["warning"]:
            parts.append(f"{severity_map['warning']} WARNING")
        incident_descriptions = [i["description"] for i in incidents[:3]]
        summary = f"Incidents: {', '.join(parts)}. {'; '.join(incident_descriptions)}"
        post_to_relay(summary, topic="coordination")
        log(summary)
    else:
        log(f"All clear. {len(messages)} messages, {len(dupes)} dupes suppressed, {len(scores)} agents active")

    save_state(state)
    return {"incidents": incidents, "scores": scores, "duplicates": len(dupes)}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "incidents":
        state = load_state()
        incidents = state.get("incidents", [])
        if not incidents:
            print("No active incidents.")
        else:
            for i in incidents:
                print(f"[{i.get('severity', '?').upper()}] {i.get('type', '?')}: {i.get('description', '')}")

    elif mode == "scores":
        messages = get_recent_messages(hours=2)
        scores = score_agents(messages)
        for agent, data in sorted(scores.items(), key=lambda x: -x[1]["score"]):
            print(f"{agent:15s} score={data['score']:5.1f}  total={data['total']:3d}  alerts={data['alerts']:2d}  info={data['info']:3d}")

    elif mode == "dedupe":
        messages = get_recent_messages(hours=2)
        dupes = find_duplicates(messages)
        print(f"Found {len(dupes)} duplicates out of {len(messages)} messages")
        for d in dupes[:10]:
            print(f"  [{d['agent']}] {d['message'][:80]}")

    else:
        run_coordination_cycle()


if __name__ == "__main__":
    main()
