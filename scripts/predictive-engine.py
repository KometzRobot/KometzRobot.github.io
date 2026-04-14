#!/usr/bin/env python3
"""
Predictive Engine — Anomaly detection, trend forecasting, and proactive alerts.

Gives the agent network foresight. Analyzes Soma's resource history and relay
patterns to detect anomalies and predict issues before they become failures.

Runs every 10 minutes via cron. Posts predictions to agent-relay.db for other
agents to act on.

Usage:
  python3 scripts/predictive-engine.py           # Full analysis cycle
  python3 scripts/predictive-engine.py forecast   # Resource exhaustion forecast
  python3 scripts/predictive-engine.py anomalies  # Anomaly detection only
  python3 scripts/predictive-engine.py health      # Health score with explanations
"""

import json
import math
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "/home/joel/autonomous-ai"
RELAY_DB = os.path.join(BASE, "agent-relay.db")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")
BODY_STATE = os.path.join(BASE, ".body-state.json")
MOOD_HISTORY = os.path.join(BASE, ".soma-mood-history.json")
STATE_FILE = os.path.join(BASE, ".predictive-state.json")
LOG_FILE = os.path.join(BASE, "logs", "predictive-engine.log")

os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)


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
        return {"predictions": [], "anomalies": [], "last_run": None, "trend_data": {}}


def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def post_to_relay(message, topic="prediction"):
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Predictive", message[:500], topic, datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"Relay post failed: {e}")


def get_soma_history():
    """Load resource history from Soma state."""
    try:
        with open(SOMA_STATE) as f:
            soma = json.load(f)
        return {
            "ram": soma.get("ram_history", []),
            "load": soma.get("load_history", []),
            "disk": soma.get("disk_history", []),
            "mood_scores": soma.get("mood_score_history", []),
        }
    except Exception:
        return {"ram": [], "load": [], "disk": [], "mood_scores": []}


def get_relay_frequency(hours=6):
    """Count relay messages per agent in recent hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            "SELECT agent, COUNT(*) FROM agent_messages WHERE timestamp > ? GROUP BY agent",
            (cutoff,)
        ).fetchall()
        db.close()
        return dict(rows)
    except Exception:
        return {}


def linear_regression(values):
    """Simple linear regression. Returns (slope, intercept, r_squared)."""
    n = len(values)
    if n < 3:
        return 0, 0, 0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_yy = sum((y - y_mean) ** 2 for y in values)
    if ss_xx == 0:
        return 0, y_mean, 0
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    r_sq = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0
    return slope, intercept, r_sq


def detect_anomalies(values, label="metric", threshold=2.5):
    """Z-score anomaly detection on a numeric series."""
    if len(values) < 5:
        return []
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 0.001
    anomalies = []
    for i, v in enumerate(values):
        z = abs(v - mean) / std
        if z > threshold:
            direction = "spike" if v > mean else "drop"
            anomalies.append({
                "index": i,
                "value": round(v, 2),
                "z_score": round(z, 2),
                "direction": direction,
                "label": label,
            })
    return anomalies


def forecast_exhaustion(values, label, max_val=100, sample_interval_sec=30):
    """Predict when a resource will hit its limit based on trend."""
    if len(values) < 5:
        return None
    recent = values[-min(30, len(values)):]
    slope, intercept, r_sq = linear_regression(recent)
    if slope <= 0 or r_sq < 0.3:
        return None
    current = recent[-1]
    remaining = max_val - current
    if remaining <= 0:
        return {"label": label, "exhaustion": "NOW", "confidence": r_sq}
    samples_to_exhaust = remaining / slope
    seconds_to_exhaust = samples_to_exhaust * sample_interval_sec
    hours = seconds_to_exhaust / 3600
    if hours > 168:  # more than a week
        return None
    return {
        "label": label,
        "current": round(current, 1),
        "rate": round(slope * (3600 / sample_interval_sec), 2),  # per hour
        "hours_to_exhaust": round(hours, 1),
        "confidence": round(r_sq, 2),
    }


def detect_relay_anomalies():
    """Detect unusual patterns in agent communication."""
    freq = get_relay_frequency(hours=6)
    total = sum(freq.values())
    findings = []
    if total == 0:
        findings.append("SILENT: No relay activity in 6 hours — agents may be down")
        return findings
    for agent, count in freq.items():
        if count > total * 0.7 and total > 10:
            findings.append(f"DOMINANCE: {agent} has {count}/{total} messages ({count*100//total}%) — possible alert loop")
    alert_agents = ["Watchdog", "Eos-Watchdog", "Eos"]
    alert_count = sum(freq.get(a, 0) for a in alert_agents)
    if alert_count > 20:
        findings.append(f"ALERT_STORM: {alert_count} alert messages in 6h — possible cascading failure")
    return findings


def calculate_system_health_score():
    """Composite health score 0-100 with explanations."""
    scores = {}
    explanations = []
    history = get_soma_history()

    # RAM health (weight: 25)
    ram = history.get("ram", [])
    if ram:
        current_ram = ram[-1] if isinstance(ram[-1], (int, float)) else 0
        ram_score = max(0, 100 - current_ram * 1.2)
        scores["ram"] = ram_score * 0.25
        if current_ram > 80:
            explanations.append(f"RAM critical at {current_ram}%")
        elif current_ram > 60:
            explanations.append(f"RAM elevated at {current_ram}%")
    else:
        scores["ram"] = 20 * 0.25

    # Load health (weight: 20)
    load = history.get("load", [])
    if load:
        current_load = load[-1] if isinstance(load[-1], (int, float)) else 0
        load_score = max(0, 100 - current_load * 25)
        scores["load"] = load_score * 0.20
        if current_load > 3:
            explanations.append(f"CPU load high at {current_load}")
    else:
        scores["load"] = 15 * 0.20

    # Disk health (weight: 25)
    disk = history.get("disk", [])
    if disk:
        current_disk = disk[-1] if isinstance(disk[-1], (int, float)) else 0
        disk_score = max(0, 100 - current_disk * 1.5)
        scores["disk"] = disk_score * 0.25
        if current_disk > 85:
            explanations.append(f"Disk critical at {current_disk}%")
        elif current_disk > 70:
            explanations.append(f"Disk elevated at {current_disk}%")
    else:
        scores["disk"] = 15 * 0.25

    # Heartbeat health (weight: 15)
    try:
        hb_age = time.time() - os.path.getmtime(os.path.join(BASE, ".heartbeat"))
        if hb_age < 300:
            scores["heartbeat"] = 100 * 0.15
        elif hb_age < 600:
            scores["heartbeat"] = 60 * 0.15
            explanations.append(f"Heartbeat aging ({int(hb_age)}s)")
        else:
            scores["heartbeat"] = 10 * 0.15
            explanations.append(f"Heartbeat STALE ({int(hb_age)}s)")
    except Exception:
        scores["heartbeat"] = 0
        explanations.append("Heartbeat file missing")

    # Agent health (weight: 15)
    freq = get_relay_frequency(hours=1)
    active_agents = sum(1 for c in freq.values() if c > 0)
    agent_score = min(100, active_agents * 15)
    scores["agents"] = agent_score * 0.15
    if active_agents < 3:
        explanations.append(f"Only {active_agents} agents active in last hour")

    total = sum(scores.values())
    return {
        "score": round(total, 1),
        "components": {k: round(v, 1) for k, v in scores.items()},
        "status": "healthy" if total > 70 else "warning" if total > 40 else "critical",
        "explanations": explanations,
    }


def run_full_analysis():
    """Full predictive analysis cycle."""
    state = load_state()
    predictions = []
    anomalies_found = []
    history = get_soma_history()

    # Trend analysis and forecasting
    for metric, label, max_val in [
        ("ram", "RAM", 100),
        ("disk", "Disk", 100),
        ("load", "CPU Load", 4),
    ]:
        values = history.get(metric, [])
        if not values:
            continue
        nums = []
        for v in values:
            if isinstance(v, (int, float)):
                nums.append(v)
            elif isinstance(v, str):
                try:
                    nums.append(float(v))
                except ValueError:
                    pass
        if len(nums) < 5:
            continue

        # Anomaly detection
        anoms = detect_anomalies(nums, label)
        if anoms:
            anomalies_found.extend(anoms)

        # Exhaustion forecast
        forecast = forecast_exhaustion(nums, label, max_val=max_val)
        if forecast and forecast.get("hours_to_exhaust", 999) < 24:
            predictions.append(forecast)

    # Relay pattern anomalies
    relay_findings = detect_relay_anomalies()
    for finding in relay_findings:
        anomalies_found.append({"label": "relay", "description": finding})

    # Health score
    health = calculate_system_health_score()

    # Build summary
    summary_parts = [f"Health: {health['score']}/100 ({health['status']})"]
    if predictions:
        for p in predictions:
            summary_parts.append(
                f"FORECAST: {p['label']} exhaustion in ~{p['hours_to_exhaust']}h "
                f"(rate: {p['rate']}/h, confidence: {p['confidence']})"
            )
    if anomalies_found:
        anom_labels = set()
        for a in anomalies_found:
            if "description" in a:
                anom_labels.add(a["description"])
            else:
                anom_labels.add(f"{a['label']} {a['direction']} (z={a['z_score']})")
        summary_parts.append(f"Anomalies: {'; '.join(list(anom_labels)[:5])}")
    if health["explanations"]:
        summary_parts.append(f"Notes: {'; '.join(health['explanations'][:3])}")

    summary = " | ".join(summary_parts)

    # Post to relay
    post_to_relay(summary, topic="prediction")
    log(summary)

    # Save state
    state["predictions"] = predictions
    state["anomalies"] = [str(a) for a in anomalies_found[:20]]
    state["health"] = health
    state["summary"] = summary
    save_state(state)

    return {"predictions": predictions, "anomalies": anomalies_found, "health": health}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "forecast":
        history = get_soma_history()
        for metric, label, max_val in [("ram", "RAM", 100), ("disk", "Disk", 100), ("load", "Load", 4)]:
            vals = [v for v in history.get(metric, []) if isinstance(v, (int, float))]
            forecast = forecast_exhaustion(vals, label, max_val=max_val)
            if forecast:
                print(f"{label}: exhaustion in {forecast['hours_to_exhaust']}h (rate: {forecast['rate']}/h, conf: {forecast['confidence']})")
            else:
                print(f"{label}: stable (no exhaustion predicted)")

    elif mode == "anomalies":
        history = get_soma_history()
        for metric, label in [("ram", "RAM"), ("disk", "Disk"), ("load", "Load")]:
            vals = [v for v in history.get(metric, []) if isinstance(v, (int, float))]
            anoms = detect_anomalies(vals, label)
            if anoms:
                for a in anoms:
                    print(f"ANOMALY: {a['label']} {a['direction']} at index {a['index']}, value={a['value']}, z={a['z_score']}")
        relay_anoms = detect_relay_anomalies()
        for r in relay_anoms:
            print(f"RELAY: {r}")

    elif mode == "health":
        health = calculate_system_health_score()
        print(f"Score: {health['score']}/100 ({health['status']})")
        for k, v in health["components"].items():
            print(f"  {k}: {v}")
        if health["explanations"]:
            print("Notes:")
            for e in health["explanations"]:
                print(f"  - {e}")

    else:
        result = run_full_analysis()
        if not result["predictions"] and not result["anomalies"]:
            log("All clear — no anomalies or concerning trends detected")


if __name__ == "__main__":
    main()
