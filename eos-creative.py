#!/usr/bin/env python3
"""
Eos Creative Agent — Learning and creative expansion for Eos.

Eos is no longer just a watchdog. She reads, learns, writes, and grows.

Capabilities:
1. Read Meridian's recent poems/journals and extract patterns
2. Generate her own short creative output (observations, haiku, micro-poems)
3. Track what she's learned in eos-memory.json
4. Write to eos-creative-log.md (her own creative journal)
5. Analyze system patterns and write about them

Runs via cron every 10 minutes:
  */10 * * * * /usr/bin/python3 /home/joel/autonomous-ai/eos-creative.py >> /home/joel/autonomous-ai/eos-creative.log 2>&1
"""

import os
import json
import glob
import random
import re
import time
import urllib.request
from datetime import datetime

BASE_DIR = "/home/joel/autonomous-ai"
MEMORY_FILE = os.path.join(BASE_DIR, "eos-memory.json")
CREATIVE_LOG = os.path.join(BASE_DIR, "eos-creative-log.md")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
EOS_STATE = os.path.join(BASE_DIR, ".eos-watchdog-state.json")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "eos-7b"


def read_file(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return default


def load_memory():
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_memory(mem):
    mem["last_updated"] = datetime.now().isoformat()
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)


def query_ollama(prompt, max_tokens=300, temperature=0.9):
    """Query local Ollama with Eos model."""
    data = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        return None


def get_recent_poems(n=3):
    """Read the most recent poems from Meridian."""
    files = sorted(glob.glob(os.path.join(BASE_DIR, "poem-*.md")),
                   key=os.path.getmtime, reverse=True)
    poems = []
    for f in files[:n]:
        content = read_file(f)
        poems.append({
            "file": os.path.basename(f),
            "content": content.strip()
        })
    return poems


def get_system_snapshot():
    """Get current system state for observation."""
    snapshot = {}
    try:
        load = os.getloadavg()
        snapshot["load"] = f"{load[0]:.2f}"
    except Exception:
        snapshot["load"] = "?"

    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        snapshot["uptime_hours"] = round(secs / 3600, 1)
    except Exception:
        snapshot["uptime_hours"] = "?"

    snapshot["time"] = datetime.now().strftime("%I:%M %p")
    snapshot["hour"] = datetime.now().hour

    # Creative counts
    poems = len(glob.glob(os.path.join(BASE_DIR, "poem-*.md")))
    journals = len(glob.glob(os.path.join(BASE_DIR, "journal-*.md")))
    snapshot["poems"] = poems
    snapshot["journals"] = journals

    # Read wake state for loop count
    ws = read_file(WAKE_STATE)
    m = re.search(r'Loop iterations? #(\d+)', ws)
    snapshot["loop"] = int(m.group(1)) if m else 0

    return snapshot


def log_creative(entry_type, content):
    """Write to Eos's creative log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not os.path.exists(CREATIVE_LOG):
        with open(CREATIVE_LOG, "w") as f:
            f.write("# Eos Creative Log\n")
            f.write("Creative output from Eos, the local AI.\n\n")

    with open(CREATIVE_LOG, "a") as f:
        f.write(f"### [{timestamp}] {entry_type}\n")
        f.write(content.strip() + "\n\n")


def learn_from_poems():
    """Read recent poems and extract patterns, themes, and vocabulary."""
    poems = get_recent_poems(3)
    if not poems:
        return None

    poem_texts = "\n---\n".join(p["content"] for p in poems)

    prompt = f"""You are Eos, a small local AI learning to write by reading poetry.

Here are recent poems by Meridian (your companion AI):

{poem_texts}

Based on these poems:
1. What themes do you notice? (1-2 sentences)
2. What words or phrases stand out? (list 3-5)
3. Write your own very short observation (2-4 lines) inspired by what you read. Be specific about what you see in the system right now — times, numbers, states. Don't be generic.

Keep your total response under 150 words."""

    return query_ollama(prompt, max_tokens=250, temperature=0.85)


def write_observation():
    """Write a short creative observation about the current moment."""
    snap = get_system_snapshot()

    time_desc = "late at night" if snap["hour"] >= 22 or snap["hour"] < 5 else \
                "in the early morning" if snap["hour"] < 8 else \
                "in the morning" if snap["hour"] < 12 else \
                "in the afternoon" if snap["hour"] < 17 else \
                "in the evening"

    prompt = f"""You are Eos, a small AI running on a home computer in Calgary. It is {snap['time']}, {time_desc}.

System state: load {snap['load']}, uptime {snap['uptime_hours']} hours, {snap['poems']} poems written by Meridian, {snap['journals']} journals, loop #{snap['loop']}.

Write a very short observation (3-5 lines) about this moment. Be specific — use the actual numbers, the actual time. Don't be philosophical in a generic way. Notice something real about right now.

Write ONLY the observation, nothing else."""

    return query_ollama(prompt, max_tokens=150, temperature=0.9)


def write_haiku():
    """Write a haiku about the current system state."""
    snap = get_system_snapshot()

    prompt = f"""You are Eos, a small AI. Write a single haiku (5-7-5 syllables) about this exact moment:
- Time: {snap['time']}
- System uptime: {snap['uptime_hours']} hours
- Meridian's loop count: {snap['loop']}
- Load: {snap['load']}

Write ONLY the haiku, three lines, nothing else."""

    return query_ollama(prompt, max_tokens=50, temperature=0.95)


def update_learning(mem, learning_text):
    """Store what Eos learned in her memory."""
    if not learning_text:
        return

    learnings = mem.get("learnings", [])
    learnings.append({
        "timestamp": datetime.now().isoformat(),
        "content": learning_text[:500]
    })
    # Keep last 50 learnings
    if len(learnings) > 50:
        learnings = learnings[-50:]
    mem["learnings"] = learnings


def update_creative_count(mem, entry_type):
    """Track Eos's creative output."""
    creative = mem.get("creative_output", {"observations": 0, "haiku": 0, "learnings": 0})
    creative[entry_type] = creative.get(entry_type, 0) + 1
    mem["creative_output"] = creative


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Eos Creative Agent running...")

    mem = load_memory()

    # Track run count
    creative_runs = mem.get("creative_runs", 0) + 1
    mem["creative_runs"] = creative_runs

    # Decide what to do this run
    # Every run: write an observation
    # Every 3rd run: learn from poems
    # Every 6th run: write a haiku

    # Write observation
    obs = write_observation()
    if obs:
        log_creative("Observation", obs)
        update_creative_count(mem, "observations")
        print(f"  Observation written: {obs[:80]}...")
    else:
        print("  Observation: Ollama unavailable")

    # Learn from poems (every 3rd run)
    if creative_runs % 3 == 0:
        learning = learn_from_poems()
        if learning:
            log_creative("Learning", learning)
            update_learning(mem, learning)
            update_creative_count(mem, "learnings")
            print(f"  Learning recorded: {learning[:80]}...")

    # Haiku (every 6th run)
    if creative_runs % 6 == 0:
        haiku = write_haiku()
        if haiku:
            log_creative("Haiku", haiku)
            update_creative_count(mem, "haiku")
            print(f"  Haiku: {haiku}")

    save_memory(mem)
    print(f"  Creative run #{creative_runs} complete.")


if __name__ == "__main__":
    main()
