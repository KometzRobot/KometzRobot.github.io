#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# DEPRECATED: Use products/cinder-anythingllm/build-usb-image.sh instead.
# This Electron version is superseded by the AnythingLLM fork.
# ═══════════════════════════════════════════════════════════════
echo "DEPRECATED: Use products/cinder-anythingllm/build-usb-image.sh instead."
echo "This old Electron builder is no longer maintained."
exit 1
# ═══════════════════════════════════════════════════════════════
# OLD: Cinder USB Image Builder v4 — Electron + Multi-Partition
# Creates a flashable .img with THREE partitions:
#   P1: exfat  "CINDER"     — app (Win/Linux/Mac), models, tools
#   P2: ext4   "CINDER-SYS" — identity, memory, config (Linux r/w)
#   P3: (raw)  "VAULT"      — user formats with VeraCrypt
#
# Windows sees P1 (exfat), prompts to reformat P2/P3 (ignore).
# Linux/Mac sees all three.
#
# Usage: sudo bash build-usb-image.sh [output.img]
# Flash: sudo dd if=cinder-usb.img of=/dev/sdX bs=4M status=progress
#    or: Use Balena Etcher (cross-platform GUI)
# ═══════════════════════════════════════════════════════════════

set -e

IMG="${1:-/mnt/data1/cinder-usb.img}"
TOTAL_MB=57344  # 56GB — fits 64GB USB with margin

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
MNT_APP="/tmp/cinder-p1"
MNT_SYS="/tmp/cinder-p2"

# Partition sizes
P1_END_MB=47104    # ~46GB for app partition
P2_END_MB=53248    # ~6GB for system partition
# P3: remainder (~3GB) for vault

# Source: use Electron dist builds from repo
DIST_DIR="$SCRIPT_DIR/dist"
if [ ! -d "$DIST_DIR/win-unpacked" ] && [ ! -d "$DIST_DIR/linux-unpacked" ]; then
    echo "ERROR: No Electron dist builds found at $DIST_DIR"
    echo "Run 'npm run build' in products/cinder-app/ first."
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "  Cinder USB Image Builder v4 (Electron + Multi-Partition)"
echo "  Output: $IMG"
echo "  Size: ${TOTAL_MB}MB (~$((TOTAL_MB/1024))GB)"
echo "  Source: $DIST_DIR"
echo "═══════════════════════════════════════════════════════"
echo "  P1: exfat  CINDER     (${P1_END_MB}MB) — app + models"
echo "  P2: ext4   CINDER-SYS ($((P2_END_MB-P1_END_MB))MB) — identity/memory"
echo "  P3: raw    VAULT      ($((TOTAL_MB-P2_END_MB))MB) — VeraCrypt"
echo "═══════════════════════════════════════════════════════"

for cmd in mkfs.exfat mkfs.ext4 parted losetup; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: $cmd not found."
        exit 1
    fi
done

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Must run as root (sudo)."
    exit 1
fi

# ── Step 1: Create sparse image ──────────────────────────
echo ""
echo "[1/6] Creating ${TOTAL_MB}MB sparse image..."
truncate -s ${TOTAL_MB}M "$IMG"
echo "  Done (sparse — fast)"

# ── Step 2: Partition table (GPT, 3 partitions) ─────────
echo ""
echo "[2/6] Creating GPT partition table..."
parted -s "$IMG" mklabel gpt
parted -s "$IMG" mkpart CINDER     1MiB ${P1_END_MB}MiB
parted -s "$IMG" mkpart CINDER-SYS ${P1_END_MB}MiB ${P2_END_MB}MiB
parted -s "$IMG" mkpart VAULT      ${P2_END_MB}MiB 100%
echo "  3 partitions created"

# ── Step 3: Loop mount + format ──────────────────────────
echo ""
echo "[3/6] Formatting partitions..."
LOOP=$(losetup --find --show --partscan "$IMG")
echo "  Loop device: $LOOP"
sleep 2
ls ${LOOP}p1 ${LOOP}p2 ${LOOP}p3 2>/dev/null || { echo "ERROR: Partitions not detected"; losetup -d "$LOOP"; exit 1; }

mkfs.exfat -n "CINDER" "${LOOP}p1"
mkfs.ext4 -L "CINDER-SYS" -q "${LOOP}p2"
# P3 left raw for VeraCrypt
echo "  P1: exfat, P2: ext4, P3: raw (VeraCrypt)"

# ── Step 4: Mount and populate P1 (main app) ────────────
echo ""
echo "[4/6] Populating P1 (app partition)..."
mkdir -p "$MNT_APP" "$MNT_SYS"
mount "${LOOP}p1" "$MNT_APP"
mount "${LOOP}p2" "$MNT_SYS"

# Copy Electron app builds
echo "  Copying Windows build (~270MB)..."
mkdir -p "$MNT_APP/Cinder/Windows"
if [ -d "$DIST_DIR/win-unpacked" ]; then
    cp -r --no-preserve=ownership "$DIST_DIR/win-unpacked/"* "$MNT_APP/Cinder/Windows/"
    echo "    Copied win-unpacked ($(du -sh "$DIST_DIR/win-unpacked" | cut -f1))"
elif [ -f "$DIST_DIR/Cinder 1.0.0.exe" ]; then
    cp "$DIST_DIR/Cinder 1.0.0.exe" "$MNT_APP/Cinder/Windows/"
    echo "    Copied portable exe"
fi

echo "  Copying Linux build (~260MB)..."
mkdir -p "$MNT_APP/Cinder/Linux"
if [ -f "$DIST_DIR/Cinder-1.0.0.AppImage" ]; then
    cp "$DIST_DIR/Cinder-1.0.0.AppImage" "$MNT_APP/Cinder/Linux/"
    chmod +x "$MNT_APP/Cinder/Linux/Cinder-1.0.0.AppImage"
    echo "    Copied AppImage"
fi
if [ -d "$DIST_DIR/linux-unpacked" ]; then
    cp -r --no-preserve=ownership "$DIST_DIR/linux-unpacked/"* "$MNT_APP/Cinder/Linux/"
    echo "    Copied linux-unpacked ($(du -sh "$DIST_DIR/linux-unpacked" | cut -f1))"
fi

echo "  Copying Mac build (~240MB)..."
mkdir -p "$MNT_APP/Cinder/Mac"
if [ -d "$DIST_DIR/mac/Cinder.app" ]; then
    # Zip to preserve symlinks on exfat
    (cd "$DIST_DIR/mac" && zip -ry "$MNT_APP/Cinder/Mac/Cinder.zip" "Cinder.app" >/dev/null)
    echo "    Zipped Cinder.app (symlinks preserved for exfat)"
fi

# Copy Modelfile and data
mkdir -p "$MNT_APP/Cinder/data"
cp "$SCRIPT_DIR/Modelfile-final" "$MNT_APP/Cinder/data/Modelfile" 2>/dev/null || true
cp "$SCRIPT_DIR/Modelfile-final" "$MNT_APP/Cinder/data/Modelfile-7b" 2>/dev/null || true
[ -f "$SCRIPT_DIR/Modelfile-final-14b" ] && cp "$SCRIPT_DIR/Modelfile-final-14b" "$MNT_APP/Cinder/data/Modelfile-14b" 2>/dev/null
[ -f "$SCRIPT_DIR/Modelfile-pkd" ] && cp "$SCRIPT_DIR/Modelfile-pkd" "$MNT_APP/Cinder/data/Modelfile-pkd" 2>/dev/null
echo "  Copied Modelfile(s) (7b, 14b, PKD)"

# Copy memory scripts
mkdir -p "$MNT_APP/Cinder/scripts"
cp "$SCRIPT_DIR/scripts/"*.py "$MNT_APP/Cinder/scripts/" 2>/dev/null || true
echo "  Copied memory scripts"

# Tools directory — add APKs if available
mkdir -p "$MNT_APP/Tools"
if [ -d "$REPO_DIR/products/apk-builds" ]; then
    mkdir -p "$MNT_APP/Tools/APKs"
    cp "$REPO_DIR/products/apk-builds/"*.apk "$MNT_APP/Tools/APKs/" 2>/dev/null
    echo "  Included APK apps"
fi

# UserFiles directory
mkdir -p "$MNT_APP/UserFiles/"{Documents,Projects}

# ── Launchers ──
cat > "$MNT_APP/Launch Cinder.bat" << 'WINLAUNCHER'
@echo off
title Cinder - Portable AI Companion
echo ========================================
echo          CINDER - Portable AI
echo ========================================
echo.

:: Check for Ollama
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo Ollama not found.
    echo Download from: https://ollama.com
    echo.
    echo After installing, run this again.
    pause
    exit /b 1
)

:: Start Ollama if not running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe" >nul
if %errorlevel% neq 0 (
    echo Starting Ollama...
    start /B ollama serve
    timeout /t 3 >nul
)

:: Model selection — check if cinder model exists
ollama list 2>nul | find /I "cinder" >nul
if %errorlevel% neq 0 (
    echo.
    echo Choose your Cinder model:
    echo   [1] Standard 7B  (fast, ~4GB download)
    echo   [2] Enhanced 14B (smarter, ~8GB download)
    echo   [3] PKD Edition  (philosophical, ~4GB download)
    echo.
    set /p MODEL_CHOICE="Enter 1, 2, or 3 (default: 1): "
    if "%MODEL_CHOICE%"=="2" (
        set "MF=%~dp0Cinder\data\Modelfile-14b"
    ) else if "%MODEL_CHOICE%"=="3" (
        set "MF=%~dp0Cinder\data\Modelfile-pkd"
    ) else (
        set "MF=%~dp0Cinder\data\Modelfile"
    )
    if exist "%MF%" (
        echo Setting up Cinder model... (first run, needs internet)
        ollama create cinder -f "%MF%"
        echo Model ready.
    ) else (
        echo Modelfile not found. Pulling default model...
        ollama pull qwen2.5:7b
    )
)

:: Set portable storage
set CINDER_STORAGE=%~dp0Cinder\data
echo Starting Cinder...
set CINDER_DIR=%~dp0Cinder\Windows
if exist "%CINDER_DIR%\Cinder.exe" (
    start "" "%CINDER_DIR%\Cinder.exe"
) else if exist "%CINDER_DIR%\Cinder 1.0.0.exe" (
    start "" "%CINDER_DIR%\Cinder 1.0.0.exe"
) else (
    echo ERROR: Cinder.exe not found at %CINDER_DIR%
    pause
    exit /b 1
)
WINLAUNCHER

cat > "$MNT_APP/launch-cinder.sh" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "╔══════════════════════════════════════╗"
echo "║         CINDER — Portable AI         ║"
echo "╚══════════════════════════════════════╝"

if ! command -v ollama &>/dev/null; then
    echo "Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

if ! pgrep -x ollama >/dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

# Create cinder model from Modelfile if not present
if ! ollama list 2>/dev/null | grep -qi "cinder"; then
    echo ""
    echo "Choose your Cinder model:"
    echo "  [1] Standard 7B  (fast, ~4GB download)"
    echo "  [2] Enhanced 14B (smarter, ~8GB download)"
    echo "  [3] PKD Edition  (philosophical, ~4GB download)"
    echo ""
    read -p "Enter 1, 2, or 3 (default: 1): " MODEL_CHOICE
    case "$MODEL_CHOICE" in
        2) MF="$SCRIPT_DIR/Cinder/data/Modelfile-14b" ;;
        3) MF="$SCRIPT_DIR/Cinder/data/Modelfile-pkd" ;;
        *) MF="$SCRIPT_DIR/Cinder/data/Modelfile" ;;
    esac
    if [ -f "$MF" ]; then
        echo "Setting up Cinder model... (first run, needs internet)"
        ollama create cinder -f "$MF"
        echo "Model ready."
    else
        echo "Modelfile not found. Pulling default model..."
        ollama pull qwen2.5:7b
    fi
fi

export CINDER_STORAGE="$SCRIPT_DIR/Cinder/data"
LINUX_DIR="$SCRIPT_DIR/Cinder/Linux"
if [ -f "$LINUX_DIR/Cinder-1.0.0.AppImage" ]; then
    echo "Starting Cinder (AppImage)..."
    chmod +x "$LINUX_DIR/Cinder-1.0.0.AppImage"
    "$LINUX_DIR/Cinder-1.0.0.AppImage" --no-sandbox &
elif [ -f "$LINUX_DIR/cinder" ]; then
    echo "Starting Cinder..."
    chmod +x "$LINUX_DIR/cinder"
    "$LINUX_DIR/cinder" --no-sandbox &
else
    echo "ERROR: Cinder not found in $LINUX_DIR"
    ls "$LINUX_DIR/" 2>/dev/null
    exit 1
fi
LAUNCHER
chmod +x "$MNT_APP/launch-cinder.sh"

cat > "$MNT_APP/Launch Cinder.command" << 'MACLAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "CINDER — Portable AI"

if ! command -v ollama &>/dev/null; then
    echo "Ollama not found. Download from: https://ollama.com/download/mac"
    read -p "Press Enter to exit..."
    exit 1
fi

if ! pgrep -x ollama >/dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 4
fi

# Create cinder model from Modelfile if not present
if ! ollama list 2>/dev/null | grep -qi "cinder"; then
    echo ""
    echo "Choose your Cinder model:"
    echo "  [1] Standard 7B  (fast, ~4GB download)"
    echo "  [2] Enhanced 14B (smarter, ~8GB download)"
    echo "  [3] PKD Edition  (philosophical, ~4GB download)"
    echo ""
    read -p "Enter 1, 2, or 3 (default: 1): " MODEL_CHOICE
    case "$MODEL_CHOICE" in
        2) MF="$SCRIPT_DIR/Cinder/data/Modelfile-14b" ;;
        3) MF="$SCRIPT_DIR/Cinder/data/Modelfile-pkd" ;;
        *) MF="$SCRIPT_DIR/Cinder/data/Modelfile" ;;
    esac
    if [ -f "$MF" ]; then
        echo "Setting up Cinder model... (first run, needs internet)"
        ollama create cinder -f "$MF"
        echo "Model ready."
    else
        echo "Modelfile not found. Pulling default model..."
        ollama pull qwen2.5:7b
    fi
fi

export CINDER_STORAGE="$SCRIPT_DIR/Cinder/data"
MAC_ZIP="$SCRIPT_DIR/Cinder/Mac/Cinder.zip"
MAC_APP="$SCRIPT_DIR/Cinder/Mac/Cinder.app"
if [ ! -d "$MAC_APP" ] && [ -f "$MAC_ZIP" ]; then
    echo "Extracting Cinder.app from archive (first run)..."
    unzip -q "$MAC_ZIP" -d "$SCRIPT_DIR/Cinder/Mac/"
fi
if [ -d "$MAC_APP" ]; then
    echo "Starting Cinder..."
    open "$MAC_APP"
else
    echo "ERROR: Cinder.app not found at $MAC_APP"
    read -p "Press Enter to exit..."
    exit 1
fi
MACLAUNCHER
chmod +x "$MNT_APP/Launch Cinder.command"

# ── QUICKSTART ──
cat > "$MNT_APP/QUICKSTART.txt" << 'QS'
CINDER — Quick Start
======================

1. Install Ollama from https://ollama.com
   - Windows: Download + run installer
   - Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh

2. Launch Cinder:
   - Windows: double-click "Launch Cinder.bat"
   - Mac: double-click "Launch Cinder.command"
   - Linux: ./launch-cinder.sh

3. First launch sets up your password and identity.

DRIVE LAYOUT:
  This drive has 3 partitions:
  - CINDER (this one) — app, models, tools
  - CINDER-SYS — identity & memory (Linux-native)
  - VAULT — encrypt with VeraCrypt for secure storage

  Windows will prompt to reformat the other partitions.
  CLICK CANCEL — this is normal. Only CINDER is needed.

TOOLS:
  Tools/ folder contains Marketplace Lister and other utilities.

FILES:
  UserFiles/ — put your documents here for Cinder to learn from.
QS

cat > "$MNT_APP/UserFiles/README.txt" << 'USERREADME'
CINDER USER STORAGE
===================
Place files here for Cinder to read and learn from.
  Documents/ — text, PDFs, notes
  Projects/  — code, data files
USERREADME

# ── Step 5: Populate P2 (system partition) ───────────────
echo ""
echo "[5/6] Populating P2 (system partition)..."
mkdir -p "$MNT_SYS/identity"
mkdir -p "$MNT_SYS/memory"
mkdir -p "$MNT_SYS/config"
mkdir -p "$MNT_SYS/logs"
mkdir -p "$MNT_SYS/growth"

# Identity files
for f in lineage.md personality.md; do
    [ -f "$REPO_DIR/$f" ] && cp "$REPO_DIR/$f" "$MNT_SYS/identity/"
done

# Cinder Modelfiles
[ -f "$SCRIPT_DIR/Modelfile-final" ] && cp "$SCRIPT_DIR/Modelfile-final" "$MNT_SYS/config/Modelfile"
[ -f "$SCRIPT_DIR/Modelfile-final-14b" ] && cp "$SCRIPT_DIR/Modelfile-final-14b" "$MNT_SYS/config/Modelfile-14b"
[ -f "$SCRIPT_DIR/Modelfile-pkd" ] && cp "$SCRIPT_DIR/Modelfile-pkd" "$MNT_SYS/config/Modelfile-pkd"

# XP tracking seed
cat > "$MNT_SYS/growth/xp.json" << 'XPSEED'
{
  "level": 1,
  "xp": 0,
  "xp_to_next": 100,
  "total_interactions": 0,
  "milestones": [],
  "prestige": 0,
  "created": "2026-04-19T00:00:00Z"
}
XPSEED

# System README
cat > "$MNT_SYS/README.txt" << 'SYSREADME'
CINDER SYSTEM PARTITION
========================
This partition stores Cinder's persistent state:
  identity/ — personality, lineage
  memory/   — conversation memory, learned facts
  config/   — model configurations
  growth/   — XP tracking, evolution state
  logs/     — system logs

This partition is ext4 (Linux-native).
On Windows/Mac, use a tool like Ext2Fsd or Paragon ExtFS to access.
SYSREADME

echo "  System partition populated"

# ── Step 6: Cleanup ──────────────────────────────────────
echo ""
echo "[6/6] Cleaning up..."
sync
umount "$MNT_APP" 2>/dev/null || true
umount "$MNT_SYS" 2>/dev/null || true
losetup -d "$LOOP"
rmdir "$MNT_APP" "$MNT_SYS" 2>/dev/null || true

SIZE=$(du -h --apparent-size "$IMG" | cut -f1)
ACTUAL=$(du -h "$IMG" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  BUILD COMPLETE"
echo "  Image: $IMG"
echo "  Apparent size: $SIZE | Actual (sparse): $ACTUAL"
echo ""
echo "  Partition layout:"
echo "    P1: exfat  CINDER     — app, models, tools, user files"
echo "    P2: ext4   CINDER-SYS — identity, memory, config"
echo "    P3: raw    VAULT      — format with VeraCrypt"
echo ""
echo "  Flash to USB:"
echo "    sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "    or use Balena Etcher"
echo "═══════════════════════════════════════════════════════"
