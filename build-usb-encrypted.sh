#!/bin/bash
# build-usb-encrypted.sh — Create LUKS-encrypted Cinder USB image
# Files on the vault partition are NOT browsable without the passphrase.
#
# Layout:
#   Partition 1 (FAT32, 256MB): BOOT — launcher, README only
#   Partition 2 (LUKS encrypted ext4): VAULT — model, scripts, identity
#
# Flash with: sudo dd if=cinder-usb-encrypted.img of=/dev/sdX bs=4M status=progress
# Or use Balena Etcher.
#
# Built: Loop 3750 (Meridian, 2026-03-29)

set -e

SRC="/home/joel/cinder-usb"
IMG="/home/joel/cinder-usb-encrypted.img"
MOUNT_BOOT="/tmp/cinder-boot"
MOUNT_VAULT="/tmp/cinder-vault"
IMG_SIZE_MB=3072
PASSPHRASE="cinder"  # Default passphrase — Joel can change before shipping

echo "=== Building Encrypted Cinder USB Image ==="
echo "Source: $SRC"
echo "Output: $IMG"
echo "Default passphrase: $PASSPHRASE"
echo ""

# Step 1: Create image
echo "[1/8] Creating ${IMG_SIZE_MB}MB image..."
dd if=/dev/zero of="$IMG" bs=1M count=$IMG_SIZE_MB status=progress 2>&1

# Step 2: Partition
echo "[2/8] Creating partition table..."
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32 1MiB 257MiB
parted -s "$IMG" mkpart primary 257MiB 100%
parted -s "$IMG" set 1 boot on

# Step 3: Loop device
echo "[3/8] Setting up loop device..."
LOOP=$(sudo losetup --find --show --partscan "$IMG")
sleep 1
BOOT_PART="${LOOP}p1"
VAULT_PART="${LOOP}p2"

# Step 4: Format boot (FAT32, visible to all OSes)
echo "[4/8] Formatting boot partition (FAT32)..."
sudo mkfs.vfat -F 32 -n "CINDER" "$BOOT_PART"

# Step 5: LUKS encrypt vault partition
echo "[5/8] Encrypting vault partition (LUKS)..."
echo -n "$PASSPHRASE" | sudo cryptsetup luksFormat --batch-mode "$VAULT_PART" -d -
echo -n "$PASSPHRASE" | sudo cryptsetup open "$VAULT_PART" cinder-vault -d -
sudo mkfs.ext4 -L "VAULT" -q /dev/mapper/cinder-vault

# Step 6: Copy boot files
echo "[6/8] Copying boot partition files..."
sudo mkdir -p "$MOUNT_BOOT" "$MOUNT_VAULT"
sudo mount "$BOOT_PART" "$MOUNT_BOOT"

sudo cp "$SRC/README.md" "$MOUNT_BOOT/"
sudo cp "$SRC/QUICKSTART.txt" "$MOUNT_BOOT/"

# Create unlock + launch script
sudo tee "$MOUNT_BOOT/unlock.sh" > /dev/null << 'UNLOCK'
#!/bin/bash
# Cinder USB — Unlock vault and launch
set -e
echo "╔══════════════════════════════════════╗"
echo "║     CINDER — Stasis Key              ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Find the LUKS partition (partition 2 on same device)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVICE=$(df "$SCRIPT_DIR" 2>/dev/null | tail -1 | awk '{print $1}' | sed 's/[0-9]*$//')
VAULT_PART="${DEVICE}2"

if [ ! -b "$VAULT_PART" ]; then
    echo "Error: Cannot find vault partition at $VAULT_PART"
    exit 1
fi

# Check if already unlocked
if [ -e /dev/mapper/cinder-vault ]; then
    echo "Vault already unlocked."
else
    echo "Enter passphrase to unlock vault:"
    sudo cryptsetup open "$VAULT_PART" cinder-vault
    echo "Vault unlocked."
fi

# Mount
MOUNT="/tmp/cinder-vault"
if ! mountpoint -q "$MOUNT" 2>/dev/null; then
    sudo mkdir -p "$MOUNT"
    sudo mount /dev/mapper/cinder-vault "$MOUNT"
fi
echo "Vault mounted at $MOUNT"

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

# Load model
if ! ollama list 2>/dev/null | grep -qi "cinder"; then
    echo "Loading Cinder model..."
    cd "$MOUNT/models"
    ollama create cinder -f Modelfile
fi

echo ""
echo "Cinder ready. Starting web launcher..."
if [ -f "$MOUNT/scripts/cinder-web-launcher.py" ]; then
    python3 "$MOUNT/scripts/cinder-web-launcher.py"
else
    ollama run cinder
fi
UNLOCK
sudo chmod +x "$MOUNT_BOOT/unlock.sh"

# Windows unlock
sudo tee "$MOUNT_BOOT/README-WINDOWS.txt" > /dev/null << 'WINREADME'
CINDER USB — Windows Users

The vault partition on this USB is encrypted (LUKS).
Windows cannot read it natively.

Options:
1. Use on Linux or macOS (recommended)
2. Install WSL2 on Windows, then run: bash /mnt/d/unlock.sh
3. Boot a Linux USB to access the vault

The encryption protects the AI model and identity files.
This is intentional — it's a security feature, not a bug.
WINREADME

sudo umount "$MOUNT_BOOT"

# Step 7: Copy vault files
echo "[7/8] Copying vault files (encrypted)..."
sudo mount /dev/mapper/cinder-vault "$MOUNT_VAULT"

sudo cp -r "$SRC/models" "$MOUNT_VAULT/"
sudo cp -r "$SRC/scripts" "$MOUNT_VAULT/"
sudo cp -r "$SRC/memory" "$MOUNT_VAULT/"
sudo cp -r "$SRC/identity" "$MOUNT_VAULT/"
sudo cp -r "$SRC/archive" "$MOUNT_VAULT/" 2>/dev/null || true

sudo chmod -R 755 "$MOUNT_VAULT/"
sudo umount "$MOUNT_VAULT"

# Step 8: Clean up
echo "[8/8] Cleaning up..."
sudo cryptsetup close cinder-vault
sudo losetup -d "$LOOP"
sudo rmdir "$MOUNT_BOOT" "$MOUNT_VAULT" 2>/dev/null || true

SIZE=$(du -sh "$IMG" | cut -f1)
echo ""
echo "=== Done ==="
echo "Encrypted image: $IMG ($SIZE)"
echo "Default passphrase: $PASSPHRASE"
echo ""
echo "To flash: sudo dd if=$IMG of=/dev/sdX bs=4M status=progress"
echo "To use:   plug in, run unlock.sh from boot partition"
echo ""
echo "IMPORTANT: Change the passphrase before shipping!"
echo "  sudo cryptsetup luksChangeKey /dev/sdX2"
