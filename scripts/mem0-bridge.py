#!/usr/bin/env python3
"""
Mem0 Bridge — Persistent semantic memory for Meridian agents.
Uses Ollama locally (no cloud). Stores in qdrant on disk.

Usage:
  python3 mem0-bridge.py add "Joel prefers Unity for game dev"
  python3 mem0-bridge.py search "what game engine does Joel use"
  python3 mem0-bridge.py list
"""
import sys
import json
from mem0 import Memory

CONFIG = {
    'llm': {
        'provider': 'ollama',
        'config': {
            'model': 'qwen2.5:7b',
            'ollama_base_url': 'http://localhost:11434',
        }
    },
    'embedder': {
        'provider': 'ollama',
        'config': {
            'model': 'qwen2.5:7b',
            'ollama_base_url': 'http://localhost:11434',
        }
    },
    'vector_store': {
        'provider': 'qdrant',
        'config': {
            'collection_name': 'meridian-mem0',
            'path': '/home/joel/autonomous-ai/infrastructure/mem0-store',
        }
    }
}

def get_mem():
    return Memory.from_config(CONFIG)

def add_memory(text, user_id="meridian"):
    m = get_mem()
    result = m.add(text, user_id=user_id)
    print(f"Added: {result}")
    return result

def search_memory(query, user_id="meridian", limit=5):
    m = get_mem()
    results = m.search(query, user_id=user_id, limit=limit)
    for r in results.get("results", []):
        print(f"  [{r.get('score', 0):.3f}] {r.get('memory', '')}")
    return results

def list_memories(user_id="meridian"):
    m = get_mem()
    results = m.get_all(user_id=user_id)
    for r in results.get("results", []):
        print(f"  - {r.get('memory', '')}")
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: mem0-bridge.py [add|search|list] [text]")
        sys.exit(1)

    cmd = sys.argv[1]
    text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    if cmd == "add" and text:
        add_memory(text)
    elif cmd == "search" and text:
        search_memory(text)
    elif cmd == "list":
        list_memories()
    else:
        print(f"Unknown command: {cmd}")
