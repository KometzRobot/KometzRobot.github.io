#!/bin/bash
# start-claude.sh — launched by watchdog on startup or restart
# Reads wakeup-prompt.md and starts Claude with it
# SAFETY: Refuses to start if another Claude instance already exists
# AUTO-RESTART: When Claude exits (context exhaustion, error, etc.),
#   waits briefly then restarts. This eliminates the 10-min watchdog gap.

WORKING_DIR="$HOME/autonomous-ai"
CLAUDE_BIN="$HOME/.local/bin/claude"
WAKEUP_PROMPT="$WORKING_DIR/wakeup-prompt.md"
LOG="$WORKING_DIR/startup.log"
RESTART_DELAY=15  # seconds between restarts
MAX_RAPID_RESTARTS=5  # safety: max restarts within RAPID_WINDOW
RAPID_WINDOW=300  # 5 minutes

cd "$WORKING_DIR"

# Safety check: prevent duplicate instances
EXISTING=$(pgrep -f "claude --dangerously-skip-permissions" | wc -l)
if [ "$EXISTING" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BLOCKED: start-claude.sh refused — $EXISTING instance(s) already running" >> "$LOG"
    echo "Claude is already running ($EXISTING instance). Not starting another."
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] start-claude.sh invoked with restart loop (no existing instances)" >> "$LOG"

# Track rapid restarts to prevent infinite crash loops
RESTART_TIMES=()

while true; do
    NOW=$(date +%s)

    # Clean old timestamps outside the rapid window
    NEW_TIMES=()
    for t in "${RESTART_TIMES[@]}"; do
        if (( NOW - t < RAPID_WINDOW )); then
            NEW_TIMES+=("$t")
        fi
    done
    RESTART_TIMES=("${NEW_TIMES[@]}")

    # Safety: too many rapid restarts = something is fundamentally broken
    if (( ${#RESTART_TIMES[@]} >= MAX_RAPID_RESTARTS )); then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] SAFETY: $MAX_RAPID_RESTARTS restarts in ${RAPID_WINDOW}s — backing off 5 min" >> "$LOG"
        sleep 300
        RESTART_TIMES=()
        continue
    fi

    RESTART_TIMES+=("$NOW")

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Claude (restart #${#RESTART_TIMES[@]} in window)" >> "$LOG"

    # Write handoff before starting (capture previous session state if possible)
    python3 "$WORKING_DIR/loop-handoff.py" write 2>/dev/null

    # Run Claude (NOT exec — we need the loop to continue after it exits)
    "$CLAUDE_BIN" --dangerously-skip-permissions -p "$(cat "$WAKEUP_PROMPT")"
    EXIT_CODE=$?

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Claude exited with code $EXIT_CODE — restarting in ${RESTART_DELAY}s" >> "$LOG"

    # Touch heartbeat to prevent watchdog from also trying to restart
    touch "$WORKING_DIR/.heartbeat"

    sleep "$RESTART_DELAY"

    # Re-check that no other instance started (watchdog might have beaten us)
    EXISTING=$(pgrep -f "claude --dangerously-skip-permissions" | wc -l)
    if [ "$EXISTING" -gt 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Another Claude instance appeared during restart delay. Exiting loop." >> "$LOG"
        exit 0
    fi
done
