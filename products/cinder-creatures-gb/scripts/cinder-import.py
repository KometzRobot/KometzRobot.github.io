#!/usr/bin/env python3
"""
cinder-import.py — merge Cinder Creatures into an existing GB Studio project.

Use when you have a BLANK (or partially-built) GB Studio 4.x project open and
want to drop in the v0.44 cinder-creatures plugin + scenes + assets.

  python3 cinder-import.py /path/to/your-project-dir [--force]

The target dir must contain a *.gbsproj file. The script copies:
  - plugins/cinder-creatures/      (events + plugin assets)
  - assets/{backgrounds,sprites,tilesets,sounds,fonts,ui,avatars,emotes,music}/*
  - project/scenes/cinder_*/        (player room, lab, route, gyms, intros, void)
  - project/variables.gbsres        (vars for the catch loop) — only if absent

Idempotent: existing files are skipped unless --force. Reports the count of
files copied vs skipped.

Run AFTER closing GB Studio. Re-open the project and GB Studio will re-scan
assets and surface the new events under the "Cinder Creatures" group.
"""

from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # products/cinder-creatures-gb
SRC_STARTER = HERE / "cinder-starter"
SRC_PLUGIN = HERE / "plugins" / "cinder-creatures"


def find_gbsproj(target: Path) -> Path | None:
    for p in target.glob("*.gbsproj"):
        return p
    return None


def copy_tree(src: Path, dst: Path, force: bool, stats: dict[str, int], label: str):
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.rglob("*"):
        rel = entry.relative_to(src)
        out = dst / rel
        if entry.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        if out.exists() and not force:
            stats[f"{label}_skipped"] += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, out)
        stats[f"{label}_copied"] += 1


def main():
    ap = argparse.ArgumentParser(
        description="Merge Cinder Creatures into an existing GB Studio project."
    )
    ap.add_argument("target", type=Path, help="Path to your GB Studio project dir")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (default: skip)",
    )
    ap.add_argument(
        "--no-scenes",
        action="store_true",
        help="Skip copying cinder_* scenes (plugin + assets only)",
    )
    args = ap.parse_args()

    target: Path = args.target.expanduser().resolve()
    if not target.is_dir():
        sys.exit(f"ERROR: {target} is not a directory")

    proj = find_gbsproj(target)
    if not proj:
        sys.exit(
            f"ERROR: no *.gbsproj in {target}\n"
            f"       Open or create a GB Studio project first, then point this script at it."
        )

    print(f"Target project: {proj.name}  ({target})")
    print(f"Source starter: {SRC_STARTER}")
    print(f"Source plugin:  {SRC_PLUGIN}")
    print(f"Mode: {'OVERWRITE' if args.force else 'merge (skip existing)'}")
    print()

    stats: dict[str, int] = {
        "plugin_copied": 0, "plugin_skipped": 0,
        "assets_copied": 0, "assets_skipped": 0,
        "scenes_copied": 0, "scenes_skipped": 0,
        "vars_copied": 0, "vars_skipped": 0,
    }

    # 1) Plugin -> target/plugins/cinder-creatures/
    copy_tree(
        SRC_PLUGIN,
        target / "plugins" / "cinder-creatures",
        args.force,
        stats,
        "plugin",
    )

    # 2) Assets -> target/assets/<subdir>/
    starter_assets = SRC_STARTER / "assets"
    if starter_assets.exists():
        for subdir in starter_assets.iterdir():
            if subdir.is_dir():
                copy_tree(
                    subdir,
                    target / "assets" / subdir.name,
                    args.force,
                    stats,
                    "assets",
                )

    # 3) Scenes -> target/project/scenes/cinder_*/
    if not args.no_scenes:
        starter_scenes = SRC_STARTER / "project" / "scenes"
        if starter_scenes.exists():
            for scene_dir in starter_scenes.iterdir():
                if scene_dir.is_dir() and scene_dir.name.startswith("cinder_"):
                    copy_tree(
                        scene_dir,
                        target / "project" / "scenes" / scene_dir.name,
                        args.force,
                        stats,
                        "scenes",
                    )

    # 4) Variables -> target/project/variables.gbsres (only if absent, never overwrite by default)
    src_vars = SRC_STARTER / "project" / "variables.gbsres"
    dst_vars = target / "project" / "variables.gbsres"
    if src_vars.exists():
        if dst_vars.exists() and not args.force:
            stats["vars_skipped"] += 1
            print(f"NOTE: {dst_vars.relative_to(target)} already exists — left untouched.")
            print("      Cinder vars (cc_pool_00..15, cc_intro_*_seen, etc.) NOT merged.")
            print("      Re-run with --force to overwrite, OR open variables.gbsres in")
            print("      a text editor and merge manually from cinder-starter.")
        else:
            dst_vars.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_vars, dst_vars)
            stats["vars_copied"] += 1

    # Summary
    print("\n--- Summary ---")
    for k in sorted(stats):
        if stats[k]:
            print(f"  {k:20s} {stats[k]}")

    print(
        "\nDone. Now:\n"
        "  1. Re-open your project in GB Studio.\n"
        "  2. The plugin shows up under Add Event -> Plugin -> Cinder Creatures.\n"
        "  3. Backgrounds / sprites appear in their respective panels.\n"
        "  4. Cinder scenes appear in the World view (you may need to drag them onto\n"
        "     the world canvas if they were never registered in your project).\n"
    )


if __name__ == "__main__":
    main()
