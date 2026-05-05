#!/usr/bin/env python3
"""Daily backup of memory.db using SQLite online backup, with retention."""
import os, sys, sqlite3, datetime, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'data', 'memory.db')
KEEP = 7  # daily backups to retain


def main():
    if not os.path.exists(SRC):
        print(f'SOURCE MISSING: {SRC}')
        return 1

    today = datetime.datetime.now().strftime('%Y%m%d')
    dst = os.path.join(REPO, 'data', f'memory.db.backup.{today}')

    src_conn = sqlite3.connect(SRC)
    dst_conn = sqlite3.connect(dst)
    with dst_conn:
        src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    integ = sqlite3.connect(dst).execute('PRAGMA integrity_check').fetchone()[0]
    if integ != 'ok':
        print(f'INTEGRITY FAIL: {integ}')
        os.rename(dst, dst + '.corrupt')
        return 2

    backups = sorted(glob.glob(os.path.join(REPO, 'data', 'memory.db.backup.*')))
    backups = [b for b in backups if not b.endswith('.corrupt')]
    pruned = 0
    for old in backups[:-KEEP]:
        os.remove(old)
        pruned += 1

    size_mb = os.path.getsize(dst) / 1024 / 1024
    print(f'OK {dst} ({size_mb:.1f}MB) integrity=ok pruned={pruned}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
