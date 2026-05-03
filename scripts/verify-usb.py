#!/usr/bin/env python3
"""verify-usb.py — Verify Cinder USB drive contents against expected manifest.
Prevents the "claimed done but wasn't" problem. Run after building/cloning a USB.

Usage: python3 scripts/verify-usb.py /media/usb0-p1 [/media/usb0-p2]
"""
import sys
import os

# Boot partition (FAT32/exFAT, ~512MB) — launcher scripts
EXPECTED_P1 = {
    "files": [
        "README.txt",
        "Start Cinder.bat",
        "Start Cinder (Mac).command",
        "start-cinder.sh",
        "autorun.inf",
        "Start Cinder.vbs",
    ],
    "dirs": [],
    "critical_files": [],
    "critical_paths": [],
    "min_sizes": {},
}

# App partition (exFAT, ~40GB) — bins, models, data
EXPECTED_P2 = {
    "dirs": [
        "Cinder",
        "Cinder/Windows",
        "Cinder/Linux",
        "Cinder/Mac",
        "Cinder/ollama",
        "Cinder/ollama/models",
        "Cinder/data",
        "Cinder/data/identity",
        "Library Catalogue",
        "Library Catalogue/Code",
        "Library Catalogue/Documents",
        "Library Catalogue/Media",
        "Library Catalogue/Reference",
    ],
    "files": [
        "Cinder/data/identity/Modelfile",
    ],
    "critical_files": [
        "Cinder/Windows/Cinder.exe",
        "Cinder/Linux/cinder-desktop",
        "Cinder/ollama/ollama",
    ],
    "critical_paths": [
        "Cinder/Mac/Cinder.app",  # Mac .app is a directory bundle
        "Cinder/ollama/models/blobs",  # Ollama model blobs directory
    ],
    "min_sizes": {
        "Cinder/Windows/Cinder.exe": 100_000,
        "Cinder/Linux/cinder-desktop": 100_000,
        "Cinder/ollama/ollama": 35_000_000,  # Ollama binary (v0.6+ is ~43MB)
    },
}


def check_path(base, rel, kind="file"):
    full = os.path.join(base, rel)
    if kind == "file":
        return os.path.isfile(full)
    elif kind == "dir":
        return os.path.isdir(full)
    return os.path.exists(full)


def check_size(base, rel, min_bytes):
    full = os.path.join(base, rel)
    if not os.path.isfile(full):
        return False, 0
    size = os.path.getsize(full)
    return size >= min_bytes, size


def verify_partition(base, manifest, label):
    ok = 0
    fail = 0
    warnings = []

    if not os.path.isdir(base):
        print(f"  FAIL: {base} not mounted or doesn't exist")
        return 0, 1

    for d in manifest.get("dirs", []):
        if check_path(base, d, "dir"):
            ok += 1
        else:
            print(f"  MISSING DIR: {d}")
            fail += 1

    for f in manifest.get("files", []):
        if check_path(base, f, "file"):
            ok += 1
        else:
            print(f"  MISSING FILE: {f}")
            fail += 1

    for f in manifest.get("critical_files", []):
        if check_path(base, f, "file"):
            ok += 1
        else:
            print(f"  MISSING CRITICAL: {f}")
            fail += 1

    for p in manifest.get("critical_paths", []):
        if os.path.exists(os.path.join(base, p)):
            ok += 1
        else:
            print(f"  MISSING CRITICAL: {p}")
            fail += 1

    for f, min_bytes in manifest.get("min_sizes", {}).items():
        passed, actual = check_size(base, f, min_bytes)
        if passed:
            ok += 1
        else:
            mb = actual / 1_000_000
            expected_mb = min_bytes / 1_000_000
            print(f"  SIZE FAIL: {f} is {mb:.1f}MB, expected >{expected_mb:.0f}MB")
            fail += 1

    return ok, fail


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify-usb.py <p1_mount> [p2_mount]")
        print("Example: python3 verify-usb.py /media/usb0-p1 /media/usb0-p2")
        sys.exit(1)

    p1 = sys.argv[1]
    p2 = sys.argv[2] if len(sys.argv) > 2 else None

    total_ok = 0
    total_fail = 0

    print(f"Verifying BOOT (P1): {p1}")
    ok, fail = verify_partition(p1, EXPECTED_P1, "P1")
    total_ok += ok
    total_fail += fail
    print(f"  BOOT: {ok} passed, {fail} failed")

    if p2:
        print(f"Verifying APP (P2): {p2}")
        ok, fail = verify_partition(p2, EXPECTED_P2, "P2")
        total_ok += ok
        total_fail += fail
        print(f"  APP: {ok} passed, {fail} failed")

    print(f"\nTotal: {total_ok} passed, {total_fail} failed")
    if total_fail == 0:
        print("USB VERIFIED OK")
    else:
        print("USB HAS ISSUES — fix before shipping")
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
