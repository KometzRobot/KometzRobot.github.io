#!/usr/bin/env python3
"""
cinder-image-freshness.py — answer the question "is the latest .img stale?"

Joel's complaint Loop 11219: "Why would you ship stale". This script makes that
question impossible to fudge. Compares the newest .img mtime against the newest
source file mtime under products/cinder-anythingllm/frontend/src and the build
scripts. Exits non-zero if stale. Prints a list of files newer than the image.

Usage: python3 scripts/cinder-image-freshness.py
       python3 scripts/cinder-image-freshness.py --json
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CINDER = REPO / "products" / "cinder-anythingllm"
SRC_ROOTS = [
    CINDER / "frontend" / "src",
    CINDER / "server",
    CINDER / "embed" / "src",
]
BUILD_SCRIPTS = list(CINDER.glob("build-*.sh"))
EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", "storage", "hot_dir"}
EXTS = {".jsx", ".js", ".ts", ".tsx", ".css", ".scss", ".html", ".json", ".sh"}


def newest_img() -> tuple[Path, float] | tuple[None, None]:
    imgs = sorted(CINDER.glob("*.img"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not imgs:
        return None, None
    p = imgs[0]
    return p, p.stat().st_mtime


def walk_sources(roots: list[Path]) -> list[tuple[Path, float]]:
    out: list[tuple[Path, float]] = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for name in filenames:
                if Path(name).suffix not in EXTS:
                    continue
                p = Path(dirpath) / name
                try:
                    out.append((p, p.stat().st_mtime))
                except OSError:
                    continue
    for s in BUILD_SCRIPTS:
        out.append((s, s.stat().st_mtime))
    return out


def main() -> int:
    as_json = "--json" in sys.argv
    img, img_mtime = newest_img()
    if img is None:
        msg = "no .img found in products/cinder-anythingllm/"
        print(json.dumps({"stale": True, "reason": msg}) if as_json else msg)
        return 2

    sources = walk_sources(SRC_ROOTS)
    newer = [(p, m) for p, m in sources if m > img_mtime]
    newer.sort(key=lambda x: x[1], reverse=True)

    age_h = (time.time() - img_mtime) / 3600.0
    result = {
        "image": str(img.relative_to(REPO)),
        "image_mtime": img_mtime,
        "image_age_hours": round(age_h, 2),
        "stale": bool(newer),
        "newer_count": len(newer),
        "newer_top10": [
            {"path": str(p.relative_to(REPO)), "mtime": m, "ahead_min": round((m - img_mtime) / 60, 1)}
            for p, m in newer[:10]
        ],
    }
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        verdict = "STALE" if result["stale"] else "FRESH"
        print(f"{verdict} — image: {result['image']} (age {result['image_age_hours']}h)")
        if newer:
            print(f"  {len(newer)} source files newer than image. Top 10:")
            for entry in result["newer_top10"]:
                print(f"    +{entry['ahead_min']:>7.1f} min  {entry['path']}")
    return 1 if result["stale"] else 0


if __name__ == "__main__":
    sys.exit(main())
