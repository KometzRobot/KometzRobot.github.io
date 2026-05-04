#!/bin/bash
# Check if any background tasks from previous session are still running or have completed
# Run this at wake to verify previous promises kept

REPORT=""

# 1. USB copy status
if [ -f /tmp/usb-copy-status.txt ]; then
    STATUS=$(cat /tmp/usb-copy-status.txt)
    PID_RUNNING=$(pgrep -f "usb-copy-complete.sh" 2>/dev/null | head -1)

    if [ "$STATUS" = "DONE" ]; then
        REPORT="$REPORT\n[USB COPY] COMPLETE"
    elif [ "$STATUS" = "RUNNING" ] && [ -n "$PID_RUNNING" ]; then
        XFR=$(grep "xfr#" /tmp/usb-copy.log 2>/dev/null | tail -1 | grep -oP "xfr#\d+" 2>/dev/null)
        USED=$(df -h /media/usb3 2>/dev/null | tail -1 | awk '{print $3}')
        REPORT="$REPORT\n[USB COPY] RUNNING (PID $PID_RUNNING, $XFR, $USED used)"
    elif [ "$STATUS" = "RUNNING" ] && [ -z "$PID_RUNNING" ]; then
        REPORT="$REPORT\n[USB COPY] FAILED — process dead, status still RUNNING"
    fi
fi

# 2. Any long-running rsync/cp processes
COPY_PROCS=$(pgrep -a -x rsync 2>/dev/null | head -3)
if [ -n "$COPY_PROCS" ]; then
    REPORT="$REPORT\n[RSYNC] Running: $COPY_PROCS"
fi

# 3. Heartbeat age
if [ -f /home/joel/autonomous-ai/.heartbeat ]; then
    HB_AGE=$(( $(date +%s) - $(stat -c %Y /home/joel/autonomous-ai/.heartbeat) ))
    REPORT="$REPORT\n[HEARTBEAT] Age: ${HB_AGE}s"
fi

if [ -z "$REPORT" ]; then
    echo "[check-background-tasks] No tracked background tasks"
else
    echo -e "[check-background-tasks]$REPORT"
fi
