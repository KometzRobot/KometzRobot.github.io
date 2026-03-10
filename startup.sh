#!/bin/bash
# KometzRobot startup script
# Called at @reboot via crontab
# Starts supplementary services not managed by systemd
#
# SYSTEMD HANDLES (user): Hub v2 (port 8090), Cloudflare tunnel, Soma (symbiosense)
# SYSTEMD HANDLES (system): Ollama, Tailscale
# DESKTOP AUTOSTART: ProtonMail Bridge (systemd service disabled — conflicts with GUI)
# THIS SCRIPT: Service verification, Proton Bridge wait, watchdog trigger with retry

WORKING_DIR="$HOME/autonomous-ai"
LOG="$WORKING_DIR/startup.log"
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

for SVC in meridian-hub-v2 cloudflare-tunnel symbiosense; do
    if systemctl --user is-active "$SVC" > /dev/null 2>&1; then
        log "OK: $SVC is active"
    else
        log "WARNING: $SVC not active. Attempting start..."
        systemctl --user start "$SVC" 2>/dev/null
        sleep 2
        if systemctl --user is-active "$SVC" > /dev/null 2>&1; then
            log "OK: $SVC started successfully"
        else
            log "FAILED: Could not start $SVC"
        fi
    fi
done

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

# Wait for DISPLAY to become available (desktop login required for Claude terminal)
DISPLAY_WAIT=0
DISPLAY_MAX=180
while [ $DISPLAY_WAIT -lt $DISPLAY_MAX ]; do
    DETECTED_DISPLAY=$(ls /tmp/.X11-unix/ 2>/dev/null | head -1 | tr -d X)
    if [ -n "$DETECTED_DISPLAY" ]; then
        export DISPLAY=":$DETECTED_DISPLAY"
        export XAUTHORITY="$HOME/.Xauthority"
        log "DISPLAY detected: $DISPLAY (waited ${DISPLAY_WAIT}s)"
        break
    fi
    sleep 10
    DISPLAY_WAIT=$((DISPLAY_WAIT + 10))
done
if [ -z "$DETECTED_DISPLAY" ]; then
    log "WARNING: No DISPLAY after ${DISPLAY_MAX}s. Claude cannot open terminal. Cron watchdog will handle it."
fi

# Start Claude (main AI loop) via watchdog — with retry
MAX_RETRIES=3
RETRY_DELAY=30
if [ -n "$DETECTED_DISPLAY" ]; then
    for ATTEMPT in $(seq 1 $MAX_RETRIES); do
        log "Triggering watchdog to start Claude (attempt $ATTEMPT/$MAX_RETRIES)..."
        bash "$WORKING_DIR/watchdog.sh"
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
