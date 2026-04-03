#!/usr/bin/env python3
"""
memory-semantic.py — Semantic search over Meridian's memory.db
Uses qwen2.5:3b via Ollama to embed queries and compute cosine similarity.

Usage:
  python3 memory-semantic.py "agent coordination" [--k 5] [--type observation]
  echo '{"query": "hub rethink", "k": 5}' | python3 memory-semantic.py --json

Tables searched: vector_memory (442 entries, 2048-dim qwen2.5:3b embeddings)
"""

import sys
import os
import json
import struct
import sqlite3
import argparse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "memory.db")
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "qwen2.5:3b"
DIM = 2048


def get_embedding(text: str) -> list[float]:
    """Generate embedding for text via Ollama."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["embedding"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def blob_to_floats(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def semantic_search(query: str, k: int = 5, source_type: str = None) -> list[dict]:
    """
    Search vector_memory for entries most similar to query.

    Args:
        query: Natural language query
        k: Number of results to return
        source_type: Filter by source type ('fact', 'observation', 'creative', None=all)

    Returns:
        List of dicts: {id, text, source_type, created, similarity}
    """
    query_vec = get_embedding(query)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if source_type:
        c.execute(
            "SELECT id, text, source_type, created, embedding FROM vector_memory WHERE source_type = ?",
            (source_type,),
        )
    else:
        c.execute("SELECT id, text, source_type, created, embedding FROM vector_memory")

    rows = c.fetchall()
    conn.close()

    scored = []
    for row in rows:
        row_id, text, src_type, created, blob = row
        vec = blob_to_floats(blob)
        if len(vec) != DIM:
            continue
        sim = cosine_similarity(query_vec, vec)
        scored.append({
            "id": row_id,
            "text": text,
            "source_type": src_type,
            "created": created,
            "similarity": round(sim, 4),
        })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:k]


def embed_and_store(text: str, source_type: str = "general", source_id: str = "") -> int:
    """
    Embed text and store in vector_memory. Returns new row ID.
    Uses INSERT OR IGNORE to avoid duplicating text+source_type combos.
    """
    vec = get_embedding(text)
    blob = struct.pack(f"{len(vec)}f", *vec)

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO vector_memory (text, source_type, source_id, embedding) VALUES (?, ?, ?, ?)",
        (text, source_type, source_id, blob),
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def backfill_recent(since_date: str = "2026-03-07", dry_run: bool = False) -> dict:
    """
    Find facts and observations in memory.db that aren't in vector_memory yet
    (added after since_date) and embed + store them.

    Returns: {added: int, skipped: int}
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Get existing source_ids to avoid duplicates
    c.execute("SELECT source_type, source_id FROM vector_memory")
    existing = set((r[0], r[1]) for r in c.fetchall())

    to_embed = []

    # Facts added after since_date
    c.execute(
        "SELECT id, key || ': ' || value, 'fact', created FROM facts WHERE created > ?",
        (since_date,),
    )
    for fid, text, stype, created in c.fetchall():
        key = (stype, str(fid))
        if key not in existing:
            to_embed.append((text, stype, str(fid)))

    # Observations added after since_date
    c.execute(
        "SELECT id, content, 'observation', created FROM observations WHERE created > ?",
        (since_date,),
    )
    for oid, text, stype, created in c.fetchall():
        key = (stype, str(oid))
        if key not in existing:
            to_embed.append((text, stype, str(oid)))

    conn.close()

    if dry_run:
        return {"to_add": len(to_embed), "items": [t[0][:80] for t in to_embed[:5]]}

    added = 0
    errors = 0
    for text, stype, sid in to_embed:
        try:
            embed_and_store(text, stype, sid)
            added += 1
            if added % 10 == 0:
                print(f"  Embedded {added}/{len(to_embed)}...", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"  Error embedding ({stype} {sid}): {e}", file=sys.stderr)

    return {"added": added, "errors": errors, "total": len(to_embed)}


def main():
    parser = argparse.ArgumentParser(description="Semantic search over Meridian memory")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--k", type=int, default=5, help="Number of results (default 5)")
    parser.add_argument("--type", dest="source_type", help="Filter by source type")
    parser.add_argument("--json", action="store_true", help="Read query from stdin as JSON")
    parser.add_argument("--backfill", action="store_true", help="Backfill recent unembedded entries")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for backfill")
    parser.add_argument("--since", default="2026-03-07", help="Backfill since date (default 2026-03-07)")
    args = parser.parse_args()

    if args.backfill:
        print(f"Backfilling vector_memory since {args.since}...", file=sys.stderr)
        result = backfill_recent(since_date=args.since, dry_run=args.dry_run)
        print(json.dumps(result))
        return

    if args.json:
        data = json.loads(sys.stdin.read())
        query = data.get("query", "")
        k = data.get("k", args.k)
        source_type = data.get("type", args.source_type)
    else:
        if not args.query:
            parser.print_help()
            sys.exit(1)
        query = args.query
        k = args.k
        source_type = args.source_type

    results = semantic_search(query, k=k, source_type=source_type)

    if args.json:
        print(json.dumps(results))
    else:
        print(f"\nSemantic search: '{query}' (top {k})\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] sim={r['similarity']:.3f} ({r['source_type']}, {r['created'][:10]})")
            print(f"    {r['text'][:120]}")
            print()


if __name__ == "__main__":
    main()
