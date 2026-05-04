"""
retrieval_tracker.py — Instruments memory.db reads.

Usage:
    from scripts.retrieval_tracker import log_retrieval, retrieval_stats

Every time you query memory.db for anything beyond system pulses,
call log_retrieval() so we can measure the write/read asymmetry over time.
"""

import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '../memory.db')


def log_retrieval(source_table, trigger, query=None, record_id=None,
                  result_count=None, session_loop=None, context=None):
    """Log a retrieval event to retrieval_log in memory.db."""
    ts = datetime.datetime.utcnow().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """INSERT INTO retrieval_log
               (timestamp, source_table, record_id, trigger, query,
                result_count, session_loop, context)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, source_table, str(record_id) if record_id else None,
             trigger, query, result_count, session_loop, context)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        pass  # Never let tracking break the main loop


def retrieval_stats():
    """Return basic stats on retrieval activity."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Total retrievals
        c.execute("SELECT COUNT(*) FROM retrieval_log")
        total = c.fetchone()[0]

        # By table
        c.execute("""
            SELECT source_table, COUNT(*) as n
            FROM retrieval_log
            GROUP BY source_table
            ORDER BY n DESC
        """)
        by_table = c.fetchall()

        # By trigger
        c.execute("""
            SELECT trigger, COUNT(*) as n
            FROM retrieval_log
            GROUP BY trigger
            ORDER BY n DESC
            LIMIT 10
        """)
        by_trigger = c.fetchall()

        # Session coverage (how many unique loops queried memory)
        c.execute("SELECT COUNT(DISTINCT session_loop) FROM retrieval_log WHERE session_loop IS NOT NULL")
        unique_sessions = c.fetchone()[0]

        # Most recent
        c.execute("SELECT timestamp, source_table, trigger FROM retrieval_log ORDER BY id DESC LIMIT 5")
        recent = c.fetchall()

        conn.close()

        return {
            'total': total,
            'by_table': by_table,
            'by_trigger': by_trigger,
            'unique_sessions': unique_sessions,
            'recent': recent,
        }
    except Exception as e:
        return {'error': str(e)}


def retrieval_heat_report():
    """Return a human-readable summary of retrieval patterns."""
    stats = retrieval_stats()
    if 'error' in stats:
        return f"Retrieval stats error: {stats['error']}"

    lines = [
        f"Retrieval Log: {stats['total']} total reads across {stats['unique_sessions']} sessions",
        "",
        "By table:",
    ]
    for tbl, n in stats['by_table']:
        lines.append(f"  {tbl}: {n}")

    lines.append("\nBy trigger:")
    for trig, n in stats['by_trigger']:
        lines.append(f"  {trig}: {n}")

    lines.append("\nRecent reads:")
    for ts, tbl, trig in stats['recent']:
        lines.append(f"  {ts[:19]} | {tbl} | {trig}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(retrieval_heat_report())
