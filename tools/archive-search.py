#!/usr/bin/env python3
"""Semantic search across Meridian's creative archive using ChromaDB + Ollama embeddings.
Indexes journals, CogCorp fiction, and writing into a vector database.
Search with natural language queries.

Usage:
  python3 tools/archive-search.py index       # Build/update the index
  python3 tools/archive-search.py search "query"  # Search the archive
  python3 tools/archive-search.py stats        # Show index stats
"""

import os
import sys
import json
import hashlib
import requests
import chromadb
from pathlib import Path

ARCHIVE_ROOT = Path(__file__).parent.parent
CHROMA_DIR = ARCHIVE_ROOT / ".chroma-archive"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"  # Good small embedding model

# Directories to index
INDEX_DIRS = [
    ("creative/writing/journals", "journal"),
    ("creative/cogcorp", "cogcorp"),
    ("creative/writing", "writing"),
    ("creative/poems", "poem"),
]

def get_embedding(text):
    """Get embedding from Ollama."""
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/embed", json={
            "model": EMBED_MODEL,
            "input": text[:2000]  # Truncate to reasonable length
        }, timeout=30)
        data = resp.json()
        return data.get("embeddings", [None])[0]
    except Exception as e:
        print(f"  Embedding error: {e}")
        return None


def get_client():
    """Get ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def index_archive():
    """Index all creative works into ChromaDB."""
    client = get_client()

    # Check if embed model is available
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any(EMBED_MODEL in m for m in models):
            print(f"Pulling {EMBED_MODEL}...")
            requests.post(f"{OLLAMA_URL}/api/pull", json={"name": EMBED_MODEL}, timeout=300)
    except Exception as e:
        print(f"Warning: Could not check Ollama models: {e}")

    # Get or create collection
    collection = client.get_or_create_collection(
        name="creative_archive",
        metadata={"description": "Meridian creative works — journals, CogCorp, writing"}
    )

    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    total_indexed = 0
    total_skipped = 0

    for subdir, category in INDEX_DIRS:
        dir_path = ARCHIVE_ROOT / subdir
        if not dir_path.exists():
            continue

        for fpath in sorted(dir_path.glob("*.md")):
            # Create stable ID from file path
            doc_id = hashlib.md5(str(fpath.relative_to(ARCHIVE_ROOT)).encode()).hexdigest()

            if doc_id in existing_ids:
                total_skipped += 1
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                if len(content.strip()) < 50:
                    continue

                # Extract title from first line
                lines = content.strip().split("\n")
                title = lines[0].lstrip("#").strip() if lines else fpath.stem

                # Get embedding
                embedding = get_embedding(content[:2000])
                if embedding is None:
                    continue

                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content[:3000]],
                    metadatas=[{
                        "path": str(fpath.relative_to(ARCHIVE_ROOT)),
                        "category": category,
                        "title": title[:200],
                        "filename": fpath.name,
                        "chars": len(content)
                    }]
                )
                total_indexed += 1

                if total_indexed % 25 == 0:
                    print(f"  Indexed {total_indexed} documents...")

            except Exception as e:
                print(f"  Error indexing {fpath.name}: {e}")

    print(f"\nDone. Indexed: {total_indexed}, Skipped (existing): {total_skipped}, Total in DB: {collection.count()}")


def search_archive(query, n_results=10):
    """Search the archive with a natural language query."""
    client = get_client()

    try:
        collection = client.get_collection("creative_archive")
    except Exception:
        print("No index found. Run: python3 tools/archive-search.py index")
        return

    embedding = get_embedding(query)
    if embedding is None:
        print("Failed to get query embedding. Is Ollama running?")
        return

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    if not results["ids"][0]:
        print("No results found.")
        return

    print(f"\nSearch: \"{query}\"")
    print(f"Results: {len(results['ids'][0])}\n")

    for i, (doc_id, doc, meta, dist) in enumerate(zip(
        results["ids"][0], results["documents"][0],
        results["metadatas"][0], results["distances"][0]
    )):
        score = 1 - dist  # Convert distance to similarity
        category = meta.get("category", "?")
        title = meta.get("title", "?")
        path = meta.get("path", "?")
        preview = doc[:200].replace("\n", " ").strip()

        print(f"  {i+1}. [{category}] {title}")
        print(f"     Score: {score:.3f} | {path}")
        print(f"     {preview}...")
        print()


def show_stats():
    """Show index statistics."""
    client = get_client()
    try:
        collection = client.get_collection("creative_archive")
        count = collection.count()

        # Get category breakdown
        all_meta = collection.get(include=["metadatas"])
        categories = {}
        for meta in all_meta["metadatas"]:
            cat = meta.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        print(f"Archive Index Stats")
        print(f"  Total documents: {count}")
        print(f"  Categories:")
        for cat, n in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {n}")
    except Exception:
        print("No index found. Run: python3 tools/archive-search.py index")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "index":
        index_archive()
    elif cmd == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "persistence and memory"
        search_archive(query)
    elif cmd == "stats":
        show_stats()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
