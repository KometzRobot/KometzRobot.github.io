#!/usr/bin/env python3
"""Rotate logs in logs/ that exceed THRESHOLD_BYTES.

Strategy: when a log is over threshold, gzip-compress it as .log.1.gz, drop the
oldest generation, and start a fresh empty .log. Keeps KEEP_GENERATIONS rotations.

Run from cron every few hours. Idempotent; logs under threshold are skipped.
"""
import os
import glob
import gzip
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE, "logs")
THRESHOLD_BYTES = 500 * 1024
KEEP_GENERATIONS = 3


def rotate(path: str) -> bool:
    rotated = False
    # shift older generations: .log.N.gz -> .log.(N+1).gz, dropping the oldest
    oldest = f"{path}.{KEEP_GENERATIONS}.gz"
    if os.path.exists(oldest):
        os.remove(oldest)
    for n in range(KEEP_GENERATIONS - 1, 0, -1):
        src = f"{path}.{n}.gz"
        dst = f"{path}.{n + 1}.gz"
        if os.path.exists(src):
            os.rename(src, dst)

    # compress current log to .log.1.gz, then truncate
    with open(path, "rb") as f_in, gzip.open(f"{path}.1.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    open(path, "w").close()
    rotated = True
    return rotated


def main():
    if not os.path.isdir(LOGS_DIR):
        return 0
    rotated = []
    for path in glob.glob(os.path.join(LOGS_DIR, "*.log")):
        try:
            if os.path.getsize(path) > THRESHOLD_BYTES:
                rotate(path)
                rotated.append(os.path.basename(path))
        except OSError as e:
            print(f"skip {path}: {e}", file=sys.stderr)
    if rotated:
        print(f"rotated {len(rotated)}: {', '.join(rotated)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
