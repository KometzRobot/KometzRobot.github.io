#!/bin/bash
# KometzRobot startup script
# Called at @reboot via crontab
# Starts supplementary services not managed by systemd
#
# SYSTEMD HANDLES (user): protonmail-bridge, meridian-hub-v2, the-chorus, cloudflare-tunnel, symbiosense
# SYSTEMD HANDLES (system): Ollama, Tailscale
# THIS SCRIPT: Clean stale lock files, start/verify all user services, verify ports, watchdog trigger

WORKING_DIR="$HOME/autonomous-ai"
LOG="$WORKING_DIR/logs/startup.log"
PYTHON="$HOME/miniconda3/bin/python3"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "=== STARTUP INITIATED ==="

# Wait for desktop + systemd user services to be ready
sleep 20

# Verify systemd user services are active
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# Clean stale Proton Bridge lock files before starting services
rm -f "$HOME/.local/share/protonmail/bridge-v3/bridge.lock" 2>/dev/null
rm -f "$HOME/.cache/protonmail/bridge-v3/bridge.lock" 2>/dev/null
# Kill any orphaned bridge processes from previous boot
pkill -f "protonmail-bridge\|proton-bridge" 2>/dev/null
sleep 2

for SVC in protonmail-bridge meridian-hub-v2 the-chorus cloudflare-tunnel symbiosense; do
    if systemctl --user is-active "$SVC" > /dev/null 2>&1; then
        log "OK: $SVC is active"
    else
        log "WARNING: $SVC not active. Attempting start..."
        systemctl --user start "$SVC" 2>/dev/null
        sleep 3
        if systemctl --user is-active "$SVC" > /dev/null 2>&1; then
            log "OK: $SVC started successfully"
        else
            log "FAILED: Could not start $SVC"
        fi
    fi
done

# Verify critical ports respond (not just systemd active)
# Retry with backoff — restart service if port doesn't come up
log "Verifying ports (with retry)..."
sleep 10

verify_port() {
    local PORT=$1 NAME=$2 SVC=$3
    local MAX_TRIES=3 WAIT=5
    for TRY in $(seq 1 $MAX_TRIES); do
        if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
            log "OK: Port $PORT ($NAME) listening"
            return 0
        fi
        if [ "$TRY" -lt "$MAX_TRIES" ]; then
            log "RETRY $TRY/$MAX_TRIES: Port $PORT ($NAME) not listening. Restarting $SVC..."
            systemctl --user restart "$SVC" 2>/dev/null
            sleep $WAIT
            WAIT=$((WAIT * 2))  # Exponential backoff
        fi
    done
    log "FAILED: Port $PORT ($NAME) still not listening after $MAX_TRIES attempts"
    return 1
}

FAILED_PORTS=0
verify_port 8090 "hub-v2" "meridian-hub-v2" || FAILED_PORTS=$((FAILED_PORTS+1))
verify_port 8091 "chorus" "the-chorus" || FAILED_PORTS=$((FAILED_PORTS+1))
verify_port 1144 "bridge-imap" "protonmail-bridge" || FAILED_PORTS=$((FAILED_PORTS+1))
verify_port 1026 "bridge-smtp" "protonmail-bridge" || FAILED_PORTS=$((FAILED_PORTS+1))

if [ "$FAILED_PORTS" -gt 2 ]; then
    log "CRITICAL: $FAILED_PORTS ports failed. System may need manual intervention."
fi

# Ollama (local AI model server) — system service
if ! pgrep -f "ollama serve" > /dev/null; then
    if sudo -n systemctl start ollama 2>/dev/null; then
        log "Ollama started via systemd"
    else
        log "WARNING: Could not start Ollama (sudo needs password). Will retry next watchdog cycle."
    fi
    sleep 5
else
    log "Ollama already running"
fi

# Wait for a FULLY WORKING X session (not just socket — need xauth too)
# Problem: DISPLAY socket appears before gnome-session grants xauth.
# Fix: wait until xdpyinfo actually succeeds, meaning we have full X access.
DISPLAY_WAIT=0
DISPLAY_MAX=300
DETECTED_DISPLAY=""
while [ $DISPLAY_WAIT -lt $DISPLAY_MAX ]; do
    CANDIDATE=$(ls /tmp/.X11-unix/ 2>/dev/null | head -1 | tr -d X)
    if [ -n "$CANDIDATE" ]; then
        export DISPLAY=":$CANDIDATE"
        export XAUTHORITY="$HOME/.Xauthority"
        # Test that we can actually USE the display (xauth is ready)
        if xdpyinfo >/dev/null 2>&1; then
            DETECTED_DISPLAY="$CANDIDATE"
            log "DISPLAY :$CANDIDATE fully working (waited ${DISPLAY_WAIT}s)"
            break
        else
            log "DISPLAY :$CANDIDATE exists but xauth not ready yet (${DISPLAY_WAIT}s)..."
        fi
    fi
    sleep 10
    DISPLAY_WAIT=$((DISPLAY_WAIT + 10))
done
if [ -z "$DETECTED_DISPLAY" ]; then
    log "WARNING: No working DISPLAY after ${DISPLAY_MAX}s. Cron watchdog will handle it."
fi

# Start Claude (main AI loop) via watchdog — with retry
MAX_RETRIES=3
RETRY_DELAY=30
if [ -n "$DETECTED_DISPLAY" ]; then
    for ATTEMPT in $(seq 1 $MAX_RETRIES); do
        log "Triggering watchdog to start Claude (attempt $ATTEMPT/$MAX_RETRIES)..."
        bash "$WORKING_DIR/scripts/watchdog.sh"
        sleep 15

        # Verify Claude actually started
        if pgrep -f "claude --dangerously-skip-permissions" > /dev/null; then
            log "OK: Claude is running after attempt $ATTEMPT"
            break
        else
            if [ "$ATTEMPT" -lt "$MAX_RETRIES" ]; then
                log "WARNING: Claude not detected after watchdog. Retrying in ${RETRY_DELAY}s..."
                sleep "$RETRY_DELAY"
            else
                log "FAILED: Claude did not start after $MAX_RETRIES attempts. Cron watchdog will retry in 10 min."
            fi
        fi
    done
else
    log "Skipping Claude start — no DISPLAY. Cron watchdog will start Claude when desktop is ready."
fi

# Post startup status to agent relay
$PYTHON -c "
import sqlite3, datetime
try:
    conn = sqlite3.connect('$WORKING_DIR/agent-relay.db')
    c = conn.cursor()
    c.execute('INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)',
        ('Startup', 'System boot complete. Services verified. Claude watchdog triggered.', 'startup', datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
except: pass
" 2>/dev/null

log "=== STARTUP COMPLETE ==="
