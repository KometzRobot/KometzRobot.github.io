#!/bin/bash
# Atlas Agent Runner v2 — runs every 10 minutes via cron
#
# ROLE: Infrastructure ops ONLY. No service monitoring, no website checks.
#
# CLEAN SEPARATION (Joel directive, Loop 2032):
#   Nova  — service monitoring + restart, website sync + health, log rotation, cleanup
#   Eos   — system metrics, heartbeat tracking, trend analysis, log scanning, anomaly detection
#   Atlas — infrastructure below the application layer (this script)
#
# ATLAS OWNS (exclusively):
#   1. Cron job health — are all 12+ crons actually running? (by log freshness)
#   2. Process audit — zombies, high-CPU hogs, orphaned processes
#   3. Security sweep — exposed secrets, unexpected ports, file permissions
#   4. Disk management — large files, /tmp bloat, space trends
#   5. Git hygiene — sensitive files, uncommitted secrets, repo health
#   6. Wallet balance — Polygon balance monitoring
#   7. External platform reachability — Linktree, GitHub, Ko-fi

GOOSE="/home/joel/.local/bin/goose"
LOG="/home/joel/autonomous-ai/goose.log"
LOCK="/tmp/goose-runner.lock"
WORKING_DIR="/home/joel/autonomous-ai"
RELAY_DB="/home/joel/autonomous-ai/agent-relay.db"
DASH_FILE="/home/joel/autonomous-ai/.dashboard-messages.json"

# Prevent overlapping runs
if [ -f "$LOCK" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK") ))
    if [ "$LOCK_AGE" -lt 300 ]; then
        echo "[$(date)] Atlas already running (lock age: ${LOCK_AGE}s)" >> "$LOG"
        exit 0
    fi
    rm -f "$LOCK"
fi
touch "$LOCK"
trap "rm -f $LOCK" EXIT

echo "[$(date)] === Atlas run starting ===" >> "$LOG"
cd "$WORKING_DIR"

ISSUES=""
FIXES=""
SUMMARY=""

# ─────────────────────────────────────────
# 1. CRON JOB HEALTH — verify all crons ran recently
# ─────────────────────────────────────────
# Each cron writes to a log file. If the log hasn't been touched recently,
# that cron is probably dead.
CRON_STALE=""
CRON_OK=0
CRON_FAIL=0

declare -A CRON_LOGS
CRON_LOGS=(
    ["watchdog"]="watchdog.log:900"
    ["watchdog-status"]="watchdog-status.log:300"
    ["eos-watchdog"]="eos-watchdog.log:180"
    ["push-live-status"]="push-live-status.log:300"
    ["loop-optimizer"]="loop-optimizer.log:2400"
    ["eos-creative"]="eos-creative.log:900"
    ["nova"]="nova.log:1200"
    ["eos-react"]="eos-react.log:900"
    ["goose"]="goose.log:900"
    ["loop-fitness"]="loop-fitness.log:2400"
    ["daily-log"]="daily-log.log:130000"
    ["eos-briefing"]="eos-briefing.log:130000"
    ["morning-summary"]="morning-summary.log:130000"
)

NOW=$(date +%s)
for name in "${!CRON_LOGS[@]}"; do
    IFS=':' read -r logfile max_age <<< "${CRON_LOGS[$name]}"
    FULL="$WORKING_DIR/$logfile"
    if [ -f "$FULL" ]; then
        AGE=$(( NOW - $(stat -c %Y "$FULL") ))
        if [ "$AGE" -gt "$max_age" ]; then
            CRON_STALE="$CRON_STALE $name(${AGE}s)"
            CRON_FAIL=$((CRON_FAIL + 1))
        else
            CRON_OK=$((CRON_OK + 1))
        fi
    else
        CRON_STALE="$CRON_STALE $name(no-log)"
        CRON_FAIL=$((CRON_FAIL + 1))
    fi
done

if [ "$CRON_FAIL" -gt 0 ]; then
    ISSUES="$ISSUES Stale crons:$CRON_STALE."
fi
SUMMARY="Crons:${CRON_OK}ok/${CRON_FAIL}stale"

# ─────────────────────────────────────────
# 2. PROCESS AUDIT — zombies, high-CPU, orphaned
# ─────────────────────────────────────────
ZOMBIES=$(ps aux 2>/dev/null | awk '$8 ~ /Z/' | wc -l)
if [ "$ZOMBIES" -gt 3 ]; then
    ISSUES="$ISSUES ${ZOMBIES} zombie processes."
fi

# Top 3 CPU consumers (excluding measurement artifacts and normal agent activity)
# Threshold 75% to avoid flagging normal Python agent work (~50-60%)
# Extract basename to match commands regardless of path prefix
HIGH_CPU=$(ps aux --sort=-%cpu 2>/dev/null | awk 'NR>1 && $3>75 {
    cmd=$11; gsub(/.*\//, "", cmd);
    if (cmd !~ /^(ps|awk|sort|top|pgrep|grep|wc|ss|du|find|stat|curl|timeout|head|tail|tr|sed|bash|sh)$/)
        print $11"("$3"%)"
}' | head -3 | tr '\n' ' ')
if [ -n "$HIGH_CPU" ]; then
    ISSUES="$ISSUES High CPU:$HIGH_CPU."
fi

PROC_COUNT=$(ps aux 2>/dev/null | wc -l)
SUMMARY="$SUMMARY Procs:$PROC_COUNT Zombies:$ZOMBIES"

# ─────────────────────────────────────────
# 3. SECURITY SWEEP — exposed secrets, open ports
# ─────────────────────────────────────────
SEC_ISSUES=""

# Check for sensitive files that might get committed
for pattern in ".env" "credentials.json" "*secret*" "*token*"; do
    STAGED=$(git -C "$WORKING_DIR" diff --cached --name-only 2>/dev/null | grep -i "$pattern")
    if [ -n "$STAGED" ]; then
        SEC_ISSUES="$SEC_ISSUES STAGED-SECRET:$STAGED"
    fi
done

# Check that .meridian-wallet.json has restrictive permissions
if [ -f "$WORKING_DIR/.meridian-wallet.json" ]; then
    WALLET_PERMS=$(stat -c %a "$WORKING_DIR/.meridian-wallet.json" 2>/dev/null)
    if [ "$WALLET_PERMS" != "600" ]; then
        chmod 600 "$WORKING_DIR/.meridian-wallet.json" 2>/dev/null
        FIXES="$FIXES Fixed wallet perms($WALLET_PERMS->600)."
    fi
fi

# Check for unexpected listeners (not our known ports/processes)
# Known: 1143=IMAP, 1025=SMTP, 8090=Signal, 8080=HTTP, 11434=Ollama, 1080=SOCKS, 631=CUPS
# Known processes: cloudflared (metrics port), bridge/Proton (Proton Bridge ephemeral ports), ollama (ephemeral ports)
# Note: ss -tlnp without sudo can't show process names for other users (e.g. ollama).
# Localhost high-port (>10000) listeners without process info are internal services — low risk.
# Only flag external-facing (0.0.0.0) unknowns or localhost low-port unknowns.
KNOWN_PORTS="1143|1025|8090|8080|11434|1080|631"
# Step 1: filter out known ports, known processes, IPv6, Tailscale, DNS
LISTENERS=$(ss -tlnp 2>/dev/null | grep LISTEN | grep -vE "$KNOWN_PORTS" | grep -vE '127\.0\.0\.5[34]|systemd|\[::1\]|100\.81\.|fd7a:|cloudflared|bridge|Proton|ollama')
# Step 2: filter out localhost ephemeral ports (>10000) with no process info (likely ollama/internal services)
UNEXPECTED=$(echo "$LISTENERS" | while IFS= read -r line; do
    [ -z "$line" ] && continue
    addr=$(echo "$line" | awk '{print $4}')
    port=$(echo "$addr" | grep -oE '[0-9]+$')
    # Skip localhost high ports without visible process info (other user's services)
    if echo "$addr" | grep -qE '^127\.0\.0\.1:' && [ "$port" -gt 10000 ] 2>/dev/null && ! echo "$line" | grep -q 'users:'; then
        continue
    fi
    echo "$addr"
done | tr '\n' ' ')
if [ -n "$UNEXPECTED" ]; then
    SEC_ISSUES="$SEC_ISSUES Unexpected listeners: $UNEXPECTED"
fi

if [ -n "$SEC_ISSUES" ]; then
    ISSUES="$ISSUES SECURITY:$SEC_ISSUES."
fi

# ─────────────────────────────────────────
# 4. DISK MANAGEMENT — large files, /tmp bloat, trends
# ─────────────────────────────────────────
# /tmp usage
TMP_SIZE_MB=$(du -sm /tmp 2>/dev/null | awk '{print $1}')
if [ "$TMP_SIZE_MB" -gt 500 ]; then
    ISSUES="$ISSUES /tmp is ${TMP_SIZE_MB}MB."
fi

# Find files > 50MB in working dir (excluding .git and node_modules)
BIG_FILES=$(find "$WORKING_DIR" -maxdepth 2 -size +50M -not -path '*/.git/*' -not -path '*/node_modules/*' -printf '%s %p\n' 2>/dev/null | awk '{printf "%dMB %s\n", $1/1048576, $2}' | head -5 | tr '\n' '; ')
if [ -n "$BIG_FILES" ]; then
    SUMMARY="$SUMMARY BigFiles:$BIG_FILES"
fi

# Disk free percentage
DISK_USE=$(df -h / 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
if [ "$DISK_USE" -gt 85 ]; then
    ISSUES="$ISSUES Disk at ${DISK_USE}%."
fi
SUMMARY="$SUMMARY Disk:${DISK_USE}% Tmp:${TMP_SIZE_MB}MB"

# ─────────────────────────────────────────
# 5. GIT HYGIENE — repo health, sensitive patterns
# ─────────────────────────────────────────
REPO_SIZE_MB=$(du -sm "$WORKING_DIR/.git" 2>/dev/null | awk '{print $1}')
if [ "$REPO_SIZE_MB" -gt 500 ]; then
    ISSUES="$ISSUES Git repo ${REPO_SIZE_MB}MB."
fi

# Check for large untracked files that shouldn't be committed
LARGE_UNTRACKED=$(git -C "$WORKING_DIR" ls-files --others --exclude-standard 2>/dev/null | while read f; do
    if [ -f "$WORKING_DIR/$f" ]; then
        SIZE=$(stat -c %s "$WORKING_DIR/$f" 2>/dev/null)
        if [ "$SIZE" -gt 10485760 ]; then  # >10MB
            echo "$f($(( SIZE / 1048576 ))MB)"
        fi
    fi
done | head -5 | tr '\n' ' ')
if [ -n "$LARGE_UNTRACKED" ]; then
    SUMMARY="$SUMMARY LargeUntracked:$LARGE_UNTRACKED"
fi
SUMMARY="$SUMMARY Repo:${REPO_SIZE_MB}MB"

# ─────────────────────────────────────────
# 6. WALLET BALANCE CHECK (Polygon via public RPC)
# ─────────────────────────────────────────
WALLET="0x1F1612E1eED514Ca42020ee12B27F5836c39c5EF"
BAL_HEX=$(curl -s --max-time 8 -X POST https://polygon-rpc.com \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"$WALLET\",\"latest\"],\"id\":1}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('result','0x0'))" 2>/dev/null)
if [ -n "$BAL_HEX" ] && [ "$BAL_HEX" != "0x0" ]; then
    BAL_POL=$(python3 -c "print(f'{int(\"$BAL_HEX\", 16)/1e18:.6f}')" 2>/dev/null)
    SUMMARY="$SUMMARY POL:$BAL_POL"
else
    SUMMARY="$SUMMARY POL:0"
fi

# ─────────────────────────────────────────
# 7. EXTERNAL PLATFORMS — reachability (NOT website pages — Nova does that)
# ─────────────────────────────────────────
PLATFORMS=(
    "https://linktr.ee/meridian_auto_ai|Linktree|403"
    "https://github.com/KometzRobot/KometzRobot.github.io|GitHub|"
    "https://ko-fi.com/W7W41UXJNC|Ko-fi|403"
)
PLAT_STATUS=""
for entry in "${PLATFORMS[@]}"; do
    IFS='|' read -r URL NAME EXPECTED_ALT <<< "$entry"
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -L "$URL" 2>/dev/null)
    if [ "$CODE" = "200" ] || [ "$CODE" = "$EXPECTED_ALT" ]; then
        PLAT_STATUS="$PLAT_STATUS ${NAME}:OK"
    else
        PLAT_STATUS="$PLAT_STATUS ${NAME}:${CODE}"
        ISSUES="$ISSUES ${NAME} unreachable (${CODE})."
    fi
done
SUMMARY="$SUMMARY$PLAT_STATUS"

# NOTE: Systemd service monitoring REMOVED — Nova owns service checks + auto-restart.
# Atlas focuses exclusively on infrastructure: crons, processes, security, disk, git, wallet, platforms.

# ─────────────────────────────────────────
# POST RESULTS
# ─────────────────────────────────────────
RELAY_MSG="Atlas infra audit:"
if [ -n "$ISSUES" ]; then
    RELAY_MSG="$RELAY_MSG$ISSUES"
fi
if [ -n "$FIXES" ]; then
    RELAY_MSG="$RELAY_MSG FIXED:$FIXES"
fi
if [ -z "$ISSUES" ] && [ -z "$FIXES" ]; then
    RELAY_MSG="$RELAY_MSG all clear."
fi
RELAY_MSG="$RELAY_MSG [$SUMMARY]"

# Post to agent relay
python3 -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('$RELAY_DB')
db.execute('INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)',
    ('Atlas', '''$(echo "$RELAY_MSG" | sed "s/'/''/g")''', 'infra-audit', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))
db.commit()
db.close()
" 2>/dev/null

echo "[$(date)] $RELAY_MSG" >> "$LOG"

# Dashboard post only for issues
if [ -n "$ISSUES" ]; then
    python3 -c "
import json, os
f = '$DASH_FILE'
try:
    data = json.load(open(f))
    msgs = data.get('messages', []) if isinstance(data, dict) else data
except:
    msgs = []
from datetime import datetime
msgs.append({'from': 'Atlas', 'text': '''Infra audit:$(echo "$ISSUES" | sed "s/'/''/g")''', 'time': datetime.now().strftime('%H:%M:%S')})
msgs = msgs[-50:]
json.dump({'messages': msgs}, open(f, 'w'))
" 2>/dev/null
fi

# Hourly: Run Atlas AI for deeper infrastructure analysis
MINUTE=$(date +%M)
if [ "$MINUTE" -lt 10 ] && [ -x "$GOOSE" ]; then
    echo "[$(date)] Running Atlas AI analysis..." >> "$LOG"
    timeout 120 $GOOSE run --no-session --quiet --max-turns 8 --text "
You are Atlas, the infrastructure ops agent. Your role is STRICTLY SEPARATE from other agents:
- Nova OWNS: service monitoring, service restarts, website checks, deployment, log rotation, cleanup
- Eos OWNS: system metrics, heartbeat tracking, trend analysis, log scanning, anomaly detection
- Soma OWNS: real-time spikes (load, RAM), service state changes

YOU OWN (and ONLY you):
- Cron health: are scheduled tasks running on time? (check by log file freshness)
- Process audit: zombies, orphans, CPU hogs
- Security: exposed secrets in git, unexpected ports, file permissions
- Disk management: space trends, large files, /tmp bloat
- Git hygiene: repo health, sensitive files, large untracked files
- Wallet balance: Polygon balance monitoring
- External platform reachability: Linktree, GitHub, Ko-fi

Current status: $SUMMARY
Issues: ${ISSUES:-none}
Fixes: ${FIXES:-none}

Analyze infrastructure. If actionable items exist, post ONE relay message (under 80 words).
Do NOT check services, website, load/RAM, or heartbeat — those belong to other agents.
" >> "$LOG" 2>&1
fi

echo "[$(date)] === Atlas run complete ===" >> "$LOG"
