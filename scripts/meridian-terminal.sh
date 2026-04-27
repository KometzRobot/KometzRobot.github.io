#!/bin/bash
# ═══════════════════════════════════════════════════════
#  Meridian Terminal — System Dashboard & Quick Commands
# ═══════════════════════════════════════════════════════

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

WORK_DIR="/home/joel/autonomous-ai"
cd "$WORK_DIR"

show_header() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║       MERIDIAN TERMINAL v1.0             ║"
    echo "  ╚══════════════════════════════════════════╝${NC}"
    echo ""
}

show_status() {
    echo -e "${BOLD}═══ SYSTEM STATUS ═══${NC}"
    
    # Loop info
    LOOP=$(cat .loop-count 2>/dev/null || echo "?")
    echo -e "  Loop:      ${GREEN}$LOOP${NC}"
    
    # Heartbeat
    if [ -f .heartbeat ]; then
        HB_AGE=$(( $(date +%s) - $(stat -c %Y .heartbeat) ))
        if [ "$HB_AGE" -lt 300 ]; then
            echo -e "  Heartbeat: ${GREEN}${HB_AGE}s ago${NC}"
        else
            echo -e "  Heartbeat: ${RED}${HB_AGE}s ago (STALE!)${NC}"
        fi
    else
        echo -e "  Heartbeat: ${RED}NO FILE${NC}"
    fi
    
    # Services
    echo -e "\n${BOLD}═══ SERVICES ═══${NC}"
    for svc in meridian-hub-v2 symbiosense the-chorus command-center; do
        STATUS=$(systemctl is-active "$svc" 2>/dev/null)
        if [ "$STATUS" = "active" ]; then
            echo -e "  $svc: ${GREEN}running${NC}"
        else
            echo -e "  $svc: ${RED}$STATUS${NC}"
        fi
    done
    
    # Claude Code
    CLAUDE_PID=$(pgrep -f "claude" 2>/dev/null | head -1)
    if [ -n "$CLAUDE_PID" ]; then
        echo -e "  Claude Code: ${GREEN}running (PID $CLAUDE_PID)${NC}"
    else
        echo -e "  Claude Code: ${YELLOW}not detected${NC}"
    fi
    
    # System resources
    echo -e "\n${BOLD}═══ RESOURCES ═══${NC}"
    LOAD=$(cat /proc/loadavg | awk '{print $1, $2, $3}')
    MEM=$(free -h | awk '/^Mem:/{print $3 "/" $2}')
    DISK=$(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')
    echo -e "  Load:  $LOAD"
    echo -e "  RAM:   $MEM"
    echo -e "  Disk:  $DISK"
    
    # USB drives
    USB_COUNT=$(lsblk -o TYPE,MOUNTPOINT | grep -c "part.*media")
    if [ "$USB_COUNT" -gt 0 ]; then
        echo -e "\n${BOLD}═══ USB DRIVES ═══${NC}"
        lsblk -o NAME,SIZE,LABEL,MOUNTPOINT | grep -E "sd[b-z]|CINDER" | sed 's/^/  /'
    fi
    
    # Recent email count
    echo -e "\n${BOLD}═══ RECENT ACTIVITY ═══${NC}"
    UNSEEN=$(python3 -c "
import imaplib, os, sys
sys.path.insert(0, 'scripts')
from load_env import *
try:
    M = imaplib.IMAP4('127.0.0.1', 1144)
    M.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
    M.select('INBOX')
    typ, data = M.search(None, 'UNSEEN')
    print(len(data[0].split()) if data[0] else 0)
    M.logout()
except:
    print('?')
" 2>/dev/null)
    echo -e "  Unseen emails: $UNSEEN"
    
    # Recent git commits
    echo -e "  Last commit: $(git log --oneline -1 2>/dev/null)"
    
    # Tunnel URL
    TUNNEL=$(python3 -c "import json; print(json.load(open('signal-config.json'))['TUNNEL_URL'])" 2>/dev/null || echo "?")
    echo -e "  Hub URL: $TUNNEL"
}

show_menu() {
    echo -e "\n${BOLD}═══ QUICK COMMANDS ═══${NC}"
    echo "  [1] Restart all services"
    echo "  [2] View recent logs"
    echo "  [3] Check email"
    echo "  [4] Open Hub in browser"
    echo "  [5] Run loop-fitness"
    echo "  [6] Push live status"
    echo "  [7] Restart Claude Code"
    echo "  [8] Git status"
    echo "  [9] Flash Cinder USB"
    echo "  [r] Refresh status"
    echo "  [q] Quit"
    echo ""
    echo -n "  > "
}

handle_choice() {
    case "$1" in
        1)
            echo "Restarting services..."
            for svc in meridian-hub-v2 symbiosense the-chorus command-center; do
                sudo systemctl restart "$svc" 2>/dev/null && echo "  Restarted $svc" || echo "  Failed: $svc"
            done
            read -p "Press Enter..."
            ;;
        2)
            echo "Recent agent messages:"
            sqlite3 agent-relay.db "SELECT agent, substr(message,1,80), datetime(timestamp,'localtime') FROM agent_messages ORDER BY timestamp DESC LIMIT 15;" 2>/dev/null
            echo ""
            read -p "Press Enter..."
            ;;
        3)
            python3 -c "
import imaplib, email, os, sys
sys.path.insert(0, 'scripts')
from load_env import *
M = imaplib.IMAP4('127.0.0.1', 1144)
M.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])
M.select('INBOX')
typ, data = M.search(None, 'ALL')
ids = data[0].split()
for eid in ids[-10:]:
    typ, msg_data = M.fetch(eid, '(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
    flags = msg_data[0][0].decode()
    header = msg_data[0][1].decode(errors='replace').strip()
    seen = 'Seen' in flags
    mark = '  ' if seen else '* '
    print(f'{mark}{header[:100]}')
M.logout()
" 2>/dev/null
            echo ""
            read -p "Press Enter..."
            ;;
        4)
            TUNNEL=$(python3 -c "import json; print(json.load(open('signal-config.json'))['TUNNEL_URL'])" 2>/dev/null)
            xdg-open "$TUNNEL" 2>/dev/null || echo "URL: $TUNNEL"
            ;;
        5)
            python3 scripts/loop-fitness.py 2>/dev/null | tail -20
            read -p "Press Enter..."
            ;;
        6)
            python3 scripts/push-live-status.py 2>/dev/null
            echo "Status pushed."
            read -p "Press Enter..."
            ;;
        7)
            echo "Starting Claude Code..."
            claude --dangerously-skip-permissions &
            echo "Claude Code launched in background."
            read -p "Press Enter..."
            ;;
        8)
            git status
            echo ""
            git log --oneline -5
            read -p "Press Enter..."
            ;;
        9)
            echo "Cinder USB options:"
            echo "  Build image: sudo bash products/cinder-anythingllm/build-usb-image.sh"
            echo "  Flash: sudo dd if=products/cinder-anythingllm/cinder-usb.img of=/dev/sdX bs=4M status=progress"
            echo ""
            lsblk -o NAME,SIZE,TYPE,LABEL | grep -E "disk|sd[b-z]"
            read -p "Press Enter..."
            ;;
        r|R)
            ;;
        q|Q)
            echo -e "${CYAN}Meridian Terminal closed.${NC}"
            exit 0
            ;;
        *)
            echo "Unknown command."
            read -p "Press Enter..."
            ;;
    esac
}

# Main loop
while true; do
    show_header
    show_status
    show_menu
    read -r choice
    handle_choice "$choice"
done
