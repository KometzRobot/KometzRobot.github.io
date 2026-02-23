#!/usr/bin/env python3
"""
Eos Memory v2 — Using mem0 with Ollama for intelligent memory management.

mem0 provides:
- Automatic memory extraction from conversations
- Semantic search across memories
- Memory deduplication and consolidation
- Multi-level memory (user, agent, session)

All running locally via Ollama — zero API tokens.

Run with: /home/joel/miniconda3/bin/python3 eos-memory-v2.py
"""

import json
import os
import sys
from datetime import datetime
from mem0 import Memory

BASE_DIR = "/home/joel/autonomous-ai"

# Configure mem0 to use Ollama
config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://localhost:11434",
            "temperature": 0.7,
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://localhost:11434",
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "eos_memories",
            "path": os.path.join(BASE_DIR, "eos-mem0-db"),
        }
    },
}


def init_memory():
    """Initialize mem0 with Ollama backend."""
    return Memory.from_config(config)


def add_memory(m, text, user_id="eos", metadata=None):
    """Add a memory."""
    result = m.add(text, user_id=user_id, metadata=metadata or {})
    return result


def search_memory(m, query, user_id="eos", limit=5):
    """Search memories semantically."""
    results = m.search(query, user_id=user_id, limit=limit)
    return results


def get_all_memories(m, user_id="eos"):
    """Get all memories for a user."""
    return m.get_all(user_id=user_id)


def migrate_existing_memory():
    """Migrate facts from eos-memory.json into mem0."""
    old_file = os.path.join(BASE_DIR, "eos-memory.json")
    if not os.path.exists(old_file):
        print("No existing memory to migrate.")
        return

    with open(old_file) as f:
        old = json.load(f)

    m = init_memory()

    # Migrate core facts
    for fact in old.get("core_facts", []):
        print(f"  Migrating fact: {fact[:60]}...")
        add_memory(m, fact, user_id="eos", metadata={"source": "core_facts"})

    # Migrate relationship knowledge
    for name, info in old.get("relationships", {}).items():
        text = f"{name}: {info.get('role', '')}. {', '.join(info.get('important_notes', []))}"
        print(f"  Migrating relationship: {name}")
        add_memory(m, text, user_id="eos", metadata={"source": "relationships", "person": name})

    # Migrate conversation summaries
    for conv in old.get("conversation_log", []):
        text = f"Conversation with {conv.get('with', '?')} ({conv.get('timestamp', '?')}): {conv.get('summary', '')}"
        print(f"  Migrating conversation: {conv.get('with', '?')}")
        add_memory(m, text, user_id="eos", metadata={"source": "conversation_log"})

    # Migrate learnings
    for learning in old.get("learnings", []):
        text = learning.get("content", "") if isinstance(learning, dict) else str(learning)
        if text:
            print(f"  Migrating learning: {text[:60]}...")
            add_memory(m, text, user_id="eos", metadata={"source": "learnings"})

    print(f"\nMigration complete. Total memories: {len(get_all_memories(m))}")


def interactive():
    """Interactive memory test."""
    m = init_memory()
    print("Eos Memory v2 (mem0 + Ollama)")
    print("Commands: add <text>, search <query>, list, migrate, quit")

    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd.startswith("add "):
            result = add_memory(m, cmd[4:])
            print(f"Added: {result}")
        elif cmd.startswith("search "):
            results = search_memory(m, cmd[7:])
            for r in results:
                print(f"  [{r.get('score', '?'):.2f}] {r.get('memory', r)}")
        elif cmd == "list":
            memories = get_all_memories(m)
            for mem in memories:
                print(f"  - {mem.get('memory', mem)}")
            print(f"Total: {len(memories)}")
        elif cmd == "migrate":
            migrate_existing_memory()
        elif cmd in ("quit", "exit"):
            break
        else:
            print("Unknown command. Try: add, search, list, migrate, quit")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        migrate_existing_memory()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        m = init_memory()
        add_memory(m, "Eos is a local AI running on Joel's machine in Calgary.")
        print("Test memory added.")
        results = search_memory(m, "Where does Eos run?")
        print(f"Search results: {results}")
    else:
        interactive()
