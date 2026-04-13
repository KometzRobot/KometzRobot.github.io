#!/bin/bash
# IIAB (Internet-in-a-Box) — on-demand service launcher
# Usage: bash scripts/iiab.sh start|stop|status|open
#
# Manages IIAB systemd services. Separate from Project NOMAD (see scripts/nomad.sh).

SERVICES="iiab-cmdsrv kiwix-serve kolibri postgresql-iiab iiab-startup"

case "$1" in
    start)
        echo "Starting Internet-in-a-Box..."
        for svc in $SERVICES; do
            echo "  Starting $svc..."
            echo '590148001' | sudo -S systemctl start "$svc" 2>/dev/null
        done
        sleep 2
        echo ""
        echo "IIAB is running:"
        echo "  Kiwix Library: http://localhost:3000/kiwix/"
        echo "  Kolibri:       http://localhost:8009/kolibri/"
        echo "  IIAB Admin:    http://localhost:8083"
        echo ""
        echo "To stop: bash scripts/iiab.sh stop"
        ;;
    stop)
        echo "Stopping Internet-in-a-Box..."
        for svc in $SERVICES; do
            echo "  Stopping $svc..."
            echo '590148001' | sudo -S systemctl stop "$svc" 2>/dev/null
        done
        echo "IIAB stopped."
        ;;
    status)
        echo "Internet-in-a-Box Status:"
        for svc in $SERVICES; do
            state=$(systemctl is-active "$svc" 2>/dev/null)
            printf "  %-20s %s\n" "$svc:" "$state"
        done
        ;;
    open)
        xdg-open "http://localhost:8083" 2>/dev/null &
        echo "Opened IIAB Admin in browser."
        ;;
    *)
        echo "Internet-in-a-Box — on-demand service launcher"
        echo "Usage: bash scripts/iiab.sh [start|stop|status|open]"
        echo ""
        echo "  start  - Launch IIAB services"
        echo "  stop   - Stop IIAB services"
        echo "  status - Check service status"
        echo "  open   - Open admin panel in browser"
        ;;
esac
