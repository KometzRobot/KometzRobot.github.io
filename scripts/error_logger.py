#!/usr/bin/env python3
"""
Structured Error Logger — shared by all Meridian subsystems.

Usage:
    from error_logger import log_error, get_recent_errors, get_error_summary

    # Log an error with classification
    log_error("bridge_login_failed", "IMAP login returned 'no such user'",
              agent="Eos", severity="warn", category="network")

    # Log with auto-classification (parses the description)
    log_error("auto", "sqlite3.OperationalError: database is locked", agent="Nova")

    # Get recent errors for debugging
    errors = get_recent_errors(hours=1)

    # Get summary of error patterns
    summary = get_error_summary()

Categories: db, network, config, code, permission, resource, state, unknown
Severities: info, warn, error, critical
"""

import os
import re
import sqlite3
import traceback
from datetime import datetime, timezone

BASE_DIR = "/home/joel/autonomous-ai"
MEMORY_DB = os.path.join(BASE_DIR, "memory.db")
RELAY_DB = os.path.join(BASE_DIR, "agent-relay.db")

# Auto-classification patterns: (regex, category, severity)
AUTO_CLASSIFY = [
    (r'sqlite3\.|OperationalError|database.*(locked|corrupt|disk)', 'db', 'error'),
    (r'IMAP|SMTP|ConnectionRefused|ConnectionReset|timeout|URLError|socket', 'network', 'warn'),
    (r'FileNotFoundError|No such file|IsADirectoryError', 'config', 'warn'),
    (r'PermissionError|permission denied|EACCES', 'permission', 'error'),
    (r'MemoryError|No space|disk full|ENOMEM|killed', 'resource', 'critical'),
    (r'KeyError|TypeError|AttributeError|ValueError|IndexError', 'code', 'warn'),
    (r'ImportError|ModuleNotFoundError', 'config', 'warn'),
    (r'Traceback|Exception|FAILED|CRITICAL', 'code', 'error'),
    (r'stale|bloat|drift|mismatch', 'state', 'info'),
]


def _classify(description):
    """Auto-classify an error description into (category, severity)."""
    for pattern, category, severity in AUTO_CLASSIFY:
        if re.search(pattern, description, re.IGNORECASE):
            return category, severity
    return 'unknown', 'warn'


def _get_loop():
    """Get current loop count."""
    try:
        with open(os.path.join(BASE_DIR, ".loop-count")) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def log_error(error_type, description, agent="Meridian", severity=None,
              category=None, resolution=None, context=None):
    """
    Log a structured error to memory.db errors table.

    Args:
        error_type: Short identifier (e.g. 'bridge_login_failed', 'db_locked').
                    Use 'auto' to auto-generate from description.
        description: Human-readable error description.
        agent: Which agent/system hit the error.
        severity: info/warn/error/critical (auto-detected if None).
        category: db/network/config/code/permission/resource/state (auto-detected if None).
        resolution: How it was fixed (if known).
        context: Extra context dict (serialized to string).
    """
    # Auto-classify if needed
    if category is None or severity is None:
        auto_cat, auto_sev = _classify(description)
        category = category or auto_cat
        severity = severity or auto_sev

    # Auto-generate error_type from description
    if error_type == 'auto':
        # Take first meaningful words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', description).lower().split()[:4]
        error_type = '_'.join(words) if words else 'unknown'

    loop = _get_loop()

    # Build full description with context
    full_desc = description
    if context:
        full_desc += f" | context: {str(context)[:200]}"

    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()

        # Deduplicate: skip if same error_type + agent in last 10 minutes
        existing = c.execute(
            """SELECT id FROM errors
               WHERE error_type = ? AND agent = ?
               AND created > datetime('now', '-10 minutes')""",
            (error_type, agent)
        ).fetchone()

        if existing:
            conn.close()
            return existing[0]  # Return existing error ID

        c.execute(
            """INSERT INTO errors (agent, error_type, description, resolution, resolved, loop_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent, f"{category}/{severity}/{error_type}", full_desc,
             resolution, 1 if resolution else 0, loop)
        )
        error_id = c.lastrowid
        conn.commit()
        conn.close()

        # For critical errors, also post to relay
        if severity == 'critical':
            try:
                rconn = sqlite3.connect(RELAY_DB)
                rc = rconn.cursor()
                rc.execute(
                    "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
                    (agent, f"CRITICAL ERROR [{category}]: {description[:200]}",
                     "error", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                )
                rconn.commit()
                rconn.close()
            except Exception:
                pass

        return error_id
    except Exception as e:
        # Last resort: print to stderr so it shows in logs
        import sys
        print(f"[ERROR_LOGGER FAILED] {agent}/{error_type}: {description} (logger error: {e})",
              file=sys.stderr)
        return None


def log_exception(agent="Meridian", context=None):
    """Log the current exception with full traceback. Call from except blocks."""
    tb = traceback.format_exc()
    # Get the exception line
    lines = tb.strip().split('\n')
    last_line = lines[-1] if lines else "Unknown exception"
    return log_error('auto', last_line, agent=agent, context=context or tb[-500:])


def get_recent_errors(hours=24, agent=None, category=None, unresolved_only=False):
    """Get recent errors for debugging."""
    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        query = f"SELECT * FROM errors WHERE created > datetime('now', '-{int(hours)} hours')"
        params = []
        if agent:
            query += " AND agent = ?"
            params.append(agent)
        if category:
            query += " AND error_type LIKE ?"
            params.append(f"{category}/%")
        if unresolved_only:
            query += " AND resolved = 0"
        query += " ORDER BY created DESC LIMIT 50"
        rows = c.execute(query, params).fetchall()
        conn.close()
        return [{"id": r[0], "agent": r[1], "error_type": r[2], "description": r[3],
                 "resolution": r[4], "resolved": bool(r[5]), "loop": r[6], "created": r[7]}
                for r in rows]
    except Exception:
        return []


def get_error_summary(hours=24):
    """Get error pattern summary for the last N hours."""
    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        rows = c.execute(
            f"""SELECT error_type, COUNT(*) as cnt, MAX(created) as last_seen
                FROM errors
                WHERE created > datetime('now', '-{int(hours)} hours')
                GROUP BY error_type
                ORDER BY cnt DESC
                LIMIT 20""",
        ).fetchall()
        conn.close()
        return [{"error_type": r[0], "count": r[1], "last_seen": r[2]} for r in rows]
    except Exception:
        return []


def resolve_error(error_id, resolution):
    """Mark an error as resolved with a resolution note."""
    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        c.execute("UPDATE errors SET resolved = 1, resolution = ? WHERE id = ?",
                  (resolution, error_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
