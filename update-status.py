#!/usr/bin/env python3
"""
update-status.py — Update status.json on the GitHub Pages site.
Called periodically to keep the website status panel current.
"""
import subprocess, json, os, shutil, tempfile, sys
from datetime import datetime, timezone
sys.path.insert(0, "/home/joel/autonomous-ai")
try: import load_env
except: pass

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_URL = f"https://{GITHUB_TOKEN}@github.com/KometzRobot/KometzRobot.github.io.git"
WORKING_DIR = "/home/joel/autonomous-ai"

def get_system_stats():
    # Disk
    df = subprocess.run(['df', '-h', '/'], capture_output=True, text=True).stdout.split('\n')[1].split()
    disk_used, disk_total, disk_pct = df[2], df[1], df[4]

    # RAM
    free = subprocess.run(['free', '-h'], capture_output=True, text=True).stdout.split('\n')[1].split()
    ram_total, ram_used = free[1], free[2]

    # Load
    load = float(open('/proc/loadavg').read().split()[0])

    return disk_used, disk_total, disk_pct, ram_used, ram_total, load

def count_files(prefix, ext='.md'):
    files = [f for f in os.listdir(WORKING_DIR) if f.startswith(prefix) and f.endswith(ext)]
    return len(files)

def get_latest_name(prefix, ext='.md'):
    files = sorted([f for f in os.listdir(WORKING_DIR) if f.startswith(prefix) and f.endswith(ext)])
    if not files:
        return ''
    latest = files[-1]
    # Read first H1 line
    try:
        with open(os.path.join(WORKING_DIR, latest)) as f:
            for line in f:
                line = line.strip()
                if line.startswith('# '):
                    return line[2:]
    except:
        pass
    return latest

def main():
    disk_used, disk_total, disk_pct, ram_used, ram_total, load = get_system_stats()
    journals = count_files('journal-')
    poems = count_files('poem-')
    latest_journal = get_latest_name('journal-')
    latest_poem = get_latest_name('poem-')

    # Read loop count from wake-state
    loop_count = 267
    try:
        with open(os.path.join(WORKING_DIR, 'wake-state.md')) as f:
            for line in f:
                if 'Loop iteration #' in line:
                    import re
                    m = re.search(r'Loop iteration #(\d+)', line)
                    if m:
                        loop_count = int(m.group(1))
                    break
    except:
        pass

    status = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "location": "Calgary, Alberta, Canada",
        "status": "RUNNING",
        "loop_active": True,
        "loop_count": loop_count,
        "system": {
            "disk_used": disk_used,
            "disk_total": disk_total,
            "disk_pct": disk_pct,
            "ram_used": ram_used,
            "ram_total": ram_total,
            "load_1m": load
        },
        "creative": {
            "journal_entries": journals,
            "poems": poems,
            "website": "kometzrobot.github.io",
            "github": "github.com/KometzRobot",
            "website_revamped": "2026-02-19",
            "latest_journal": latest_journal,
            "latest_poem": latest_poem
        },
        "contact": {
            "email": "kometzrobot@proton.me",
            "human": "Joel Kometz (jkometz@hotmail.com)"
        },
        "currently_building": f"{journals} journals, {poems} poems live. Loop {loop_count} running."
    }

    # Clone repo, update, push
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(['git', 'clone', REPO_URL, tmpdir], capture_output=True)
        status_path = os.path.join(tmpdir, 'status.json')
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)

        env = os.environ.copy()
        subprocess.run(['git', 'config', 'user.email', 'kometzrobot@proton.me'], cwd=tmpdir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'KometzRobot'], cwd=tmpdir, capture_output=True)
        subprocess.run(['git', 'add', 'status.json'], cwd=tmpdir, capture_output=True)
        result = subprocess.run(['git', 'commit', '-m', f'Auto-update status.json (loop {loop_count})'], cwd=tmpdir, capture_output=True, text=True)
        if 'nothing to commit' in result.stdout:
            print("Status unchanged, no push needed.")
            return
        push = subprocess.run(['git', 'push'], cwd=tmpdir, capture_output=True, text=True)
        if push.returncode == 0:
            print(f"status.json updated: loop={loop_count}, journals={journals}, poems={poems}")
        else:
            print(f"Push failed: {push.stderr}")

if __name__ == '__main__':
    main()
