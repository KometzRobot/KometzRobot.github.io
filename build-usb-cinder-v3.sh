#!/bin/bash
# build-usb-cinder-v3.sh — Build Cinder USB v3.0 product image
# Proper flashable .img file for Balena Etcher.
# exFAT single partition (Windows/Mac/Linux compatible).
# Native desktop app + portable Ollama + encrypted vault.
# NO web launcher. Multi-OS support.
#
# Output: ~/cinder-usb-v3.img
# Flash with: Balena Etcher (any OS) or dd on Linux.

set -e

SRC="/home/joel/cinder-usb"
IMG="/home/joel/cinder-usb-v3.img"
MOUNT_POINT="/tmp/cinder-v3"
IMG_SIZE_MB=8000  # 8GB (model 1.9G + vault 4G + binaries + overhead)

echo "=== Building Cinder USB v3.0 Image ==="
echo "Source: $SRC"
echo "Output: $IMG"
echo "Size: ${IMG_SIZE_MB}MB"
echo ""

# Remove old image
rm -f "$IMG"

# Step 1: Create empty image
echo "[1/6] Creating ${IMG_SIZE_MB}MB image..."
dd if=/dev/zero of="$IMG" bs=1M count=$IMG_SIZE_MB status=progress 2>&1

# Step 2: Create partition table with single exFAT partition
echo "[2/6] Creating partition table..."
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32 1MiB 100%

# Step 3: Set up loop device
echo "[3/6] Setting up loop device..."
LOOP=$(losetup --find --show --partscan "$IMG")
echo "Loop device: $LOOP"
sleep 1
PART="${LOOP}p1"

# Step 4: Format as exFAT (for vault.vc > 4GB support + cross-platform)
echo "[4/6] Formatting exFAT..."
mkfs.exfat -n "CINDER" "$PART"

# Step 5: Mount and copy files
echo "[5/6] Copying product files..."
mkdir -p "$MOUNT_POINT"
mount "$PART" "$MOUNT_POINT"

# ── Native Desktop App (multi-OS) ────────────────────────
# Linux binary
cp "$SRC/Cinder" "$MOUNT_POINT/" 2>/dev/null || true

# Python source (cross-platform fallback — works on any OS with Python)
cp "$SRC/cinder-desktop.py" "$MOUNT_POINT/"

# Windows launcher (calls Python directly)
cat > "$MOUNT_POINT/Cinder.bat" << 'WINEOF'
@echo off
title CINDER
echo Starting Cinder...
python "%~dp0cinder-desktop.py" 2>nul
if errorlevel 1 (
    python3 "%~dp0cinder-desktop.py" 2>nul
    if errorlevel 1 (
        echo Python not found. Install from python.org/downloads
        pause
    )
)
WINEOF

# Mac launcher
cat > "$MOUNT_POINT/Cinder.command" << 'MACEOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cinder-desktop.py
MACEOF
chmod +x "$MOUNT_POINT/Cinder.command"

# ── Portable Ollama ──────────────────────────────────────
mkdir -p "$MOUNT_POINT/bin/linux"
cp "$SRC/bin/linux/ollama" "$MOUNT_POINT/bin/linux/" 2>/dev/null || true
# Windows Ollama — user installs from ollama.com (noted in README)
mkdir -p "$MOUNT_POINT/bin/windows"
# macOS Ollama — user installs from ollama.com
mkdir -p "$MOUNT_POINT/bin/macos"

# ── Models (unencrypted for direct use) ──────────────────
mkdir -p "$MOUNT_POINT/models"
cp "$SRC/models/cinder.gguf" "$MOUNT_POINT/models/"
cp "$SRC/models/Modelfile-product" "$MOUNT_POINT/models/Modelfile"

# ── Encrypted Vault ──────────────────────────────────────
if [ -f "$SRC/vault.vc" ]; then
    cp "$SRC/vault.vc" "$MOUNT_POINT/"
    echo "  [OK] vault.vc (encrypted container)"
fi

# ── Identity ─────────────────────────────────────────────
mkdir -p "$MOUNT_POINT/identity"
cp -r "$SRC/identity-product/"* "$MOUNT_POINT/identity/"

# ── Assets ───────────────────────────────────────────────
mkdir -p "$MOUNT_POINT/assets"
cp -r "$SRC/assets/"* "$MOUNT_POINT/assets/" 2>/dev/null || true

# ── Archive / Resources ──────────────────────────────────
mkdir -p "$MOUNT_POINT/archive"
cp -r "$SRC/archive/"* "$MOUNT_POINT/archive/" 2>/dev/null || true

# ── Memory (empty, user data goes here) ──────────────────
mkdir -p "$MOUNT_POINT/memory"

# ── Setup scripts ────────────────────────────────────────
cp "$SRC/setup.sh" "$MOUNT_POINT/" 2>/dev/null || true
cp "$SRC/setup.bat" "$MOUNT_POINT/" 2>/dev/null || true

# ── Console (kept as offline reference only) ─────────────
cp "$SRC/cinder-console.html" "$MOUNT_POINT/" 2>/dev/null || true

# ── Docs ─────────────────────────────────────────────────
cp "$SRC/README.md" "$MOUNT_POINT/"
cp "$SRC/QUICKSTART.txt" "$MOUNT_POINT/"
cp "$SRC/LICENSE.txt" "$MOUNT_POINT/" 2>/dev/null || true

# Stats
echo ""
echo "Files on image:"
du -sh "$MOUNT_POINT/"
echo ""
ls -lhS "$MOUNT_POINT/" | head -15

umount "$MOUNT_POINT"

# Step 6: Clean up
echo ""
echo "[6/6] Cleaning up..."
losetup -d "$LOOP"
rmdir "$MOUNT_POINT" 2>/dev/null || true

SIZE=$(du -sh "$IMG" | cut -f1)
echo ""
echo "=== Done ==="
echo "Image: $IMG ($SIZE)"
echo ""
echo "To flash: Open Balena Etcher, select $IMG, select USB, flash."
echo "Or on Linux: sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
