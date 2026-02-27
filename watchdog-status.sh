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
    # Email alerts DISABLED (Loop 2060) — Joel asked us to stop spamming him.
    # Alerts now go to relay + log only.
    local subject="$1"
    local body="$2"
    log "ALERT (no email): $subject — $body"
    $PYTHON -c "
import sqlite3, datetime
conn = sqlite3.connect('$WORKING_DIR/agent-relay.db')
c = conn.cursor()
c.execute('INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)',
    ('Watchdog', '''$subject: $body'''[:300], 'alert', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
conn.commit()
conn.close()
" 2>/dev/null
}

export DISPLAY=:$(ls /tmp/.X11-unix/ 2>/dev/null | head -1 | tr -d X || echo 0)

# Set XAUTHORITY so X11 apps can connect
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY="/run/user/1000/gdm/Xauthority"
elif [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

FAILURES=""
RESTARTS=""

# ── Check The Signal (web dashboard, port 8090) ──────────────────
# Managed by systemd: meridian-web-dashboard. Check via pgrep for the-signal.py.
if ! pgrep -f "the-signal.py" > /dev/null; then
    log "ALERT: The Signal is NOT running. Restarting via systemd..."
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    systemctl --user restart meridian-web-dashboard 2>/dev/null
    log "The Signal restarted via systemd"
    RESTARTS="${RESTARTS}The Signal (systemd restart)\n"
else
    log "OK: The Signal is running."
fi

# ── Check Command Center v20 (desktop hub) ────────────────────────
# Managed by systemd: meridian-hub-v16
if ! pgrep -f "command-center-v1[56].py" > /dev/null; then
    log "ALERT: Desktop hub is NOT running. Restarting via systemd..."
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    systemctl --user restart meridian-hub-v16 2>/dev/null
    log "Desktop hub restarted via systemd"
    RESTARTS="${RESTARTS}Desktop Hub v20 (systemd restart)\n"
else
    log "OK: Desktop hub is running."
fi

# IRC bot RETIRED (Loop 2022) — removed from watchdog

# ── Check Ollama ──────────────────────────────────────────────────
# Ollama is a system-level service (not user).
if ! pgrep -f "ollama serve" > /dev/null; then
    log "ALERT: Ollama is NOT running. Restarting via systemd..."
    sudo systemctl restart ollama 2>/dev/null
    log "Ollama restarted via systemd"
    RESTARTS="${RESTARTS}Ollama (systemd restart)\n"
else
    log "OK: Ollama is running."
fi

# ── Check Proton Bridge ──────────────────────────────────────────
# Bridge managed by systemd user service (protonmail-bridge).
# Known issue: snap can lose account after reboot. Joel must re-add via GUI.
if ! pgrep -f "protonmail-bridge" > /dev/null; then
    log "ALERT: Proton Bridge is NOT running."
    FAILURES="${FAILURES}Proton Bridge is DOWN\n"
    # Try systemd restart (won't fix missing account, but starts the process)
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    systemctl --user restart protonmail-bridge 2>/dev/null
    log "Attempted Proton Bridge restart via systemd"
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
