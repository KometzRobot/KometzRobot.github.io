#!/bin/bash
# ============================================================
# Cinder — Portable AI Companion (AnythingLLM Edition, Linux)
# Runs entirely from USB. Never installs anything on the host.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
echo "   AnythingLLM Edition"
echo "  ========================================="
echo ""

# ── Locate portable Ollama binary ────────────────────────
OLLAMA_BIN=""
for candidate in \
    "$USB_ROOT/ollama/linux/ollama" \
    "$USB_ROOT/Cinder/bin/linux/ollama"; do
    if [ -f "$candidate" ]; then
        OLLAMA_BIN="$candidate"
        break
    fi
done

if [ -z "$OLLAMA_BIN" ]; then
    if command -v ollama &>/dev/null; then
        echo "  Using system Ollama."
        OLLAMA_BIN="$(command -v ollama)"
    fi
fi

if [ -z "$OLLAMA_BIN" ]; then
    echo "  ERROR: Ollama not found on USB or system."
    echo "  Install: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Or place the binary in: $USB_ROOT/ollama/linux/"
    read -p "  Press Enter to exit..." _
    exit 1
fi

# ── Copy Ollama to temp (USB may be mounted noexec) ──────
echo "  Preparing AI engine..."
mkdir -p "$RUNTIME_DIR"
cp "$OLLAMA_BIN" "$RUNTIME_DIR/ollama"
chmod +x "$RUNTIME_DIR/ollama"

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
    echo "  Starting AI engine (portable, from USB)..."
    "$RUNTIME_DIR/ollama" serve >"$RUNTIME_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!

    for i in $(seq 1 30); do
        if curl -s "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
            break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "  ERROR: AI engine failed to start. Check log:"
            tail -10 "$RUNTIME_DIR/ollama.log" 2>/dev/null
            read -p "  Press Enter to exit..." _
            exit 1
        fi
        sleep 1
    done
    echo "  AI engine ready."
fi

# ── Load Cinder model if not present ─────────────────────
if ! "$RUNTIME_DIR/ollama" list 2>/dev/null | grep -qi cinder; then
    echo "  Loading Cinder model (first time may take a minute)..."
    MODELFILE=""
    for mf in \
        "$USB_ROOT/cinder/Modelfile-final" \
        "$USB_ROOT/cinder/Modelfile-final-14b" \
        "$USB_ROOT/cinder/Modelfile-v3" \
        "$USB_ROOT/cinder/Modelfile"; do
        if [ -f "$mf" ]; then
            MODELFILE="$mf"
            break
        fi
    done

    if [ -n "$MODELFILE" ]; then
        MODELFILE_DIR="$(dirname "$MODELFILE")"
        (cd "$MODELFILE_DIR" && "$RUNTIME_DIR/ollama" create cinder -f "$(basename "$MODELFILE")")
        echo "  Cinder model loaded."
    else
        echo "  No Modelfile found — using base model."
    fi
fi

# ── Launch AnythingLLM ───────────────────────────────────
STORAGE_PATH="$USB_ROOT/anythingllm/storage"
mkdir -p "$STORAGE_PATH"

APPIMAGE=""
for candidate in \
    "$USB_ROOT/anythingllm/AnythingLLMDesktop.AppImage" \
    "$USB_ROOT/anythingllm/"*.AppImage; do
    if [ -f "$candidate" ]; then
        APPIMAGE="$candidate"
        break
    fi
done

if [ -z "$APPIMAGE" ]; then
    echo "  ERROR: AnythingLLM AppImage not found."
    echo "  Expected at: $USB_ROOT/anythingllm/AnythingLLMDesktop.AppImage"
    read -p "  Press Enter to exit..." _
    exit 1
fi

echo "  Launching Cinder (AnythingLLM)..."
echo "  Data stored on USB at: $STORAGE_PATH"
echo ""

# Copy AppImage to temp (noexec workaround)
cp "$APPIMAGE" "$RUNTIME_DIR/AnythingLLM.AppImage"
chmod +x "$RUNTIME_DIR/AnythingLLM.AppImage"

# Create portable home directory on USB (keeps all data on USB)
PORTABLE_HOME="$USB_ROOT/anythingllm/AnythingLLMDesktop.AppImage.home"
mkdir -p "$PORTABLE_HOME"

# Set storage to USB and point Ollama to our portable instance
export STORAGE_DIR="$STORAGE_PATH"
export HOME="$PORTABLE_HOME"
export LLM_PROVIDER="ollama"
export OLLAMA_BASE_PATH="http://127.0.0.1:$OLLAMA_PORT"

"$RUNTIME_DIR/AnythingLLM.AppImage" --no-sandbox --start-maximized
