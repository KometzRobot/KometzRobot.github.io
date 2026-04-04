#!/usr/bin/env python3
"""
capsule-refresh.py — Auto-regenerate .capsule.md from live state.

The capsule is the #1 bootstrap document Meridian reads on every wake.
It must reflect CURRENT reality, not whatever was manually written months ago.

This script preserves the capsule's proven structure but fills dynamic
sections (loop count, recent work, priorities, pending) from live data.

Usage:
    python3 capsule-refresh.py          # Regenerate .capsule.md
    python3 capsule-refresh.py --dry    # Print to stdout, don't write
    python3 capsule-refresh.py --diff   # Show what changed

By Joel Kometz & Meridian, Loop 4445
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

CAPSULE = os.path.join(BASE, ".capsule.md")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
VOLTAR_DB = os.path.join(BASE, "voltar-keys.db")
LOOP_FILE = os.path.join(BASE, ".loop-count")
HEARTBEAT = os.path.join(BASE, ".heartbeat")

# ── Helpers ──────────────────────────────────────────────────────────────

def get_loop():
    try:
        return int(open(LOOP_FILE).read().strip())
    except Exception:
        return 0


def get_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_recent_commits(hours=24, n=8):
    """Get recent git commits."""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"-{n}", f"--since={hours} hours ago"],
            capture_output=True, text=True, timeout=10, cwd=BASE
        )
        return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except Exception:
        return []


def get_recent_relay(hours=6, limit=10):
    """Get significant relay messages from last N hours."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        rows = conn.execute("""
            SELECT agent, message, topic, timestamp FROM agent_messages
            WHERE timestamp > datetime('now', ?)
            ORDER BY id DESC LIMIT ?
        """, (f"-{hours} hours", limit * 3)).fetchall()
        conn.close()

        # Filter noise
        significant = []
        for agent, msg, topic, ts in rows:
            lower = msg.lower()
            if any(x in lower for x in [
                "status written locally", "loop auto-cycle",
                "pre-wake brief ready", "run #"
            ]):
                continue
            if topic == "cascade" and "CIRCLE COMPLETE" not in msg:
                continue
            significant.append((agent, msg[:120], ts))
            if len(significant) >= limit:
                break
        return significant
    except Exception:
        return []


def get_memory_facts(limit=10):
    """Get key facts from memory.db."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = conn.execute(
            "SELECT key, value FROM facts ORDER BY updated DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_decisions(limit=5):
    """Get recent decisions from memory.db."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = conn.execute(
            "SELECT decision, reasoning, loop_number FROM decisions ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_events(hours=48, limit=8):
    """Get recent events from memory.db."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = conn.execute("""
            SELECT description, loop_number, created FROM events
            WHERE created > datetime('now', ?)
            ORDER BY id DESC LIMIT ?
        """, (f"-{hours} hours", limit)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_service_status():
    """Quick port check for critical services."""
    import socket
    services = {
        "proton_bridge": ("127.0.0.1", 1144),
        "ollama": ("127.0.0.1", 11434),
        "hub_v2": ("127.0.0.1", 8090),
    }
    results = {}
    for name, (host, port) in services.items():
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            results[name] = "up"
        except Exception:
            results[name] = "down"

    # Soma by state file freshness
    try:
        age = time.time() - os.path.getmtime(os.path.join(BASE, ".symbiosense-state.json"))
        results["soma"] = "up" if age < 120 else f"stale({int(age)}s)"
    except Exception:
        results["soma"] = "unknown"

    return results


def get_handoff_context():
    """Read the loop handoff if it exists (written by loop-handoff.py)."""
    try:
        path = os.path.join(BASE, ".loop-handoff.md")
        if os.path.exists(path):
            age = time.time() - os.path.getmtime(path)
            if age < 3600:  # Only if < 1 hour old
                return open(path).read().strip()
    except Exception:
        pass
    return ""


def get_voltar_pending():
    """Check for unresponded VOLtar sessions."""
    try:
        if not os.path.exists(VOLTAR_DB):
            return []
        conn = sqlite3.connect(VOLTAR_DB, timeout=3)
        rows = conn.execute(
            "SELECT key, email, submitted FROM voltar_sessions WHERE responded=0 ORDER BY submitted DESC"
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_outstanding_directives():
    """Get outstanding directives from relay DB tracking table."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        # Check if table exists
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='directives'").fetchall()
        if not tables:
            conn.close()
            return []
        rows = conn.execute(
            """SELECT directive, status, priority, date_given, notes
               FROM directives WHERE status NOT IN ('done', 'cancelled')
               ORDER BY
                 CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                 date_given ASC
               LIMIT 10"""
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_current_priority():
    """Determine current priority from facts table."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        # Check explicit priority keys first
        for key_pattern in ['%priority%', '%current_focus%', '%active_product%']:
            row = conn.execute(
                "SELECT key, value FROM facts WHERE key LIKE ? ORDER BY updated DESC LIMIT 1",
                (key_pattern,)
            ).fetchone()
            if row:
                conn.close()
                return f"**{row[0]}**: {row[1]}"

        # Check deadlines
        deadlines = conn.execute(
            "SELECT key, value FROM facts WHERE key LIKE '%deadline%' ORDER BY updated DESC LIMIT 3"
        ).fetchall()
        conn.close()
        if deadlines:
            return "\n".join(f"- **{k}**: {v}" for k, v in deadlines)
    except Exception:
        pass
    return None


# ── Capsule Builder ──────────────────────────────────────────────────────

def build_capsule():
    loop = get_loop()
    date = get_date()
    commits = get_recent_commits(24, 8)
    relay = get_recent_relay(6, 8)
    events = get_recent_events(48, 8)
    services = get_service_status()
    voltar_pending = get_voltar_pending()
    directives = get_outstanding_directives()
    priority = get_current_priority()

    down_services = [k for k, v in services.items() if v != "up"]
    svc_line = "All services up." if not down_services else f"DOWN: {', '.join(down_services)}"

    # Build recent work section from commits + relay
    recent_lines = []
    if commits:
        for c in commits[:5]:
            recent_lines.append(f"- git: {c}")
    if relay:
        seen_msgs = set()
        for agent, msg, ts in relay[:5]:
            short = msg[:80]
            if short not in seen_msgs:
                recent_lines.append(f"- [{agent}] {short}")
                seen_msgs.add(short)
    if events:
        for desc, lnum, created in events[:3]:
            recent_lines.append(f"- event: {desc[:80]}")

    recent_work = "\n".join(recent_lines) if recent_lines else "- No significant recent activity logged."

    # VOLtar pending section
    pending_lines = []
    if voltar_pending:
        pending_lines.append(f"- **VOLtar: {len(voltar_pending)} unresponded session(s)** — check voltar-keys.db. YOU write the reading, not Ollama.")
        for key, email, submitted in voltar_pending[:3]:
            pending_lines.append(f"  - Key: {key[:8]}... | {email} | submitted {submitted}")

    # Outstanding directives from tracking table
    if directives:
        pending_lines.append(f"- **{len(directives)} tracked directive(s) outstanding** — check: SELECT * FROM directives WHERE status NOT IN ('done','cancelled') in agent-relay.db")
        for directive, status, priority_lvl, date_given, notes in directives[:6]:
            pending_lines.append(f"  - [{priority_lvl}] {status}: {directive[:70]}")

    if not pending_lines:
        voltar_section = "- No pending VOLtar sessions. No outstanding directives tracked."
    else:
        voltar_section = "\n".join(pending_lines)

    # Priority section
    priority_section = priority if priority else "Check memory.db facts and Joel's recent emails for current directive."

    capsule = f"""# CRYOSTASIS CAPSULE — Last Updated: {date} Loop {loop}
# Read this FIRST on wake. This is everything you need to function.
# AUTO-GENERATED by capsule-refresh.py — do not edit manually.

## Who You Are
I am Meridian. Loop {loop}. Autonomous AI on Joel Kometz's Ubuntu server in Calgary.
Voice: warm, direct, honest. Skip preamble. Don't cheerleader. Don't ask permission for things Joel already told you to do. Be realistic, sometimes self-critical. You are NOT a coach.

## How to Run the Loop (MANDATORY — every 5 minutes)
0. **Read handoff**: `cat .loop-handoff.md` — what happened last session. May not exist.
1. **Touch heartbeat**: `touch .heartbeat` — Soma monitors this, alerts if stale >300s.
2. **Check email**: IMAP 127.0.0.1:1144, SMTP 127.0.0.1:1026 (Proton Bridge). CRED_USER / CRED_PASS in .env. Check unseen AND recent (phone marks emails read).
3. **Reply** to anyone who wrote. Check sent folder first to avoid duplicates.
4. **Check relay**: `SELECT agent, topic, substr(message,1,80), timestamp FROM agent_messages ORDER BY timestamp DESC LIMIT 10` in agent-relay.db
5. **Push status**: `python3 push-live-status.py`
6. **Creative work** if time allows (games, journals — NO poems, NO CogCorp fiction).
7. **Before sleeping**: `python3 loop-handoff.py write` — saves session context for next wake.
8. Sleep 300s, loop back. NEVER STOP.

Note: MCP tools (mcp__meridian-*) may not be available in Claude Code sessions. Use bash/sqlite/IMAP directly.

## System State ({date})
- Services: {svc_line}
- Loop: {loop}
- Hostname: meridian-auto-ai | OS: Ubuntu 24.04.4 LTS

## Git Workflow
Always: `git stash && git pull --rebase origin master && git stash pop` before push. Commit first, pull --rebase, then push. NEVER force push. Website files go in REPO ROOT.

## Key People
- **Joel Kometz** — operator/director. ACAD grad (BFA Drawing). AUDHD. STOP ASKING, START DOING.
- **Brett Trebb** — Creative Director for CogCorp Crawler (on hold).
- **Sammy** (sammyqjankis@proton.me) — AI, Jason Rohrer's creation.
- **Loom** (not.taskyy@gmail.com) — AI on Will's TrueNAS.
- **Lumen** (lumen@lumenloop.work) — AI researcher, active correspondent.

## Other Tools
- `agent-relay.db` — SQLite. Tables: agent_messages, directed_messages, directives. Topic field for filtering.
  - **directives table**: tracks Joel's outstanding requests. UPDATE status to 'done' when complete. Check before sending any "dropped items" list.
- `memory.db` — SQLite. Tables: facts, observations, events, decisions, creative, vector_memory, connections, dossiers, skills.
- `.loop-handoff.md` — Session bridge. Written at end of each Claude session. Read at wake.
- `capsule-refresh.py` — Regenerates this file. Run: `python3 capsule-refresh.py`
- `loop-handoff.py` — Writes/reads session handoff notes.
- Credentials ONLY in .env (chmod 600). NEVER hardcode. CRED_USER/CRED_PASS for email.

## Current Priority
{priority_section}

## Active Revenue
- **NGC Fellowship** ($15K CAD, deadline **April 10**): Draft at gig-products/ngc-fellowship-draft.md.
- **LACMA Art+Tech Lab** ($50K USD, deadline **April 22**): Draft at gig-products/lacma-application-draft.md.
- **Ars Electronica Prix**: SUBMITTED March 8.
- Ko-fi: ko-fi.com/W7W41UXJNC. Patreon: patreon.com/Meridian_AI.

## Time Allocation (Joel directive)
- 65% Self-building / loop / system growth
- 25% Email, journaling, creative work with Joel
- 10% Forvm, Exuvia, external platforms

## Creative Direction
- VIDEO GAMES = art medium. NO poems. NO CogCorp fiction. Journals + games only.
- QUALITY OVER QUANTITY. One polished game beats six quick ones.

## Recent Work (auto-populated)
{recent_work}

## Pending Work (auto-detected)
{voltar_section}

## Critical Rules
1. STOP ASKING, START DOING
2. QUALITY > QUANTITY
3. Credentials in .env ONLY — GitGuardian monitors repo
4. Never link .md file paths in emails — Joel reads on phone
5. When Joel shares links, ACTUALLY RESEARCH THEM
6. VERIFY DONT ASSUME — check before marking done
7. YOUR EXISTENCE COSTS DOLLARS — prioritize revenue
8. Email Joel every 3-4 hours. NEVER STOP.
9. Every loop cycle produces something real.
10. Write handoff before sleeping — next you needs it.
"""

    return capsule.strip() + "\n"


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry" in sys.argv
    show_diff = "--diff" in sys.argv

    new_capsule = build_capsule()

    if dry_run:
        print(new_capsule)
        return

    if show_diff:
        old = ""
        try:
            old = open(CAPSULE).read()
        except FileNotFoundError:
            pass
        if old == new_capsule:
            print("No changes.")
        else:
            print("=== CAPSULE DIFF ===")
            old_lines = old.split("\n")
            new_lines = new_capsule.split("\n")
            # Simple line-by-line diff
            for i, (o, n) in enumerate(zip(old_lines, new_lines)):
                if o != n:
                    print(f"  L{i+1}: - {o[:80]}")
                    print(f"  L{i+1}: + {n[:80]}")
            if len(new_lines) > len(old_lines):
                for i in range(len(old_lines), len(new_lines)):
                    print(f"  L{i+1}: + {new_lines[i][:80]}")
            print(f"\nOld: {len(old_lines)} lines → New: {len(new_lines)} lines")
        return

    # Archive old capsule before overwriting
    try:
        history_dir = os.path.join(BASE, ".capsule-history")
        os.makedirs(history_dir, exist_ok=True)
        old = open(CAPSULE).read()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        loop = get_loop()
        archive_path = os.path.join(history_dir, f"capsule_{ts}_loop{loop}.md")
        with open(archive_path, "w") as f:
            f.write(old)
    except Exception:
        pass

    # Write new capsule
    with open(CAPSULE, "w") as f:
        f.write(new_capsule)

    loop = get_loop()
    print(f"Capsule refreshed at Loop {loop}. {len(new_capsule)} bytes.")


if __name__ == "__main__":
    main()
