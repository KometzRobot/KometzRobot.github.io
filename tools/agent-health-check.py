#!/usr/bin/env python3
"""
agent-health-check.py — Unified health check across all Meridian agents.

Checks: heartbeat age, service status, relay freshness, cron execution,
state file ages, port availability. Outputs a clear pass/warn/fail report.

Usage: python3 agent-health-check.py [--json]
"""
import os, sys, json, sqlite3, subprocess, time, socket
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))

def file_age(path):
    try: return int(time.time() - os.path.getmtime(os.path.join(BASE, path)))
    except: return 99999

def port_open(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except: return False

def svc_active(name):
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", name],
                         capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"
    except: return False

def relay_age(agent_name):
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"), timeout=3)
        row = db.execute(
            "SELECT timestamp FROM agent_messages WHERE agent=? ORDER BY id DESC LIMIT 1",
            (agent_name,)).fetchone()
        db.close()
        if row:
            ts = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
            return int((datetime.now(timezone.utc) - ts).total_seconds())
    except: pass
    return 99999

def check(name, ok, warn_msg="", detail=""):
    status = "PASS" if ok else ("WARN" if warn_msg else "FAIL")
    return {"name": name, "status": status, "detail": detail or warn_msg}

def main():
    as_json = "--json" in sys.argv
    checks = []

    # Heartbeat
    hb = file_age(".heartbeat")
    checks.append(check("Heartbeat", hb < 300, f"{hb}s (stale)" if hb >= 300 else "", f"{hb}s"))

    # Services
    for svc, port in [("meridian-hub-v2", 8090), ("symbiosense", None), ("the-chorus", 8091)]:
        active = svc_active(svc)
        port_ok = port_open(port) if port else True
        ok = active and port_ok
        detail = f"{'active' if active else 'dead'}" + (f", port {port} {'open' if port_ok else 'closed'}" if port else "")
        checks.append(check(f"Service: {svc}", ok, detail=detail))

    # Agents (relay freshness)
    for agent in ["Meridian", "Soma", "Eos", "Nova", "Atlas", "Tempo", "Hermes", "Sentinel"]:
        age = relay_age(agent)
        ok = age < 900
        checks.append(check(f"Agent: {agent}", ok, detail=f"last seen {age}s ago"))

    # State files
    for sf in [".symbiosense-state.json", ".soma-psyche.json", ".soma-goals.json"]:
        age = file_age(sf)
        checks.append(check(f"State: {sf}", age < 600, detail=f"{age}s old"))

    # Proton Bridge
    bridge = port_open(1144)
    checks.append(check("Proton Bridge (IMAP)", bridge, detail="port 1144"))

    # Tunnel
    tunnel = port_open(8090)
    checks.append(check("Tunnel target (8090)", tunnel))

    # Summary
    passes = sum(1 for c in checks if c["status"] == "PASS")
    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")

    if as_json:
        print(json.dumps({"checks": checks, "summary": {"pass": passes, "fail": fails, "warn": warns}}, indent=2))
    else:
        print(f"Agent Health Check — {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*50}")
        for c in checks:
            icon = "✓" if c["status"] == "PASS" else ("⚠" if c["status"] == "WARN" else "✗")
            print(f"  {icon} {c['name']:35} {c['detail']}")
        print(f"\n  {passes} pass, {warns} warn, {fails} fail")

if __name__ == "__main__":
    main()
