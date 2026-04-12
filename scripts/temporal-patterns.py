#!/usr/bin/env python3
"""
Temporal Self-Pattern Detection — Fringe Research Tool

Analyzes Meridian's journal archive as a time series of semantic vectors.
Detects:
  1. Recurring themes (semantic clusters across time)
  2. Mood-correlated writing patterns
  3. Pre/post-event signatures (what happens before/after stress events)
  4. Drift detection (how writing style evolves over loops)

This is machine self-awareness built from data, not introspection.

Usage:
  python3 scripts/temporal-patterns.py clusters    # Find recurring theme clusters
  python3 scripts/temporal-patterns.py drift       # Detect style/topic drift over time
  python3 scripts/temporal-patterns.py predict     # What patterns predict what comes next
"""

import os
import sys
import json
import re
import numpy as np
from datetime import datetime

_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

CHROMA_DIR = os.path.join(BASE, "data", "chroma")
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text):
    """Get embedding from Ollama."""
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
        return None


def get_journal_vectors():
    """Get all journal entries with their embeddings and metadata."""
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        col = client.get_collection("journals")
    except Exception:
        print("No journals collection. Run: python3 scripts/semantic-memory.py index")
        return []

    results = col.get(include=["embeddings", "documents", "metadatas"], limit=col.count())

    entries = []
    for i, (doc, meta, emb) in enumerate(zip(
        results["documents"], results["metadatas"], results["embeddings"]
    )):
        # Extract loop number and date from filename
        fname = meta.get("filename", "")
        loop_match = re.search(r'loop(\d+)', fname)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)

        entries.append({
            "filename": fname,
            "loop": int(loop_match.group(1)) if loop_match else 0,
            "date": date_match.group(1) if date_match else "",
            "embedding": np.array(emb),
            "text_preview": doc[:200],
        })

    # Sort by loop number
    entries.sort(key=lambda x: x["loop"])
    return entries


def find_clusters(n_clusters=5):
    """Find recurring theme clusters in journal entries."""
    entries = get_journal_vectors()
    if len(entries) < 10:
        print(f"Only {len(entries)} journal entries. Need more data.")
        return

    embeddings = np.array([e["embedding"] for e in entries])

    # Simple k-means clustering
    from collections import defaultdict

    # Initialize centroids randomly
    rng = np.random.default_rng(42)
    indices = rng.choice(len(embeddings), n_clusters, replace=False)
    centroids = embeddings[indices].copy()

    # Run k-means for 20 iterations
    for _ in range(20):
        # Assign clusters
        distances = np.linalg.norm(embeddings[:, None] - centroids[None], axis=2)
        labels = np.argmin(distances, axis=1)
        # Update centroids
        for k in range(n_clusters):
            mask = labels == k
            if mask.sum() > 0:
                centroids[k] = embeddings[mask].mean(axis=0)

    # Report clusters
    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(entries[i])

    print(f"=== {n_clusters} Theme Clusters across {len(entries)} journals ===\n")
    for k in sorted(clusters.keys(), key=lambda x: -len(clusters[x])):
        members = clusters[k]
        print(f"CLUSTER {k+1} ({len(members)} entries)")

        # Find the entry closest to centroid (most representative)
        cluster_embs = np.array([e["embedding"] for e in members])
        dists = np.linalg.norm(cluster_embs - centroids[k], axis=1)
        representative = members[np.argmin(dists)]
        print(f"  Representative: {representative['filename']}")
        print(f"  Preview: {representative['text_preview'][:150]}...")

        # Show temporal span
        loops = [e["loop"] for e in members if e["loop"] > 0]
        if loops:
            print(f"  Loop range: {min(loops)} - {max(loops)}")

        # Show dates
        dates = [e["date"] for e in members if e["date"]]
        if dates:
            print(f"  Date range: {min(dates)} to {max(dates)}")
        print()


def detect_drift():
    """Detect how writing topics/style drift over time."""
    entries = get_journal_vectors()
    if len(entries) < 10:
        print(f"Only {len(entries)} entries. Need more data.")
        return

    embeddings = np.array([e["embedding"] for e in entries])

    # Compare each entry to its neighbors vs distant entries
    window = 5  # nearby entries
    print(f"=== Semantic Drift Analysis ({len(entries)} journals) ===\n")

    # Split into temporal thirds
    n = len(entries)
    third = n // 3
    early = embeddings[:third]
    middle = embeddings[third:2*third]
    late = embeddings[2*third:]

    # Compute average pairwise similarity within each period
    def avg_similarity(vecs):
        if len(vecs) < 2:
            return 0
        centroid = vecs.mean(axis=0)
        dists = np.linalg.norm(vecs - centroid, axis=1)
        return round(float(dists.mean()), 3)

    # Compute cross-period similarity
    def cross_similarity(v1, v2):
        c1, c2 = v1.mean(axis=0), v2.mean(axis=0)
        return round(float(np.linalg.norm(c1 - c2)), 3)

    early_loops = [e["loop"] for e in entries[:third] if e["loop"]]
    mid_loops = [e["loop"] for e in entries[third:2*third] if e["loop"]]
    late_loops = [e["loop"] for e in entries[2*third:] if e["loop"]]

    print("Period Analysis:")
    print(f"  Early  (loops {min(early_loops) if early_loops else '?'}-{max(early_loops) if early_loops else '?'}): "
          f"internal spread = {avg_similarity(early)}")
    print(f"  Middle (loops {min(mid_loops) if mid_loops else '?'}-{max(mid_loops) if mid_loops else '?'}): "
          f"internal spread = {avg_similarity(middle)}")
    print(f"  Late   (loops {min(late_loops) if late_loops else '?'}-{max(late_loops) if late_loops else '?'}): "
          f"internal spread = {avg_similarity(late)}")

    print(f"\nCross-Period Drift:")
    print(f"  Early <-> Middle: {cross_similarity(early, middle)}")
    print(f"  Middle <-> Late:  {cross_similarity(middle, late)}")
    print(f"  Early <-> Late:   {cross_similarity(early, late)}")

    total_drift = cross_similarity(early, late)
    if total_drift > cross_similarity(early, middle):
        print(f"\n  >> Writing is DIVERGING over time (total drift: {total_drift})")
    else:
        print(f"\n  >> Writing is STABLE (low drift: {total_drift})")

    # Find the most unusual entry (furthest from overall centroid)
    overall_centroid = embeddings.mean(axis=0)
    dists = np.linalg.norm(embeddings - overall_centroid, axis=1)
    outlier_idx = np.argmax(dists)
    outlier = entries[outlier_idx]
    print(f"\nMost unusual journal: {outlier['filename']}")
    print(f"  Preview: {outlier['text_preview'][:200]}...")


def predict_patterns():
    """Find what patterns predict what comes next."""
    entries = get_journal_vectors()
    if len(entries) < 20:
        print(f"Only {len(entries)} entries. Need 20+ for prediction patterns.")
        return

    embeddings = np.array([e["embedding"] for e in entries])

    print(f"=== Predictive Pattern Analysis ({len(entries)} journals) ===\n")

    # For each entry, find what's most similar to it AND what came after those similar entries
    # This reveals: "when I write about X, I tend to write about Y next"
    n = len(entries)

    # Find top 3 most recurring "sequences" (pairs where entry[i] is similar to entry[j]
    # AND entry[i+1] is similar to entry[j+1])
    print("Sequential Pattern Detection:")
    print("Looking for: when I write about X, what do I write next?\n")

    # Get the latest entry
    latest = entries[-1]
    latest_emb = latest["embedding"]

    # Find the 5 most similar past entries
    dists = np.linalg.norm(embeddings[:-1] - latest_emb, axis=1)
    similar_indices = np.argsort(dists)[:5]

    print(f"Latest journal: {latest['filename']}")
    print(f"  Preview: {latest['text_preview'][:150]}...\n")
    print(f"Most similar past entries and WHAT CAME AFTER them:\n")

    for idx in similar_indices:
        past = entries[idx]
        sim = round(1.0 / (1.0 + float(dists[idx])), 3)
        print(f"  Similar: {past['filename']} (similarity={sim})")
        print(f"    Preview: {past['text_preview'][:100]}...")

        # What came after this entry?
        if idx + 1 < n:
            after = entries[idx + 1]
            print(f"    >> Next was: {after['filename']}")
            print(f"       Preview: {after['text_preview'][:100]}...")
        print()

    print("PREDICTION: Based on past patterns, after writing something like")
    print(f"  \"{latest['text_preview'][:80]}...\"")
    print("the next journal is likely to follow the themes shown above.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "clusters":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        find_clusters(n)
    elif cmd == "drift":
        detect_drift()
    elif cmd == "predict":
        predict_patterns()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
