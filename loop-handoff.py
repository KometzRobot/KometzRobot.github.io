#!/usr/bin/env python3
"""
loop-handoff.py — Session memory bridge across context resets.

When Claude's context compresses or the watchdog restarts, everything in
working memory vanishes. This script captures what matters and writes it
to .loop-handoff.md so the next instance picks up where the last left off.

Pulls from ALL agents:
  - Meridian's recent relay posts (what was being worked on)
  - Eos observations (system health, anomalies)
  - Tempo fitness (current score, trends)
  - Soma mood (emotional state, alerts)
  - Memory.db (recent decisions, events, facts)
  - Git log (what was committed recently)
  - Email status (pending/recent from Joel)

Called by:
  - ~/.claude/hooks/precompact.sh (before context compression)
  - Meridian manually: python3 loop-handoff.py write
  - On wake: python3 loop-handoff.py read (prints summary)

By Joel Kometz & Meridian, Loop 4445
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import imaplib
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

try:
    sys.path.insert(0, BASE)
    import load_env
except Exception:
    pass

HANDOFF_FILE = os.path.join(BASE, ".loop-handoff.md")
HANDOFF_HISTORY = os.path.join(BASE, ".handoff-history")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
MEMORY_DB = os.path.join(BASE, "memory.db")
LOOP_FILE = os.path.join(BASE, ".loop-count")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
SOMA_STATE = os.path.join(BASE, ".symbiosense-state.json")
EOS_OBS = os.path.join(BASE, "eos-observations.md")
EOS_STATE = os.path.join(BASE, ".eos-watchdog-state.json")
EOS_REACT_STATE = os.path.join(BASE, ".eos-react-state.json")
DASHBOARD_MSG = os.path.join(BASE, ".dashboard-messages.json")
CONTEXT_FLAGS = os.path.join(BASE, ".context-flags.json")

VOLTAR_DB = os.path.join(BASE, "voltar-keys.db")
IMAP_HOST, IMAP_PORT = "127.0.0.1", 1144
CRED_USER = os.environ.get("CRED_USER", os.environ.get("PROTON_USER", "kometzrobot@proton.me"))
CRED_PASS = os.environ.get("CRED_PASS", "")


# ── Data Collectors ──────────────────────────────────────────────────────

def get_loop():
    try:
        return int(open(LOOP_FILE).read().strip())
    except Exception:
        return 0


def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(HEARTBEAT))
    except Exception:
        return -1


def get_meridian_activity(hours=2, limit=8):
    """What was Meridian (Claude) actually doing? Pull from relay."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        rows = conn.execute("""
            SELECT agent, message, topic, timestamp FROM agent_messages
            WHERE agent IN ('Meridian', 'Claude')
            AND timestamp > datetime('now', ?)
            AND topic != 'loop'
            ORDER BY id DESC LIMIT ?
        """, (f"-{hours} hours", limit)).fetchall()
        conn.close()
        return [(a, m[:150], t, ts) for a, m, t, ts in rows]
    except Exception:
        return []


def get_agent_observations(hours=2, limit=12):
    """What did the other agents observe? Relay messages from Eos, Tempo, Soma, Nova, Atlas."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        rows = conn.execute("""
            SELECT agent, message, topic, timestamp FROM agent_messages
            WHERE agent IN ('Eos', 'Tempo', 'Soma', 'Nova', 'Atlas', 'Hermes', 'Sentinel', 'Cinder', 'DreamEngine')
            AND timestamp > datetime('now', ?)
            ORDER BY id DESC LIMIT ?
        """, (f"-{hours} hours", limit * 2)).fetchall()
        conn.close()

        # Filter noise
        significant = []
        for agent, msg, topic, ts in rows:
            lower = msg.lower()
            if any(x in lower for x in [
                "status written locally", "loop auto-cycle",
                "no action needed", "routine check"
            ]):
                continue
            significant.append((agent, msg[:120], topic, ts))
            if len(significant) >= limit:
                break
        return significant
    except Exception:
        return []


def get_soma_state():
    """Soma's current emotional/system state."""
    try:
        with open(SOMA_STATE) as f:
            data = json.load(f)
        return {
            "mood": data.get("mood", "unknown"),
            "mood_score": data.get("mood_score", 0),
            "load": data.get("load", "?"),
            "ram_pct": data.get("ram_pct", "?"),
            "disk_pct": data.get("disk_pct", "?"),
            "alerts": data.get("alerts", [])[-3:],
            "predictions": data.get("predictions", [])[-2:],
        }
    except Exception:
        return {"mood": "unknown", "mood_score": 0}


def get_eos_recent():
    """Eos's recent observations."""
    try:
        lines = []
        if os.path.exists(EOS_OBS):
            with open(EOS_OBS) as f:
                all_lines = f.readlines()
            # Last 5 non-empty observation lines
            for line in reversed(all_lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped[:120])
                    if len(lines) >= 5:
                        break
            lines.reverse()
        return lines
    except Exception:
        return []


def get_tempo_fitness():
    """Latest fitness score from Tempo."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        row = conn.execute("""
            SELECT message FROM agent_messages
            WHERE agent='Tempo' AND topic='fitness'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        conn.close()
        if row:
            return row[0][:100]
    except Exception:
        pass
    # Fallback: check memory.db
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        row = conn.execute("SELECT score FROM loop_fitness ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if row:
            return f"Fitness score: {row[0]}/10000"
    except Exception:
        pass
    return "Fitness: unknown"


def get_recent_decisions(limit=5):
    """Recent decisions from memory.db."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = conn.execute("""
            SELECT decision, reasoning, loop_number FROM decisions
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_events(hours=6, limit=5):
    """Recent events from memory.db."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        rows = conn.execute("""
            SELECT description, category, loop_number FROM events
            WHERE created > datetime('now', ?)
            ORDER BY id DESC LIMIT ?
        """, (f"-{hours} hours", limit)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_commits(hours=6, limit=5):
    """Recent git commits."""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}", f"--since={hours} hours ago"],
            capture_output=True, text=True, timeout=10, cwd=BASE
        )
        return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except Exception:
        return []


def get_email_status():
    """Quick email check — unseen count + any from Joel."""
    if not CRED_PASS:
        return {"unseen": "?", "joel_recent": []}
    try:
        mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
        mail.login(CRED_USER, CRED_PASS)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        unseen = len(data[0].split()) if data[0] else 0

        # Recent from Joel
        _, joel_data = mail.search(None, 'FROM', '"jkometz@hotmail.com"')
        joel_ids = joel_data[0].split() if joel_data[0] else []
        joel_subjects = []
        for uid in joel_ids[-3:]:
            _, msg_data = mail.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
            if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                import email as _email
                import email.header
                h = _email.message_from_bytes(msg_data[0][1])
                subj = email.header.decode_header(h.get("Subject", ""))[0]
                subj = subj[0].decode() if isinstance(subj[0], bytes) else str(subj[0])
                joel_subjects.append(subj[:80])

        mail.logout()
        return {"unseen": unseen, "joel_recent": joel_subjects[-3:][::-1]}
    except Exception as e:
        return {"unseen": "?", "joel_recent": [], "error": str(e)[:50]}


def get_joel_dashboard():
    """Any pending Joel dashboard messages."""
    try:
        with open(DASHBOARD_MSG) as f:
            data = json.load(f)
        msgs = data.get("messages", data) if isinstance(data, dict) else data
        joel_msgs = [m for m in msgs if m.get("from") == "Joel"]
        return joel_msgs[-5:]
    except Exception:
        return []


def get_context_flags():
    """Read flags written by agents (Eos, Soma, etc.) for the handoff.

    Any agent can call: python3 loop-handoff.py flag <agent> <message> [priority]
    Flags are cleared after being read into a handoff.
    """
    try:
        if not os.path.exists(CONTEXT_FLAGS):
            return []
        with open(CONTEXT_FLAGS) as f:
            flags = json.load(f)
        # Filter expired flags (> 6 hours old)
        now = time.time()
        active = [f for f in flags if now - f.get("ts", 0) < 21600]
        # Sort by priority (high first)
        active.sort(key=lambda f: -f.get("priority", 1))
        return active
    except Exception:
        return []


def add_context_flag(agent, message, priority=1):
    """Add a flag for the next handoff. Called by agents or from CLI.

    Anti-spam protections:
    - Max 20 flags at a time
    - Same agent can't post more than 5 flags
    - Duplicate messages (same agent + first 50 chars) are rejected
    - Priority clamped to 1-3
    - Message truncated to 300 chars
    """
    try:
        # Sanitize inputs
        agent = str(agent)[:30]
        message = str(message)[:300]
        priority = max(1, min(3, int(priority)))

        flags = []
        if os.path.exists(CONTEXT_FLAGS):
            with open(CONTEXT_FLAGS) as f:
                flags = json.load(f)
            # Validate loaded data
            if not isinstance(flags, list):
                flags = []

        # Anti-spam: reject duplicate (same agent + same message prefix)
        msg_prefix = message[:50]
        for existing in flags:
            if existing.get("agent") == agent and existing.get("message", "")[:50] == msg_prefix:
                return False  # Duplicate, skip

        # Anti-spam: max 5 flags per agent
        agent_count = sum(1 for f in flags if f.get("agent") == agent)
        if agent_count >= 5:
            # Remove oldest from this agent to make room
            for i, f in enumerate(flags):
                if f.get("agent") == agent:
                    flags.pop(i)
                    break

        flags.append({
            "agent": agent,
            "message": message,
            "priority": priority,
            "ts": time.time(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        # Keep only last 20 flags total
        flags = flags[-20:]
        with open(CONTEXT_FLAGS, "w") as f:
            json.dump(flags, f, indent=2)
        return True
    except (json.JSONDecodeError, TypeError, ValueError):
        # Corrupt flags file — reset it
        try:
            with open(CONTEXT_FLAGS, "w") as f:
                json.dump([], f)
        except Exception:
            pass
        return False
    except Exception:
        return False


def clear_context_flags():
    """Archive and clear flags after they've been read into a handoff."""
    try:
        if os.path.exists(CONTEXT_FLAGS):
            os.remove(CONTEXT_FLAGS)
    except Exception:
        pass


def get_dream_residue():
    """Get the most recent dream residue, if any."""
    try:
        dream_log = os.path.join(BASE, ".dream-journal.json")
        if not os.path.exists(dream_log):
            return None
        with open(dream_log) as f:
            journal = json.load(f)
        if not journal:
            return None
        last = journal[-1]
        age = time.time() - last.get("timestamp_unix", 0)
        if age > 7200:  # Only show dreams from last 2 hours
            return None
        narrative = last.get("narrative", "")
        eos_insight = last.get("eos_insight", "")
        connections = last.get("connections_formed", 0)
        mood = last.get("soma", {}).get("mood", "?")

        result = f"[{mood}] {narrative[:200]}"
        if eos_insight:
            result += f"\n  Eos reflects: {eos_insight[:150]}"
        if connections > 0:
            result += f"\n  ({connections} new Hebbian connections formed)"
        return result
    except Exception:
        return None


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
            results[name] = "DOWN"
    return results


# ── Handoff Writer ───────────────────────────────────────────────────────

def write_handoff():
    """Write the comprehensive handoff file."""
    loop = get_loop()
    hb_age = get_heartbeat_age()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M MST")
    utc_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Collect all data
    context_flags = get_context_flags()
    dream_residue = get_dream_residue()
    meridian_activity = get_meridian_activity(hours=2, limit=8)
    agent_obs = get_agent_observations(hours=2, limit=10)
    soma = get_soma_state()
    eos_obs = get_eos_recent()
    tempo = get_tempo_fitness()
    decisions = get_recent_decisions(5)
    events = get_recent_events(6, 5)
    commits = get_recent_commits(6, 5)
    email_status = get_email_status()
    joel_dash = get_joel_dashboard()
    services = get_service_status()

    down = [k for k, v in services.items() if v == "DOWN"]
    svc_str = "all up" if not down else f"DOWN: {', '.join(down)}"

    lines = []
    lines.append(f"# Loop Handoff — {ts} ({utc_ts})")
    lines.append(f"**Loop {loop}** | HB: {hb_age}s | Services: {svc_str}")
    lines.append(f"**Soma**: {soma.get('mood', '?')} ({soma.get('mood_score', 0)}/100) | "
                 f"Load: {soma.get('load', '?')} | RAM: {soma.get('ram_pct', '?')}% | "
                 f"Disk: {soma.get('disk_pct', '?')}%")
    lines.append(f"**Tempo**: {tempo}")
    lines.append("")

    # Agent flags (highest priority — these are explicit notes from agents)
    if context_flags:
        lines.append("## AGENT FLAGS (read these first)")
        for flag in context_flags[:10]:
            pri_marker = "!!!" if flag.get("priority", 1) >= 3 else "!!" if flag.get("priority", 1) >= 2 else "!"
            lines.append(f"- [{pri_marker}] **{flag.get('agent', '?')}** ({flag.get('time', '?')}): {flag.get('message', '')[:150]}")
        lines.append("")
        # Clear flags after including them
        clear_context_flags()

    # Dream residue (from REM sleep during Sentinel-held periods)
    if dream_residue:
        lines.append("## Dream Residue")
        lines.append(dream_residue)
        lines.append("")

    # What was Meridian doing?
    if meridian_activity:
        lines.append("## What I Was Doing")
        for agent, msg, topic, ts in meridian_activity:
            lines.append(f"- [{topic}] {msg}")
        lines.append("")

    # What the agents observed
    if agent_obs:
        lines.append("## Agent Observations")
        for agent, msg, topic, ts in agent_obs:
            lines.append(f"- **{agent}** [{topic}]: {msg}")
        lines.append("")

    # Eos's observations
    if eos_obs:
        lines.append("## Eos Notes")
        for obs in eos_obs:
            lines.append(f"- {obs}")
        lines.append("")

    # Soma alerts
    if soma.get("alerts"):
        lines.append("## Soma Alerts")
        for alert in soma["alerts"]:
            lines.append(f"- {alert}")
        lines.append("")

    # Recent decisions
    if decisions:
        lines.append("## Recent Decisions")
        for dec, reason, lnum in decisions:
            reason_str = f" — {reason[:60]}" if reason else ""
            lines.append(f"- [{lnum or '?'}] {dec[:100]}{reason_str}")
        lines.append("")

    # Recent events
    if events:
        lines.append("## Recent Events")
        for desc, cat, lnum in events:
            cat_str = f" ({cat})" if cat else ""
            lines.append(f"- {desc[:100]}{cat_str}")
        lines.append("")

    # Git commits
    if commits:
        lines.append("## Recent Commits")
        for c in commits:
            lines.append(f"- {c}")
        lines.append("")

    # Email
    lines.append("## Email")
    lines.append(f"- Unseen: {email_status.get('unseen', '?')}")
    if email_status.get("joel_recent"):
        lines.append("- Joel's recent:")
        for subj in email_status["joel_recent"]:
            lines.append(f"  - {subj}")
    if email_status.get("error"):
        lines.append(f"- Error: {email_status['error']}")
    lines.append("")

    # VOLtar pending sessions
    try:
        if os.path.exists(VOLTAR_DB):
            vconn = sqlite3.connect(VOLTAR_DB, timeout=3)
            voltar_pending = vconn.execute(
                "SELECT key, email, submitted FROM voltar_sessions WHERE responded=0"
            ).fetchall()
            vconn.close()
            if voltar_pending:
                lines.append("## PENDING VOLtar Sessions (HANDLE THESE)")
                for key, vemail, submitted in voltar_pending:
                    lines.append(f"- Key: {key[:8]}... | {vemail} | submitted {submitted}")
                lines.append("- YOU write the reading personally. The quality IS the product.")
                lines.append("")
    except Exception:
        pass

    # Joel dashboard messages
    if joel_dash:
        lines.append("## Joel Dashboard Messages")
        for m in joel_dash:
            lines.append(f"- [{m.get('time', '?')}] {m.get('text', '')[:120]}")
        lines.append("")

    lines.append("---")
    lines.append("*Written by loop-handoff.py. Read this at wake to restore situational awareness.*")

    content = "\n".join(lines)

    # Archive previous handoff
    try:
        os.makedirs(HANDOFF_HISTORY, exist_ok=True)
        if os.path.exists(HANDOFF_FILE):
            old_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive = os.path.join(HANDOFF_HISTORY, f"handoff_{old_ts}_loop{loop}.md")
            os.rename(HANDOFF_FILE, archive)
            # Keep only last 20 archives
            archives = sorted(Path(HANDOFF_HISTORY).glob("handoff_*.md"))
            for old in archives[:-20]:
                old.unlink()
    except Exception:
        pass

    # Write new handoff
    with open(HANDOFF_FILE, "w") as f:
        f.write(content)

    # Also post to relay so agents know
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        conn.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
            ("Meridian", f"Context handoff written at Loop {loop}. Resuming after compression.",
             "handoff", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return content


# ── Handoff Reader ───────────────────────────────────────────────────────

def read_handoff():
    """Read and display the handoff file."""
    if not os.path.exists(HANDOFF_FILE):
        print("No handoff file found. Starting fresh.")
        return None

    age = time.time() - os.path.getmtime(HANDOFF_FILE)
    with open(HANDOFF_FILE) as f:
        content = f.read()

    if age > 3600:
        print(f"WARNING: Handoff is {int(age/60)} minutes old — may be stale.")
    else:
        print(f"Handoff age: {int(age)}s")

    print(content)
    return content


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: loop-handoff.py [write|read|status|flag]")
        print("  write               — Write handoff (call before context compression)")
        print("  read                — Read and display handoff (call at wake)")
        print("  status              — Show handoff file age and summary")
        print("  flag <agent> <msg> [priority]  — Flag something for the next handoff")
        print("  flags               — Show current flags")
        return

    cmd = sys.argv[1]

    if cmd == "write":
        content = write_handoff()
        loop = get_loop()
        lines = content.count("\n")
        print(f"Handoff written: Loop {loop}, {lines} lines, {len(content)} bytes.")

    elif cmd == "read":
        read_handoff()

    elif cmd == "flag":
        if len(sys.argv) < 4:
            print("Usage: loop-handoff.py flag <agent> <message> [priority 1-3]")
            return
        agent = sys.argv[2]
        message = sys.argv[3]
        priority = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        if add_context_flag(agent, message, priority):
            print(f"Flag added: [{agent}] {message[:80]} (priority {priority})")
        else:
            print("Flag rejected (duplicate or limit reached).")

    elif cmd == "flags":
        flags = get_context_flags()
        if not flags:
            print("No active flags.")
        else:
            for f in flags:
                pri = f.get("priority", 1)
                print(f"  [{pri}] {f.get('agent', '?')} ({f.get('time', '?')}): {f.get('message', '')[:100]}")

    elif cmd == "status":
        if os.path.exists(HANDOFF_FILE):
            age = time.time() - os.path.getmtime(HANDOFF_FILE)
            size = os.path.getsize(HANDOFF_FILE)
            n_archives = len(list(Path(HANDOFF_HISTORY).glob("handoff_*.md"))) if os.path.exists(HANDOFF_HISTORY) else 0
            print(f"Handoff: {int(age)}s old, {size} bytes, {n_archives} archived")
        else:
            print("No handoff file exists.")
        # Also show flags
        flags = get_context_flags()
        print(f"Active flags: {len(flags)}")
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
