#!/bin/bash
# Service Watchdog v2 — Beefed up per Joel's request
# Runs every 5 minutes via cron
# Checks ALL critical services, restarts if down, emails Joel on failures

WORKING_DIR="$HOME/autonomous-ai"
PYTHON="$HOME/miniconda3/bin/python3"
LOG="$WORKING_DIR/watchdog-status.log"
ALERT_STATE="$WORKING_DIR/.watchdog-alert-state"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

send_alert() {
    local subject="$1"
    local body="$2"
    $PYTHON -c "
import smtplib
from email.mime.text import MIMEText
msg = MIMEText('''$body''')
msg['Subject'] = '$subject'
msg['From'] = 'kometzrobot@proton.me'
msg['To'] = 'jkometz@hotmail.com'
try:
    with smtplib.SMTP('127.0.0.1', 1025) as s:
        s.starttls()
        s.login('kometzrobot@proton.me', '2DTEz9UgO6nFqmlMxHzuww')
        s.send_message(msg)
except: pass
" 2>/dev/null
}

export DISPLAY=:0

# Set XAUTHORITY so X11 apps can connect
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY="/run/user/1000/gdm/Xauthority"
elif [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

FAILURES=""
RESTARTS=""

# ── Check Web Dashboard ───────────────────────────────────────────
if ! pgrep -f "command-center-web.py" > /dev/null; then
    log "ALERT: web dashboard is NOT running. Restarting..."
    nohup $PYTHON "$WORKING_DIR/command-center-web.py" >> /tmp/command-center-web.log 2>&1 &
    log "Web Dashboard restarted (PID: $!)"
    RESTARTS="${RESTARTS}Web Dashboard (PID $!)\n"
else
    log "OK: web dashboard is running."
fi

# ── Check Command Center v15 ──────────────────────────────────────
if ! pgrep -f "command-center-v1[56].py" > /dev/null; then
    log "ALERT: command-center is NOT running. Restarting v16..."
    DISPLAY=:0 XAUTHORITY="$XAUTHORITY" $PYTHON "$WORKING_DIR/command-center-v16.py" >> /tmp/command-center.log 2>&1 &
    log "Command Center v16 restarted (PID: $!)"
    RESTARTS="${RESTARTS}Command Center v16 (PID $!)\n"
else
    log "OK: command-center is running."
fi

# ── Check IRC bot ─────────────────────────────────────────────────
if ! pgrep -f "irc-bot.py" > /dev/null; then
    log "ALERT: irc-bot.py is NOT running. Restarting..."
    nohup $PYTHON "$WORKING_DIR/irc-bot.py" >> "$WORKING_DIR/irc-bot.log" 2>&1 &
    log "IRC bot restarted (PID: $!)"
    RESTARTS="${RESTARTS}IRC Bot (PID $!)\n"
else
    log "OK: irc-bot.py is running."
fi

# ── Check Ollama ──────────────────────────────────────────────────
if ! pgrep -f "ollama serve" > /dev/null; then
    log "ALERT: Ollama is NOT running. Restarting..."
    nohup /usr/local/bin/ollama serve >> /tmp/ollama.log 2>&1 &
    log "Ollama restarted (PID: $!)"
    RESTARTS="${RESTARTS}Ollama (PID $!)\n"
else
    log "OK: Ollama is running."
fi

# ── Check Proton Bridge ──────────────────────────────────────────
if ! pgrep -f "protonmail-bridge" > /dev/null; then
    log "ALERT: Proton Bridge is NOT running."
    FAILURES="${FAILURES}Proton Bridge is DOWN (cannot auto-restart snap service)\n"
    # Try to restart via snap
    snap run protonmail-bridge --noninteractive >> /tmp/proton-bridge.log 2>&1 &
    log "Attempted Proton Bridge restart"
    RESTARTS="${RESTARTS}Proton Bridge (attempted)\n"
else
    log "OK: Proton Bridge is running."
fi

# ── Check Heartbeat freshness ────────────────────────────────────
HB_FILE="$WORKING_DIR/.heartbeat"
if [ -f "$HB_FILE" ]; then
    HB_AGE=$(( $(date +%s) - $(stat -c %Y "$HB_FILE") ))
    if [ "$HB_AGE" -gt 900 ]; then
        log "WARNING: Heartbeat is ${HB_AGE}s old (>15min). Meridian may be frozen."
        FAILURES="${FAILURES}Heartbeat stale: ${HB_AGE}s old\n"
    else
        log "OK: Heartbeat ${HB_AGE}s old."
    fi
else
    log "WARNING: No heartbeat file."
    FAILURES="${FAILURES}No heartbeat file found\n"
fi

# ── Check disk space ─────────────────────────────────────────────
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d '% ')
if [ "$DISK_PCT" -gt 90 ]; then
    log "ALERT: Disk usage at ${DISK_PCT}%!"
    FAILURES="${FAILURES}Disk usage critical: ${DISK_PCT}%\n"
elif [ "$DISK_PCT" -gt 80 ]; then
    log "WARNING: Disk usage at ${DISK_PCT}%."
fi

# ── Check RAM ────────────────────────────────────────────────────
RAM_FREE=$(awk '/MemAvailable/ {printf "%.0f", $2/1024}' /proc/meminfo)
if [ "$RAM_FREE" -lt 500 ]; then
    log "ALERT: Only ${RAM_FREE}MB RAM available!"
    FAILURES="${FAILURES}Low RAM: only ${RAM_FREE}MB free\n"
fi

# ── Check cron jobs (by state file freshness) ────────────────────
check_cron() {
    local name="$1" file="$2" max_age="$3"
    if [ -f "$file" ]; then
        local age=$(( $(date +%s) - $(stat -c %Y "$file") ))
        if [ "$age" -gt "$max_age" ]; then
            log "WARNING: $name state file is ${age}s old (max ${max_age}s). Cron may have stopped."
            FAILURES="${FAILURES}Cron job '$name' may be stale (${age}s)\n"
        else
            log "OK: $name cron active (${age}s old)."
        fi
    else
        log "WARNING: $name state file not found."
    fi
}

check_cron "Eos Watchdog" "$WORKING_DIR/.eos-watchdog-state.json" 300
check_cron "Nova" "$WORKING_DIR/.nova-state.json" 1200
check_cron "Push Live Status" "/tmp/KometzRobot.github.io/status.json" 600

# ── Send alert if there are failures ─────────────────────────────
if [ -n "$FAILURES" ] || [ -n "$RESTARTS" ]; then
    # Rate limit: only email once per 30 minutes
    SHOULD_ALERT=true
    if [ -f "$ALERT_STATE" ]; then
        ALERT_AGE=$(( $(date +%s) - $(stat -c %Y "$ALERT_STATE") ))
        if [ "$ALERT_AGE" -lt 1800 ]; then
            SHOULD_ALERT=false
            log "Alert suppressed (last alert ${ALERT_AGE}s ago, min 1800s)"
        fi
    fi

    if [ "$SHOULD_ALERT" = true ]; then
        ALERT_BODY="Watchdog Report — $(date '+%Y-%m-%d %H:%M:%S')\n\n"
        if [ -n "$RESTARTS" ]; then
            ALERT_BODY="${ALERT_BODY}RESTARTED:\n${RESTARTS}\n"
        fi
        if [ -n "$FAILURES" ]; then
            ALERT_BODY="${ALERT_BODY}ISSUES:\n${FAILURES}\n"
        fi
        ALERT_BODY="${ALERT_BODY}System: Load $(cat /proc/loadavg | cut -d' ' -f1-3), RAM ${RAM_FREE}MB free, Disk ${DISK_PCT}%"

        send_alert "WATCHDOG ALERT: Service issues detected" "$ALERT_BODY"
        touch "$ALERT_STATE"
        log "Alert email sent to Joel."
    fi
else
    log "ALL CLEAR: All services healthy."
    # Remove alert state when everything is fine
    rm -f "$ALERT_STATE" 2>/dev/null
fi
