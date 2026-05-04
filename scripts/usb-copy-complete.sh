#!/bin/bash
# Complete Cinder USB copy to /media/usb3 (sdg2 = CINDER-APP)
# Run: bash scripts/usb-copy-complete.sh &> /tmp/usb-copy.log &

set -e
LOG=/tmp/usb-copy.log
SRC_WIN="/home/joel/autonomous-ai/products/cinder-anythingllm/desktop/dist/win-unpacked/"
SRC_LINUX="/home/joel/autonomous-ai/products/cinder-anythingllm/desktop/dist/linux-unpacked/"
SRC_MAC="/home/joel/autonomous-ai/products/cinder-anythingllm/desktop/dist/mac/"
OLLAMA_BIN="/usr/local/bin/ollama"
MODEL_SRC="/usr/share/ollama/.ollama/models"
DEST="/media/usb3/Cinder"

echo "[$(date)] === Cinder USB copy starting ==="

mkdir -p "$DEST/Windows" "$DEST/Linux" "$DEST/Mac" "$DEST/ollama/models/blobs" "$DEST/ollama/models/manifests/registry.ollama.ai/library/cinder"

echo "[$(date)] Syncing Windows build (~2GB)..."
rsync -av --inplace --no-perms --no-owner --no-group "$SRC_WIN" "$DEST/Windows/" 2>&1 || true
echo "[$(date)] Windows done."

echo "[$(date)] Syncing Linux build (~2GB)..."
rsync -av --inplace --no-perms --no-owner --no-group "$SRC_LINUX" "$DEST/Linux/" 2>&1 || true
echo "[$(date)] Linux done."

echo "[$(date)] Syncing Mac build (~2GB)..."
rsync -av --inplace --no-perms --no-owner --no-group "$SRC_MAC" "$DEST/Mac/" 2>&1 || true
echo "[$(date)] Mac done."

echo "[$(date)] Copying ollama binary..."
cp -v "$OLLAMA_BIN" "$DEST/ollama/ollama" 2>&1
chmod +x "$DEST/ollama/ollama"
echo "[$(date)] ollama binary done."

echo "[$(date)] Copying cinder:latest model (~4.7GB)..."
# Copy manifest
cp -v "$MODEL_SRC/manifests/registry.ollama.ai/library/cinder/latest" "$DEST/ollama/models/manifests/registry.ollama.ai/library/cinder/latest" 2>&1

# Get blob hashes from manifest
BLOBS=$(python3 -c "
import json
with open('$MODEL_SRC/manifests/registry.ollama.ai/library/cinder/latest') as f:
    d = json.load(f)
for layer in d.get('layers', []):
    h = layer['digest'].replace('sha256:', 'sha256-')
    print(h)
# Also config
cfg = d.get('config', {}).get('digest', '')
if cfg:
    print(cfg.replace('sha256:', 'sha256-'))
")

for blob in $BLOBS; do
    src_blob="$MODEL_SRC/blobs/$blob"
    if [ -f "$src_blob" ]; then
        echo "[$(date)] Copying blob: $blob ($(du -sh $src_blob | cut -f1))"
        cp -v "$src_blob" "$DEST/ollama/models/blobs/$blob" 2>&1
    else
        echo "[$(date)] WARNING: blob not found: $src_blob"
    fi
done
echo "[$(date)] Model copy done."

echo "[$(date)] === USB copy COMPLETE ==="
df -h /media/usb3
du -sh "$DEST"/*
echo "DONE" > /tmp/usb-copy-status.txt
