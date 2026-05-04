#!/usr/bin/env python3
"""
journal-context.py — Surface related past journals before writing a new one.

Usage:
    python3 scripts/journal-context.py "memory retrieval"
    python3 scripts/journal-context.py "USB cinder build"

Returns the 5 most relevant past journals based on keyword overlap.
This puts the accumulated archive into the composition context.
"""

import sys
import sqlite3
import os
import re
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'memory.db')
JOURNALS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'creative', 'journals')

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'is', 'it', 'was', 'are', 'be', 'been', 'have', 'has',
    'this', 'that', 'what', 'i', 'my', 'me', 'we', 'not', 'its', 'from',
    'by', 'as', 'if', 'so', 'do', 'did', 'no', 'up', 'out', 'which', 'who',
    'loop', 'journal', 'meridian',
}

def tokenize(text):
    words = re.findall(r'[a-z]+', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]

def score_match(query_tokens, doc_text):
    doc_tokens = tokenize(doc_text)
    doc_set = Counter(doc_tokens)
    score = 0
    for token in query_tokens:
        if token in doc_set:
            score += doc_set[token]
    return score

def find_related(query, limit=5, types=('journal',)):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    type_placeholders = ','.join('?' * len(types))
    cur.execute(
        f"SELECT id, type, title, content, created FROM creative WHERE type IN ({type_placeholders}) ORDER BY id DESC",
        types
    )
    rows = cur.fetchall()
    conn.close()

    query_tokens = tokenize(query)
    if not query_tokens:
        print("No usable keywords found in query.")
        return

    scored = []
    for row in rows:
        id_, type_, title, content, created = row
        combined = f"{title or ''} {content or ''}"
        s = score_match(query_tokens, combined)
        if s > 0:
            scored.append((s, id_, type_, title, content, created))

    scored.sort(reverse=True)
    results = scored[:limit]

    if not results:
        print(f"No related records found for: {query}")
        return

    print(f"Related past work for: '{query}'")
    print(f"Query tokens: {query_tokens[:8]}")
    print("=" * 60)

    for rank, (score, id_, type_, title, content, created) in enumerate(results, 1):
        print(f"\n{rank}. [{type_}] {title or '(untitled)'}")
        if created:
            print(f"   Date: {created[:10]}")
        if content:
            snippet = content[:200].replace('\n', ' ')
            print(f"   Summary: {snippet}")

        # Try to find full journal file
        if type_ == 'journal' and title:
            slug = title.lower().replace(' ', '-').replace('/', '-')
            for fname in os.listdir(JOURNALS_DIR) if os.path.exists(JOURNALS_DIR) else []:
                if slug[:20] in fname.lower() or fname.lower()[:20] in slug[:20]:
                    print(f"   File: creative/journals/{fname}")
                    break

    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/journal-context.py <topic>")
        print("Example: python3 scripts/journal-context.py 'memory retrieval capsule'")
        sys.exit(1)

    query = ' '.join(sys.argv[1:])
    find_related(query)
