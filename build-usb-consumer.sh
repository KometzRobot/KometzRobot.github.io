#!/bin/bash
# build-usb-consumer.sh — Build a consumer-friendly Cinder USB image
# Uses FAT32 single partition (Windows/Mac/Linux compatible)
# Produces: ~/cinder-usb-consumer.img
# Flash with: sudo dd if=cinder-usb-consumer.img of=/dev/sdX bs=4M status=progress
# Or use Balena Etcher on any OS.
#
# Built: Loop 3804 (Meridian, 2026-03-29)

set -e

SRC="/home/joel/cinder-usb"
IMG="/home/joel/cinder-usb-consumer.img"
MOUNT_POINT="/tmp/cinder-consumer"
IMG_SIZE_MB=2400  # 2.4GB (model is ~1.8GB + overhead)

echo "=== Building Cinder USB Consumer Image ==="
echo "Source: $SRC"
echo "Output: $IMG"
echo "Size: ${IMG_SIZE_MB}MB"

# Remove old image
rm -f "$IMG"

# Step 1: Create empty image
echo "[1/6] Creating ${IMG_SIZE_MB}MB image..."
dd if=/dev/zero of="$IMG" bs=1M count=$IMG_SIZE_MB status=progress 2>&1

# Step 2: Create partition table with single FAT32 partition
echo "[2/6] Creating partition table..."
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32 1MiB 100%
parted -s "$IMG" set 1 boot on

# Step 3: Set up loop device
echo "[3/6] Setting up loop device..."
LOOP=$(sudo losetup --find --show --partscan "$IMG")
echo "Loop device: $LOOP"
sleep 1
PART="${LOOP}p1"

# Step 4: Format as FAT32 (Windows/Mac/Linux compatible)
echo "[4/6] Formatting FAT32..."
sudo mkfs.vfat -F 32 -n "CINDER-v1" "$PART"

# Step 5: Mount and copy files
echo "[5/6] Copying product files..."
sudo mkdir -p "$MOUNT_POINT"
sudo mount "$PART" "$MOUNT_POINT"

# Models
sudo mkdir -p "$MOUNT_POINT/models"
sudo cp "$SRC/models/cinder.gguf" "$MOUNT_POINT/models/"
sudo cp "$SRC/models/Modelfile-product" "$MOUNT_POINT/models/Modelfile"
sudo cp "$SRC/models/Modelfile-14b" "$MOUNT_POINT/models/"

# Scripts
sudo mkdir -p "$MOUNT_POINT/scripts"
sudo cp "$SRC/scripts/cinder-web-launcher.py" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/cinder-enhanced.py" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/cinder-memory.py" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/build-index.py" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/memory-recall.py" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/cinder-launcher.sh" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/launch.sh" "$MOUNT_POINT/scripts/"
sudo cp "$SRC/scripts/launch.bat" "$MOUNT_POINT/scripts/"

# Assets
sudo mkdir -p "$MOUNT_POINT/assets"
sudo cp -r "$SRC/assets/"* "$MOUNT_POINT/assets/"

# Identity (product version)
sudo mkdir -p "$MOUNT_POINT/identity"
sudo mkdir -p "$MOUNT_POINT/identity-product"
sudo cp -r "$SRC/identity-product/"* "$MOUNT_POINT/identity/"
sudo cp -r "$SRC/identity-product/"* "$MOUNT_POINT/identity-product/"

# Memory
sudo mkdir -p "$MOUNT_POINT/memory"
sudo cp -r "$SRC/memory/"* "$MOUNT_POINT/memory/" 2>/dev/null || true

# Archive (knowledge base + curated resources)
sudo mkdir -p "$MOUNT_POINT/archive"
sudo cp -r "$SRC/archive/"* "$MOUNT_POINT/archive/" 2>/dev/null || true

# Root files
sudo cp "$SRC/README.md" "$MOUNT_POINT/"
sudo cp "$SRC/QUICKSTART.txt" "$MOUNT_POINT/"
sudo cp "$SRC/LICENSE.txt" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/autorun.inf" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/launch-web.sh" "$MOUNT_POINT/"
sudo cp "$SRC/launch-web.bat" "$MOUNT_POINT/"
sudo cp "$SRC/setup.sh" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/setup.bat" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/Cinder" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/cinder-app.py" "$MOUNT_POINT/" 2>/dev/null || true
sudo cp "$SRC/cinder-console.html" "$MOUNT_POINT/" 2>/dev/null || true

# Stats
echo ""
echo "Files on image:"
sudo du -sh "$MOUNT_POINT/"
echo ""
sudo ls -la "$MOUNT_POINT/"

sudo umount "$MOUNT_POINT"

# Step 6: Clean up
echo "[6/6] Cleaning up..."
sudo losetup -d "$LOOP"
sudo rmdir "$MOUNT_POINT" 2>/dev/null || true

SIZE=$(du -sh "$IMG" | cut -f1)
echo ""
echo "=== Done ==="
echo "Image: $IMG ($SIZE)"
echo ""
echo "To flash to USB:"
echo "  Linux:   sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "  Etcher:  Open Balena Etcher, select $IMG, select USB, flash"
