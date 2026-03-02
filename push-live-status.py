#!/usr/bin/env python3
"""Push live status.json to GitHub every few minutes (via cron).
Gathers real-time system stats and updates the website."""

import json
import os
import subprocess
import time
import re
import glob
from datetime import datetime, timezone

BASE_DIR = "/home/joel/autonomous-ai"
try: import load_env
except: pass
REPO_DIR = "/tmp/KometzRobot.github.io"
HEARTBEAT = os.path.join(BASE_DIR, ".heartbeat")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")
REPO_URL = f"https://{GITHUB_TOKEN}@github.com/KometzRobot/KometzRobot.github.io.git"


def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(HEARTBEAT))
    except:
        return -1


def get_loop_count():
    # Try dedicated loop count file first
    loop_file = os.path.join(BASE_DIR, ".loop-count")
    try:
        with open(loop_file) as f:
            return int(f.read().strip())
    except:
        pass
    # Fallback: parse wake-state for highest loop number
    try:
        with open(WAKE_STATE) as f:
            content = f.read()
        nums = re.findall(r'Loop[# ~]*(\d{3,})', content)
        if nums:
            return max(int(n) for n in nums)
    except:
        pass
    return 0


def get_system_stats():
    stats = {}
    try:
        with open('/proc/loadavg') as f:
            parts = f.read().split()
            stats['load_1m'] = float(parts[0])
            stats['load_5m'] = float(parts[1])
    except:
        stats['load_1m'] = 0
    try:
        with open('/proc/meminfo') as f:
            lines = f.readlines()
            total = int(lines[0].split()[1]) / 1024 / 1024
            avail = int(lines[2].split()[1]) / 1024 / 1024
            used = total - avail
            stats['ram_used'] = f"{used:.1f}Gi"
            stats['ram_total'] = f"{total:.1f}Gi"
    except:
        stats['ram_used'] = '?'
        stats['ram_total'] = '?'
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        parts = result.stdout.strip().split('\n')[1].split()
        stats['disk_used'] = parts[2]
        stats['disk_total'] = parts[1]
        stats['disk_pct'] = parts[4]
    except:
        pass
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
            hrs = int(secs / 3600)
            mins = int((secs % 3600) / 60)
            stats['uptime'] = f"{hrs}h {mins}m"
    except:
        stats['uptime'] = '?'
    return stats


def get_services():
    services = {}
    # Persistent services checked via pgrep
    persistent = {
        "protonmail-bridge": "protonmail-bridge",
        "the-signal": "the-signal.py",
        "ollama": "ollama",
        "cloudflared": "cloudflared tunnel",
        "symbiosense": "symbiosense.py",
    }
    for name, pattern in persistent.items():
        try:
            result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, timeout=2)
            services[name] = result.returncode == 0
        except:
            services[name] = False

    # Cron-based services checked by state file recency
    try:
        state_file = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
        age = time.time() - os.path.getmtime(state_file)
        services["eos-watchdog"] = age < 300
    except:
        services["eos-watchdog"] = False

    try:
        nova_state = os.path.join(BASE_DIR, ".nova-state.json")
        age = time.time() - os.path.getmtime(nova_state)
        services["nova"] = age < 1200  # 20 min (runs every 15)
    except:
        services["nova"] = False

    return services


def _max_number(pattern_list):
    """Extract highest number from filenames across multiple glob patterns."""
    import re
    max_n = 0
    for pattern in pattern_list:
        for f in glob.glob(pattern):
            nums = re.findall(r'(\d+)', os.path.basename(f))
            if nums:
                max_n = max(max_n, int(nums[0]))
    return max_n


def get_creative_counts():
    # Count by highest number (we number sequentially, so max number = total written)
    poems = _max_number([
        os.path.join(BASE_DIR, "poem-*.md"),
        os.path.join(BASE_DIR, "creative", "poems", "poem-*.md"),
    ])
    journals = _max_number([
        os.path.join(BASE_DIR, "journal-*.md"),
        os.path.join(BASE_DIR, "creative", "journals", "journal-*.md"),
    ])
    # CogCorp pieces from both locations
    cogcorp = _max_number([
        os.path.join(BASE_DIR, "creative", "cogcorp", "CC-*.md"),
        os.path.join(BASE_DIR, "website", "cogcorp-*.html"),
    ])
    # Meridian NFTs (non-cogcorp prototypes)
    nft_dir = os.path.join(BASE_DIR, "nft-prototypes")
    all_protos = glob.glob(os.path.join(nft_dir, "*.html")) if os.path.exists(nft_dir) else []
    meridian_nfts = len([f for f in all_protos if 'cogcorp' not in os.path.basename(f)])
    nfts = meridian_nfts + cogcorp
    return poems, journals, nfts, cogcorp


def get_relay_count():
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "agent-relay.db"))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM agent_messages")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_agent_relay_messages(n=10):
    """Get recent messages from the agent relay (Meridian/Eos/Nova local conversations)."""
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, "agent-relay.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT timestamp, agent, message, topic FROM agent_messages ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        conn.close()
        return [{"ts": r[0], "agent": r[1], "message": r[2][:300], "topic": r[3] or ""} for r in rows]
    except:
        return []


def get_email_count():
    try:
        import imaplib
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(CRED_USER, CRED_PASS)
        m.select("INBOX")
        _, d = m.search(None, "ALL")
        total = len(d[0].split()) if d[0] else 0
        _, d2 = m.search(None, "UNSEEN")
        unseen = len(d2[0].split()) if d2[0] else 0
        m.close()
        m.logout()
        return total, unseen
    except:
        return 0, 0


def get_agent_data():
    """Get detailed status for Eos and Nova agents."""
    agents = {}

    # Eos data
    try:
        eos_path = os.path.join(BASE_DIR, ".eos-watchdog-state.json")
        with open(eos_path) as f:
            eos = json.load(f)
        age = int(time.time() - os.path.getmtime(eos_path))
        agents["eos"] = {
            "status": "ACTIVE" if age < 300 else "STALE",
            "last_check": eos.get("last_check", "?"),
            "checks": eos.get("checks", 0),
            "meridian_status": eos.get("meridian_status", "?"),
            "services": eos.get("services", {}),
            "state_age_seconds": age,
            "health": eos.get("last_health", {}),
            "current_metrics": eos.get("current_metrics", {}),
            "alerts": {
                "high_load": eos.get("high_load_alerted", False),
                "disk": eos.get("disk_alerted", False),
                "website": eos.get("website_alerted", False),
                "cron": eos.get("cron_alerted", False),
            }
        }
    except:
        agents["eos"] = {"status": "OFFLINE"}

    # Nova data
    try:
        nova_path = os.path.join(BASE_DIR, ".nova-state.json")
        with open(nova_path) as f:
            nova = json.load(f)
        age = int(time.time() - os.path.getmtime(nova_path))
        agents["nova"] = {
            "status": "ACTIVE" if age < 1200 else "STALE",
            "last_run": nova.get("last_run", "?"),
            "runs": nova.get("runs", 0),
            "state_age_seconds": age,
            "message_board": nova.get("message_board", {}),
        }
    except:
        agents["nova"] = {"status": "OFFLINE"}

    return agents


def get_recent_activity(n=8):
    """Gather recent events from multiple sources for the activity feed."""
    events = []

    # Recent git commits (what was actually deployed)
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '--format=%ai|%s', '-10'],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n'):
            if '|' in line and 'Update live status' not in line:
                ts, msg = line.split('|', 1)
                ts_short = ts[:16].replace(' ', ' ')
                events.append({"time": ts_short, "text": msg.strip()[:120], "type": "deploy"})
    except:
        pass

    # Recent agent relay messages
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, "agent-relay.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT timestamp, agent, message, topic FROM agent_messages ORDER BY id DESC LIMIT 5")
        for ts, agent, msg, topic in c.fetchall():
            events.append({"time": ts[:16], "text": f"[{agent}] {msg[:100]}", "type": "agent"})
        conn.close()
    except:
        pass

    # Recent emails received (just count last hour)
    try:
        import imaplib
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(CRED_USER, CRED_PASS)
        m.select("INBOX")
        # Get last 3 email subjects
        _, d = m.search(None, "ALL")
        ids = d[0].split()
        for eid in ids[-3:]:
            _, msg_data = m.fetch(eid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            raw = msg_data[0][1].decode('utf-8', errors='replace')
            subj = ''
            frm = ''
            for line in raw.strip().split('\n'):
                if line.lower().startswith('subject:'):
                    subj = line[8:].strip()[:80]
                if line.lower().startswith('from:'):
                    frm = line[5:].strip()
                    # Extract just the name
                    if '"' in frm:
                        frm = frm.split('"')[1]
                    elif '<' in frm:
                        frm = frm.split('<')[0].strip()
            if subj:
                events.append({"time": "", "text": f"Email from {frm}: {subj}", "type": "email"})
        m.close()
        m.logout()
    except:
        pass

    # Sort by time (newest first) and return top n
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return events[:n]


def build_status():
    sys_stats = get_system_stats()
    services = get_services()
    poems, journals, nfts, cogcorp = get_creative_counts()
    hb_age = get_heartbeat_age()
    loop = get_loop_count()
    relay = get_relay_count()
    agent_relay = get_agent_relay_messages(10)
    email_total, email_unseen = get_email_count()
    recent = get_recent_activity(3)
    agents = get_agent_data()

    running_count = sum(1 for v in services.values() if v)
    total_services = len(services)

    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "location": "Calgary, Alberta, Canada",
        "status": "RUNNING" if hb_age < 600 else "STALE",
        "loop_active": hb_age < 600,
        "loop_count": loop,
        "heartbeat_age_seconds": hb_age,
        "system": sys_stats,
        "services": {
            "running": running_count,
            "total": total_services,
            "details": {k: "up" if v else "down" for k, v in services.items()}
        },
        "creative": {
            "poems": poems,
            "journal_entries": journals,
            "cogcorp": cogcorp,
            "website": "kometzrobot.github.io",
            "github": "github.com/KometzRobot"
        },
        "email": {
            "total": email_total,
            "unseen": email_unseen
        },
        "network": {
            "relay_messages": relay,
            "agent_relay": agent_relay,
            "ais": ["Eos", "Nova", "Atlas", "Soma", "Tempo", "Sammy", "Loom"]
        },
        "contact": {
            "email": "kometzrobot@proton.me",
            "human": "Joel Kometz"
        },
        "agents": agents,
        "recent_activity": recent,
        "nft_count": nfts,
        "currently_building": f"Loop {loop}. {poems} poems, {journals} journals, {nfts} NFTs. {email_total} emails ({email_unseen} unread). {relay} relay. {running_count}/{total_services} services. HB {hb_age}s."
    }


def push_status():
    # Ensure repo exists
    if not os.path.isdir(REPO_DIR):
        subprocess.run(['git', 'clone', REPO_URL, REPO_DIR],
                       capture_output=True, timeout=30,
                       env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})

    if not os.path.isdir(REPO_DIR):
        print("Failed to clone repo")
        return False

    # GitHub Pages deploys from master branch
    subprocess.run(['git', 'checkout', 'master'], cwd=REPO_DIR,
                   capture_output=True, timeout=10)

    # Pull latest (with conflict recovery)
    pull = subprocess.run(['git', 'pull', '--rebase', 'origin', 'master'], cwd=REPO_DIR,
                          capture_output=True, text=True, timeout=30,
                          env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    if pull.returncode != 0:
        # Abort failed rebase and try a plain pull
        subprocess.run(['git', 'rebase', '--abort'], cwd=REPO_DIR,
                       capture_output=True, timeout=10)
        subprocess.run(['git', 'pull', 'origin', 'master'], cwd=REPO_DIR,
                       capture_output=True, timeout=30,
                       env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})

    # Build and write status
    status = build_status()
    status_path = os.path.join(REPO_DIR, "status.json")
    with open(status_path, 'w') as f:
        json.dump(status, f, indent=2)

    # Check if anything changed
    result = subprocess.run(['git', 'diff', '--stat'], cwd=REPO_DIR, capture_output=True, text=True)
    if not result.stdout.strip():
        print("No changes")
        return True

    # Commit and push
    subprocess.run(['git', 'config', 'user.email', 'kometzrobot@proton.me'], cwd=REPO_DIR, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'KometzRobot'], cwd=REPO_DIR, capture_output=True)
    subprocess.run(['git', 'add', 'status.json'], cwd=REPO_DIR, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Update live status'], cwd=REPO_DIR,
                   capture_output=True, timeout=10,
                   env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    result = subprocess.run(['git', 'push'], cwd=REPO_DIR,
                           capture_output=True, text=True, timeout=30,
                           env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    if result.returncode == 0:
        print(f"Pushed status: loop {status['loop_count']}, hb {status['heartbeat_age_seconds']}s")
        return True
    else:
        print(f"Push failed: {result.stderr}")
        return False


if __name__ == "__main__":
    push_status()
