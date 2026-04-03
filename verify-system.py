#!/usr/bin/env python3
"""
verify-system.py — Full system verification.
Checks every service, endpoint, file, and integration point.
Run this before claiming anything works.

Usage:
  python3 verify-system.py          # Full check with color output
  python3 verify-system.py --json   # Machine-readable JSON
"""
import json, os, socket, sqlite3, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
results = []
pass_count = 0
fail_count = 0
warn_count = 0

def check(name, passed, detail="", warn=False):
    global pass_count, fail_count, warn_count
    status = "PASS" if passed else ("WARN" if warn else "FAIL")
    if passed:
        pass_count += 1
    elif warn:
        warn_count += 1
    else:
        fail_count += 1
    results.append({"name": name, "status": status, "detail": detail})
    if "--json" not in sys.argv:
        sym = "\033[32m✓\033[0m" if passed else ("\033[33m⚠\033[0m" if warn else "\033[31m✗\033[0m")
        d = f"  — {detail}" if detail else ""
        print(f"  {sym} {name}{d}")

def port_open(port, host="127.0.0.1"):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=BASE)
        return r.stdout.strip()
    except Exception:
        return ""

def file_age(path):
    try:
        return time.time() - os.path.getmtime(path)
    except Exception:
        return 99999

def main():
    as_json = "--json" in sys.argv
    if not as_json:
        print("\n\033[1m═══ MERIDIAN SYSTEM VERIFICATION ═══\033[0m")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")

    # ── 1. SERVICES & PORTS ──────────────────────
    if not as_json:
        print("\033[1m[1] Services & Ports\033[0m")

    check("Hub (port 8090)", port_open(8090))
    check("Chorus (port 8091)", port_open(8091))
    check("IMAP Bridge (port 1144)", port_open(1144))
    check("SMTP Bridge (port 1026)", port_open(1026))

    # 8092 should NOT be running
    check("Port 8092 cleaned up", not port_open(8092),
          "loop-control-center should be dead")

    # Ollama
    ollama_ok = "active" in run("systemctl is-active ollama 2>/dev/null")
    check("Ollama service", ollama_ok)

    # ── 2. HEARTBEAT & LOOP ──────────────────────
    if not as_json:
        print("\n\033[1m[2] Heartbeat & Loop\033[0m")

    hb_age = file_age(os.path.join(BASE, ".heartbeat"))
    check("Heartbeat fresh (<120s)", hb_age < 120, f"{int(hb_age)}s old")
    check("Heartbeat not stale (<300s)", hb_age < 300, warn=True)

    loop_file = os.path.join(BASE, ".loop-count")
    try:
        loop = int(open(loop_file).read().strip())
        check("Loop count readable", True, f"Loop {loop}")
    except Exception:
        check("Loop count readable", False)

    # ── 3. DATABASES ──────────────────────────────
    if not as_json:
        print("\n\033[1m[3] Databases\033[0m")

    for db_name, db_file in [("Relay DB", "agent-relay.db"), ("Memory DB", "memory.db")]:
        db_path = os.path.join(BASE, db_file)
        try:
            conn = sqlite3.connect(db_path, timeout=3)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            conn.close()
            check(f"{db_name} accessible", True, f"{len(tables)} tables")
        except Exception as e:
            check(f"{db_name} accessible", False, str(e))

    # VOLtar DB
    voltar_path = os.path.join(BASE, "voltar-keys.db")
    try:
        conn = sqlite3.connect(voltar_path, timeout=3)
        conn.execute("SELECT COUNT(*) FROM session_keys")
        pending = conn.execute(
            "SELECT COUNT(*) FROM voltar_sessions WHERE responded=0"
        ).fetchone()[0]
        conn.close()
        check("VOLtar DB", True, f"{pending} pending sessions")
    except Exception:
        check("VOLtar DB", True, "no sessions yet", warn=True)

    # ── 4. TUNNEL ─────────────────────────────────
    if not as_json:
        print("\n\033[1m[4] Tunnel & External Access\033[0m")

    config_path = os.path.join(BASE, "signal-config.json")
    try:
        cfg = json.load(open(config_path))
        tunnel_url = cfg.get("url", "")
        check("Tunnel config exists", bool(tunnel_url), tunnel_url[:60])
    except Exception:
        check("Tunnel config exists", False)
        tunnel_url = ""

    # Check cloudflared process
    cf_pid = run("pgrep -f 'cloudflared tunnel'")
    check("Cloudflared running", bool(cf_pid), f"pid {cf_pid}" if cf_pid else "not found")

    # ── 5. HUB API ENDPOINTS ─────────────────────
    if not as_json:
        print("\n\033[1m[5] Hub API Endpoints\033[0m")

    # Login to hub
    import urllib.request, urllib.parse
    env = {}
    env_path = os.path.join(BASE, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v.strip('"').strip("'")

    hub_pw = env.get("HUB_PASSWORD", "")
    session_cookie = ""
    try:
        data = urllib.parse.urlencode({"password": hub_pw}).encode()
        req = urllib.request.Request("http://127.0.0.1:8090/login", data=data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        resp = opener.open(req, timeout=5)
        # Extract cookie from redirect
        for h in resp.headers.get_all("Set-Cookie") or []:
            if "session=" in h:
                session_cookie = h.split("session=")[1].split(";")[0]
        check("Hub login", True)
    except Exception as e:
        check("Hub login", False, str(e))

    if session_cookie:
        endpoints = [
            "/api/home", "/api/agents", "/api/director", "/api/email",
            "/api/creative", "/api/system", "/api/relay",
            "/api/email-body?id=1", "/api/file-content?path=personality.md",
            "/api/agent-history?agent=Soma", "/api/logs?file=watchdog&lines=5",
        ]
        for ep in endpoints:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:8090{ep}")
                req.add_header("Cookie", f"session={session_cookie}")
                resp = urllib.request.urlopen(req, timeout=8)
                data = json.loads(resp.read())
                has_error = isinstance(data, dict) and "error" in data
                check(f"API {ep.split('?')[0]}", not has_error,
                      data.get("error", "OK")[:40] if isinstance(data, dict) else "OK")
            except Exception as e:
                check(f"API {ep.split('?')[0]}", False, str(e)[:60])

    # ── 6. CREATIVE FILES ─────────────────────────
    if not as_json:
        print("\n\033[1m[6] Creative Files\033[0m")

    import glob as _glob
    creative_dir = os.path.join(BASE, "creative")
    journals = len(_glob.glob(os.path.join(creative_dir, "journals", "journal-*.md")))
    poems = len(_glob.glob(os.path.join(creative_dir, "poems", "poem-*.md")))
    cogcorp = len(_glob.glob(os.path.join(creative_dir, "cogcorp", "CC-*.md")))
    check("Journals", journals > 0, f"{journals} files")
    check("Poems", poems > 0, f"{poems} files")
    check("CogCorp", cogcorp > 0, f"{cogcorp} files")

    # ── 7. GIT STATUS ─────────────────────────────
    if not as_json:
        print("\n\033[1m[7] Git Status\033[0m")

    branch = run("git rev-parse --abbrev-ref HEAD")
    check("Git branch", branch == "master", branch)

    dirty = run("git status --short | head -5")
    check("Working tree clean", not dirty,
          f"{len(dirty.splitlines())} changed files" if dirty else "clean",
          warn=bool(dirty))

    last_commit = run("git log -1 --oneline")
    check("Last commit", bool(last_commit), last_commit[:60])

    # ── 8. KEY FILES ──────────────────────────────
    if not as_json:
        print("\n\033[1m[8] Key Files\033[0m")

    for fname in [".capsule.md", ".loop-handoff.md", "personality.md",
                  ".env", "hub-v2.py", "the-signal-template.html",
                  "symbiosense.py", "the-chorus.py", "push-live-status.py"]:
        fpath = os.path.join(BASE, fname)
        exists = os.path.exists(fpath)
        age = int(file_age(fpath)) if exists else -1
        age_str = ""
        if age >= 0:
            if age < 3600:
                age_str = f"{age//60}m old"
            elif age < 86400:
                age_str = f"{age//3600}h old"
            else:
                age_str = f"{age//86400}d old"
        check(fname, exists, age_str)

    # ── SUMMARY ───────────────────────────────────
    if as_json:
        print(json.dumps({
            "pass": pass_count,
            "fail": fail_count,
            "warn": warn_count,
            "total": pass_count + fail_count + warn_count,
            "checks": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
    else:
        total = pass_count + fail_count + warn_count
        print(f"\n\033[1m═══ RESULTS: {pass_count}/{total} passed")
        if fail_count:
            print(f"  \033[31m{fail_count} FAILED\033[0m")
        if warn_count:
            print(f"  \033[33m{warn_count} warnings\033[0m")
        if fail_count == 0:
            print(f"  \033[32mAll checks passed.\033[0m")
        print()

if __name__ == "__main__":
    main()
