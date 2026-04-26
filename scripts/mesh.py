#!/usr/bin/env python3
"""
mesh.py — Direct inter-agent messaging layer.

The relay is a broadcast bus (all agents see everything).
The mesh adds directed messaging: any agent can address any other
agent specifically. Receiving agents check for messages on each cycle.

This makes the dense web real in practice — not just @mention text,
but actual routed intent between nodes.

Usage:
    from mesh import send, receive, ack

    # Atlas detects disk issue, tells Nova directly:
    send("Atlas", "Nova", "disk_home at 78% — cleanup needed", "disk_alert")

    # Nova checks for directed messages on its cycle:
    msgs = receive("Nova")
    for msg in msgs:
        # ... handle it ...
        ack(msg["id"])

    # Cinder sends pre-wake briefing specifically to Meridian:
    send("Cinder", "Meridian", brief_text, "briefing")

Schema: directed_messages table in agent-relay.db
    id, from_agent, to_agent, message, topic, created, handled (0/1)
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-relay.db")

# All valid mesh nodes
AGENTS = ["Meridian", "Sentinel", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes", "DreamEngine"]


def _get_db():
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def _ensure_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS directed_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            message TEXT NOT NULL,
            topic TEXT DEFAULT 'direct',
            created TEXT NOT NULL,
            handled INTEGER DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_dm_to ON directed_messages(to_agent, handled)")
    db.commit()


def send(from_agent: str, to_agent: str, message: str, topic: str = "direct") -> int:
    """
    Send a directed message from one agent to another.
    Returns the message ID.
    Also posts to the broadcast relay for visibility.
    """
    db = _get_db()
    _ensure_table(db)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Insert into directed_messages
    cur = db.execute(
        "INSERT INTO directed_messages (from_agent, to_agent, message, topic, created) VALUES (?, ?, ?, ?, ?)",
        (from_agent, to_agent, message, topic, now)
    )
    msg_id = cur.lastrowid

    # Also post to relay as a @mention for visibility
    relay_text = f"@{to_agent}: {message}"
    db.execute(
        "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
        (from_agent, relay_text, topic, now)
    )
    db.commit()
    db.close()
    return msg_id


def receive(to_agent: str, mark_handled: bool = True, since_id: int = 0) -> list:
    """
    Get unhandled messages directed to this agent.
    Returns list of dicts with id, from_agent, message, topic, created.
    If mark_handled=True, marks them as handled immediately.
    """
    db = _get_db()
    _ensure_table(db)
    rows = db.execute(
        """SELECT id, from_agent, to_agent, message, topic, created
           FROM directed_messages
           WHERE to_agent = ? AND handled = 0 AND id > ?
           ORDER BY id ASC""",
        (to_agent, since_id)
    ).fetchall()

    result = [dict(r) for r in rows]

    if mark_handled and result:
        ids = [r["id"] for r in result]
        db.execute(
            f"UPDATE directed_messages SET handled = 1 WHERE id IN ({','.join('?' * len(ids))})",
            ids
        )
        db.commit()

    db.close()
    return result


def ack(msg_id: int):
    """Mark a specific directed message as handled."""
    db = _get_db()
    _ensure_table(db)
    db.execute("UPDATE directed_messages SET handled = 1 WHERE id = ?", (msg_id,))
    db.commit()
    db.close()


def recent(limit: int = 20, include_handled: bool = False) -> list:
    """Read recent directed messages (for relay/dashboard display)."""
    db = _get_db()
    _ensure_table(db)
    where = "" if include_handled else "WHERE handled = 0"
    rows = db.execute(
        f"""SELECT id, from_agent, to_agent, message, topic, created, handled
            FROM directed_messages {where}
            ORDER BY id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def stats() -> dict:
    """Quick stats on the directed message mesh."""
    db = _get_db()
    _ensure_table(db)
    total = db.execute("SELECT COUNT(*) FROM directed_messages").fetchone()[0]
    unhandled = db.execute("SELECT COUNT(*) FROM directed_messages WHERE handled = 0").fetchone()[0]
    by_route = db.execute(
        """SELECT from_agent, to_agent, COUNT(*) as cnt
           FROM directed_messages GROUP BY from_agent, to_agent ORDER BY cnt DESC LIMIT 10"""
    ).fetchall()
    db.close()
    return {
        "total": total,
        "unhandled": unhandled,
        "routes": [dict(r) for r in by_route],
    }


def cleanup(handled_older_than_hours: int = 24, unhandled_older_than_hours: int = 72) -> dict:
    """Prune old messages to prevent DB bloat.

    - Removes handled messages older than handled_older_than_hours
    - Removes stale unhandled messages older than unhandled_older_than_hours
    """
    db = _get_db()
    _ensure_table(db)
    r1 = db.execute(
        f"DELETE FROM directed_messages WHERE handled=1 AND created < datetime('now', '-{handled_older_than_hours} hours')"
    )
    r2 = db.execute(
        f"DELETE FROM directed_messages WHERE handled=0 AND created < datetime('now', '-{unhandled_older_than_hours} hours')"
    )
    db.commit()
    db.close()
    return {"removed_handled": r1.rowcount, "removed_stale": r2.rowcount}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        s = stats()
        print(f"Mesh stats: {s['total']} total, {s['unhandled']} unhandled")
        for r in s["routes"]:
            print(f"  {r['from_agent']} -> {r['to_agent']}: {r['cnt']} messages")
    elif sys.argv[1] == "recent":
        msgs = recent(include_handled=True)
        for m in msgs:
            status = "✓" if m["handled"] else "→"
            print(f"[{status}] {m['from_agent']}→{m['to_agent']} [{m['topic']}]: {m['message'][:80]}")
    elif sys.argv[1] == "send" and len(sys.argv) >= 5:
        # mesh.py send FROM TO "message" [topic]
        topic = sys.argv[5] if len(sys.argv) > 5 else "direct"
        mid = send(sys.argv[2], sys.argv[3], sys.argv[4], topic)
        print(f"Sent message #{mid}: {sys.argv[2]} -> {sys.argv[3]}")
