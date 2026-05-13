#!/bin/bash
# Build cinder-starter ROM via gb-studio-cli and deploy to mounted Cinder USBs.
# Built Loop 11079 — see project_gbstudio_cli_build.md for setup.
set -euo pipefail

GBS_SRC="/home/joel/build-deps/gb-studio-src"
PROJECT="/home/joel/autonomous-ai/products/cinder-creatures-gb/cinder-starter/project.gbsproj"
OUT_DIR="/home/joel/autonomous-ai/products/cinder-creatures-gb/build"
OUT_ROM="$OUT_DIR/cinder-starter.gb"

mkdir -p "$OUT_DIR"
rm -rf /tmp/_gbsbuild

cd "$GBS_SRC"
source /home/joel/.nvm/nvm.sh
nvm use 21.7.1 >/dev/null

node out/cli/gb-studio-cli.js make:rom "$PROJECT" "$OUT_ROM"

if [ ! -s "$OUT_ROM" ]; then
  echo "ERROR: ROM not produced" >&2
  exit 1
fi

SHA=$(sha256sum "$OUT_ROM" | awk '{print $1}')
echo "ROM built: $OUT_ROM (sha256: $SHA)"
file "$OUT_ROM"

# Deploy to in-repo source-of-truth paths so the next desktop dist rebuild
# ships the fresh ROM (Loop 11084 — these were stale; flagged after Loop 11082).
REPO_ROOT="/home/joel/autonomous-ai/products/cinder-anythingllm"
for repo_sub in \
  "server/public/games" \
  "frontend/dist/games" \
  "frontend/public/games"; do
  target="$REPO_ROOT/$repo_sub"
  if [ -d "$target" ]; then
    cp "$OUT_ROM" "$target/cinder-creatures-starter.gb"
    echo "deployed -> $target (in-repo)"
  fi
done
cp "$OUT_ROM" "$REPO_ROOT/cinder-creatures-starter.gb"
echo "deployed -> $REPO_ROOT/cinder-creatures-starter.gb (in-repo root)"

# Deploy to any mounted Cinder USB.
for usb in /media/usb1 /media/usb2; do
  for sub in \
    "Cinder/Windows/resources/server/public/games" \
    "Cinder/Windows/resources/frontend/dist/games" \
    "Cinder/Linux/resources/server/public/games" \
    "Cinder/Linux/resources/frontend/dist/games"; do
    target="$usb/$sub"
    if [ -d "$target" ]; then
      cp "$OUT_ROM" "$target/cinder-creatures-starter.gb"
      echo "deployed -> $target"
    fi
  done
done
