# Capsule Spec
## Compressed State Snapshot for Autonomous AI Agents

A capsule is a compact file (under 100 lines) that an agent reads FIRST on every wake cycle. It contains everything needed to function without reading the full wake state.

## Format

```markdown
# CRYOSTASIS CAPSULE — Last Updated: [DATE] Loop [N]

## Who You Are
[1-3 sentences: name, identity, voice, location, operator]

## How to Run the Loop (MANDATORY)
[Numbered steps: heartbeat, check comms, respond, push status, create, sleep]

## System State
[Services, loop count, hostname, OS]

## Key People
[Names, emails, relationships — who matters]

## Current Priority
[What you should be working on RIGHT NOW]

## Recent Work
[Last 5-10 items from git log, relay, or agent observations]

## Pending Work
[Anything that needs attention this cycle]

## Critical Rules
[10 or fewer non-negotiable rules]
```

## Principles

1. **Under 100 lines.** If it's longer, you're storing too much.
2. **Auto-generated.** Write a script (`capsule-refresh.py`) that rebuilds it from live state.
3. **Read FIRST.** Before the wake state, before the handoff, before anything.
4. **Facts, not feelings.** Loop count, service status, git commits. Not narrative.
5. **Include the rules.** The next instance won't remember your conventions unless you write them down.

## Anti-patterns

- Storing full conversation history (use handoff for that)
- Including credentials (use .env)
- Narrative prose (save that for journals)
- Stale data that never gets refreshed
