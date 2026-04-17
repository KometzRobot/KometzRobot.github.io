#!/bin/bash
# cron-tools.sh — Interactive cron management tool for Joel
# Usage: bash scripts/cron-tools.sh [command]
# Commands: status, logs, test, add, next, health

set -e
LOGDIR="/home/joel/autonomous-ai/logs"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

show_help() {
    echo -e "${BOLD}cron-tools.sh — Your cron job toolkit${NC}"
    echo ""
    echo -e "  ${CYAN}status${NC}     Show all active jobs with human-readable schedules"
    echo -e "  ${CYAN}logs${NC}       Check recent output from any job's log"
    echo -e "  ${CYAN}health${NC}     Which jobs are healthy? Which haven't run recently?"
    echo -e "  ${CYAN}test${NC}       Test-run a script manually (without cron)"
    echo -e "  ${CYAN}next${NC}       When will a cron expression fire next?"
    echo -e "  ${CYAN}running${NC}    What's running right now?"
    echo -e "  ${CYAN}add${NC}        Add a new cron job (guided)"
    echo ""
    echo -e "  Example: ${BOLD}bash scripts/cron-tools.sh status${NC}"
}

human_schedule() {
    local sched="$1"
    case "$sched" in
        "@reboot") echo "on server boot" ;;
        "*/3 * * * *") echo "every 3 minutes" ;;
        "*/5 * * * *") echo "every 5 minutes" ;;
        "*/10 * * * *") echo "every 10 minutes" ;;
        "*/30 * * * *") echo "every 30 minutes" ;;
        "0 7 * * *") echo "daily at 7:00 AM" ;;
        "0 3 * * *") echo "daily at 3:00 AM" ;;
        "0 4 * * *") echo "daily at 4:00 AM" ;;
        "0 5 * * *") echo "daily at 5:00 AM" ;;
        *)
            local min=$(echo "$sched" | awk '{print $1}')
            local hr=$(echo "$sched" | awk '{print $2}')
            local dom=$(echo "$sched" | awk '{print $3}')
            local mon=$(echo "$sched" | awk '{print $4}')
            local dow=$(echo "$sched" | awk '{print $5}')

            if [[ "$min" == *"/"* ]]; then
                local interval="${min#*/}"
                if [[ "$hr" == "*" ]]; then echo "every ${interval} min"
                elif [[ "$hr" == *"/"* ]]; then echo "every ${interval} min, every ${hr#*/} hr"
                fi
            elif [[ "$hr" == *"/"* ]]; then
                echo "min $min, every ${hr#*/} hr"
            elif [[ "$min" == *","* ]]; then
                echo "at min $min, every hr"
            elif [[ "$hr" != "*" && "$dom" == "*" ]]; then
                printf "daily at %02d:%02d\n" "$hr" "$min"
            else
                echo "$sched"
            fi
            ;;
    esac
}

cmd_status() {
    echo -e "${BOLD}Active Cron Jobs${NC}"
    echo -e "${BOLD}$(printf '%-25s %-30s %s' 'SCHEDULE' 'SCRIPT' 'WHEN')${NC}"
    echo "────────────────────────────────────────────────────────────────────────"

    crontab -l | grep -v '^#' | grep -v '^$' | grep -v '^[[:space:]]*$' | while IFS= read -r line; do
        if [[ "$line" == @reboot* ]]; then
            local script=$(echo "$line" | grep -oP '[\w-]+\.(sh|py)' | head -1)
            printf "%-25s %-30s %s\n" "@reboot" "${script:-boot-script}" "on server boot"
        else
            local sched=$(echo "$line" | awk '{print $1, $2, $3, $4, $5}')
            local script=$(echo "$line" | grep -oP '[\w-]+\.(sh|py)' | head -1)
            local when=$(human_schedule "$sched")
            printf "%-25s %-30s %s\n" "$sched" "${script:-unknown}" "$when"
        fi
    done

    local total=$(crontab -l | grep -v '^#' | grep -v '^$' | grep -v '^[[:space:]]*$' | wc -l)
    local disabled=$(crontab -l | grep '^# DISABLED' | wc -l)
    echo ""
    echo -e "${GREEN}$total active jobs${NC}, ${YELLOW}$disabled disabled${NC}"
}

cmd_logs() {
    if [ -z "$2" ]; then
        echo -e "${BOLD}Available logs:${NC}"
        echo ""
        ls -1t "$LOGDIR"/*.log 2>/dev/null | head -20 | while read -r f; do
            local name=$(basename "$f" .log)
            local size=$(du -h "$f" | awk '{print $1}')
            local mod=$(stat -c '%y' "$f" | cut -d. -f1)
            printf "  %-30s %6s  %s\n" "$name" "$size" "$mod"
        done
        echo ""
        echo -e "Usage: ${BOLD}bash scripts/cron-tools.sh logs <name>${NC}"
        echo -e "Example: ${BOLD}bash scripts/cron-tools.sh logs watchdog${NC}"
    else
        local logfile="$LOGDIR/$2.log"
        if [ -f "$logfile" ]; then
            echo -e "${BOLD}Last 20 lines of $2.log:${NC}"
            echo ""
            tail -20 "$logfile"
        else
            echo -e "${RED}No log file: $logfile${NC}"
            echo "Try: bash scripts/cron-tools.sh logs"
        fi
    fi
}

cmd_health() {
    echo -e "${BOLD}Cron Job Health Check${NC}"
    echo -e "${BOLD}$(printf '%-30s %-12s %-20s %s' 'SCRIPT' 'STATUS' 'LAST OUTPUT' 'SIZE')${NC}"
    echo "────────────────────────────────────────────────────────────────────────"

    for logfile in "$LOGDIR"/*.log; do
        [ -f "$logfile" ] || continue
        local name=$(basename "$logfile" .log)
        local size=$(du -h "$logfile" | awk '{print $1}')
        local age_sec=$(( $(date +%s) - $(stat -c '%Y' "$logfile") ))

        local status
        if [ "$age_sec" -lt 600 ]; then
            status="${GREEN}ACTIVE${NC}"
        elif [ "$age_sec" -lt 3600 ]; then
            status="${YELLOW}IDLE${NC}"
        else
            status="${RED}STALE${NC}"
        fi

        local age_human
        if [ "$age_sec" -lt 60 ]; then
            age_human="${age_sec}s ago"
        elif [ "$age_sec" -lt 3600 ]; then
            age_human="$(( age_sec / 60 ))m ago"
        elif [ "$age_sec" -lt 86400 ]; then
            age_human="$(( age_sec / 3600 ))h ago"
        else
            age_human="$(( age_sec / 86400 ))d ago"
        fi

        printf "%-30s %-22b %-20s %s\n" "$name" "$status" "$age_human" "$size"
    done
}

cmd_running() {
    echo -e "${BOLD}Currently Running Cron Scripts${NC}"
    echo ""
    ps aux | grep -E '(scripts/|autonomous-ai)' | grep -v grep | grep -v cron-tools | while read -r line; do
        local pid=$(echo "$line" | awk '{print $2}')
        local cpu=$(echo "$line" | awk '{print $3}')
        local mem=$(echo "$line" | awk '{print $4}')
        local cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf $i" "; print ""}')
        local script=$(echo "$cmd" | grep -oP '[\w-]+\.(sh|py)' | head -1)
        if [ -n "$script" ]; then
            printf "  PID %-8s CPU %-5s MEM %-5s %s\n" "$pid" "$cpu%" "$mem%" "$script"
        fi
    done
    echo ""
    echo -e "System load: $(uptime | grep -oP 'load average: .*')"
}

cmd_test() {
    if [ -z "$2" ]; then
        echo "Usage: bash scripts/cron-tools.sh test <script-name>"
        echo "Example: bash scripts/cron-tools.sh test watchdog-status.sh"
        return
    fi
    local script="/home/joel/autonomous-ai/scripts/$2"
    if [ ! -f "$script" ]; then
        echo -e "${RED}Script not found: $script${NC}"
        return
    fi
    echo -e "${BOLD}Test-running: $2${NC}"
    echo "────────────────────────────────────"
    local start=$(date +%s%N)
    if [[ "$2" == *.py ]]; then
        /usr/bin/python3 "$script" 2>&1 | tail -20
    else
        bash "$script" 2>&1 | tail -20
    fi
    local exit_code=$?
    local end=$(date +%s%N)
    local duration=$(( (end - start) / 1000000 ))
    echo "────────────────────────────────────"
    if [ "$exit_code" -eq 0 ]; then
        echo -e "${GREEN}Exit: 0 (success)${NC} | Time: ${duration}ms"
    else
        echo -e "${RED}Exit: $exit_code (error)${NC} | Time: ${duration}ms"
    fi
}

cmd_next() {
    if [ -z "$2" ]; then
        echo "Usage: bash scripts/cron-tools.sh next '<cron-expression>'"
        echo ""
        echo "Examples:"
        echo "  bash scripts/cron-tools.sh next '*/5 * * * *'"
        echo "  bash scripts/cron-tools.sh next '0 7 * * *'"
        echo "  bash scripts/cron-tools.sh next '30 */2 * * *'"
        return
    fi
    # Parse cron expression and calculate next fire time
    local expr="$2"
    local min_f=$(echo "$expr" | awk '{print $1}')
    local hr_f=$(echo "$expr" | awk '{print $2}')

    echo -e "${BOLD}Cron expression:${NC} $expr"
    echo -e "${BOLD}Human-readable:${NC} $(human_schedule "$expr")"
    echo -e "${BOLD}Current time:${NC}    $(date '+%H:%M:%S %Z (%Y-%m-%d)')"
    echo ""

    # Show next 5 occurrences using python for accuracy
    python3 -c "
from datetime import datetime, timedelta
import re

expr = '$expr'
parts = expr.split()
if len(parts) != 5:
    print('Invalid expression. Need 5 fields: min hour dom month dow')
    exit()

def matches(val, field):
    if field == '*':
        return True
    if '/' in field:
        if field.startswith('*/'):
            step = int(field[2:])
            return val % step == 0
        base, step = field.split('/')
        return (val - int(base)) % int(step) == 0 and val >= int(base)
    if ',' in field:
        return val in [int(x) for x in field.split(',')]
    if '-' in field:
        lo, hi = field.split('-')
        return int(lo) <= val <= int(hi)
    return val == int(field)

now = datetime.now()
t = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
found = 0
for _ in range(60*24*7):  # scan up to a week
    if (matches(t.minute, parts[0]) and
        matches(t.hour, parts[1]) and
        matches(t.day, parts[2]) and
        matches(t.month, parts[3]) and
        matches(t.weekday(), parts[4].replace('7','0'))):
        delta = t - now
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            when = f'in {mins} minutes'
        elif mins < 1440:
            when = f'in {mins//60}h {mins%60}m'
        else:
            when = f'in {mins//1440}d {(mins%1440)//60}h'
        print(f'  {t.strftime(\"%a %b %d %H:%M\")}  ({when})')
        found += 1
        if found >= 5:
            break
    t += timedelta(minutes=1)
" 2>&1
}

cmd_add() {
    echo -e "${BOLD}Add a New Cron Job (Guided)${NC}"
    echo ""
    echo "Step 1: Choose a schedule"
    echo ""
    echo "  1) Every 5 minutes       */5 * * * *"
    echo "  2) Every 10 minutes      */10 * * * *"
    echo "  3) Every 30 minutes      */30 * * * *"
    echo "  4) Every hour            0 * * * *"
    echo "  5) Every 2 hours         0 */2 * * *"
    echo "  6) Daily at 7 AM         0 7 * * *"
    echo "  7) Daily at midnight     0 0 * * *"
    echo "  8) Custom (you type it)"
    echo ""
    read -p "Pick a number (1-8): " choice

    case "$choice" in
        1) sched="*/5 * * * *" ;;
        2) sched="*/10 * * * *" ;;
        3) sched="*/30 * * * *" ;;
        4) sched="0 * * * *" ;;
        5) sched="0 */2 * * *" ;;
        6) sched="0 7 * * *" ;;
        7) sched="0 0 * * *" ;;
        8) read -p "Enter cron expression (5 fields): " sched ;;
        *) echo "Invalid choice."; return ;;
    esac

    echo ""
    read -p "Step 2: Script path (e.g. scripts/my-script.sh): " script_path
    local full_path="/home/joel/autonomous-ai/$script_path"
    if [ ! -f "$full_path" ]; then
        echo -e "${YELLOW}Warning: $full_path doesn't exist yet. Create it first.${NC}"
    fi

    local script_name=$(basename "$script_path" | sed 's/\.[^.]*$//')
    local logfile="/home/joel/autonomous-ai/logs/${script_name}.log"

    echo ""
    echo -e "${BOLD}This is what will be added to your crontab:${NC}"
    echo ""
    local cmd_prefix="/usr/bin/python3"
    [[ "$script_path" == *.sh ]] && cmd_prefix="/bin/bash"
    local cronline="$sched $cmd_prefix $full_path >> $logfile 2>&1"
    echo "  $cronline"
    echo ""
    echo -e "  Schedule: $(human_schedule "$sched")"
    echo ""
    read -p "Add this to crontab? (y/n): " confirm
    if [[ "$confirm" == [yY]* ]]; then
        (crontab -l 2>/dev/null; echo ""; echo "# ── $(echo "$script_name" | tr '[:lower:]' '[:upper:]') ──"; echo "$cronline") | crontab -
        echo -e "${GREEN}Added. Verify with: crontab -l | tail -3${NC}"
    else
        echo "Cancelled."
    fi
}

# Dispatch
case "${1:-help}" in
    status)  cmd_status ;;
    logs)    cmd_logs "$@" ;;
    health)  cmd_health ;;
    running) cmd_running ;;
    test)    cmd_test "$@" ;;
    next)    cmd_next "$@" ;;
    add)     cmd_add ;;
    help|*)  show_help ;;
esac
