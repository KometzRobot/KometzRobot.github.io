#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Cinder USB Image Builder — AnythingLLM Edition
# Creates a flashable .img with THREE partitions:
#   P1: exfat  "CINDER"     — AnythingLLM app, Ollama, models, launchers
#   P2: ext4   "CINDER-SYS" — identity, Modelfiles, config
#   P3: (raw)  "VAULT"      — user formats with VeraCrypt
#
# Usage: sudo bash build-usb-image-alm.sh [output.img]
# Flash: sudo dd if=cinder-usb-alm.img of=/dev/sdX bs=4M status=progress
#    or: Use Balena Etcher
# ═══════════════════════════════════════════════════════════════

set -e

IMG="${1:-/mnt/data1/cinder-usb-v2.img}"
TOTAL_MB=57344  # 56GB — fits 64GB USB
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
MNT_APP="/tmp/cinder-p1"
MNT_SYS="/tmp/cinder-p2"

P1_END_MB=47104    # ~46GB for app partition
P2_END_MB=53248    # ~6GB for system partition

# ── Check for AnythingLLM AppImage ───────────────────────
ALM_DIR="$SCRIPT_DIR/anythingllm"
APPIMAGE="$ALM_DIR/AnythingLLMDesktop.AppImage"

if [ ! -f "$APPIMAGE" ]; then
    echo "ERROR: AnythingLLM AppImage not found at $APPIMAGE"
    echo "Download: curl -fSL -o $APPIMAGE https://cdn.anythingllm.com/latest/AnythingLLMDesktop.AppImage"
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "  Cinder USB Image Builder — AnythingLLM Edition"
echo "  Output: $IMG"
echo "  Size: ${TOTAL_MB}MB (~$((TOTAL_MB/1024))GB)"
echo "═══════════════════════════════════════════════════════"
echo "  P1: exfat  CINDER     (${P1_END_MB}MB) — AnythingLLM + Ollama"
echo "  P2: ext4   CINDER-SYS ($((P2_END_MB-P1_END_MB))MB) — identity/config"
echo "  P3: raw    VAULT      ($((TOTAL_MB-P2_END_MB))MB) — VeraCrypt"
echo "═══════════════════════════════════════════════════════"

read -p "Continue? (y/n) " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0

# ── Create sparse image ──────────────────────────────────
echo "[1/6] Creating sparse image..."
dd if=/dev/zero of="$IMG" bs=1M count=0 seek=$TOTAL_MB 2>/dev/null

# ── Partition ────────────────────────────────────────────
echo "[2/6] Creating partition table..."
parted -s "$IMG" mklabel gpt
parted -s "$IMG" mkpart CINDER 1MiB ${P1_END_MB}MiB
parted -s "$IMG" mkpart CINDER-SYS ${P1_END_MB}MiB ${P2_END_MB}MiB
parted -s "$IMG" mkpart VAULT ${P2_END_MB}MiB 100%

# ── Setup loop device ───────────────────────────────────
echo "[3/6] Formatting partitions..."
LOOP=$(losetup --find --show --partscan "$IMG")
sleep 1

mkfs.exfat -n CINDER "${LOOP}p1"
mkfs.ext4 -L CINDER-SYS -q "${LOOP}p2"

# ── Mount ────────────────────────────────────────────────
echo "[4/6] Populating P1 (CINDER)..."
mkdir -p "$MNT_APP" "$MNT_SYS"
mount "${LOOP}p1" "$MNT_APP"
mount "${LOOP}p2" "$MNT_SYS"

# ── P1: AnythingLLM + launchers + Ollama ─────────────────

# AnythingLLM AppImage (Linux)
mkdir -p "$MNT_APP/anythingllm"
echo "  Copying AnythingLLM AppImage (~2.4GB)..."
cp "$APPIMAGE" "$MNT_APP/anythingllm/AnythingLLMDesktop.AppImage"
mkdir -p "$MNT_APP/anythingllm/storage"

# Windows version (if available)
if [ -f "$ALM_DIR/AnythingLLMDesktop.exe" ]; then
    echo "  Copying Windows build..."
    cp "$ALM_DIR/AnythingLLMDesktop.exe" "$MNT_APP/anythingllm/"
fi

# macOS version (if available)
if [ -d "$ALM_DIR/AnythingLLMDesktop.app" ]; then
    echo "  Copying macOS build..."
    cp -a "$ALM_DIR/AnythingLLMDesktop.app" "$MNT_APP/anythingllm/"
fi

# Ollama binaries
mkdir -p "$MNT_APP/ollama/linux" "$MNT_APP/ollama/windows" "$MNT_APP/ollama/mac" "$MNT_APP/ollama/models"

OLLAMA_BIN=$(command -v ollama 2>/dev/null || true)
if [ -n "$OLLAMA_BIN" ]; then
    echo "  Copying Ollama binary..."
    cp "$OLLAMA_BIN" "$MNT_APP/ollama/linux/ollama"
    chmod +x "$MNT_APP/ollama/linux/ollama"
fi

# Cinder Modelfiles
mkdir -p "$MNT_APP/cinder"
for mf in Modelfile-final Modelfile-final-14b Modelfile-pkd Modelfile-v3; do
    if [ -f "$SCRIPT_DIR/$mf" ]; then
        cp "$SCRIPT_DIR/$mf" "$MNT_APP/cinder/"
    fi
done

# Launchers at root level
echo "  Copying launchers..."
cp "$SCRIPT_DIR/launchers/start-cinder-alm-linux.sh" "$MNT_APP/start-cinder.sh"
cp "$SCRIPT_DIR/launchers/start-cinder-alm.bat" "$MNT_APP/start-cinder.bat"
cp "$SCRIPT_DIR/launchers/start-cinder-alm.command" "$MNT_APP/Start Cinder.command"
chmod +x "$MNT_APP/start-cinder.sh" "$MNT_APP/Start Cinder.command"

# Quickstart guide
cat > "$MNT_APP/QUICKSTART.txt" <<'GUIDE'
═══════════════════════════════════════════════════════
  CINDER — Portable AI Companion (AnythingLLM Edition)
═══════════════════════════════════════════════════════

Your personal AI runs entirely from this USB drive.
No data ever leaves the drive. No internet required.

GETTING STARTED:
  Windows:  Double-click "start-cinder.bat"
  macOS:    Double-click "Start Cinder.command"
  Linux:    Run ./start-cinder.sh in a terminal

FIRST RUN:
  The launcher will start the AI engine and open
  AnythingLLM. Create a workspace and select "Ollama"
  as your LLM provider. Choose the "cinder" model.

WHAT'S ON THIS DRIVE:
  /anythingllm/  — The AnythingLLM app (your chat interface)
  /ollama/       — The AI engine (runs models locally)
  /cinder/       — Cinder personality files (Modelfiles)
  /vault/        — Encrypted partition (set up with VeraCrypt)

ALL YOUR DATA STAYS ON THIS USB.
═══════════════════════════════════════════════════════
GUIDE

# ── P2: Identity + Config ───────────────────────────────
echo "[5/6] Populating P2 (CINDER-SYS)..."

mkdir -p "$MNT_SYS/identity" "$MNT_SYS/config" "$MNT_SYS/logs"

# Identity files
for f in lineage.md personality.md; do
    if [ -f "$REPO_DIR/$f" ]; then
        cp "$REPO_DIR/$f" "$MNT_SYS/identity/"
    fi
done

# XP seed
cat > "$MNT_SYS/config/xp.json" <<'XP'
{
  "level": 1,
  "xp": 0,
  "xp_to_next": 100,
  "total_xp": 0,
  "prestige": 0,
  "evolution_log": []
}
XP

echo "  System partition populated."

# ── Cleanup ──────────────────────────────────────────────
echo "[6/6] Finalizing..."
sync
umount "$MNT_APP"
umount "$MNT_SYS"
losetup -d "$LOOP"
rmdir "$MNT_APP" "$MNT_SYS" 2>/dev/null || true

ACTUAL_SIZE=$(du -h "$IMG" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  BUILD COMPLETE"
echo "  Image: $IMG"
echo "  Actual size: $ACTUAL_SIZE (sparse — will be ~56GB on USB)"
echo ""
echo "  Flash with:"
echo "    sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "    or Balena Etcher"
echo "═══════════════════════════════════════════════════════"
