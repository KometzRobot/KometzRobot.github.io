#!/usr/bin/env bash
# cinder-gb-import.sh — drop Cinder + curated assets into a target GB Studio project
#
# Usage: scripts/cinder-gb-import.sh /path/to/your-gbstudio-project
#
# Joel's pain (Loop 9705): "I have a blank project open right now and am unable
# to import any previous work." GB Studio has no project-merge feature. This
# script copies the cinder-creatures plugin + selected community plugins +
# stub asset folders into a target .gbsproj directory, then prints the next
# step (re-open the project so GB Studio re-scans plugins/).

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 /path/to/gbstudio-project-dir" >&2
  exit 2
fi

DEST="$1"
if [[ ! -d "$DEST" ]]; then
  echo "Not a directory: $DEST" >&2
  exit 2
fi
if ! ls "$DEST"/*.gbsproj >/dev/null 2>&1 && ! ls "$DEST"/*.gbsproj.json >/dev/null 2>&1; then
  echo "Warning: no .gbsproj in $DEST — continuing anyway" >&2
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC_PLUGIN="$REPO/products/cinder-creatures-gb/plugins/cinder-creatures"
EXTRACTED="$REPO/products/cinder-creatures-gb/asset-library/extracted"

mkdir -p "$DEST/plugins"

echo "==> Copying Cinder Creatures plugin → $DEST/plugins/cinder-creatures"
rsync -a --delete "$SRC_PLUGIN/" "$DEST/plugins/cinder-creatures/"

if [[ -d "$EXTRACTED" ]]; then
  echo "==> Copying community plugins from asset-library/extracted/"
  for pdir in "$EXTRACTED"/*/; do
    [[ -d "$pdir" ]] || continue
    # plugins/ subfolders inside e.g. gbs-plugin-collection-main wrap nested dirs;
    # we copy the inner plugin dirs (those containing plugin.json or events/)
    while IFS= read -r -d '' manifest; do
      plugindir="$(dirname "$manifest")"
      plugname="$(basename "$plugindir")"
      [[ "$plugname" == "cinder-creatures" ]] && continue
      mkdir -p "$DEST/plugins/$plugname"
      rsync -a "$plugindir/" "$DEST/plugins/$plugname/"
      echo "    + $plugname"
    done < <(find "$pdir" -maxdepth 5 -name plugin.json -print0)
  done
fi

mkdir -p "$DEST/assets/backgrounds" "$DEST/assets/sprites" "$DEST/assets/music" "$DEST/assets/sounds"

echo
echo "DONE. Re-open $DEST in GB Studio so it re-scans plugins/."
echo "Cinder events will appear under 'Cinder Creatures' in the event picker."
