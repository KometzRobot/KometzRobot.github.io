#!/usr/bin/env python3
"""
semantic-memory.py — Semantic Vector Memory Layer for Meridian

Uses ChromaDB + nomic-embed-text (Ollama) for meaning-based memory retrieval.
Auto-indexes facts, observations, decisions, dossiers, and creative works.

This is Layer 14 of the Meridian Memory Architecture:
  1-13: capsule, handoff, personality, wake-state, facts, observations,
        decisions, dossiers, spiderweb, hebbian, relay, soma, creative
  14:   Semantic vector memory (THIS) — meaning-based cross-layer retrieval

Usage:
  python3 semantic-memory.py index          # Index all memory tables
  python3 semantic-memory.py query "text"   # Search by meaning
  python3 semantic-memory.py status         # Show index stats
  python3 semantic-memory.py auto           # Index + show stats (for cron)

Architecture:
  - ChromaDB persistent store in data/chroma/
  - nomic-embed-text via Ollama for embeddings (768-dim)
  - Collections: facts, observations, decisions, dossiers, creative, journals
  - Cross-collection search for unified semantic retrieval
"""

import os
import sys
import json
import sqlite3
import glob
from datetime import datetime, timezone

_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

MEMORY_DB = os.path.join(BASE, "memory.db")
CHROMA_DIR = os.path.join(BASE, "data", "chroma")
EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"


def get_embedding(text):
    """Get embedding from Ollama nomic-embed-text."""
    import urllib.request
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text[:8000]}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["embedding"]
    except Exception as e:
        print(f"  Embedding error: {e}")
        return None


def get_chroma_client():
    """Get or create persistent ChromaDB client."""
    import chromadb
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def index_table(client, table_name, rows, id_prefix=""):
    """Index rows into a ChromaDB collection."""
    collection = client.get_or_create_collection(
        name=table_name,
        metadata={"description": f"Meridian {table_name} memory layer"}
    )

    indexed = 0
    for row_id, text, metadata in rows:
        doc_id = f"{id_prefix}{row_id}"
        # Skip if already indexed with same content
        try:
            existing = collection.get(ids=[doc_id])
            if existing and existing['documents'] and existing['documents'][0] == text:
                continue
        except Exception:
            pass

        embedding = get_embedding(text)
        if embedding:
            collection.upsert(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata] if metadata else None
            )
            indexed += 1

    return indexed, collection.count()


def index_all():
    """Index all memory tables into ChromaDB."""
    client = get_chroma_client()
    db = sqlite3.connect(MEMORY_DB)
    total_indexed = 0

    # Index facts
    print("Indexing facts...")
    rows = db.execute("SELECT id, key, value, tags, agent, created FROM facts").fetchall()
    fact_rows = [(f"fact_{r[0]}", f"{r[1]}: {r[2]}",
                  {"table": "facts", "key": r[1], "tags": r[3] or "", "agent": r[4] or "", "created": r[5] or ""})
                 for r in rows]
    n, total = index_table(client, "facts", fact_rows)
    print(f"  Facts: {n} new, {total} total")
    total_indexed += n

    # Index observations
    print("Indexing observations...")
    rows = db.execute("SELECT id, agent, content, category, importance, created FROM observations").fetchall()
    obs_rows = [(f"obs_{r[0]}", f"[{r[1]}] {r[2]}",
                 {"table": "observations", "agent": r[1] or "", "category": r[3] or "",
                  "importance": str(r[4] or 0), "created": r[5] or ""})
                for r in rows]
    n, total = index_table(client, "observations", obs_rows)
    print(f"  Observations: {n} new, {total} total")
    total_indexed += n

    # Index decisions
    print("Indexing decisions...")
    rows = db.execute("SELECT id, decision, context, outcome, agent, created FROM decisions").fetchall()
    dec_rows = [(f"dec_{r[0]}", f"Decision: {r[1]}. Context: {r[2]}. Outcome: {r[3]}",
                 {"table": "decisions", "agent": r[4] or "", "created": r[5] or ""})
                for r in rows]
    n, total = index_table(client, "decisions", dec_rows)
    print(f"  Decisions: {n} new, {total} total")
    total_indexed += n

    # Index dossiers
    print("Indexing dossiers...")
    rows = db.execute("SELECT id, topic, summary, key_facts, updated FROM dossiers").fetchall()
    dos_rows = [(f"dos_{r[0]}", f"{r[1]}: {r[2]}",
                 {"table": "dossiers", "topic": r[1] or "", "updated": r[4] or ""})
                for r in rows]
    n, total = index_table(client, "dossiers", dos_rows)
    print(f"  Dossiers: {n} new, {total} total")
    total_indexed += n

    # Index creative works
    print("Indexing creative works...")
    rows = db.execute("SELECT id, type, title, content, agent, created FROM creative").fetchall()
    cre_rows = [(f"cre_{r[0]}", f"[{r[1]}] {r[2]}: {r[3][:500]}",
                 {"table": "creative", "type": r[1] or "", "title": r[2] or "",
                  "agent": r[4] or "", "created": r[5] or ""})
                for r in rows]
    n, total = index_table(client, "creative", cre_rows)
    print(f"  Creative: {n} new, {total} total")
    total_indexed += n

    # Index journal files
    print("Indexing journals...")
    journal_rows = []
    journal_dirs = [
        os.path.join(BASE, "creative", "journals"),
        os.path.join(BASE, "creative", "writing", "journals"),
    ]
    for journal_dir in journal_dirs:
      for jpath in sorted(glob.glob(os.path.join(journal_dir, "journal-*.md"))):
        fname = os.path.basename(jpath)
        try:
            with open(jpath) as f:
                content = f.read()[:2000]
            journal_rows.append((f"jnl_{fname}", content,
                                {"table": "journals", "filename": fname}))
        except Exception:
            pass
    if journal_rows:
        n, total = index_table(client, "journals", journal_rows)
        print(f"  Journals: {n} new, {total} total")
        total_indexed += n

    # Index CogCorp markdown files from filesystem
    print("Indexing CogCorp files...")
    cogcorp_rows = []
    cogcorp_dir = os.path.join(BASE, "creative", "cogcorp")
    for cpath in sorted(glob.glob(os.path.join(cogcorp_dir, "CC-*.md"))):
        fname = os.path.basename(cpath)
        try:
            with open(cpath) as f:
                content = f.read()[:2000]
            cogcorp_rows.append((f"cc_{fname}", content,
                                {"table": "cogcorp", "filename": fname}))
        except Exception:
            pass
    if cogcorp_rows:
        n, total = index_table(client, "cogcorp", cogcorp_rows)
        print(f"  CogCorp: {n} new, {total} total")
        total_indexed += n

    # Index emails from IMAP
    print("Indexing emails...")
    email_rows = []
    try:
        # Load credentials
        sys.path.insert(0, os.path.join(BASE, "scripts"))
        try:
            from load_env import load_env
            load_env()
        except Exception:
            pass
        import imaplib
        import email as email_mod
        from email.header import decode_header
        imap = imaplib.IMAP4('127.0.0.1', 1144)
        imap.login(os.environ.get('CRED_USER', ''), os.environ.get('CRED_PASS', ''))

        for folder in ['INBOX', 'Sent']:
            imap.select(folder, readonly=True)
            status, msgs = imap.search(None, 'ALL')
            msg_ids = msgs[0].split() if msgs[0] else []
            for mid in msg_ids:
                try:
                    status, data = imap.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])')
                    hdr = data[0][1].decode('utf-8', errors='replace')
                    status, data = imap.fetch(mid, '(BODY.PEEK[TEXT])')
                    body = data[0][1].decode('utf-8', errors='replace')
                    import re
                    body = re.sub(r'<[^>]+>', ' ', body)
                    body = re.sub(r'=\n', '', body)
                    body = re.sub(r'=3D', '=', body)
                    body = re.sub(r'&nbsp;', ' ', body)
                    body = re.sub(r'\s+', ' ', body).strip()
                    text_content = f"{hdr.strip()}\n\n{body[:1500]}"
                    if len(text_content.strip()) < 50:
                        continue
                    email_rows.append((f"email_{folder}_{mid.decode()}", text_content,
                                      {"table": "emails", "folder": folder, "msg_id": mid.decode()}))
                except Exception:
                    pass
        imap.logout()
    except Exception as e:
        print(f"  Email indexing error: {e}")

    if email_rows:
        n, total = index_table(client, "emails", email_rows)
        print(f"  Emails: {n} new, {total} total")
        total_indexed += n

    db.close()
    print(f"\nTotal indexed this run: {total_indexed}")
    return total_indexed


def query(text, k=5, collection_name=None):
    """Semantic search across all memory collections."""
    client = get_chroma_client()
    embedding = get_embedding(text)
    if not embedding:
        print("Failed to generate query embedding")
        return []

    results = []
    collections = [collection_name] if collection_name else \
        ["facts", "observations", "decisions", "dossiers", "creative", "journals", "cogcorp", "emails"]

    for cname in collections:
        try:
            collection = client.get_collection(cname)
            if collection.count() == 0:
                continue
            r = collection.query(
                query_embeddings=[embedding],
                n_results=min(k, collection.count()),
                include=["documents", "metadatas", "distances"]
            )
            for i, doc in enumerate(r['documents'][0]):
                dist = r['distances'][0][i] if r['distances'] else 0
                meta = r['metadatas'][0][i] if r['metadatas'] else {}
                results.append({
                    "collection": cname,
                    "document": doc[:300],
                    "distance": dist,
                    "similarity": 1 - dist,  # cosine distance to similarity
                    "metadata": meta
                })
        except Exception:
            pass

    # Sort by similarity (highest first)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:k]


def status():
    """Show index statistics."""
    client = get_chroma_client()
    print("Semantic Memory Status:")
    print("=" * 50)
    total = 0
    for cname in ["facts", "observations", "decisions", "dossiers", "creative", "journals"]:
        try:
            collection = client.get_collection(cname)
            count = collection.count()
            total += count
            print(f"  {cname:15s}: {count:4d} vectors")
        except Exception:
            print(f"  {cname:15s}: not indexed")
    print(f"  {'TOTAL':15s}: {total:4d} vectors")
    print(f"\n  Store: {CHROMA_DIR}")
    print(f"  Model: {EMBED_MODEL}")


def main():
    if len(sys.argv) < 2:
        print("Usage: semantic-memory.py [index|query|status|auto] [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "index":
        index_all()
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: semantic-memory.py query 'search text' [--k N]")
            sys.exit(1)
        text = sys.argv[2]
        k = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--k" else 5
        results = query(text, k)
        for i, r in enumerate(results):
            sim = r['similarity']
            print(f"\n[{i+1}] ({r['collection']}, sim={sim:.3f})")
            print(f"    {r['document'][:200]}")
    elif cmd == "status":
        status()
    elif cmd == "auto":
        index_all()
        print()
        status()
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
