"""
Proton mailbox archiver — snapshots all mail to a local mbox file.

Reason: Proton Mail Plus expires 2026-05-18. After that, Bridge stops
authenticating. The mailbox stays alive (downgraded to free) but we
can't poll it from this server. This script dumps the current state
to disk so the history isn't trapped behind a paywall login.

Usage:
    python3 scripts/proton-archive.py [--folder INBOX] [--out backups/proton-INBOX.mbox]

Run before May 18 to capture everything. Re-run anytime for an updated
snapshot. Existing mbox files are overwritten, not appended (mbox is
idempotent — same UID = same message).

To capture all standard folders in one shot:
    for f in INBOX Sent Drafts Archive "All Mail" Trash; do
        python3 scripts/proton-archive.py --folder "$f"
    done
"""

import argparse
import mailbox
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from load_env import *  # noqa: F401, F403
from mail_endpoint import imap_open


def safe_filename(folder):
    return folder.replace("/", "_").replace(" ", "_")


def archive(folder, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()  # mbox.add appends; we want a fresh snapshot
    mb = mailbox.mbox(str(out_path))
    mb.lock()
    saved = 0
    try:
        with imap_open(timeout=60) as m:
            typ, _ = m.select(f'"{folder}"', readonly=True)
            if typ != "OK":
                print(f"[proton-archive] cannot select {folder}: {typ}")
                return 0
            typ, data = m.search(None, "ALL")
            if typ != "OK":
                print(f"[proton-archive] search failed in {folder}")
                return 0
            ids = data[0].split()
            total = len(ids)
            print(f"[proton-archive] {folder}: {total} messages")
            for n, uid in enumerate(ids, 1):
                try:
                    typ, fetched = m.fetch(uid, "(RFC822)")
                    if typ != "OK" or not fetched or fetched[0] is None:
                        continue
                    raw = fetched[0][1]
                    mb.add(raw)
                    saved += 1
                    if n % 100 == 0:
                        print(f"  [{n}/{total}] saved {saved}")
                        mb.flush()
                except Exception as e:
                    print(f"  uid {uid!r} failed: {e}")
    finally:
        mb.flush()
        mb.unlock()
        mb.close()
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="INBOX")
    ap.add_argument("--out", default=None,
                    help="output path; default backups/proton-<folder>.mbox")
    args = ap.parse_args()

    out = Path(args.out) if args.out else Path(
        f"backups/proton-{safe_filename(args.folder)}.mbox"
    )
    start = time.time()
    saved = archive(args.folder, out)
    elapsed = time.time() - start
    size = out.stat().st_size if out.exists() else 0
    print(
        f"[proton-archive] done: {saved} messages, "
        f"{size/1024/1024:.1f} MB, {elapsed:.1f}s, {out}"
    )


if __name__ == "__main__":
    main()
