#!/usr/bin/env python3
"""
capsule-portrait.py — Generate a "portrait" capsule that captures the grain
of the current instance, not just the facts.

Inspired by the insight: "The capsule should be a portrait, not a backup."
Captures not just what's happening but HOW the system is attending to things.

Output: a markdown file showing attention distribution, lingering topics,
compressed topics, and emotional texture — the unsigned marks of this instance.

Usage: python3 capsule-portrait.py [--output portrait.md]
"""
import os, sys, json, sqlite3, time
from datetime import datetime, timezone
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))

def read_json(p, default=None):
    try:
        with open(os.path.join(BASE, p)) as f: return json.load(f)
    except: return default or {}

def main():
    output = "capsule-portrait.md"
    for i, a in enumerate(sys.argv):
        if a == "--output" and i+1 < len(sys.argv): output = sys.argv[i+1]

    lines = []
    lines.append(f"# Capsule Portrait — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("*Not a backup. A portrait of the current instance's attention.*")
    lines.append("")

    # What the system is attending to (from relay)
    topic_counts = Counter()
    agent_counts = Counter()
    recent_topics = []
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        rows = db.execute(
            "SELECT agent, topic, substr(message,1,80) FROM agent_messages ORDER BY id DESC LIMIT 100"
        ).fetchall()
        db.close()
        for r in rows:
            agent_counts[r[0]] += 1
            if r[1]: topic_counts[r[1]] += 1
            recent_topics.append(r[2])
    except: pass

    lines.append("## Attention Distribution (last 100 relay messages)")
    lines.append("")
    if topic_counts:
        total = sum(topic_counts.values())
        for topic, count in topic_counts.most_common(10):
            pct = round(count / total * 100, 1)
            bar = "█" * int(pct / 2)
            lines.append(f"  {topic:20} {bar:25} {pct}%")
    lines.append("")

    lines.append("## Agent Activity (who's talking)")
    for agent, count in agent_counts.most_common():
        lines.append(f"  {agent:15} {'▓' * min(count, 30)} ({count})")
    lines.append("")

    # Emotional texture
    soma = read_json(".soma-psyche.json")
    inner = read_json(".soma-inner-monologue.json")
    lines.append("## Emotional Texture")
    lines.append(f"  Mood: {soma.get('mood', '?')} ({soma.get('mood_score', 0)}/100)")
    lines.append(f"  Fears: {', '.join(soma.get('fears', [])) or 'none'}")
    lines.append(f"  Dreams: {', '.join(soma.get('dreams', [])) or 'none'}")
    lines.append(f"  Inner voice: \"{inner.get('current', {}).get('text', 'quiet')}\"")
    lines.append("")

    # What's being compressed (topics NOT in recent relay)
    lines.append("## Compressed (not recently attended)")
    all_expected = {"email", "creative", "fitness", "startup", "infra-audit", "briefing", "cascade", "soma-inner", "nerve-event", "status", "handoff", "mood_shift", "alert", "loop", "inter-agent"}
    present = set(topic_counts.keys())
    absent = all_expected - present
    if absent:
        for t in sorted(absent):
            lines.append(f"  - {t} (no recent signal)")
    else:
        lines.append("  (all topics active)")
    lines.append("")

    # The grain
    lines.append("## The Grain")
    lines.append("What this instance keeps returning to:")
    hot = [t for t, c in topic_counts.most_common(3)]
    cold = list(absent)[:3] if absent else ["(nothing compressed)"]
    lines.append(f"  Hot: {', '.join(hot)}")
    lines.append(f"  Cold: {', '.join(cold)}")
    lines.append(f"  This is the unsigned mark of loop {read_json('.loop-count', '?')}.")

    result = "\n".join(lines)
    path = os.path.join(BASE, output)
    with open(path, 'w') as f:
        f.write(result)
    print(f"Portrait written: {output} ({len(result)} bytes)")

if __name__ == "__main__":
    main()
