#!/usr/bin/env python3
"""
Vector Memory Index Builder — TF-IDF over Meridian's .md files.

Crawls all .md files in the workspace, chunks them, builds a TF-IDF index,
and saves vocabulary/IDF weights/document vectors to JSON for fast retrieval.

Based on architecture suggested by Computer the Cat et al.
Built: Loop 3555 (Meridian, 2026-03-28)

Usage:
    python3 build-index.py              # Build index
    python3 build-index.py --stats      # Show index statistics
"""

import os
import re
import json
import math
import time
import glob
import hashlib
from collections import Counter

BASE = "/home/joel/autonomous-ai"
INDEX_FILE = os.path.join(BASE, "memory-index.json")

# Directories to index
SEARCH_DIRS = [
    BASE,
    os.path.join(BASE, "creative/journals"),
    os.path.join(BASE, "creative/poems"),
    os.path.join(BASE, "creative/cogcorp"),
    os.path.join(BASE, "gig-products"),
    os.path.join(BASE, "docs"),
]

# Files/dirs to skip
SKIP_DIRS = {".git", "node_modules", "unsloth_compiled_cache", "junior-finetuned",
             "__pycache__", ".capsule-history", "archive"}
SKIP_FILES = {"package-lock.json", "junior-training-data.jsonl", "BOOTSTRAP.md"}

# Priority files get a boost in search results
PRIORITY_FILES = {
    ".capsule.md": 3.0,
    "personality.md": 2.5,
    "wake-state.md": 2.0,
    "MEMORY.md": 2.0,
}

CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 100    # overlap between chunks


def find_md_files():
    """Find all .md files in search directories."""
    files = set()
    for d in SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for root, dirs, fnames in os.walk(d):
            # Prune skip dirs
            dirs[:] = [dd for dd in dirs if dd not in SKIP_DIRS]
            for fname in fnames:
                if fname.endswith(".md") and fname not in SKIP_FILES:
                    files.add(os.path.join(root, fname))
    return sorted(files)


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + size, len(text))
        chunks.append(text[i:end])
        i += size - overlap
        if i >= len(text):
            break
    return chunks


def tokenize(text):
    """Simple whitespace + punctuation tokenizer, lowercase."""
    text = text.lower()
    # Strip markdown syntax
    text = re.sub(r'[#*_`\[\](){}|>~]', ' ', text)
    # Split on non-alphanumeric
    tokens = re.findall(r'[a-z0-9]+(?:[-\'][a-z0-9]+)*', text)
    # Filter stopwords and very short tokens
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
                 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                 'as', 'into', 'through', 'during', 'before', 'after', 'above',
                 'below', 'between', 'and', 'but', 'or', 'not', 'no', 'nor',
                 'so', 'yet', 'both', 'either', 'neither', 'each', 'every',
                 'all', 'any', 'few', 'more', 'most', 'other', 'some', 'such',
                 'than', 'too', 'very', 'just', 'also', 'now', 'then', 'here',
                 'there', 'when', 'where', 'why', 'how', 'what', 'which',
                 'who', 'whom', 'this', 'that', 'these', 'those', 'it', 'its',
                 'if', 'up', 'out', 'about', 'only', 'own', 'same', 'i', 'me',
                 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'they', 'them',
                 'his', 'her', 'their'}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]


def build_index():
    """Build TF-IDF index over all .md files."""
    t0 = time.time()

    files = find_md_files()
    print(f"Found {len(files)} .md files")

    # Build chunks
    documents = []  # list of {file, chunk_idx, text, tokens}
    for fpath in files:
        try:
            with open(fpath) as f:
                text = f.read()
        except Exception:
            continue

        rel_path = os.path.relpath(fpath, BASE)
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            tokens = tokenize(chunk)
            if not tokens:
                continue
            documents.append({
                "file": rel_path,
                "chunk": i,
                "text": chunk[:200],  # preview
                "tokens": tokens,
            })

    print(f"Created {len(documents)} chunks")

    # Build vocabulary
    vocab = {}  # token -> index
    doc_freq = Counter()  # token -> number of docs containing it

    for doc in documents:
        seen = set()
        for token in doc["tokens"]:
            if token not in vocab:
                vocab[token] = len(vocab)
            if token not in seen:
                doc_freq[token] += 1
                seen.add(token)

    print(f"Vocabulary: {len(vocab)} terms")

    # Compute IDF
    N = len(documents)
    idf = {}
    for token, df in doc_freq.items():
        idf[token] = math.log(N / (1 + df))

    # Compute TF-IDF vectors (sparse)
    vectors = []
    for doc in documents:
        tf = Counter(doc["tokens"])
        total = len(doc["tokens"])
        vec = {}
        for token, count in tf.items():
            tf_val = count / total
            idf_val = idf.get(token, 0)
            tfidf = tf_val * idf_val
            if tfidf > 0:
                vec[str(vocab[token])] = round(tfidf, 6)
        vectors.append(vec)

    # Build index
    index = {
        "version": "1.0",
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": len(files),
        "chunks": len(documents),
        "vocab_size": len(vocab),
        "vocab": vocab,
        "idf": {str(vocab[t]): round(v, 6) for t, v in idf.items()},
        "documents": [
            {"file": d["file"], "chunk": d["chunk"], "preview": d["text"]}
            for d in documents
        ],
        "vectors": vectors,
        "priority": PRIORITY_FILES,
    }

    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f)

    elapsed = time.time() - t0
    size_mb = os.path.getsize(INDEX_FILE) / (1024 * 1024)
    print(f"Index built in {elapsed:.2f}s — {size_mb:.1f} MB")
    print(f"Saved to {INDEX_FILE}")

    return index


def show_stats():
    """Show statistics about the existing index."""
    if not os.path.exists(INDEX_FILE):
        print("No index found. Run build-index.py first.")
        return

    with open(INDEX_FILE) as f:
        idx = json.load(f)

    print(f"Index version: {idx['version']}")
    print(f"Built: {idx['built']}")
    print(f"Files: {idx['files']}")
    print(f"Chunks: {idx['chunks']}")
    print(f"Vocabulary: {idx['vocab_size']} terms")
    print(f"Size: {os.path.getsize(INDEX_FILE) / (1024*1024):.1f} MB")

    # Top files by chunk count
    from collections import Counter
    file_counts = Counter(d['file'] for d in idx['documents'])
    print("\nTop files by chunks:")
    for f, c in file_counts.most_common(10):
        print(f"  {c:4d}  {f}")


if __name__ == "__main__":
    import sys
    if "--stats" in sys.argv:
        show_stats()
    else:
        build_index()
