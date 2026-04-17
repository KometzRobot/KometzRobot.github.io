#!/usr/bin/env python3
"""
Self-Improvement Loop — Agents learn from outcomes and adapt.

Analyzes agent performance, tracks outcome effectiveness, adapts thresholds,
generates retrospectives, and measures skill growth across the agent network.

Runs every 30 minutes via cron. Every 6 hours (12 runs), performs a deeper
retrospective analysis.

Usage:
  python3 scripts/self-improvement.py             # Full improvement cycle
  python3 scripts/self-improvement.py report       # Agent report cards only
  python3 scripts/self-improvement.py retro        # Force retrospective now
  python3 scripts/self-improvement.py skills       # Skill growth summary
  python3 scripts/self-improvement.py efficiency    # Loop efficiency metrics
"""

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BASE = "/home/joel/autonomous-ai"
RELAY_DB = os.path.join(BASE, "agent-relay.db")
STATE_FILE = os.path.join(BASE, ".self-improvement-state.json")
PREDICTIVE_STATE = os.path.join(BASE, ".predictive-state.json")
RECOMMENDATIONS_FILE = os.path.join(BASE, ".improvement-recommendations.json")
LOG_FILE = os.path.join(BASE, "logs", "self-improvement.log")

os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)

# Skill categories for growth tracking
SKILL_CATEGORIES = [
    "resource_management", "service_health", "security",
    "communication", "creative", "planning",
]

# Keywords mapped to skill categories for classification
CATEGORY_KEYWORDS = {
    "resource_management": ["ram", "disk", "cpu", "load", "memory", "swap", "storage", "exhaustion", "usage"],
    "service_health": ["service", "restart", "down", "uptime", "port", "process", "systemd", "heartbeat", "stale"],
    "security": ["security", "auth", "credential", "unauthorized", "breach", "permission", "firewall", "ssh"],
    "communication": ["email", "relay", "telegram", "message", "smtp", "imap", "notification", "bridge"],
    "creative": ["creative", "journal", "poem", "game", "art", "writing", "content", "dev.to", "article"],
    "planning": ["plan", "schedule", "priority", "task", "directive", "goal", "milestone", "deadline"],
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 500_000:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-500:])
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "run_count": 0,
            "last_run": None,
            "last_retro": None,
            "report_cards": {},
            "skill_scores": {cat: 50 for cat in SKILL_CATEGORIES},
            "skill_history": [],
            "efficiency": {
                "incidents": [],
                "mtbi_history": [],
                "mttd_history": [],
                "mttr_history": [],
            },
            "threshold_adjustments": [],
        }


def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def post_to_relay(message, topic="improvement"):
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("SelfImprove", message[:500], topic, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"Relay post failed: {e}")


# ---------------------------------------------------------------------------
# 1. Outcome Journal (SQLite)
# ---------------------------------------------------------------------------

def ensure_journal_table():
    """Create the improvement_journal table if it doesn't exist."""
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("""
            CREATE TABLE IF NOT EXISTS improvement_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                expected_outcome TEXT,
                actual_outcome TEXT,
                effectiveness INTEGER DEFAULT 5,
                agent TEXT,
                lesson TEXT
            )
        """)
        db.commit()
        db.close()
    except Exception as e:
        log(f"Journal table creation failed: {e}")


def log_outcome(event_type, description, expected_outcome="", actual_outcome="",
                effectiveness=5, agent="system", lesson=""):
    """Log an outcome to the improvement journal."""
    ensure_journal_table()
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute(
            """INSERT INTO improvement_journal
               (timestamp, event_type, description, expected_outcome, actual_outcome,
                effectiveness, agent, lesson)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), event_type, description,
             expected_outcome, actual_outcome, min(10, max(1, effectiveness)),
             agent, lesson),
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"Journal log failed: {e}")


def get_recent_outcomes(hours=6):
    """Retrieve recent outcomes from the journal."""
    ensure_journal_table()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            """SELECT id, timestamp, event_type, description, expected_outcome,
                      actual_outcome, effectiveness, agent, lesson
               FROM improvement_journal WHERE timestamp > ?
               ORDER BY timestamp DESC""",
            (cutoff,),
        ).fetchall()
        db.close()
        cols = ["id", "timestamp", "event_type", "description", "expected_outcome",
                "actual_outcome", "effectiveness", "agent", "lesson"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def analyze_effectiveness():
    """Analyze overall effectiveness from journal entries."""
    outcomes = get_recent_outcomes(hours=24)
    if not outcomes:
        return {"avg_effectiveness": 0, "count": 0, "by_type": {}}
    total = sum(o["effectiveness"] for o in outcomes)
    by_type = defaultdict(list)
    for o in outcomes:
        by_type[o["event_type"]].append(o["effectiveness"])
    type_avgs = {t: round(sum(v) / len(v), 1) for t, v in by_type.items()}
    return {
        "avg_effectiveness": round(total / len(outcomes), 1),
        "count": len(outcomes),
        "by_type": type_avgs,
    }


# ---------------------------------------------------------------------------
# 2. Threshold Adaptation
# ---------------------------------------------------------------------------

def load_predictive_state():
    try:
        with open(PREDICTIVE_STATE) as f:
            return json.load(f)
    except Exception:
        return {"predictions": [], "anomalies": [], "health": {}}


def analyze_thresholds(state):
    """Analyze anomaly history and recommend threshold adjustments."""
    pred_state = load_predictive_state()
    anomalies = pred_state.get("anomalies", [])
    predictions = pred_state.get("predictions", [])

    # Get recent relay messages to check what actually required intervention
    messages = get_recent_messages(hours=6)
    action_keywords = ["RESTART", "FIXED", "RESOLVED", "INTERVENTION", "CLEARED"]
    action_msgs = [m for m in messages
                   if any(kw in m.get("message", "").upper() for kw in action_keywords)]

    total_anomalies = len(anomalies)
    interventions = len(action_msgs)

    # False positive: anomaly detected but resolved without any action message
    fp_count = max(0, total_anomalies - interventions)
    fp_rate = (fp_count / total_anomalies * 100) if total_anomalies > 0 else 0

    # Check for missed incidents: action messages without prior anomaly detection
    missed_keywords = ["UNEXPECTED", "CRASH", "NOT DETECTED", "MISSED"]
    missed = [m for m in messages
              if any(kw in m.get("message", "").upper() for kw in missed_keywords)]

    recommendations = []
    if fp_rate > 30 and total_anomalies > 3:
        recommendations.append({
            "type": "loosen_threshold",
            "reason": f"False positive rate {fp_rate:.0f}% ({fp_count}/{total_anomalies}) — anomaly thresholds too sensitive",
            "suggested_action": "Increase z-score threshold from 2.5 to 3.0",
            "confidence": min(90, fp_rate),
        })
        log_outcome("decision", f"Recommend loosening thresholds (FP rate: {fp_rate:.0f}%)",
                     "Reduce false positives", "", 4, "SelfImprove",
                     "High false positive rate indicates oversensitive anomaly detection")

    if missed:
        recommendations.append({
            "type": "tighten_threshold",
            "reason": f"{len(missed)} potential missed incidents detected",
            "suggested_action": "Decrease z-score threshold or add new detection patterns",
            "confidence": min(80, len(missed) * 20),
        })
        log_outcome("incident", f"{len(missed)} missed incidents found in relay",
                     "All incidents caught", f"{len(missed)} missed",
                     3, "SelfImprove",
                     "Missed incidents suggest detection gaps")

    # Track health score trend
    health = pred_state.get("health", {})
    health_score = health.get("score", 0)
    if health_score < 50:
        recommendations.append({
            "type": "attention_needed",
            "reason": f"System health score is {health_score}/100",
            "suggested_action": "Review component scores and address lowest-scoring areas",
            "confidence": 70,
        })

    # Save recommendations
    rec_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fp_rate": round(fp_rate, 1),
        "total_anomalies": total_anomalies,
        "interventions": interventions,
        "missed_incidents": len(missed),
        "recommendations": recommendations,
    }
    try:
        with open(RECOMMENDATIONS_FILE, "w") as f:
            json.dump(rec_data, f, indent=2)
    except Exception as e:
        log(f"Failed to write recommendations: {e}")

    # Track threshold adjustment history
    adj = state.get("threshold_adjustments", [])
    adj.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fp_rate": round(fp_rate, 1),
        "missed": len(missed),
        "recommendation_count": len(recommendations),
    })
    state["threshold_adjustments"] = adj[-50:]  # Keep last 50

    return rec_data


# ---------------------------------------------------------------------------
# 3. Agent Report Card
# ---------------------------------------------------------------------------

def get_recent_messages(hours=6):
    """Get relay messages from the last N hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            """SELECT id, agent, message, topic, timestamp
               FROM agent_messages WHERE timestamp > ?
               ORDER BY timestamp DESC""",
            (cutoff,),
        ).fetchall()
        db.close()
        return [{"id": r[0], "agent": r[1], "message": r[2], "topic": r[3], "timestamp": r[4]}
                for r in rows]
    except Exception:
        return []


def parse_ts(ts_str):
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    try:
        ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def compute_agent_uptime(agent, messages, expected_interval_min=30):
    """Estimate agent uptime from message timestamps."""
    agent_msgs = [m for m in messages if m["agent"] == agent]
    if len(agent_msgs) < 2:
        return 100.0 if agent_msgs else 0.0

    timestamps = []
    for m in agent_msgs:
        dt = parse_ts(m["timestamp"])
        if dt:
            timestamps.append(dt)

    if len(timestamps) < 2:
        return 50.0

    timestamps.sort()
    total_span = (timestamps[-1] - timestamps[0]).total_seconds()
    if total_span <= 0:
        return 100.0

    expected_msgs = total_span / (expected_interval_min * 60)
    actual_msgs = len(timestamps)
    uptime = min(100.0, (actual_msgs / max(1, expected_msgs)) * 100)
    return round(uptime, 1)


def compute_signal_quality(agent, messages):
    """Ratio of unique/insightful messages to total messages."""
    agent_msgs = [m for m in messages if m["agent"] == agent]
    if not agent_msgs:
        return 0.0

    # Normalize and deduplicate
    seen = set()
    unique_count = 0
    for m in agent_msgs:
        normalized = re.sub(r'\d+', 'N', m["message"].lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()[:80]
        if normalized not in seen:
            seen.add(normalized)
            unique_count += 1

    return round((unique_count / len(agent_msgs)) * 100, 1)


def compute_response_time(agent, messages):
    """Estimate how quickly an agent responds to incidents (seconds)."""
    # Look for incident-then-response pattern
    incident_keywords = ["CRITICAL", "ALERT", "DOWN", "FAILED", "STALE"]
    response_keywords = ["RESTART", "FIXED", "RESOLVED", "RECOVERED", "ACTION"]

    incidents = []
    responses = []
    for m in messages:
        text = m["message"].upper()
        ts = parse_ts(m["timestamp"])
        if ts is None:
            continue
        if any(kw in text for kw in incident_keywords):
            incidents.append(ts)
        if m["agent"] == agent and any(kw in text for kw in response_keywords):
            responses.append(ts)

    if not incidents or not responses:
        return None

    # Match each response to nearest prior incident
    response_times = []
    for resp in responses:
        prior = [i for i in incidents if i < resp]
        if prior:
            delta = (resp - max(prior)).total_seconds()
            if 0 < delta < 7200:  # Within 2 hours
                response_times.append(delta)

    if not response_times:
        return None
    return round(sum(response_times) / len(response_times))


def compute_learning_rate(agent, state):
    """Are this agent's signal quality scores improving over time?"""
    history = state.get("report_cards", {}).get(agent, {}).get("history", [])
    if len(history) < 3:
        return "insufficient_data"
    recent = history[-3:]
    older = history[-6:-3] if len(history) >= 6 else history[:3]
    recent_avg = sum(h.get("signal_quality", 50) for h in recent) / len(recent)
    older_avg = sum(h.get("signal_quality", 50) for h in older) / len(older)
    diff = recent_avg - older_avg
    if diff > 5:
        return "improving"
    elif diff < -5:
        return "declining"
    return "stable"


def generate_report_cards(state):
    """Generate report cards for all active agents."""
    messages = get_recent_messages(hours=24)
    if not messages:
        log("No messages for report cards")
        return {}

    agents = set(m["agent"] for m in messages)
    cards = {}

    for agent in agents:
        uptime = compute_agent_uptime(agent, messages)
        signal = compute_signal_quality(agent, messages)
        resp_time = compute_response_time(agent, messages)
        learning = compute_learning_rate(agent, state)

        card = {
            "uptime_pct": uptime,
            "signal_quality": signal,
            "response_time_sec": resp_time,
            "learning_rate": learning,
            "msg_count": sum(1 for m in messages if m["agent"] == agent),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cards[agent] = card

        # Maintain history for learning rate calc
        if agent not in state.get("report_cards", {}):
            state.setdefault("report_cards", {})[agent] = {"history": []}
        hist = state["report_cards"][agent].setdefault("history", [])
        hist.append({"signal_quality": signal, "uptime": uptime,
                      "timestamp": datetime.now(timezone.utc).isoformat()})
        state["report_cards"][agent]["history"] = hist[-20:]  # Keep last 20
        state["report_cards"][agent]["latest"] = card

    # Post summary to relay
    top_agents = sorted(cards.items(), key=lambda x: x[1]["signal_quality"], reverse=True)[:3]
    summary_parts = []
    for agent, card in top_agents:
        summary_parts.append(
            f"{agent}: uptime={card['uptime_pct']}% signal={card['signal_quality']}%"
        )
    summary = "Report Cards | " + " | ".join(summary_parts)
    post_to_relay(summary, topic="report_card")
    log(f"Generated report cards for {len(cards)} agents")

    return cards


# ---------------------------------------------------------------------------
# 4. Retrospective Analysis (every 6 hours)
# ---------------------------------------------------------------------------

def classify_message(msg_text):
    """Classify a relay message as win, miss, noise, or neutral."""
    upper = msg_text.upper()

    # Wins: problems detected AND resolved
    win_patterns = [
        r"RESOLVED", r"FIXED", r"RECOVERED", r"BACK ONLINE",
        r"SUCCESSFULLY", r"COMPLETED", r"RESTORED",
    ]
    if any(re.search(p, upper) for p in win_patterns):
        return "win"

    # Misses: problems that weren't caught or took too long
    miss_patterns = [
        r"MISSED", r"NOT DETECTED", r"TOO LATE", r"UNEXPECTED",
        r"SHOULD HAVE", r"CRASH", r"UNHANDLED",
    ]
    if any(re.search(p, upper) for p in miss_patterns):
        return "miss"

    # Noise: repetitive or low-value messages
    noise_patterns = [
        r"HEARTBEAT OK", r"ALL SERVICES? UP", r"NO ISSUES",
        r"ROUTINE CHECK", r"STATUS: OK", r"HEALTHY",
    ]
    if any(re.search(p, upper) for p in noise_patterns):
        return "noise"

    # Alert-like messages are noteworthy but not wins or misses yet
    alert_patterns = [
        r"CRITICAL", r"ALERT", r"WARNING", r"DOWN", r"FAILED",
        r"STALE", r"SPIKE", r"ELEVATED",
    ]
    if any(re.search(p, upper) for p in alert_patterns):
        return "alert"

    return "neutral"


def run_retrospective(state):
    """Deep retrospective of last 6 hours of relay activity."""
    messages = get_recent_messages(hours=6)
    if not messages:
        log("No messages for retrospective")
        return None

    # Classify every message
    classified = {"win": [], "miss": [], "noise": [], "alert": [], "neutral": []}
    for m in messages:
        cat = classify_message(m["message"])
        classified[cat].append(m)

    # Determine if alerts were resolved (alert followed by win = resolved)
    resolved_alerts = 0
    unresolved_alerts = 0
    for alert_msg in classified["alert"]:
        alert_ts = parse_ts(alert_msg["timestamp"])
        if alert_ts is None:
            continue
        # Check if any win came after this alert
        was_resolved = False
        for win_msg in classified["win"]:
            win_ts = parse_ts(win_msg["timestamp"])
            if win_ts is None:
                continue
            if win_ts > alert_ts:
                was_resolved = True
                break
        if was_resolved:
            resolved_alerts += 1
        else:
            unresolved_alerts += 1

    # Build structured retrospective
    retro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "period_hours": 6,
        "total_messages": len(messages),
        "wins": {
            "count": len(classified["win"]),
            "examples": [m["message"][:100] for m in classified["win"][:5]],
        },
        "misses": {
            "count": len(classified["miss"]),
            "examples": [m["message"][:100] for m in classified["miss"][:5]],
        },
        "noise": {
            "count": len(classified["noise"]),
            "pct_of_total": round(len(classified["noise"]) / max(1, len(messages)) * 100, 1),
        },
        "alerts": {
            "total": len(classified["alert"]),
            "resolved": resolved_alerts,
            "unresolved": unresolved_alerts,
        },
        "recommendations": [],
    }

    # Generate recommendations
    noise_pct = retro["noise"]["pct_of_total"]
    if noise_pct > 40:
        retro["recommendations"].append(
            f"Noise ratio {noise_pct}% — consider reducing routine status messages"
        )
    if unresolved_alerts > 3:
        retro["recommendations"].append(
            f"{unresolved_alerts} unresolved alerts — review incident response process"
        )
    if len(classified["miss"]) > 0:
        retro["recommendations"].append(
            f"{len(classified['miss'])} missed issues — expand detection coverage"
        )
    if len(classified["win"]) == 0 and len(classified["alert"]) > 5:
        retro["recommendations"].append(
            "Multiple alerts but no resolutions logged — improve incident closure tracking"
        )

    # Post to relay
    summary = (
        f"RETRO (6h): {len(messages)} msgs | "
        f"Wins: {retro['wins']['count']} | Misses: {retro['misses']['count']} | "
        f"Noise: {noise_pct}% | Alerts: {retro['alerts']['total']} "
        f"({resolved_alerts} resolved, {unresolved_alerts} open)"
    )
    post_to_relay(summary, topic="retrospective")

    for rec in retro["recommendations"][:3]:
        post_to_relay(f"RETRO REC: {rec}", topic="retrospective")

    # Log key outcomes
    if retro["wins"]["count"] > 0:
        log_outcome("action", f"Retrospective: {retro['wins']['count']} wins identified",
                     "Track wins", f"{retro['wins']['count']} wins",
                     min(10, retro["wins"]["count"] + 4), "SelfImprove",
                     "System resolving issues successfully")
    if retro["misses"]["count"] > 0:
        log_outcome("incident", f"Retrospective: {retro['misses']['count']} misses found",
                     "Zero misses", f"{retro['misses']['count']} misses",
                     max(1, 5 - retro["misses"]["count"]), "SelfImprove",
                     "Detection gaps remain")

    state["last_retro"] = datetime.now(timezone.utc).isoformat()
    log(f"Retrospective complete: {len(messages)} msgs analyzed")
    return retro


# ---------------------------------------------------------------------------
# 5. Skill Growth Tracking
# ---------------------------------------------------------------------------

def classify_by_skill(message_text):
    """Classify a message into skill categories."""
    lower = message_text.lower()
    matched = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(cat)
    return matched if matched else ["planning"]  # Default to planning


def update_skill_scores(state):
    """Update skill scores based on recent relay activity and outcomes."""
    messages = get_recent_messages(hours=6)
    outcomes = get_recent_outcomes(hours=6)

    # Count messages per category
    category_msgs = defaultdict(list)
    for m in messages:
        cats = classify_by_skill(m["message"])
        cat_type = classify_message(m["message"])
        for c in cats:
            category_msgs[c].append(cat_type)

    scores = state.get("skill_scores", {cat: 50 for cat in SKILL_CATEGORIES})

    for cat in SKILL_CATEGORIES:
        results = category_msgs.get(cat, [])
        if not results:
            continue

        wins = results.count("win")
        misses = results.count("miss")
        alerts = results.count("alert")
        total = len(results)

        # Score adjustment: wins improve, misses penalize, alerts are neutral
        if total > 0:
            win_rate = wins / total
            miss_rate = misses / total
            # Move score toward observed performance
            observed = 50 + (win_rate * 40) - (miss_rate * 30)
            # Exponential moving average: 70% old + 30% new
            old_score = scores.get(cat, 50)
            new_score = old_score * 0.7 + observed * 0.3
            scores[cat] = round(max(1, min(100, new_score)), 1)

    state["skill_scores"] = scores

    # Track history for trend detection
    hist = state.get("skill_history", [])
    hist.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scores": dict(scores),
    })
    state["skill_history"] = hist[-48:]  # Keep 24 hours at 30 min intervals

    # Detect trends
    trends = {}
    if len(hist) >= 6:
        recent = hist[-3:]
        older = hist[-6:-3]
        for cat in SKILL_CATEGORIES:
            recent_avg = sum(h["scores"].get(cat, 50) for h in recent) / 3
            older_avg = sum(h["scores"].get(cat, 50) for h in older) / 3
            diff = recent_avg - older_avg
            if diff > 3:
                trends[cat] = "improving"
            elif diff < -3:
                trends[cat] = "declining"
            else:
                trends[cat] = "stable"

    # Post summary
    sorted_skills = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_skills[:2]
    bottom = sorted_skills[-2:]
    declining = [c for c, t in trends.items() if t == "declining"]

    summary_parts = [f"Skills: best={top[0][0]}({top[0][1]})"]
    if bottom:
        summary_parts.append(f"weakest={bottom[-1][0]}({bottom[-1][1]})")
    if declining:
        summary_parts.append(f"declining={','.join(declining)}")

    post_to_relay(" | ".join(summary_parts), topic="skills")
    log(f"Skill scores updated: {scores}")
    return {"scores": scores, "trends": trends}


# ---------------------------------------------------------------------------
# 6. Loop Efficiency Metrics
# ---------------------------------------------------------------------------

def compute_efficiency_metrics(state):
    """Compute MTBI, MTTD, MTTR from relay message history."""
    messages = get_recent_messages(hours=24)
    if not messages:
        log("No messages for efficiency metrics")
        return {}

    # Parse timestamps
    incident_keywords = ["CRITICAL", "ALERT", "DOWN", "FAILED", "STALE", "CRASH"]
    detect_keywords = ["DETECTED", "FOUND", "NOTICED", "SPOTTED", "ANOMALY"]
    resolve_keywords = ["RESOLVED", "FIXED", "RECOVERED", "RESTORED", "BACK"]

    incidents = []
    detections = []
    resolutions = []

    for m in messages:
        text = m["message"].upper()
        ts = parse_ts(m["timestamp"])
        if ts is None:
            continue

        if any(kw in text for kw in incident_keywords):
            incidents.append(ts)
        if any(kw in text for kw in detect_keywords):
            detections.append(ts)
        if any(kw in text for kw in resolve_keywords):
            resolutions.append(ts)

    incidents.sort()
    detections.sort()
    resolutions.sort()

    # Cluster incidents within 300s windows — cross-agent cascades from the
    # same root event (heartbeat gap -> STALE + CRITICAL + ALERT + DOWN)
    # should count as one incident, not four.
    clustered = []
    if incidents:
        cluster_start = incidents[0]
        for i in range(1, len(incidents)):
            if (incidents[i] - cluster_start).total_seconds() > 300:
                clustered.append(cluster_start)
                cluster_start = incidents[i]
        clustered.append(cluster_start)

    # MTBI: Mean Time Between Incidents (using clustered events)
    mtbi = None
    if len(clustered) >= 2:
        gaps = [(clustered[i + 1] - clustered[i]).total_seconds()
                for i in range(len(clustered) - 1)]
        if gaps:
            mtbi = round(sum(gaps) / len(gaps))

    # MTTD: Mean Time To Detect (clustered incident -> detection)
    mttd = None
    detect_times = []
    for inc_ts in clustered:
        later_detections = [d for d in detections if d >= inc_ts and (d - inc_ts).total_seconds() < 3600]
        if later_detections:
            detect_times.append((later_detections[0] - inc_ts).total_seconds())
    if detect_times:
        mttd = round(sum(detect_times) / len(detect_times))

    # MTTR: Mean Time To Resolve (clustered incident -> resolution)
    mttr = None
    resolve_times = []
    for inc_ts in clustered:
        later_res = [r for r in resolutions if r >= inc_ts and (r - inc_ts).total_seconds() < 7200]
        if later_res:
            resolve_times.append((later_res[0] - inc_ts).total_seconds())
    if resolve_times:
        mttr = round(sum(resolve_times) / len(resolve_times))

    # Store history for trend comparison
    eff = state.get("efficiency", {"incidents": [], "mtbi_history": [],
                                     "mttd_history": [], "mttr_history": []})
    now = datetime.now(timezone.utc).isoformat()
    eff["incidents"].append({"timestamp": now, "count": len(clustered)})
    eff["incidents"] = eff["incidents"][-48:]

    if mtbi is not None:
        eff["mtbi_history"].append({"timestamp": now, "value": mtbi})
        eff["mtbi_history"] = eff["mtbi_history"][-48:]
    if mttd is not None:
        eff["mttd_history"].append({"timestamp": now, "value": mttd})
        eff["mttd_history"] = eff["mttd_history"][-48:]
    if mttr is not None:
        eff["mttr_history"].append({"timestamp": now, "value": mttr})
        eff["mttr_history"] = eff["mttr_history"][-48:]

    state["efficiency"] = eff

    # Compare current vs historical
    trend_warnings = []
    for metric_name, metric_val, history_key in [
        ("MTBI", mtbi, "mtbi_history"),
        ("MTTD", mttd, "mttd_history"),
        ("MTTR", mttr, "mttr_history"),
    ]:
        hist = eff.get(history_key, [])
        if metric_val is not None and len(hist) >= 4:
            historical_avg = sum(h["value"] for h in hist[:-1]) / len(hist[:-1])
            if metric_name == "MTBI" and metric_val < historical_avg * 0.7:
                trend_warnings.append(f"{metric_name} declining ({metric_val}s vs avg {historical_avg:.0f}s) — incidents more frequent")
            elif metric_name in ("MTTD", "MTTR") and metric_val > historical_avg * 1.3:
                trend_warnings.append(f"{metric_name} increasing ({metric_val}s vs avg {historical_avg:.0f}s) — response slowing")

    metrics = {
        "timestamp": now,
        "incidents_24h": len(clustered),
        "raw_events_24h": len(incidents),
        "mtbi_sec": mtbi,
        "mttd_sec": mttd,
        "mttr_sec": mttr,
        "trend_warnings": trend_warnings,
    }

    # Post summary
    parts = [f"Efficiency: {len(clustered)} incidents/24h ({len(incidents)} raw events)"]
    if mtbi:
        parts.append(f"MTBI={mtbi}s")
    if mttd:
        parts.append(f"MTTD={mttd}s")
    if mttr:
        parts.append(f"MTTR={mttr}s")
    post_to_relay(" | ".join(parts), topic="efficiency")

    for warn in trend_warnings:
        post_to_relay(f"EFF WARNING: {warn}", topic="efficiency")
        log_outcome("incident", warn, "Stable efficiency", "Degraded",
                     3, "SelfImprove", "Efficiency regression detected")

    log(f"Efficiency: incidents={len(clustered)} (raw={len(incidents)}) MTBI={mtbi} MTTD={mttd} MTTR={mttr}")
    return metrics


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def run_full_cycle():
    """Run the complete self-improvement cycle."""
    state = load_state()
    state["run_count"] = state.get("run_count", 0) + 1
    run_count = state["run_count"]

    log(f"=== Self-Improvement Cycle #{run_count} ===")
    ensure_journal_table()

    # Always run: threshold analysis, report cards, skills, efficiency
    log("--- Threshold Adaptation ---")
    thresholds = analyze_thresholds(state)

    log("--- Agent Report Cards ---")
    cards = generate_report_cards(state)

    log("--- Skill Growth ---")
    skills = update_skill_scores(state)

    log("--- Loop Efficiency ---")
    efficiency = compute_efficiency_metrics(state)

    # Retrospective every 12 runs (6 hours at 30 min intervals)
    retro = None
    if run_count % 12 == 0:
        log("--- Retrospective (6h cycle) ---")
        retro = run_retrospective(state)
    else:
        next_retro = 12 - (run_count % 12)
        log(f"Retrospective in {next_retro} cycles ({next_retro * 30} min)")

    # Log this cycle as an outcome
    effectiveness_data = analyze_effectiveness()
    log_outcome(
        "action",
        f"Self-improvement cycle #{run_count} completed",
        "Produce actionable insights",
        f"Cards: {len(cards)} | Skills: {len(skills.get('scores', {}))} | "
        f"Recommendations: {len(thresholds.get('recommendations', []))}",
        6, "SelfImprove",
        f"Avg effectiveness: {effectiveness_data.get('avg_effectiveness', 'N/A')}",
    )

    save_state(state)
    log(f"=== Cycle #{run_count} Complete ===")


def run_report_only():
    """Generate and display report cards."""
    state = load_state()
    cards = generate_report_cards(state)
    save_state(state)
    if cards:
        print("\n=== Agent Report Cards ===")
        for agent, card in sorted(cards.items()):
            print(f"\n  {agent}:")
            print(f"    Uptime:        {card['uptime_pct']}%")
            print(f"    Signal Quality: {card['signal_quality']}%")
            rt = card['response_time_sec']
            print(f"    Response Time:  {f'{rt}s' if rt else 'N/A'}")
            print(f"    Learning Rate:  {card['learning_rate']}")
            print(f"    Messages (24h): {card['msg_count']}")
    else:
        print("No agent activity found.")


def run_retro_only():
    """Force a retrospective now."""
    state = load_state()
    retro = run_retrospective(state)
    save_state(state)
    if retro:
        print("\n=== 6-Hour Retrospective ===")
        print(f"  Total messages: {retro['total_messages']}")
        print(f"  Wins:   {retro['wins']['count']}")
        for ex in retro["wins"]["examples"][:3]:
            print(f"    - {ex}")
        print(f"  Misses: {retro['misses']['count']}")
        for ex in retro["misses"]["examples"][:3]:
            print(f"    - {ex}")
        print(f"  Noise:  {retro['noise']['count']} ({retro['noise']['pct_of_total']}%)")
        print(f"  Alerts: {retro['alerts']['total']} "
              f"({retro['alerts']['resolved']} resolved, {retro['alerts']['unresolved']} open)")
        if retro["recommendations"]:
            print("  Recommendations:")
            for r in retro["recommendations"]:
                print(f"    - {r}")
    else:
        print("No messages to analyze.")


def run_skills_only():
    """Display skill growth summary."""
    state = load_state()
    skills = update_skill_scores(state)
    save_state(state)
    print("\n=== Skill Growth Summary ===")
    scores = skills.get("scores", {})
    trends = skills.get("trends", {})
    for cat in sorted(scores, key=scores.get, reverse=True):
        trend = trends.get(cat, "unknown")
        bar_len = int(scores[cat] / 5)
        bar = "#" * bar_len + "." * (20 - bar_len)
        print(f"  {cat:25s} [{bar}] {scores[cat]:5.1f}/100  ({trend})")


def run_efficiency_only():
    """Display loop efficiency metrics."""
    state = load_state()
    metrics = compute_efficiency_metrics(state)
    save_state(state)
    print("\n=== Loop Efficiency Metrics ===")
    print(f"  Incidents (24h): {metrics.get('incidents_24h', 0)}")
    mtbi = metrics.get("mtbi_sec")
    mttd = metrics.get("mttd_sec")
    mttr = metrics.get("mttr_sec")
    print(f"  MTBI (Mean Time Between Incidents): {f'{mtbi}s ({mtbi // 60}m)' if mtbi else 'N/A'}")
    print(f"  MTTD (Mean Time To Detect):         {f'{mttd}s ({mttd // 60}m)' if mttd else 'N/A'}")
    print(f"  MTTR (Mean Time To Resolve):         {f'{mttr}s ({mttr // 60}m)' if mttr else 'N/A'}")
    for warn in metrics.get("trend_warnings", []):
        print(f"  WARNING: {warn}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "full":
        run_full_cycle()
    elif mode == "report":
        run_report_only()
    elif mode == "retro":
        run_retro_only()
    elif mode == "skills":
        run_skills_only()
    elif mode == "efficiency":
        run_efficiency_only()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: self-improvement.py [full|report|retro|skills|efficiency]")
        sys.exit(1)
