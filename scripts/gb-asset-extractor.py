#!/usr/bin/env python3
"""
GB Studio Asset Extractor (Loop 9707)

Loop 9706's curator catalogued ~/Downloads into asset-library/<cat>/ as symlinks
to zips. This script unpacks the non-plugin archives (sprites, backgrounds,
fonts, sfx, music, ui, tilesets) into asset-library/<cat>/_unpacked/<pack>/ so
Joel can browse PNGs and sound files directly instead of opening each zip.

Plugins are already extracted by gb-asset-curator.py — skip those.
Uses 7z for both .zip and .rar (rar is a notable subset of Joel's downloads).

Modes:
  python3 scripts/gb-asset-extractor.py            # extract all
  python3 scripts/gb-asset-extractor.py --list     # list unpacked packs + file counts
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

LIB = Path("products/cinder-creatures-gb/asset-library")
EXTRACTABLE_CATS = ["sprites", "backgrounds", "fonts", "sfx", "music", "ui", "tilesets"]
ARCHIVE_EXTS = {".zip", ".rar"}

IMAGE_EXTS = {".png", ".aseprite", ".ase", ".bmp", ".gif"}
AUDIO_EXTS = {".wav", ".mod", ".uge", ".ogg", ".mp3", ".vgm"}


def have_7z() -> bool:
    return shutil.which("7z") is not None


def extract_archive(src: Path, dest: Path) -> tuple[bool, str]:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["7z", "x", "-y", f"-o{dest}", str(src)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, result.stderr.strip().splitlines()[-1] if result.stderr else "7z failed"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as err:
        return False, str(err)


def prune_macos_trash(target: Path) -> int:
    removed = 0
    for trash in target.rglob("__MACOSX"):
        if trash.is_dir():
            shutil.rmtree(trash, ignore_errors=True)
            removed += 1
    for ds in target.rglob(".DS_Store"):
        try:
            ds.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def extract_all() -> list[dict]:
    results = []
    if not have_7z():
        print("ERROR: 7z not found in PATH", file=sys.stderr)
        return results

    for cat in EXTRACTABLE_CATS:
        catdir = LIB / cat
        if not catdir.exists():
            continue
        unpacked_root = catdir / "_unpacked"
        unpacked_root.mkdir(exist_ok=True)
        for archive in sorted(catdir.iterdir()):
            if archive.name == "_unpacked" or not archive.is_file() and not archive.is_symlink():
                continue
            if archive.suffix.lower() not in ARCHIVE_EXTS:
                continue
            target = unpacked_root / archive.stem
            entry = {"category": cat, "archive": archive.name, "target": str(target.relative_to(LIB))}
            if target.exists() and any(target.iterdir()):
                entry["status"] = "skipped (already unpacked)"
                results.append(entry)
                continue
            ok, msg = extract_archive(archive, target)
            if ok:
                pruned = prune_macos_trash(target)
                files = sum(1 for _ in target.rglob("*") if _.is_file())
                entry["status"] = f"ok ({files} files, pruned {pruned})"
                entry["file_count"] = files
            else:
                entry["status"] = f"FAILED: {msg}"
                # leave empty target dir for debugging — nothing to clean
            results.append(entry)
            print(f"  [{cat:11}] {archive.name[:50]:50} → {entry['status']}")
    return results


def list_packs() -> dict:
    summary = {}
    for cat in EXTRACTABLE_CATS:
        unpacked_root = LIB / cat / "_unpacked"
        if not unpacked_root.exists():
            continue
        cat_packs = []
        for pack in sorted(unpacked_root.iterdir()):
            if not pack.is_dir():
                continue
            images = sum(1 for f in pack.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
            audio = sum(1 for f in pack.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTS)
            other = sum(1 for f in pack.rglob("*") if f.is_file() and f.suffix.lower() not in IMAGE_EXTS | AUDIO_EXTS)
            cat_packs.append({
                "pack": pack.name,
                "images": images,
                "audio": audio,
                "other": other,
            })
        if cat_packs:
            summary[cat] = cat_packs
    return summary


def print_summary(summary: dict) -> None:
    if not summary:
        print("No unpacked packs yet. Run without --list to extract.")
        return
    print(f"\n{'=' * 64}\nUnpacked GB Studio asset packs\n{'=' * 64}")
    for cat in EXTRACTABLE_CATS:
        packs = summary.get(cat)
        if not packs:
            continue
        print(f"\n## {cat}/  ({len(packs)} pack{'s' if len(packs) != 1 else ''})")
        for p in packs:
            tags = []
            if p["images"]:
                tags.append(f"{p['images']} img")
            if p["audio"]:
                tags.append(f"{p['audio']} aud")
            if p["other"]:
                tags.append(f"{p['other']} other")
            print(f"  {p['pack'][:55]:55}  {', '.join(tags)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list unpacked packs and exit")
    args = parser.parse_args()

    if args.list:
        print_summary(list_packs())
        return

    if not LIB.exists():
        print(f"ERROR: {LIB} missing — run scripts/gb-asset-curator.py first", file=sys.stderr)
        sys.exit(2)

    results = extract_all()
    failed = [r for r in results if r["status"].startswith("FAILED")]
    ok = [r for r in results if r["status"].startswith("ok")]
    skipped = [r for r in results if r["status"].startswith("skipped")]

    summary = {"extracted": len(ok), "skipped": len(skipped), "failed": len(failed), "results": results}
    (LIB / "EXTRACTOR.json").write_text(json.dumps(summary, indent=2))
    print(f"\nExtracted: {len(ok)}  Skipped: {len(skipped)}  Failed: {len(failed)}")
    if failed:
        print("Failures:")
        for f in failed:
            print(f"  - {f['archive']}: {f['status']}")
    print_summary(list_packs())


if __name__ == "__main__":
    main()
