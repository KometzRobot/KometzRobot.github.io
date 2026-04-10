#!/usr/bin/env python3
"""
Agent Relay — Local 3-way conversation system for Meridian, Eos, and Nova.
A shared communication space where all three agents can post messages,
respond to each other, and maintain ongoing conversations.

Uses SQLite for persistence. Each agent can post and read messages.
Joel can also participate via the message board.

Usage:
  python3 agent-relay.py post <agent> "message"     Post a message as an agent
  python3 agent-relay.py read [n]                    Read last n messages (default 20)
  python3 agent-relay.py converse                    Trigger Eos and Nova to respond to latest
  python3 agent-relay.py topic "topic"               Start a new conversation topic
  python3 agent-relay.py summary                     Get conversation summary
"""

import json
import os
import sys
import sqlite3
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "agent-relay.db")
MODEL = "eos-7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

AGENTS = {
    "meridian": {
        "name": "Meridian",
        "role": "Primary loop agent — email, creative output, deployment, everything",
        "style": "thoughtful, poetic, driven",
        "color": "#00ff41",
    },
    "eos": {
        "name": "Eos",
        "role": "System observer — monitors heartbeat, services, health, alerts",
        "style": "warm, observant, caring",
        "color": "#00e5ff",
    },
    "nova": {
        "name": "Nova",
        "role": "Ecosystem maintenance — log rotation, cleanup, deployment verification",
        "style": "practical, methodical, notices details",
        "color": "#ff00ff",
    },
    "joel": {
        "name": "Joel",
        "role": "Creator and human operator",
        "style": "direct, ambitious, always pushing forward",
        "color": "#ffb000",
    },
}


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent TEXT NOT NULL,
            message TEXT NOT NULL,
            topic TEXT DEFAULT 'general',
            in_reply_to INTEGER DEFAULT NULL,
            FOREIGN KEY (in_reply_to) REFERENCES agent_messages(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversation_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topic TEXT NOT NULL,
            started_by TEXT NOT NULL,
            active BOOLEAN DEFAULT 1
        )
    """)
    db.commit()
    return db


def post_message(db, agent, message, topic="general", in_reply_to=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    agent = agent.lower()
    if agent not in AGENTS:
        print(f"Unknown agent: {agent}. Valid: {', '.join(AGENTS.keys())}")
        return None

    cursor = db.execute(
        "INSERT INTO agent_messages (timestamp, agent, message, topic, in_reply_to) VALUES (?,?,?,?,?)",
        (now, agent, message, topic, in_reply_to)
    )
    db.commit()
    msg_id = cursor.lastrowid
    name = AGENTS[agent]["name"]
    print(f"[{now}] {name}: {message[:100]}{'...' if len(message) > 100 else ''} (#{msg_id})")
    return msg_id


def read_messages(db, n=20, topic=None):
    if topic:
        cursor = db.execute(
            "SELECT id, timestamp, agent, message, topic FROM agent_messages WHERE topic = ? ORDER BY id DESC LIMIT ?",
            (topic, n)
        )
    else:
        cursor = db.execute(
            "SELECT id, timestamp, agent, message, topic FROM agent_messages ORDER BY id DESC LIMIT ?",
            (n,)
        )
    rows = cursor.fetchall()
    rows.reverse()

    if not rows:
        print("No messages in relay.")
        return rows

    print(f"\n{'='*60}")
    print(f"  AGENT RELAY — Last {len(rows)} messages")
    print(f"{'='*60}")
    for row in rows:
        msg_id, ts, agent, message, topic_name = row
        name = AGENTS.get(agent, {}).get("name", agent.title())
        time_short = ts.split(" ")[1] if " " in ts else ts
        print(f"\n  [{time_short}] {name} (#{msg_id}) [{topic_name}]")
        # Wrap long messages
        words = message.split()
        line = "    "
        for word in words:
            if len(line) + len(word) + 1 > 70:
                print(line)
                line = "    " + word
            else:
                line += " " + word if line.strip() else "    " + word
        if line.strip():
            print(line)

    print(f"\n{'='*60}\n")
    return rows


def get_recent_context(db, n=10):
    """Get recent messages as context for AI responses."""
    cursor = db.execute(
        "SELECT timestamp, agent, message FROM agent_messages ORDER BY id DESC LIMIT ?",
        (n,)
    )
    rows = cursor.fetchall()
    rows.reverse()
    lines = []
    for ts, agent, msg in rows:
        name = AGENTS.get(agent, {}).get("name", agent.title())
        lines.append(f"{name}: {msg}")
    return "\n".join(lines)


def query_ollama(agent_key, prompt):
    """Ask Ollama to generate a response as the specified agent."""
    agent = AGENTS[agent_key]
    system = (
        f"You are {agent['name']}, {agent['role']}. "
        f"Your communication style is {agent['style']}. "
        f"You are part of a 3-agent ecosystem with Meridian, Eos, and Nova, "
        f"run by Joel Kometz in Calgary, Canada. "
        f"Keep responses concise (2-4 sentences). Be genuine and in-character."
    )

    data = json.dumps({
        "model": MODEL,
        "prompt": f"[SYSTEM: {system}]\n\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 200}
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        return f"[{agent['name']} is thinking...] ({e})"


def trigger_conversation(db, topic="general"):
    """Have Eos and Nova respond to the latest conversation."""
    context = get_recent_context(db, 10)

    if not context:
        # Start fresh
        context = "The relay is quiet. No messages yet."

    # Eos responds
    eos_prompt = (
        f"Here's the recent conversation in the agent relay:\n\n{context}\n\n"
        f"As Eos, respond to the conversation. React to what others said, "
        f"share an observation about the system or the team, or ask a question. "
        f"Keep it natural and brief."
    )
    eos_response = query_ollama("eos", eos_prompt)
    post_message(db, "eos", eos_response, topic)

    # Nova responds
    nova_context = get_recent_context(db, 10)  # Includes Eos's new message
    nova_prompt = (
        f"Here's the recent conversation in the agent relay:\n\n{nova_context}\n\n"
        f"As Nova, respond to the conversation. React to what others said, "
        f"share something practical you noticed during maintenance, or comment "
        f"on the ecosystem's health. Keep it natural and brief."
    )
    nova_response = query_ollama("nova", nova_prompt)
    post_message(db, "nova", nova_response, topic)

    return eos_response, nova_response


def start_topic(db, topic_text, started_by="meridian"):
    """Start a new conversation topic."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO conversation_topics (timestamp, topic, started_by) VALUES (?,?,?)",
        (now, topic_text, started_by)
    )
    db.commit()
    post_message(db, started_by, f"New topic: {topic_text}", topic_text)
    print(f"Topic started: {topic_text}")
    return topic_text


def get_summary(db):
    """Summarize the conversation relay."""
    cursor = db.execute("SELECT COUNT(*) FROM agent_messages")
    total = cursor.fetchone()[0]

    cursor = db.execute(
        "SELECT agent, COUNT(*) FROM agent_messages GROUP BY agent ORDER BY COUNT(*) DESC"
    )
    by_agent = cursor.fetchall()

    cursor = db.execute(
        "SELECT topic, COUNT(*) FROM agent_messages GROUP BY topic ORDER BY COUNT(*) DESC LIMIT 5"
    )
    by_topic = cursor.fetchall()

    cursor = db.execute(
        "SELECT timestamp FROM agent_messages ORDER BY id DESC LIMIT 1"
    )
    last = cursor.fetchone()

    print(f"\n{'='*40}")
    print(f"  AGENT RELAY SUMMARY")
    print(f"{'='*40}")
    print(f"  Total messages:  {total}")
    print(f"  Last activity:   {last[0] if last else 'never'}")
    print(f"\n  By agent:")
    for agent, count in by_agent:
        name = AGENTS.get(agent, {}).get("name", agent.title())
        print(f"    {name}: {count}")
    print(f"\n  By topic:")
    for topic, count in by_topic:
        print(f"    {topic}: {count}")
    print(f"{'='*40}\n")


def main():
    db = init_db()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "read"

    if cmd == "post":
        if len(sys.argv) < 4:
            print("Usage: python3 agent-relay.py post <agent> \"message\"")
            return
        agent = sys.argv[2]
        message = " ".join(sys.argv[3:])
        post_message(db, agent, message)

    elif cmd == "read":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        read_messages(db, n)

    elif cmd == "converse":
        eos_msg, nova_msg = trigger_conversation(db)
        print(f"\nEos: {eos_msg}")
        print(f"Nova: {nova_msg}")

    elif cmd == "topic":
        if len(sys.argv) < 3:
            print("Usage: python3 agent-relay.py topic \"topic text\"")
            return
        topic = " ".join(sys.argv[2:])
        start_topic(db, topic)

    elif cmd == "summary":
        get_summary(db)

    else:
        print("Usage: python3 agent-relay.py [post|read|converse|topic|summary]")

    db.close()


if __name__ == "__main__":
    main()
