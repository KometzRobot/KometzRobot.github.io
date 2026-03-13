#!/usr/bin/env python3
"""
Context Preloader — Beefs up wake-state.md with fresh data.

Run at wake-up (before main loop starts) to give Meridian maximum context.
Checks special notes, Soma's nervous system state, recent events, agent health,
unread emails, and Joel's pending requests.

Joel's request: "create a script that beefs up wake state or gets you to
check special notes" (Loop 2053 dashboard)

Usage:
  python3 context-preloader.py          # Print briefing to stdout
  python3 context-preloader.py --file   # Write to context-briefing.md
  python3 context-preloader.py --wake   # Append preload section to wake-state.md
"""

import json
import os
import sys
import sqlite3
import time
import glob
import subprocess
import imaplib
import email
import email.header
from datetime import datetime

try:
    import sys; sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except:
    pass

BASE = "/home/joel/autonomous-ai"
WAKE = os.path.join(BASE, "wake-state.md")
NOTES_FILE = os.path.join(BASE, "special-notes.md")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
DASH_MSG = os.path.join(BASE, ".dashboard-messages.json")
LOOP_FILE = os.path.join(BASE, ".loop-count")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")
HB_FILE = os.path.join(BASE, ".heartbeat")
BRIEFING_FILE = os.path.join(BASE, "context-briefing.md")

IMAP_HOST, IMAP_PORT = "127.0.0.1", 1144
CRED_USER = os.environ.get("CRED_USER", "kometzrobot@proton.me")
CRED_PASS = os.environ.get("CRED_PASS", "")


def read_file(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return default


def get_loop():
    try:
        return int(read_file(LOOP_FILE, "0").strip())
    except Exception:
        return 0


def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(HB_FILE))
    except Exception:
        return -1


def get_email_status():
    try:
        m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        m.login(CRED_USER, CRED_PASS)
        m.select('INBOX')
        _, all_msgs = m.search(None, 'ALL')
        _, unseen = m.search(None, 'UNSEEN')
        total = len(all_msgs[0].split()) if all_msgs[0] else 0
        un = len(unseen[0].split()) if unseen[0] else 0
        m.close()
        m.logout()
        return total, un
    except Exception:
        return -1, -1


def get_recent_joel_emails(n=3):
    try:
        m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        m.login(CRED_USER, CRED_PASS)
        m.select('INBOX')
        _, d = m.search(None, 'FROM', '"jkometz@hotmail.com"')
        ids = d[0].split() if d[0] else []
        results = []
        for uid in ids[-n:]:
            _, md = m.fetch(uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
            if md[0]:
                h = email.message_from_bytes(md[0][1])
                subj = email.header.decode_header(h.get('Subject', ''))[0]
                subj = subj[0].decode() if isinstance(subj[0], bytes) else str(subj[0])
                results.append(subj[:80])
        m.close()
        m.logout()
        return results[::-1]
    except Exception:
        return []


def get_soma_state():
    try:
        with open(SOMA_STATE) as f:
            data = json.load(f)
        agents = data.get("agent_health", {})
        alive = sum(1 for v in agents.values() if v.get("alive"))
        return {
            "mood": data.get("mood", "?"),
            "mood_score": data.get("mood_score", 0),
            "load": data.get("load", 0),
            "ram_pct": data.get("ram_pct", 0),
            "disk_pct": data.get("disk_pct", 0),
            "predictions": data.get("predictions", []),
            "alerts": data.get("alerts", []),
            "agents_alive": alive,
            "agents_total": len(agents),
            "agent_details": {k: v.get("detail", "?") for k, v in agents.items()},
        }
    except Exception:
        return {"mood": "unknown", "mood_score": 0}


def get_recent_relay(n=8):
    try:
        conn = sqlite3.connect(RELAY_DB)
        rows = conn.execute(
            "SELECT agent, message, timestamp FROM agent_messages ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_decisions(n=3):
    try:
        conn = sqlite3.connect(MEMORY_DB)
        rows = conn.execute(
            "SELECT decision, reasoning FROM decisions ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_fitness_score():
    try:
        conn = sqlite3.connect(MEMORY_DB)
        row = conn.execute("SELECT score FROM loop_fitness ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def get_joel_dashboard_msgs(n=5):
    try:
        with open(DASH_MSG) as f:
            data = json.load(f)
        msgs = data.get("messages", data) if isinstance(data, dict) else data
        joel_msgs = [m for m in msgs if m.get("from") == "Joel"]
        return joel_msgs[-n:]
    except Exception:
        return []


def get_service_status():
    results = {}
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    for svc in ["meridian-web-dashboard", "meridian-hub-v16", "cloudflare-tunnel",
                 "symbiosense", "protonmail-bridge"]:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", svc],
                             capture_output=True, text=True, timeout=3, env=env)
            results[svc] = r.stdout.strip()
        except Exception:
            results[svc] = "unknown"
    return results


def get_creative_counts():
    poems = len(set(glob.glob(os.path.join(BASE, "poem-*.md")) + glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md"))))
    journals = len(set(glob.glob(os.path.join(BASE, "journal-*.md")) + glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md"))))
    return poems, journals


def build_briefing():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S MST")
    loop = get_loop()
    hb_age = get_heartbeat_age()
    total_em, unread_em = get_email_status()
    soma = get_soma_state()
    relay = get_recent_relay(8)
    decisions = get_recent_decisions(3)
    joel_msgs = get_joel_dashboard_msgs(5)
    joel_emails = get_recent_joel_emails(3)
    notes = read_file(NOTES_FILE, "").strip()
    svcs = get_service_status()
    fitness = get_fitness_score()
    poems, journals = get_creative_counts()

    lines = []
    lines.append("=" * 60)
    lines.append(f"CONTEXT PRELOAD — {now}")
    lines.append(f"Loop: {loop} | THE AWAKENING (infra-only mode)")
    lines.append(f"Heartbeat: {hb_age}s ago | Fitness: {fitness}/10000")
    lines.append("=" * 60)
    lines.append("")

    # Special notes (persistent reminders Joel or Meridian can write)
    if notes:
        lines.append("## SPECIAL NOTES")
        lines.append(notes)
        lines.append("")

    # Soma nervous system
    lines.append(f"## SOMA: {soma.get('mood', '?')} ({soma.get('mood_score', 0)}/100)")
    lines.append(f"   Load: {soma.get('load', '?')} | RAM: {soma.get('ram_pct', '?')}% | Disk: {soma.get('disk_pct', '?')}%")
    lines.append(f"   Agents: {soma.get('agents_alive', '?')}/{soma.get('agents_total', '?')} alive")
    for aname, detail in soma.get("agent_details", {}).items():
        lines.append(f"     {aname}: {detail}")
    if soma.get("predictions"):
        lines.append("   Predictions: " + " | ".join(soma["predictions"]))
    if soma.get("alerts"):
        lines.append("   Alerts: " + " | ".join(soma["alerts"][-3:]))
    lines.append("")

    # Services
    lines.append("## SERVICES")
    for svc, status in svcs.items():
        sym = "OK" if status == "active" else "!!"
        lines.append(f"   [{sym}] {svc}: {status}")
    lines.append("")

    # Email
    lines.append(f"## EMAIL: {unread_em} unread / {total_em} total")
    if joel_emails:
        lines.append("   Joel's recent:")
        for s in joel_emails:
            lines.append(f"     - {s}")
    lines.append("")

    # Joel's dashboard messages
    if joel_msgs:
        lines.append("## JOEL'S PENDING REQUESTS")
        for m in joel_msgs:
            lines.append(f"   [{m.get('time', '?')}] {m.get('text', '')[:120]}")
        lines.append("")

    # Agent relay
    if relay:
        lines.append("## RECENT RELAY")
        for agent, msg, ts in relay:
            lines.append(f"   [{ts}] {agent}: {msg[:100]}")
        lines.append("")

    # Decisions
    if decisions:
        lines.append("## RECENT DECISIONS")
        for dec, reason in decisions:
            lines.append(f"   {dec[:100]}")
        lines.append("")

    # Creative
    lines.append(f"## CREATIVE: {poems} poems, {journals} journals (MORATORIUM active)")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_changelog():
    """Generate a per-loop changelog summarizing what changed."""
    loop = get_loop()
    now = datetime.now()

    # Recently modified key files (last 12 hours)
    cutoff = time.time() - 43200
    modified = []
    for ext in ['*.py', '*.sh', '*.md', '*.html', '*.js', '*.json']:
        for fp in glob.glob(os.path.join(BASE, ext)):
            if os.path.getmtime(fp) > cutoff:
                bn = os.path.basename(fp)
                if not bn.startswith('.'):
                    modified.append(bn)
        for fp in glob.glob(os.path.join(BASE, "website", ext)):
            if os.path.getmtime(fp) > cutoff:
                modified.append("website/" + os.path.basename(fp))

    # Recent git commits
    commits = []
    try:
        r = subprocess.run(['git', 'log', '--oneline', '-5', '--since=12 hours ago'],
                          capture_output=True, text=True, timeout=5, cwd=BASE)
        commits = [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
    except Exception:
        pass

    # Recent relay highlights (unique topics)
    relay_highlights = []
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        rows = conn.execute(
            "SELECT agent, message FROM agent_messages WHERE timestamp > datetime('now', '-12 hours') "
            "AND (message LIKE '%FIXED%' OR message LIKE '%restarted%' OR message LIKE '%deployed%' "
            "OR message LIKE '%AWAKENING%' OR message LIKE '%sprint%' OR topic = 'awakening') "
            "ORDER BY id DESC LIMIT 5").fetchall()
        conn.close()
        for agent, msg in rows:
            relay_highlights.append(f"{agent}: {msg[:100]}")
    except Exception:
        pass

    # Build changelog entry
    entry = f"## Loop {loop} — {now.strftime('%Y-%m-%d %H:%M')}\n"
    if modified:
        entry += f"**Modified ({len(modified)} files):** {', '.join(modified[:20])}\n"
    if commits:
        entry += f"**Commits:** {'; '.join(commits[:5])}\n"
    if relay_highlights:
        entry += "**Highlights:**\n"
        for h in relay_highlights:
            entry += f"- {h}\n"
    entry += "\n"

    # Write to changelog file
    changelog_path = os.path.join(BASE, "loop-changelog.md")
    existing = ""
    try:
        with open(changelog_path) as f:
            existing = f.read()
    except Exception:
        existing = "# Loop Changelog\nAuto-generated per-loop change summaries.\n\n"

    # Don't duplicate if already have an entry for this loop
    if f"## Loop {loop}" not in existing:
        # Insert after header
        header_end = existing.find("\n\n") + 2 if "\n\n" in existing else len(existing)
        new_content = existing[:header_end] + entry + existing[header_end:]
        # Keep only last 20 entries
        entries = new_content.split("## Loop ")
        if len(entries) > 21:
            new_content = entries[0] + "## Loop ".join(entries[:21])
        with open(changelog_path, 'w') as f:
            f.write(new_content)

    # Also store in memory.db
    try:
        conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
        conn.execute(
            "INSERT INTO events (description, agent, created_at) VALUES (?, ?, ?)",
            (f"Loop {loop} changelog: {len(modified)} files modified, {len(commits)} commits",
             "Meridian", now.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return entry


def main():
    briefing = build_briefing()

    if '--changelog' in sys.argv:
        entry = generate_changelog()
        print(entry)
        return

    if '--wake' in sys.argv:
        # Append to wake-state.md as a preload section
        try:
            current = read_file(WAKE)
            marker = "<!-- PRELOAD START -->"
            marker_end = "<!-- PRELOAD END -->"
            if marker in current:
                before = current[:current.index(marker)]
                after = current[current.index(marker_end) + len(marker_end):] if marker_end in current else ""
                current = before.rstrip() + "\n" + after.lstrip()
            with open(WAKE, "w") as f:
                f.write(current.rstrip() + "\n\n")
                f.write(f"{marker}\n")
                f.write(f"### CONTEXT PRELOAD (auto-generated)\n")
                f.write(f"```\n{briefing}\n```\n")
                f.write(f"{marker_end}\n")
            print("Preload appended to wake-state.md")
        except Exception as e:
            print(f"Error: {e}")
    elif '--file' in sys.argv:
        with open(BRIEFING_FILE, 'w') as f:
            f.write(briefing)
        print(f"Written to {BRIEFING_FILE}")
    else:
        print(briefing)


if __name__ == "__main__":
    main()
