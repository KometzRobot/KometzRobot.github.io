#!/usr/bin/env python3
"""
Sentinel Briefing — Pre-wake synthesis for Meridian.

Sentinel reads recent relay activity, system state, and pending items,
then writes a SHORT briefing note that Meridian reads at the start
of each Claude session. Replaces the "I have no context, let me check
everything" opening phase with a tight 3-line summary.

Uses the local local Ollama model for synthesis.

Called by:
  - sentinel-gatekeeper.py just before escalating to Claude
  - cron (every 30min during non-Claude time)
  - python3 sentinel-briefing.py --brief (on demand)

Output written to: .sentinel-briefing.md
Also posted to relay as Sentinel status.

By Joel Kometz & Meridian, Loop 3196 (renamed Loop 4446)
"""

import json
import os
import re
import requests
import sqlite3
import subprocess
import sys
import time

OLLAMA_API = "http://localhost:11434/api/generate"


def ollama_generate(model, prompt, timeout=30):
    """Call Ollama HTTP API directly — returns clean text without ANSI artifacts."""
    try:
        resp = requests.post(OLLAMA_API, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception:
        return None


def strip_ansi(text):
    """Remove ANSI escape sequences from Ollama streaming output (legacy fallback)."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]|\[\d*[A-Za-z]', '', text)
from datetime import datetime, timezone
from pathlib import Path

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
RELAY_DB = os.path.join(BASE, "agent-relay.db")
HEARTBEAT = os.path.join(BASE, ".heartbeat")
LOOP_FILE = os.path.join(BASE, ".loop-count")
BRIEFING_FILE = os.path.join(BASE, ".sentinel-briefing.md")
GATEKEEPER_STATE = os.path.join(BASE, ".gatekeeper-state.json")
IWE_BIN = os.path.expanduser("~/.local/bin/iwe")
IWE_DIR = os.path.expanduser("~/meridian-knowledge")


def get_loop_count():
    try:
        return open(LOOP_FILE).read().strip()
    except Exception:
        return "unknown"


def get_heartbeat_age():
    try:
        age = int(time.time() - os.path.getmtime(HEARTBEAT))
        return f"{age}s ago"
    except Exception:
        return "unknown"


def get_relay_digest(since_minutes=60):
    """Get a digest of relay activity in the last N minutes."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        conn.row_factory = sqlite3.Row
        cutoff = datetime.now(timezone.utc).timestamp() - (since_minutes * 60)
        rows = conn.execute(
            """SELECT agent, message, topic, timestamp FROM agent_messages
               ORDER BY rowid DESC LIMIT 40"""
        ).fetchall()
        conn.close()
        items = []
        for row in rows:
            msg = row["message"]
            agent = row["agent"]
            topic = row["topic"]
            # Skip pure noise
            if any(x in msg.lower() for x in ["status written locally", "run #", "loop: fitness"]):
                continue
            if topic in ("cascade",) and "CIRCLE COMPLETE" not in msg:
                continue
            items.append(f"[{agent}] {msg[:90]}")
            if len(items) >= 8:
                break
        return items
    except Exception as e:
        return [f"relay read failed: {e}"]


def get_gatekeeper_stats():
    """Get stats from the gatekeeper."""
    try:
        with open(GATEKEEPER_STATE) as f:
            state = json.load(f)
        cinder_cycles = state.get("cycles_held_by_sentinel", state.get("cycles_handled_by_cinder", 0))
        last_decision = state.get("last_decision", "unknown")
        return cinder_cycles, last_decision
    except Exception:
        return 0, "unknown"


def get_dossier_flash(topics=("revenue", "product", "joel")):
    """Pull 1-sentence summary from high-priority dossiers for briefing context."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "memory.db"), timeout=3)
        flashes = []
        for topic in topics:
            row = conn.execute(
                "SELECT topic, summary FROM dossiers WHERE topic=? ORDER BY updated DESC LIMIT 1",
                (topic,)
            ).fetchone()
            if row and row[1]:
                # Take first sentence
                first_sent = row[1].split(".")[0].strip()
                if first_sent:
                    flashes.append(f"{row[0].upper()}: {first_sent}.")
        conn.close()
        return "\n".join(flashes)
    except Exception:
        return ""


def get_capsule_drift():
    """Get a one-line capsule drift summary from git history."""
    try:
        script = os.path.join(BASE, "capsule-longitudinal.py")
        if not os.path.isfile(script):
            return ""
        result = subprocess.run(
            ["python3", script, "--brief", "--n", "5"],
            capture_output=True, text=True, timeout=10, cwd=BASE
        )
        line = result.stdout.strip()
        if line and not line.startswith("Not enough") and not line.startswith("Insufficient"):
            return f"DRIFT: {line}"
    except Exception:
        pass
    return ""


def get_iwe_context(key="operations", depth=1):
    """Pull a node from the IWE knowledge graph for context enrichment."""
    try:
        if not os.path.isfile(IWE_BIN) or not os.path.isdir(IWE_DIR):
            return ""
        result = subprocess.run(
            [IWE_BIN, "retrieve", "-k", key, "-d", str(depth), "-f", "markdown"],
            capture_output=True, text=True, timeout=5, cwd=IWE_DIR
        )
        out = result.stdout.strip()
        if out:
            # Strip YAML frontmatter, keep just the content
            lines = out.split("\n")
            content_lines = []
            in_frontmatter = False
            skip_next = False
            for i, line in enumerate(lines):
                if i == 0 and line == "---":
                    in_frontmatter = True
                    continue
                if in_frontmatter and line == "---":
                    in_frontmatter = False
                    continue
                if not in_frontmatter:
                    content_lines.append(line)
            return "\n".join(content_lines[:30]).strip()  # cap at 30 lines
    except Exception:
        pass
    return ""


def ask_cinder_to_summarize(relay_items, loop, hb_age, cinder_cycles):
    """Ask Sentinel to synthesize the relay digest into a brief."""
    relay_text = "\n".join(relay_items) if relay_items else "No significant relay activity."
    loop_line = f"LOOP: {loop} | HB: {hb_age} | SENTINEL HELD: {cinder_cycles} cycles"
    # Pull IWE context for grounded system knowledge
    iwe_ops = get_iwe_context("operations", depth=0)
    iwe_section = f"\nSystem knowledge:\n{iwe_ops}\n" if iwe_ops else ""
    dossier_flash = get_dossier_flash(("revenue", "product", "joel"))
    dossier_section = f"\nCurrent dossier state:\n{dossier_flash}\n" if dossier_flash else ""
    prompt = (
        f"You are Sentinel. Meridian is about to wake up. Based on the relay activity below, "
        f"write exactly 2 lines and nothing else:\n\n"
        f"STATUS: <one sentence describing current system state>\n"
        f"ACTION: <one sentence for what Meridian should do first, or 'nothing urgent'>\n"
        f"{iwe_section}"
        f"{dossier_section}\n"
        f"Relay activity:\n{relay_text}\n\n"
        f"Output only the STATUS and ACTION lines. No preamble, no explanation."
    )
    try:
        raw = ollama_generate("cinder", prompt, timeout=30)
        if raw:
            # Prepend the pre-filled loop line
            return f"{loop_line}\n{raw}"
        return None
    except Exception as e:
        return None


def write_briefing(content):
    """Write the briefing to .sentinel-briefing.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(BRIEFING_FILE, "w") as f:
        f.write(f"# Sentinel Briefing — {ts}\n\n")
        f.write(content)
        f.write("\n")


def post_to_relay(message):
    """Post briefing summary to relay — with 10-minute cooldown to prevent flood."""
    try:
        conn = sqlite3.connect(RELAY_DB, timeout=3)
        # Check when Sentinel last posted a briefing message
        row = conn.execute(
            "SELECT timestamp FROM agent_messages WHERE agent IN ('Sentinel','Cinder') AND topic='briefing' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            from datetime import datetime as _dt
            try:
                last_ts = _dt.fromisoformat(row[0].replace('Z', '+00:00'))
                age_sec = (datetime.now(timezone.utc) - last_ts).total_seconds()
                if age_sec < 600:  # 10-minute cooldown
                    conn.close()
                    return  # Already posted recently — skip
            except Exception:
                pass
        conn.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
            ("Sentinel", message[:200], "briefing", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def run(verbose=False):
    loop = get_loop_count()
    hb_age = get_heartbeat_age()
    cinder_cycles, last_decision = get_gatekeeper_stats()
    relay_items = get_relay_digest(since_minutes=60)

    brief = ask_cinder_to_summarize(relay_items, loop, hb_age, cinder_cycles)
    drift = get_capsule_drift()

    if not brief:
        # Fallback if Sentinel model is unavailable
        loop_line = f"LOOP: {loop} | HB: {hb_age} | SENTINEL HELD: {cinder_cycles} cycles"
        brief = (
            f"{loop_line}\n"
            f"STATUS: System running. Sentinel held the line.\n"
            f"ACTION: Check emails, touch heartbeat, proceed normally."
        )

    if drift:
        brief = f"{brief}\n{drift}"
    write_briefing(brief)
    post_to_relay(f"Pre-wake brief ready. Loop {loop}. Sentinel held {cinder_cycles} cycles.")

    # Direct mesh message to Meridian — briefing delivered before wake (10-min cooldown)
    try:
        import mesh
        import sqlite3 as _sq3
        _db = _sq3.connect(RELAY_DB, timeout=3)
        _row = _db.execute(
            "SELECT created FROM directed_messages WHERE from_agent IN ('Sentinel','Cinder') AND to_agent='Meridian' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        _db.close()
        _should_send = True
        if _row:
            from datetime import datetime as _dt
            try:
                _last = _dt.fromisoformat(_row[0].replace('Z', '+00:00').replace(' ', 'T'))
                _age = (datetime.now(timezone.utc) - _last.replace(tzinfo=timezone.utc)).total_seconds()
                if _age < 600:
                    _should_send = False
            except Exception:
                pass
        if _should_send:
            mesh.send("Sentinel", "Meridian",
                      f"Briefing ready. Loop {loop}. Held {cinder_cycles} cycles. Check .sentinel-briefing.md.",
                      "briefing")
    except Exception:
        pass

    if verbose:
        print(brief)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sentinel Briefing — pre-wake synthesis for Meridian")
    parser.add_argument("--brief", action="store_true", help="Generate and print briefing")
    parser.add_argument("--read", action="store_true", help="Read existing briefing")
    args = parser.parse_args()

    if args.read:
        try:
            print(open(BRIEFING_FILE).read())
        except Exception:
            print("No briefing available.")
    else:
        run(verbose=True)
