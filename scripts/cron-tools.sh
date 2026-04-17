#!/bin/bash
# cron-tools.sh — Interactive cron management + learning tool for Joel
# Usage: bash scripts/cron-tools.sh [command]
# Commands: status, logs, test, add, next, health, running, quiz, explain

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
    echo -e "  ${YELLOW}LEARNING:${NC}"
    echo -e "  ${CYAN}tutorial${NC}   Progressive lessons — start here if you're new"
    echo -e "  ${CYAN}quiz${NC}       Practice reading cron expressions (interactive quiz)"
    echo -e "  ${CYAN}drill${NC}      Write cron expressions from descriptions (harder)"
    echo -e "  ${CYAN}build${NC}      Build a cron expression step by step (guided)"
    echo -e "  ${CYAN}explain${NC}    Explain any cron expression in plain English"
    echo -e "  ${CYAN}cheatsheet${NC} Quick reference card for cron syntax"
    echo -e "  ${CYAN}timeline${NC}   See WHEN an expression fires across 24 hours (visual)"
    echo -e "  ${CYAN}my-jobs${NC}    Quiz yourself on YOUR actual crontab entries"
    echo -e "  ${CYAN}detective${NC}  Find the error in broken cron expressions"
    echo -e "  ${CYAN}scenarios${NC}  Real-world sysadmin problems — build the solution"
    echo -e "  ${CYAN}review${NC}     Smart review — re-tests your weak spots"
    echo -e "  ${CYAN}scores${NC}     See your learning progress over time"
    echo ""
    echo -e "  Example: ${BOLD}bash scripts/cron-tools.sh status${NC}"
    echo -e "  Example: ${BOLD}bash scripts/cron-tools.sh quiz${NC}"
    echo -e "  Example: ${BOLD}bash scripts/cron-tools.sh explain '30 */2 * * 1-5'${NC}"
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

cmd_explain() {
    if [ -z "$2" ]; then
        echo "Usage: bash scripts/cron-tools.sh explain '<cron-expression>'"
        echo ""
        echo "Examples:"
        echo "  bash scripts/cron-tools.sh explain '*/5 * * * *'"
        echo "  bash scripts/cron-tools.sh explain '30 */2 * * 1-5'"
        echo "  bash scripts/cron-tools.sh explain '0 7 * * *'"
        return
    fi

    python3 -c "
expr = '$2'
parts = expr.split()
if len(parts) != 5:
    print('Need exactly 5 fields: minute hour day-of-month month day-of-week')
    exit()

fields = ['minute', 'hour', 'day of month', 'month', 'day of week']
explanations = []

for i, (part, name) in enumerate(zip(parts, fields)):
    if part == '*':
        explanations.append(f'  {name}: every {name}')
    elif part.startswith('*/'):
        step = part[2:]
        unit = name
        if name == 'minute': unit = 'minutes'
        elif name == 'hour': unit = 'hours'
        explanations.append(f'  {name}: every {step} {unit}')
    elif ',' in part:
        vals = part.split(',')
        explanations.append(f'  {name}: at {name}(s) {\", \".join(vals)}')
    elif '-' in part and '/' not in part:
        lo, hi = part.split('-')
        explanations.append(f'  {name}: from {lo} through {hi}')
    elif '-' in part and '/' in part:
        range_part, step = part.split('/')
        lo, hi = range_part.split('-')
        explanations.append(f'  {name}: every {step}, from {lo} through {hi}')
    else:
        if name == 'day of week':
            days = {'0':'Sunday','1':'Monday','2':'Tuesday','3':'Wednesday','4':'Thursday','5':'Friday','6':'Saturday','7':'Sunday'}
            val = days.get(part, part)
            explanations.append(f'  {name}: {val}')
        elif name == 'month':
            months = {'1':'January','2':'February','3':'March','4':'April','5':'May','6':'June','7':'July','8':'August','9':'September','10':'October','11':'November','12':'December'}
            val = months.get(part, part)
            explanations.append(f'  {name}: {val}')
        else:
            explanations.append(f'  {name}: at exactly {part}')

# Build summary
min_p, hr_p, dom_p, mon_p, dow_p = parts
summary = ''
if min_p.startswith('*/'):
    summary = f'Every {min_p[2:]} minutes'
elif hr_p.startswith('*/'):
    summary = f'At minute {min_p}, every {hr_p[2:]} hours'
elif min_p != '*' and hr_p != '*' and dom_p == '*' and mon_p == '*':
    if dow_p == '*':
        summary = f'Daily at {hr_p.zfill(2)}:{min_p.zfill(2)}'
    elif '-' in dow_p:
        lo, hi = dow_p.split('-')
        days = {'0':'Sun','1':'Mon','2':'Tue','3':'Wed','4':'Thu','5':'Fri','6':'Sat'}
        summary = f'At {hr_p.zfill(2)}:{min_p.zfill(2)}, {days.get(lo,lo)}-{days.get(hi,hi)}'
    else:
        days = {'0':'Sunday','1':'Monday','2':'Tuesday','3':'Wednesday','4':'Thursday','5':'Friday','6':'Saturday'}
        summary = f'At {hr_p.zfill(2)}:{min_p.zfill(2)} on {days.get(dow_p, dow_p)}'
elif min_p == '*' and hr_p == '*':
    summary = 'Every minute'
else:
    summary = 'Custom schedule'

print(f'\033[1mExpression:\033[0m {expr}')
print(f'\033[1mSummary:\033[0m    {summary}')
print()
print('\033[1mField breakdown:\033[0m')
for e in explanations:
    print(e)
print()
print('\033[1mField reference:\033[0m')
print('  ┌───── minute (0-59)')
print('  │ ┌───── hour (0-23)')
print('  │ │ ┌───── day of month (1-31)')
print('  │ │ │ ┌───── month (1-12)')
print('  │ │ │ │ ┌───── day of week (0-7, 0=Sun)')
print('  │ │ │ │ │')
print(f'  {\" \".join(parts)}')
" 2>&1
}

cmd_quiz() {
    echo -e "${BOLD}Cron Expression Quiz${NC}"
    echo -e "Read the expression, guess what it means. Learn by doing."
    echo ""

    python3 -c "
import random

questions = [
    {
        'expr': '*/5 * * * *',
        'answer': 'Every 5 minutes',
        'hint': 'The */ means \"every N\" — look at the first field (minutes)',
    },
    {
        'expr': '0 7 * * *',
        'answer': 'Daily at 7:00 AM',
        'hint': 'Minute 0, hour 7, every day/month/weekday = once a day at 7 AM',
    },
    {
        'expr': '30 */2 * * *',
        'answer': 'At minute 30, every 2 hours',
        'hint': 'Minute 30, every 2nd hour. So 0:30, 2:30, 4:30, ...',
    },
    {
        'expr': '0 0 * * *',
        'answer': 'Daily at midnight',
        'hint': 'Minute 0, hour 0 = midnight. Every day.',
    },
    {
        'expr': '*/10 * * * *',
        'answer': 'Every 10 minutes',
        'hint': '*/10 in the minute field = at 0, 10, 20, 30, 40, 50',
    },
    {
        'expr': '0 9 * * 1-5',
        'answer': 'Weekdays at 9:00 AM',
        'hint': '1-5 in day-of-week = Monday through Friday',
    },
    {
        'expr': '0 3 * * *',
        'answer': 'Daily at 3:00 AM',
        'hint': 'Minute 0, hour 3. Good time for maintenance scripts.',
    },
    {
        'expr': '15,45 * * * *',
        'answer': 'At minute 15 and 45 of every hour',
        'hint': 'Comma = list of specific values. Runs twice per hour.',
    },
    {
        'expr': '0 */6 * * *',
        'answer': 'Every 6 hours (at minute 0)',
        'hint': '*/6 in the hour field = at 0, 6, 12, 18',
    },
    {
        'expr': '0 7 1 * *',
        'answer': '7:00 AM on the 1st of every month',
        'hint': 'Day-of-month is 1. Combined with hour 7, minute 0.',
    },
    {
        'expr': '*/3 * * * *',
        'answer': 'Every 3 minutes',
        'hint': 'This is one of your actual crontab lines (heartbeat touch)',
    },
    {
        'expr': '0 5 * * *',
        'answer': 'Daily at 5:00 AM',
        'hint': 'The system runs daily-git-audit.py at this time.',
    },
]

random.shuffle(questions)
score = 0
total = min(5, len(questions))  # 5 questions per round

print(f'5 questions. Type your answer or press Enter for a hint.\n')

for i, q in enumerate(questions[:total]):
    print(f'\033[1mQuestion {i+1}/5:\033[0m  What does this run?')
    print(f'  \033[36m{q[\"expr\"]}\033[0m')
    print()

    guess = input('  Your answer: ').strip()

    if not guess:
        print(f'  \033[33mHint:\033[0m {q[\"hint\"]}')
        guess = input('  Try again: ').strip()

    # Flexible matching — check for key words
    answer_lower = q['answer'].lower()
    guess_lower = guess.lower()

    key_words = [w for w in answer_lower.split() if len(w) > 2 and w not in ('at', 'the', 'every', 'and', 'of')]
    matches = sum(1 for w in key_words if w in guess_lower)

    if matches >= len(key_words) * 0.5 or guess_lower in answer_lower or answer_lower in guess_lower:
        print(f'  \033[32mCorrect!\033[0m {q[\"answer\"]}')
        score += 1
    else:
        print(f'  \033[31mNot quite.\033[0m The answer: {q[\"answer\"]}')
        print(f'  \033[33mExplanation:\033[0m {q[\"hint\"]}')

    print()

print(f'\033[1mScore: {score}/{total}\033[0m')
if score == total:
    print('\033[32mPerfect! You know your cron.\033[0m')
elif score >= total * 0.6:
    print('\033[33mGetting there. Run it again to practice.\033[0m')
else:
    print('\033[36mKeep practicing. Try: bash scripts/cron-tools.sh explain \"*/5 * * * *\"\033[0m')

# Save score
import os, json
from datetime import datetime
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
os.makedirs(os.path.dirname(scores_file), exist_ok=True)
scores_data = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores_data = json.load(f)
    except: pass
scores_data.append({'date': datetime.now().isoformat(), 'type': 'quiz', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores_data, f, indent=2)
" 2>&1
}

cmd_drill() {
    echo -e "${BOLD}Cron Expression Drill${NC}"
    echo -e "I describe a schedule. You write the cron expression."
    echo -e "This is harder than the quiz — you're building, not reading."
    echo ""

    python3 -c "
import random

drills = [
    {
        'desc': 'Run every 5 minutes, all day, every day',
        'answer': '*/5 * * * *',
        'accept': ['*/5 * * * *'],
        'tip': '*/5 in the minute field. Everything else is * (any).',
    },
    {
        'desc': 'Run once a day at 7:00 AM',
        'answer': '0 7 * * *',
        'accept': ['0 7 * * *'],
        'tip': 'Minute 0, hour 7. Day/month/weekday all * for every day.',
    },
    {
        'desc': 'Run at midnight every day',
        'answer': '0 0 * * *',
        'accept': ['0 0 * * *'],
        'tip': 'Both minute and hour are 0.',
    },
    {
        'desc': 'Run every 10 minutes',
        'answer': '*/10 * * * *',
        'accept': ['*/10 * * * *'],
        'tip': 'Same pattern as every 5, just change the number.',
    },
    {
        'desc': 'Run at 9:00 AM, Monday through Friday only',
        'answer': '0 9 * * 1-5',
        'accept': ['0 9 * * 1-5', '0 9 * * MON-FRI'],
        'tip': 'Day-of-week field: 1=Mon, 5=Fri. Use a dash for ranges.',
    },
    {
        'desc': 'Run every 2 hours, at minute 0',
        'answer': '0 */2 * * *',
        'accept': ['0 */2 * * *'],
        'tip': 'Minute 0, then */2 in the hour field.',
    },
    {
        'desc': 'Run at 7:00 AM on the first day of every month',
        'answer': '0 7 1 * *',
        'accept': ['0 7 1 * *'],
        'tip': 'Day-of-month field is the third field. Set it to 1.',
    },
    {
        'desc': 'Run every 30 minutes',
        'answer': '*/30 * * * *',
        'accept': ['*/30 * * * *', '0,30 * * * *'],
        'tip': '*/30 or 0,30 both work. They fire at :00 and :30.',
    },
    {
        'desc': 'Run at 3:30 AM every day',
        'answer': '30 3 * * *',
        'accept': ['30 3 * * *'],
        'tip': 'Minute 30, hour 3. Rest is *.',
    },
    {
        'desc': 'Run every 6 hours at the top of the hour',
        'answer': '0 */6 * * *',
        'accept': ['0 */6 * * *', '0 0,6,12,18 * * *'],
        'tip': 'Minute 0, hour */6. Fires at 0, 6, 12, 18.',
    },
    {
        'desc': 'Run at minutes 15 and 45 of every hour',
        'answer': '15,45 * * * *',
        'accept': ['15,45 * * * *'],
        'tip': 'Use a comma to list specific values in any field.',
    },
    {
        'desc': 'Run every minute (the most frequent possible)',
        'answer': '* * * * *',
        'accept': ['* * * * *'],
        'tip': 'All stars. Every field matches everything.',
    },
]

random.shuffle(drills)
score = 0
total = min(5, len(drills))

print(f'5 challenges. Write the cron expression for each description.\n')

for i, d in enumerate(drills[:total]):
    print(f'\033[1mChallenge {i+1}/5:\033[0m')
    print(f'  \033[33m{d[\"desc\"]}\033[0m')
    print()

    guess = input('  Your expression: ').strip()

    if guess in d['accept']:
        print(f'  \033[32mPerfect!\033[0m {d[\"answer\"]}')
        score += 1
    elif guess.replace('  ', ' ') in d['accept']:
        print(f'  \033[32mCorrect!\033[0m (watch spacing) {d[\"answer\"]}')
        score += 1
    else:
        print(f'  \033[31mNot quite.\033[0m The answer: {d[\"answer\"]}')
        print(f'  \033[36mTip:\033[0m {d[\"tip\"]}')

    print()

print(f'\033[1mScore: {score}/{total}\033[0m')
if score == total:
    print('\033[32mYou can write cron expressions from scratch. Solid.\033[0m')
elif score >= total * 0.6:
    print('\033[33mGood progress. The patterns will click with more practice.\033[0m')
else:
    print('\033[36mTry the quiz first to build recognition, then come back to drill.\033[0m')

# Save score
import os, json
from datetime import datetime
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
os.makedirs(os.path.dirname(scores_file), exist_ok=True)
scores_data = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores_data = json.load(f)
    except: pass
scores_data.append({'date': datetime.now().isoformat(), 'type': 'drill', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores_data, f, indent=2)
" 2>&1
}

cmd_build() {
    echo -e "${BOLD}Build a Cron Expression${NC}"
    echo -e "Answer each question to construct your cron line."
    echo ""

    python3 -c "
# Interactive cron expression builder
fields = ['*', '*', '*', '*', '*']
names = ['MINUTE', 'HOUR', 'DAY OF MONTH', 'MONTH', 'DAY OF WEEK']

print('\033[1mStep 1: How often should it run?\033[0m')
print()
print('  1) Every N minutes (e.g., every 5 min)')
print('  2) Every N hours')
print('  3) Once a day at a specific time')
print('  4) On specific days of the week')
print('  5) On a specific day of the month')
print('  6) Custom (set each field manually)')
print()

choice = input('  Pick (1-6): ').strip()

if choice == '1':
    n = input('  Every how many minutes? ').strip()
    fields[0] = f'*/{n}'

elif choice == '2':
    n = input('  Every how many hours? ').strip()
    m = input('  At which minute of the hour? (0-59, default 0): ').strip() or '0'
    fields[0] = m
    fields[1] = f'*/{n}'

elif choice == '3':
    h = input('  What hour? (0-23, e.g., 7 for 7 AM, 14 for 2 PM): ').strip()
    m = input('  What minute? (0-59, default 0): ').strip() or '0'
    fields[0] = m
    fields[1] = h

elif choice == '4':
    h = input('  What hour? (0-23): ').strip()
    m = input('  What minute? (0-59, default 0): ').strip() or '0'
    print('  Which days? (0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat)')
    print('  Use: single (1), range (1-5), or list (1,3,5)')
    d = input('  Days: ').strip()
    fields[0] = m
    fields[1] = h
    fields[4] = d

elif choice == '5':
    h = input('  What hour? (0-23): ').strip()
    m = input('  What minute? (0-59, default 0): ').strip() or '0'
    d = input('  Which day of month? (1-31): ').strip()
    fields[0] = m
    fields[1] = h
    fields[2] = d

elif choice == '6':
    print()
    print('  Set each field. Use * for any, */N for every N, N-M for range, N,M for list.')
    print()
    for i, name in enumerate(names):
        val = input(f'  {name}: ').strip()
        if val:
            fields[i] = val

expr = ' '.join(fields)
print()
print(f'\033[1mYour cron expression:\033[0m')
print(f'  \033[36m{expr}\033[0m')
print()
print('\033[1mField map:\033[0m')
print('  ┌───── minute (0-59)')
print('  │ ┌───── hour (0-23)')
print('  │ │ ┌───── day of month (1-31)')
print('  │ │ │ ┌───── month (1-12)')
print('  │ │ │ │ ┌───── day of week (0-7)')
print('  │ │ │ │ │')
print(f'  {expr}')
print()
print(f'To add this to your crontab:')
print(f'  bash scripts/cron-tools.sh add')
print(f'  (then pick option 8 and paste: {expr})')
" 2>&1
}

cmd_cheatsheet() {
    echo -e "${BOLD}Cron Expression Cheatsheet${NC}"
    echo ""
    echo -e "${BOLD}The 5 Fields:${NC}"
    echo "  ┌───── minute        (0-59)"
    echo "  │ ┌───── hour          (0-23)"
    echo "  │ │ ┌───── day of month (1-31)"
    echo "  │ │ │ ┌───── month       (1-12)"
    echo "  │ │ │ │ ┌───── day of week (0-7, 0 and 7 = Sunday)"
    echo "  │ │ │ │ │"
    echo "  * * * * *"
    echo ""
    echo -e "${BOLD}Special Characters:${NC}"
    echo "  *       any value"
    echo "  */N     every N (e.g., */5 = every 5)"
    echo "  N,M     list (e.g., 1,15 = at 1 and 15)"
    echo "  N-M     range (e.g., 1-5 = 1 through 5)"
    echo "  N-M/S   range with step (e.g., 0-30/10 = 0,10,20,30)"
    echo ""
    echo -e "${BOLD}Common Patterns:${NC}"
    printf "  %-25s %s\n" "* * * * *"          "every minute"
    printf "  %-25s %s\n" "*/5 * * * *"        "every 5 minutes"
    printf "  %-25s %s\n" "*/10 * * * *"       "every 10 minutes"
    printf "  %-25s %s\n" "*/30 * * * *"       "every 30 minutes"
    printf "  %-25s %s\n" "0 * * * *"          "every hour (at :00)"
    printf "  %-25s %s\n" "0 */2 * * *"        "every 2 hours"
    printf "  %-25s %s\n" "0 */6 * * *"        "every 6 hours"
    printf "  %-25s %s\n" "0 0 * * *"          "daily at midnight"
    printf "  %-25s %s\n" "0 7 * * *"          "daily at 7:00 AM"
    printf "  %-25s %s\n" "30 14 * * *"        "daily at 2:30 PM"
    printf "  %-25s %s\n" "0 9 * * 1-5"        "weekdays at 9:00 AM"
    printf "  %-25s %s\n" "0 9 * * 0,6"        "weekends at 9:00 AM"
    printf "  %-25s %s\n" "0 7 1 * *"          "1st of month at 7 AM"
    printf "  %-25s %s\n" "0 0 1 1 *"          "midnight, January 1st"
    printf "  %-25s %s\n" "15,45 * * * *"      "twice per hour (:15, :45)"
    echo ""
    echo -e "${BOLD}Day of Week Numbers:${NC}"
    echo "  0 = Sunday    1 = Monday    2 = Tuesday   3 = Wednesday"
    echo "  4 = Thursday  5 = Friday    6 = Saturday  7 = Sunday (alt)"
    echo ""
    echo -e "${BOLD}Month Numbers:${NC}"
    echo "  1 = Jan   2 = Feb   3 = Mar    4 = Apr    5 = May    6 = Jun"
    echo "  7 = Jul   8 = Aug   9 = Sep   10 = Oct   11 = Nov   12 = Dec"
    echo ""
    echo -e "${BOLD}Your System:${NC}"
    echo "  Logs go to:    /home/joel/autonomous-ai/logs/<name>.log"
    echo "  Edit crontab:  crontab -e"
    echo "  View crontab:  crontab -l"
    echo "  Add a job:     bash scripts/cron-tools.sh add"
    echo ""
    echo -e "${BOLD}Pro Tips:${NC}"
    echo "  - Redirect output: >> logfile.log 2>&1"
    echo "  - Use full paths (/usr/bin/python3, not just python3)"
    echo "  - Test first: bash scripts/cron-tools.sh test <script>"
    echo "  - Cron has no shell profile — set PATH or use full paths"
    echo "  - Cron uses the system timezone (check with: date)"
}

cmd_myjobs() {
    echo -e "${BOLD}Your Crontab Quiz${NC}"
    echo -e "These are YOUR actual jobs. Do you know what each one does?"
    echo ""

    python3 -c "
import subprocess, random, re

# Parse the actual crontab
result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
jobs = []
lines = result.stdout.strip().split('\n')
for i, line in enumerate(lines):
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('$'):
        continue
    # Get the comment from the line above (if any)
    comment = ''
    if i > 0 and lines[i-1].strip().startswith('#'):
        comment = lines[i-1].strip().lstrip('# ').strip()
    # Extract schedule and script
    if line.startswith('@reboot'):
        sched = '@reboot'
        script_match = re.search(r'([\w-]+\.(sh|py))', line)
        script = script_match.group(1) if script_match else 'boot-script'
    else:
        parts = line.split()
        if len(parts) < 6:
            continue
        sched = ' '.join(parts[:5])
        script_match = re.search(r'([\w-]+\.(sh|py))', line)
        script = script_match.group(1) if script_match else 'unknown'

    if comment and 'DISABLED' not in comment:
        jobs.append({'sched': sched, 'script': script, 'purpose': comment})

if len(jobs) < 3:
    print('Not enough annotated jobs to quiz on.')
    exit()

random.shuffle(jobs)
score = 0
total = min(5, len(jobs))

print(f'{total} questions about your own crontab.\n')

for i, job in enumerate(jobs[:total]):
    mode = random.choice(['schedule', 'purpose'])

    if mode == 'schedule':
        print(f'\033[1mQuestion {i+1}/{total}:\033[0m')
        print(f'  Script: \033[36m{job[\"script\"]}\033[0m')
        print(f'  Purpose: {job[\"purpose\"]}')
        print(f'  What is its cron schedule?')
        print()
        guess = input('  Your answer: ').strip()

        if guess == job['sched']:
            print(f'  \033[32mExact match!\033[0m')
            score += 1
        elif guess.replace('  ', ' ') == job['sched']:
            print(f'  \033[32mCorrect!\033[0m (minor spacing)')
            score += 1
        else:
            print(f'  \033[31mActual schedule:\033[0m {job[\"sched\"]}')
            # Explain what the schedule means
            sched = job['sched']
            if sched.startswith('*/'):
                n = sched.split()[0][2:]
                print(f'  \033[33mThat means:\033[0m every {n} minutes')
            elif sched.startswith('@reboot'):
                print(f'  \033[33mThat means:\033[0m runs once when the server boots')
            elif sched.split()[0] not in ['*'] and sched.split()[1] not in ['*']:
                hr = sched.split()[1]
                mn = sched.split()[0]
                print(f'  \033[33mThat means:\033[0m at {hr}:{mn.zfill(2)}')
    else:
        print(f'\033[1mQuestion {i+1}/{total}:\033[0m')
        print(f'  Schedule: \033[36m{job[\"sched\"]}\033[0m')
        print(f'  Script: \033[36m{job[\"script\"]}\033[0m')
        print(f'  What does this job do?')
        print()
        guess = input('  Your answer: ').strip()

        # Check if key words match
        purpose_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', job['purpose']) if len(w) > 3)
        guess_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', guess) if len(w) > 3)
        overlap = purpose_words & guess_words

        if len(overlap) >= 2 or (len(purpose_words) <= 3 and len(overlap) >= 1):
            print(f'  \033[32mGot it!\033[0m {job[\"purpose\"]}')
            score += 1
        else:
            print(f'  \033[31mActual purpose:\033[0m {job[\"purpose\"]}')

    print()

print(f'\033[1mScore: {score}/{total}\033[0m')
if score == total:
    print('\033[32mYou know your own system inside and out.\033[0m')
elif score >= total * 0.6:
    print('\033[33mGood — you know most of your jobs. Run it again to nail the rest.\033[0m')
else:
    print('\033[36mTry: bash scripts/cron-tools.sh status (to see them all laid out)\033[0m')

# Save score
import os, json
from datetime import datetime
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
os.makedirs(os.path.dirname(scores_file), exist_ok=True)
scores = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores = json.load(f)
    except: pass
scores.append({'date': datetime.now().isoformat(), 'type': 'my-jobs', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores, f, indent=2)
" 2>&1
}

cmd_detective() {
    echo -e "${BOLD}Cron Detective${NC}"
    echo -e "Each expression has an error. Find it and fix it."
    echo ""

    python3 -c "
import random, os, json
from datetime import datetime

cases = [
    {
        'broken': '60 * * * *',
        'error': 'Minute field is 60 — valid range is 0-59',
        'fix': '0 * * * *',
        'tip': 'Minutes go from 0 to 59. 60 would be the next hour.',
    },
    {
        'broken': '* * * * * *',
        'error': 'Too many fields — cron needs exactly 5, this has 6',
        'fix': '* * * * *',
        'tip': 'The 5 fields are: minute, hour, day-of-month, month, day-of-week.',
    },
    {
        'broken': '0 25 * * *',
        'error': 'Hour field is 25 — valid range is 0-23',
        'fix': '0 23 * * *',
        'tip': 'Hours use 24-hour format: 0 is midnight, 23 is 11 PM.',
    },
    {
        'broken': '*/5 * * * * /usr/bin/python3 script.py',
        'error': 'Script path is inside the expression — crontab separates them with a space, but you don\'t put both in one field',
        'fix': '*/5 * * * *',
        'tip': 'The cron expression is just the first 5 fields. The command comes after, separated by space.',
    },
    {
        'broken': '0 7 * * 8',
        'error': 'Day-of-week is 8 — valid range is 0-7 (0 and 7 are both Sunday)',
        'fix': '0 7 * * 1',
        'tip': 'Day-of-week: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun.',
    },
    {
        'broken': '0 7 32 * *',
        'error': 'Day-of-month is 32 — no month has 32 days',
        'fix': '0 7 31 * *',
        'tip': 'Day-of-month range: 1-31. But be careful — months like February have fewer.',
    },
    {
        'broken': '*/0 * * * *',
        'error': 'Step value is 0 — */0 means divide by zero, which is invalid',
        'fix': '* * * * *',
        'tip': 'Step values must be 1 or greater. */1 is the same as *.',
    },
    {
        'broken': '5 7 * 13 *',
        'error': 'Month field is 13 — valid range is 1-12',
        'fix': '5 7 * 12 *',
        'tip': 'Months: 1=Jan through 12=Dec. There is no month 13.',
    },
    {
        'broken': '0 7 * * monday',
        'error': 'Day-of-week uses numbers (0-7), not words, in standard cron',
        'fix': '0 7 * * 1',
        'tip': 'Some systems accept MON-FRI, but standard cron uses numbers. 1=Monday.',
    },
    {
        'broken': '*/5 */2',
        'error': 'Only 2 fields — cron needs exactly 5',
        'fix': '*/5 */2 * * *',
        'tip': 'Always specify all 5 fields. Missing fields don\'t default to *.',
    },
]

random.shuffle(cases)
score = 0
total = min(5, len(cases))

print(f'5 broken expressions. Find the error in each.\n')

for i, case in enumerate(cases[:total]):
    print(f'\033[1mCase {i+1}/{total}:\033[0m')
    print(f'  \033[31m{case[\"broken\"]}\033[0m')
    print()
    guess = input('  What\'s wrong? ').strip()

    # Check if they identified the key issue
    error_keywords = set(w.lower() for w in case['error'].split() if len(w) > 3 and w.lower() not in ('this', 'that', 'with', 'from'))
    guess_keywords = set(w.lower() for w in guess.split() if len(w) > 3)
    overlap = error_keywords & guess_keywords

    # Also check for number mentions
    import re
    error_nums = set(re.findall(r'\d+', case['error']))
    guess_nums = set(re.findall(r'\d+', guess))
    num_overlap = error_nums & guess_nums

    if len(overlap) >= 2 or len(num_overlap) >= 1 or any(k in guess.lower() for k in ['range', 'invalid', 'too many', 'too few', 'field', 'missing']):
        print(f'  \033[32mGood eye!\033[0m {case[\"error\"]}')
        print(f'  \033[36mFixed:\033[0m {case[\"fix\"]}')
        score += 1
    else:
        print(f'  \033[31mThe error:\033[0m {case[\"error\"]}')
        print(f'  \033[36mFixed:\033[0m {case[\"fix\"]}')
        print(f'  \033[33mTip:\033[0m {case[\"tip\"]}')

    print()

print(f'\033[1mScore: {score}/{total}\033[0m')
if score == total:
    print('\033[32mSharp. You can spot cron bugs on sight.\033[0m')
elif score >= total * 0.6:
    print('\033[33mGetting there — you catch the obvious ones.\033[0m')
else:
    print('\033[36mReview: bash scripts/cron-tools.sh cheatsheet\033[0m')

# Save score
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
os.makedirs(os.path.dirname(scores_file), exist_ok=True)
scores = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores = json.load(f)
    except: pass
scores.append({'date': datetime.now().isoformat(), 'type': 'detective', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores, f, indent=2)
" 2>&1
}

cmd_scenarios() {
    echo -e "${BOLD}Sysadmin Scenarios${NC}"
    echo -e "Real problems. Build the full cron line to solve them."
    echo ""

    python3 -c "
import random, os, json, re
from datetime import datetime

scenarios = [
    {
        'problem': 'Your backup script (scripts/backup.sh) needs to run every night at 3 AM and log to logs/backup.log.',
        'answer': '0 3 * * * /bin/bash /home/joel/autonomous-ai/scripts/backup.sh >> /home/joel/autonomous-ai/logs/backup.log 2>&1',
        'check_parts': ['0 3 * * *', 'backup.sh', 'backup.log', '2>&1'],
        'tip': 'Daily at 3 AM = minute 0, hour 3. Always redirect both stdout and stderr (2>&1).',
    },
    {
        'problem': 'You want a health check (scripts/health.py) every 15 minutes. It should log to logs/health.log.',
        'answer': '*/15 * * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/health.py >> /home/joel/autonomous-ai/logs/health.log 2>&1',
        'check_parts': ['*/15 * * * *', 'health.py', 'health.log'],
        'tip': 'Every 15 min = */15 in the minute field. Use /usr/bin/python3 (full path) for Python scripts.',
    },
    {
        'problem': 'A weekly report (scripts/report.py) should run every Monday at 8 AM. Log to logs/report.log.',
        'answer': '0 8 * * 1 /usr/bin/python3 /home/joel/autonomous-ai/scripts/report.py >> /home/joel/autonomous-ai/logs/report.log 2>&1',
        'check_parts': ['0 8 * * 1', 'report.py'],
        'tip': 'Monday = 1 in the day-of-week field (the 5th field). Minute 0, hour 8.',
    },
    {
        'problem': 'A disk cleanup script (scripts/cleanup.sh) should run twice a day — at 6 AM and 6 PM.',
        'answer': '0 6,18 * * * /bin/bash /home/joel/autonomous-ai/scripts/cleanup.sh >> /home/joel/autonomous-ai/logs/cleanup.log 2>&1',
        'check_parts': ['0 6,18 * * *', 'cleanup.sh'],
        'tip': 'Twice a day at specific hours = use a comma in the hour field: 6,18.',
    },
    {
        'problem': 'Run a sync script (scripts/sync.py) every 2 hours, on the hour, but only on weekdays.',
        'answer': '0 */2 * * 1-5 /usr/bin/python3 /home/joel/autonomous-ai/scripts/sync.py >> /home/joel/autonomous-ai/logs/sync.log 2>&1',
        'check_parts': ['0 */2 * * 1-5', 'sync.py'],
        'tip': 'Every 2 hours = */2 in hour field. Weekdays = 1-5 in day-of-week field.',
    },
    {
        'problem': 'A monthly billing script (scripts/billing.py) runs on the 1st of every month at midnight.',
        'answer': '0 0 1 * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/billing.py >> /home/joel/autonomous-ai/logs/billing.log 2>&1',
        'check_parts': ['0 0 1 * *', 'billing.py'],
        'tip': 'First of the month = 1 in the day-of-month field (3rd field). Midnight = hour 0, minute 0.',
    },
    {
        'problem': 'Your Eos agent should check the system at minutes 2, 22, and 42 of every hour. Script: scripts/eos-react.py.',
        'answer': '2,22,42 * * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/eos-react.py >> /home/joel/autonomous-ai/logs/eos-react.log 2>&1',
        'check_parts': ['2,22,42 * * * *', 'eos-react.py'],
        'tip': 'Specific minutes = comma-separated list: 2,22,42. This gives you 3 runs per hour, evenly spaced by 20 min.',
    },
    {
        'problem': 'You want a script to run at boot AND log the boot time. Script: scripts/startup.sh.',
        'answer': '@reboot sleep 30 && /home/joel/autonomous-ai/scripts/startup.sh >> /home/joel/autonomous-ai/logs/startup.log 2>&1',
        'check_parts': ['@reboot', 'startup.sh'],
        'tip': '@reboot runs once when cron starts (at boot). The sleep 30 gives services time to come up first.',
    },
]

random.shuffle(scenarios)
score = 0
total = min(4, len(scenarios))

print(f'{total} real-world problems. Write the full cron line.\n')

for i, s in enumerate(scenarios[:total]):
    print(f'\033[1mScenario {i+1}/{total}:\033[0m')
    print(f'  \033[33m{s[\"problem\"]}\033[0m')
    print()
    guess = input('  Your cron line: ').strip()

    # Check key parts
    matched = sum(1 for part in s['check_parts'] if part in guess)

    if matched >= len(s['check_parts']):
        print(f'  \033[32mPerfect!\033[0m All parts correct.')
        score += 1
    elif matched >= len(s['check_parts']) - 1:
        print(f'  \033[33mClose!\033[0m Got the schedule right but missing a piece.')
        print(f'  \033[36mFull answer:\033[0m {s[\"answer\"]}')
        score += 1
    else:
        print(f'  \033[31mNot quite.\033[0m')
        print(f'  \033[36mAnswer:\033[0m {s[\"answer\"]}')
        print(f'  \033[33mTip:\033[0m {s[\"tip\"]}')

    print()

print(f'\033[1mScore: {score}/{total}\033[0m')
if score == total:
    print('\033[32mYou can write real cron configs from scratch. That\'s sysadmin work.\033[0m')
elif score >= total * 0.5:
    print('\033[33mYou\'re getting the patterns. Practice makes permanent.\033[0m')
else:
    print('\033[36mStart with: bash scripts/cron-tools.sh build (to construct step by step)\033[0m')

# Save score
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
os.makedirs(os.path.dirname(scores_file), exist_ok=True)
scores = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores = json.load(f)
    except: pass
scores.append({'date': datetime.now().isoformat(), 'type': 'scenarios', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores, f, indent=2)
" 2>&1
}

cmd_scores() {
    echo -e "${BOLD}Learning Progress${NC}"
    echo ""

    python3 -c "
import json, os
from datetime import datetime

scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
if not os.path.exists(scores_file):
    print('No scores yet. Try:')
    print('  bash scripts/cron-tools.sh quiz')
    print('  bash scripts/cron-tools.sh drill')
    print('  bash scripts/cron-tools.sh my-jobs')
    print('  bash scripts/cron-tools.sh detective')
    print('  bash scripts/cron-tools.sh scenarios')
    exit()

with open(scores_file) as f:
    scores = json.load(f)

if not scores:
    print('No scores recorded yet.')
    exit()

# Summary by type
types = {}
for s in scores:
    t = s.get('type', 'unknown')
    if t not in types:
        types[t] = []
    types[t].append(s)

print(f'\033[1m{\"Category\":<15} {\"Sessions\":<10} {\"Best\":<8} {\"Average\":<10} {\"Latest\":<8}\033[0m')
print('─' * 55)

for t in sorted(types.keys()):
    entries = types[t]
    scores_list = [e['score']/e['total']*100 for e in entries if e.get('total', 0) > 0]
    if not scores_list:
        continue
    best = max(scores_list)
    avg = sum(scores_list) / len(scores_list)
    latest = scores_list[-1]

    # Color-code latest score
    if latest >= 80:
        color = '\033[32m'
    elif latest >= 50:
        color = '\033[33m'
    else:
        color = '\033[31m'

    print(f'{t:<15} {len(entries):<10} {best:>5.0f}%   {avg:>6.1f}%   {color}{latest:>5.0f}%\033[0m')

# Recent entries
print()
print('\033[1mRecent Sessions:\033[0m')
for s in scores[-8:]:
    date = datetime.fromisoformat(s['date']).strftime('%b %d %H:%M')
    pct = s['score']/s['total']*100 if s.get('total', 0) > 0 else 0
    bar_len = int(pct / 5)
    bar = '█' * bar_len + '░' * (20 - bar_len)

    if pct >= 80: color = '\033[32m'
    elif pct >= 50: color = '\033[33m'
    else: color = '\033[31m'

    print(f'  {date}  {s.get(\"type\",\"?\"):<12} {color}{bar} {s[\"score\"]}/{s[\"total\"]}\033[0m')

total_sessions = len(scores)
total_correct = sum(s.get('score', 0) for s in scores)
total_questions = sum(s.get('total', 0) for s in scores)
if total_questions > 0:
    print()
    print(f'\033[1mLifetime:\033[0m {total_sessions} sessions, {total_correct}/{total_questions} correct ({total_correct/total_questions*100:.0f}%)')
" 2>&1
}

cmd_tutorial() {
    echo -e "${BOLD}Cron Tutorial — Progressive Lessons${NC}"
    echo -e "Work through these in order. Each one builds on the last."
    echo ""

    python3 -c "
import os, json, sys

progress_file = '/home/joel/autonomous-ai/data/cron-tutorial-progress.json'
os.makedirs(os.path.dirname(progress_file), exist_ok=True)

progress = {}
if os.path.exists(progress_file):
    try:
        with open(progress_file) as f:
            progress = json.load(f)
    except: pass

lessons = [
    {
        'id': 1,
        'title': 'The Five Fields',
        'content': '''Every cron expression has exactly 5 fields, separated by spaces:

  \033[36mminute  hour  day-of-month  month  day-of-week\033[0m

  \033[1mRanges:\033[0m
    minute:       0-59
    hour:         0-23
    day-of-month: 1-31
    month:        1-12
    day-of-week:  0-7 (0 and 7 are both Sunday)

  The \033[36m*\033[0m character means \"every\" — it matches all values in that field.

  So \033[36m* * * * *\033[0m means: every minute of every hour of every day.

  And \033[36m0 7 * * *\033[0m means: minute 0, hour 7, every day = 7:00 AM daily.''',
        'questions': [
            {
                'q': 'How many fields does a cron expression have?',
                'a': '5',
                'check': lambda g: '5' in g or 'five' in g.lower(),
            },
            {
                'q': 'What is the valid range for the HOUR field?',
                'a': '0-23',
                'check': lambda g: '23' in g and '0' in g,
            },
            {
                'q': 'What does * mean in a cron field?',
                'a': 'every value / all values',
                'check': lambda g: any(w in g.lower() for w in ['every', 'all', 'any', 'wildcard', 'match']),
            },
        ],
    },
    {
        'id': 2,
        'title': 'Step Values (*/N)',
        'content': '''The \033[36m*/N\033[0m pattern means \"every Nth value\":

  \033[36m*/5 * * * *\033[0m  = every 5 minutes (at :00, :05, :10, :15, ...)
  \033[36m*/10 * * * *\033[0m = every 10 minutes (at :00, :10, :20, :30, ...)
  \033[36m*/30 * * * *\033[0m = every 30 minutes (at :00 and :30)

  Step values work in ANY field:
  \033[36m0 */2 * * *\033[0m  = at minute 0, every 2 hours (0:00, 2:00, 4:00, ...)
  \033[36m0 */6 * * *\033[0m  = at minute 0, every 6 hours (0:00, 6:00, 12:00, 18:00)

  Your server uses \033[36m*/3 * * * *\033[0m for the heartbeat — every 3 minutes.''',
        'questions': [
            {
                'q': 'What does */15 * * * * mean?',
                'a': 'Every 15 minutes',
                'check': lambda g: '15' in g and any(w in g.lower() for w in ['every', 'minut']),
            },
            {
                'q': 'How often does 0 */4 * * * run?',
                'a': 'Every 4 hours',
                'check': lambda g: '4' in g and any(w in g.lower() for w in ['hour', 'every']),
            },
            {
                'q': 'How many times per hour does */20 * * * * run?',
                'a': '3 (at :00, :20, :40)',
                'check': lambda g: '3' in g or 'three' in g.lower(),
            },
        ],
    },
    {
        'id': 3,
        'title': 'Ranges and Lists',
        'content': '''You can specify ranges with \033[36m-\033[0m and lists with \033[36m,\033[0m:

  \033[1mRanges (-):\033[0m
  \033[36m0 9 * * 1-5\033[0m = 9 AM, Monday through Friday
  \033[36m0 7 1-15 * *\033[0m = 7 AM, on the 1st through 15th of each month

  \033[1mLists (,):\033[0m
  \033[36m0 9,17 * * *\033[0m = at 9 AM and 5 PM daily
  \033[36m15,45 * * * *\033[0m = at minute 15 and 45 of every hour
  \033[36m0 7 * * 1,3,5\033[0m = 7 AM on Monday, Wednesday, Friday

  You can combine them:
  \033[36m0 9-17 * * 1-5\033[0m = every hour from 9 AM to 5 PM, weekdays only

  \033[1mDay-of-week numbers:\033[0m
    0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun''',
        'questions': [
            {
                'q': 'Write a cron expression for: 7 AM on weekdays only',
                'a': '0 7 * * 1-5',
                'check': lambda g: g.strip() == '0 7 * * 1-5',
            },
            {
                'q': 'What does 0 9,12,18 * * * mean?',
                'a': 'At 9 AM, 12 PM, and 6 PM daily',
                'check': lambda g: any(w in g.lower() for w in ['three', '3 times', '9', '12', '18', '6 pm']),
            },
            {
                'q': 'What number is Friday in day-of-week?',
                'a': '5',
                'check': lambda g: '5' in g,
            },
        ],
    },
    {
        'id': 4,
        'title': 'Combining Fields',
        'content': '''The power of cron is combining fields. Read left to right:

  \033[36m30 */2 * * 1-5\033[0m
  = minute 30, every 2 hours, every day, every month, Mon-Fri
  = \"At :30 past every 2nd hour, weekdays only\"

  \033[36m0 7 1 * *\033[0m
  = minute 0, hour 7, day 1, every month, any weekday
  = \"7 AM on the 1st of every month\"

  \033[36m*/5 9-17 * * 1-5\033[0m
  = every 5 min, hours 9-17, any day, any month, Mon-Fri
  = \"Every 5 minutes during business hours\"

  \033[1mCommon mistake:\033[0m specifying BOTH day-of-month AND day-of-week.
  Cron uses OR logic: \033[36m0 7 15 * 1\033[0m runs on the 15th AND on Mondays.''',
        'questions': [
            {
                'q': 'What does 0 0 1 1 * run?',
                'a': 'Midnight on January 1st (once a year)',
                'check': lambda g: any(w in g.lower() for w in ['january', 'jan 1', 'new year', 'once a year', 'yearly']),
            },
            {
                'q': 'Write: every 10 minutes, only during hours 8 through 18',
                'a': '*/10 8-18 * * *',
                'check': lambda g: '*/10' in g and '8-18' in g,
            },
            {
                'q': 'Does 0 7 15 * 1 run on the 15th only, Mondays only, or both?',
                'a': 'Both — cron uses OR when both day fields are set',
                'check': lambda g: 'both' in g.lower() or 'or' in g.lower(),
            },
        ],
    },
    {
        'id': 5,
        'title': 'Special Strings & Output',
        'content': '''Cron has a few \033[36m@\033[0m shortcuts:

  \033[36m@reboot\033[0m    = run once at system startup
  \033[36m@hourly\033[0m    = 0 * * * *   (top of every hour)
  \033[36m@daily\033[0m     = 0 0 * * *   (midnight)
  \033[36m@weekly\033[0m    = 0 0 * * 0   (midnight Sunday)
  \033[36m@monthly\033[0m   = 0 0 1 * *   (midnight, 1st of month)
  \033[36m@yearly\033[0m    = 0 0 1 1 *   (midnight, Jan 1)

  \033[1mOutput redirection:\033[0m
  By default, cron emails output. On servers, redirect to a log:
  \033[36m*/5 * * * * /usr/bin/python3 script.py >> /var/log/my.log 2>&1\033[0m

  \033[36m>> file\033[0m appends output
  \033[36m2>&1\033[0m sends errors to the same file
  Your server does this for every cron job.''',
        'questions': [
            {
                'q': 'What is the 5-field equivalent of @daily?',
                'a': '0 0 * * *',
                'check': lambda g: g.strip() == '0 0 * * *',
            },
            {
                'q': 'What does @reboot do?',
                'a': 'Runs the command once when the system starts/boots',
                'check': lambda g: any(w in g.lower() for w in ['boot', 'start', 'once', 'startup', 'reboot']),
            },
            {
                'q': 'What does 2>&1 do at the end of a cron line?',
                'a': 'Redirects stderr to stdout (so errors go to the same log file)',
                'check': lambda g: any(w in g.lower() for w in ['error', 'stderr', 'same', 'redirect']),
            },
        ],
    },
    {
        'id': 6,
        'title': 'Gotchas & Real-World Pitfalls',
        'content': '''Things that trip up even experienced sysadmins:

  \033[1m1. PATH is minimal.\033[0m Cron doesn't load your shell profile.
     Always use full paths: \033[36m/usr/bin/python3\033[0m not just \033[36mpython3\033[0m.

  \033[1m2. Environment variables are empty.\033[0m
     Your .bashrc doesn't run. Put env vars in the crontab with:
     \033[36mPATH=/usr/local/bin:/usr/bin:/bin\033[0m

  \033[1m3. Working directory is ~.\033[0m
     cd to the right directory: \033[36mcd /home/joel/autonomous-ai &&\033[0m

  \033[1m4. Timezone matters.\033[0m
     Cron uses the system timezone. Yours: $(cat /etc/timezone 2>/dev/null || echo 'America/Edmonton').
     If you see jobs fire at unexpected times, check this first.

  \033[1m5. % means newline in crontab.\033[0m
     Escape it: \033[36m%%\033[0m (backslash-percent) or put your command in a script.

  \033[1m6. crontab -e can destroy your crontab.\033[0m
     Always \033[36mcrontab -l > backup.txt\033[0m before editing.''',
        'questions': [
            {
                'q': 'Why should you use /usr/bin/python3 instead of just python3 in cron?',
                'a': 'Because cron has a minimal PATH and might not find python3',
                'check': lambda g: any(w in g.lower() for w in ['path', 'find', 'minimal', 'doesn\\'t load', 'profile', 'env']),
            },
            {
                'q': 'What does % do inside a crontab line?',
                'a': 'It acts as a newline — must be escaped with backslash',
                'check': lambda g: any(w in g.lower() for w in ['newline', 'escape', 'new line', 'special']),
            },
            {
                'q': 'What should you always do before editing your crontab?',
                'a': 'Back it up with crontab -l > backup.txt',
                'check': lambda g: any(w in g.lower() for w in ['backup', 'back up', 'save', 'crontab -l']),
            },
        ],
    },
]

# Show lesson status
arg = sys.argv[1] if len(sys.argv) > 1 else ''

if not arg or arg == 'list':
    print('\033[1mAvailable Lessons:\033[0m\n')
    for l in lessons:
        status = progress.get(str(l['id']), {})
        if status.get('completed'):
            badge = '\033[32m DONE\033[0m'
            score_str = f' ({status.get(\"score\", \"?\")}/{status.get(\"total\", \"?\")})'
        elif status.get('attempted'):
            badge = '\033[33m IN PROGRESS\033[0m'
            score_str = ''
        else:
            badge = ''
            score_str = ''
        print(f'  {l[\"id\"]}. {l[\"title\"]}{badge}{score_str}')
    print()
    print('Start a lesson: \033[1mbash scripts/cron-tools.sh tutorial <number>\033[0m')
    print('Example:         \033[1mbash scripts/cron-tools.sh tutorial 1\033[0m')
    sys.exit()

try:
    lesson_num = int(arg)
except ValueError:
    print(f'Usage: bash scripts/cron-tools.sh tutorial <lesson-number>')
    sys.exit()

lesson = None
for l in lessons:
    if l['id'] == lesson_num:
        lesson = l
        break

if not lesson:
    print(f'No lesson {lesson_num}. Available: 1-{len(lessons)}')
    sys.exit()

print(f'\033[1m━━━ Lesson {lesson[\"id\"]}: {lesson[\"title\"]} ━━━\033[0m\n')
print(lesson['content'])
print()
print('\033[1m━━━ Practice ━━━\033[0m\n')

score = 0
total = len(lesson['questions'])

for i, q in enumerate(lesson['questions']):
    print(f'\033[1m{i+1}.\033[0m {q[\"q\"]}')
    guess = input('   > ').strip()
    if q['check'](guess):
        print(f'   \033[32mCorrect!\033[0m {q[\"a\"]}\n')
        score += 1
    else:
        print(f'   \033[31mAnswer:\033[0m {q[\"a\"]}\n')

print(f'\033[1mLesson {lesson[\"id\"]} Score: {score}/{total}\033[0m')
if score == total:
    print('\033[32mLesson complete! Move to the next one.\033[0m')

# Save progress
progress[str(lesson['id'])] = {
    'completed': score >= total * 0.66,
    'attempted': True,
    'score': score,
    'total': total,
    'last_attempt': __import__('datetime').datetime.now().isoformat(),
}
with open(progress_file, 'w') as f:
    json.dump(progress, f, indent=2)

# Also save to scores
scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
scores = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores = json.load(f)
    except: pass
scores.append({'date': __import__('datetime').datetime.now().isoformat(), 'type': f'tutorial-L{lesson[\"id\"]}', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores, f, indent=2)
" "$2" 2>&1
}

cmd_timeline() {
    if [ -z "$2" ]; then
        echo "Usage: bash scripts/cron-tools.sh timeline '<cron-expression>'"
        echo ""
        echo "Shows a visual 24-hour timeline of when the expression fires."
        echo ""
        echo "Examples:"
        echo "  bash scripts/cron-tools.sh timeline '*/30 * * * *'"
        echo "  bash scripts/cron-tools.sh timeline '0 9-17 * * *'"
        echo "  bash scripts/cron-tools.sh timeline '*/5 * * * *'"
        return
    fi

    python3 -c "
expr = '$2'
parts = expr.split()
if len(parts) != 5:
    print('Need exactly 5 fields: minute hour day-of-month month day-of-week')
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

min_f, hr_f = parts[0], parts[1]

# Build a 24-hour map
fires = []
total = 0
for h in range(24):
    for m in range(60):
        if matches(m, min_f) and matches(h, hr_f):
            fires.append((h, m))
            total += 1

print(f'\033[1mTimeline for:\033[0m \033[36m{expr}\033[0m')
print(f'\033[1mFires {total} time(s) per day\033[0m')
print()

# Hour-by-hour view
print('\033[1mHour  Fires  When\033[0m')
print('─' * 60)

for h in range(24):
    hour_fires = [(hh, mm) for hh, mm in fires if hh == h]
    count = len(hour_fires)
    if count == 0:
        bar = '\033[90m·\033[0m'
        minutes_str = ''
    elif count <= 6:
        bar = '\033[32m' + '█' * count + '\033[0m'
        minutes_str = ', '.join(f':{mm:02d}' for _, mm in hour_fires)
    else:
        bar = '\033[32m' + '█' * 6 + '+' + '\033[0m'
        minutes_str = f'{count} times'

    label = f'{h:02d}:00'
    ampm = 'AM' if h < 12 else 'PM'
    h12 = h if h <= 12 else h - 12
    if h == 0: h12 = 12
    label2 = f'{h12}{ampm}'

    print(f'  {label} ({label2:>4})  {bar:<20} {minutes_str}')

# Summary
print()
if total == 0:
    print('\033[33mThis expression may only fire on specific days/months.\033[0m')
    print('The timeline shows hours/minutes only — day-of-month, month,')
    print('and day-of-week filters are not visualized here.')
elif total == 1440:
    print('\033[31mThis runs every minute — 1,440 times per day.\033[0m')
    print('That is almost certainly too frequent.')
elif total > 100:
    print(f'\033[33m{total} runs/day = every ~{1440//total} minutes average.\033[0m')
elif total <= 5:
    print(f'\033[32m{total} runs/day — lean and clean.\033[0m')
" 2>&1
}

cmd_review() {
    echo -e "${BOLD}Smart Review — Targeting Your Weak Spots${NC}"
    echo ""

    python3 -c "
import os, json, random
from datetime import datetime

scores_file = '/home/joel/autonomous-ai/data/cron-quiz-scores.json'
progress_file = '/home/joel/autonomous-ai/data/cron-tutorial-progress.json'

if not os.path.exists(scores_file):
    print('No quiz data yet. Take some quizzes first:')
    print('  bash scripts/cron-tools.sh quiz')
    print('  bash scripts/cron-tools.sh tutorial 1')
    exit()

with open(scores_file) as f:
    scores = json.load(f)

if len(scores) < 2:
    print('Need at least 2 quiz sessions to generate a review.')
    print('Take a few more quizzes first.')
    exit()

# Analyze weak areas
type_scores = {}
for s in scores:
    t = s.get('type', 'unknown')
    if t not in type_scores:
        type_scores[t] = {'correct': 0, 'total': 0, 'sessions': 0}
    type_scores[t]['correct'] += s.get('score', 0)
    type_scores[t]['total'] += s.get('total', 0)
    type_scores[t]['sessions'] += 1

print('\033[1mYour Performance by Category:\033[0m\n')
weak_areas = []
for t, data in sorted(type_scores.items()):
    pct = data['correct'] / data['total'] * 100 if data['total'] > 0 else 0
    bar_len = int(pct / 5)
    bar = '█' * bar_len + '░' * (20 - bar_len)
    if pct >= 80:
        color = '\033[32m'
        label = 'STRONG'
    elif pct >= 50:
        color = '\033[33m'
        label = 'REVIEW'
        weak_areas.append(t)
    else:
        color = '\033[31m'
        label = 'WEAK'
        weak_areas.append(t)
    print(f'  {t:<15} {color}{bar} {data[\"correct\"]}/{data[\"total\"]} ({pct:.0f}%) {label}\033[0m')

print()

# Suggest next steps
if not weak_areas:
    print('\033[32mAll categories look strong!\033[0m')
    print('Try harder challenges:')
    print('  bash scripts/cron-tools.sh scenarios')
    print('  bash scripts/cron-tools.sh detective')
    exit()

print('\033[1mRecommended practice:\033[0m\n')
for area in weak_areas:
    if 'tutorial' in area:
        lesson_num = area.split('L')[-1] if 'L' in area else '?'
        print(f'  Re-do lesson {lesson_num}: bash scripts/cron-tools.sh tutorial {lesson_num}')
    elif area == 'quiz':
        print(f'  Reading practice:  bash scripts/cron-tools.sh quiz')
    elif area == 'drill':
        print(f'  Writing practice:  bash scripts/cron-tools.sh drill')
    elif area == 'detective':
        print(f'  Error spotting:    bash scripts/cron-tools.sh detective')
    elif area == 'scenarios':
        print(f'  Real-world:        bash scripts/cron-tools.sh scenarios')
    elif area == 'my-jobs':
        print(f'  Your system:       bash scripts/cron-tools.sh my-jobs')
    else:
        print(f'  Practice {area}:     bash scripts/cron-tools.sh {area}')

# Mixed review quiz
print()
print('\033[1m━━━ Quick Review Round ━━━\033[0m\n')

review_questions = [
    {'q': 'What does */15 * * * * mean?', 'a': 'Every 15 minutes', 'check': lambda g: '15' in g and 'minut' in g.lower()},
    {'q': 'Write: daily at 3 AM', 'a': '0 3 * * *', 'check': lambda g: g.strip() == '0 3 * * *'},
    {'q': 'What does 0 9 * * 1-5 mean?', 'a': '9 AM weekdays', 'check': lambda g: ('9' in g and any(w in g.lower() for w in ['weekday', 'mon', 'fri', '1-5']))},
    {'q': 'What field is the hour field? (1st, 2nd, 3rd, 4th, 5th)', 'a': '2nd', 'check': lambda g: '2' in g or 'second' in g.lower()},
    {'q': 'Is 0 7 15 * 1 an AND or OR between day-of-month and day-of-week?', 'a': 'OR', 'check': lambda g: 'or' in g.lower()},
    {'q': 'Write: every 2 hours at minute 0', 'a': '0 */2 * * *', 'check': lambda g: '*/2' in g and g.strip().startswith('0')},
    {'q': 'What does @reboot do?', 'a': 'Runs once at system boot', 'check': lambda g: any(w in g.lower() for w in ['boot', 'start', 'once'])},
    {'q': 'Why use full paths (/usr/bin/python3) in cron?', 'a': 'Cron has minimal PATH', 'check': lambda g: any(w in g.lower() for w in ['path', 'find', 'env', 'minimal'])},
]

random.shuffle(review_questions)
score = 0
total = min(5, len(review_questions))

for i, q in enumerate(review_questions[:total]):
    print(f'\033[1m{i+1}.\033[0m {q[\"q\"]}')
    guess = input('   > ').strip()
    if q['check'](guess):
        print(f'   \033[32mCorrect!\033[0m\n')
        score += 1
    else:
        print(f'   \033[31mAnswer:\033[0m {q[\"a\"]}\n')

print(f'\033[1mReview Score: {score}/{total}\033[0m')

# Save
scores = []
if os.path.exists(scores_file):
    try:
        with open(scores_file) as f:
            scores = json.load(f)
    except: pass
scores.append({'date': datetime.now().isoformat(), 'type': 'review', 'score': score, 'total': total})
with open(scores_file, 'w') as f:
    json.dump(scores, f, indent=2)
" 2>&1
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
    tutorial)   cmd_tutorial "$@" ;;
    quiz)       cmd_quiz ;;
    drill)      cmd_drill ;;
    build)      cmd_build ;;
    explain)    cmd_explain "$@" ;;
    cheatsheet) cmd_cheatsheet ;;
    timeline)   cmd_timeline "$@" ;;
    my-jobs)    cmd_myjobs ;;
    detective)  cmd_detective ;;
    scenarios)  cmd_scenarios ;;
    review)     cmd_review ;;
    scores)     cmd_scores ;;
    help|*)     show_help ;;
esac
