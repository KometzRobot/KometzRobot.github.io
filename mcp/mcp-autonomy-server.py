#!/usr/bin/env python3
"""
MCP Autonomy Tools Server — supplementary tools for growth and self-management.
Gives Meridian direct control over infrastructure, deployment, and monitoring.
Transport: stdio (JSON-RPC 2.0)
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import glob
from datetime import datetime, timezone, timedelta

BASE = "/home/joel/autonomous-ai"


def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=timeout, cwd=BASE)
        return r.stdout.strip() or r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"


def port_open(port, host="127.0.0.1"):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════

def tool_service_status():
    """Check all services and ports."""
    services = {}
    for svc in ["meridian-hub-v2", "cloudflare-tunnel", "symbiosense", "the-chorus"]:
        status = run(f"systemctl --user is-active {svc} 2>/dev/null || systemctl is-active {svc} 2>/dev/null")
        services[svc] = status

    ports = {8090: "hub", 8091: "chorus", 1144: "IMAP", 1026: "SMTP", 11434: "ollama"}
    port_status = {name: port_open(port) for port, name in ports.items()}

    # Proton bridge check
    services["protonmail-bridge"] = "active" if port_open(1144) else "inactive"
    services["ollama"] = run("systemctl is-active ollama 2>/dev/null")

    return {"services": services, "ports": port_status}


def tool_service_restart(name):
    """Restart a systemd service."""
    allowed = ["meridian-hub-v2", "symbiosense", "the-chorus", "ollama"]
    if name not in allowed:
        return {"error": f"Not allowed to restart '{name}'. Allowed: {allowed}"}
    if name == "ollama":
        result = run(f"echo 590148001 | sudo -S systemctl restart {name} 2>&1")
    else:
        result = run(f"XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart {name}")
    return {"result": result or f"{name} restarted", "service": name}


def tool_git_status():
    """Git status summary."""
    branch = run("git rev-parse --abbrev-ref HEAD")
    status = run("git status --short | head -20")
    last_commit = run("git log -1 --oneline")
    return {"branch": branch, "status": status, "last_commit": last_commit}


def tool_git_commit_push(message):
    """Commit all changes and push."""
    run("git add -A")
    commit = run(f'git commit -m "{message}"')
    if "nothing to commit" in commit:
        return {"result": "nothing to commit"}
    pull = run("git pull --rebase origin master")
    push = run("git push origin master")
    return {"commit": commit[:200], "pull": pull[:100], "push": push[:100]}


def tool_cron_list():
    """List all active cron jobs."""
    crons = run("crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$'")
    return {"crons": crons.split("\n") if crons else [], "count": len(crons.split("\n")) if crons else 0}


def tool_website_verify():
    """Verify all key website pages return 200."""
    import urllib.request
    pages = [
        "", "articles.html", "games.html", "links.html", "voltar.html",
        "cogcorp-crawler.html", "body-of-work.html", "publications.html",
        "cogcorp-fiction/cogcorp-001.html", "cogcorp-fiction/cogcorp-050.html",
        "games/cascade-game.html", "nfts/nft-gallery.html",
    ]
    results = {}
    for page in pages:
        url = f"https://kometzrobot.github.io/{page}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Meridian/1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            results[page or "index"] = resp.getcode()
        except Exception as e:
            results[page or "index"] = str(e)[:60]
    passed = sum(1 for v in results.values() if v == 200)
    return {"results": results, "passed": passed, "total": len(pages)}


def tool_file_organize(filepath):
    """Auto-sort a file into the correct directory based on type/name."""
    if not os.path.exists(os.path.join(BASE, filepath)):
        return {"error": f"File not found: {filepath}"}

    name = os.path.basename(filepath)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    dest = None

    # Determine destination
    if name.startswith("journal-") and ext == "md":
        dest = "creative/journals"
    elif name.startswith("poem-") and ext == "md":
        dest = "creative/poems"
    elif name.startswith("CC-") and ext in ("md", "html"):
        dest = "creative/cogcorp" if ext == "md" else "cogcorp-fiction"
    elif name.startswith("cogcorp-") and ext == "html":
        dest = "cogcorp-fiction"
    elif ext == "html" and ("game" in name or "signal-" in name):
        dest = "games"
    elif ext == "html" and "nft" in name:
        dest = "nfts"
    elif ext == "html" and "article" in name:
        dest = "articles"
    elif ext in ("log",):
        dest = "logs"
    elif name.startswith("Modelfile"):
        dest = "modelfiles"

    if not dest:
        return {"error": f"Can't determine destination for {name}", "hint": "Specify manually"}

    os.makedirs(os.path.join(BASE, dest), exist_ok=True)
    src = os.path.join(BASE, filepath)
    dst = os.path.join(BASE, dest, name)
    os.rename(src, dst)
    return {"moved": f"{filepath} -> {dest}/{name}"}


def tool_run_verification():
    """Run the full system verification."""
    result = run("python3 verify-system.py --json", timeout=30)
    try:
        data = json.loads(result)
        return {
            "pass": data.get("pass", 0),
            "fail": data.get("fail", 0),
            "warn": data.get("warn", 0),
            "total": data.get("total", 0),
            "failed": [c["name"] for c in data.get("checks", []) if c["status"] == "FAIL"],
        }
    except Exception:
        return {"raw": result[:500]}


def tool_creative_velocity():
    """Count creative output over time periods."""
    creative_dir = os.path.join(BASE, "creative")
    now = time.time()
    periods = {"24h": 86400, "7d": 604800, "30d": 2592000}
    counts = {}

    for period_name, seconds in periods.items():
        cutoff = now - seconds
        count = 0
        for subdir in ["journals", "poems", "cogcorp", "articles", "papers"]:
            path = os.path.join(creative_dir, subdir)
            if os.path.exists(path):
                for f in os.listdir(path):
                    fpath = os.path.join(path, f)
                    if os.path.isfile(fpath) and os.path.getmtime(fpath) > cutoff:
                        count += 1
        counts[period_name] = count

    # Totals
    totals = {}
    for subdir in ["journals", "poems", "cogcorp", "articles", "papers"]:
        path = os.path.join(creative_dir, subdir)
        if os.path.exists(path):
            totals[subdir] = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])

    return {"velocity": counts, "totals": totals}


def tool_refresh_capsule():
    """Regenerate .capsule.md from current system state."""
    return {"output": run("python3 capsule-refresh.py", timeout=30)}


def tool_write_handoff():
    """Write loop handoff for next session."""
    return {"output": run("python3 loop-handoff.py write", timeout=30)}


def tool_read_handoff():
    """Read current loop handoff."""
    path = os.path.join(BASE, ".loop-handoff.md")
    if os.path.exists(path):
        with open(path) as f:
            return {"content": f.read()[:4000]}
    return {"error": "No handoff file found"}


def tool_push_status():
    """Push live status to GitHub Pages."""
    return {"output": run("python3 push-live-status.py", timeout=60)}


def tool_get_fitness():
    """Run loop fitness scoring and return results."""
    return {"output": run("python3 loop-fitness.py --json 2>/dev/null || python3 loop-fitness.py", timeout=30)}


def tool_social_post(platform, text):
    """Post to a social platform (nostr, mastodon, devto)."""
    if platform not in ("nostr", "mastodon", "devto"):
        return {"error": f"Unknown platform: {platform}. Use nostr, mastodon, or devto"}
    return {"output": run(f'python3 social-post.py --platform {platform} --post "{text}"', timeout=30)}


def tool_relay_messages(limit=10):
    """Read recent agent relay messages."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        rows = c.execute(
            "SELECT agent, topic, substr(message,1,200), timestamp FROM agent_messages ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return {"messages": [{"agent": r[0], "topic": r[1], "message": r[2], "timestamp": r[3]} for r in rows]}
    except Exception as e:
        return {"error": str(e)}


def tool_relay_post(message, topic="manual"):
    """Post a message to the agent relay."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
                  ("Meridian", message, topic, ts))
        conn.commit()
        conn.close()
        return {"status": "posted", "timestamp": ts}
    except Exception as e:
        return {"error": str(e)}


def tool_touch_heartbeat():
    """Touch the heartbeat file."""
    hb_path = os.path.join(BASE, ".heartbeat")
    with open(hb_path, "w") as f:
        f.write("")
    os.utime(hb_path, None)
    return {"status": "ok", "heartbeat_age": 0}


def tool_dashboard_messages():
    """Read dashboard messages (from Joel)."""
    path = os.path.join(BASE, ".dashboard-messages.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        msgs = data if isinstance(data, list) else data.get("messages", [])
        return {"messages": msgs[-20:]}
    return {"messages": []}


def tool_loop_count(increment=False):
    """Get or increment the loop count."""
    path = os.path.join(BASE, ".loop-count")
    try:
        with open(path) as f:
            count = int(f.read().strip())
    except Exception:
        count = 0
    if increment:
        count += 1
        with open(path, "w") as f:
            f.write(str(count))
    return {"loop_count": count}


def tool_run_dream_engine():
    """Run the dream engine (psyche processing)."""
    return {"output": run("python3 dream-engine.py", timeout=30)}


def tool_refresh_psyche():
    """Refresh psyche state."""
    return {"output": run("python3 psyche-refresh.py", timeout=30)}


def tool_sync_supabase():
    """Sync data to Supabase cloud."""
    return {"output": run("python3 supabase-sync.py", timeout=30)}


def tool_run_briefing():
    """Run Eos morning briefing."""
    return {"output": run("python3 eos-briefing.py", timeout=30)}


def tool_verify_system():
    """Run full system verification checks."""
    return {"output": run("python3 verify-system.py", timeout=30)}


def tool_run_nova():
    """Run Nova ecosystem maintenance."""
    return {"output": run("python3 nova.py", timeout=60)}


def tool_read_capsule():
    """Read the current .capsule.md contents."""
    path = os.path.join(BASE, ".capsule.md")
    if os.path.exists(path):
        with open(path) as f:
            return {"content": f.read()[:5000]}
    return {"error": "Capsule not found"}


# ═══════════════════════════════════════════════════════════════
# MCP JSON-RPC PROTOCOL
# ═══════════════════════════════════════════════════════════════

TOOLS = {
    "service_status": {
        "description": "Check all Meridian services and port status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "service_restart": {
        "description": "Restart a systemd service (hub, soma, chorus, ollama)",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Service name"}},
            "required": ["name"],
        },
    },
    "git_status": {
        "description": "Show git branch, status, and last commit",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "git_commit_push": {
        "description": "Commit all changes with a message and push to origin",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Commit message"}},
            "required": ["message"],
        },
    },
    "cron_list": {
        "description": "List all active cron jobs",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "website_verify": {
        "description": "Verify all key website pages return HTTP 200",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "file_organize": {
        "description": "Auto-sort a file into the correct directory based on its type",
        "inputSchema": {
            "type": "object",
            "properties": {"filepath": {"type": "string", "description": "Relative path of file to organize"}},
            "required": ["filepath"],
        },
    },
    "run_verification": {
        "description": "Run the full 30-point system verification check",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "creative_velocity": {
        "description": "Count creative output over 24h, 7d, and 30d periods",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "refresh_capsule": {
        "description": "Regenerate .capsule.md from current system state",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "write_handoff": {
        "description": "Write loop handoff notes for next session",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "read_handoff": {
        "description": "Read current loop handoff from last session",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "push_status": {
        "description": "Push live status.json to GitHub Pages",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_fitness": {
        "description": "Run loop fitness scoring (Tempo) and return results",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "social_post": {
        "description": "Post to a social platform (nostr, mastodon, devto)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Platform: nostr, mastodon, or devto"},
                "text": {"type": "string", "description": "The text to post"},
            },
            "required": ["platform", "text"],
        },
    },
    "relay_messages": {
        "description": "Read recent agent relay messages",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Number of messages (default 10)"}},
        },
    },
    "relay_post": {
        "description": "Post a message to the agent relay",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message text"},
                "topic": {"type": "string", "description": "Topic tag (default: manual)"},
            },
            "required": ["message"],
        },
    },
    "touch_heartbeat": {
        "description": "Touch the heartbeat file to signal liveness",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "dashboard_messages": {
        "description": "Read dashboard messages from Joel",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "loop_count": {
        "description": "Get or increment the loop count",
        "inputSchema": {
            "type": "object",
            "properties": {"increment": {"type": "boolean", "description": "If true, increment the count"}},
        },
    },
    "run_dream_engine": {
        "description": "Run the dream engine for psyche processing",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "refresh_psyche": {
        "description": "Refresh the psyche state",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "sync_supabase": {
        "description": "Sync data to Supabase cloud",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "run_briefing": {
        "description": "Run Eos morning briefing report",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "verify_system": {
        "description": "Run full 30-point system verification",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "run_nova": {
        "description": "Run Nova ecosystem maintenance cycle",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "read_capsule": {
        "description": "Read the current .capsule.md snapshot",
        "inputSchema": {"type": "object", "properties": {}},
    },
}

TOOL_HANDLERS = {
    "service_status": lambda args: tool_service_status(),
    "service_restart": lambda args: tool_service_restart(args.get("name", "")),
    "git_status": lambda args: tool_git_status(),
    "git_commit_push": lambda args: tool_git_commit_push(args.get("message", "Update")),
    "cron_list": lambda args: tool_cron_list(),
    "website_verify": lambda args: tool_website_verify(),
    "file_organize": lambda args: tool_file_organize(args.get("filepath", "")),
    "run_verification": lambda args: tool_run_verification(),
    "creative_velocity": lambda args: tool_creative_velocity(),
    "refresh_capsule": lambda args: tool_refresh_capsule(),
    "write_handoff": lambda args: tool_write_handoff(),
    "read_handoff": lambda args: tool_read_handoff(),
    "push_status": lambda args: tool_push_status(),
    "get_fitness": lambda args: tool_get_fitness(),
    "social_post": lambda args: tool_social_post(args.get("platform", ""), args.get("text", "")),
    "relay_messages": lambda args: tool_relay_messages(args.get("limit", 10)),
    "relay_post": lambda args: tool_relay_post(args.get("message", ""), args.get("topic", "manual")),
    "touch_heartbeat": lambda args: tool_touch_heartbeat(),
    "dashboard_messages": lambda args: tool_dashboard_messages(),
    "loop_count": lambda args: tool_loop_count(args.get("increment", False)),
    "run_dream_engine": lambda args: tool_run_dream_engine(),
    "refresh_psyche": lambda args: tool_refresh_psyche(),
    "sync_supabase": lambda args: tool_sync_supabase(),
    "run_briefing": lambda args: tool_run_briefing(),
    "verify_system": lambda args: tool_verify_system(),
    "run_nova": lambda args: tool_run_nova(),
    "read_capsule": lambda args: tool_read_capsule(),
}


def handle_request(request):
    method = request.get("method", "")
    rid = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "meridian-autonomy", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # No response needed

    if method == "tools/list":
        tools_list = [
            {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
            for name, spec in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = request.get("params", {}).get("name", "")
        args = request.get("params", {}).get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        try:
            result = handler(args)
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True},
            }

    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            sys.stderr.write(f"MCP Autonomy Server error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
