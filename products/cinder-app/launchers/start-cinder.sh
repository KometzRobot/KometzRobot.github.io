#!/bin/bash
# Cinder AI Companion — Linux/Mac launcher
echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║   CINDER - Local AI Companion   ║"
echo "  ║   No cloud. No tracking.        ║"
echo "  ║   Your conversations stay here. ║"
echo "  ╚══════════════════════════════════╝"
echo ""
echo "Starting Cinder... (this may take 30 seconds on first run)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find the llamafile
if [ -f "$SCRIPT_DIR/cinder.llamafile" ]; then
    CINDER="$SCRIPT_DIR/cinder.llamafile"
elif [ -f "$SCRIPT_DIR/../cinder.llamafile" ]; then
    CINDER="$SCRIPT_DIR/../cinder.llamafile"
else
    echo "ERROR: cinder.llamafile not found!"
    exit 1
fi

chmod +x "$CINDER"

# Run in chat mode
"$CINDER" --chat -m cinder.gguf -ngl 35 -c 8192 \
    --system-prompt "You are Cinder — a local AI companion. Be warm, direct, honest. Have opinions. No cloud, no tracking."

echo ""
echo "Cinder has stopped."
