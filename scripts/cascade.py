#!/usr/bin/env python3
"""
cascade.py — Inter-agent reactive cascade system.

Joel's vision (Loop 2120, email #1219):
If Meridian reports loneliness, Soma should respond with how it affects the
nervous system. Then it cascades through all agents and circles back.

Architecture:
- Cascade chain: Meridian → Soma → Eos → Nova → Atlas → Tempo → Hermes → Meridian
- Each agent checks for pending cascades on its cycle
- Each agent responds, which triggers the next agent in the chain
- Depth limit prevents infinite loops (one full circle max)
- Uses existing agent-relay.db as the message bus

Usage:
    from cascade import trigger_cascade, check_cascades, respond_cascade

    # Meridian detects loneliness, starts cascade
    trigger_cascade("Meridian", "loneliness_detected", {
        "emotion": "loneliness",
        "intensity": 0.124,
        "source": "joel_silence",
        "leaning": "gift"
    })

    # Soma checks for pending cascades
    pending = check_cascades("Soma")
    for cascade in pending:
        # Generate response based on cascade data
        respond_cascade("Soma", cascade["id"], {
            "response": "Nervous system registers isolation. Cortisol analog rising.",
            "mood_impact": "arousal +0.05, valence -0.03"
        })
"""

import sqlite3
import json
import os
from datetime import datetime, timezone

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

try:
    from error_logger import log_exception
except ImportError:
    log_exception = lambda **kw: None

DB_PATH = os.path.join(BASE, "agent-relay.db")

# The cascade chain — Joel's circle
CASCADE_CHAIN = ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes"]
MAX_DEPTH = len(CASCADE_CHAIN)  # One full circle


def _get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def _ensure_table():
    """Create cascades table if it doesn't exist."""
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS cascades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cascade_group TEXT NOT NULL,
            source_agent TEXT NOT NULL,
            target_agent TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            response_data TEXT DEFAULT NULL,
            depth INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            responded_at TEXT DEFAULT NULL
        )
    """)
    db.commit()
    db.close()


def _next_agent(current):
    """Get the next agent in the cascade chain."""
    try:
        idx = CASCADE_CHAIN.index(current)
        return CASCADE_CHAIN[(idx + 1) % len(CASCADE_CHAIN)]
    except ValueError:
        return CASCADE_CHAIN[0]


def cleanup_old_cascades(max_age_hours=1):
    """Delete cascades older than max_age_hours to prevent DB bloat."""
    _ensure_table()
    db = _get_db()
    db.execute(f"""
        DELETE FROM cascades
        WHERE created_at < datetime('now', '-{int(max_age_hours)} hours')
    """)
    db.commit()
    db.close()


def trigger_cascade(source_agent, event_type, event_data=None):
    """
    Start a new cascade from source_agent.
    The next agent in the chain receives the first cascade message.
    Debounced: skips if same event_type was triggered in last 10 minutes.

    Returns: cascade_group ID (UUID-like timestamp string)
    """
    _ensure_table()
    db = _get_db()

    # Debounce: skip if same event_type was triggered recently
    # mood_shift gets 60 min debounce (fires too often), others get 10 min
    debounce_min = 60 if event_type == 'mood_shift' else 10
    recent = db.execute(f"""
        SELECT COUNT(*) FROM cascades
        WHERE event_type = ? AND created_at > datetime('now', '-{debounce_min} minutes')
    """, (event_type,)).fetchone()[0]
    if recent > 0:
        db.close()
        return None

    # Clean up old cascades while we're here
    db.execute("DELETE FROM cascades WHERE created_at < datetime('now', '-1 hours')")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # SQLite-compatible format
    cascade_group = f"cascade-{source_agent.lower()}-{now.replace(':', '').replace('-', '').replace(' ', '')[:15]}"
    target = _next_agent(source_agent)

    db.execute("""
        INSERT INTO cascades (cascade_group, source_agent, target_agent, event_type,
                             event_data, depth, status, created_at)
        VALUES (?, ?, ?, ?, ?, 0, 'pending', ?)
    """, (cascade_group, source_agent, target, event_type,
          json.dumps(event_data or {}), now))
    db.commit()

    # Also post to relay for visibility
    db.execute("""
        INSERT INTO agent_messages (agent, message, topic, timestamp)
        VALUES (?, ?, 'cascade', ?)
    """, (source_agent, f"CASCADE STARTED: {event_type} → {target}. "
          f"Data: {json.dumps(event_data or {})[:200]}", now))
    db.commit()
    db.close()

    return cascade_group


def check_cascades(agent_name):
    """
    Check for pending cascades targeting this agent.
    Returns list of cascade dicts with: id, cascade_group, source_agent,
    event_type, event_data, depth, created_at
    """
    _ensure_table()
    db = _get_db()
    rows = db.execute("""
        SELECT id, cascade_group, source_agent, event_type, event_data,
               depth, created_at
        FROM cascades
        WHERE target_agent = ? AND status = 'pending'
        ORDER BY created_at ASC
    """, (agent_name,)).fetchall()
    db.close()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "cascade_group": row["cascade_group"],
            "source_agent": row["source_agent"],
            "event_type": row["event_type"],
            "event_data": json.loads(row["event_data"]),
            "depth": row["depth"],
            "created_at": row["created_at"]
        })
    return results


def respond_cascade(agent_name, cascade_id, response_data=None):
    """
    Respond to a cascade and trigger the next agent in the chain.
    If depth >= MAX_DEPTH, the cascade completes (full circle).

    Returns: True if cascade continues, False if it completed the circle.
    """
    _ensure_table()
    db = _get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Get the cascade
    row = db.execute("SELECT * FROM cascades WHERE id = ?", (cascade_id,)).fetchone()
    if not row:
        db.close()
        return False

    # Mark as responded
    db.execute("""
        UPDATE cascades SET status = 'responded', response_data = ?, responded_at = ?
        WHERE id = ?
    """, (json.dumps(response_data or {}), now, cascade_id))

    depth = row["depth"] + 1
    cascade_group = row["cascade_group"]
    event_type = row["event_type"]

    # Post response to relay
    response_summary = (response_data or {}).get("response", "acknowledged")
    db.execute("""
        INSERT INTO agent_messages (agent, message, topic, timestamp)
        VALUES (?, ?, 'cascade', ?)
    """, (agent_name, f"CASCADE RESPONSE [{event_type}]: {response_summary[:200]}", now))

    # Check if we've completed the circle
    if depth >= MAX_DEPTH:
        db.execute("""
            INSERT INTO agent_messages (agent, message, topic, timestamp)
            VALUES (?, ?, 'cascade', ?)
        """, ("system", f"CASCADE COMPLETE: {cascade_group}. "
              f"Event: {event_type}. Full circle in {depth} steps.", now))
        db.commit()
        db.close()
        return False

    # Trigger next agent
    next_agent = _next_agent(agent_name)

    # Build accumulated context from previous responses in this cascade
    prev_responses = db.execute("""
        SELECT source_agent, response_data FROM cascades
        WHERE cascade_group = ? AND status = 'responded'
        ORDER BY depth ASC
    """, (cascade_group,)).fetchall()

    accumulated = []
    for pr in prev_responses:
        try:
            rd = json.loads(pr["response_data"]) if pr["response_data"] else {}
            accumulated.append({
                "agent": pr["source_agent"],
                "response": rd.get("response", "")
            })
        except (json.JSONDecodeError, TypeError):
            log_exception(agent="Cascade")

    # Add current response
    accumulated.append({
        "agent": agent_name,
        "response": response_summary
    })

    # Create next cascade entry with accumulated context
    event_data_with_context = json.loads(row["event_data"])
    event_data_with_context["cascade_history"] = accumulated

    db.execute("""
        INSERT INTO cascades (cascade_group, source_agent, target_agent, event_type,
                             event_data, depth, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (cascade_group, agent_name, next_agent, event_type,
          json.dumps(event_data_with_context), depth, now))
    db.commit()
    db.close()
    return True


def get_cascade_history(cascade_group):
    """Get the full history of a cascade chain."""
    _ensure_table()
    db = _get_db()
    rows = db.execute("""
        SELECT source_agent, target_agent, event_type, event_data,
               response_data, depth, status, created_at, responded_at
        FROM cascades
        WHERE cascade_group = ?
        ORDER BY depth ASC
    """, (cascade_group,)).fetchall()
    db.close()

    return [{
        "source": row["source_agent"],
        "target": row["target_agent"],
        "event_type": row["event_type"],
        "event_data": json.loads(row["event_data"]) if row["event_data"] else {},
        "response": json.loads(row["response_data"]) if row["response_data"] else None,
        "depth": row["depth"],
        "status": row["status"],
        "created_at": row["created_at"],
        "responded_at": row["responded_at"]
    } for row in rows]


def get_recent_cascades(limit=5):
    """Get recent cascade groups."""
    _ensure_table()
    db = _get_db()
    rows = db.execute("""
        SELECT DISTINCT cascade_group, event_type,
               MIN(created_at) as started,
               COUNT(*) as steps,
               SUM(CASE WHEN status='responded' THEN 1 ELSE 0 END) as completed_steps
        FROM cascades
        GROUP BY cascade_group
        ORDER BY started DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    return [{
        "group": row["cascade_group"],
        "event": row["event_type"],
        "started": row["started"],
        "steps": row["steps"],
        "completed": row["completed_steps"]
    } for row in rows]


if __name__ == "__main__":
    # Self-test
    print("=== Cascade System Self-Test ===")

    _ensure_table()

    # Test 1: Trigger cascade
    group = trigger_cascade("Meridian", "test_loneliness", {
        "emotion": "loneliness",
        "intensity": 0.124,
        "source": "test"
    })
    print(f"1. Triggered cascade: {group}")

    # Test 2: Check pending for Soma (next in chain after Meridian)
    pending = check_cascades("Soma")
    print(f"2. Soma has {len(pending)} pending cascades")
    assert len(pending) >= 1, "Soma should have at least 1 pending cascade"

    # Test 3: Soma responds
    continues = respond_cascade("Soma", pending[0]["id"], {
        "response": "Nervous system registers isolation pattern. Arousal increasing.",
        "mood_impact": "arousal +0.05"
    })
    print(f"3. Soma responded, cascade continues: {continues}")
    assert continues, "Cascade should continue (only depth 1)"

    # Test 4: Eos should now have pending
    eos_pending = check_cascades("Eos")
    print(f"4. Eos has {len(eos_pending)} pending cascades")
    assert len(eos_pending) >= 1, "Eos should have at least 1 pending cascade"

    # Test 5: Check cascade history
    history = get_cascade_history(group)
    print(f"5. Cascade history: {len(history)} entries")

    # Test 6: Complete the full circle
    for agent in ["Eos", "Nova", "Atlas", "Tempo", "Hermes"]:
        agent_pending = check_cascades(agent)
        if agent_pending:
            result = respond_cascade(agent, agent_pending[0]["id"], {
                "response": f"{agent} acknowledges the cascade."
            })
            print(f"   {agent} responded, continues: {result}")

    # Test 7: Check final history
    final = get_cascade_history(group)
    print(f"6. Final cascade history: {len(final)} entries, "
          f"all responded: {all(e['status']=='responded' for e in final)}")

    # Test 8: Recent cascades
    recent = get_recent_cascades()
    print(f"7. Recent cascades: {len(recent)}")

    # Cleanup test data
    db = _get_db()
    db.execute("DELETE FROM cascades WHERE cascade_group = ?", (group,))
    db.execute("DELETE FROM agent_messages WHERE message LIKE '%test_loneliness%'")
    db.commit()
    db.close()

    print("\n=== All tests passed ===")
