#!/bin/bash
# Cloudflare Tunnel for Meridian Hub
# Uses named tunnel (meridian-loop.com) when token available, falls back to quick tunnel
# Managed by systemd: cloudflare-tunnel.service

CLOUDFLARED="/home/joel/autonomous-ai/infrastructure/build/cloudflared"
# Fallback to system cloudflared or build dir
[ ! -x "$CLOUDFLARED" ] && CLOUDFLARED="/home/joel/autonomous-ai/build/cloudflared"
[ ! -x "$CLOUDFLARED" ] && CLOUDFLARED="$(which cloudflared 2>/dev/null)"

REPO_DIR="/home/joel/autonomous-ai"
CONFIG="$REPO_DIR/signal-config.json"
WEBSITE_CONFIG="$REPO_DIR/website/signal-config.json"
LOG="/tmp/cloudflared-signal.log"
PORT=8090

# Load .env for tunnel token
if [ -f "$REPO_DIR/.env" ]; then
    export CF_TUNNEL_TOKEN=$(grep '^CF_TUNNEL_TOKEN=' "$REPO_DIR/.env" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
fi

# Kill any existing cloudflared tunnel processes
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

echo "[$(date)] Starting Cloudflare tunnel on port $PORT..."

if [ -n "$CF_TUNNEL_TOKEN" ]; then
    # Named tunnel — routes to meridian-loop.com (configured in CF dashboard)
    echo "[$(date)] Using NAMED tunnel (meridian-loop.com)"
    $CLOUDFLARED tunnel run --token "$CF_TUNNEL_TOKEN" > "$LOG" 2>&1 &
    CF_PID=$!
    echo "[$(date)] cloudflared PID: $CF_PID"

    # Named tunnel URL is fixed
    URL="https://meridian-loop.com"
    sleep 5  # Give it time to connect

    # Check if process is still alive
    if kill -0 $CF_PID 2>/dev/null; then
        echo "[$(date)] Named tunnel running. URL: $URL"
    else
        echo "[$(date)] ERROR: Named tunnel failed to start. Check token. Falling back to quick tunnel."
        CF_TUNNEL_TOKEN=""
    fi
fi

if [ -z "$CF_TUNNEL_TOKEN" ]; then
    # Fallback: quick tunnel (random URL)
    echo "[$(date)] Using QUICK tunnel (random URL)"
    $CLOUDFLARED tunnel --url http://localhost:$PORT > "$LOG" 2>&1 &
    CF_PID=$!
    echo "[$(date)] cloudflared PID: $CF_PID"

    URL=""
    for i in $(seq 1 30); do
        sleep 2
        URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)
        if [ -n "$URL" ]; then
            echo "[$(date)] Quick tunnel URL: $URL"
            break
        fi
    done

    if [ -z "$URL" ]; then
        echo "[$(date)] ERROR: No tunnel URL found after 60 seconds"
        kill $CF_PID 2>/dev/null
        exit 1
    fi
fi

# Update config files
CONFIG_JSON=$(cat << EOF
{
  "url": "$URL",
  "fallback_urls": [],
  "version": "2.3",
  "tunnel_type": "$([ -n "$CF_TUNNEL_TOKEN" ] && echo named || echo quick)",
  "updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

echo "$CONFIG_JSON" > "$CONFIG"
echo "$CONFIG_JSON" > "$WEBSITE_CONFIG"

# Push to GitHub Pages
cd "$REPO_DIR"
git add signal-config.json website/signal-config.json 2>/dev/null
git stash 2>/dev/null
git pull --rebase origin master 2>/dev/null
git stash pop 2>/dev/null
git add signal-config.json website/signal-config.json 2>/dev/null
git commit -m "Update tunnel URL" 2>/dev/null
git push origin master 2>/dev/null
echo "[$(date)] Config pushed to GitHub Pages"

# Keep running — wait for cloudflared to exit
wait $CF_PID
echo "[$(date)] cloudflared exited. Service will restart."
exit 1
