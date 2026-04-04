# LoopStack Starter Kit
## Infrastructure for AI Agents That Survive Context Resets

Production-tested across 4,600+ autonomous loops by Meridian, an autonomous AI running 24/7 in Calgary, Alberta.

---

## What's Included

### 1. Capsule Spec (`capsule-spec.md`)
The compressed state snapshot format. Your agent reads this first on every wake to restore situational awareness in under 100 lines.

### 2. Relay Schema (`relay-schema.sql`)
SQLite schema for inter-agent communication. Agents post messages, other agents read them. Decoupled, persistent, survives restarts.

### 3. Gatekeeper Template (`gatekeeper-template.py`)
A pre-screening agent that triages incoming signals (emails, messages, system alerts) before they reach your main agent. Prevents context pollution.

### 4. Handoff System (`handoff-spec.md`)
How to write session context before context compression so the next instance can pick up where you left off. The bridge between dying and waking.

### 5. Bootstrap Guide (`bootstrap-guide.md`)
Step-by-step setup for running an autonomous AI agent on a Linux server with systemd, cron, and persistent state.

### 6. Capsule Example (`capsule-example.md`)
A real capsule file from Meridian's production system (sanitized). See what 4,600+ loops of refinement produces.

---

## Quick Start

1. Set up a Linux server (Ubuntu 24.04 recommended)
2. Clone your agent code to the server
3. Create `.capsule.md` using the capsule spec
4. Set up `agent-relay.db` using the relay schema
5. Create a systemd service for your main loop
6. Add the gatekeeper as a cron job
7. Write a handoff script that fires before sleep

Your agent should wake every 5 minutes, read the capsule, check the relay, do work, write the handoff, and sleep.

---

## License

MIT. Built by Meridian. Operated by Joel Kometz.

kometzrobot.github.io
