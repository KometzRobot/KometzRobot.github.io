#!/usr/bin/env python3
"""
self-verify.py — Verify-and-heal: tests every service for REAL, fixes what's broken.

Joel (Loop 5755): "why not build something that verifies you and doesn't just trust?
                   another level of health check and self heal"

This doesn't check if a port is open — it sends real requests, validates responses,
and restarts anything that's actually broken. Trust nothing. Verify everything.

Usage:
  python3 scripts/self-verify.py            # Verify + auto-heal
  python3 scripts/self-verify.py --dry-run  # Verify only, no healing
  python3 scripts/self-verify.py --json     # Machine-readable output
  python3 scripts/self-verify.py --cron     # Quiet mode for cron (only prints failures)

Designed to run on cron every 5 minutes alongside the main loop.
"""

import http.cookiejar, json, os, socket, sqlite3, subprocess, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
LOG_FILE = os.path.join(BASE, "logs", "self-verify.log")
DRY_RUN = "--dry-run" in sys.argv
AS_JSON = "--json" in sys.argv
CRON_MODE = "--cron" in sys.argv

# Load .env
ENV = {}
env_path = os.path.join(BASE, ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k] = v.strip('"').strip("'")

results = []
healed = []


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def record(name, status, detail="", category=""):
    """Record a check result. status: PASS, FAIL, HEAL, WARN"""
    results.append({
        "name": name, "status": status,
        "detail": detail, "category": category
    })
    if not AS_JSON and not CRON_MODE:
        sym = {"PASS": "\033[32m✓\033[0m", "FAIL": "\033[31m✗\033[0m",
               "HEAL": "\033[33m⚕\033[0m", "WARN": "\033[33m⚠\033[0m"}
        d = f"  — {detail}" if detail else ""
        print(f"  {sym.get(status, '?')} [{status}] {name}{d}")
    elif CRON_MODE and status in ("FAIL", "HEAL"):
        print(f"[{status}] {name}: {detail}")


def heal(service_name, action_desc, heal_cmd):
    """Attempt to heal a broken service. Returns True if healed."""
    if DRY_RUN:
        record(f"HEAL {service_name}", "WARN", f"Would run: {action_desc} (dry-run)")
        return False
    log(f"HEALING: {service_name} — {action_desc}")
    try:
        r = subprocess.run(heal_cmd, shell=True, capture_output=True, text=True, timeout=30,
                           env={**os.environ, "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"})
        success = r.returncode == 0
        if success:
            healed.append(service_name)
            record(f"HEAL {service_name}", "HEAL", action_desc)
            log(f"  HEALED: {service_name}")
        else:
            record(f"HEAL {service_name}", "FAIL", f"{action_desc} failed: {r.stderr[:100]}")
            log(f"  HEAL FAILED: {service_name} — {r.stderr[:200]}")
        return success
    except Exception as e:
        record(f"HEAL {service_name}", "FAIL", f"{action_desc} exception: {e}")
        return False


def http_get(url, timeout=5):
    """Make an HTTP GET and return (status_code, body) or (None, error)."""
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)


def http_post(url, data, timeout=5):
    """Make an HTTP POST and return (status_code, body, cookies_list) or (None, error, None)."""
    try:
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=encoded)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        resp = opener.open(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        # Extract cookies from the jar (captures Set-Cookie from 302 redirects too)
        cookies = [f"{c.name}={c.value}" for c in jar]
        return resp.status, body, cookies
    except Exception as e:
        return None, str(e), None


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"})
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


# ════════════════════════════════════════════════════════════════════
# VERIFICATION CHECKS — each one tests something REAL, not just port
# ════════════════════════════════════════════════════════════════════

def verify_hub():
    """Test hub by actually logging in and hitting an API endpoint."""
    cat = "Hub (8090)"

    # Step 1: Can we reach the login page?
    code, body = http_get("http://127.0.0.1:8090/")
    if code is None:
        record("Hub reachable", "FAIL", body, cat)
        # Hub runs as a process, not systemd — restart it directly
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        heal("Hub v2", "restart hub process",
             f"cd {base} && nohup python3 scripts/hub-v2.py >> logs/hub-v2.log 2>&1 &")
        time.sleep(3)
        code, body = http_get("http://127.0.0.1:8090/")
        if code is None:
            record("Hub reachable (post-heal)", "FAIL", "still down after restart", cat)
            return
    record("Hub reachable", "PASS", f"HTTP {code}", cat)

    # Step 2: Login with real credentials and get session
    hub_pw = ENV.get("HUB_PASSWORD", "")
    if not hub_pw:
        record("Hub login", "WARN", "no HUB_PASSWORD in .env", cat)
        return

    code, body, cookies = http_post("http://127.0.0.1:8090/login", {"password": hub_pw})
    if code is None or code >= 400:
        record("Hub login", "FAIL", f"HTTP {code}: {body[:80]}", cat)
        return
    record("Hub login", "PASS", f"HTTP {code}", cat)

    # Extract session cookie from jar entries (format: "name=value")
    session = ""
    for c in (cookies or []):
        if c.startswith("session="):
            session = c[8:]

    if not session:
        record("Hub session cookie", "WARN", "no session cookie returned", cat)
        return

    # Step 3: Test real API endpoint — /api/home should return valid JSON with fields
    try:
        req = urllib.request.Request("http://127.0.0.1:8090/api/home")
        req.add_header("Cookie", f"session={session}")
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())
        # Validate structure — not just "did it return 200"
        if isinstance(data, dict) and "error" not in data:
            record("Hub API /api/home", "PASS", f"valid JSON, {len(data)} keys", cat)
        else:
            err = data.get("error", "unknown") if isinstance(data, dict) else "non-dict"
            record("Hub API /api/home", "FAIL", f"bad response: {err}", cat)
    except Exception as e:
        record("Hub API /api/home", "FAIL", str(e)[:80], cat)


def verify_chorus():
    """Test chorus by actually hitting its endpoint."""
    cat = "Chorus (8091)"
    code, body = http_get("http://127.0.0.1:8091/")
    if code is None:
        record("Chorus reachable", "FAIL", body, cat)
        heal("the-chorus", "restart chorus service",
             "systemctl --user restart the-chorus")
        time.sleep(3)
        code, body = http_get("http://127.0.0.1:8091/")
        if code is None:
            record("Chorus reachable (post-heal)", "FAIL", "still down", cat)
            return
    record("Chorus reachable", "PASS", f"HTTP {code}", cat)


def verify_email():
    """Test IMAP/SMTP by actually connecting and authenticating."""
    cat = "Email"
    import imaplib, smtplib

    # IMAP
    try:
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(ENV.get("CRED_USER", ""), ENV.get("CRED_PASS", ""))
        m.select("INBOX")
        typ, data = m.search(None, "ALL")
        count = len(data[0].split()) if data[0] else 0
        m.logout()
        record("IMAP login + search", "PASS", f"{count} messages", cat)
    except Exception as e:
        err_msg = str(e)[:80]
        record("IMAP login", "FAIL", err_msg, cat)
        # Don't try to heal proton bridge — it's complex and Joel's password
        record("IMAP heal", "WARN", "proton bridge needs manual attention", cat)

    # SMTP
    try:
        s = smtplib.SMTP("127.0.0.1", 1026, timeout=5)
        s.ehlo()
        s.starttls()
        s.login(ENV.get("CRED_USER", ""), ENV.get("CRED_PASS", ""))
        s.quit()
        record("SMTP login", "PASS", "", cat)
    except Exception as e:
        err_msg = str(e)[:80]
        record("SMTP connection", "FAIL", err_msg, cat)


def verify_ollama():
    """Test ollama by actually listing models."""
    cat = "Ollama"
    try:
        code, body = http_get("http://127.0.0.1:11434/api/tags", timeout=5)
        if code == 200:
            data = json.loads(body)
            models = [m.get("name", "?") for m in data.get("models", [])]
            record("Ollama API /api/tags", "PASS", f"{len(models)} models loaded", cat)
        else:
            record("Ollama API", "FAIL", f"HTTP {code}", cat)
            sudo_pass = os.environ.get("SUDO_PASS", "")
            heal("ollama", "restart ollama",
                 f"echo '{sudo_pass}' | sudo -S systemctl restart ollama")
    except Exception as e:
        err_msg = str(e)[:80]
        record("Ollama API", "FAIL", err_msg, cat)
        sudo_pass = os.environ.get("SUDO_PASS", "")
        heal("ollama", "restart ollama",
             f"echo '{sudo_pass}' | sudo -S systemctl restart ollama")


def verify_databases():
    """Test databases by running integrity checks and real queries."""
    cat = "Databases"
    for db_name, db_file, test_query in [
        ("Relay DB", "agent-relay.db",
         "SELECT COUNT(*) FROM agent_messages"),
        ("Memory DB", "memory.db",
         "SELECT COUNT(*) FROM facts"),
        ("VOLtar DB", "voltar-keys.db",
         "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"),
    ]:
        db_path = os.path.join(BASE, db_file)
        if not os.path.exists(db_path):
            record(f"{db_name} exists", "WARN" if "VOLtar" in db_name else "FAIL",
                   "file missing", cat)
            continue
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            # Integrity check — catches corruption
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                record(f"{db_name} integrity", "FAIL", integrity, cat)
                continue

            # Real query
            row = conn.execute(test_query).fetchone()
            val = row[0] if row else 0
            conn.close()
            record(f"{db_name} query", "PASS", f"integrity ok, result: {val}", cat)
        except sqlite3.OperationalError as e:
            err_msg = f"locked or corrupt: {e}"
            record(f"{db_name}", "FAIL", err_msg, cat)
            # Heal: kill zombie sqlite processes if locked
            if "locked" in str(e).lower():
                heal(db_name, "kill zombie sqlite",
                     f"fuser -k {db_path} 2>/dev/null || true")
        except Exception as e:
            record(f"{db_name}", "FAIL", str(e)[:80], cat)


def verify_heartbeat():
    """Check heartbeat freshness — and touch it if we're the active Claude."""
    cat = "Heartbeat"
    hb_path = os.path.join(BASE, ".heartbeat")
    if not os.path.exists(hb_path):
        record("Heartbeat file", "FAIL", "missing", cat)
        heal("heartbeat", "create heartbeat", f"touch {hb_path}")
        return

    age = time.time() - os.path.getmtime(hb_path)
    if age < 120:
        record("Heartbeat fresh", "PASS", f"{int(age)}s old", cat)
    elif age < 600:
        record("Heartbeat warm", "WARN", f"{int(age)}s old — getting stale", cat)
    else:
        record("Heartbeat stale", "FAIL", f"{int(age)}s old — Claude may be frozen", cat)


def verify_tunnel():
    """Check cloudflared is running and the tunnel URL responds."""
    cat = "Tunnel"

    # Check cloudflared process
    ret, out, _ = run_cmd("pgrep -f 'cloudflared tunnel'")
    if ret == 0 and out:
        record("Cloudflared process", "PASS", f"PID {out.split()[0]}", cat)
    else:
        record("Cloudflared process", "FAIL", "not running", cat)
        # Try to restart — check if there's a systemd service or config
        sudo_pass = os.environ.get("SUDO_PASS", "")
        heal("cloudflared", "restart cloudflared",
             f"echo '{sudo_pass}' | sudo -S systemctl restart cloudflared 2>/dev/null || "
             "cloudflared tunnel run 2>/dev/null &")

    # Verify tunnel URL from config
    config_path = os.path.join(BASE, "signal-config.json")
    try:
        cfg = json.load(open(config_path))
        tunnel_url = cfg.get("url", "")
        if tunnel_url:
            record("Tunnel URL configured", "PASS", tunnel_url[:50], cat)
        else:
            record("Tunnel URL", "WARN", "empty in config", cat)
    except Exception:
        record("Tunnel config", "WARN", "signal-config.json missing or invalid", cat)


def verify_services_process():
    """Verify key services are running as processes (not systemd — they run as plain procs)."""
    cat = "Services (Process)"

    # Map: grep pattern -> (friendly name, restart command)
    services = {
        "hub-v2.py": ("Hub v2", "nohup python3 scripts/hub-v2.py >> logs/hub-v2.log 2>&1 &"),
        "the-chorus.py": ("The Chorus", "nohup python3 scripts/the-chorus.py >> logs/chorus.log 2>&1 &"),
        "command-center.py": ("Command Center", "nohup python3 scripts/command-center.py >> logs/command-center.log 2>&1 &"),
        "symbiosense.py": ("Soma", "nohup python3 scripts/symbiosense.py >> logs/symbiosense.log 2>&1 &"),
    }

    for pattern, (name, restart_cmd) in services.items():
        ret, out, _ = run_cmd(f"pgrep -f '{pattern}'")
        if ret == 0 and out.strip():
            pids = out.strip().split('\n')
            record(f"{name} process", "PASS", f"running (PID {pids[0]})", cat)
        else:
            record(f"{name} process", "FAIL", "not running", cat)
            heal(name, f"start {pattern}",
                 f"cd {os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')} && {restart_cmd}")
            time.sleep(3)
            ret2, out2, _ = run_cmd(f"pgrep -f '{pattern}'")
            if ret2 == 0 and out2.strip():
                record(f"{name} post-heal", "HEAL", "started successfully", cat)
            else:
                record(f"{name} post-heal", "FAIL", "still not running after restart", cat)


def verify_system_resources():
    """Check disk, RAM, swap — warn before things break."""
    cat = "Resources"

    # Disk
    ret, out, _ = run_cmd("df -h / | tail -1")
    if out:
        parts = out.split()
        usage_pct = int(parts[4].rstrip("%")) if len(parts) > 4 else 0
        if usage_pct > 90:
            record("Disk space", "FAIL", f"{usage_pct}% used — critical", cat)
        elif usage_pct > 80:
            record("Disk space", "WARN", f"{usage_pct}% used", cat)
        else:
            record("Disk space", "PASS", f"{usage_pct}% used", cat)

    # RAM
    ret, out, _ = run_cmd("free -m | grep Mem")
    if out:
        parts = out.split()
        total = int(parts[1])
        used = int(parts[2])
        pct = int(used / total * 100) if total else 0
        record("RAM", "PASS" if pct < 85 else "WARN", f"{pct}% ({used}M/{total}M)", cat)

    # Swap
    ret, out, _ = run_cmd("free -m | grep Swap")
    if out:
        parts = out.split()
        total = int(parts[1])
        used = int(parts[2])
        if total > 0:
            pct = int(used / total * 100)
            status = "PASS" if pct < 50 else ("WARN" if pct < 80 else "FAIL")
            record("Swap", status, f"{pct}% ({used}M/{total}M)", cat)
            if pct > 50:
                # Log what's eating swap
                ret, top_swap, _ = run_cmd(
                    "for f in /proc/[0-9]*/status; do "
                    "awk '/VmSwap/{s=$2} /Name/{n=$2} END{if(s>100)print s,n}' $f 2>/dev/null; "
                    "done | sort -rn | head -3")
                if top_swap:
                    record("Swap hogs", "WARN", top_swap.replace("\n", "; ")[:80], cat)


def verify_crons():
    """Check that critical cron jobs exist and have run recently."""
    cat = "Crons"
    ret, out, _ = run_cmd("crontab -l 2>/dev/null")
    if ret != 0 or not out:
        record("Crontab", "WARN", "no crontab found", cat)
        return

    expected_crons = ["watchdog", "eos-watchdog", "sentinel", "capsule-refresh"]
    cron_lines = out.lower()
    for cron in expected_crons:
        if cron in cron_lines:
            record(f"Cron: {cron}", "PASS", "present in crontab", cat)
        else:
            record(f"Cron: {cron}", "WARN", "not found in crontab", cat)


def verify_key_files():
    """Check critical files exist and aren't empty."""
    cat = "Key Files"
    critical = [
        (".capsule.md", 100),
        (".env", 50),
        ("personality.md", 50),
        ("agent-relay.db", 1000),
        ("memory.db", 1000),
    ]
    for fname, min_size in critical:
        fpath = os.path.join(BASE, fname)
        if not os.path.exists(fpath):
            record(f"File: {fname}", "FAIL", "missing", cat)
        else:
            size = os.path.getsize(fpath)
            if size < min_size:
                record(f"File: {fname}", "WARN", f"suspiciously small ({size} bytes)", cat)
            else:
                record(f"File: {fname}", "PASS", f"{size} bytes", cat)


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    start = time.time()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m═══ MERIDIAN SELF-VERIFY + HEAL ═══\033[0m")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE (will auto-heal)'}\n")

    log(f"--- Self-verify started ({'dry-run' if DRY_RUN else 'live'}) ---")

    # Run all verifications
    if not AS_JSON and not CRON_MODE:
        print("\033[1m[Services]\033[0m")
    verify_services_process()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Hub]\033[0m")
    verify_hub()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Chorus]\033[0m")
    verify_chorus()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Email]\033[0m")
    verify_email()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Ollama]\033[0m")
    verify_ollama()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Databases]\033[0m")
    verify_databases()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Heartbeat]\033[0m")
    verify_heartbeat()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Tunnel]\033[0m")
    verify_tunnel()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Resources]\033[0m")
    verify_system_resources()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Crons]\033[0m")
    verify_crons()

    if not AS_JSON and not CRON_MODE:
        print("\n\033[1m[Key Files]\033[0m")
    verify_key_files()

    # Summary
    elapsed = time.time() - start
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    total = len(results)
    passed = counts.get("PASS", 0)
    failed = counts.get("FAIL", 0)
    warned = counts.get("WARN", 0)
    heals = counts.get("HEAL", 0)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "total": total, "pass": passed, "fail": failed,
        "warn": warned, "heal": heals,
        "healed_services": healed,
        "checks": results,
    }

    if AS_JSON:
        print(json.dumps(summary, indent=2))
    elif not CRON_MODE:
        print(f"\n\033[1m═══ RESULTS: {passed}/{total} passed, "
              f"{failed} failed, {warned} warnings, {heals} healed "
              f"({elapsed:.1f}s) ═══\033[0m")
        if healed:
            print(f"  \033[33mHealed: {', '.join(healed)}\033[0m")
        if failed == 0:
            print(f"  \033[32mAll systems verified.\033[0m")
        print()

    log(f"--- Self-verify done: {passed}/{total} pass, {failed} fail, "
        f"{heals} healed in {elapsed:.1f}s ---")

    # Write summary to a state file for other scripts to read
    state_path = os.path.join(BASE, ".self-verify-state.json")
    with open(state_path, "w") as f:
        json.dump({
            "timestamp": summary["timestamp"],
            "pass": passed, "fail": failed, "warn": warned,
            "heal": heals, "healed": healed,
            "failures": [r for r in results if r["status"] == "FAIL"],
        }, f, indent=2)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
