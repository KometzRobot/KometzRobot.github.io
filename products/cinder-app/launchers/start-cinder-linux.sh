#!/bin/bash
# ============================================================
# Cinder — Portable AI Companion (Linux Launcher)
# Runs entirely from USB. Never installs anything on the host.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Launcher is at USB root, so USB_ROOT = SCRIPT_DIR
USB_ROOT="$SCRIPT_DIR"
RUNTIME_DIR="/tmp/cinder-runtime-$$"
OLLAMA_PORT=11435
OLLAMA_PID=""

cleanup() {
    if [ -n "$OLLAMA_PID" ] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "  Shutting down AI engine..."
        kill "$OLLAMA_PID" 2>/dev/null
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
    rm -rf "$RUNTIME_DIR" 2>/dev/null || true
    echo "  Cinder closed."
}
trap cleanup EXIT

echo ""
echo "  ========================================="
echo "   Cinder — Portable AI Companion"
echo "  ========================================="
echo ""

# ── Locate portable Ollama binary ────────────────────────
OLLAMA_SRC=""
for candidate in \
    "$USB_ROOT/Cinder/bin/linux/ollama" \
    "$USB_ROOT/bin/linux/ollama"; do
    if [ -f "$candidate" ]; then
        OLLAMA_SRC="$candidate"
        break
    fi
done

# Fallback: check system Ollama
if [ -z "$OLLAMA_SRC" ]; then
    if command -v ollama &>/dev/null; then
        echo "  Using system Ollama installation."
        OLLAMA_SRC="$(command -v ollama)"
    fi
fi

if [ -z "$OLLAMA_SRC" ]; then
    echo "  ERROR: Ollama not found."
    echo ""
    echo "  Cinder needs Ollama to run its AI model."
    echo "  Install: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Or place the binary in: $USB_ROOT/Cinder/bin/linux/"
    echo ""
    read -p "  Press Enter to exit..." _
    exit 1
fi

# ── Copy Ollama to temp (USB may be mounted noexec) ──────
echo "  Preparing AI engine..."
mkdir -p "$RUNTIME_DIR"
cp "$OLLAMA_SRC" "$RUNTIME_DIR/ollama"
chmod +x "$RUNTIME_DIR/ollama"

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
    "$RUNTIME_DIR/ollama" serve >"$RUNTIME_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!

    for i in $(seq 1 30); do
        if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
            break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "  ERROR: AI engine failed to start."
            echo "  Log: $RUNTIME_DIR/ollama.log"
            cat "$RUNTIME_DIR/ollama.log" 2>/dev/null | tail -10
            read -p "  Press Enter to exit..." _
            exit 1
        fi
        sleep 1
    done
    echo "  AI engine ready."
fi

# ── Load Cinder model if not already loaded ──────────────
if ! "$RUNTIME_DIR/ollama" list 2>/dev/null | grep -qi cinder; then
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
        (cd "$MODELFILE_DIR" && "$RUNTIME_DIR/ollama" create cinder -f "$(basename "$MODELFILE")")
        echo "  Model loaded."
    fi
fi

# ── Launch Cinder app ────────────────────────────────────
echo ""

# Try Linux binary in Cinder/Linux
LINUX_BIN="$USB_ROOT/Cinder/Linux/cinder-desktop"
if [ -f "$LINUX_BIN" ]; then
    cp "$LINUX_BIN" "$RUNTIME_DIR/cinder-desktop"
    chmod +x "$RUNTIME_DIR/cinder-desktop"
    echo "  Launching Cinder..."
    OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT" "$RUNTIME_DIR/cinder-desktop" --no-sandbox
    exit 0
fi

# Try AppImage
for appimg in "$USB_ROOT/Cinder/Linux/"*.AppImage; do
    if [ -f "$appimg" ]; then
        cp "$appimg" "$RUNTIME_DIR/cinder.AppImage"
        chmod +x "$RUNTIME_DIR/cinder.AppImage"
        echo "  Launching Cinder..."
        OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT" "$RUNTIME_DIR/cinder.AppImage" --no-sandbox
        exit 0
    fi
done

echo "  ERROR: Could not find Cinder app binary."
echo "  Checked: $USB_ROOT/Cinder/Linux/"
read -p "  Press Enter to exit..." _
exit 1
