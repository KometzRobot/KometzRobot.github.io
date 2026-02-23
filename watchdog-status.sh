#!/bin/bash
# Service Watchdog
# Runs every 5 minutes via cron
# Restarts critical services if they're not running

WORKING_DIR="$HOME/autonomous-ai"
PYTHON="$HOME/miniconda3/bin/python3"
LOG="$WORKING_DIR/watchdog-status.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

export DISPLAY=:0

# Set XAUTHORITY so X11 apps can connect
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY="/run/user/1000/gdm/Xauthority"
elif [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

# Check Command Center v12
if ! pgrep -f "command-center-v13.py" > /dev/null; then
    log "ALERT: command-center-v13.py is NOT running. Restarting..."
    DISPLAY=:0 XAUTHORITY="$XAUTHORITY" $PYTHON "$WORKING_DIR/command-center-v13.py" >> /tmp/command-center.log 2>&1 &
    log "Command Center v12 restarted (PID: $!)"
else
    log "OK: command-center-v13.py is running."
fi

# Check IRC bot
if ! pgrep -f "irc-bot.py" > /dev/null; then
    log "ALERT: irc-bot.py is NOT running. Restarting..."
    nohup $PYTHON "$WORKING_DIR/irc-bot.py" >> "$WORKING_DIR/irc-bot.log" 2>&1 &
    log "IRC bot restarted (PID: $!)"
fi
