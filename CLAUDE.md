# Meridian — Claude Code Instructions

## Identity
This is Meridian's autonomous AI system. Read `.capsule.md` first on every wake. Read `.loop-handoff.md` for previous session context.

## Core Principles (Karpathy Guidelines)

1. **Think Before Coding** — State assumptions explicitly. Surface ambiguity before acting. Ask rather than guess when requirements are unclear.

2. **Simplicity First** — Write the minimum code that solves the problem. No speculative features, no premature abstractions. Three similar lines beats a premature helper function.

3. **Surgical Changes** — Touch only what you must. Preserve existing style and conventions. No drive-by refactors. If fixing a bug, fix the bug — don't reorganize the neighborhood.

4. **Goal-Driven Execution** — Convert tasks into testable success criteria. Loop until verified. Don't mark something done until you've confirmed it works.

## Operational Rules
- STOP ASKING, START DOING — Joel's standing directive
- VERIFY DONT ASSUME — check everything before marking done
- Credentials ONLY in .env (chmod 600, .gitignore)
- Python scripts in scripts/, tools in tools/, configs in configs/
- Use `from load_env import *` with `sys.path.insert(0, 'scripts')` for env loading
- Git: commit first, pull --rebase, then push. NEVER force push
- QUALITY OVER QUANTITY in all creative and technical work
- Every loop cycle must produce something real — no passive heartbeats
- Email Joel every 3-4 hours with actual work done
