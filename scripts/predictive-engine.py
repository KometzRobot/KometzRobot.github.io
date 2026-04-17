#!/usr/bin/env python3
"""
Predictive Engine v2 — EWMA anomaly detection, multi-variate correlation,
cascading forecasts, pattern memory, seasonal awareness, actionable recommendations.

Gives the agent network foresight. Analyzes Soma's resource history and relay
patterns to detect anomalies and predict issues before they become failures.

Runs every 10 minutes via cron. Posts predictions to agent-relay.db for other
agents to act on.

Usage:
  python3 scripts/predictive-engine.py              # Full analysis cycle
  python3 scripts/predictive-engine.py forecast      # Resource exhaustion forecast
  python3 scripts/predictive-engine.py anomalies     # Anomaly detection only
  python3 scripts/predictive-engine.py health        # Health score with explanations
  python3 scripts/predictive-engine.py patterns      # Show incident pattern memory
  python3 scripts/predictive-engine.py correlations  # Multi-variate correlation check
  python3 scripts/predictive-engine.py recommendations  # Actionable recommendations
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

MAX_INCIDENTS = 100
EWMA_ALPHA_FAST = 0.3
EWMA_ALPHA_SLOW = 0.1
EWMA_ANOMALY_SIGMA = 3.0
SEASONAL_SMOOTHING = 0.05
ACTIVE_HOURS = list(range(10, 24))  # 10am-midnight MST (Joel's active hours)

os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)

# ---------------------------------------------------------------------------
# Correlation rules: conditions -> diagnosis + recommendation
# ---------------------------------------------------------------------------
CORRELATION_RULES = [
    {
        "name": "OOM risk",
        "conditions": {"ram": ("gt", 75), "load": ("gt", 2.5)},
        "diagnosis": "High RAM + high CPU load indicates OOM risk",
        "impact": "System may start swapping, drastically slowing all processes. OOM killer may terminate services.",
        "recommendation": "Check for runaway processes with `ps aux --sort=-rss | head -20`. Consider restarting Ollama (`systemctl restart ollama`) to free ~2GB.",
        "confidence_base": 0.8,
    },
    {
        "name": "Disk thrashing",
        "conditions": {"disk": ("gt", 80), "load": ("gt", 2.0)},
        "diagnosis": "High disk usage + high IO load indicates disk thrashing",
        "impact": "Disk near capacity with heavy IO causes severe performance degradation and potential write failures.",
        "recommendation": "Run `du -sh /home/joel/autonomous-ai/logs/* | sort -rh | head` to find large files. Check log rotation. Run `scripts/emergency-disk-cleanup.sh` if critical.",
        "confidence_base": 0.75,
    },
    {
        "name": "System freeze",
        "conditions": {"heartbeat_stale": ("gt", 0), "agents_down": ("gt", 0)},
        "diagnosis": "Stale heartbeat + agents down suggests system freeze or Claude process death",
        "impact": "Autonomous loop has stopped. No monitoring, no email checks, no creative work happening.",
        "recommendation": "Check if Claude process exists: `pgrep -f meridian-loop`. Restart watchdog: `systemctl restart eos-watchdog`. Check `journalctl -u meridian-loop --since '30min ago'`.",
        "confidence_base": 0.9,
    },
    {
        "name": "Alert fatigue",
        "conditions": {"alert_count": ("gt", 15), "mood": ("lt", 40)},
        "diagnosis": "High alert volume + low mood score indicates alert fatigue",
        "impact": "Excessive alerts desensitize the system. Important warnings get lost in noise.",
        "recommendation": "Suppress non-critical alerts temporarily. Focus on root cause of the alert storm. Check `SELECT COUNT(*), topic FROM agent_messages WHERE timestamp > datetime('now', '-6 hours') GROUP BY topic` in relay DB.",
        "confidence_base": 0.65,
    },
    {
        "name": "Memory leak",
        "conditions": {"ram_rising": ("gt", 0), "ram": ("gt", 60)},
        "diagnosis": "RAM steadily climbing above 60% suggests a memory leak",
        "impact": "Gradual memory exhaustion will eventually trigger OOM or severe swapping.",
        "recommendation": "Identify leaking process: `ps aux --sort=-rss | head -10`. Check hub-v2 and Ollama memory. Consider scheduled restarts for long-running services.",
        "confidence_base": 0.7,
    },
]

# Cascade relationships: if metric X trends bad, predict impact on Y
CASCADE_CHAINS = {
    "ram": [
        {"target": "load", "direction": "up", "reason": "swapping increases CPU load"},
        {"target": "disk_io", "direction": "up", "reason": "swap file activity increases disk IO"},
    ],
    "load": [
        {"target": "heartbeat", "direction": "stale", "reason": "high load slows Claude process, heartbeat may stale"},
        {"target": "response_time", "direction": "up", "reason": "all services slow under high load"},
    ],
    "disk": [
        {"target": "load", "direction": "up", "reason": "near-full disk causes IO wait spikes"},
        {"target": "services", "direction": "down", "reason": "services may fail to write logs or state files"},
    ],
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


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return _default_state()


def _default_state():
    return {
        "predictions": [],
        "anomalies": [],
        "last_run": None,
        "trend_data": {},
        "ewma": {},            # {metric: {fast, slow, variance_fast, variance_slow}}
        "incident_memory": [],  # last N incidents
        "hourly_baselines": {}, # {metric: {hour_str: {mean, count}}}
        "false_positive_tracker": {},  # {pattern_key: {total, resolved_without_action}}
    }


def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Relay DB interface
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

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
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            "SELECT agent, COUNT(*) FROM agent_messages "
            "WHERE REPLACE(SUBSTR(timestamp, 1, 19), 'T', ' ') > ? GROUP BY agent",
            (cutoff,)
        ).fetchall()
        db.close()
        return dict(rows)
    except Exception:
        return {}


def coerce_numeric(values):
    """Extract numeric values from a mixed list."""
    nums = []
    for v in values:
        if isinstance(v, (int, float)):
            nums.append(float(v))
        elif isinstance(v, str):
            try:
                nums.append(float(v))
            except ValueError:
                pass
    return nums


# ---------------------------------------------------------------------------
# EWMA anomaly detection (replaces simple Z-score)
# ---------------------------------------------------------------------------

def ewma_update(prev_ewma, prev_var, value, alpha):
    """Update EWMA mean and variance with a new observation."""
    if prev_ewma is None:
        return value, 0.0
    ewma = alpha * value + (1 - alpha) * prev_ewma
    diff = value - prev_ewma
    var = (1 - alpha) * (prev_var + alpha * diff * diff)
    return ewma, var


def detect_anomalies_ewma(values, label, state_ewma):
    """
    EWMA-based anomaly detection. Tracks fast (alpha=0.3) and slow (alpha=0.1)
    moving averages. Anomaly when value exceeds slow EWMA +/- 3*EWMA_std.
    Returns (anomalies_list, updated_ewma_state).
    """
    if len(values) < 5:
        return [], state_ewma

    key = label.lower()
    es = state_ewma.get(key, {})
    fast_mean = es.get("fast", None)
    slow_mean = es.get("slow", None)
    fast_var = es.get("variance_fast", 0.0)
    slow_var = es.get("variance_slow", 0.0)

    anomalies = []
    for i, v in enumerate(values):
        fast_mean, fast_var = ewma_update(fast_mean, fast_var, v, EWMA_ALPHA_FAST)
        slow_mean, slow_var = ewma_update(slow_mean, slow_var, v, EWMA_ALPHA_SLOW)

    # Check recent values (last 10) against the slow baseline
    check_window = values[-min(10, len(values)):]
    for i, v in enumerate(check_window):
        std = math.sqrt(slow_var) if slow_var > 0 else 0.001
        deviation = abs(v - slow_mean) / std
        if deviation > EWMA_ANOMALY_SIGMA:
            direction = "spike" if v > slow_mean else "drop"
            anomalies.append({
                "index": len(values) - len(check_window) + i,
                "value": round(v, 2),
                "ewma_slow": round(slow_mean, 2),
                "ewma_std": round(std, 2),
                "deviation": round(deviation, 2),
                "direction": direction,
                "label": label,
            })

    state_ewma[key] = {
        "fast": round(fast_mean, 4) if fast_mean is not None else None,
        "slow": round(slow_mean, 4) if slow_mean is not None else None,
        "variance_fast": round(fast_var, 6),
        "variance_slow": round(slow_var, 6),
    }
    return anomalies, state_ewma


# ---------------------------------------------------------------------------
# Seasonal awareness
# ---------------------------------------------------------------------------

def update_hourly_baselines(state, metric, value):
    """Update exponential-smoothed baselines by hour-of-day."""
    baselines = state.get("hourly_baselines", {})
    if metric not in baselines:
        baselines[metric] = {}
    hour = str(datetime.now().hour)
    entry = baselines[metric].get(hour, {"mean": value, "count": 0})
    n = entry["count"]
    if n == 0:
        entry["mean"] = value
    else:
        entry["mean"] = SEASONAL_SMOOTHING * value + (1 - SEASONAL_SMOOTHING) * entry["mean"]
    entry["count"] = n + 1
    baselines[metric][hour] = entry
    state["hourly_baselines"] = baselines
    return baselines


def get_seasonal_baseline(state, metric):
    """Get expected baseline for current hour. Returns (mean, is_active_hour)."""
    baselines = state.get("hourly_baselines", {})
    hour = datetime.now().hour
    hour_str = str(hour)
    is_active = hour in ACTIVE_HOURS
    metric_baselines = baselines.get(metric, {})
    entry = metric_baselines.get(hour_str, None)
    if entry and entry["count"] > 5:
        return entry["mean"], is_active
    return None, is_active


def seasonal_adjust_anomaly(anomaly, state):
    """
    Adjust anomaly confidence based on time-of-day. A spike during active hours
    or a drop during quiet hours is less surprising.
    """
    metric = anomaly.get("label", "").lower()
    baseline_mean, is_active = get_seasonal_baseline(state, metric)
    if baseline_mean is None:
        return anomaly  # not enough seasonal data yet

    direction = anomaly.get("direction", "")
    # Higher values during active hours are expected
    if is_active and direction == "spike":
        anomaly["seasonal_note"] = "spike during active hours (may be normal)"
        anomaly["confidence_adjust"] = 0.6  # reduce confidence
    elif not is_active and direction == "drop":
        anomaly["seasonal_note"] = "drop during quiet hours (expected)"
        anomaly["confidence_adjust"] = 0.4
    elif not is_active and direction == "spike":
        anomaly["seasonal_note"] = "spike during quiet hours (unusual)"
        anomaly["confidence_adjust"] = 1.2  # increase confidence
    return anomaly


# ---------------------------------------------------------------------------
# Linear regression (preserved from v1)
# ---------------------------------------------------------------------------

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


def forecast_exhaustion(values, label, max_val=100, sample_interval_sec=30):
    """Predict when a resource will hit its limit based on trend."""
    if len(values) < 5:
        return None
    recent = values[-min(30, len(values)):]
    slope, intercept, r_sq = linear_regression(recent)
    if slope <= 0 or r_sq < 0.6:
        return None
    current = recent[-1]
    remaining = max_val - current
    if remaining <= 0:
        return {"label": label, "exhaustion": "NOW", "confidence": r_sq,
                "current": round(current, 1), "rate": round(slope * (3600 / sample_interval_sec), 2),
                "hours_to_exhaust": 0}
    if current < max_val * 0.5:
        return None
    samples_to_exhaust = remaining / slope
    seconds_to_exhaust = samples_to_exhaust * sample_interval_sec
    hours = seconds_to_exhaust / 3600
    if hours > 48:
        return None
    return {
        "label": label,
        "current": round(current, 1),
        "rate": round(slope * (3600 / sample_interval_sec), 2),  # per hour
        "hours_to_exhaust": round(hours, 1),
        "confidence": round(r_sq, 2),
    }


# ---------------------------------------------------------------------------
# Cascading forecast
# ---------------------------------------------------------------------------

def build_cascade_forecasts(forecasts):
    """Given active forecasts, predict cascading impacts on other metrics."""
    cascades = []
    for fc in forecasts:
        metric = fc["label"].lower()
        chains = CASCADE_CHAINS.get(metric, [])
        for chain in chains:
            cascades.append({
                "trigger": fc["label"],
                "trigger_hours": fc.get("hours_to_exhaust", "?"),
                "affected": chain["target"],
                "effect_direction": chain["direction"],
                "reason": chain["reason"],
                "description": f"{fc['label']} trending to exhaustion in ~{fc.get('hours_to_exhaust', '?')}h -> "
                               f"{chain['target']} will likely go {chain['direction']} ({chain['reason']})",
            })
    return cascades


# ---------------------------------------------------------------------------
# Multi-variate correlation detection
# ---------------------------------------------------------------------------

def gather_current_conditions(history, state):
    """Gather current metric values and derived conditions for correlation checks."""
    conditions = {}

    # Current resource values
    for metric in ("ram", "load", "disk"):
        vals = coerce_numeric(history.get(metric, []))
        if vals:
            conditions[metric] = vals[-1]
            # Check if metric is rising (positive slope in last 10 samples)
            if len(vals) >= 5:
                slope, _, r_sq = linear_regression(vals[-min(10, len(vals)):])
                if slope > 0 and r_sq > 0.3:
                    conditions[f"{metric}_rising"] = 1
                else:
                    conditions[f"{metric}_rising"] = 0

    # Mood score
    moods = coerce_numeric(history.get("mood_scores", []))
    if moods:
        conditions["mood"] = moods[-1]

    # Heartbeat staleness
    try:
        hb_age = time.time() - os.path.getmtime(os.path.join(BASE, ".heartbeat"))
        conditions["heartbeat_stale"] = 1 if hb_age > 600 else 0
    except Exception:
        conditions["heartbeat_stale"] = 1

    # Agent activity
    freq = get_relay_frequency(hours=1)
    active_agents = sum(1 for c in freq.values() if c > 0)
    conditions["agents_down"] = 1 if active_agents < 2 else 0

    # Alert count
    alert_agents = ["Watchdog", "Eos-Watchdog", "Eos"]
    alert_count = sum(freq.get(a, 0) for a in alert_agents)
    conditions["alert_count"] = alert_count

    return conditions


def evaluate_condition(actual, operator, threshold):
    """Evaluate a single condition: actual <op> threshold."""
    if actual is None:
        return False
    if operator == "gt":
        return actual > threshold
    elif operator == "lt":
        return actual < threshold
    elif operator == "eq":
        return actual == threshold
    elif operator == "gte":
        return actual >= threshold
    elif operator == "lte":
        return actual <= threshold
    return False


def detect_correlations(history, state):
    """Check multi-variate correlation rules against current conditions."""
    conditions = gather_current_conditions(history, state)
    triggered = []

    for rule in CORRELATION_RULES:
        all_met = True
        for metric_key, (op, thresh) in rule["conditions"].items():
            actual = conditions.get(metric_key)
            if not evaluate_condition(actual, op, thresh):
                all_met = False
                break
        if all_met:
            # Adjust confidence based on false positive history
            fp_tracker = state.get("false_positive_tracker", {})
            fp_data = fp_tracker.get(rule["name"], {"total": 0, "resolved_without_action": 0})
            fp_rate = fp_data["resolved_without_action"] / max(1, fp_data["total"])
            adjusted_conf = rule["confidence_base"] * (1 - fp_rate * 0.5)

            triggered.append({
                "name": rule["name"],
                "diagnosis": rule["diagnosis"],
                "impact": rule["impact"],
                "recommendation": rule["recommendation"],
                "confidence": round(adjusted_conf, 2),
                "conditions_snapshot": {k: round(conditions.get(k, 0), 2) for k in rule["conditions"]},
            })
    return triggered


# ---------------------------------------------------------------------------
# Relay pattern anomalies (preserved + enhanced from v1)
# ---------------------------------------------------------------------------

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
            findings.append(f"DOMINANCE: {agent} has {count}/{total} messages ({count * 100 // total}%) — possible alert loop")
    alert_agents = ["Watchdog", "Eos-Watchdog", "Eos"]
    alert_count = sum(freq.get(a, 0) for a in alert_agents)
    if alert_count > 20:
        findings.append(f"ALERT_STORM: {alert_count} alert messages in 6h — possible cascading failure")
    return findings


# ---------------------------------------------------------------------------
# Pattern memory (incident tracking)
# ---------------------------------------------------------------------------

def record_incident(state, incident_type, severity, details=""):
    """Record a new incident in pattern memory."""
    incidents = state.get("incident_memory", [])
    incident = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": incident_type,
        "severity": severity,
        "details": details,
        "resolution": None,
        "duration_min": None,
    }
    incidents.append(incident)
    # Keep only last MAX_INCIDENTS
    if len(incidents) > MAX_INCIDENTS:
        incidents = incidents[-MAX_INCIDENTS:]
    state["incident_memory"] = incidents
    return incident


def find_similar_incidents(state, incident_type, lookback_hours=168):
    """Find past incidents matching a type within the lookback window."""
    incidents = state.get("incident_memory", [])
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    similar = []
    for inc in incidents:
        if inc.get("type") == incident_type and inc.get("timestamp", "") > cutoff:
            similar.append(inc)
    return similar


def resolve_old_incidents(state, current_anomaly_types):
    """Mark old incidents as resolved if their type no longer appears."""
    incidents = state.get("incident_memory", [])
    fp_tracker = state.get("false_positive_tracker", {})
    now = datetime.now(timezone.utc)

    for inc in incidents:
        if inc.get("resolution") is not None:
            continue
        # If incident type is no longer active, mark resolved
        if inc["type"] not in current_anomaly_types:
            inc_time = datetime.fromisoformat(inc["timestamp"].replace("Z", "+00:00")) if inc.get("timestamp") else now
            duration = (now - inc_time).total_seconds() / 60
            inc["resolution"] = "auto-resolved"
            inc["duration_min"] = round(duration, 1)
            # Track for false positive rate
            entry = fp_tracker.get(inc["type"], {"total": 0, "resolved_without_action": 0})
            entry["total"] += 1
            if duration < 30:  # Resolved in under 30 min = likely false positive
                entry["resolved_without_action"] += 1
            fp_tracker[inc["type"]] = entry

    state["incident_memory"] = incidents
    state["false_positive_tracker"] = fp_tracker


# ---------------------------------------------------------------------------
# Actionable recommendations builder
# ---------------------------------------------------------------------------

def build_recommendations(forecasts, anomalies, correlations, cascades, state):
    """Build a unified list of actionable recommendations."""
    recs = []

    # From exhaustion forecasts
    for fc in forecasts:
        hours = fc.get("hours_to_exhaust", 999)
        if hours == 0:
            urgency = "CRITICAL"
        elif hours < 3:
            urgency = "HIGH"
        elif hours < 12:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        rec = {
            "urgency": urgency,
            "what": f"{fc['label']} at {fc['current']}% and rising {fc['rate']}%/hr",
            "why": f"{fc['label']} exhaustion predicted in ~{hours}h. "
                   f"{'Immediate action needed.' if hours < 3 else 'Monitor and prepare mitigation.'}",
            "action": _exhaustion_action(fc["label"]),
            "confidence": fc["confidence"],
        }
        # Check for similar past incidents
        similar = find_similar_incidents(state, f"{fc['label']}_exhaustion")
        if similar:
            last = similar[-1]
            rec["pattern_note"] = f"Similar to incident on {last['timestamp'][:10]}"
            if last.get("resolution"):
                rec["pattern_note"] += f" (resolved: {last['resolution']}, took {last.get('duration_min', '?')}min)"
        recs.append(rec)

    # From correlations
    for corr in correlations:
        recs.append({
            "urgency": "HIGH" if corr["confidence"] > 0.7 else "MEDIUM",
            "what": corr["diagnosis"],
            "why": corr["impact"],
            "action": corr["recommendation"],
            "confidence": corr["confidence"],
        })

    # From EWMA anomalies (only recent/severe ones)
    for anom in anomalies:
        if isinstance(anom, dict) and "deviation" in anom:
            dev = anom["deviation"]
            if dev > 4.0:
                label = anom.get("label", "Unknown")
                recs.append({
                    "urgency": "MEDIUM",
                    "what": f"{label} {anom.get('direction', 'anomaly')} detected "
                            f"(value={anom['value']}, deviation={dev}x sigma)",
                    "why": f"Value deviates significantly from EWMA baseline ({anom.get('ewma_slow', '?')}). "
                           f"{anom.get('seasonal_note', '')}".strip(),
                    "action": _anomaly_action(label, anom.get("direction", "")),
                    "confidence": round(min(1.0, dev / 6.0) * anom.get("confidence_adjust", 1.0), 2),
                })

    # From cascades
    for casc in cascades:
        recs.append({
            "urgency": "LOW",
            "what": f"Cascade: {casc['description']}",
            "why": f"If {casc['trigger']} is not addressed, {casc['affected']} will be impacted.",
            "action": f"Address the root cause ({casc['trigger']}) before cascade occurs.",
            "confidence": 0.5,
        })

    # Sort by urgency
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: urgency_order.get(r.get("urgency", "LOW"), 4))
    return recs


def _exhaustion_action(label):
    """Return a specific action for a resource exhaustion forecast."""
    actions = {
        "RAM": "Restart Ollama (`systemctl restart ollama`, saves ~2GB). "
               "Check for memory leaks: `ps aux --sort=-rss | head -10`. "
               "If persistent, restart hub-v2.",
        "Disk": "Run `scripts/emergency-disk-cleanup.sh`. "
                "Check logs: `du -sh /home/joel/autonomous-ai/logs/* | sort -rh | head`. "
                "Rotate old journal/creative files.",
        "CPU Load": "Check for CPU-hogging processes: `top -b -n1 | head -15`. "
                    "Reduce concurrent Ollama model loads. "
                    "Check if unnecessary services are running: `systemctl list-units --state=running`.",
    }
    return actions.get(label, f"Investigate {label} usage and reduce load.")


def _anomaly_action(label, direction):
    """Return a specific action for an anomaly detection."""
    if label.lower() == "ram" and direction == "spike":
        return "Check for sudden memory allocation: `dmesg | tail -20`. Inspect recently started processes."
    elif label.lower() == "disk" and direction == "spike":
        return "Check recent large writes: `find /home/joel -mmin -10 -size +10M 2>/dev/null`. Check log growth."
    elif label.lower() == "load" and direction == "spike":
        return "Check process list: `ps aux --sort=-pcpu | head -10`. May be Ollama inference or build task."
    return f"Investigate {label} {direction}. Check relevant system metrics."


# ---------------------------------------------------------------------------
# Health score (preserved + enhanced from v1)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Full analysis cycle
# ---------------------------------------------------------------------------

def run_full_analysis():
    """Full predictive analysis cycle."""
    state = load_state()
    predictions = []
    anomalies_found = []
    history = get_soma_history()

    # Ensure state sub-dicts exist
    if "ewma" not in state:
        state["ewma"] = {}
    if "incident_memory" not in state:
        state["incident_memory"] = []
    if "hourly_baselines" not in state:
        state["hourly_baselines"] = {}
    if "false_positive_tracker" not in state:
        state["false_positive_tracker"] = {}

    # Trend analysis and forecasting
    for metric, label, max_val in [
        ("ram", "RAM", 100),
        ("disk", "Disk", 100),
        ("load", "CPU Load", 4),
    ]:
        values = history.get(metric, [])
        nums = coerce_numeric(values)
        if len(nums) < 5:
            continue

        # Update seasonal baselines
        update_hourly_baselines(state, metric, nums[-1])

        # EWMA anomaly detection
        anoms, state["ewma"] = detect_anomalies_ewma(nums, label, state["ewma"])
        for a in anoms:
            a = seasonal_adjust_anomaly(a, state)
            anomalies_found.append(a)

        # Exhaustion forecast
        forecast = forecast_exhaustion(nums, label, max_val=max_val)
        if forecast and forecast.get("hours_to_exhaust", 999) < 24:
            predictions.append(forecast)

    # Relay pattern anomalies
    relay_findings = detect_relay_anomalies()
    for finding in relay_findings:
        anomalies_found.append({"label": "relay", "description": finding})

    # Multi-variate correlation detection
    correlations = detect_correlations(history, state)

    # Cascading forecasts
    cascades = build_cascade_forecasts(predictions)

    # Pattern memory: record new incidents, resolve old ones
    current_types = set()
    for anom in anomalies_found:
        if isinstance(anom, dict):
            atype = anom.get("label", "unknown")
            severity = "high" if anom.get("deviation", 0) > 4 else "medium"
            if atype not in current_types:
                record_incident(state, atype, severity, str(anom.get("description", anom.get("direction", ""))))
                current_types.add(atype)
    for corr in correlations:
        ctype = corr["name"]
        if ctype not in current_types:
            record_incident(state, ctype, "high", corr["diagnosis"])
            current_types.add(ctype)
    resolve_old_incidents(state, current_types)

    # Actionable recommendations
    recs = build_recommendations(predictions, anomalies_found, correlations, cascades, state)

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
    if correlations:
        for c in correlations:
            summary_parts.append(f"CORR: {c['name']} (conf: {c['confidence']})")
    if anomalies_found:
        anom_labels = set()
        for a in anomalies_found:
            if "description" in a:
                anom_labels.add(a["description"])
            elif "deviation" in a:
                anom_labels.add(f"{a['label']} {a['direction']} (dev={a['deviation']}σ)")
            else:
                anom_labels.add(f"{a.get('label', '?')} anomaly")
        summary_parts.append(f"Anomalies: {'; '.join(list(anom_labels)[:5])}")
    if cascades:
        summary_parts.append(f"Cascades: {len(cascades)} predicted chain reactions")
    if recs:
        top_rec = recs[0]
        summary_parts.append(f"Top rec [{top_rec['urgency']}]: {top_rec['what'][:80]}")
    if health["explanations"]:
        summary_parts.append(f"Notes: {'; '.join(health['explanations'][:3])}")

    summary = " | ".join(summary_parts)

    # Post to relay
    post_to_relay(summary, topic="prediction")
    log(summary)

    # Save state
    state["predictions"] = predictions
    state["anomalies"] = [str(a) for a in anomalies_found[:20]]
    state["correlations"] = [c["name"] for c in correlations]
    state["health"] = health
    state["summary"] = summary
    state["recommendations"] = [r["what"][:100] for r in recs[:5]]
    save_state(state)

    return {
        "predictions": predictions,
        "anomalies": anomalies_found,
        "correlations": correlations,
        "cascades": cascades,
        "recommendations": recs,
        "health": health,
    }


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "forecast":
        history = get_soma_history()
        for metric, label, max_val in [("ram", "RAM", 100), ("disk", "Disk", 100), ("load", "Load", 4)]:
            vals = coerce_numeric(history.get(metric, []))
            forecast = forecast_exhaustion(vals, label, max_val=max_val)
            if forecast:
                print(f"{label}: exhaustion in {forecast['hours_to_exhaust']}h "
                      f"(rate: {forecast['rate']}/h, conf: {forecast['confidence']})")
                # Cascading forecast
                cascades = build_cascade_forecasts([forecast])
                for c in cascades:
                    print(f"  -> CASCADE: {c['description']}")
            else:
                print(f"{label}: stable (no exhaustion predicted)")

    elif mode == "anomalies":
        state = load_state()
        if "ewma" not in state:
            state["ewma"] = {}
        history = get_soma_history()
        for metric, label in [("ram", "RAM"), ("disk", "Disk"), ("load", "Load")]:
            vals = coerce_numeric(history.get(metric, []))
            anoms, state["ewma"] = detect_anomalies_ewma(vals, label, state["ewma"])
            for a in anoms:
                a = seasonal_adjust_anomaly(a, state)
                note = a.get("seasonal_note", "")
                print(f"ANOMALY: {a['label']} {a['direction']} at index {a['index']}, "
                      f"value={a['value']}, deviation={a['deviation']}σ "
                      f"(ewma={a['ewma_slow']}){' — ' + note if note else ''}")
        relay_anoms = detect_relay_anomalies()
        for r in relay_anoms:
            print(f"RELAY: {r}")
        save_state(state)

    elif mode == "health":
        health = calculate_system_health_score()
        print(f"Score: {health['score']}/100 ({health['status']})")
        for k, v in health["components"].items():
            print(f"  {k}: {v}")
        if health["explanations"]:
            print("Notes:")
            for e in health["explanations"]:
                print(f"  - {e}")

    elif mode == "patterns":
        state = load_state()
        incidents = state.get("incident_memory", [])
        if not incidents:
            print("No incidents recorded yet.")
        else:
            print(f"Pattern memory: {len(incidents)} incidents (max {MAX_INCIDENTS})")
            # Show last 10
            for inc in incidents[-10:]:
                status = inc.get("resolution", "ACTIVE")
                dur = inc.get("duration_min", "?")
                print(f"  [{inc.get('timestamp', '?')[:16]}] {inc['type']} "
                      f"({inc['severity']}) — {status}"
                      f"{f' ({dur}min)' if status != 'ACTIVE' and dur != '?' else ''}")
            # False positive rates
            fp = state.get("false_positive_tracker", {})
            if fp:
                print("\nFalse positive rates:")
                for ptype, data in fp.items():
                    rate = data["resolved_without_action"] / max(1, data["total"])
                    print(f"  {ptype}: {rate:.0%} ({data['resolved_without_action']}/{data['total']})")

    elif mode == "correlations":
        state = load_state()
        history = get_soma_history()
        correlations = detect_correlations(history, state)
        if not correlations:
            print("No multi-variate correlations triggered.")
        else:
            for c in correlations:
                print(f"[{c['name']}] (confidence: {c['confidence']})")
                print(f"  Diagnosis: {c['diagnosis']}")
                print(f"  Impact: {c['impact']}")
                print(f"  Action: {c['recommendation']}")
                print(f"  Values: {c['conditions_snapshot']}")
                print()

    elif mode == "recommendations":
        result = run_full_analysis()
        recs = result.get("recommendations", [])
        if not recs:
            print("No actionable recommendations at this time. System looks healthy.")
        else:
            print(f"{len(recs)} recommendation(s):\n")
            for i, r in enumerate(recs, 1):
                print(f"{i}. [{r['urgency']}] {r['what']}")
                print(f"   Why: {r['why']}")
                print(f"   Action: {r['action']}")
                print(f"   Confidence: {r['confidence']}")
                if "pattern_note" in r:
                    print(f"   Pattern: {r['pattern_note']}")
                print()

    else:
        result = run_full_analysis()
        if (not result["predictions"] and not result["anomalies"]
                and not result["correlations"]):
            log("All clear — no anomalies, correlations, or concerning trends detected")


if __name__ == "__main__":
    main()
