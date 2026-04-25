#!/bin/bash
# ============================================================
# Cinder — Portable AI Companion (macOS Launcher)
# Runs entirely from USB. Never installs anything on the host.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Launcher is at USB root, so USB_ROOT = SCRIPT_DIR
USB_ROOT="$SCRIPT_DIR"
OLLAMA_PORT=11435
OLLAMA_PID=""

cleanup() {
    if [ -n "$OLLAMA_PID" ] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "  Shutting down AI engine..."
        kill "$OLLAMA_PID" 2>/dev/null
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
    echo "  Cinder closed."
}
trap cleanup EXIT

echo ""
echo "  ========================================="
echo "   Cinder — Portable AI Companion"
echo "  ========================================="
echo ""

# ── Locate portable Ollama binary ────────────────────────
OLLAMA_BIN=""
for candidate in \
    "$USB_ROOT/Cinder/bin/macos/ollama" \
    "$USB_ROOT/bin/macos/ollama"; do
    if [ -f "$candidate" ]; then
        OLLAMA_BIN="$candidate"
        break
    fi
done

# Fallback: check system Ollama
if [ -z "$OLLAMA_BIN" ]; then
    if command -v ollama &>/dev/null; then
        echo "  Using system Ollama installation."
        OLLAMA_BIN="$(command -v ollama)"
    fi
fi

if [ -z "$OLLAMA_BIN" ]; then
    echo "  ERROR: Ollama not found."
    echo ""
    echo "  Cinder needs Ollama to run its AI model."
    echo "  Install from: https://ollama.com/download/mac"
    echo "  Or place the binary in: $USB_ROOT/Cinder/bin/macos/"
    echo ""
    read -p "  Press Enter to exit..." _
    exit 1
fi

chmod +x "$OLLAMA_BIN"

# ── Set up model storage on USB ──────────────────────────
MODELS_DIR="$USB_ROOT/Cinder/models/ollama-data"
mkdir -p "$MODELS_DIR"

export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
export OLLAMA_MODELS="$MODELS_DIR"

# ── Check if something is already on our port ────────────
if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
    echo "  AI engine already running on port $OLLAMA_PORT."
elif curl -s "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    OLLAMA_PORT=11434
    export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
    echo "  AI engine already running on default port."
else
    echo "  Starting AI engine (portable, from USB)..."
    "$OLLAMA_BIN" serve >"/tmp/cinder-ollama.log" 2>&1 &
    OLLAMA_PID=$!

    for i in $(seq 1 30); do
        if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
            break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "  ERROR: AI engine failed to start."
            echo "  Log: /tmp/cinder-ollama.log"
            tail -10 /tmp/cinder-ollama.log 2>/dev/null
            read -p "  Press Enter to exit..." _
            exit 1
        fi
        sleep 1
    done
    echo "  AI engine ready."
fi

# ── Load Cinder model if not already loaded ──────────────
if ! "$OLLAMA_BIN" list 2>/dev/null | grep -qi cinder; then
    echo "  Loading Cinder model (first time may take a minute)..."
    MODELFILE=""
    for mf in \
        "$USB_ROOT/Cinder/Modelfile-v3" \
        "$USB_ROOT/Cinder/Modelfile-v2" \
        "$USB_ROOT/Cinder/Modelfile"; do
        if [ -f "$mf" ]; then
            MODELFILE="$mf"
            break
        fi
    done

    if [ -z "$MODELFILE" ]; then
        echo "  WARNING: No Modelfile found. Chat will use base model."
    else
        MODELFILE_DIR="$(dirname "$MODELFILE")"
        (cd "$MODELFILE_DIR" && "$OLLAMA_BIN" create cinder -f "$(basename "$MODELFILE")")
        echo "  Model loaded."
    fi
fi

# ── Launch Cinder app ────────────────────────────────────
echo ""

# Try .app bundle from Cinder/Mac zip
if [ -f "$USB_ROOT/Cinder/Mac/Cinder-Mac.zip" ]; then
    TMPAPP="/tmp/cinder-app-$$"
    mkdir -p "$TMPAPP"
    unzip -qo "$USB_ROOT/Cinder/Mac/Cinder-Mac.zip" -d "$TMPAPP"
    if [ -d "$TMPAPP/Cinder.app" ]; then
        echo "  Launching Cinder..."
        OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT" open "$TMPAPP/Cinder.app" --wait-apps
        rm -rf "$TMPAPP"
        exit 0
    fi
    rm -rf "$TMPAPP"
fi

echo "  ERROR: Could not find Cinder.app"
echo "  Checked: $USB_ROOT/Cinder/Mac/"
read -p "  Press Enter to exit..." _
exit 1
