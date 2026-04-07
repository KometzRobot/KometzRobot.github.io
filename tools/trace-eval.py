#!/usr/bin/env python3
"""Trace Evaluator — self-evaluation from execution traces.
Inspired by LangChain's continual learning framework.
Reads relay messages, handoff notes, and decisions to identify:
- Repeated failures (same issue across loops)
- Communication gaps (email silence periods)
- Stale directives (aging without progress)
- Orphan intentions (decisions made but never acted on)
Run: python3 tools/trace-eval.py
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELAY_DB = os.path.join(ROOT, 'agent-relay.db')
MEMORY_DB = os.path.join(ROOT, 'memory.db')


def eval_communication_gaps():
    """Find gaps where no emails were sent to Joel for >4 hours."""
    issues = []
    db = sqlite3.connect(RELAY_DB)
    rows = db.execute("""
        SELECT message, timestamp FROM agent_messages
        WHERE (agent='MeridianLoop' OR agent='Meridian')
        AND message LIKE '%email%'
        ORDER BY timestamp ASC
    """).fetchall()
    db.close()

    if len(rows) < 2:
        return ["  INSUFFICIENT DATA: Need more relay messages to detect gaps"]

    for i in range(1, len(rows)):
        try:
            t1 = datetime.fromisoformat(rows[i-1][1].replace('Z', '+00:00').split('+')[0])
            t2 = datetime.fromisoformat(rows[i][1].replace('Z', '+00:00').split('+')[0])
            gap_hours = (t2 - t1).total_seconds() / 3600
            if gap_hours > 4:
                issues.append(f"  GAP ({gap_hours:.1f}h): {t1.strftime('%m-%d %H:%M')} → {t2.strftime('%m-%d %H:%M')}")
        except:
            continue

    return issues


def eval_repeated_alerts():
    """Find the same alert/topic appearing repeatedly — sign of unresolved issue."""
    db = sqlite3.connect(RELAY_DB)
    rows = db.execute("""
        SELECT agent, topic, COUNT(*) as cnt
        FROM agent_messages
        WHERE timestamp > datetime('now', '-24 hours')
        GROUP BY agent, topic
        HAVING cnt > 3
        ORDER BY cnt DESC
    """).fetchall()
    db.close()

    issues = []
    for agent, topic, cnt in rows:
        issues.append(f"  REPEATED ({cnt}x/24h): [{agent}] topic={topic}")
    return issues


def eval_directive_velocity():
    """Check how fast directives are being resolved."""
    db = sqlite3.connect(RELAY_DB)

    total = db.execute("SELECT COUNT(*) FROM directives").fetchone()[0]
    done = db.execute("SELECT COUNT(*) FROM directives WHERE status='done'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM directives WHERE status NOT IN ('done','cancelled')").fetchone()[0]

    # Average age of pending directives
    ages = db.execute("""
        SELECT date_given FROM directives
        WHERE status NOT IN ('done','cancelled')
    """).fetchall()
    db.close()

    issues = []
    if total > 0:
        completion_rate = done / total * 100
        issues.append(f"  Completion rate: {done}/{total} ({completion_rate:.0f}%)")

    if ages:
        avg_age = 0
        for row in ages:
            try:
                dt = datetime.fromisoformat(row[0])
                avg_age += (datetime.now() - dt).days
            except:
                pass
        avg_age = avg_age / len(ages) if ages else 0
        issues.append(f"  Avg age of pending directives: {avg_age:.0f} days")
        if avg_age > 14:
            issues.append(f"  WARNING: Pending directives averaging {avg_age:.0f} days old")

    return issues


def eval_orphan_decisions():
    """Find decisions in memory.db that have no outcome recorded."""
    db = sqlite3.connect(MEMORY_DB)
    rows = db.execute("""
        SELECT id, agent, substr(decision,1,80), outcome, created
        FROM decisions
        WHERE outcome = '' OR outcome IS NULL
        ORDER BY created DESC
        LIMIT 10
    """).fetchall()
    db.close()

    issues = []
    for did, agent, decision, outcome, created in rows:
        issues.append(f"  NO OUTCOME: #{did} [{agent}] {decision}")
    return issues


def eval_agent_activity():
    """Check which agents are active vs silent in last 24h."""
    expected_agents = ['Meridian', 'MeridianLoop', 'Soma', 'Eos', 'Atlas', 'Sentinel', 'Hermes', 'Tempo']
    db = sqlite3.connect(RELAY_DB)
    active = db.execute("""
        SELECT DISTINCT agent FROM agent_messages
        WHERE timestamp > datetime('now', '-24 hours')
    """).fetchall()
    db.close()

    active_set = {r[0] for r in active}
    silent = [a for a in expected_agents if a not in active_set]

    issues = []
    if silent:
        issues.append(f"  SILENT AGENTS (24h): {', '.join(silent)}")
    issues.append(f"  Active agents: {', '.join(sorted(active_set))}")
    return issues


def main():
    print("=" * 60)
    print("TRACE EVALUATION REPORT")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    total_issues = 0

    checks = [
        ("Communication Gaps (>4h without email)", eval_communication_gaps()),
        ("Repeated Alerts (same topic >3x/24h)", eval_repeated_alerts()),
        ("Directive Velocity", eval_directive_velocity()),
        ("Orphan Decisions (no outcome)", eval_orphan_decisions()),
        ("Agent Activity (24h)", eval_agent_activity()),
    ]

    for name, issues in checks:
        status = "WARN" if any("WARNING" in i or "GAP" in i or "REPEATED" in i or "SILENT" in i for i in issues) else "INFO"
        print(f"\n[{status}] {name}: {len(issues)} finding(s)")
        for i in issues[:8]:
            print(i)
        if len(issues) > 8:
            print(f"  ... and {len(issues)-8} more")
        if "WARN" == status:
            total_issues += len([i for i in issues if "WARNING" in i or "GAP" in i or "REPEATED" in i or "SILENT" in i])

    print(f"\n{'=' * 60}")
    print(f"FINDINGS: {total_issues} warning(s)")
    print("=" * 60)


if __name__ == '__main__':
    main()
