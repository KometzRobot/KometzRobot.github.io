#!/usr/bin/env python3
"""
photo-catalog-gen.py — Scans all project images (excluding node_modules, mcp,
game-assets, .git), extracts EXIF/metadata, categorizes by project, and
generates creative/writing/photo-catalog.md.
"""

import os
import sys
import json
import datetime
from pathlib import Path
from collections import defaultdict

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("Pillow not available. Install with: pip install Pillow --break-system-packages")
    sys.exit(1)

BASE = Path("/home/joel/autonomous-ai")
OUTPUT = BASE / "creative" / "writing" / "photo-catalog.md"

# Directories to skip entirely
SKIP_DIRS = {
    "node_modules", "mcp", ".git", "game-assets",
    "unsloth_compiled_cache", "__pycache__",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# ── Project categorization ──────────────────────────────────────────────

def categorize(rel_path: str, filename: str) -> str:
    """Assign a project category based on path and filename."""
    fn = filename.lower()
    rp = rel_path.lower()

    # NGC Grant
    if fn.startswith("ngc-") or "/ngc-" in rp or "ngc_" in fn:
        return "NGC Grant"

    # LACMA Grant
    if fn.startswith("lacma-") or "/lacma-" in rp:
        return "LACMA Grant"

    # Ars Electronica
    if "ars-submission" in rp or "ars-electronica" in rp or fn.startswith("ars-"):
        return "Ars Electronica Submission"

    # VOLtar
    if fn.startswith("voltar-") or "voltar" in rp:
        return "VOLtar"

    # Mooshu Books
    if fn.startswith("mooshu-") or "mooshu" in rp:
        return "Mooshu Books"

    # Patreon content
    if "patreon" in rp and ("patreon-posts" in rp or "header" in fn or "stats" in fn or "daily-card" in fn or "preview-screenshot" in fn):
        return "Patreon Content"

    # CogCorp / Website
    if any(k in fn for k in ["website-", "crawler-", "cogcorp", "hub-"]) or \
       any(k in rp for k in ["cogcorp", "bots-of-cog"]):
        return "CogCorp / Website"

    # Kinect Vision
    if "kinect" in fn or "kinect" in rp:
        return "Kinect Vision"

    # NFT Previews
    if "nft" in rp or fn.startswith("nft-"):
        return "NFT Archive"

    # Platform Setup (root dotfiles and logs/screenshots for various platforms)
    platform_keys = [
        "opensea", "substack", "medium", "kofi", "devto", "hashnode",
        "linktree", "stakely", "x-login", "patreon", "rarible", "faucet",
        "bmac",
    ]
    if any(k in fn for k in platform_keys):
        return "Platform Setup"

    # Book / Ebook covers
    if any(k in fn for k in ["book-cover", "cover-v", "ebook"]):
        return "Book / Ebook Covers"

    # Video frames (Ars video, demo)
    if "video-frame" in rp or "video-frame" in fn:
        return "Video Frames (Demo Reel)"

    # Agents / System diagrams
    if fn.startswith("agents-") or fn.startswith("daily-"):
        return "System Visuals / Daily Stats"

    # Infrastructure screenshots
    if "infrastructure" in rp:
        return "Infrastructure"

    # Godot / game exports
    if "godot" in rp or "reclamation" in rp:
        return "Game Exports"

    # Orbits
    if "orbits" in fn:
        return "CogCorp / Website"

    # Archive misc
    if "archive" in rp:
        return "Archive / Misc"

    # Logs screenshots (remaining)
    if "logs/screenshots" in rp:
        return "Platform Setup"

    # Self-portrait
    if "self-portrait" in fn or "portrait" in fn:
        return "Self-Portrait / Identity"

    return "Other / Uncategorized"


# ── EXIF extraction ─────────────────────────────────────────────────────

def get_exif_data(filepath: Path) -> dict:
    """Extract EXIF metadata from an image file."""
    result = {
        "width": None,
        "height": None,
        "exif_date": None,
        "camera_make": None,
        "camera_model": None,
        "gps_lat": None,
        "gps_lon": None,
        "gps_readable": None,
        "software": None,
        "color_space": None,
    }

    try:
        with Image.open(filepath) as img:
            result["width"] = img.width
            result["height"] = img.height

            # Try to get EXIF
            exif_raw = img.getexif() if hasattr(img, "getexif") else None
            if not exif_raw:
                return result

            exif = {}
            for tag_id, value in exif_raw.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                exif[tag_name] = value

            # Date
            for date_key in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
                if date_key in exif:
                    try:
                        dt = datetime.datetime.strptime(str(exif[date_key]), "%Y:%m:%d %H:%M:%S")
                        result["exif_date"] = dt.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        result["exif_date"] = str(exif[date_key])
                    break

            # Camera
            if "Make" in exif:
                result["camera_make"] = str(exif["Make"]).strip()
            if "Model" in exif:
                result["camera_model"] = str(exif["Model"]).strip()
            if "Software" in exif:
                result["software"] = str(exif["Software"]).strip()

            # GPS
            gps_info = exif.get("GPSInfo")
            if gps_info and isinstance(gps_info, dict):
                gps = {}
                for gps_tag_id, gps_value in gps_info.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    gps[gps_tag] = gps_value

                def dms_to_decimal(dms, ref):
                    try:
                        d, m, s = [float(x) for x in dms]
                        dec = d + m / 60.0 + s / 3600.0
                        if ref in ("S", "W"):
                            dec = -dec
                        return round(dec, 6)
                    except Exception:
                        return None

                if "GPSLatitude" in gps and "GPSLatitudeRef" in gps:
                    result["gps_lat"] = dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
                if "GPSLongitude" in gps and "GPSLongitudeRef" in gps:
                    result["gps_lon"] = dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
                if result["gps_lat"] and result["gps_lon"]:
                    result["gps_readable"] = f"{result['gps_lat']}, {result['gps_lon']}"

    except Exception as e:
        # Silently handle unreadable images
        pass

    return result


def infer_description(rel_path: str, filename: str) -> str:
    """Infer a human-readable description from the filename and path."""
    fn = filename.lower()
    stem = Path(filename).stem

    # Clean up stem for description
    desc = stem.replace("-", " ").replace("_", " ").replace(".", " ")

    # Add contextual info
    if "screenshot" in fn:
        desc = f"Screenshot: {desc}"
    elif "diagram" in fn:
        desc = f"Diagram: {desc}"
    elif "cover" in fn:
        desc = f"Cover art: {desc}"
    elif "poster" in fn:
        desc = f"Poster: {desc}"
    elif "portrait" in fn:
        desc = f"Portrait: {desc}"
    elif "character" in fn:
        desc = f"Character art: {desc}"
    elif "ticket" in fn:
        desc = f"Ticket design: {desc}"
    elif "machine" in fn:
        desc = f"Machine design: {desc}"
    elif "header" in fn:
        desc = f"Header image: {desc}"
    elif "step" in fn or "login" in fn:
        desc = f"Setup step: {desc}"
    elif "preview" in fn:
        desc = f"Preview: {desc}"
    elif "depth" in fn:
        desc = f"Depth map: {desc}"
    elif "rgb" in fn:
        desc = f"RGB capture: {desc}"
    elif "stats" in fn:
        desc = f"Statistics: {desc}"
    elif "daily" in fn:
        desc = f"Daily visual: {desc}"
    elif "form" in fn or "filled" in fn:
        desc = f"Form/setup: {desc}"
    elif "dashboard" in fn or "dash" in fn:
        desc = f"Dashboard: {desc}"
    elif "style" in fn:
        desc = f"Style reference: {desc}"

    return desc.strip()


def format_size(size_bytes: int) -> str:
    """Format file size nicely."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ── Main scan ───────────────────────────────────────────────────────────

def scan_images():
    """Walk the repo, collect all project images with metadata."""
    images_by_category = defaultdict(list)
    total_size = 0
    total_count = 0
    formats_count = defaultdict(int)
    has_gps = 0
    has_exif_date = 0

    for root, dirs, files in os.walk(BASE):
        # Prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in sorted(files):
            ext = Path(f).suffix.lower()
            if ext not in IMAGE_EXTS:
                continue

            filepath = Path(root) / f
            rel_path = str(filepath.relative_to(BASE))

            # Get file stats
            try:
                stat = filepath.stat()
                file_size = stat.st_size
                file_mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                continue

            # Get EXIF
            exif = get_exif_data(filepath)

            # Determine date (prefer EXIF, fall back to mtime)
            date_str = exif.get("exif_date") or file_mtime
            date_source = "EXIF" if exif.get("exif_date") else "file"

            # Categorize
            category = categorize(rel_path, f)

            # Build record
            record = {
                "filename": f,
                "rel_path": rel_path,
                "date": date_str,
                "date_source": date_source,
                "width": exif.get("width"),
                "height": exif.get("height"),
                "file_size": file_size,
                "file_size_fmt": format_size(file_size),
                "camera": None,
                "gps": exif.get("gps_readable"),
                "software": exif.get("software"),
                "description": infer_description(rel_path, f),
                "format": ext.lstrip(".").upper(),
            }

            if exif.get("camera_make") or exif.get("camera_model"):
                parts = [exif.get("camera_make", ""), exif.get("camera_model", "")]
                record["camera"] = " ".join(p for p in parts if p).strip()

            # Stats
            total_size += file_size
            total_count += 1
            formats_count[record["format"]] += 1
            if exif.get("gps_readable"):
                has_gps += 1
            if exif.get("exif_date"):
                has_exif_date += 1

            images_by_category[category].append(record)

    # Sort each category by date
    for cat in images_by_category:
        images_by_category[cat].sort(key=lambda r: r["date"])

    stats = {
        "total_count": total_count,
        "total_size": total_size,
        "total_size_fmt": format_size(total_size),
        "formats": dict(formats_count),
        "categories": len(images_by_category),
        "has_gps": has_gps,
        "has_exif_date": has_exif_date,
    }

    return images_by_category, stats


def generate_markdown(images_by_category: dict, stats: dict):
    """Generate the photo-catalog.md document."""
    lines = []

    # Header
    lines.append("# Photo & Image Catalog")
    lines.append("")
    lines.append(f"*Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"*Repo: autonomous-ai | Total images: {stats['total_count']} | "
                 f"Total size: {stats['total_size_fmt']}*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Category order (most important first)
    cat_order = [
        "NGC Grant",
        "LACMA Grant",
        "Ars Electronica Submission",
        "VOLtar",
        "Mooshu Books",
        "Patreon Content",
        "CogCorp / Website",
        "Book / Ebook Covers",
        "Kinect Vision",
        "NFT Archive",
        "Platform Setup",
        "Video Frames (Demo Reel)",
        "System Visuals / Daily Stats",
        "Self-Portrait / Identity",
        "Infrastructure",
        "Game Exports",
        "Archive / Misc",
        "Other / Uncategorized",
    ]

    # Ensure all categories appear
    all_cats = list(images_by_category.keys())
    for c in all_cats:
        if c not in cat_order:
            cat_order.append(c)

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    for cat in cat_order:
        if cat not in images_by_category:
            continue
        count = len(images_by_category[cat])
        cat_size = sum(r["file_size"] for r in images_by_category[cat])
        anchor = cat.lower().replace(" ", "-").replace("/", "").replace("(", "").replace(")", "")
        lines.append(f"- [{cat}](#{anchor}) ({count} images, {format_size(cat_size)})")
    lines.append(f"- [Summary Statistics](#summary-statistics)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Each category section
    for cat in cat_order:
        if cat not in images_by_category:
            continue
        records = images_by_category[cat]
        cat_size = sum(r["file_size"] for r in records)

        lines.append(f"## {cat}")
        lines.append("")
        lines.append(f"**{len(records)} images** | {format_size(cat_size)} total")
        lines.append("")

        # Table header
        lines.append("| # | Filename | Path | Date | Source | Dimensions | Size | Format | Location | Camera/Software | Description |")
        lines.append("|---|----------|------|------|--------|------------|------|--------|----------|-----------------|-------------|")

        for i, r in enumerate(records, 1):
            dims = f"{r['width']}x{r['height']}" if r['width'] and r['height'] else "N/A"
            gps = r["gps"] or "--"
            cam = r["camera"] or r["software"] or "--"
            # Truncate long paths
            path_short = r["rel_path"]
            if len(path_short) > 55:
                path_short = "..." + path_short[-52:]

            lines.append(
                f"| {i} | {r['filename']} | `{path_short}` | {r['date']} | {r['date_source']} | "
                f"{dims} | {r['file_size_fmt']} | {r['format']} | {gps} | {cam} | {r['description']} |"
            )

        lines.append("")
        lines.append("---")
        lines.append("")

    # Summary Statistics
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total images cataloged | {stats['total_count']} |")
    lines.append(f"| Total file size | {stats['total_size_fmt']} |")
    lines.append(f"| Project categories | {stats['categories']} |")
    lines.append(f"| Images with EXIF date | {stats['has_exif_date']} |")
    lines.append(f"| Images with GPS data | {stats['has_gps']} |")

    # Format breakdown
    lines.append("")
    lines.append("### Format Breakdown")
    lines.append("")
    lines.append("| Format | Count |")
    lines.append("|--------|-------|")
    for fmt, count in sorted(stats["formats"].items(), key=lambda x: -x[1]):
        lines.append(f"| {fmt} | {count} |")

    # Category breakdown
    lines.append("")
    lines.append("### Images by Project")
    lines.append("")
    lines.append("| Project | Count | Size |")
    lines.append("|---------|-------|------|")
    for cat in cat_order:
        if cat not in images_by_category:
            continue
        records = images_by_category[cat]
        cat_size = sum(r["file_size"] for r in records)
        lines.append(f"| {cat} | {len(records)} | {format_size(cat_size)} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This catalog was auto-generated by `tools/photo-catalog-gen.py`. "
                 "Re-run to update after adding new images.*")
    lines.append("")

    return "\n".join(lines)


# ── Entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Scanning images...")
    images_by_category, stats = scan_images()

    print(f"Found {stats['total_count']} images across {stats['categories']} categories")
    print(f"Total size: {stats['total_size_fmt']}")
    print(f"EXIF dates: {stats['has_exif_date']}, GPS: {stats['has_gps']}")

    print("Generating catalog...")
    md = generate_markdown(images_by_category, stats)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(md)

    print(f"Catalog written to: {OUTPUT}")
    print(f"Lines: {len(md.splitlines())}")

    # Print category summary
    print("\nCategory breakdown:")
    for cat in sorted(images_by_category.keys()):
        print(f"  {cat}: {len(images_by_category[cat])} images")
