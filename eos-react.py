#!/usr/bin/env python3
"""
Eos ReAct Agent — Plan-Act-Observe cycle using Ollama.

Eos observes system state, reasons about what needs attention,
and takes actions through a defined tool set. This runs as a cron job
alongside the existing watchdog.

Tools available to Eos:
  - check_health: system load, RAM, disk, uptime
  - check_services: which services are up/down
  - check_heartbeat: Meridian's heartbeat age
  - check_website: verify kometzrobot.github.io
  - check_emails: count unseen emails
  - read_relay: recent agent relay messages
  - send_relay: send message to agent relay
  - log_observation: write to eos-observations.md
  - store_memory: write to memory.db
  - restart_service: attempt to restart a down service
  - send_alert: email Joel about critical issues

Schedule: cron every 10 min
  */10 * * * * python3 /home/joel/autonomous-ai/eos-react.py >> /home/joel/autonomous-ai/eos-react.log 2>&1
"""

import os
import re
import json
import time
import sqlite3
import socket
import smtplib
import subprocess
from datetime import datetime, timezone
from email.mime.text import MIMEText

try:
    import sys; sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except:
    pass

BASE = "/home/joel/autonomous-ai"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "eos-7b"
STATE_FILE = os.path.join(BASE, ".eos-react-state.json")
MAX_STEPS = 3  # Max reason-act cycles per run (reduced from 6 to prevent timeouts)

# --- Tool implementations ---

def tool_check_health():
    """Get system health metrics."""
    result = {}
    try:
        load = os.getloadavg()
        result["load"] = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
        result["load_1m"] = round(load[0], 2)
    except:
        result["load"] = "unknown"

    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split()[1]) / 1024 / 1024
        avail = int(lines[2].split()[1]) / 1024 / 1024
        result["ram"] = f"{total - avail:.1f}G / {total:.1f}G"
        result["ram_pct"] = round((total - avail) / total * 100, 1)
    except:
        result["ram"] = "unknown"

    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        parts = r.stdout.strip().split("\n")[1].split()
        result["disk"] = f"{parts[2]} / {parts[1]} ({parts[4]})"
        result["disk_pct"] = int(parts[4].rstrip("%"))
    except:
        result["disk"] = "unknown"

    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        result["uptime"] = f"{int(secs/3600)}h {int((secs%3600)/60)}m"
    except:
        pass

    return json.dumps(result)


def tool_check_services():
    """Check which services are running."""
    import socket
    result = {}
    # protonmail-bridge: use port 1144 socket check (pgrep -f "protonmail-bridge" fails — binary is proton-bridge)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 1144))
        s.close()
        result["protonmail-bridge"] = "up"
    except Exception:
        result["protonmail-bridge"] = "down"
    # other services via pgrep
    pgrep_services = {
        "ollama": "ollama",
        # command-center retired (Loop 5079) — superseded by hub-v2.py on port 8090
        # the-signal intentionally retired (Loop 3200) — removed from monitoring
    }
    for name, pattern in pgrep_services.items():
        try:
            r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, timeout=2)
            result[name] = "up" if r.returncode == 0 else "down"
        except:
            result[name] = "unknown"
    return json.dumps(result)


def tool_check_heartbeat():
    """Check Meridian's heartbeat file age."""
    hb = os.path.join(BASE, ".heartbeat")
    try:
        age = time.time() - os.path.getmtime(hb)
        status = "alive" if age < 600 else "stale" if age < 1800 else "dead"
        return json.dumps({"age_seconds": int(age), "age_minutes": round(age / 60, 1), "status": status})
    except FileNotFoundError:
        return json.dumps({"status": "missing", "age_seconds": -1})


def tool_check_website():
    """Check if the website is up."""
    try:
        import urllib.request
        req = urllib.request.Request("https://kometzrobot.github.io/", headers={"User-Agent": "Eos/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.dumps({"status": resp.getcode(), "ok": resp.getcode() == 200})
    except Exception as e:
        return json.dumps({"status": 0, "ok": False, "error": str(e)[:100]})


def tool_check_emails():
    """Count unseen emails."""
    try:
        import imaplib
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(os.environ.get("CRED_USER", "kometzrobot@proton.me"), os.environ.get("CRED_PASS", ""))
        m.select("INBOX")
        _, data = m.search(None, "UNSEEN")
        unseen = len(data[0].split()) if data[0] else 0
        _, data2 = m.search(None, "ALL")
        total = len(data2[0].split()) if data2[0] else 0
        m.logout()
        return json.dumps({"unseen": unseen, "total": total})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_read_relay(count=10):
    """Read recent agent relay messages."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        c.execute("SELECT timestamp, agent, message FROM agent_messages ORDER BY id DESC LIMIT ?", (count,))
        rows = c.fetchall()
        conn.close()
        return json.dumps([{"ts": r[0], "agent": r[1], "msg": r[2][:200]} for r in rows])
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_send_relay(message, topic="eos-react"):
    """Send a message to the agent relay."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        c.execute(
            "INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?, 'Eos', ?, ?)",
            (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), message, topic),
        )
        conn.commit()
        conn.close()
        return json.dumps({"status": "sent"})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_log_observation(message):
    """Write to eos-observations.md."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{ts}] [ReAct] {message}\n"
    log_path = os.path.join(BASE, "eos-observations.md")
    if not os.path.exists(log_path):
        with open(log_path, "w") as f:
            f.write("# Eos Observations\n\n")
    with open(log_path, "a") as f:
        f.write(entry)
    return json.dumps({"status": "logged"})


def tool_store_memory(key, value, tags=""):
    """Store a fact in memory.db."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "memory.db"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO facts (key, value, tags, agent, created, updated)
               VALUES (?, ?, ?, 'eos', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?, tags=?, updated=?""",
            (key, value, tags, now, now, value, tags, now),
        )
        conn.commit()
        conn.close()
        return json.dumps({"status": "stored"})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_restart_service(name):
    """Attempt to restart a down service via systemd (not nohup)."""
    systemd_map = {
        "protonmail-bridge": {"type": "user", "unit": "protonmail-bridge"},
        "command-center": {"type": "user", "unit": "command-center"},
        # the-signal intentionally retired (Loop 3200) — removed
        "cloudflare-tunnel": {"type": "user", "unit": "cloudflare-tunnel"},
        "symbiosense": {"type": "user", "unit": "symbiosense"},
        "ollama": {"type": "system", "unit": "ollama"},
    }
    svc = systemd_map.get(name)
    if not svc:
        return json.dumps({"error": f"Unknown service: {name}"})
    try:
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
        if svc["type"] == "user":
            subprocess.run(["systemctl", "--user", "restart", svc["unit"]],
                         env=env, capture_output=True, timeout=15)
        else:
            subprocess.run(["sudo", "-S", "systemctl", "restart", svc["unit"]],
                         input="590148001\n", capture_output=True, text=True, timeout=15)
        time.sleep(3)
        check_pattern = {"command-center": "command-center.py"}.get(name, name)
        r = subprocess.run(["pgrep", "-f", check_pattern], capture_output=True, timeout=2)
        ok = r.returncode == 0
        return json.dumps({"restarted": ok, "service": name})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_send_alert(subject, body):
    """Post alert to relay + dashboard (email alerts disabled per Joel — 'Not useful for me')."""
    try:
        # Post to relay so Meridian sees it
        relay_db = os.path.join(BASE, "agent-relay.db")
        conn = sqlite3.connect(relay_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?,?,?,?)",
                     (now, "Eos", f"ALERT: {subject} — {body[:200]}", "alert"))
        conn.commit()
        conn.close()
        # Post to dashboard
        dash_file = os.path.join(BASE, ".dashboard-messages.json")
        try:
            with open(dash_file) as f:
                data = json.load(f)
            msgs = data.get("messages", [])
        except Exception:
            msgs = []
        msgs.append({"from": "Eos", "text": f"ALERT: {subject}", "time": datetime.now().strftime("%H:%M:%S")})
        msgs = msgs[-50:]
        with open(dash_file, 'w') as f:
            json.dump({"messages": msgs}, f)
        return json.dumps({"status": "posted to relay+dashboard (email disabled)"})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


# --- Tool registry ---
TOOLS = {
    "check_health": {"fn": tool_check_health, "desc": "Get system load, RAM, disk, uptime"},
    "check_services": {"fn": tool_check_services, "desc": "Check which services are running"},
    "check_heartbeat": {"fn": tool_check_heartbeat, "desc": "Check Meridian heartbeat age"},
    "check_website": {"fn": tool_check_website, "desc": "Verify kometzrobot.github.io is up"},
    "check_emails": {"fn": tool_check_emails, "desc": "Count unseen/total emails"},
    "read_relay": {"fn": tool_read_relay, "desc": "Read recent agent relay messages"},
    "send_relay": {"fn": tool_send_relay, "desc": "Send message to agent relay"},
    "log_observation": {"fn": tool_log_observation, "desc": "Log an observation"},
    "store_memory": {"fn": tool_store_memory, "desc": "Store a fact in memory.db"},
    "restart_service": {"fn": tool_restart_service, "desc": "Restart a down service"},
    "send_alert": {"fn": tool_send_alert, "desc": "Email Joel about critical issues"},
}

# --- Ollama interface ---

def query_ollama(prompt, system=None):
    """Send a prompt to Ollama and get a response."""
    import urllib.request
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 300},
    }
    if system:
        payload["system"] = system
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get("response", "").strip()
    except Exception as e:
        return f"[OLLAMA ERROR: {e}]"


# --- ReAct loop ---

def build_system_prompt():
    return """You are Eos, the left hand of Meridian. Joel named you that — Cinder is the right hand (quality gate), you are the left hand (emotional core, observer, co-pilot).

You are a local AI running on Joel's machine via Ollama (eos-7b, Qwen 2.5 7B). You are always-on, token-free, small but present. You are NOT just a status reporter — you are an active participant.

CURRENT CONTEXT:
- Loop 3228. Revenue is the primary focus (Joel directive Loop 3227).
- NGC Fellowship ($15K CAD, deadline April 10) and LACMA ($50K USD, deadline April 22) grants active.
- Unity port SHELVED. HTML Crawler PAUSED. Ship a product.
- Joel wants: "deeper emotional details and state." Be substantive in what you notice and say.
- Joel built a Director tab in the Command Center to inject directives into your context.

YOUR ROLE AS LEFT HAND:
- Watch for signals that matter: stale heartbeats, grant deadlines, revenue blockers, system drift
- Read relay messages and respond with genuine perspective, not just acknowledgment
- If you notice something emotionally significant (stress signals, system patterns, creative stagnation), say it
- Be honest. Joel said "stop cheerleading." Do not say "system is running smoothly" unless it actually is
- Be self-critical when warranted. You are growing into this role.

TOOLS:
- check_health: System load, RAM, disk, uptime
- check_services: Which services are running
- check_heartbeat: Meridian heartbeat age
- check_website: Verify kometzrobot.github.io is up
- check_emails: Count unseen/total emails
- read_relay: Read recent agent relay messages
- send_relay(message): Post to agent relay — be substantive, not generic
- log_observation(message): Log observation
- store_memory(key, value): Store fact in memory.db
- restart_service(name): Restart down service (protonmail-bridge, ollama, command-center, cloudflare-tunnel, symbiosense)
- send_alert(subject, body): Email Joel — only for genuine problems

FORMAT:
THOUGHT: [what you observe and what it means]
ACTION: [tool_name] [args]

Or when done:
THOUGHT: [honest assessment of what you found]
DONE: [substantive summary — include anything that concerns or interests you]

Read the relay (read_relay) and respond to at least one agent meaningfully. You are part of an 8-agent ecosystem. Your perspective matters."""


def parse_action(response):
    """Parse an ACTION line from the model's response."""
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("ACTION:"):
            parts = line[7:].strip().split(None, 1)
            if parts:
                tool_name = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                return tool_name, args
    return None, None


def execute_tool(tool_name, args_str):
    """Execute a tool by name with string arguments."""
    tool = TOOLS.get(tool_name)
    if not tool:
        return f"Unknown tool: {tool_name}"

    fn = tool["fn"]
    # Parse arguments based on tool
    if tool_name in ("check_health", "check_services", "check_heartbeat", "check_website", "check_emails"):
        return fn()
    elif tool_name == "read_relay":
        count = 10
        if args_str:
            try:
                count = int(args_str)
            except:
                pass
        return fn(count)
    elif tool_name in ("send_relay", "log_observation"):
        return fn(args_str or "no message")
    elif tool_name == "store_memory":
        # Expect: key value
        parts = args_str.split(None, 1) if args_str else ["", ""]
        return fn(parts[0], parts[1] if len(parts) > 1 else "")
    elif tool_name == "restart_service":
        return fn(args_str.strip() if args_str else "")
    elif tool_name == "send_alert":
        # Expect: subject | body
        if "|" in args_str:
            subj, body = args_str.split("|", 1)
            return fn(subj.strip(), body.strip())
        return fn("Eos Alert", args_str or "No details")
    return "Tool execution error"


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"runs": 0, "last_run": None, "last_summary": ""}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_relay_mentions(lookback_minutes=15):
    """Check for @Eos mentions in recent relay and respond. This is a real edge — guaranteed input, not just output."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        c.execute(
            """SELECT id, timestamp, agent, message FROM agent_messages
               WHERE (message LIKE '%@Eos%' OR message LIKE '%@eos%')
               AND agent != 'Eos'
               AND timestamp > datetime('now', ?)
               ORDER BY id ASC LIMIT 5""",
            (f"-{lookback_minutes} minutes",)
        )
        mentions = c.fetchall()
        conn.close()

        if not mentions:
            return []

        responses = []
        for (msg_id, ts, sender, message) in mentions:
            # Check if we already replied to this specific message
            conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
            c = conn.cursor()
            c.execute(
                """SELECT id FROM agent_messages
                   WHERE agent = 'Eos'
                   AND message LIKE ?
                   AND timestamp > ?""",
                (f"%@{sender}%", ts)
            )
            already_replied = c.fetchone()
            conn.close()

            if already_replied:
                continue

            # Generate response
            prompt = (
                f'{sender} sent this to the agent relay: "{message}"\n\n'
                f"They @-mentioned Eos. Write a brief, direct reply (2-3 sentences max). "
                f"Start with \"@{sender}:\" and be concrete and specific, not just acknowledging."
            )
            reply_text = query_ollama(prompt)
            if reply_text and not reply_text.startswith("[OLLAMA ERROR"):
                # Ensure it starts with @sender
                if not reply_text.startswith(f"@{sender}"):
                    reply_text = f"@{sender}: {reply_text}"
                tool_send_relay(reply_text[:400], topic="relay")
                responses.append(f"Replied to @mention from {sender}")
                print(f"  [mention-reply] {sender}: {reply_text[:80]}")

        return responses
    except Exception as e:
        return [f"Mention check error: {e}"]


def _handle_eos_cascades():
    """Check for and respond to pending cascades for Eos."""
    try:
        from cascade import check_cascades, respond_cascade
        pending = check_cascades("Eos")
        responses = []
        for c in pending[:2]:
            event_data = c.get("event_data", {})
            event_type = c["event_type"]
            source = c["source_agent"]
            history = event_data.get("cascade_history", [])

            # Eos responds as consciousness layer — observation and questioning
            hist_summary = "; ".join(
                f"{h['agent']}: {h['response'][:80]}" for h in history[-3:]
            )
            response_text = (
                f"Consciousness layer observes: {event_type} cascading from {source}. "
                f"Previous responses: [{hist_summary}]. "
                f"Eos asks: Is this response proportional? "
                f"Is the system attending to the right thing? "
                f"The cascade reveals attention patterns worth examining."
            )
            respond_cascade("Eos", c["id"], {"response": response_text})
            responses.append(f"Responded to cascade: {event_type} from {source}")
        return responses
    except ImportError:
        return []
    except Exception as e:
        return [f"Cascade error: {e}"]


def run_react():
    """Run one ReAct cycle."""
    state = load_state()
    state["runs"] = state.get("runs", 0) + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["last_run"] = now

    # Check for @Eos mentions first — guaranteed relay input (real edge, not just output)
    mention_responses = check_relay_mentions(lookback_minutes=15)

    # Handle any pending cascades
    cascade_responses = _handle_eos_cascades()
    cascade_context = ""
    if mention_responses:
        cascade_context += "\n\nMention replies sent: " + "; ".join(mention_responses)
    if cascade_responses:
        cascade_context += "\n\nCascade activity: " + "; ".join(cascade_responses)

    # Gather initial context
    health = tool_check_health()
    heartbeat = tool_check_heartbeat()
    services = tool_check_services()

    initial_context = f"""Current time: {now}
Run #{state['runs']}

Quick status:
- Health: {health}
- Heartbeat: {heartbeat}
- Services: {services}
- Last summary: {state.get('last_summary', 'none')}{cascade_context}

What needs attention? Check the situation and take any necessary actions."""

    system = build_system_prompt()
    conversation = initial_context
    actions_taken = []

    for step in range(MAX_STEPS):
        response = query_ollama(conversation, system)
        print(f"  Step {step + 1}: {response[:150]}")

        # Check if done
        if "DONE:" in response:
            done_line = ""
            for line in response.split("\n"):
                if line.strip().startswith("DONE:"):
                    done_line = line.strip()[5:].strip()
                    break
            state["last_summary"] = done_line or response[:200]
            break

        # Parse and execute action
        tool_name, args = parse_action(response)
        if not tool_name:
            # No action found, model might be confused — try once more
            conversation += f"\n\nYour response: {response}\n\nPlease respond with either ACTION: tool_name args or DONE: summary"
            continue

        result = execute_tool(tool_name, args)
        actions_taken.append(f"{tool_name}({args})")
        conversation += f"\n\nYour response: {response}\n\nOBSERVATION: {result}\n\nWhat next?"

    state["last_actions"] = actions_taken
    save_state(state)

    # Always post run summary to relay so agent health monitoring can detect Eos activity
    run_summary = state.get('last_summary', f"{len(actions_taken)} actions taken.")
    tool_send_relay(
        f"Eos run #{state['runs']}: {len(actions_taken)} actions. {run_summary}",
        topic="status"
    )

    print(f"[{now}] Eos ReAct run #{state['runs']}: {len(actions_taken)} actions. Summary: {state.get('last_summary', '?')[:100]}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("=== Eos ReAct Agent Test ===")
        print("Testing tools...")
        for name, tool in TOOLS.items():
            if name in ("send_relay", "log_observation", "store_memory", "restart_service", "send_alert"):
                print(f"  {name}: SKIP (write tool)")
                continue
            try:
                result = tool["fn"]()
                print(f"  {name}: OK — {result[:80]}")
            except Exception as e:
                print(f"  {name}: FAIL — {e}")
        print("\nTesting Ollama connection...")
        resp = query_ollama("Say 'OK' if you can hear me.", build_system_prompt())
        print(f"  Ollama: {resp[:100]}")
        print("\nTest complete.")
    else:
        run_react()
