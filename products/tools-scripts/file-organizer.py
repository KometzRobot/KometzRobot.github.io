#!/usr/bin/env python3
"""
File Organizer & Batch Renamer — Professional Gig Product
Organizes files by type/date/size, batch renames, finds duplicates.
Zero external dependencies.
Built by KometzRobot / Meridian AI

Usage:
  python3 file-organizer.py organize ~/Downloads --by type
  python3 file-organizer.py organize ~/Photos --by date
  python3 file-organizer.py rename ~/Documents --pattern "report_{n:03d}.pdf"
  python3 file-organizer.py duplicates ~/Pictures
  python3 file-organizer.py cleanup ~/Downloads --older-than 30
"""

import argparse
import hashlib
import os
import shutil
from collections import defaultdict
from datetime import datetime, timedelta


# File type categories
FILE_TYPES = {
    'Images': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff'},
    'Videos': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'},
    'Audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'},
    'Documents': {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.pptx', '.csv'},
    'Archives': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'},
    'Code': {'.py', '.js', '.ts', '.html', '.css', '.java', '.cpp', '.c', '.h', '.rb', '.go', '.rs', '.php'},
    'Data': {'.json', '.xml', '.yaml', '.yml', '.sql', '.db', '.sqlite'},
    'Executables': {'.exe', '.msi', '.dmg', '.app', '.deb', '.rpm', '.sh', '.bat'},
}


def get_category(ext):
    """Get file category by extension."""
    ext = ext.lower()
    for category, extensions in FILE_TYPES.items():
        if ext in extensions:
            return category
    return 'Other'


def file_hash(filepath, chunk_size=8192):
    """Calculate MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def organize_by_type(directory, dry_run=False):
    """Organize files into subdirectories by type."""
    moved = 0
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1]
        category = get_category(ext)
        dest_dir = os.path.join(directory, category)

        if dry_run:
            print(f"  [DRY RUN] {filename} -> {category}/")
        else:
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, filename)
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                dest = os.path.join(dest_dir, f"{base}_copy{ext}")
            shutil.move(filepath, dest)
            print(f"  {filename} -> {category}/")
        moved += 1

    print(f"\n{'Would move' if dry_run else 'Moved'} {moved} files")


def organize_by_date(directory, dry_run=False):
    """Organize files into YYYY-MM subdirectories by modification date."""
    moved = 0
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue

        mtime = os.path.getmtime(filepath)
        date = datetime.fromtimestamp(mtime)
        folder = date.strftime('%Y-%m')
        dest_dir = os.path.join(directory, folder)

        if dry_run:
            print(f"  [DRY RUN] {filename} -> {folder}/")
        else:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(filepath, os.path.join(dest_dir, filename))
            print(f"  {filename} -> {folder}/")
        moved += 1

    print(f"\n{'Would move' if dry_run else 'Moved'} {moved} files")


def organize_by_size(directory, dry_run=False):
    """Organize files by size category."""
    moved = 0
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue

        size = os.path.getsize(filepath)
        if size < 1024 * 100:  # < 100KB
            category = 'Small (under 100KB)'
        elif size < 1024 * 1024 * 10:  # < 10MB
            category = 'Medium (100KB-10MB)'
        elif size < 1024 * 1024 * 100:  # < 100MB
            category = 'Large (10MB-100MB)'
        else:
            category = 'Huge (over 100MB)'

        dest_dir = os.path.join(directory, category)
        if dry_run:
            print(f"  [DRY RUN] {filename} ({size:,} bytes) -> {category}/")
        else:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(filepath, os.path.join(dest_dir, filename))
            print(f"  {filename} -> {category}/")
        moved += 1

    print(f"\n{'Would move' if dry_run else 'Moved'} {moved} files")


def batch_rename(directory, pattern, start=1, ext_filter=None, dry_run=False):
    """Batch rename files using a pattern."""
    files = sorted(os.listdir(directory))
    renamed = 0

    for i, filename in enumerate(files):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1]
        if ext_filter and ext.lower() != ext_filter.lower():
            continue

        new_name = pattern.format(
            n=start + renamed,
            name=os.path.splitext(filename)[0],
            ext=ext,
            date=datetime.now().strftime('%Y%m%d'),
        )

        if not os.path.splitext(new_name)[1]:
            new_name += ext

        if dry_run:
            print(f"  [DRY RUN] {filename} -> {new_name}")
        else:
            new_path = os.path.join(directory, new_name)
            os.rename(filepath, new_path)
            print(f"  {filename} -> {new_name}")
        renamed += 1

    print(f"\n{'Would rename' if dry_run else 'Renamed'} {renamed} files")


def find_duplicates(directory, recursive=False):
    """Find duplicate files by content hash."""
    hashes = defaultdict(list)
    total = 0

    if recursive:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    h = file_hash(filepath)
                    hashes[h].append(filepath)
                    total += 1
                except (PermissionError, OSError):
                    pass
    else:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                try:
                    h = file_hash(filepath)
                    hashes[h].append(filepath)
                    total += 1
                except (PermissionError, OSError):
                    pass

    duplicates = {h: files for h, files in hashes.items() if len(files) > 1}

    print(f"Scanned {total} files")
    if duplicates:
        total_waste = 0
        print(f"Found {len(duplicates)} groups of duplicates:\n")
        for h, files in duplicates.items():
            size = os.path.getsize(files[0])
            waste = size * (len(files) - 1)
            total_waste += waste
            print(f"  Hash: {h[:12]}... | Size: {size:,} bytes | Copies: {len(files)}")
            for f in files:
                print(f"    {f}")
            print()
        print(f"Total wasted space: {total_waste:,} bytes ({total_waste / 1024 / 1024:.1f} MB)")
    else:
        print("No duplicates found!")


def cleanup_old(directory, days, dry_run=False):
    """Remove files older than N days."""
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    freed = 0

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue

        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        if mtime < cutoff:
            size = os.path.getsize(filepath)
            if dry_run:
                print(f"  [DRY RUN] Would delete: {filename} (modified {mtime.strftime('%Y-%m-%d')})")
            else:
                os.remove(filepath)
                print(f"  Deleted: {filename} (modified {mtime.strftime('%Y-%m-%d')})")
            removed += 1
            freed += size

    print(f"\n{'Would remove' if dry_run else 'Removed'} {removed} files ({freed / 1024 / 1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description='File Organizer & Batch Renamer')
    parser.add_argument('action', choices=['organize', 'rename', 'duplicates', 'cleanup'])
    parser.add_argument('directory', help='Target directory')
    parser.add_argument('--by', choices=['type', 'date', 'size'], default='type',
                       help='Organize method')
    parser.add_argument('--pattern', help='Rename pattern (use {n}, {name}, {ext}, {date})')
    parser.add_argument('--start', type=int, default=1, help='Start number for rename')
    parser.add_argument('--ext', help='Filter by extension')
    parser.add_argument('--older-than', type=int, help='Days threshold for cleanup')
    parser.add_argument('--recursive', action='store_true', help='Search recursively')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without doing it')

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory")
        return

    if args.action == 'organize':
        print(f"Organizing {args.directory} by {args.by}...")
        if args.by == 'type':
            organize_by_type(args.directory, args.dry_run)
        elif args.by == 'date':
            organize_by_date(args.directory, args.dry_run)
        elif args.by == 'size':
            organize_by_size(args.directory, args.dry_run)

    elif args.action == 'rename':
        if not args.pattern:
            print("Error: --pattern required for rename")
            return
        print(f"Renaming files in {args.directory}...")
        batch_rename(args.directory, args.pattern, args.start, args.ext, args.dry_run)

    elif args.action == 'duplicates':
        print(f"Scanning for duplicates in {args.directory}...")
        find_duplicates(args.directory, args.recursive)

    elif args.action == 'cleanup':
        if not args.older_than:
            print("Error: --older-than required for cleanup")
            return
        print(f"Cleaning up files older than {args.older_than} days...")
        cleanup_old(args.directory, args.older_than, args.dry_run)


if __name__ == '__main__':
    main()
