#!/bin/bash
# CINDER_LAUNCHER_VERSION=1   # bump + republish manifest to push patches
echo "  Cinder - Your Personal AI Companion"

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
        REMOTE_VER=$(printf '%s' "$MANIFEST" | grep -o '"linux_version"[[:space:]]*:[[:space:]]*[0-9]\+' | grep -o '[0-9]\+$' | head -1)
        REMOTE_URL=$(printf '%s' "$MANIFEST" | grep -o '"linux_url"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
        REMOTE_SHA=$(printf '%s' "$MANIFEST" | grep -o '"linux_sha256"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
        if [ -n "$REMOTE_VER" ] && [ "$REMOTE_VER" -gt "$LAUNCHER_VERSION" ] && [ -n "$REMOTE_URL" ] && [ -n "$REMOTE_SHA" ]; then
            TMP="${SELF}.new"
            if curl -fsS --max-time 30 -o "$TMP" "$REMOTE_URL" 2>/dev/null; then
                ACTUAL_SHA=$(sha256sum "$TMP" 2>/dev/null | awk '{print $1}')
                [ -z "$ACTUAL_SHA" ] && ACTUAL_SHA=$(shasum -a 256 "$TMP" 2>/dev/null | awk '{print $1}')
                if [ "$ACTUAL_SHA" = "$REMOTE_SHA" ] && [ -s "$TMP" ] && head -1 "$TMP" | grep -q '^#!'; then
                    chmod +x "$TMP" 2>/dev/null
                    mv "$TMP" "$SELF" 2>/dev/null && {
                        echo "  [OK] Launcher updated to v$REMOTE_VER — relaunching"
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
for mount in /media/$USER/CINDER-APP /mnt/CINDER-APP /run/media/$USER/CINDER-APP; do
    [ -d "$mount/Cinder/Linux" ] && APP_DIR="$mount" && break
done
if [ -z "$APP_DIR" ]; then
    # Distros without a desktop auto-mounter (or with a label-name mismatch)
    # leave us here. Tell the user exactly what to do next instead of dying silent.
    DEV=$(lsblk -o NAME,LABEL -nr 2>/dev/null | awk '$2=="CINDER-APP"{print "/dev/"$1}' | head -1)
    if [ -n "$DEV" ]; then
        echo "ERROR: CINDER-APP partition found at $DEV but not auto-mounted."
        echo "Mount it manually, then re-run this launcher:"
        echo "  sudo mkdir -p /mnt/CINDER-APP"
        echo "  sudo mount $DEV /mnt/CINDER-APP"
    else
        echo "ERROR: CINDER-APP partition not detected."
        echo "  - Make sure the Cinder USB is plugged in."
        echo "  - Try unplugging and replugging the drive."
        echo "  - If the problem persists, the partition table may be damaged;"
        echo "    re-flash the latest Cinder image with Etcher or dd."
    fi
    read -p "Press Enter to close..." _
    exit 1
fi
# Ubuntu, Pop!_OS, Fedora, and most modern desktop distros mount removable
# vfat/exfat with noexec by default. Without this check, both ollama and
# cinder-desktop will fail with "Permission denied" and the user has no idea
# why. Detect early and give a concrete remount command.
APP_OPTS=$(findmnt -no OPTIONS --target "$APP_DIR" 2>/dev/null)
if echo ",$APP_OPTS," | grep -q ',noexec,'; then
    APP_DEV=$(findmnt -no SOURCE --target "$APP_DIR" 2>/dev/null)
    echo ""
    echo "ERROR: USB is mounted noexec — Linux can't run the Cinder binary from it."
    echo "       (Ubuntu/Pop/Fedora set this for removable media by default.)"
    echo ""
    echo "FIX (one-time, requires admin password):"
    echo "  sudo mount -o remount,exec $APP_DIR"
    echo ""
    echo "Then re-run this launcher: bash \"$0\""
    read -p "Press Enter to close..." _
    exit 1
fi
# Portable storage — keep all user data on the USB, not the host machine.
# Prefer CINDERVAULT (the visible "vault" partition); fall back to CINDER-APP.
# Auto-mount can lag a few seconds behind plug-in, so retry briefly.
VAULT_DIR=""
for _ in 1 2 3 4 5; do
    for mount in /media/$USER/CINDERVAULT /mnt/CINDERVAULT /run/media/$USER/CINDERVAULT; do
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
# Without it, ollama writes ~/.ollama on the host — violating the
# "USB-only, never install on host" rule and leaving artifacts on every
# Linux machine the buyer plugs into.
export OLLAMA_HOME="$APP_DIR/Cinder/ollama"
export OLLAMA_MODELS="$APP_DIR/Cinder/ollama/models"
export OLLAMA_HOST="127.0.0.1:11436"
export OLLAMA_BASE_PATH="http://127.0.0.1:11436"
export OLLAMA_MODEL_PREF="cinder"
export LLM_PROVIDER="ollama"
export EMBEDDING_ENGINE="native"
# Verify the ollama binary is actually on the USB before trying to spawn it.
# A corrupted .img flash can land cinder-desktop without ollama, in which
# case `ollama serve` silently fails and the buyer just sees a blank chat
# with no clue why.
if [ ! -x "$APP_DIR/Cinder/ollama/ollama" ]; then
    echo ""
    echo "ERROR: ollama binary missing from USB at $APP_DIR/Cinder/ollama/ollama"
    echo "       The image may be corrupted. Re-flash the latest Cinder image."
    read -p "Press Enter to close..." _
    exit 1
fi
# If port 11436 is already serving, reuse it. A previous run that exited
# without firing the trap (sigkill, terminal closed, kernel oom) can leave
# an orphan ollama on 11436 — without this check, the new spawn fails to
# bind and the polling loop times out, leaving the buyer with a blank chat.
# Verify the listener actually IS ollama (returns a /api/tags JSON with a
# "models" key) — otherwise an unrelated app on 11436 would be silently
# treated as our backend and Cinder would hang on garbage replies.
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
# Poll for ollama to come up (up to 8s) instead of a fixed sleep — first-launch
# on a slow USB can take longer than 3s, and a fixed sleep means Cinder loads
# before ollama is ready and the buyer sees a blank chat.
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
# Verify cinder-desktop binary actually exists before trying to launch it.
# Without this check, a corrupted .img flash that landed ollama but not
# cinder-desktop would fail with a confusing "No such file" deep in the
# script after the buyer has already waited through the ollama startup.
if [ ! -f "$APP_DIR/Cinder/Linux/cinder-desktop" ]; then
    echo ""
    echo "ERROR: cinder-desktop binary missing at $APP_DIR/Cinder/Linux/cinder-desktop"
    echo "       The image may be corrupted. Re-flash the latest Cinder image."
    read -p "Press Enter to close..." _
    exit 1
fi
cd "$APP_DIR/Cinder/Linux" && chmod +x cinder-desktop
echo "Cinder running."
# Run cinder-desktop in foreground so the script exits when the user quits it.
"$APP_DIR/Cinder/Linux/cinder-desktop"
