#!/bin/bash
# Deploy website to gh-pages branch
# Usage: bash scripts/deploy-site.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/site-build-$$"

echo "Building site from $REPO_DIR..."
mkdir -p "$BUILD_DIR"

# Copy website root
cp -r "$REPO_DIR/website/"* "$BUILD_DIR/"

# Games
mkdir -p "$BUILD_DIR/games"
cp -r "$REPO_DIR/products/games/"* "$BUILD_DIR/games/" 2>/dev/null || true
for game in "$REPO_DIR/creative/games/godot-"*/; do
    gamename=$(basename "$game")
    if [ -d "$game/export/web" ]; then
        mkdir -p "$BUILD_DIR/games/$gamename/export/web"
        cp -r "$game/export/web/"* "$BUILD_DIR/games/$gamename/export/web/"
    fi
done

# CogCorp fiction (from both locations)
mkdir -p "$BUILD_DIR/cogcorp-fiction"
cp -r "$REPO_DIR/cogcorp-fiction/"* "$BUILD_DIR/cogcorp-fiction/" 2>/dev/null || true
cp -r "$REPO_DIR/creative/cogcorp-fiction/"* "$BUILD_DIR/cogcorp-fiction/" 2>/dev/null || true

# NFTs, assets, visuals
cp -r "$REPO_DIR/creative/nfts" "$BUILD_DIR/nfts" 2>/dev/null || true
cp -r "$REPO_DIR/assets" "$BUILD_DIR/assets" 2>/dev/null || true
cp -r "$REPO_DIR/visuals" "$BUILD_DIR/visuals" 2>/dev/null || true

# Root HTML files (real only, no symlinks)
for f in "$REPO_DIR"/*.html; do
    [ -f "$f" ] && [ ! -L "$f" ] && cp "$f" "$BUILD_DIR/"
done

# Status files
cp "$REPO_DIR/status.json" "$BUILD_DIR/" 2>/dev/null || true
touch "$BUILD_DIR/.nojekyll"

# Deploy
cd "$BUILD_DIR"
git init -q
git checkout -q -b gh-pages
git add -A
git commit -q -m "Deploy site - Loop $(cat "$REPO_DIR/.loop-count" 2>/dev/null || echo '?')"

REMOTE=$(git -C "$REPO_DIR" remote get-url origin)
git remote add origin "$REMOTE"
git push origin gh-pages --force -q 2>&1

echo "Deployed: $(find . -type f | wc -l) files, $(du -sh . | cut -f1)"
rm -rf "$BUILD_DIR"
