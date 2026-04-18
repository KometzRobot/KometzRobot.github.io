#!/usr/bin/env python3
"""
Cinder Memory System — persistent conversation memory with SQLite.
Core feature of the Cinder USB product.

Usage:
  python3 cinder-memory.py save "user" "Hello Cinder"
  python3 cinder-memory.py save "assistant" "Hey there."
  python3 cinder-memory.py load [--limit 20] [--session SESSION_ID]
  python3 cinder-memory.py search "what did we talk about"
  python3 cinder-memory.py sessions
  python3 cinder-memory.py distill [SESSION_ID]
  python3 cinder-memory.py stats
  python3 cinder-memory.py import-jsonl conversation-log.jsonl
"""

import sqlite3
import json
import os
import sys
import uuid
import math
import re
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

# Memory DB lives alongside the script (USB-portable)
SCRIPT_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = SCRIPT_DIR / "memory"
DB_PATH = MEMORY_DIR / "cinder-memory.db"
INDEX_PATH = MEMORY_DIR / "memory-index.json"

# ── Schema ──────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    tokens_approx INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    turn_count INTEGER DEFAULT 0,
    summary TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('fact', 'preference', 'event', 'insight', 'distilled')),
    content TEXT NOT NULL,
    source_session TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    importance REAL DEFAULT 0.5,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tfidf_index (
    term TEXT NOT NULL,
    doc_id INTEGER NOT NULL,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('conversation', 'memory')),
    tf REAL NOT NULL,
    PRIMARY KEY (term, doc_id, doc_type)
);

CREATE TABLE IF NOT EXISTS index_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_tfidf_term ON tfidf_index(term);
"""


def get_db():
    """Get database connection, creating schema if needed."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def approx_tokens(text):
    """Rough token count (words * 1.3)."""
    return int(len(text.split()) * 1.3)


# ── Session Management ──────────────────────────────────────

def get_or_create_session(conn, session_id=None):
    """Get existing session or create a new one."""
    if session_id:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row:
            return session_id
    new_id = session_id or str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, started_at) VALUES (?, ?)",
        (new_id, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    return new_id


def current_session(conn):
    """Get the most recent active session, or create one."""
    row = conn.execute(
        "SELECT session_id FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if row:
        return row["session_id"]
    return get_or_create_session(conn)


# ── Core Operations ─────────────────────────────────────────

def save_message(conn, role, content, session_id=None, metadata=None):
    """Save a conversation message."""
    sid = session_id or current_session(conn)
    get_or_create_session(conn, sid)
    tokens = approx_tokens(content)
    meta = json.dumps(metadata or {})
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, tokens_approx, metadata) VALUES (?, ?, ?, ?, ?)",
        (sid, role, content, tokens, meta)
    )
    conn.execute(
        "UPDATE sessions SET turn_count = turn_count + 1 WHERE session_id = ?",
        (sid,)
    )
    conn.commit()
    return sid


def load_messages(conn, limit=20, session_id=None):
    """Load recent messages, optionally filtered by session."""
    if session_id:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return list(reversed(rows))


def save_memory(conn, mem_type, content, source_session=None, importance=0.5, metadata=None):
    """Save a long-term memory."""
    meta = json.dumps(metadata or {})
    conn.execute(
        "INSERT INTO memories (type, content, source_session, importance, metadata) VALUES (?, ?, ?, ?, ?)",
        (mem_type, content, source_session, importance, meta)
    )
    conn.commit()


# ── TF-IDF Search ───────────────────────────────────────────

def tokenize(text):
    """Simple tokenizer: lowercase, split on non-alpha, remove stopwords."""
    STOPWORDS = {
        'the', 'a', 'an', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'before', 'after', 'and', 'but', 'or', 'not', 'no', 'nor', 'so',
        'yet', 'both', 'either', 'neither', 'each', 'every', 'all', 'any',
        'few', 'more', 'most', 'other', 'some', 'such', 'than', 'too', 'very',
        'just', 'that', 'this', 'these', 'those', 'it', 'its', 'i', 'me',
        'my', 'we', 'our', 'you', 'your', 'he', 'him', 'his', 'she', 'her',
        'they', 'them', 'their', 'what', 'which', 'who', 'whom', 'how',
        'when', 'where', 'why', 'if', 'then', 'else', 'about', 'up', 'out',
    }
    words = re.findall(r'[a-z0-9]+', text.lower())
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def build_index(conn):
    """Build TF-IDF index from all conversations and memories."""
    conn.execute("DELETE FROM tfidf_index")

    # Index conversations (group by session as documents)
    sessions = conn.execute(
        "SELECT DISTINCT session_id FROM conversations"
    ).fetchall()

    doc_count = 0
    df = Counter()  # document frequency per term
    docs = []

    for sess in sessions:
        sid = sess["session_id"]
        messages = conn.execute(
            "SELECT content FROM conversations WHERE session_id = ? AND role != 'system'",
            (sid,)
        ).fetchall()
        text = " ".join(m["content"] for m in messages)
        tokens = tokenize(text)
        if not tokens:
            continue
        doc_count += 1
        term_counts = Counter(tokens)
        unique_terms = set(tokens)
        for t in unique_terms:
            df[t] += 1
        docs.append(("conversation", sid, term_counts, len(tokens)))

    # Index memories
    mems = conn.execute("SELECT id, content FROM memories").fetchall()
    for mem in mems:
        tokens = tokenize(mem["content"])
        if not tokens:
            continue
        doc_count += 1
        term_counts = Counter(tokens)
        unique_terms = set(tokens)
        for t in unique_terms:
            df[t] += 1
        docs.append(("memory", mem["id"], term_counts, len(tokens)))

    # Compute TF-IDF and store
    if doc_count == 0:
        conn.commit()
        return 0

    batch = []
    for doc_type, doc_id, term_counts, total_tokens in docs:
        for term, count in term_counts.items():
            tf = count / total_tokens
            idf = math.log(doc_count / (1 + df[term]))
            tfidf = tf * idf
            if tfidf > 0.001:  # threshold to keep index lean
                if doc_type == "conversation":
                    # Map session_id to numeric for storage
                    numeric_id = hash(doc_id) % (2**31)
                else:
                    numeric_id = doc_id
                batch.append((term, numeric_id, doc_type, tfidf))

    conn.executemany(
        "INSERT OR REPLACE INTO tfidf_index (term, doc_id, doc_type, tf) VALUES (?, ?, ?, ?)",
        batch
    )

    # Store session ID mapping
    session_map = {hash(s["session_id"]) % (2**31): s["session_id"] for s in sessions}
    conn.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES ('session_map', ?)",
        (json.dumps(session_map),)
    )
    conn.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES ('doc_count', ?)",
        (str(doc_count),)
    )
    conn.execute(
        "INSERT OR REPLACE INTO index_meta (key, value) VALUES ('indexed_at', ?)",
        (datetime.now(timezone.utc).isoformat(),)
    )

    conn.commit()
    return len(batch)


def search(conn, query, limit=10):
    """Search conversations and memories using TF-IDF."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Score documents by sum of TF-IDF for matching terms
    placeholders = ",".join("?" * len(query_tokens))
    rows = conn.execute(f"""
        SELECT doc_id, doc_type, SUM(tf) as score
        FROM tfidf_index
        WHERE term IN ({placeholders})
        GROUP BY doc_id, doc_type
        ORDER BY score DESC
        LIMIT ?
    """, query_tokens + [limit]).fetchall()

    # Resolve results
    results = []
    session_map = {}
    meta_row = conn.execute(
        "SELECT value FROM index_meta WHERE key = 'session_map'"
    ).fetchone()
    if meta_row:
        raw_map = json.loads(meta_row["value"])
        session_map = {int(k): v for k, v in raw_map.items()}

    for row in rows:
        if row["doc_type"] == "conversation":
            sid = session_map.get(row["doc_id"], str(row["doc_id"]))
            messages = conn.execute(
                "SELECT role, content, created_at FROM conversations WHERE session_id = ? ORDER BY created_at LIMIT 5",
                (sid,)
            ).fetchall()
            preview = " | ".join(f"[{m['role']}] {m['content'][:80]}" for m in messages)
            results.append({
                "type": "conversation",
                "session_id": sid,
                "score": row["score"],
                "preview": preview
            })
        elif row["doc_type"] == "memory":
            mem = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (row["doc_id"],)
            ).fetchone()
            if mem:
                results.append({
                    "type": "memory",
                    "memory_type": mem["type"],
                    "content": mem["content"],
                    "score": row["score"],
                    "importance": mem["importance"]
                })

    return results


def distill_session(conn, session_id):
    """Extract key facts/insights from a session and store as long-term memories."""
    messages = conn.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()

    if not messages:
        return 0

    # Simple distillation: extract user questions and assistant key points
    facts = []
    for msg in messages:
        content = msg["content"].strip()
        if not content:
            continue
        # User preferences and statements
        if msg["role"] == "user" and len(content) > 20:
            # Look for preference patterns
            for pattern in ["i like", "i prefer", "i want", "i need", "my name", "i am", "i'm"]:
                if pattern in content.lower():
                    facts.append(("preference", content[:200]))
                    break
        # Assistant insights
        if msg["role"] == "assistant" and len(content) > 50:
            sentences = content.split(". ")
            for s in sentences[:2]:
                if len(s) > 30:
                    facts.append(("insight", s[:200]))

    count = 0
    for mem_type, content in facts[:10]:  # cap at 10 per session
        save_memory(conn, mem_type, content, source_session=session_id, importance=0.6)
        count += 1

    # Mark session as distilled
    conn.execute(
        "UPDATE sessions SET ended_at = COALESCE(ended_at, ?) WHERE session_id = ?",
        (datetime.now(timezone.utc).isoformat(), session_id)
    )
    conn.commit()
    return count


def recall(conn, query=None, limit=8):
    """Recall relevant memories for context injection into conversations.
    If query provided, uses TF-IDF search. Otherwise returns recent high-importance memories.
    Returns a list of memory dicts suitable for system prompt injection."""
    results = []

    if query:
        # Search for query-relevant memories first
        search_results = search(conn, query, limit=limit)
        for r in search_results:
            if r["type"] == "memory":
                results.append({
                    "type": r["memory_type"],
                    "content": r["content"],
                    "score": r["score"]
                })

    # Always include high-importance memories (facts and preferences)
    seen_content = {r["content"] for r in results}
    important = conn.execute(
        "SELECT type, content, importance FROM memories "
        "WHERE importance >= 0.5 AND type IN ('fact', 'preference') "
        "ORDER BY importance DESC, created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()

    for m in important:
        if m["content"] not in seen_content:
            results.append({
                "type": m["type"],
                "content": m["content"],
                "score": m["importance"]
            })
            seen_content.add(m["content"])

    # Cap total results
    return results[:limit]


def import_jsonl(conn, filepath):
    """Import from JSONL conversation log (migration from Electron's basic format)."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return 0

    session_id = get_or_create_session(conn, f"import-{str(uuid.uuid4())[:6]}")
    count = 0
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                role = entry.get("role", "user")
                content = entry.get("content", "")
                ts = entry.get("ts", datetime.now(timezone.utc).isoformat())
                if content:
                    conn.execute(
                        "INSERT INTO conversations (session_id, role, content, created_at, tokens_approx) VALUES (?, ?, ?, ?, ?)",
                        (session_id, role, content, ts, approx_tokens(content))
                    )
                    count += 1
            except json.JSONDecodeError:
                continue

    conn.execute(
        "UPDATE sessions SET turn_count = ? WHERE session_id = ?",
        (count, session_id)
    )
    conn.commit()
    return count


def get_stats(conn):
    """Return memory system statistics."""
    stats = {}
    row = conn.execute("SELECT COUNT(*) as c FROM conversations").fetchone()
    stats["total_messages"] = row["c"]

    row = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()
    stats["total_sessions"] = row["c"]

    row = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()
    stats["total_memories"] = row["c"]

    row = conn.execute("SELECT COUNT(DISTINCT term) as c FROM tfidf_index").fetchone()
    stats["indexed_terms"] = row["c"]

    row = conn.execute("SELECT SUM(tokens_approx) as c FROM conversations").fetchone()
    stats["total_tokens"] = row["c"] or 0

    row = conn.execute("SELECT value FROM index_meta WHERE key = 'indexed_at'").fetchone()
    stats["last_indexed"] = row["value"] if row else "never"

    # Memory type breakdown
    types = conn.execute(
        "SELECT type, COUNT(*) as c FROM memories GROUP BY type"
    ).fetchall()
    stats["memory_types"] = {t["type"]: t["c"] for t in types}

    return stats


# ── CLI Interface ───────────────────────────────────────────

def _row_to_dict(row):
    """Convert sqlite3.Row to plain dict."""
    return {k: row[k] for k in row.keys()}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    # Parse global --json flag
    use_json = "--json" in sys.argv
    args = [a for a in sys.argv if a != "--json"]

    cmd = args[1] if len(args) > 1 else None
    conn = get_db()

    if cmd == "save" and len(args) >= 4:
        role = args[2]
        content = args[3]
        session_id = args[4] if len(args) > 4 else None
        sid = save_message(conn, role, content, session_id)
        if use_json:
            print(json.dumps({"ok": True, "session_id": sid, "role": role}))
        else:
            print(f"Saved [{role}] to session {sid}")

    elif cmd == "load":
        limit = 20
        session_id = None
        i = 2
        while i < len(args):
            if args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            elif args[i] == "--session" and i + 1 < len(args):
                session_id = args[i + 1]
                i += 2
            else:
                i += 1
        messages = load_messages(conn, limit, session_id)
        if use_json:
            print(json.dumps([_row_to_dict(m) for m in messages]))
        else:
            for m in messages:
                print(f"[{m['created_at']}] {m['role'].upper()}: {m['content'][:200]}")

    elif cmd == "search" and len(args) >= 3:
        query = " ".join(args[2:])
        results = search(conn, query)
        if use_json:
            print(json.dumps(results))
        else:
            if not results:
                print("No results. Try 'build-index' first if index is empty.")
            for r in results:
                if r["type"] == "conversation":
                    print(f"[session:{r['session_id']}] score={r['score']:.3f}")
                    print(f"  {r['preview'][:160]}")
                else:
                    print(f"[{r['memory_type']}] score={r['score']:.3f} importance={r['importance']}")
                    print(f"  {r['content'][:160]}")
                print()

    elif cmd == "sessions":
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 20"
        ).fetchall()
        if use_json:
            print(json.dumps([_row_to_dict(r) for r in rows]))
        else:
            for r in rows:
                status = "active" if not r["ended_at"] else "ended"
                print(f"{r['session_id']}  turns={r['turn_count']}  {status}  started={r['started_at']}")
                if r["summary"]:
                    print(f"  summary: {r['summary'][:120]}")

    elif cmd == "new-session":
        sid = get_or_create_session(conn)
        if use_json:
            print(json.dumps({"session_id": sid}))
        else:
            print(f"New session: {sid}")

    elif cmd == "distill":
        session_id = args[2] if len(args) > 2 else current_session(conn)
        count = distill_session(conn, session_id)
        if use_json:
            print(json.dumps({"ok": True, "count": count, "session_id": session_id}))
        else:
            print(f"Distilled {count} memories from session {session_id}")

    elif cmd == "build-index":
        count = build_index(conn)
        if use_json:
            print(json.dumps({"ok": True, "count": count}))
        else:
            print(f"Indexed {count} term-document pairs")

    elif cmd == "import-jsonl" and len(args) >= 3:
        count = import_jsonl(conn, args[2])
        if use_json:
            print(json.dumps({"ok": True, "count": count}))
        else:
            print(f"Imported {count} messages")

    elif cmd == "stats":
        stats = get_stats(conn)
        if use_json:
            print(json.dumps(stats))
        else:
            print(f"Messages: {stats['total_messages']}")
            print(f"Sessions: {stats['total_sessions']}")
            print(f"Memories: {stats['total_memories']}")
            print(f"Tokens (approx): {stats['total_tokens']}")
            print(f"Indexed terms: {stats['indexed_terms']}")
            print(f"Last indexed: {stats['last_indexed']}")
            if stats["memory_types"]:
                print(f"Memory types: {stats['memory_types']}")

    elif cmd == "remember" and len(args) >= 4:
        mem_type = args[2]
        content = " ".join(args[3:])
        save_memory(conn, mem_type, content)
        if use_json:
            print(json.dumps({"ok": True, "type": mem_type}))
        else:
            print(f"Saved [{mem_type}] memory")

    elif cmd == "recall":
        query = " ".join(args[2:]) if len(args) > 2 else None
        limit = 8
        # Parse --limit flag
        if "--limit" in args:
            idx = args.index("--limit")
            if idx + 1 < len(args):
                limit = int(args[idx + 1])
                query_parts = [a for a in args[2:] if a not in ("--limit", args[idx + 1])]
                query = " ".join(query_parts) if query_parts else None
        results = recall(conn, query, limit)
        if use_json:
            print(json.dumps(results))
        else:
            if not results:
                print("No memories to recall.")
            for r in results:
                print(f"[{r['type']}] {r['content'][:160]}")

    else:
        print(__doc__)

    conn.close()


if __name__ == "__main__":
    main()
