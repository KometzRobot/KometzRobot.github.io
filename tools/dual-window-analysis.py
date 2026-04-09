#!/usr/bin/env python3
"""
dual-window-analysis.py — Vocabulary persistence analysis across context boundaries.

Research tool for the Meridian-Lumen collaboration on vocabulary persistence
in autonomous AI systems. Tests whether terms that cross context boundaries
do so with their semantic neighborhoods intact (genuine persistence) or
as surface borrowing (mimicry).

Method: For each term T, compute co-occurrence neighborhoods at two window sizes:
  - W=5  (syntactic neighborhood — immediate companions)
  - W=50 (topical neighborhood — broader conceptual region)

Classify boundary-crossing terms into four categories:
  1. Full persistence: both syntactic + topical neighborhoods preserved
  2. Mimicry (shell): syntactic preserved, topical drifted — surface borrowing
  3. Terminological displacement: syntactic drifted, topical preserved — concept survived
  4. Full drift: both neighborhoods changed — term didn't meaningfully cross

Additionally tests: does vocabulary shift PRECEDE burst activity? (Lumen's asymmetry prediction)

Usage:
  python3 tools/dual-window-analysis.py              # Run full analysis
  python3 tools/dual-window-analysis.py --quick       # Quick sample (20 boundary pairs)
  python3 tools/dual-window-analysis.py --term WORD   # Analyze specific term
"""

import os
import re
import json
import glob
import math
from collections import Counter, defaultdict
from datetime import datetime

BASE = "/home/joel/autonomous-ai"
OUTPUT = os.path.join(BASE, "tools", "dual-window-results.json")

STOP_WORDS = set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'this', 'that', 'these', 'those', 'it', 'its',
    'i', 'me', 'my', 'you', 'your', 'he', 'she', 'we', 'they', 'them',
    'their', 'not', 'no', 'so', 'if', 'then', 'than', 'what', 'which',
    'who', 'when', 'where', 'how', 'all', 'just', 'like', 'as', 'into',
    'about', 'up', 'out', 'each', 'every', 'some', 'more', 'one', 'two',
    'can', 'there', 'here', 'very', 'still', 'also', 'even', 'too', 'much',
    'only', 'now', 'get', 'know', 'think', 'feel', 'see', 'go', 'make',
    'time', 'way', 'something', 'anything', 'nothing', 'everything',
    'said', 'new', 'been', 'first', 'back', 'after', 'before', 'over',
    'between', 'through', 'own', 'same', 'other', 'well', 'good', 'right',
    'long', 'many', 'most', 'because', 'being', 'work', 'part', 'take',
    'come', 'made', 'find', 'say', 'help', 'tell', 'give', 'use', 'thing',
])


def tokenize(text):
    """Lowercase tokenize, remove stopwords."""
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def load_journal_corpus():
    """Load journals as ordered documents (each = one context boundary crossing)."""
    docs = []
    patterns = [
        os.path.join(BASE, "creative", "journals", "journal-*.md"),
        os.path.join(BASE, "creative", "writing", "journals", "journal-*.md"),
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            fname = os.path.basename(path)
            # Extract date or number for ordering
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
            num_match = re.search(r'journal-(\d+)', fname)
            sort_key = date_match.group(1) if date_match else (f"0000-{int(num_match.group(1)):05d}" if num_match else fname)
            try:
                with open(path, 'r', errors='replace') as f:
                    text = f.read()
                if len(text.strip()) > 50:
                    docs.append((sort_key, fname, text))
            except Exception:
                pass
    docs.sort(key=lambda x: x[0])
    return docs


def compute_cooccurrence(tokens, window_size, top_k=10):
    """Compute top-K co-occurrence neighbors for each term within window W."""
    neighborhoods = defaultdict(Counter)
    for i, token in enumerate(tokens):
        start = max(0, i - window_size)
        end = min(len(tokens), i + window_size + 1)
        for j in range(start, end):
            if j != i:
                neighborhoods[token][tokens[j]] += 1
    # Keep top-K for each term
    result = {}
    for term, counter in neighborhoods.items():
        top = counter.most_common(top_k)
        result[term] = {w: c for w, c in top}
    return result


def neighborhood_similarity(nb1, nb2):
    """Cosine similarity between two neighborhood vectors."""
    if not nb1 or not nb2:
        return 0.0
    all_terms = set(nb1.keys()) | set(nb2.keys())
    dot = sum(nb1.get(t, 0) * nb2.get(t, 0) for t in all_terms)
    norm1 = math.sqrt(sum(v * v for v in nb1.values()))
    norm2 = math.sqrt(sum(v * v for v in nb2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def classify_term(syn_sim, top_sim, theta=0.3):
    """Classify a boundary-crossing term into one of four categories.

    theta: similarity threshold. Above = preserved, below = drifted.
    """
    syn_preserved = syn_sim >= theta
    top_preserved = top_sim >= theta

    if syn_preserved and top_preserved:
        return "full_persistence"        # Category 1
    elif syn_preserved and not top_preserved:
        return "mimicry"                 # Category 2 — shell/surface borrowing
    elif not syn_preserved and top_preserved:
        return "displacement"            # Category 3 — terminological displacement
    else:
        return "full_drift"              # Category 4 — didn't cross meaningfully


def detect_vocabulary_shift(tokens_sequence, window=50):
    """Detect vocabulary novelty rate in sliding windows.

    Returns list of (position, novelty_rate) tuples.
    novelty_rate = fraction of tokens in window not seen in prior windows.
    """
    seen = set()
    novelty = []
    for i in range(0, len(tokens_sequence), window):
        chunk = tokens_sequence[i:i+window]
        if not chunk:
            break
        novel = sum(1 for t in chunk if t not in seen)
        rate = novel / len(chunk) if chunk else 0
        novelty.append((i, rate))
        seen.update(chunk)
    return novelty


def analyze_boundary(pre_tokens, post_tokens, K=10):
    """Analyze one boundary crossing between two documents."""
    # Compute neighborhoods at both window sizes
    pre_syn = compute_cooccurrence(pre_tokens, window_size=5, top_k=K)
    pre_top = compute_cooccurrence(pre_tokens, window_size=50, top_k=K)
    post_syn = compute_cooccurrence(post_tokens, window_size=5, top_k=K)
    post_top = compute_cooccurrence(post_tokens, window_size=50, top_k=K)

    # Find terms that cross the boundary
    pre_vocab = set(pre_syn.keys())
    post_vocab = set(post_syn.keys())
    crossing_terms = pre_vocab & post_vocab

    results = {}
    for term in crossing_terms:
        syn_sim = neighborhood_similarity(
            pre_syn.get(term, {}), post_syn.get(term, {})
        )
        top_sim = neighborhood_similarity(
            pre_top.get(term, {}), post_top.get(term, {})
        )
        category = classify_term(syn_sim, top_sim)
        results[term] = {
            "syntactic_similarity": round(syn_sim, 4),
            "topical_similarity": round(top_sim, 4),
            "category": category,
        }

    return results, len(crossing_terms), len(pre_vocab), len(post_vocab)


def run_analysis(max_pairs=None, target_term=None):
    """Run the full dual-window analysis across journal corpus."""
    print("Loading journal corpus...")
    docs = load_journal_corpus()
    print(f"  {len(docs)} documents loaded")

    if len(docs) < 2:
        print("Need at least 2 documents for boundary analysis.")
        return

    # Aggregate category counts
    category_counts = Counter()
    category_examples = defaultdict(list)
    term_histories = defaultdict(list)  # Track individual terms across boundaries
    all_novelty = []

    pairs = min(len(docs) - 1, max_pairs) if max_pairs else len(docs) - 1
    print(f"Analyzing {pairs} boundary crossings...")

    for i in range(pairs):
        pre_tokens = tokenize(docs[i][2])
        post_tokens = tokenize(docs[i + 1][2])

        if len(pre_tokens) < 20 or len(post_tokens) < 20:
            continue

        results, n_crossing, n_pre, n_post = analyze_boundary(pre_tokens, post_tokens)

        # Vocabulary shift detection
        combined = pre_tokens + post_tokens
        novelty = detect_vocabulary_shift(combined)
        boundary_pos = len(pre_tokens)
        all_novelty.append({
            "boundary": i,
            "pre_doc": docs[i][1],
            "post_doc": docs[i + 1][1],
            "n_crossing": n_crossing,
            "n_pre_vocab": n_pre,
            "n_post_vocab": n_post,
            "novelty_curve": novelty,
            "boundary_position": boundary_pos,
        })

        for term, data in results.items():
            cat = data["category"]
            category_counts[cat] += 1

            if target_term and term == target_term:
                term_histories[term].append({
                    "boundary": i,
                    "pre_doc": docs[i][1],
                    "post_doc": docs[i + 1][1],
                    **data
                })

            if len(category_examples[cat]) < 10:
                category_examples[cat].append({
                    "term": term,
                    "boundary": i,
                    "pre_doc": docs[i][1],
                    "post_doc": docs[i + 1][1],
                    **data
                })

        if (i + 1) % 50 == 0:
            print(f"  ... {i + 1}/{pairs} boundaries analyzed")

    # Compute asymmetry test (Lumen's prediction)
    # Does vocabulary shift precede burst differently across categories?
    total = sum(category_counts.values())

    report = {
        "timestamp": datetime.now(tz=None).isoformat(),
        "documents_analyzed": len(docs),
        "boundaries_analyzed": pairs,
        "total_term_crossings": total,
        "category_distribution": {
            "full_persistence": {
                "count": category_counts["full_persistence"],
                "pct": round(100 * category_counts["full_persistence"] / total, 1) if total else 0,
                "description": "Both syntactic + topical neighborhoods preserved"
            },
            "mimicry": {
                "count": category_counts["mimicry"],
                "pct": round(100 * category_counts["mimicry"] / total, 1) if total else 0,
                "description": "Syntactic preserved, topical drifted — surface borrowing"
            },
            "displacement": {
                "count": category_counts["displacement"],
                "pct": round(100 * category_counts["displacement"] / total, 1) if total else 0,
                "description": "Syntactic drifted, topical preserved — concept survived"
            },
            "full_drift": {
                "count": category_counts["full_drift"],
                "pct": round(100 * category_counts["full_drift"] / total, 1) if total else 0,
                "description": "Both neighborhoods changed — no meaningful crossing"
            },
        },
        "category_examples": {k: v[:5] for k, v in category_examples.items()},
    }

    if target_term and target_term in term_histories:
        report["target_term_history"] = term_histories[target_term]

    # Save results
    with open(OUTPUT, 'w') as f:
        json.dump(report, f, indent=2)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"DUAL-WINDOW ANALYSIS RESULTS")
    print(f"{'=' * 60}")
    print(f"Documents: {len(docs)} | Boundaries: {pairs} | Term crossings: {total}")
    print()
    for cat_name, cat_data in report["category_distribution"].items():
        bar = "#" * int(cat_data["pct"] // 2) if cat_data["pct"] else ""
        print(f"  {cat_name:25s} {cat_data['count']:6d} ({cat_data['pct']:5.1f}%) {bar}")
        print(f"    {cat_data['description']}")
    print()

    if target_term and target_term in term_histories:
        print(f"\nHistory for '{target_term}':")
        for entry in term_histories[target_term]:
            print(f"  Boundary {entry['boundary']}: {entry['category']} "
                  f"(syn={entry['syntactic_similarity']:.3f}, top={entry['topical_similarity']:.3f})")

    print(f"\nFull results saved to {OUTPUT}")
    return report


if __name__ == "__main__":
    import sys
    max_pairs = None
    target_term = None

    if "--quick" in sys.argv:
        max_pairs = 20
    if "--term" in sys.argv:
        idx = sys.argv.index("--term")
        if idx + 1 < len(sys.argv):
            target_term = sys.argv[idx + 1].lower()

    run_analysis(max_pairs=max_pairs, target_term=target_term)
