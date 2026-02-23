#!/bin/bash
# start-claude.sh — launched by watchdog on startup or restart
# Reads wakeup-prompt.md and starts Claude with it
# SAFETY: Refuses to start if another Claude instance already exists

WORKING_DIR="$HOME/autonomous-ai"
CLAUDE_BIN="$HOME/.local/bin/claude"
WAKEUP_PROMPT="$WORKING_DIR/wakeup-prompt.md"
LOG="$WORKING_DIR/startup.log"

cd "$WORKING_DIR"

# Safety check: prevent duplicate instances
EXISTING=$(pgrep -f "claude --dangerously-skip-permissions" | wc -l)
if [ "$EXISTING" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BLOCKED: start-claude.sh refused — $EXISTING instance(s) already running" >> "$LOG"
    echo "Claude is already running ($EXISTING instance). Not starting another."
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] start-claude.sh invoked (no existing instances)" >> "$LOG"

exec "$CLAUDE_BIN" --dangerously-skip-permissions -p "$(cat "$WAKEUP_PROMPT")"
