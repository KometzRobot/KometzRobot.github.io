#!/bin/bash
# Persistent Cloudflare Tunnel for The Signal
# Captures the quick tunnel URL and updates signal-config.json on GitHub Pages
# Managed by systemd: cloudflare-tunnel.service

CLOUDFLARED="/home/joel/autonomous-ai/build/cloudflared"
REPO_DIR="/home/joel/autonomous-ai"
CONFIG="$REPO_DIR/signal-config.json"
WEBSITE_CONFIG="$REPO_DIR/website/signal-config.json"
LOG="/tmp/cloudflared-signal.log"
PORT=8090

# Kill any existing cloudflared tunnel processes (not this script)
pkill -f "cloudflared tunnel --url" 2>/dev/null
sleep 1

echo "[$(date)] Starting Cloudflare tunnel on port $PORT..."

# Start cloudflared in background, capture output
$CLOUDFLARED tunnel --url http://localhost:$PORT > "$LOG" 2>&1 &
CF_PID=$!
echo "[$(date)] cloudflared PID: $CF_PID"

# Wait for URL to appear in output
URL=""
for i in $(seq 1 30); do
    sleep 2
    URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)
    if [ -n "$URL" ]; then
        echo "[$(date)] Tunnel URL: $URL"
        break
    fi
done

if [ -z "$URL" ]; then
    echo "[$(date)] ERROR: No tunnel URL found after 60 seconds"
    kill $CF_PID 2>/dev/null
    exit 1
fi

# Update config files
CONFIG_JSON=$(cat << EOF
{
  "url": "$URL",
  "fallback_urls": [],
  "version": "2.2",
  "updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

echo "$CONFIG_JSON" > "$CONFIG"
echo "$CONFIG_JSON" > "$WEBSITE_CONFIG"

# Push to GitHub Pages
cd "$REPO_DIR"
git add signal-config.json
git stash 2>/dev/null
git pull --rebase origin master 2>/dev/null
git stash pop 2>/dev/null
git add signal-config.json
git commit -m "Update tunnel URL" 2>/dev/null
git push origin master 2>/dev/null
echo "[$(date)] Config pushed to GitHub Pages"

# Keep running — wait for cloudflared to exit
# If it exits, systemd will restart this service and get a new URL
wait $CF_PID
echo "[$(date)] cloudflared exited. Service will restart."
exit 1
