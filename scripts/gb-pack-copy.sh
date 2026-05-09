#!/usr/bin/env bash
# gb-pack-copy.sh — copy a curated asset pack into a GB Studio project
#
# Usage:
#   scripts/gb-pack-copy.sh /path/to/gbstudio-project pack-name [pack-name...]
#   scripts/gb-pack-copy.sh /path/to/gbstudio-project --all-fonts
#   scripts/gb-pack-copy.sh --list
#
# Pack names come from `python3 scripts/gb-asset-extractor.py --list`.
# The script auto-detects category and copies asset-library/<cat>/_unpacked/<pack>/
# into <project>/assets/<cat>/<pack>/.
#
# GB Studio shows nested folders inside assets/ as collapsible groups, so the
# pack stays organized rather than dumping 200 PNGs into a flat list.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$REPO/products/cinder-creatures-gb/asset-library"
CATS=(sprites backgrounds fonts sfx music ui tilesets)

if [[ $# -eq 0 ]] || [[ "${1:-}" == "--list" ]]; then
  python3 "$REPO/scripts/gb-asset-extractor.py" --list
  exit 0
fi

DEST="$1"
shift
if [[ ! -d "$DEST" ]]; then
  echo "Not a directory: $DEST" >&2
  exit 2
fi

# Map category aliases to GB Studio's actual asset folders
gb_subdir() {
  case "$1" in
    sprites) echo "assets/sprites" ;;
    backgrounds|tilesets) echo "assets/backgrounds" ;;
    fonts) echo "assets/fonts" ;;
    sfx) echo "assets/sounds" ;;
    music) echo "assets/music" ;;
    ui) echo "assets/ui" ;;
    *) echo "" ;;
  esac
}

find_pack_category() {
  local pack="$1"
  for cat in "${CATS[@]}"; do
    if [[ -d "$LIB/$cat/_unpacked/$pack" ]]; then
      echo "$cat"
      return 0
    fi
  done
  return 1
}

copy_pack() {
  local pack="$1"
  local cat
  if ! cat="$(find_pack_category "$pack")"; then
    echo "  pack not found in any _unpacked/ : $pack" >&2
    return 1
  fi
  local sub
  sub="$(gb_subdir "$cat")"
  if [[ -z "$sub" ]]; then
    echo "  no GB Studio subdir mapping for category $cat" >&2
    return 1
  fi
  local target="$DEST/$sub/$pack"
  mkdir -p "$(dirname "$target")"
  rsync -a --exclude='__MACOSX' --exclude='.DS_Store' \
        "$LIB/$cat/_unpacked/$pack/" "$target/"
  local files
  files="$(find "$target" -type f | wc -l)"
  echo "  + $cat/$pack → $sub/$pack ($files files)"
}

# Handle --all-<cat> shortcuts
expand_args() {
  for arg in "$@"; do
    case "$arg" in
      --all-sprites|--all-fonts|--all-ui|--all-sfx|--all-music|--all-backgrounds|--all-tilesets)
        local cat="${arg#--all-}"
        if [[ -d "$LIB/$cat/_unpacked" ]]; then
          for pdir in "$LIB/$cat/_unpacked"/*/; do
            [[ -d "$pdir" ]] && basename "$pdir"
          done
        fi
        ;;
      *) echo "$arg" ;;
    esac
  done
}

mapfile -t PACKS < <(expand_args "$@")

if [[ ${#PACKS[@]} -eq 0 ]]; then
  echo "No packs specified" >&2
  exit 2
fi

echo "==> Copying ${#PACKS[@]} pack(s) into $DEST"
fail=0
for p in "${PACKS[@]}"; do
  copy_pack "$p" || fail=$((fail + 1))
done

echo
echo "DONE. Re-open the project in GB Studio to refresh the asset list."
[[ $fail -eq 0 ]] || { echo "$fail pack(s) failed." >&2; exit 1; }
