#!/bin/bash
# ============================================================
# Cinder — Portable AI Companion (AnythingLLM Edition, macOS)
# Runs entirely from USB. Never installs anything on the host.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
echo "   AnythingLLM Edition"
echo "  ========================================="
echo ""

# ── Locate Ollama ────────────────────────────────────────
OLLAMA_BIN=""
for candidate in \
    "$USB_ROOT/ollama/mac/ollama" \
    "/usr/local/bin/ollama"; do
    if [ -f "$candidate" ]; then
        OLLAMA_BIN="$candidate"
        break
    fi
done

if [ -z "$OLLAMA_BIN" ]; then
    if command -v ollama &>/dev/null; then
        OLLAMA_BIN="$(command -v ollama)"
        echo "  Using system Ollama."
    fi
fi

if [ -z "$OLLAMA_BIN" ]; then
    echo "  ERROR: Ollama not found."
    echo "  Install from: https://ollama.com/download/mac"
    echo "  Or place the binary in: $USB_ROOT/ollama/mac/"
    read -p "  Press Enter to exit..." _
    exit 1
fi

# ── Set up model storage on USB ──────────────────────────
MODELS_DIR="$USB_ROOT/ollama/models"
mkdir -p "$MODELS_DIR"

export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
export OLLAMA_MODELS="$MODELS_DIR"

# ── Start Ollama if not running ──────────────────────────
if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
    echo "  AI engine already running on port $OLLAMA_PORT."
elif curl -s "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    OLLAMA_PORT=11434
    export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
    echo "  AI engine already running on default port."
else
    echo "  Starting AI engine..."
    "$OLLAMA_BIN" serve >/tmp/cinder-ollama.log 2>&1 &
    OLLAMA_PID=$!

    for i in $(seq 1 30); do
        if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
            break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "  ERROR: AI engine failed to start."
            tail -10 /tmp/cinder-ollama.log 2>/dev/null
            read -p "  Press Enter to exit..." _
            exit 1
        fi
        sleep 1
    done
    echo "  AI engine ready."
fi

# ── Load Cinder model if not present ─────────────────────
if ! "$OLLAMA_BIN" list 2>/dev/null | grep -qi cinder; then
    echo "  Loading Cinder model..."
    MODELFILE=""
    for mf in \
        "$USB_ROOT/cinder/Modelfile-final" \
        "$USB_ROOT/cinder/Modelfile-final-14b" \
        "$USB_ROOT/cinder/Modelfile-v3"; do
        if [ -f "$mf" ]; then
            MODELFILE="$mf"
            break
        fi
    done

    if [ -n "$MODELFILE" ]; then
        (cd "$(dirname "$MODELFILE")" && "$OLLAMA_BIN" create cinder -f "$(basename "$MODELFILE")")
        echo "  Cinder model loaded."
    else
        echo "  No Modelfile found — using base model."
    fi
fi

# ── Launch AnythingLLM ───────────────────────────────────
STORAGE_PATH="$USB_ROOT/anythingllm/storage"
mkdir -p "$STORAGE_PATH"

ALM_APP=""
if [ -d "$USB_ROOT/anythingllm/AnythingLLMDesktop.app" ]; then
    ALM_APP="$USB_ROOT/anythingllm/AnythingLLMDesktop.app"
fi

if [ -z "$ALM_APP" ]; then
    # Check for system-installed AnythingLLM
    if [ -d "/Applications/AnythingLLMDesktop.app" ]; then
        ALM_APP="/Applications/AnythingLLMDesktop.app"
        echo "  Using installed AnythingLLM."
    fi
fi

if [ -z "$ALM_APP" ]; then
    echo ""
    echo "  AnythingLLM Desktop not found on USB or system."
    echo ""
    echo "  Ollama and the Cinder model are ready!"
    echo "  To complete setup, install AnythingLLM Desktop:"
    echo "    https://anythingllm.com/download"
    echo ""
    DMG_FILE="$USB_ROOT/anythingllm/AnythingLLMDesktop.dmg"
    if [ -f "$DMG_FILE" ]; then
        echo "  Or install from the DMG on this USB:"
        echo "    open \"$DMG_FILE\""
        echo "  Then drag to Applications and re-run this launcher."
    fi
    echo ""
    echo "  After installing, run this launcher again."
    echo "  Or open AnythingLLM manually and set:"
    echo "    LLM Provider: Ollama"
    echo "    Model: cinder"
    echo "    Ollama URL: http://127.0.0.1:$OLLAMA_PORT"
    echo ""
    read -p "  Press Enter to exit..." _
    exit 0
fi

echo "  Launching Cinder (AnythingLLM)..."
echo "  Data stored on USB at: $STORAGE_PATH"
echo ""

export STORAGE_DIR="$STORAGE_PATH"
export LLM_PROVIDER="ollama"
export OLLAMA_BASE_PATH="http://127.0.0.1:$OLLAMA_PORT"

open "$ALM_APP" --args --start-maximized --env STORAGE_DIR="$STORAGE_PATH" 2>/dev/null || open "$ALM_APP" --args --start-maximized
