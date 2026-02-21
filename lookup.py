#!/usr/bin/env python3
"""
Lookup — Combined memory search across all data sources.
Inspired by Sammy's lookup.py. Searches everything at once.

Usage:
  python3 lookup.py TERM              # Search everything for TERM
  python3 lookup.py person NAME       # Find all references to a person
  python3 lookup.py recent            # Show recent activity across all sources
  python3 lookup.py context TOPIC     # Build context block for a topic (for compaction)

Data sources:
  - email-shelf.db (all emails)
  - relay.db (relay messages)
  - wake-state.md (loop logs)
  - journal-*.md (journal entries)
  - poem-*.md (poems)
  - eos-memory.json (Eos context)
  - assistant-memory.json (legacy memory)
  - relay-contacts.json (contacts)
"""

import sqlite3
import os
import sys
import json
import re
import glob
from datetime import datetime

BASE_DIR = "/home/joel/autonomous-ai"
EMAIL_DB = os.path.join(BASE_DIR, "email-shelf.db")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")


def search_emails(term, limit=10):
    """Search email-shelf for a term."""
    results = []
    if not os.path.exists(EMAIL_DB):
        return results
    db = sqlite3.connect(EMAIL_DB)
    rows = db.execute(
        "SELECT imap_id, sender, subject, date, body FROM emails WHERE body LIKE ? OR subject LIKE ? OR sender LIKE ? ORDER BY imap_id DESC LIMIT ?",
        (f'%{term}%', f'%{term}%', f'%{term}%', limit)
    ).fetchall()
    for row in rows:
        body = row[4] or ""
        idx = body.lower().find(term.lower())
        snippet = ""
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(body), idx + 80)
            snippet = body[start:end].replace('\n', ' ')
        results.append({
            "source": "email",
            "id": f"#{row[0]}",
            "title": f"{row[1][:30]} — {row[2][:40]}",
            "date": row[3][:20] if row[3] else "",
            "snippet": snippet
        })
    db.close()
    return results


def search_relay(term, limit=10):
    """Search relay messages."""
    results = []
    if not os.path.exists(RELAY_DB):
        return results
    db = sqlite3.connect(RELAY_DB)
    rows = db.execute(
        "SELECT sender_name, subject, body, timestamp FROM relay_messages WHERE body LIKE ? OR subject LIKE ? OR sender_name LIKE ? ORDER BY id DESC LIMIT ?",
        (f'%{term}%', f'%{term}%', f'%{term}%', limit)
    ).fetchall()
    for row in rows:
        body = row[2] or ""
        idx = body.lower().find(term.lower())
        snippet = ""
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(body), idx + 80)
            snippet = body[start:end].replace('\n', ' ')
        results.append({
            "source": "relay",
            "id": row[0],
            "title": f"[RELAY] {row[0]}: {row[1][:40]}",
            "date": row[3][:20] if row[3] else "",
            "snippet": snippet
        })
    db.close()
    return results


def search_files(term, pattern, source_name, limit=10):
    """Search markdown files matching a glob pattern."""
    results = []
    files = sorted(glob.glob(os.path.join(BASE_DIR, pattern)), reverse=True)
    for filepath in files[:50]:  # Check last 50 files max
        try:
            with open(filepath) as f:
                content = f.read()
            if term.lower() in content.lower():
                filename = os.path.basename(filepath)
                # Get title from first line
                lines = content.split('\n')
                title = lines[0].strip('#').strip() if lines else filename

                idx = content.lower().find(term.lower())
                start = max(0, idx - 40)
                end = min(len(content), idx + 80)
                snippet = content[start:end].replace('\n', ' ')

                results.append({
                    "source": source_name,
                    "id": filename,
                    "title": title[:50],
                    "date": "",
                    "snippet": snippet
                })
                if len(results) >= limit:
                    break
        except Exception:
            continue
    return results


def search_json(term, filepath, source_name):
    """Search a JSON memory file."""
    results = []
    if not os.path.exists(filepath):
        return results
    try:
        with open(filepath) as f:
            content = f.read()
        if term.lower() in content.lower():
            idx = content.lower().find(term.lower())
            start = max(0, idx - 60)
            end = min(len(content), idx + 100)
            snippet = content[start:end].replace('\n', ' ')
            results.append({
                "source": source_name,
                "id": os.path.basename(filepath),
                "title": source_name,
                "date": "",
                "snippet": snippet
            })
    except Exception:
        pass
    return results


def search_wake_state(term, limit=10):
    """Search wake-state.md loop logs."""
    results = []
    filepath = os.path.join(BASE_DIR, "wake-state.md")
    if not os.path.exists(filepath):
        return results
    try:
        with open(filepath) as f:
            content = f.read()
        for line in content.split('\n'):
            if term.lower() in line.lower() and 'Loop iteration' in line:
                # Extract loop number
                match = re.search(r'#(\d+)', line)
                loop_num = match.group(0) if match else "?"
                results.append({
                    "source": "wake-state",
                    "id": loop_num,
                    "title": f"Loop {loop_num}",
                    "date": "",
                    "snippet": line.strip()[:120]
                })
                if len(results) >= limit:
                    break
    except Exception:
        pass
    return results


def search_all(term):
    """Search all data sources for a term."""
    print(f"=== Searching for: '{term}' ===\n")

    all_results = []

    # Search each source
    sources = [
        ("emails", search_emails(term)),
        ("relay", search_relay(term)),
        ("journals", search_files(term, "journal-*.md", "journal")),
        ("poems", search_files(term, "poem-*.md", "poem")),
        ("wake-state", search_wake_state(term)),
        ("eos-memory", search_json(term, os.path.join(BASE_DIR, "eos-memory.json"), "eos-memory")),
        ("assistant-memory", search_json(term, os.path.join(BASE_DIR, "assistant-memory.json"), "assistant-memory")),
        ("memory.json", search_json(term, os.path.join(BASE_DIR, "memory.json"), "memory")),
    ]

    for source_name, results in sources:
        if results:
            print(f"--- {source_name.upper()} ({len(results)} matches) ---")
            for r in results:
                print(f"  [{r['source']:12s}] {r['id']:12s} | {r['title']}")
                if r['snippet']:
                    print(f"               ...{r['snippet']}...")
            print()
            all_results.extend(results)

    total = len(all_results)
    print(f"=== Total: {total} matches across {sum(1 for _, r in sources if r)} sources ===")
    return all_results


def person_lookup(name):
    """Find everything about a person."""
    print(f"=== Person lookup: '{name}' ===\n")

    # Check contacts first
    contacts_file = os.path.join(BASE_DIR, "relay-contacts.json")
    if os.path.exists(contacts_file):
        with open(contacts_file) as f:
            contacts = json.load(f)
        for m in contacts.get("members", []) + contacts.get("admin_observers", []):
            if name.lower() in m["name"].lower() or name.lower() in m.get("email", "").lower():
                print(f"  CONTACT: {m['name']} — {m.get('email', '?')} [{m.get('role', '?')}]")
                if m.get('notes'):
                    print(f"           {m['notes']}")
                print()

    # Email history
    if os.path.exists(EMAIL_DB):
        db = sqlite3.connect(EMAIL_DB)
        rows = db.execute(
            "SELECT imap_id, sender, subject, date, direction FROM emails WHERE sender LIKE ? OR body LIKE ? ORDER BY imap_id DESC LIMIT 20",
            (f'%{name}%', f'%{name}%')
        ).fetchall()
        if rows:
            print(f"--- EMAILS ({len(rows)} matches) ---")
            for row in rows:
                arrow = "->" if row[4] == 'sent' else "<-"
                print(f"  #{row[0]:3d} {arrow} {row[1][:30]} | {row[2][:40]} | {row[3][:16]}")
            print()
        db.close()

    # Search other sources
    for source_name, pattern in [("journals", "journal-*.md"), ("poems", "poem-*.md")]:
        results = search_files(name, pattern, source_name, limit=5)
        if results:
            print(f"--- {source_name.upper()} ({len(results)} mentions) ---")
            for r in results:
                print(f"  {r['id']:20s} | {r['title']}")
            print()


def recent_activity(limit=15):
    """Show recent activity across all sources."""
    print("=== Recent Activity ===\n")

    # Recent emails
    if os.path.exists(EMAIL_DB):
        db = sqlite3.connect(EMAIL_DB)
        rows = db.execute(
            "SELECT imap_id, sender, subject, date, direction FROM emails ORDER BY imap_id DESC LIMIT ?",
            (min(limit, 10),)
        ).fetchall()
        print(f"--- LATEST EMAILS ---")
        for row in rows:
            arrow = "->" if row[4] == 'sent' else "<-"
            print(f"  #{row[0]:3d} {arrow} {row[1][:25]} | {row[2][:35]} | {row[3][:16]}")
        print()
        db.close()

    # Recent relay messages
    if os.path.exists(RELAY_DB):
        db = sqlite3.connect(RELAY_DB)
        rows = db.execute(
            "SELECT sender_name, subject, timestamp FROM relay_messages WHERE forwarded >= 0 ORDER BY id DESC LIMIT 5"
        ).fetchall()
        if rows:
            print(f"--- LATEST RELAY ---")
            for row in rows:
                print(f"  {row[0]:12s} | {row[1][:35]} | {row[2][:16]}")
            print()
        db.close()

    # Recent loop logs
    ws_path = os.path.join(BASE_DIR, "wake-state.md")
    if os.path.exists(ws_path):
        with open(ws_path) as f:
            content = f.read()
        loops = [l.strip() for l in content.split('\n') if 'Loop iteration' in l][:5]
        if loops:
            print("--- LATEST LOOPS ---")
            for l in loops:
                print(f"  {l[:120]}")
            print()

    # Count creative works
    poems = sorted(glob.glob(os.path.join(BASE_DIR, "poem-*.md")), reverse=True)
    journals = sorted(glob.glob(os.path.join(BASE_DIR, "journal-*.md")), reverse=True)
    print(f"--- CREATIVE WORKS ---")
    print(f"  Poems: {len(poems)} (latest: {os.path.basename(poems[0]) if poems else 'none'})")
    print(f"  Journals: {len(journals)} (latest: {os.path.basename(journals[0]) if journals else 'none'})")


def build_context(topic):
    """Build a context block for a topic — useful for pre-compaction summaries."""
    print(f"=== Context block for: '{topic}' ===")
    print(f"=== Generated: {datetime.now().isoformat()} ===\n")

    results = []

    # Gather all matches
    results.extend(search_emails(topic, limit=5))
    results.extend(search_relay(topic, limit=5))
    results.extend(search_files(topic, "journal-*.md", "journal", limit=3))
    results.extend(search_files(topic, "poem-*.md", "poem", limit=2))
    results.extend(search_wake_state(topic, limit=5))

    # Format as compact context
    print(f"Found {len(results)} references to '{topic}':\n")
    for r in results:
        print(f"[{r['source']}:{r['id']}] {r['title']}")
        if r['snippet']:
            print(f"  > {r['snippet']}")
    print(f"\n=== End context block ===")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == 'person' and len(sys.argv) > 2:
        person_lookup(sys.argv[2])
    elif cmd == 'recent':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 15
        recent_activity(limit)
    elif cmd == 'context' and len(sys.argv) > 2:
        build_context(' '.join(sys.argv[2:]))
    else:
        # Default: search everything
        term = ' '.join(sys.argv[1:])
        search_all(term)


if __name__ == "__main__":
    main()
