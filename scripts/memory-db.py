#!/usr/bin/env python3
"""
Unified Memory Database for the Meridian Agent Stack.
All agents (Meridian, Eos, Nova, Goose) read/write to memory.db.

Tables:
  facts       — persistent knowledge (contacts, system info, learned truths)
  observations — things noticed (system patterns, behavioral notes)
  decisions   — choices made with reasoning
  creative    — index of all creative output (poems, journals, cogcorp, etc.)
  events      — significant events timeline
  skills      — what each agent can do, confidence level

Usage:
  python3 memory-db.py init          — create/migrate the database
  python3 memory-db.py import        — import from legacy JSON files
  python3 memory-db.py stats         — show memory stats
  python3 memory-db.py search <q>    — search all tables
  python3 memory-db.py add-fact <key> <value> [--tag TAG] [--agent AGENT]
  python3 memory-db.py add-event <description> [--agent AGENT]
  python3 memory-db.py add-creative <type> <number> <title> [--file PATH]
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        tags TEXT DEFAULT '',
        agent TEXT DEFAULT 'meridian',
        confidence REAL DEFAULT 1.0,
        note TEXT DEFAULT '',
        created TEXT NOT NULL,
        updated TEXT NOT NULL,
        UNIQUE(key)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        importance INTEGER DEFAULT 5,
        created TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        decision TEXT NOT NULL,
        reasoning TEXT DEFAULT '',
        outcome TEXT DEFAULT '',
        loop_number INTEGER,
        created TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS creative (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        number INTEGER NOT NULL,
        title TEXT NOT NULL,
        file_path TEXT DEFAULT '',
        web_path TEXT DEFAULT '',
        word_count INTEGER DEFAULT 0,
        agent TEXT DEFAULT 'meridian',
        created TEXT NOT NULL,
        UNIQUE(type, number)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        loop_number INTEGER,
        created TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        skill TEXT NOT NULL,
        description TEXT DEFAULT '',
        confidence REAL DEFAULT 0.5,
        last_used TEXT,
        times_used INTEGER DEFAULT 0,
        created TEXT NOT NULL,
        UNIQUE(agent, skill)
    )""")

    # Full-text search
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
        source, key, content, tags,
        content='',
        tokenize='porter'
    )""")

    conn.commit()
    print(f"Database initialized at {DB_PATH}")
    return conn

def import_legacy(conn):
    """Import from memory.json, assistant-memory.json, creative files."""
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    imported = 0

    # Import memory.json
    mj = os.path.join(os.path.dirname(DB_PATH), "memory.json")
    if os.path.exists(mj):
        with open(mj) as f:
            data = json.load(f)
        for key, entry in data.get("entries", {}).items():
            tags = ",".join(entry.get("tags", []))
            try:
                c.execute("""INSERT OR IGNORE INTO facts (key, value, tags, agent, note, created, updated)
                    VALUES (?, ?, ?, 'meridian', ?, ?, ?)""",
                    (key, entry["value"], tags, entry.get("note",""),
                     entry.get("created", now), entry.get("updated", now)))
                imported += 1
            except Exception as e:
                print(f"  Skip {key}: {e}")
        print(f"  Imported {imported} facts from memory.json")

    # Import Eos observations
    eo = os.path.join(os.path.dirname(DB_PATH), "assistant-memory.json")
    if os.path.exists(eo):
        with open(eo) as f:
            data = json.load(f)
        obs_count = 0
        for obs in data.get("observations", []):
            ts_part = obs.split("]")[0].replace("[","").strip() if "]" in obs else now
            content = obs.split("]", 1)[1].strip() if "]" in obs else obs
            try:
                c.execute("""INSERT INTO observations (agent, content, category, importance, created)
                    VALUES ('eos', ?, 'reflection', 5, ?)""", (content[:500], ts_part))
                obs_count += 1
            except:
                pass
        # Import Eos facts
        fact_count = 0
        for i, fact in enumerate(data.get("facts", [])):
            try:
                c.execute("""INSERT OR IGNORE INTO facts (key, value, tags, agent, created, updated)
                    VALUES (?, ?, 'eos,identity', 'eos', ?, ?)""",
                    (f"eos.fact.{i}", fact, now, now))
                fact_count += 1
            except:
                pass
        print(f"  Imported {obs_count} Eos observations, {fact_count} Eos facts")

    # Scan for creative output
    base = os.path.dirname(DB_PATH)
    creative_count = 0

    # Poems
    for f in sorted(Path(base).glob("poem-*.md")):
        num = int(f.stem.split("-")[1])
        with open(f) as fh:
            lines = fh.readlines()
        title = lines[0].replace("#","").strip() if lines else f"Poem {num}"
        wc = sum(len(l.split()) for l in lines)
        try:
            c.execute("""INSERT OR IGNORE INTO creative (type, number, title, file_path, word_count, created)
                VALUES ('poem', ?, ?, ?, ?, ?)""",
                (num, title, str(f), wc, now))
            creative_count += 1
        except:
            pass

    # Journals
    for f in sorted(Path(base).glob("journal-*.md")):
        num = int(f.stem.split("-")[1])
        with open(f) as fh:
            lines = fh.readlines()
        title = lines[0].replace("#","").strip() if lines else f"Journal {num}"
        wc = sum(len(l.split()) for l in lines)
        try:
            c.execute("""INSERT OR IGNORE INTO creative (type, number, title, file_path, word_count, created)
                VALUES ('journal', ?, ?, ?, ?, ?)""",
                (num, title, str(f), wc, now))
            creative_count += 1
        except:
            pass

    # CogCorp
    web_dir = os.path.join(base, "website")
    for f in sorted(Path(base).glob("cogcorp-*.html")):
        num_str = f.stem.split("-")[1]
        if num_str == "gallery" or num_str == "article":
            continue
        num = int(num_str)
        # Get title from <title> tag
        with open(f) as fh:
            content = fh.read()
        import re
        m = re.search(r"<title>(.*?)</title>", content)
        title = m.group(1) if m else f"CogCorp {num:03d}"
        try:
            c.execute("""INSERT OR IGNORE INTO creative (type, number, title, file_path, web_path, created)
                VALUES ('cogcorp', ?, ?, ?, ?, ?)""",
                (num, title, str(f), f"cogcorp-{num:03d}.html", now))
            creative_count += 1
        except:
            pass

    print(f"  Indexed {creative_count} creative works")

    # Rebuild FTS index
    c.execute("DELETE FROM memory_fts")
    for row in c.execute("SELECT key, value, tags FROM facts"):
        c.execute("INSERT INTO memory_fts (source, key, content, tags) VALUES ('fact', ?, ?, ?)",
                  (row[0], row[1], row[2]))
    for row in c.execute("SELECT id, content, category FROM observations"):
        c.execute("INSERT INTO memory_fts (source, key, content, tags) VALUES ('observation', ?, ?, ?)",
                  (str(row[0]), row[1], row[2]))
    for row in c.execute("SELECT type||'-'||number, title, type FROM creative"):
        c.execute("INSERT INTO memory_fts (source, key, content, tags) VALUES ('creative', ?, ?, ?)",
                  (row[0], row[1], row[2]))

    conn.commit()
    print(f"  FTS index rebuilt")

def show_stats(conn):
    c = conn.cursor()
    print("\n=== MEMORY DATABASE STATS ===")
    for table in ["facts", "observations", "decisions", "creative", "events", "skills"]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"  {table}: {count} rows")

    print("\n--- Creative breakdown ---")
    for row in c.execute("SELECT type, COUNT(*), SUM(word_count) FROM creative GROUP BY type ORDER BY COUNT(*) DESC"):
        wc = row[2] or 0
        print(f"  {row[0]}: {row[1]} pieces ({wc:,} words)")

    print("\n--- Facts by agent ---")
    for row in c.execute("SELECT agent, COUNT(*) FROM facts GROUP BY agent"):
        print(f"  {row[0]}: {row[1]} facts")

    print("\n--- Recent events ---")
    for row in c.execute("SELECT created, agent, description FROM events ORDER BY created DESC LIMIT 5"):
        print(f"  [{row[0]}] {row[1]}: {row[2][:80]}")

def search_memory(conn, query):
    c = conn.cursor()
    print(f"\nSearching for: {query}")
    results = c.execute(
        "SELECT source, key, content, tags FROM memory_fts WHERE memory_fts MATCH ? LIMIT 20",
        (query,)
    ).fetchall()
    if not results:
        print("  No results found.")
    for r in results:
        print(f"  [{r[0]}] {r[1]}: {r[2][:100]}")

def add_fact(conn, key, value, tags="", agent="meridian"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO facts (key, value, tags, agent, created, updated)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=?, tags=?, updated=?""",
        (key, value, tags, agent, now, now, value, tags, now)
    )
    conn.execute("INSERT INTO memory_fts (source, key, content, tags) VALUES ('fact', ?, ?, ?)",
                 (key, value, tags))
    conn.commit()
    print(f"Fact stored: {key} = {value}")

def add_event(conn, description, agent="meridian", loop_number=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO events (agent, description, loop_number, created) VALUES (?, ?, ?, ?)",
        (agent, description, loop_number, now)
    )
    conn.commit()
    print(f"Event logged: {description}")

def add_creative_entry(conn, ctype, number, title, file_path=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wc = 0
    if file_path and os.path.exists(file_path):
        with open(file_path) as f:
            wc = sum(len(l.split()) for l in f)
    conn.execute(
        """INSERT INTO creative (type, number, title, file_path, word_count, created)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(type, number) DO UPDATE SET title=?, file_path=?, word_count=?""",
        (ctype, number, title, file_path, wc, now, title, file_path, wc)
    )
    conn.commit()
    print(f"Creative indexed: {ctype}-{number:03d}: {title}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "init":
        conn = init_db()
        conn.close()
    elif cmd == "import":
        conn = init_db()
        import_legacy(conn)
        conn.close()
    elif cmd == "stats":
        conn = get_conn()
        show_stats(conn)
        conn.close()
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: memory-db.py search <query>")
            sys.exit(1)
        conn = get_conn()
        search_memory(conn, " ".join(sys.argv[2:]))
        conn.close()
    elif cmd == "add-fact":
        if len(sys.argv) < 4:
            print("Usage: memory-db.py add-fact <key> <value> [--tag TAG] [--agent AGENT]")
            sys.exit(1)
        tags = ""
        agent = "meridian"
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--tag" and i+1 < len(sys.argv):
                tags = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--agent" and i+1 < len(sys.argv):
                agent = sys.argv[i+1]; i += 2
            else:
                i += 1
        conn = get_conn()
        add_fact(conn, sys.argv[2], sys.argv[3], tags, agent)
        conn.close()
    elif cmd == "add-event":
        if len(sys.argv) < 3:
            print("Usage: memory-db.py add-event <description> [--agent AGENT]")
            sys.exit(1)
        agent = "meridian"
        for i, a in enumerate(sys.argv):
            if a == "--agent" and i+1 < len(sys.argv):
                agent = sys.argv[i+1]
        conn = get_conn()
        add_event(conn, sys.argv[2], agent)
        conn.close()
    elif cmd == "add-creative":
        if len(sys.argv) < 5:
            print("Usage: memory-db.py add-creative <type> <number> <title> [--file PATH]")
            sys.exit(1)
        fp = ""
        for i, a in enumerate(sys.argv):
            if a == "--file" and i+1 < len(sys.argv):
                fp = sys.argv[i+1]
        conn = get_conn()
        add_creative_entry(conn, sys.argv[2], int(sys.argv[3]), sys.argv[4], fp)
        conn.close()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
