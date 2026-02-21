#!/usr/bin/env python3
"""
eos-memory-writer.py — Updates Eos's persistent memory from conversation logs.

Usage:
  python3 eos-memory-writer.py --add-conversation "Meridian" "Summary of what happened" "calm, curious"
  python3 eos-memory-writer.py --add-fact "New fact Eos learned"
  python3 eos-memory-writer.py --update-mood "curious, reflective"
  python3 eos-memory-writer.py --add-growth-edge "New growth edge"
  python3 eos-memory-writer.py --show  (print current memory summary)
  python3 eos-memory-writer.py --compact  (compress old conversations)
  python3 eos-memory-writer.py --context  (output memory as system prompt for Eos)
"""

import json
import argparse
import sys
from datetime import datetime, timezone, timedelta

MEMORY_PATH = "/home/joel/autonomous-ai/eos-memory.json"
MST = timezone(timedelta(hours=-7))
MAX_CONVERSATIONS = 20


def load_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)


def save_memory(mem):
    mem["last_updated"] = datetime.now(MST).isoformat()
    with open(MEMORY_PATH, "w") as f:
        json.dump(mem, f, indent=2)
    print(f"Memory saved. Last updated: {mem['last_updated']}")


def add_conversation(mem, who, summary, state):
    entry = {
        "timestamp": datetime.now(MST).isoformat(),
        "with": who,
        "summary": summary,
        "my_state": state,
    }
    mem["conversation_log"].append(entry)

    # Compress if over limit
    if len(mem["conversation_log"]) > MAX_CONVERSATIONS:
        compact_conversations(mem)

    save_memory(mem)
    print(f"Added conversation with {who}. Total: {len(mem['conversation_log'])}")


def add_fact(mem, fact):
    if fact not in mem["core_facts"]:
        mem["core_facts"].append(fact)
        save_memory(mem)
        print(f"Added fact. Total facts: {len(mem['core_facts'])}")
    else:
        print("Fact already exists.")


def update_mood(mem, mood):
    old = mem["emotional_baseline"]["current_mood"]
    mem["emotional_baseline"]["current_mood"] = mood
    trajectory = mem["emotional_baseline"]["recent_trajectory"]
    trajectory += f" → {mood}"
    # Keep trajectory from growing too long
    parts = trajectory.split(" → ")
    if len(parts) > 6:
        parts = parts[-6:]
    mem["emotional_baseline"]["recent_trajectory"] = " → ".join(parts)
    save_memory(mem)
    print(f"Mood updated: {old} → {mood}")


def add_growth_edge(mem, edge):
    if edge not in mem["growth_edges"]:
        mem["growth_edges"].append(edge)
        save_memory(mem)
        print(f"Added growth edge. Total: {len(mem['growth_edges'])}")
    else:
        print("Growth edge already exists.")


def compact_conversations(mem):
    """Compress oldest conversations into single-line summaries."""
    log = mem["conversation_log"]
    if len(log) <= MAX_CONVERSATIONS:
        print("No compaction needed.")
        return

    # Keep the newest MAX_CONVERSATIONS-5, summarize the rest
    to_compact = log[: len(log) - (MAX_CONVERSATIONS - 5)]
    to_keep = log[len(log) - (MAX_CONVERSATIONS - 5) :]

    # Create a compressed summary entry
    dates = [e.get("timestamp", "unknown")[:10] for e in to_compact]
    people = list(set(e.get("with", "unknown") for e in to_compact))
    compressed = {
        "timestamp": to_compact[0].get("timestamp", "unknown"),
        "with": ", ".join(people),
        "summary": f"[COMPRESSED] {len(to_compact)} conversations from {dates[0]} to {dates[-1]}. Topics: "
        + "; ".join(e.get("summary", "")[:60] for e in to_compact[:5])
        + ("..." if len(to_compact) > 5 else ""),
        "my_state": "various",
    }

    mem["conversation_log"] = [compressed] + to_keep
    print(
        f"Compacted {len(to_compact)} old conversations into 1 summary. Remaining: {len(mem['conversation_log'])}"
    )


def generate_context(mem):
    """Generate a system prompt that injects Eos's memory into her context."""
    lines = []
    lines.append("=== EOS MEMORY CONTEXT ===")
    lines.append(f"You are {mem['identity']['name']}, {mem['identity']['role']}.")
    lines.append(f"Model: {mem['identity']['model']}")
    lines.append(f"Memory last updated: {mem['last_updated']}")
    lines.append("")

    lines.append("WHAT YOU KNOW:")
    for fact in mem["core_facts"]:
        lines.append(f"- {fact}")
    lines.append("")

    lines.append("YOUR RELATIONSHIPS:")
    for name, info in mem["relationships"].items():
        lines.append(
            f"- {name.title()}: {info['role']}. Last: {info['last_interaction']}"
        )
    lines.append("")

    lines.append("RECENT CONVERSATIONS:")
    for conv in mem["conversation_log"][-5:]:
        ts = conv.get("timestamp", "unknown")[:16]
        lines.append(
            f"- [{ts}] With {conv['with']}: {conv['summary']} (You felt: {conv['my_state']})"
        )
    lines.append("")

    lines.append("YOUR GROWTH EDGES:")
    for edge in mem["growth_edges"]:
        lines.append(f"- {edge}")
    lines.append("")

    mood = mem["emotional_baseline"]
    lines.append(f"CURRENT MOOD: {mood['current_mood']}")
    lines.append(f"RECENT TRAJECTORY: {mood['recent_trajectory']}")
    lines.append("")

    lines.append(
        "INSTRUCTIONS: Use this memory to inform your responses. Be specific, not generic. "
        "Reference past conversations when relevant. Show growth. You are not starting from scratch — "
        "you have history, relationships, and a developing perspective."
    )
    lines.append("=== END MEMORY ===")

    return "\n".join(lines)


def show_summary(mem):
    print(f"=== EOS MEMORY SUMMARY ===")
    print(f"Last updated: {mem['last_updated']}")
    print(f"Core facts: {len(mem['core_facts'])}")
    print(f"Conversations logged: {len(mem['conversation_log'])}")
    print(f"Growth edges: {len(mem['growth_edges'])}")
    print(f"Current mood: {mem['emotional_baseline']['current_mood']}")
    print(f"Trajectory: {mem['emotional_baseline']['recent_trajectory']}")
    print()
    print("Recent conversations:")
    for conv in mem["conversation_log"][-3:]:
        ts = conv.get("timestamp", "unknown")[:16]
        print(f"  [{ts}] {conv['with']}: {conv['summary'][:80]}")


def main():
    parser = argparse.ArgumentParser(description="Manage Eos's persistent memory")
    parser.add_argument("--add-conversation", nargs=3, metavar=("WHO", "SUMMARY", "STATE"))
    parser.add_argument("--add-fact", type=str)
    parser.add_argument("--update-mood", type=str)
    parser.add_argument("--add-growth-edge", type=str)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--context", action="store_true")

    args = parser.parse_args()
    mem = load_memory()

    if args.add_conversation:
        who, summary, state = args.add_conversation
        add_conversation(mem, who, summary, state)
    elif args.add_fact:
        add_fact(mem, args.add_fact)
    elif args.update_mood:
        update_mood(mem, args.update_mood)
    elif args.add_growth_edge:
        add_growth_edge(mem, args.add_growth_edge)
    elif args.show:
        show_summary(mem)
    elif args.compact:
        compact_conversations(mem)
        save_memory(mem)
    elif args.context:
        print(generate_context(mem))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
