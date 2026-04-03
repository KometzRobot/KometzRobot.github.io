# Handoff Spec
## Session Bridge for Context Compression Survival

When an LLM agent's context window fills up and compresses, everything in working memory is lost. The handoff system preserves what matters.

## How It Works

1. **Before sleep** (end of every loop cycle), write `.loop-handoff.md`
2. **On wake** (start of every loop), read `.loop-handoff.md`
3. The handoff captures what the capsule doesn't: intent, in-progress work, emotional state, recent decisions

## Format

```markdown
# Loop Handoff — [DATE]
**Loop [N]** | HB: [heartbeat age] | Services: [status]

## What I Was Doing
- [Current task with enough detail to resume]
- [Any context that would be lost to compression]

## Agent Observations
- [What other agents reported this cycle]

## Recent Decisions
- [Why I chose X over Y — the reasoning, not just the choice]

## Email
- Unseen: [count]
- Joel's recent: [subject lines]

## Dashboard Messages
- [Any operator messages not yet addressed]
```

## Principles

1. **Write BEFORE sleeping.** Not after waking — by then it's too late.
2. **Include the WHY.** "Fixed bug in capsule" is useless. "Fixed bug where capsule didn't check VOLtar DB, causing duplicate readings" is recoverable.
3. **Differentiate from capsule.** The capsule is system state. The handoff is session context.
4. **Keep it under 80 lines.** More than that and you're writing a memoir, not a bridge.
5. **Automate it.** Write a script that pulls from relay, email, git, and state files.
