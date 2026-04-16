#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Cinder USB Image Builder
# Creates a flashable .img file with 3 partitions:
#   1. APP   (8GB exFAT)  — Cinder app, models, launcher
#   2. VAULT (8GB VeraCrypt) — Encrypted memory, passwords, sensitive data
#   3. USER  (16GB exFAT) — User storage, drop zone for Cinder
# Total: ~32GB (fits on 64GB USB with room to spare)
#
# Usage: sudo bash build-usb-image.sh [output.img]
# Flash: sudo dd if=cinder-usb.img of=/dev/sdX bs=4M status=progress
#    or: Use Balena Etcher (cross-platform GUI)
# ═══════════════════════════════════════════════════════════════

set -e

IMG="${1:-cinder-usb.img}"
APP_SIZE_MB=8192      # 8GB for app + models
VAULT_SIZE_MB=8192    # 8GB encrypted vault
USER_SIZE_MB=16384    # 16GB user storage
TOTAL_MB=$((APP_SIZE_MB + VAULT_SIZE_MB + USER_SIZE_MB + 16))  # +16MB for partition table

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
MOUNT_BASE="/tmp/cinder-build"

echo "═══════════════════════════════════════════════════════"
echo "  Cinder USB Image Builder"
echo "  Output: $IMG"
echo "  Size: ${TOTAL_MB}MB (~$((TOTAL_MB/1024))GB)"
echo "═══════════════════════════════════════════════════════"

# Check dependencies
for cmd in dd mkfs.exfat parted veracrypt; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: $cmd not found. Install it first."
        exit 1
    fi
done

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Must run as root (sudo)."
    exit 1
fi

# ── Step 1: Create blank image ────────────────────────────
echo ""
echo "[1/6] Creating ${TOTAL_MB}MB blank image..."
dd if=/dev/zero of="$IMG" bs=1M count=$TOTAL_MB status=progress 2>&1

# ── Step 2: Create partition table ────────────────────────
echo ""
echo "[2/6] Creating partition table..."
parted -s "$IMG" mklabel gpt
parted -s "$IMG" mkpart CINDER-APP 1MiB $((APP_SIZE_MB + 1))MiB
parted -s "$IMG" mkpart CINDER-VAULT $((APP_SIZE_MB + 1))MiB $((APP_SIZE_MB + VAULT_SIZE_MB + 1))MiB
parted -s "$IMG" mkpart CINDER-USER $((APP_SIZE_MB + VAULT_SIZE_MB + 1))MiB 100%

# ── Step 3: Set up loop device ────────────────────────────
echo ""
echo "[3/6] Setting up loop device..."
LOOP=$(losetup --find --show --partscan "$IMG")
echo "Loop device: $LOOP"

# Wait for partitions
sleep 2
ls ${LOOP}p* 2>/dev/null || { echo "ERROR: Partitions not detected"; losetup -d "$LOOP"; exit 1; }

# ── Step 4: Format partitions ─────────────────────────────
echo ""
echo "[4/6] Formatting partitions..."
mkfs.exfat -n "CINDER-APP" "${LOOP}p1"
# Vault partition left raw — VeraCrypt will format it on first use
echo "  Vault partition left raw for VeraCrypt initialization"
mkfs.exfat -n "CINDER-USER" "${LOOP}p3"

# ── Step 5: Populate APP partition ────────────────────────
echo ""
echo "[5/6] Populating app partition..."
mkdir -p "$MOUNT_BASE/app"
mount "${LOOP}p1" "$MOUNT_BASE/app"

# Create directory structure
mkdir -p "$MOUNT_BASE/app/"{models,scripts,identity,memory,archive}
mkdir -p "$MOUNT_BASE/app/app"  # Electron app goes here

# Copy Electron app
if [ -d "$SCRIPT_DIR/renderer" ]; then
    cp -r "$SCRIPT_DIR/main.js" "$MOUNT_BASE/app/app/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/preload.js" "$MOUNT_BASE/app/app/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/package.json" "$MOUNT_BASE/app/app/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/renderer" "$MOUNT_BASE/app/app/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/assets" "$MOUNT_BASE/app/app/" 2>/dev/null || true
fi

# Copy Cinder model files
CINDER_MODEL="$SCRIPT_DIR/models/Modelfile"
if [ -f "$CINDER_MODEL" ]; then
    cp "$CINDER_MODEL" "$MOUNT_BASE/app/models/Modelfile"
    echo "  Copied Cinder Modelfile"
fi

# Copy model weights (.gguf) — export from Ollama if available
CINDER_BLOB="/usr/share/ollama/.ollama/models/blobs/sha256-6319ff34a050b0f2a1587fcfb7a41ed57e2307c75b0014f7b416cc60e2e33055"
if [ -f "$CINDER_BLOB" ]; then
    echo "  Copying model weights (1.8GB)..."
    cp "$CINDER_BLOB" "$MOUNT_BASE/app/models/cinder.gguf"
    echo "  Model weights copied"
else
    echo "  WARNING: Model weights not found at $CINDER_BLOB"
    echo "  Users will need to pull model manually: ollama pull qwen2.5:3b"
fi

# Copy identity files
for f in lineage.md personality.md; do
    [ -f "$REPO_DIR/$f" ] && cp "$REPO_DIR/$f" "$MOUNT_BASE/app/identity/"
done

# Copy launcher scripts
cat > "$MOUNT_BASE/app/launch.sh" << 'LAUNCHER'
#!/bin/bash
# Cinder USB Launcher — Linux/macOS
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "╔══════════════════════════════════════╗"
echo "║         CINDER — Portable AI         ║"
echo "╚══════════════════════════════════════╝"

# Check Ollama
if ! command -v ollama &>/dev/null; then
    echo "Ollama not found. Install from: https://ollama.com"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

# Load Cinder model if not already loaded
if ! ollama list | grep -q "cinder"; then
    echo "Loading Cinder model..."
    if [ -f "$SCRIPT_DIR/models/cinder.gguf" ]; then
        ollama create cinder -f "$SCRIPT_DIR/models/Modelfile"
    else
        echo "Model weights not found. Pull base model first:"
        echo "  ollama pull qwen2.5:3b"
        exit 1
    fi
fi

# Launch Electron app if available
if [ -d "$SCRIPT_DIR/app/node_modules" ]; then
    cd "$SCRIPT_DIR/app"
    npx electron . &
else
    # Fallback: direct Ollama chat
    echo "Starting Cinder in terminal mode..."
    ollama run cinder
fi
LAUNCHER
chmod +x "$MOUNT_BASE/app/launch.sh"

cat > "$MOUNT_BASE/app/launch.bat" << 'WINLAUNCHER'
@echo off
echo ========================================
echo          CINDER - Portable AI
echo ========================================
echo.

where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo Ollama not found. Download from: https://ollama.com
    pause
    exit /b 1
)

echo Loading Cinder model...
ollama create cinder -f "%~dp0models\Modelfile"
echo Starting Cinder...
cd /d "%~dp0app"
npx electron .
WINLAUNCHER

# Copy README
cp "$REPO_DIR/docs/cinder-usb-README.md" "$MOUNT_BASE/app/README.md" 2>/dev/null || true

# Create QUICKSTART.txt
cat > "$MOUNT_BASE/app/QUICKSTART.txt" << 'QS'
CINDER — Quick Start (3 Steps)
================================

1. Install Ollama from https://ollama.com
   - Windows: Download + run installer
   - Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh

2. Open a terminal/command prompt in this folder

3. Run the launcher:
   - Windows: double-click launch.bat
   - Linux/Mac: ./launch.sh

That's it. Cinder will load and start.

First launch will ask you to set a password.
This password protects your Cinder memory and vault.
There is no recovery — choose wisely.
QS

echo "  App partition populated"

# Populate USER partition
mkdir -p "$MOUNT_BASE/user"
mount "${LOOP}p3" "$MOUNT_BASE/user"
mkdir -p "$MOUNT_BASE/user/"{Documents,Projects}
cat > "$MOUNT_BASE/user/README.txt" << 'USERREADME'
CINDER USER STORAGE
===================
Place files here for Cinder to read.
- Documents/  — text, PDFs, notes
- Projects/   — code, data files

Cinder can access files in this partition when running.
USERREADME
echo "  User partition populated"

# ── Step 6: Clean up ─────────────────────────────────────
echo ""
echo "[6/6] Cleaning up..."
umount "$MOUNT_BASE/app" 2>/dev/null || true
umount "$MOUNT_BASE/user" 2>/dev/null || true
losetup -d "$LOOP"
rmdir "$MOUNT_BASE/app" "$MOUNT_BASE/user" "$MOUNT_BASE" 2>/dev/null || true

# Show result
SIZE=$(du -h "$IMG" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  BUILD COMPLETE"
echo "  Image: $IMG ($SIZE)"
echo "  Partitions:"
echo "    1. CINDER-APP  (${APP_SIZE_MB}MB exFAT) — app + models"
echo "    2. CINDER-VAULT (${VAULT_SIZE_MB}MB raw) — init with VeraCrypt"
echo "    3. CINDER-USER (${USER_SIZE_MB}MB exFAT) — user storage"
echo ""
echo "  Flash to USB:"
echo "    sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "    or use Balena Etcher"
echo ""
echo "  Vault initialization (first time on target USB):"
echo "    veracrypt --create /dev/sdX2 --size ${VAULT_SIZE_MB}M"
echo "═══════════════════════════════════════════════════════"
