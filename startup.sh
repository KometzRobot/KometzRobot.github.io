#!/bin/bash
# KometzRobot startup script
# Called at @reboot via crontab
# Starts supplementary services not managed by systemd
#
# SYSTEMD HANDLES: Command Center v22, The Signal, Cloudflare tunnel, Soma
# DESKTOP AUTOSTART: ProtonMail Bridge (systemd service disabled — conflicts with GUI)
# THIS SCRIPT: Ollama (if not already running), watchdog trigger

WORKING_DIR="$HOME/autonomous-ai"
LOG="$WORKING_DIR/startup.log"
PYTHON="$HOME/miniconda3/bin/python3"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

log "=== STARTUP INITIATED ==="

# Wait for desktop + systemd user services to be ready
sleep 20

# Ollama (local AI model server) — system service
if ! pgrep -f "ollama serve" > /dev/null; then
    # Try systemd first (preferred). If that fails, DON'T start manually — it'll conflict later.
    if sudo -n systemctl start ollama 2>/dev/null; then
        log "Ollama started via systemd"
    else
        log "WARNING: Could not start Ollama (sudo needs password). Will retry next watchdog cycle."
    fi
    sleep 5
else
    log "Ollama already running"
fi

# Start Claude (main AI loop) via watchdog
log "Triggering watchdog to start Claude..."
bash "$WORKING_DIR/watchdog.sh"

log "=== STARTUP COMPLETE ==="
