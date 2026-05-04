#!/bin/bash
# Finish Cinder USB copy — resumes after Windows is done
# Windows: COMPLETE. This script does: Linux binary, model, Linux build, Mac (if space)
# Run: nohup bash scripts/usb-finish-copy.sh >> /tmp/usb-finish.log 2>&1 &

LOG=/tmp/usb-finish.log
DEST="/media/usb3/Cinder"
MODEL_SRC="/usr/share/ollama/.ollama/models"
SRC_LINUX="/home/joel/autonomous-ai/products/cinder-anythingllm/desktop/dist/linux-unpacked/"
SRC_MAC="/home/joel/autonomous-ai/products/cinder-anythingllm/desktop/dist/mac/"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== USB finish-copy starting ==="
log "Disk before: $(df -h /media/usb3 | tail -1)"

# 1. Copy Linux ollama binary
log "Copying Linux ollama binary..."
cp -v /usr/local/bin/ollama "$DEST/ollama/ollama" && chmod +x "$DEST/ollama/ollama"
log "Linux ollama binary done ($(du -sh $DEST/ollama/ollama | cut -f1))."

# 2. Copy model manifest
log "Copying model manifest..."
mkdir -p "$DEST/ollama/models/manifests/registry.ollama.ai/library/cinder"
cp -v "$MODEL_SRC/manifests/registry.ollama.ai/library/cinder/latest" \
    "$DEST/ollama/models/manifests/registry.ollama.ai/library/cinder/latest"
log "Manifest done."

# 3. Copy model blobs (4.4GB main blob)
log "Copying model blobs (~4.4GB)..."
mkdir -p "$DEST/ollama/models/blobs"
python3 << 'PYEOF'
import json, os, shutil, sys

src = '/usr/share/ollama/.ollama/models'
dst_blobs = '/media/usb3/Cinder/ollama/models/blobs'
manifest = json.load(open(f'{src}/manifests/registry.ollama.ai/library/cinder/latest'))

blobs = [manifest.get('config', {})] + manifest.get('layers', [])
for item in blobs:
    digest = item.get('digest', '')
    if not digest:
        continue
    fname = digest.replace('sha256:', 'sha256-')
    src_path = os.path.join(src, 'blobs', fname)
    dst_path = os.path.join(dst_blobs, fname)
    if os.path.exists(dst_path):
        print(f'  SKIP {fname[:30]} (already exists)', flush=True)
        continue
    if os.path.exists(src_path):
        sz = os.path.getsize(src_path)
        print(f'  Copying {fname[:30]} ({sz // 1024 // 1024}MB)...', flush=True)
        shutil.copy2(src_path, dst_path)
        print(f'  Done.', flush=True)
    else:
        print(f'  WARN: blob not found: {src_path}', flush=True)
PYEOF
log "Model blobs done."
log "Disk after model: $(df -h /media/usb3 | tail -1)"

# 4. Linux build
log "Syncing Linux build (~2GB source, ~11GB on exFAT)..."
rsync -av --inplace --no-perms --no-owner --no-group \
    "$SRC_LINUX" "$DEST/Linux/" 2>&1 || true
log "Linux done. Disk: $(df -h /media/usb3 | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"

# 5. Mac build (attempt — may not fit)
AVAIL_GB=$(df /media/usb3 | tail -1 | awk '{print int($4/1024/1024)}')
log "Available before Mac: ${AVAIL_GB}GB"
if [ "$AVAIL_GB" -gt 10 ]; then
    log "Syncing Mac build (~2GB source, ~11GB on exFAT)..."
    rsync -av --inplace --no-perms --no-owner --no-group \
        "$SRC_MAC" "$DEST/Mac/" 2>&1 || true
    log "Mac done. Disk: $(df -h /media/usb3 | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"
else
    log "SKIP Mac — not enough space (${AVAIL_GB}GB < 10GB needed)"
fi

# 6. Mark complete
log "=== USB copy COMPLETE ==="
df -h /media/usb3
du -sh "$DEST"/*
echo "DONE" > /tmp/usb-copy-status.txt
log "Status set to DONE. Notify script will email Joel."
