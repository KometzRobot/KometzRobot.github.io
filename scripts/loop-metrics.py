#!/usr/bin/env python3
"""
loop-metrics.py — Comprehensive loop health metrics for The Signal dashboard.

Generates structured metrics data covering all aspects of loop health.
Intended for API consumption or standalone reporting.

Usage: python3 loop-metrics.py [--json]
"""
import os, json, time, sqlite3, subprocess, socket
from datetime import datetime, timezone

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

def file_age(p):
    try: return int(time.time() - os.path.getmtime(os.path.join(BASE, p)))
    except: return -1

def read_json(p, default=None):
    try:
        with open(os.path.join(BASE, p)) as f: return json.load(f)
    except: return default or {}

def port_check(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1); s.connect(("127.0.0.1", port)); s.close()
        return True
    except: return False

def main():
    as_json = "--json" in sys.argv if 'sys' in dir() else "--json" in __import__('sys').argv

    # Core loop
    loop = "?"
    try:
        with open(os.path.join(BASE, ".loop-count")) as f: loop = f.read().strip()
    except: pass

    hb_age = file_age(".heartbeat")
    handoff_age = file_age(".loop-handoff.md")
    capsule_age = file_age(".capsule.md")

    # Soma
    soma = read_json(".soma-psyche.json")
    inner = read_json(".soma-inner-monologue.json")
    goals = read_json(".soma-goals.json")

    # System
    try:
        with open("/proc/loadavg") as f: load = f.read().split()[:3]
    except: load = ["?","?","?"]

    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1]) / 1048576
        avail = int(lines[2].split()[1]) / 1048576
        ram_pct = round((total - avail) / total * 100, 1)
    except: ram_pct = 0

    # Ports
    ports = {8090: "The Signal", 8091: "Chorus", 1144: "IMAP", 1026: "SMTP", 11434: "Ollama"}
    port_status = {name: port_check(port) for port, name in ports.items()}

    # Relay freshness
    relay_fresh = {}
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        for agent in ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes", "Sentinel"]:
            row = db.execute("SELECT timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1", (agent,)).fetchone()
            if row:
                ts = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                relay_fresh[agent] = int((datetime.now(timezone.utc) - ts).total_seconds())
            else:
                relay_fresh[agent] = -1
        db.close()
    except: pass

    metrics = {
        "loop": loop,
        "heartbeat_age": hb_age,
        "handoff_age": handoff_age,
        "capsule_age": capsule_age,
        "soma_mood": soma.get("mood", "?"),
        "soma_score": soma.get("mood_score", 0),
        "soma_dreams": soma.get("dreams", []),
        "inner_monologue": inner.get("current", {}).get("text", ""),
        "goals": [g["id"] for g in goals.get("goals", [])],
        "load": load,
        "ram_pct": ram_pct,
        "ports": port_status,
        "relay_freshness": relay_fresh,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if as_json:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Loop Metrics — {metrics['timestamp'][:19]}")
        print(f"  Loop: {loop} | HB: {hb_age}s | Capsule: {capsule_age}s | Handoff: {handoff_age}s")
        print(f"  Mood: {metrics['soma_mood']} ({metrics['soma_score']}) | Load: {' '.join(load)} | RAM: {ram_pct}%")
        print(f"  Ports: {sum(1 for v in port_status.values() if v)}/{len(port_status)} up")
        print(f"  Agents: {sum(1 for v in relay_fresh.values() if 0 < v < 900)}/{len(relay_fresh)} active")

if __name__ == "__main__":
    main()
