#!/usr/bin/env python3
"""
Cinder Memory Recall — semantic search over conversation history and memories.
Standalone tool for RAG mode and archive queries.

Usage:
  python3 memory-recall.py "what did we discuss about music"
  python3 memory-recall.py --rebuild "search query"
  python3 memory-recall.py --context 5 "topic"
"""

import sys
import json
from pathlib import Path

# Import from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from cinder_memory import get_db, search, build_index, load_messages, tokenize


def recall_with_context(conn, query, context_turns=5):
    """Search and return full conversation context around matches."""
    results = search(conn, query, limit=5)
    output = []

    for r in results:
        if r["type"] == "conversation":
            messages = conn.execute(
                "SELECT role, content, created_at FROM conversations WHERE session_id = ? ORDER BY created_at",
                (r["session_id"],)
            ).fetchall()
            context = []
            for m in messages[-context_turns:]:
                context.append(f"[{m['role']}] {m['content']}")
            output.append({
                "type": "conversation",
                "session": r["session_id"],
                "score": r["score"],
                "context": "\n".join(context)
            })
        elif r["type"] == "memory":
            output.append({
                "type": "memory",
                "memory_type": r["memory_type"],
                "score": r["score"],
                "content": r["content"]
            })

    return output


def format_for_prompt(results):
    """Format recall results for injection into an LLM prompt."""
    if not results:
        return "[No relevant memories found.]"

    parts = ["[MEMORY RECALL]"]
    for r in results:
        if r["type"] == "conversation":
            parts.append(f"--- Past conversation (session {r['session']}, relevance {r['score']:.2f}) ---")
            parts.append(r["context"])
        elif r["type"] == "memory":
            parts.append(f"--- Stored {r['memory_type']} (relevance {r['score']:.2f}) ---")
            parts.append(r["content"])
    parts.append("[END MEMORY RECALL]")
    return "\n".join(parts)


def main():
    rebuild = False
    context_turns = 5
    query_parts = []

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--rebuild":
            rebuild = True
        elif sys.argv[i] == "--context" and i + 1 < len(sys.argv):
            context_turns = int(sys.argv[i + 1])
            i += 1
        elif sys.argv[i] == "--json":
            pass  # default is JSON-friendly
        else:
            query_parts.append(sys.argv[i])
        i += 1

    if not query_parts:
        print("Usage: memory-recall.py [--rebuild] [--context N] \"query\"")
        return

    query = " ".join(query_parts)
    conn = get_db()

    if rebuild:
        count = build_index(conn)
        print(f"Rebuilt index: {count} entries", file=sys.stderr)

    results = recall_with_context(conn, query, context_turns)

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        print(format_for_prompt(results))

    conn.close()


if __name__ == "__main__":
    main()
