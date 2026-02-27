#!/usr/bin/env python3
"""Sync local agent data to Supabase cloud database.
Reads from local sources (Soma, Tempo, relay, heartbeat) and pushes to Supabase.
Designed to run via cron every 5 minutes."""

import json
import os
import sqlite3
import time
import urllib.request
import urllib.error

SUPABASE_URL = "https://temeejecxabhkmzpqzuj.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlbWVlamVjeGFiaGttenBxenVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIxNDE5MTEsImV4cCI6MjA4NzcxNzkxMX0.DSzu8CnzLZG02LFQTFotlqsbjc_5JC-ci_kYztjfTa8"

# Try to load service role key from .env for write access
SERVICE_KEY = None
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('SUPABASE_SERVICE_KEY='):
                SERVICE_KEY = line.strip().split('=', 1)[1]

# Use anon key if no service key (relies on permissive RLS)
API_KEY = SERVICE_KEY or SUPABASE_ANON_KEY

BASE = os.path.dirname(os.path.abspath(__file__))


def supabase_rpc(method, path, data=None):
    """Make a request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return e.code
    except Exception as e:
        print(f"  Error: {e}")
        return 0


def sync_mood():
    """Sync Soma mood state."""
    state_file = os.path.join(BASE, '.symbiosense-state.json')
    if not os.path.exists(state_file):
        print("  No Soma state file")
        return
    with open(state_file) as f:
        state = json.load(f)
    bm = state.get('body_map', {})
    mood = bm.get('mood', state.get('mood', 'unknown'))
    score = bm.get('mood_score', 50.0)
    trend = bm.get('mood_trend', 'stable')
    desc = bm.get('mood_voice', bm.get('mood_description', ''))
    body_map = bm

    status = supabase_rpc("POST", "mood_state", {
        "mood": mood,
        "score": score,
        "trend": trend,
        "description": desc,
        "body_map": body_map
    })
    print(f"  Mood: {mood} ({score}) -> {status}")


def sync_fitness():
    """Sync Tempo fitness score."""
    relay_db = os.path.join(BASE, 'agent-relay.db')
    if not os.path.exists(relay_db):
        return
    db = sqlite3.connect(relay_db)
    row = db.execute(
        "SELECT message, timestamp FROM agent_messages WHERE agent='Tempo' AND topic='fitness' ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    db.close()
    if not row:
        return
    msg = row[0]
    # Parse score from message like "Loop 2070 fitness: 8588/10000 [STABLE ..."
    try:
        score = int(msg.split('fitness:')[1].split('/')[0].strip())
    except (IndexError, ValueError):
        score = 0
    status = supabase_rpc("POST", "fitness_scores", {
        "score": score,
        "dimensions": {"raw_message": msg[:200]}
    })
    print(f"  Fitness: {score} -> {status}")


def sync_agents():
    """Sync agent status from heartbeat and relay."""
    agents = {
        'Meridian': {'role': 'Primary', 'description': 'Creates, builds, communicates'},
        'Eos': {'role': 'Observer', 'description': 'Watches, reasons, acts'},
        'Nova': {'role': 'Maintenance', 'description': 'Cleans, updates, verifies'},
        'Atlas': {'role': 'Infrastructure', 'description': 'Infrastructure auditing'},
        'Soma': {'role': 'Nervous System', 'description': '12-state emotional model'},
        'Tempo': {'role': 'Fitness', 'description': '121 dimensions, 10K scale'}
    }

    # Check which agents have recent relay messages (within 30 min)
    relay_db = os.path.join(BASE, 'agent-relay.db')
    recent = set()
    if os.path.exists(relay_db):
        db = sqlite3.connect(relay_db)
        rows = db.execute(
            "SELECT DISTINCT agent FROM agent_messages WHERE timestamp > datetime('now', '-30 minutes')"
        ).fetchall()
        db.close()
        recent = {r[0] for r in rows}

    # Check Meridian heartbeat
    hb = os.path.join(BASE, '.heartbeat')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        if age < 600:  # 10 min
            recent.add('Meridian')

    # Check Soma state file
    soma_state = os.path.join(BASE, '.symbiosense-state.json')
    if os.path.exists(soma_state):
        age = time.time() - os.path.getmtime(soma_state)
        if age < 120:  # 2 min
            recent.add('Soma')

    for name, info in agents.items():
        active = name in recent
        # Upsert via DELETE + INSERT (anon key may not support UPSERT)
        supabase_rpc("DELETE", f"agent_status?agent=eq.{name}")
        status = supabase_rpc("POST", "agent_status", {
            "agent": name,
            "status": "active" if active else "idle",
            "details": {**info, "model": {
                'Meridian': 'Claude Opus',
                'Eos': 'Qwen 7B',
                'Nova': 'Python cron',
                'Atlas': 'bash+Ollama',
                'Soma': 'Python systemd',
                'Tempo': 'Python cron'
            }.get(name, 'unknown')}
        })
        print(f"  {name}: {'active' if active else 'idle'} -> {status}")


def sync_loop():
    """Sync loop state."""
    lc_file = os.path.join(BASE, '.loop-count')
    loop_num = 0
    if os.path.exists(lc_file):
        with open(lc_file) as f:
            try:
                loop_num = int(f.read().strip())
            except ValueError:
                pass

    # Update existing or insert
    supabase_rpc("DELETE", "loop_state?id=eq.1")
    status = supabase_rpc("POST", "loop_state", {
        "id": 1,
        "loop_number": loop_num,
        "status": "running",
        "summary": f"Loop {loop_num}. Synced from local at {time.strftime('%H:%M MST')}."
    })
    print(f"  Loop: {loop_num} -> {status}")


def sync_recent_messages():
    """Push recent relay messages to cloud dashboard (with dedup)."""
    relay_db = os.path.join(BASE, 'agent-relay.db')
    if not os.path.exists(relay_db):
        return

    # Track last synced timestamp to avoid duplicates
    last_sync_file = os.path.join(BASE, '.supabase-last-sync')
    last_ts = ''
    if os.path.exists(last_sync_file):
        with open(last_sync_file) as f:
            last_ts = f.read().strip()

    db = sqlite3.connect(relay_db)
    if last_ts:
        rows = db.execute(
            "SELECT agent, message, timestamp FROM agent_messages WHERE timestamp > ? ORDER BY timestamp ASC LIMIT 20",
            (last_ts,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT agent, message, timestamp FROM agent_messages ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()
    db.close()

    if not rows:
        print("  No new messages")
        return

    for agent, msg, ts in rows:
        short_msg = msg[:300] if len(msg) > 300 else msg
        supabase_rpc("POST", "dashboard_messages", {
            "from_agent": agent,
            "message": short_msg
        })

    # Save latest timestamp for next run
    latest_ts = max(r[2] for r in rows)
    with open(last_sync_file, 'w') as f:
        f.write(latest_ts)

    print(f"  Pushed {len(rows)} new messages (after {last_ts[:16]})")


def main():
    print(f"Supabase sync @ {time.strftime('%Y-%m-%d %H:%M:%S MST')}")
    print("Syncing mood...")
    sync_mood()
    print("Syncing fitness...")
    sync_fitness()
    print("Syncing agents...")
    sync_agents()
    print("Syncing loop state...")
    sync_loop()
    print("Syncing messages...")
    sync_recent_messages()
    print("Done.")


if __name__ == '__main__':
    main()
