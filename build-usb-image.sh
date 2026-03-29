#!/bin/bash
# build-usb-image.sh — Create a flashable .img disk image for Cinder USB Stasis Key
# Produces: ~/cinder-usb.img (flash with: sudo dd if=cinder-usb.img of=/dev/sdX bs=4M status=progress)
# Or use Balena Etcher on any OS.
#
# Layout:
#   Partition 1 (FAT32, 256MB): BOOT — autorun, launcher, README, QUICKSTART
#   Partition 2 (ext4, encrypted-ready): VAULT — models, scripts, memory, identity
#
# Built: Loop 3743 (Meridian, 2026-03-28)

set -e

SRC="/home/joel/cinder-usb"
IMG="/home/joel/cinder-usb.img"
MOUNT_BOOT="/tmp/cinder-boot"
MOUNT_VAULT="/tmp/cinder-vault"
IMG_SIZE_MB=3072  # 3GB total

echo "=== Building Cinder USB Image ==="
echo "Source: $SRC"
echo "Output: $IMG"
echo "Size: ${IMG_SIZE_MB}MB"

# Step 1: Create empty image file
echo "[1/7] Creating ${IMG_SIZE_MB}MB image..."
dd if=/dev/zero of="$IMG" bs=1M count=$IMG_SIZE_MB status=progress 2>&1

# Step 2: Create partition table
echo "[2/7] Creating partition table..."
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32 1MiB 257MiB
parted -s "$IMG" mkpart primary ext4 257MiB 100%
parted -s "$IMG" set 1 boot on

# Step 3: Set up loop device
echo "[3/7] Setting up loop device..."
LOOP=$(sudo losetup --find --show --partscan "$IMG")
echo "Loop device: $LOOP"

# Wait for partitions to appear
sleep 1
BOOT_PART="${LOOP}p1"
VAULT_PART="${LOOP}p2"

# Step 4: Format partitions
echo "[4/7] Formatting partitions..."
sudo mkfs.vfat -F 32 -n "CINDER" "$BOOT_PART"
sudo mkfs.ext4 -L "VAULT" -q "$VAULT_PART"

# Step 5: Mount and copy BOOT partition (public-facing files only)
echo "[5/7] Copying boot partition files..."
sudo mkdir -p "$MOUNT_BOOT" "$MOUNT_VAULT"
sudo mount "$BOOT_PART" "$MOUNT_BOOT"

# Boot partition: only launcher and instructions
sudo cp "$SRC/README.md" "$MOUNT_BOOT/"
sudo cp "$SRC/QUICKSTART.txt" "$MOUNT_BOOT/"
sudo cp "$SRC/autorun.inf" "$MOUNT_BOOT/" 2>/dev/null || true

# Create launcher script for boot partition
sudo tee "$MOUNT_BOOT/launch.sh" > /dev/null << 'LAUNCHER'
#!/bin/bash
# Cinder USB — Launcher
# Mounts the vault partition and starts Cinder
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT=""

# Find the vault partition (ext4 labeled VAULT on same device)
DEVICE=$(df "$SCRIPT_DIR" | tail -1 | awk '{print $1}' | sed 's/[0-9]*$//')
for part in ${DEVICE}*; do
    label=$(sudo blkid -s LABEL -o value "$part" 2>/dev/null)
    if [ "$label" = "VAULT" ]; then
        VAULT="$part"
        break
    fi
done

if [ -z "$VAULT" ]; then
    echo "Error: VAULT partition not found on this device."
    echo "Make sure you're running this from the Cinder USB drive."
    exit 1
fi

# Mount vault if not already mounted
MOUNT_POINT="/tmp/cinder-vault"
if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    sudo mkdir -p "$MOUNT_POINT"
    sudo mount "$VAULT" "$MOUNT_POINT"
    echo "Vault mounted at $MOUNT_POINT"
fi

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "Ollama not found. Install it first:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    exit 1
fi

# Load Cinder model if not already loaded
if ! ollama list 2>/dev/null | grep -qi "cinder"; then
    echo "Loading Cinder model..."
    cd "$MOUNT_POINT/models"
    ollama create cinder -f Modelfile
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     CINDER — Stasis Key Active       ║"
echo "╠══════════════════════════════════════╣"
echo "║  1. Quick Chat    2. Deep Think       ║"
echo "║  3. Self-Reflect  4. Archive Search   ║"
echo "║  5. Tool Master   6. Consensus        ║"
echo "║  7. Memory Chat   8. Vector Search    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Launch web GUI if available
if [ -f "$MOUNT_POINT/scripts/cinder-web-launcher.py" ]; then
    echo "Starting web launcher..."
    python3 "$MOUNT_POINT/scripts/cinder-web-launcher.py" &
else
    echo "Starting Cinder chat..."
    ollama run cinder
fi
LAUNCHER
sudo chmod +x "$MOUNT_BOOT/launch.sh"

# Windows launcher
sudo tee "$MOUNT_BOOT/launch.bat" > /dev/null << 'WINLAUNCHER'
@echo off
echo Cinder USB - Windows launcher
echo.
echo Checking for Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo Ollama not found. Please install from https://ollama.com
    pause
    exit /b 1
)
echo Loading Cinder model...
ollama create cinder -f D:\models\Modelfile
echo Starting Cinder...
ollama run cinder
WINLAUNCHER

sudo umount "$MOUNT_BOOT"

# Step 6: Mount and copy VAULT partition (protected content)
echo "[6/7] Copying vault partition files..."
sudo mount "$VAULT_PART" "$MOUNT_VAULT"

sudo cp -r "$SRC/models" "$MOUNT_VAULT/"
sudo cp -r "$SRC/scripts" "$MOUNT_VAULT/"
sudo cp -r "$SRC/memory" "$MOUNT_VAULT/"
sudo cp -r "$SRC/identity" "$MOUNT_VAULT/"
sudo cp -r "$SRC/archive" "$MOUNT_VAULT/" 2>/dev/null || true

# Set permissions: read-only for most files
sudo chmod -R 755 "$MOUNT_VAULT/"
sudo chmod 644 "$MOUNT_VAULT/models/cinder.gguf"

sudo umount "$MOUNT_VAULT"

# Step 7: Clean up
echo "[7/7] Cleaning up..."
sudo losetup -d "$LOOP"
sudo rmdir "$MOUNT_BOOT" "$MOUNT_VAULT" 2>/dev/null || true

# Final stats
SIZE=$(du -sh "$IMG" | cut -f1)
echo ""
echo "=== Done ==="
echo "Image: $IMG ($SIZE)"
echo ""
echo "To flash to USB:"
echo "  Linux:   sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "  Etcher:  Open Balena Etcher, select $IMG, select USB, flash"
echo ""
echo "Partition layout:"
echo "  /dev/sdX1 (FAT32, 256MB) — BOOT: launcher, README"
echo "  /dev/sdX2 (ext4, ~2.7GB) — VAULT: model, scripts, identity"
