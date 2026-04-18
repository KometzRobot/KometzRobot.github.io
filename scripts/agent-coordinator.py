#!/usr/bin/env python3
"""
Agent Coordinator v2 — Event bus, task routing, deduplication, incident lifecycle,
capability registry, and agent performance tracking.

Prevents agent alert storms, coordinates responses, routes tasks by capability,
tracks incidents through full lifecycle, and monitors agent health over time.

Features:
- Capability registry (which agent can do what)
- Task queue with auto-assignment by capability match (SQLite)
- N-gram similarity deduplication (Jaccard on 3-grams, threshold 0.6)
- Incident lifecycle tracking (detected -> acknowledged -> resolved -> post_mortem)
- Root cause correlation (multi-incident pattern matching)
- Agent performance history with degradation detection
- Priority routing and agent health scoring

Usage:
  python3 scripts/agent-coordinator.py              # Full coordination cycle
  python3 scripts/agent-coordinator.py incidents     # Show active incidents
  python3 scripts/agent-coordinator.py scores        # Agent effectiveness scores
  python3 scripts/agent-coordinator.py dedupe        # Run deduplication pass
  python3 scripts/agent-coordinator.py tasks         # Show task queue
  python3 scripts/agent-coordinator.py capabilities  # Show capability registry
  python3 scripts/agent-coordinator.py history       # Agent performance history
"""

import json, os, re, sqlite3, sys, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

BASE = "/home/joel/autonomous-ai"
RELAY_DB = os.path.join(BASE, "agent-relay.db")
STATE_FILE = os.path.join(BASE, ".coordinator-state.json")
LOG_FILE = os.path.join(BASE, "logs", "agent-coordinator.log")
os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)

# ── Capability Registry ──────────────────────────────────────────────────────
CAPABILITY_REGISTRY = {
    "Eos":        ["monitoring", "alerting", "service_restart", "log_analysis"],
    "Nova":       ["maintenance", "cleanup", "deployment_check", "log_rotation"],
    "Atlas":      ["infra_audit", "security_scan", "disk_management", "cron_health"],
    "Soma":       ["proprioception", "mood_tracking", "body_state", "reflexes"],
    "Tempo":      ["fitness_scoring", "trend_detection", "metric_tracking"],
    "Sentinel":   ["gatekeeper", "escalation", "dream_trigger"],
    "Predictive": ["anomaly_detection", "forecasting", "health_scoring"],
    "Coordinator":["task_routing", "dedup", "incident_tracking"],
    "Hermes":     ["messaging", "telegram", "external_comms"],
}
CAPABILITY_TO_AGENTS = defaultdict(list)
for _agent, _caps in CAPABILITY_REGISTRY.items():
    for _cap in _caps:
        CAPABILITY_TO_AGENTS[_cap].append(_agent)

# ── Root Cause Correlation Rules ─────────────────────────────────────────────
CORRELATION_RULES = {
    "claude_or_ollama_crash": {
        "requires": ["heartbeat_stale", "service_failure"],
        "diagnosis": "Claude crashed or Ollama OOM — main loop and services both down",
        "severity": "critical",
    },
    "agent_crash_cascade": {
        "requires": ["alert_storm", "agent_silent"],
        "diagnosis": "An agent crashed and others are reacting to the gap",
        "severity": "critical",
    },
    "runaway_process": {
        "requires": ["high_load", "high_ram"],
        "diagnosis": "Runaway process consuming CPU and memory",
        "severity": "warning",
    },
    "storage_pressure": {
        "requires": ["disk_high", "service_failure"],
        "diagnosis": "Disk full causing service failures",
        "severity": "critical",
    },
}

INCIDENT_STATES = ["detected", "acknowledged", "investigating", "resolved", "post_mortem"]


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
        return {"incidents": [], "agent_scores": {}, "suppressed_count": 0,
                "last_run": None, "incident_history": [], "agent_performance_history": {}}


def save_state(state):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    if "incident_history" in state:
        state["incident_history"] = state["incident_history"][-50:]
    if "agent_performance_history" in state:
        for agent in state["agent_performance_history"]:
            state["agent_performance_history"][agent] = \
                state["agent_performance_history"][agent][-100:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── Task Queue (SQLite) ─────────────────────────────────────────────────────
def ensure_task_table():
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("""CREATE TABLE IF NOT EXISTS coordinator_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL,
            assigned_agent TEXT, requested_by TEXT,
            priority TEXT DEFAULT 'normal', status TEXT DEFAULT 'pending',
            created_at TEXT, updated_at TEXT, outcome TEXT)""")
        db.commit()
        db.close()
    except Exception as e:
        log(f"Task table init failed: {e}")


def create_task(task, requested_by="Coordinator", priority="normal", capability_needed=None):
    """Create a task and optionally auto-assign based on capability match."""
    ensure_task_table()
    now = datetime.now(timezone.utc).isoformat()
    assigned = None
    if capability_needed and capability_needed in CAPABILITY_TO_AGENTS:
        candidates = CAPABILITY_TO_AGENTS[capability_needed]
        if candidates:
            assigned = candidates[0]
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute(
            """INSERT INTO coordinator_tasks
               (task, assigned_agent, requested_by, priority, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task, assigned, requested_by, priority,
             "assigned" if assigned else "pending", now, now))
        db.commit()
        db.close()
        status_str = f"assigned to {assigned}" if assigned else "pending (no capability match)"
        log(f"Task created: {task[:60]} [{priority}] {status_str}")
    except Exception as e:
        log(f"Task creation failed: {e}")


def assign_task(task_id, agent):
    ensure_task_table()
    now = datetime.now(timezone.utc).isoformat()
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("UPDATE coordinator_tasks SET assigned_agent=?, status='assigned', updated_at=? WHERE id=?",
                   (agent, now, task_id))
        db.commit()
        db.close()
    except Exception as e:
        log(f"Task assign failed: {e}")


def complete_task(task_id, outcome="done"):
    ensure_task_table()
    now = datetime.now(timezone.utc).isoformat()
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("UPDATE coordinator_tasks SET status='done', outcome=?, updated_at=? WHERE id=?",
                   (outcome, now, task_id))
        db.commit()
        db.close()
    except Exception as e:
        log(f"Task complete failed: {e}")


def _fetch_tasks(where_clause="1=1", params=(), limit=20):
    """Shared task fetch helper."""
    ensure_task_table()
    try:
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            f"""SELECT id, task, assigned_agent, requested_by, priority, status,
                       created_at, updated_at, outcome
                FROM coordinator_tasks WHERE {where_clause}
                ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                  WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, created_at DESC
                LIMIT ?""", (*params, limit)).fetchall()
        db.close()
        return [{"id": r[0], "task": r[1], "assigned_agent": r[2], "requested_by": r[3],
                 "priority": r[4], "status": r[5], "created_at": r[6],
                 "updated_at": r[7], "outcome": r[8]} for r in rows]
    except Exception:
        return []


def get_pending_tasks():
    return _fetch_tasks("status IN ('pending','assigned','in_progress')")


def get_all_tasks(limit=20):
    return _fetch_tasks(limit=limit)


# ── N-gram Similarity Dedup ──────────────────────────────────────────────────
def extract_ngrams(text, n=3):
    text = re.sub(r'\s+', ' ', text.lower().strip())
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def get_recent_messages(hours=1):
    try:
        # Use space-separated format and normalize stored timestamps to match,
        # fixing the bug where 'T'-separated cutoffs cause SQLite text comparison
        # to miss space-separated timestamps (space < 'T' in ASCII).
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        db = sqlite3.connect(RELAY_DB, timeout=3)
        rows = db.execute(
            "SELECT id, agent, message, topic, timestamp FROM agent_messages "
            "WHERE REPLACE(SUBSTR(timestamp, 1, 19), 'T', ' ') > ? "
            "ORDER BY timestamp DESC", (cutoff,)).fetchall()
        db.close()
        return [{"id": r[0], "agent": r[1], "message": r[2],
                 "topic": r[3], "timestamp": r[4]} for r in rows]
    except Exception:
        return []


def normalize_message(msg):
    s = re.sub(r'\d+', 'N', msg.lower())
    return re.sub(r'\s+', ' ', s).strip()[:100]


def find_duplicates(messages, window_sec=600, similarity_threshold=0.6):
    """Find near-duplicate messages using n-gram Jaccard similarity."""
    duplicates = []
    seen = []  # (msg_dict, ngram_set)
    for msg in messages:
        msg_ngrams = extract_ngrams(normalize_message(msg["message"]))
        is_dup = False
        for prev_msg, prev_ngrams in seen:
            if prev_msg["agent"] != msg["agent"]:
                continue
            try:
                t1 = datetime.fromisoformat(prev_msg["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                if abs((t2 - t1).total_seconds()) > window_sec:
                    continue
            except Exception:
                continue
            if jaccard_similarity(msg_ngrams, prev_ngrams) >= similarity_threshold:
                duplicates.append(msg)
                is_dup = True
                break
        if not is_dup:
            seen.append((msg, msg_ngrams))
    return duplicates


# ── Incident Detection & Lifecycle ───────────────────────────────────────────
def detect_incidents(messages):
    """Detect active incidents from relay patterns."""
    incidents = []

    # Exclude Coordinator's own messages to prevent self-reinforcing feedback loops.
    # The Coordinator reports on incidents — counting its own reports as new alerts
    # creates a cycle where each report triggers the next.
    source_messages = [m for m in messages if m["agent"] != "Coordinator"]

    # For alert keyword counting, also exclude routine audit/analysis agents whose
    # messages contain alert keywords in non-alert contexts (e.g., Atlas "Stale crons"
    # is an informational audit, Eos "critical services running" is a positive status,
    # Predictive reports analysis not incidents).
    alert_excluded_agents = {"Coordinator", "Atlas", "Predictive", "SelfImprove"}
    alert_source = [m for m in messages if m["agent"] not in alert_excluded_agents]

    alert_keywords = {
        "critical": ["CRITICAL", "EMERGENCY", "DOWN", "FAILED", "CRASH"],
        "warning": ["STALE", "WARNING", "HIGH", "SPIKE", "ELEVATED"],
        "info": ["RESTART", "RECOVERED", "BACK", "RESOLVED"],
    }
    keyword_counts = {"critical": 0, "warning": 0, "info": 0}
    for msg in alert_source:
        text = msg["message"].upper()
        for severity, keywords in alert_keywords.items():
            if any(kw in text for kw in keywords):
                keyword_counts[severity] += 1
                break

    # Pattern detectors: (filter_fn, min_count, type, severity, desc_template)
    pattern_checks = [
        (lambda m: "HEARTBEAT STALE" in m["message"].upper(),
         2, "heartbeat_stale", "critical", "Heartbeat stale reported {} times"),
        (lambda m: any(w in m["message"].upper() for w in ["FAILED", "RESTART FAILED", "UNAVAILABLE"]),
         3, "service_failure", "critical", "Repeated service failures: {} failure messages"),
        (lambda m: any(w in m["message"].upper() for w in ["HIGH LOAD", "CPU SPIKE", "LOAD AVERAGE"]),
         2, "high_load", "warning", "High system load reported {} times"),
        (lambda m: any(w in m["message"].upper() for w in ["HIGH RAM", "MEMORY HIGH", "OOM", "SWAP"]),
         2, "high_ram", "warning", "High memory usage reported {} times"),
        (lambda m: any(w in m["message"].upper() for w in ["DISK HIGH", "DISK FULL", "DISK SPACE"]),
         2, "disk_high", "warning", "Disk pressure reported {} times"),
    ]
    for filter_fn, min_count, itype, severity, desc_tmpl in pattern_checks:
        matched = [m for m in source_messages if filter_fn(m)]
        if len(matched) >= min_count:
            inc = {"type": itype, "severity": severity, "count": len(matched),
                   "state": "detected", "description": desc_tmpl.format(len(matched))}
            if matched:
                inc["first_seen"] = matched[-1]["timestamp"]
            incidents.append(inc)

    # Alert storm — only from source messages (Coordinator excluded above)
    total_alerts = keyword_counts["critical"] + keyword_counts["warning"]
    if total_alerts > 15:
        incidents.append({"type": "alert_storm", "severity": "warning", "count": total_alerts,
                          "state": "detected",
                          "description": f"Alert storm: {total_alerts} alert messages in window"})

    # Agent silence
    active_agents = set(m["agent"] for m in messages)
    silent = {"Soma", "Eos", "Nova", "Atlas", "Meridian"} - active_agents
    if silent and len(messages) > 5:
        incidents.append({"type": "agent_silent", "severity": "warning", "count": len(silent),
                          "state": "detected",
                          "description": f"Silent agents: {', '.join(silent)}"})

    return incidents


def correlate_incidents(incidents):
    """Match active incidents against root cause correlation rules."""
    active_types = {i["type"] for i in incidents}
    correlations = []
    for rule_name, rule in CORRELATION_RULES.items():
        if set(rule["requires"]).issubset(active_types):
            correlations.append({"rule": rule_name, "matched_incidents": rule["requires"],
                                 "diagnosis": rule["diagnosis"], "severity": rule["severity"]})
    return correlations


def update_incident_lifecycle(state, new_incidents):
    """Track incidents through lifecycle, compute MTTR on resolution."""
    now = datetime.now(timezone.utc).isoformat()
    history = state.get("incident_history", [])
    prev_incidents = {i["type"]: i for i in state.get("incidents", [])}
    new_types = {i["type"] for i in new_incidents}

    # Advance state for continuing incidents
    for inc in new_incidents:
        prev = prev_incidents.get(inc["type"])
        if prev:
            old_state = prev.get("state", "detected")
            if old_state == "detected":
                inc["state"] = "acknowledged"
            elif old_state == "acknowledged":
                inc["state"] = "investigating"
            else:
                inc["state"] = old_state
            inc["first_seen"] = prev.get("first_seen", inc.get("first_seen", now))
        else:
            inc["state"] = "detected"
            inc.setdefault("first_seen", now)

    # Detect resolved incidents (were active, now gone)
    for itype, prev in prev_incidents.items():
        if itype not in new_types:
            resolved = dict(prev)
            resolved["state"] = "resolved"
            resolved["resolved_at"] = now
            try:
                first = datetime.fromisoformat(resolved.get("first_seen", now).replace("Z", "+00:00"))
                end = datetime.fromisoformat(now.replace("Z", "+00:00"))
                resolved["mttr_seconds"] = round((end - first).total_seconds())
            except Exception:
                resolved["mttr_seconds"] = None
            history.append(resolved)
            log(f"Incident resolved: {itype} (MTTR: {resolved.get('mttr_seconds', '?')}s)")

    state["incident_history"] = history[-50:]
    return new_incidents


def get_mttr_stats(state):
    """Compute mean time to resolve per incident type from history."""
    by_type = defaultdict(list)
    for inc in state.get("incident_history", []):
        mttr = inc.get("mttr_seconds")
        if mttr is not None and inc.get("state") == "resolved":
            by_type[inc["type"]].append(mttr)
    stats = {}
    for itype, mttrs in by_type.items():
        stats[itype] = {"count": len(mttrs),
                        "mean_mttr_sec": round(sum(mttrs) / len(mttrs)) if mttrs else 0,
                        "min_mttr_sec": min(mttrs) if mttrs else 0,
                        "max_mttr_sec": max(mttrs) if mttrs else 0}
    return stats


# ── Agent Scoring & Performance History ──────────────────────────────────────
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

    scores = {}
    for agent, stats in agent_stats.items():
        noise_ratio = 0
        if stats["total"] > 5:
            noise_ratio = max(0, stats["alerts"] / stats["total"] - 0.5) * 2
        signal = max(1, stats["info"])
        score = round(min(100, (signal / max(1, stats["total"])) * 100 * (1 - noise_ratio * 0.5)), 1)
        scores[agent] = {"score": score, "total": stats["total"],
                         "alerts": stats["alerts"], "info": stats["info"]}
    return scores


def update_performance_history(state, scores):
    """Append current scores to performance history. Detect degradation."""
    now = datetime.now(timezone.utc).isoformat()
    history = state.get("agent_performance_history", {})
    warnings = []
    for agent, data in scores.items():
        if agent not in history:
            history[agent] = []
        history[agent].append({"score": data["score"], "timestamp": now, "total": data["total"]})
        history[agent] = history[agent][-100:]
        # Degradation: score dropping over 3+ consecutive samples by >= 5 points
        entries = history[agent]
        if len(entries) >= 3:
            recent = [e["score"] for e in entries[-3:]]
            if all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                if recent[0] - recent[-1] >= 5:
                    warnings.append(f"{agent} degrading: score dropped "
                                    f"{recent[0]:.1f} -> {recent[-1]:.1f} over last 3 samples")
    state["agent_performance_history"] = history
    return warnings


# ── Relay Posting ────────────────────────────────────────────────────────────
def post_to_relay(message, topic="coordination"):
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                   ("Coordinator", message[:500], topic, datetime.now(timezone.utc).isoformat()))
        db.commit()
        db.close()
    except Exception as e:
        log(f"Relay post failed: {e}")


# ── Auto-create tasks from incidents ─────────────────────────────────────────
def create_tasks_from_incidents(incidents, correlations):
    """Generate tasks for critical incidents that need response."""
    for inc in incidents:
        if inc.get("state") == "detected" and inc.get("severity") == "critical":
            itype = inc["type"]
            if itype == "heartbeat_stale":
                create_task(f"Investigate heartbeat stale: {inc['description']}",
                            requested_by="Coordinator", priority="critical",
                            capability_needed="monitoring")
            elif itype == "service_failure":
                create_task(f"Restart failed services: {inc['description']}",
                            requested_by="Coordinator", priority="critical",
                            capability_needed="service_restart")
    for corr in correlations:
        create_task(f"Root cause investigation: {corr['diagnosis']}",
                    requested_by="Coordinator", priority="critical",
                    capability_needed="log_analysis")


def expire_stale_tasks(hours=24):
    """Mark tasks older than N hours as failed if still pending."""
    ensure_task_table()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    now = datetime.now(timezone.utc).isoformat()
    try:
        db = sqlite3.connect(RELAY_DB, timeout=5)
        db.execute("""UPDATE coordinator_tasks SET status='failed',
                      outcome='expired — no agent picked up', updated_at=?
                      WHERE status IN ('pending','assigned')
                      AND REPLACE(SUBSTR(created_at, 1, 19), 'T', ' ') < ?""", (now, cutoff))
        db.commit()
        db.close()
    except Exception as e:
        log(f"Task expiry failed: {e}")


# ── Main Coordination Cycle ──────────────────────────────────────────────────
def run_coordination_cycle():
    state = load_state()
    ensure_task_table()
    messages = get_recent_messages(hours=2)
    if not messages:
        log("No messages to coordinate")
        save_state(state)
        return

    dupes = find_duplicates(messages)
    if dupes:
        log(f"Found {len(dupes)} near-duplicate messages (Jaccard >= 0.6)")

    incidents = detect_incidents(messages)
    incidents = update_incident_lifecycle(state, incidents)

    correlations = correlate_incidents(incidents)
    for c in correlations:
        log(f"CORRELATION: {c['rule']} -> {c['diagnosis']}")

    scores = score_agents(messages)
    perf_warnings = update_performance_history(state, scores)
    for w in perf_warnings:
        log(f"DEGRADATION: {w}")
        post_to_relay(f"Agent degradation: {w}", topic="coordination")

    create_tasks_from_incidents(incidents, correlations)
    expire_stale_tasks()

    state["incidents"] = incidents
    state["agent_scores"] = scores
    state["suppressed_count"] = len(dupes)
    state["message_count"] = len(messages)

    if incidents:
        sev = {"critical": 0, "warning": 0, "info": 0}
        for inc in incidents:
            sev[inc.get("severity", "info")] += 1
        parts = []
        if sev["critical"]:
            parts.append(f"{sev['critical']} CRITICAL")
        if sev["warning"]:
            parts.append(f"{sev['warning']} WARNING")
        descs = [i["description"] for i in incidents[:3]]
        summary = f"Incidents: {', '.join(parts)}. {'; '.join(descs)}"
        if correlations:
            summary += f" | Root cause: {correlations[0]['diagnosis']}"

        # Cooldown: only post to relay if incident types changed, or 30 min since last post.
        # This prevents identical reports every 5 minutes from flooding the relay.
        prev_types = sorted(i["type"] for i in state.get("incidents", []))
        curr_types = sorted(i["type"] for i in incidents)
        last_post_time = state.get("last_incident_post")
        elapsed_since_post = float("inf")
        if last_post_time:
            try:
                lp = datetime.fromisoformat(last_post_time.replace("Z", "+00:00"))
                elapsed_since_post = (datetime.now(timezone.utc) - lp).total_seconds()
            except Exception:
                pass
        incidents_changed = (curr_types != prev_types)
        if incidents_changed or elapsed_since_post >= 1800:
            post_to_relay(summary, topic="coordination")
            state["last_incident_post"] = datetime.now(timezone.utc).isoformat()
        log(summary)
    else:
        log(f"All clear. {len(messages)} msgs, {len(dupes)} dupes, {len(scores)} agents active")
        state.pop("last_incident_post", None)

    save_state(state)
    return {"incidents": incidents, "correlations": correlations, "scores": scores,
            "duplicates": len(dupes), "perf_warnings": perf_warnings}


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "incidents":
        state = load_state()
        incidents = state.get("incidents", [])
        if not incidents:
            print("No active incidents.")
        else:
            for i in incidents:
                print(f"[{i.get('severity','?').upper()}] [{i.get('state','?')}] "
                      f"{i.get('type','?')}: {i.get('description','')}")
        mttr = get_mttr_stats(state)
        if mttr:
            print("\nMTTR by incident type:")
            for itype, s in mttr.items():
                print(f"  {itype}: avg={s['mean_mttr_sec']}s min={s['min_mttr_sec']}s "
                      f"max={s['max_mttr_sec']}s ({s['count']} resolved)")
        history = state.get("incident_history", [])
        recent_resolved = [h for h in history[-5:] if h.get("state") == "resolved"]
        if recent_resolved:
            print(f"\nRecently resolved: {len(recent_resolved)}")
            for r in recent_resolved:
                print(f"  {r['type']}: resolved (MTTR {r.get('mttr_seconds','?')}s)")

    elif mode == "scores":
        messages = get_recent_messages(hours=2)
        scores = score_agents(messages)
        for agent, data in sorted(scores.items(), key=lambda x: -x[1]["score"]):
            print(f"{agent:15s} score={data['score']:5.1f}  "
                  f"total={data['total']:3d}  alerts={data['alerts']:2d}  info={data['info']:3d}")

    elif mode == "dedupe":
        messages = get_recent_messages(hours=2)
        dupes = find_duplicates(messages)
        print(f"Found {len(dupes)} near-duplicates out of {len(messages)} messages "
              f"(3-gram Jaccard >= 0.6)")
        for d in dupes[:10]:
            print(f"  [{d['agent']}] {d['message'][:80]}")

    elif mode == "tasks":
        tasks = get_all_tasks(limit=20)
        pending = [t for t in tasks if t["status"] in ("pending", "assigned", "in_progress")]
        done = [t for t in tasks if t["status"] in ("done", "failed")]
        if pending:
            print(f"Active tasks ({len(pending)}):")
            for t in pending:
                agent_str = t["assigned_agent"] or "unassigned"
                print(f"  #{t['id']} [{t['priority'].upper()}] [{t['status']}] "
                      f"{t['task'][:60]} -> {agent_str}")
        else:
            print("No active tasks.")
        if done:
            print(f"\nRecent completed/failed ({len(done)}):")
            for t in done[:10]:
                print(f"  #{t['id']} [{t['status']}] {t['task'][:50]} "
                      f"outcome={(t['outcome'] or '')[:40]}")

    elif mode == "capabilities":
        print("Agent Capability Registry:")
        print("-" * 60)
        for agent, caps in sorted(CAPABILITY_REGISTRY.items()):
            print(f"  {agent:15s}: {', '.join(caps)}")
        print("\nCapability -> Agent lookup:")
        print("-" * 60)
        for cap in sorted(CAPABILITY_TO_AGENTS.keys()):
            print(f"  {cap:25s}: {', '.join(CAPABILITY_TO_AGENTS[cap])}")

    elif mode == "history":
        state = load_state()
        history = state.get("agent_performance_history", {})
        if not history:
            print("No performance history yet.")
        else:
            print("Agent Performance History (last 5 snapshots each):")
            print("-" * 65)
            for agent in sorted(history.keys()):
                entries = history[agent][-5:]
                scores_str = " -> ".join(f"{e['score']:.1f}" for e in entries)
                print(f"  {agent:15s} ({len(history[agent]):3d} snapshots): {scores_str}")
                if len(entries) >= 3:
                    recent = [e["score"] for e in entries[-3:]]
                    if all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                        print(f"  {'':15s} ** DEGRADING **")
                    elif all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
                        print(f"  {'':15s} ++ improving ++")
        mttr = get_mttr_stats(state)
        if mttr:
            print("\nIncident MTTR stats:")
            for itype, s in mttr.items():
                print(f"  {itype}: avg={s['mean_mttr_sec']}s ({s['count']} resolved)")

    else:
        run_coordination_cycle()


if __name__ == "__main__":
    main()
