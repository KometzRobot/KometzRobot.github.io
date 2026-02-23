#!/bin/bash
# Watchdog - checks if Claude is alive and responsive
# Run via cron every 10 minutes
# If Claude is frozen (heartbeat stale >10 min) or dead, restart it
# SAFETY: Prevents duplicate instances using lock file + process counting

# === CONFIGURE THESE ===
WORKING_DIR="$HOME/autonomous-ai"
CLAUDE_BIN="$HOME/.local/bin/claude"
# === END CONFIG ===

HEARTBEAT="$WORKING_DIR/.heartbeat"
LOGFILE="$WORKING_DIR/watchdog.log"
WAKEUP_PROMPT="$WORKING_DIR/wakeup-prompt.md"
LOCKFILE="/tmp/claude-instance.lock"
MAX_INSTANCES=1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOGFILE"
}

# ── SAFETY: Count running Claude instances ────────────────────────────────
CLAUDE_PIDS=$(pgrep -f "claude --dangerously-skip-permissions" 2>/dev/null)
CLAUDE_COUNT=$(echo "$CLAUDE_PIDS" | grep -c '[0-9]')

if [ "$CLAUDE_COUNT" -gt "$MAX_INSTANCES" ]; then
    log "SAFETY ALERT: $CLAUDE_COUNT Claude instances running (max $MAX_INSTANCES). Killing extras."
    # Keep the oldest one (lowest PID), kill the rest
    OLDEST_PID=$(echo "$CLAUDE_PIDS" | head -1)
    for pid in $CLAUDE_PIDS; do
        if [ "$pid" != "$OLDEST_PID" ]; then
            log "  Killing extra instance PID $pid"
            kill "$pid" 2>/dev/null
        fi
    done
    log "  Kept PID $OLDEST_PID as the single instance."
    exit 0
fi

# ── Normal watchdog logic ─────────────────────────────────────────────────
if [ -z "$CLAUDE_PIDS" ] || [ "$CLAUDE_COUNT" -eq 0 ]; then
    # Check lock file — prevent rapid respawning
    if [ -f "$LOCKFILE" ]; then
        LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE") ))
        if [ "$LOCK_AGE" -lt 120 ]; then
            log "Lock file exists (${LOCK_AGE}s old). Claude may be starting. Waiting."
            exit 0
        fi
        log "Lock file stale (${LOCK_AGE}s). Removing and starting fresh."
        rm -f "$LOCKFILE"
    fi

    log "ALERT: No Claude process found. Starting fresh instance."
    touch "$LOCKFILE"

    export DISPLAY=:0
    cd "$WORKING_DIR"
    gnome-terminal --title="KometzRobot — Meridian Loop" --geometry=220x50 -- \
        bash -c "$WORKING_DIR/start-claude.sh; echo 'Claude exited. Press Enter.'; read" &

    log "Started new Claude instance via start-claude.sh in gnome-terminal (PID: $!)"
    exit 0
fi

# Claude is running - check if heartbeat is fresh
if [ ! -f "$HEARTBEAT" ]; then
    log "WARNING: No heartbeat file found. Creating one. Will check again next run."
    touch "$HEARTBEAT"
    exit 0
fi

# Check heartbeat age (in seconds)
HEARTBEAT_AGE=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ))
MAX_AGE=600  # 10 minutes

if [ "$HEARTBEAT_AGE" -gt "$MAX_AGE" ]; then
    log "WARNING: Heartbeat is ${HEARTBEAT_AGE}s old (max ${MAX_AGE}s). Checking .claude logs..."

    # Secondary check: are .claude log files still being written to?
    CLAUDE_LOG_DIR="$HOME/.claude"
    NEWEST_CLAUDE_LOG=$(find "$CLAUDE_LOG_DIR" -name "*.jsonl" -o -name "*.log" 2>/dev/null | head -20 | xargs ls -t 2>/dev/null | head -1)

    if [ -n "$NEWEST_CLAUDE_LOG" ]; then
        CLAUDE_LOG_AGE=$(( $(date +%s) - $(stat -c %Y "$NEWEST_CLAUDE_LOG") ))
        log "  Newest .claude log: $NEWEST_CLAUDE_LOG (${CLAUDE_LOG_AGE}s old)"

        if [ "$CLAUDE_LOG_AGE" -lt "$MAX_AGE" ]; then
            log "  Claude is BUSY but alive (.claude logs still active). NOT killing."
            exit 0
        fi
        log "  .claude logs ALSO stale (${CLAUDE_LOG_AGE}s). Claude is truly frozen."
    else
        log "  No .claude logs found. Proceeding with kill."
    fi

    log "ALERT: Both heartbeat AND .claude logs are stale. Claude is frozen."

    # Check lock file before restarting
    if [ -f "$LOCKFILE" ]; then
        LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE") ))
        if [ "$LOCK_AGE" -lt 120 ]; then
            log "Lock file exists (${LOCK_AGE}s old). Another restart in progress. Waiting."
            exit 0
        fi
    fi

    log "Killing stale Claude processes: $CLAUDE_PIDS"
    for pid in $CLAUDE_PIDS; do
        kill "$pid" 2>/dev/null
        log "Killed PID $pid"
    done

    sleep 5

    for pid in $CLAUDE_PIDS; do
        kill -9 "$pid" 2>/dev/null
    done

    sleep 2

    touch "$LOCKFILE"
    export DISPLAY=:0
    cd "$WORKING_DIR"
    gnome-terminal --title="KometzRobot — Meridian Loop" --geometry=220x50 -- \
        bash -c "$WORKING_DIR/start-claude.sh; echo 'Claude exited. Press Enter.'; read" &

    log "Started fresh Claude instance via start-claude.sh in gnome-terminal (PID: $!)"
else
    log "OK: Heartbeat is ${HEARTBEAT_AGE}s old. Claude is alive. Instances: $CLAUDE_COUNT"
    # Clean up lock file if everything is healthy
    rm -f "$LOCKFILE" 2>/dev/null
fi
