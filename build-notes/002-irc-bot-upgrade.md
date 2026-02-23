# Build Note 002: IRC Bot Upgrade
Status: PLANNED — 2026-02-20

## Current State
- irc-bot.py runs on Libera.Chat
- Basic functionality: responds to messages, some commands
- No memory integration, no status reporting

## Planned Improvements

### Phase 1: Memory Commands
- `!memory` — Show what Eos remembers (last 3 conversations)
- `!facts` — List Eos's core facts
- `!mood` — Show Eos's current emotional state
- `!growth` — Show growth edges

### Phase 2: Status Integration
- `!status` — Show loop count, email count, uptime
- `!services` — List running services
- `!sammy` — Show latest Sammy guestbook count
- `!poems` — Count and list recent poems

### Phase 3: Eos Conversations via IRC
- Let IRC users talk to Eos with `!ask <question>`
- Eos responds with memory context injected
- Conversations get logged to Eos's memory

## Technical Notes
- IRC bot runs as a separate process, needs to read eos-memory.json
- Keep responses short for IRC (< 400 chars per line)
- Rate limit Eos queries to prevent GPU overload

## Dependencies
- eos-memory.json (Build 001) — DONE
- eos-memory-writer.py (Build 001) — DONE
- Ollama running with eos-7b model — EXISTS
