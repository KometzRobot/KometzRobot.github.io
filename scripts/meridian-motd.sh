#!/bin/bash
# Meridian MOTD — shows system status on SSH login
# Installed at /etc/update-motd.d/99-meridian

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║         MERIDIAN CONTROL TERMINAL        ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Loop count
LOOP=$(cat /home/joel/autonomous-ai/.loop-count 2>/dev/null || echo "?")
echo "  Loop: $LOOP"

# Heartbeat age
if [ -f /home/joel/autonomous-ai/.heartbeat ]; then
    HB_AGE=$(( $(date +%s) - $(stat -c %Y /home/joel/autonomous-ai/.heartbeat) ))
    if [ $HB_AGE -lt 300 ]; then
        echo "  Heartbeat: ${HB_AGE}s ago (ALIVE)"
    else
        echo "  Heartbeat: ${HB_AGE}s ago (STALE!)"
    fi
fi

# System load
LOAD=$(uptime | awk -F'load average:' '{print $2}' | xargs)
RAM=$(free -h | awk '/Mem:/ {printf "%s / %s (%s used)", $3, $2, $3}')
DISK=$(df -h / | awk 'NR==2 {printf "%s / %s (%s)", $3, $2, $5}')
SWAP=$(free -h | awk '/Swap:/ {printf "%s / %s", $3, $2}')

echo "  Load: $LOAD"
echo "  RAM:  $RAM"
echo "  Disk: $DISK"
echo "  Swap: $SWAP"

# Services (process-based detection)
echo ""
echo "  Services:"
declare -A SVCS=( ["hub-v2"]="hub-v2.py" ["soma"]="symbiosense.py" ["chorus"]="the-chorus.py" ["cmd-center"]="command-center.py" )
for name in hub-v2 soma chorus cmd-center; do
    PROC=${SVCS[$name]}
    PID=$(pgrep -f "$PROC" 2>/dev/null | head -1)
    if [ -n "$PID" ]; then
        echo "    ● $name: running (pid $PID)"
    else
        echo "    ○ $name: stopped"
    fi
done

# Tailscale
TS_IP=$(tailscale ip -4 2>/dev/null || echo "?")
echo ""
echo "  Tailscale IP: $TS_IP"
echo "  Hub: http://$TS_IP:8090"
echo ""
echo "  Quick commands:"
echo "    htop                    — system monitor"
echo "    journalctl -fu <svc>   — watch service logs"
echo "    cd ~/autonomous-ai     — project root"
echo "    sqlite3 agent-relay.db — agent messages"
echo ""
