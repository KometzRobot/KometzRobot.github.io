#!/usr/bin/env bash
# Cinder Creatures — opens the GB-style creature collector in your default browser.
# Cross-platform: macOS uses `open`, Linux uses `xdg-open`, Windows uses the .bat sibling.
DIR="$(cd "$(dirname "$0")" && pwd)"
GAME="$DIR/games/cinder-creatures.html"
if [ ! -f "$GAME" ]; then
  echo "[cinder-creatures] missing $GAME"
  exit 1
fi
if [ "$(uname)" = "Darwin" ]; then
  open "$GAME"
else
  xdg-open "$GAME" 2>/dev/null || sensible-browser "$GAME" 2>/dev/null || firefox "$GAME"
fi
