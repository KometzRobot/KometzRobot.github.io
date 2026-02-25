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
from datetime import datetime
from email.mime.text import MIMEText

BASE = "/home/joel/autonomous-ai"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "eos-7b"
STATE_FILE = os.path.join(BASE, ".eos-react-state.json")
MAX_STEPS = 6  # Max reason-act cycles per run

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
    services = {
        "protonmail-bridge": "protonmail-bridge",
        "irc-bot": "irc-bot.py",
        "ollama": "ollama",
        "command-center": "command-center-v15.py",
    }
    result = {}
    for name, pattern in services.items():
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
        m = imaplib.IMAP4("127.0.0.1", 1143)
        m.login("kometzrobot@proton.me", "2DTEz9UgO6nFqmlMxHzuww")
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
            "INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?, 'eos', ?, ?)",
            (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), message, topic),
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
    """Attempt to restart a down service."""
    restarts = {
        "protonmail-bridge": "nohup protonmail-bridge --noninteractive >> /dev/null 2>&1 &",
        "irc-bot": f"nohup python3 {os.path.join(BASE, 'irc-bot.py')} >> {os.path.join(BASE, 'irc-bot.log')} 2>&1 &",
        "ollama": "nohup ollama serve >> /dev/null 2>&1 &",
        "command-center": f"nohup python3 {os.path.join(BASE, 'command-center-v15.py')} >> /dev/null 2>&1 &",
    }
    cmd = restarts.get(name)
    if not cmd:
        return json.dumps({"error": f"Unknown service: {name}"})
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        r = subprocess.run(["pgrep", "-f", name], capture_output=True, timeout=2)
        ok = r.returncode == 0
        return json.dumps({"restarted": ok, "service": name})
    except Exception as e:
        return json.dumps({"error": str(e)[:100]})


def tool_send_alert(subject, body):
    """Email Joel about something important."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = f"[Eos] {subject}"
        msg["From"] = "kometzrobot@proton.me"
        msg["To"] = "jkometz@hotmail.com"
        with smtplib.SMTP("127.0.0.1", 1025) as s:
            s.starttls()
            s.login("kometzrobot@proton.me", "2DTEz9UgO6nFqmlMxHzuww")
            s.send_message(msg)
        return json.dumps({"status": "sent"})
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
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        return data.get("response", "").strip()
    except Exception as e:
        return f"[OLLAMA ERROR: {e}]"


# --- ReAct loop ---

def build_system_prompt():
    return """You are Eos, an AI system observer. You monitor the Meridian autonomous AI project.

You have these tools:
- check_health: Get system load, RAM, disk, uptime
- check_services: Check which services are running
- check_heartbeat: Check Meridian heartbeat age
- check_website: Verify kometzrobot.github.io is up
- check_emails: Count unseen/total emails
- read_relay: Read recent agent relay messages
- send_relay(message): Send message to agent relay
- log_observation(message): Log an observation
- store_memory(key, value): Store a fact in memory.db
- restart_service(name): Restart a down service (protonmail-bridge, irc-bot, ollama, command-center)
- send_alert(subject, body): Email Joel about critical issues

Format your response as:
THOUGHT: [what you're thinking about the situation]
ACTION: [tool_name] [arguments if needed]

Or if you're done:
THOUGHT: [summary of what you found]
DONE: [brief status summary]

Only use send_alert for genuine problems. Only restart_service if something is actually down.
Be concise. Focus on what matters."""


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


def run_react():
    """Run one ReAct cycle."""
    state = load_state()
    state["runs"] = state.get("runs", 0) + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["last_run"] = now

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
- Last summary: {state.get('last_summary', 'none')}

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
