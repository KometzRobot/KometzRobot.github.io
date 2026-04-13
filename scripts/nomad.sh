#!/bin/bash
# Project N.O.M.A.D. — Docker-based application (Crosstalk Solutions)
# Usage: bash scripts/nomad.sh start|stop|status|open
#
# Manages NOMAD Docker containers. Separate from IIAB (see scripts/iiab.sh).

NOMAD_DIR="/opt/project-nomad"

case "$1" in
    start)
        echo "Starting Project N.O.M.A.D..."
        cd "$NOMAD_DIR" && echo '590148001' | sudo -S docker compose up -d 2>&1
        echo ""
        echo "N.O.M.A.D. Admin: http://localhost:8080"
        echo "Dozzle Logs:      http://localhost:9999"
        echo ""
        echo "To stop: bash scripts/nomad.sh stop"
        ;;
    stop)
        echo "Stopping Project N.O.M.A.D..."
        cd "$NOMAD_DIR" && echo '590148001' | sudo -S docker compose down 2>&1
        echo "N.O.M.A.D. stopped."
        ;;
    status)
        echo "Project N.O.M.A.D. Status:"
        echo '590148001' | sudo -S docker ps -a --filter "name=^nomad_" --format "  {{.Names}}: {{.Status}}" 2>&1
        ;;
    open)
        xdg-open "http://localhost:8080" 2>/dev/null &
        echo "Opened N.O.M.A.D. Admin in browser."
        ;;
    *)
        echo "Project N.O.M.A.D. — Docker application launcher"
        echo "Usage: bash scripts/nomad.sh [start|stop|status|open]"
        echo ""
        echo "  start  - Start all NOMAD Docker containers"
        echo "  stop   - Stop all NOMAD Docker containers"
        echo "  status - Show container status"
        echo "  open   - Open admin panel in browser"
        ;;
esac
