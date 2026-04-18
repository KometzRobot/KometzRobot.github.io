#!/usr/bin/env python3
"""
Cinder Index Builder — builds TF-IDF search index from conversations,
memories, and identity/archive documents on the USB.

Usage:
  python3 build-index.py                    # Index conversations + memories
  python3 build-index.py --include-docs     # Also index identity/ and archive/ docs
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cinder_memory import get_db, build_index, save_memory, tokenize


def index_documents(conn, docs_dir, doc_type="fact"):
    """Index markdown/text documents from a directory as memories."""
    if not docs_dir.exists():
        return 0

    count = 0
    for f in docs_dir.rglob("*"):
        if f.suffix not in (".md", ".txt"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            if len(content.strip()) < 20:
                continue
            # Check if already indexed (by filename match in metadata)
            existing = conn.execute(
                "SELECT id FROM memories WHERE metadata LIKE ?",
                (f'%"source_file": "{f.name}"%',)
            ).fetchone()
            if existing:
                continue
            save_memory(
                conn, doc_type, content[:2000],
                metadata={"source_file": f.name, "full_path": str(f)}
            )
            count += 1
        except Exception as e:
            print(f"  Skip {f.name}: {e}", file=sys.stderr)

    return count


def main():
    include_docs = "--include-docs" in sys.argv
    conn = get_db()

    # Index identity docs
    app_dir = Path(__file__).resolve().parent.parent
    identity_dir = app_dir / "identity"
    archive_dir = app_dir / "archive"

    doc_count = 0
    if include_docs:
        if identity_dir.exists():
            c = index_documents(conn, identity_dir, "fact")
            print(f"Indexed {c} identity documents")
            doc_count += c
        if archive_dir.exists():
            c = index_documents(conn, archive_dir, "insight")
            print(f"Indexed {c} archive documents")
            doc_count += c

    # Build TF-IDF index
    term_count = build_index(conn)
    print(f"TF-IDF index built: {term_count} term-document pairs")
    if doc_count:
        print(f"New documents indexed: {doc_count}")

    conn.close()


if __name__ == "__main__":
    main()
