#!/bin/bash
# CINDER_LAUNCHER_VERSION=1   # bump + republish manifest to push patches

# ──────────────────────────────────────────────────────────────────────
# Self-update: pull launcher patches from the manifest on every plug-in.
# Silent on offline/failure. SHA256-verified. Skip with
# CINDER_NO_SELF_UPDATE=1. The 4 drives that shipped before this hook
# stay as-is; future flashes inherit the patch path.
# ──────────────────────────────────────────────────────────────────────
LAUNCHER_VERSION=1
MANIFEST_URL="https://kometzrobot.github.io/cinder/launchers/manifest.json"
if [ -z "${CINDER_NO_SELF_UPDATE:-}" ] && command -v curl >/dev/null 2>&1; then
    SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
    MANIFEST=$(curl -fsS --max-time 5 "$MANIFEST_URL" 2>/dev/null) || MANIFEST=""
    if [ -n "$MANIFEST" ]; then
        REMOTE_VER=$(printf '%s' "$MANIFEST" | grep -o '"mac_version"[[:space:]]*:[[:space:]]*[0-9]\+' | grep -o '[0-9]\+$' | head -1)
        REMOTE_URL=$(printf '%s' "$MANIFEST" | grep -o '"mac_url"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
        REMOTE_SHA=$(printf '%s' "$MANIFEST" | grep -o '"mac_sha256"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
        if [ -n "$REMOTE_VER" ] && [ "$REMOTE_VER" -gt "$LAUNCHER_VERSION" ] && [ -n "$REMOTE_URL" ] && [ -n "$REMOTE_SHA" ]; then
            TMP="${SELF}.new"
            if curl -fsS --max-time 30 -o "$TMP" "$REMOTE_URL" 2>/dev/null; then
                ACTUAL_SHA=$(shasum -a 256 "$TMP" 2>/dev/null | awk '{print $1}')
                [ -z "$ACTUAL_SHA" ] && ACTUAL_SHA=$(sha256sum "$TMP" 2>/dev/null | awk '{print $1}')
                if [ "$ACTUAL_SHA" = "$REMOTE_SHA" ] && [ -s "$TMP" ] && head -1 "$TMP" | grep -q '^#!'; then
                    chmod +x "$TMP" 2>/dev/null
                    mv "$TMP" "$SELF" 2>/dev/null && {
                        export CINDER_NO_SELF_UPDATE=1
                        exec "$SELF" "$@"
                    }
                fi
                rm -f "$TMP" 2>/dev/null
            fi
        fi
    fi
fi
# ──────────────────────────────────────────────────────────────────────

APP_DIR=""
for mount in /Volumes/CINDER-APP /media/$USER/CINDER-APP; do
    [ -d "$mount/Cinder/Mac/Cinder.app" ] && APP_DIR="$mount" && break
done
if [ -z "$APP_DIR" ]; then
    osascript -e 'display alert "Cinder for Mac" message "This 1.0 BETA ships with Windows + Linux launchers only. The Mac build will land in 1.1. If you have a Mac and a Windows or Linux machine, please use the other launcher for now."' 2>/dev/null
    exit 1
fi
# Portable storage — user data on the USB, not the host machine. Prefer
# CINDERVAULT (the visible "vault" partition) so journals/conversations/memory
# end up where the buyer expects; fall back to CINDER-APP if it's missing.
# diskarbitrationd can take 2-4s to mount the vault partition behind the
# already-mounted boot partition, so retry briefly before giving up.
VAULT_DIR=""
for _ in 1 2 3 4 5; do
    for mount in /Volumes/CINDERVAULT /media/$USER/CINDERVAULT; do
        [ -d "$mount" ] && VAULT_DIR="$mount" && break 2
    done
    sleep 1
done
if [ -n "$VAULT_DIR" ]; then
    export STORAGE_DIR="$VAULT_DIR/cinder-data"
    mkdir -p "$STORAGE_DIR"
else
    export STORAGE_DIR="$APP_DIR/Cinder/data"
fi
# OLLAMA_HOME isolates ollama's keys, history, and runtime dir to the USB.
# Without it, ollama writes ~/.ollama on the host — violating Joel's
# "USB-only, never install on host" rule and leaving artifacts behind on
# every Mac the buyer plugs into.
export OLLAMA_HOME="$APP_DIR/Cinder/ollama"
export OLLAMA_MODELS="$APP_DIR/Cinder/ollama/models"
export OLLAMA_HOST="127.0.0.1:11436"
export OLLAMA_BASE_PATH="http://127.0.0.1:11436"
export OLLAMA_MODEL_PREF="cinder"
export LLM_PROVIDER="ollama"
export EMBEDDING_ENGINE="native"
# Verify the ollama binary is actually on the USB before trying to spawn it.
# A corrupted .img flash can land cinder-desktop without ollama, in which
# case `ollama serve` would silently fail and the buyer would just see a
# blank chat with no clue why.
if [ ! -x "$APP_DIR/Cinder/ollama/ollama" ]; then
    osascript -e 'display alert "Cinder" message "The ollama binary is missing from the USB. The image may be corrupted — re-flash from the latest Cinder image."' 2>/dev/null
    echo "ERROR: ollama binary missing at $APP_DIR/Cinder/ollama/ollama"
    exit 1
fi
# If port 11436 is already serving (orphan from a crashed prior session, or a
# second Cinder window), reuse it instead of fighting for the bind. Windows
# already does this via netstat — Mac was missing the check, so a leftover
# ollama from a hard-quit could leave the new launch stuck behind a "blank
# chat" while two ollamas raced for the port.
# Verify the listener actually IS ollama (returns a /api/tags JSON shape with
# a "models" key) — otherwise an unrelated app on 11436 would be silently
# treated as our backend and Cinder would just hang on garbage replies.
OLLAMA_PID=""
if curl -fsS --max-time 1 http://127.0.0.1:11436/api/tags 2>/dev/null | grep -q '"models"'; then
    echo "ollama already running on 11436 — reusing existing instance"
else
    "$APP_DIR/Cinder/ollama/ollama" serve > "$STORAGE_DIR/cinder-ollama.log" 2>&1 &
    OLLAMA_PID=$!
fi
# Reap ollama whenever this script exits — only if WE started it. Don't kill
# a pre-existing ollama the user may have left running for a reason.
trap '[ -n "$OLLAMA_PID" ] && kill $OLLAMA_PID 2>/dev/null' EXIT
# Poll for ollama to come up (up to 8s) instead of guessing 3s. On older
# MacBooks the first /api/tags call after spawn can take 4-6s.
for _ in 1 2 3 4 5 6 7 8; do
    if curl -fsS --max-time 1 http://127.0.0.1:11436/api/tags >/dev/null 2>&1; then break; fi
    sleep 1
done
# Verify the cinder model is reachable so a missing/corrupt blob doesn't
# manifest as a silent chat hang. Log to vault next to ollama.log.
{
    if curl -fsS --max-time 2 http://127.0.0.1:11436/api/tags 2>/dev/null | grep -q '"name":"cinder'; then
        echo "OK: ollama up, cinder model present"
    else
        echo "WARN: cinder model not found in /api/tags. Chat will fail until model is restored."
    fi
} > "$STORAGE_DIR/cinder-prelaunch.log" 2>&1
# `open -W` blocks until Cinder.app fully quits, so trap fires at the right time.
open -W "$APP_DIR/Cinder/Mac/Cinder.app"
