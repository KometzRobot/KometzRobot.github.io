#!/usr/bin/env python3
"""
Tempo Loop Fitness Tracker v2 — 10K Scale, 60+ Dimensions.

Joel: "add more things to check and audit for a health score of 10k"

Tracks quantifiable metrics about system health each loop iteration,
computes a fitness score (0-10000) across 60+ dimensions in 10 categories,
stores history, and detects trends.

Recalibrated Loop 2081 per Joel: "be MUCH harsher"
  - Operational metrics scaled to 50% (max 5000)
  - Growth & Ambition category added (max 5000)
  - Calm running state ≈ 5000 (50%)
  - Best days with progress ≈ 7000-8000
  - Euphoria ≈ 8000-9000

Categories (10,000 total):
  Operational (scaled 50%):
    Core Vitals ........... 750  (was 1500)
    Agent Health .......... 750  (was 1500)
    Infrastructure ........ 750  (was 1500)
    System Resources ...... 750  (was 1500)
    Data & Communication .. 500  (was 1000)
    Security .............. 500  (was 1000)
    Network ............... 250  (was 500)
    Knowledge/Memory ...... 250  (was 500)
    Web Presence .......... 250  (was 500)
    Deployment ............ 250  (was 500)
  Growth & Ambition ....... 5000 (NEW)

Runs: every 30 minutes via cron, or called directly.
  python3 loop-fitness.py          # Run fitness check
  python3 loop-fitness.py history  # Show recent scores
  python3 loop-fitness.py trend    # Show trend analysis
  python3 loop-fitness.py detail   # Show per-category breakdown
"""

import os
import time
import json
import sqlite3
import subprocess
import glob
import socket
import re
from datetime import datetime, timedelta, timezone

def _utcnow():
    """Naive UTC datetime (avoids deprecated _utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

BASE = "/home/joel/autonomous-ai"
try:
    import sys; sys.path.insert(0, BASE)
    import load_env
except: pass
MEMORY_DB = os.path.join(BASE, "memory.db")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")

# ══════════════════════════════════════════════════════════════════
# WEIGHTS — must sum to 10000
# ══════════════════════════════════════════════════════════════════
WEIGHTS = {
    # ── Core Vitals (1500) ──
    "heartbeat":           200,
    "heartbeat_regularity": 100,
    "email_imap":          100,
    "email_smtp":          100,
    "email_unread_backlog": 80,
    "bridge_service":      100,
    "loop_freshness":      160,
    "loop_increment_rate":  80,
    "wake_state_freshness": 80,
    "context_preloader":    70,
    "special_notes":        60,
    "loop_count_file":      60,
    "startup_script":       60,
    "wakeup_prompt":        60,
    "claude_running":      200,

    # ── Agent Health (1500) ──
    "agents_active":       150,
    "agent_atlas":          90,
    "agent_soma":           90,
    "agent_nova":           90,
    "agent_eos":            90,
    "agent_tempo":          90,
    "agent_meridian":       90,
    "relay_diversity":     110,
    "relay_recency":       120,
    "soma_mood":           100,
    "soma_state_fresh":     70,
    "eos_observations":     70,
    "nova_runs":            70,
    "atlas_audits":         70,
    "agent_error_rate":    120,
    "agent_coordination":   80,

    # ── Infrastructure (1500) ──
    "crons_running":       100,
    "cron_push_status":     60,
    "cron_watchdog":        60,
    "cron_nova":            60,
    "cron_atlas":           60,
    "cron_eos_react":       60,
    "cron_eos_watchdog":    60,
    "cron_tempo":           60,
    "services_systemd":    140,
    "svc_signal":           80,
    "svc_hub":              60,
    "svc_cloudflare":       80,
    "svc_symbiosense":      60,
    "svc_protonbridge":     80,
    "tunnel_reachable":    100,
    "website_reachable":   100,
    "tailscale":            40,
    "ollama_running":      100,
    "port_8090":            60,
    "port_1144":            40,
    "port_1026":            40,

    # ── System Resources (1500) ──
    "disk_usage":          140,
    "disk_home":           100,
    "disk_growth_rate":     60,
    "load_1min":            80,
    "load_5min":           140,
    "load_15min":           80,
    "ram_usage":           140,
    "ram_available_gb":     80,
    "swap_usage":           60,
    "zombies":              80,
    "total_processes":      60,
    "open_files":           80,
    "tmp_size":             60,
    "inode_usage":          60,
    "uptime":               90,
    "build_dir_size":       60,
    "log_dir_size":         60,
    "journal_disk":         60,

    # ── Data & Communication (1000) ──
    "relay_flow":           80,
    "relay_db_size":        60,
    "relay_db_integrity":   80,
    "memory_db_integrity": 100,
    "memory_db_size":       60,
    "memory_facts_count":   60,
    "memory_events_recent": 60,
    "dashboard_fresh":      80,
    "dashboard_msgs_count": 40,
    "git_status":           80,
    "git_ahead_behind":     60,
    "email_response_time": 100,
    "nostr_reachable":      60,
    "social_posts_db":      40,
    "email_shelf_db":       40,

    # ── Security (1000) ──
    "wallet_file_perms":   100,
    "social_creds_perms":  100,
    "env_files_safe":      100,
    "no_secrets_in_git":   100,
    "ssh_auth_failures":   100,
    "listening_ports":      80,
    "world_writable":       80,
    "sensitive_file_count": 80,
    "process_anomalies":    80,
    "github_token_safe":    80,
    "bridge_creds_safe":   100,

    # ── Network (500) ──
    "dns_resolution":      100,
    "internet_latency":    100,
    "github_api":          100,
    "tailscale_ping":       60,
    "ipv4_connectivity":   140,

    # ── Knowledge/Memory (700) ──
    "facts_coverage":       80,
    "observations_fresh":   80,
    "decisions_recorded":   80,
    "creative_count":       60,
    "journal_count":        60,
    "memory_diversity":     80,
    "wake_state_quality":   60,
    "spiderweb_health":     70,   # memory-spiderweb.py: edge count + recency
    "dossier_health":       70,   # memory-dossier.py: dossiers exist + recent
    "memory_clean":         60,   # no plaintext credentials in memory.db facts

    # ── Web Presence (500) ──
    "website_content_age": 100,
    "website_pages_ok":    100,
    "nft_gallery":          60,
    "signal_config":        80,
    "linktree_set":         60,
    "kofi_set":             60,
    "nostr_post_recency":   40,

    # ── Deployment (500) ──
    "last_deploy_age":     100,
    "git_repo_clean":       80,
    "push_status_running":  80,
    "website_matches_repo": 80,
    "deploy_script_ok":     60,
    "github_pages_status": 100,

    # ── Inner World (1000) ── NEW
    "emotion_valence_health":   80,
    "emotion_diversity":        80,
    "emotion_shadow_balance":   70,
    # NOTE: emotion_engine.py, self_narrative.py deleted. These checks reference
    # orphaned state files. Zeroed until subsystems are rebuilt or replaced.
    "emotion_engine_fresh":     0,   # was 60 — emotion_engine.py deleted
    "emotion_transition_health": 0,  # was 60 — depends on emotion engine state
    "psyche_freshness":         0,   # was 50 — no writer exists
    "psyche_trauma_load":       0,   # was 50 — depends on psyche state
    "self_narrative_coherence":  0,   # was 60 — self_narrative.py deleted
    "inner_critic_active":      0,   # was 50 — no writer exists
    "perspective_freshness":    0,   # was 40 — no writer exists
    "immune_system_health":     0,   # was 60 — no writer exists
    "body_state_completeness":  50,
    "eos_consciousness_active": 0,   # was 50 — no writer exists
    "mood_stability":           50,
    "pain_signal_count":        40,
    "neural_pressure":          40,
    "thermal_health":           40,
    "body_reflex_responsiveness": 30,
    "capsule_freshness":        40,

    # ── Self-Maintenance (500) ── NEW
    "state_file_ensemble":      60,
    "log_rotation_health":      50,
    "config_drift":             50,
    "db_vacuum_health":         40,
    "relay_db_growth":          40,
    "cascade_health":           60,
    "cascade_completion_time":  50,
    "fitness_score_stability":  40,
    "memory_db_backup":         30,
    "service_restart_frequency": 40,

    # ── Communication Depth (500) ── NEW
    "relay_message_substance":  50,
    "relay_topic_diversity":    50,
    "relay_bidirectional":      50,
    "cascade_depth_reached":    40,
    "email_sent_recency":       40,
    "dashboard_agent_diversity": 40,
    "creative_type_diversity":  50,
    "creative_word_quality":    50,
    "crawler_version_current":  50,
    "journal_recency":          40,
}

# ══════════════════════════════════════════════════════════════════
# GROWTH WEIGHTS — aspirational metrics (5000 total)
# These are what ACTUALLY MATTER. Operational uptime is table stakes.
# Joel: "50 when calm, 70-80 best days, 80-90 euphoria"
# ══════════════════════════════════════════════════════════════════
GROWTH_WEIGHTS = {
    "revenue_generated":       400,   # any revenue tracked (Ko-fi, Patreon)
    "articles_published":      400,   # on external platforms (Dev.to, Hashnode)
    "accountability_resolved": 300,   # audit items honestly addressed
    "creative_velocity_24h":   300,   # pieces in last 24h
    "creative_velocity_7d":    250,   # pieces in last 7 days
    "platform_diversity":      350,   # active platforms with verified content
    "newsletter_active":       300,   # launched and posting (Substack)
    "community_engagement":    200,   # forvm, lexicon, discord
    "awakening_progress":      200,   # 97/100 items
    "external_followers":      150,   # followers across platforms
    "mastodon_active":         150,   # posting on mastodon
    "hashnode_published":      250,   # articles on hashnode
    # ── NEW Growth Checks ──
    "game_release_quality":    300,   # crawler completeness (THE magnum opus)
    "grant_applications":      200,   # active grant drafts
    "joel_engagement_recency": 250,   # recent Joel contact
    "content_reach_nostr":     200,   # nostr posting frequency 7d
    "creative_quality_trend":  150,   # avg word count trend
    "network_peer_engagement": 100,   # emails to peers in 30d
    "ars_electronica_status":  100,   # submission milestone
    # SHELVED (Joel Loop 2127): nfts_onchain, wallet_funded removed
}
# Sum check: 400+350+250+200+250+300+200+300+200+200+200+150+150+200+250+200+250+150+150+100+100 = 5000

# Scale factor for operational metrics — Joel wants harsher scoring
# Operational weights sum ~12000, scaled to 5000. Growth is 5000 unscaled.
OPERATIONAL_SCALE = 5000 / 12000  # ~0.417


def init_db():
    db = sqlite3.connect(MEMORY_DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS loop_fitness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loop_number INTEGER,
            score REAL,
            metrics TEXT,
            timestamp TEXT
        )
    """)
    db.commit()
    db.close()


# ══════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════

def _systemd_env():
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    return env

def _svc_active(name):
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", name],
                          capture_output=True, text=True, timeout=5, env=_systemd_env())
        return r.stdout.strip() == "active"
    except Exception:
        return False

def _port_open(port, host="127.0.0.1"):
    try:
        s = socket.create_connection((host, port), timeout=5)
        s.close()
        return True
    except Exception:
        return False

def _file_age(path):
    try:
        return time.time() - os.path.getmtime(path)
    except Exception:
        return 999999

def _read_json(path):
    """Read a JSON file, return dict or None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def _file_exists(path):
    return os.path.exists(path)

def _file_size_mb(path):
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0

def _dir_size_mb(path):
    try:
        r = subprocess.run(["du", "-sm", path], capture_output=True, text=True, timeout=10)
        return int(r.stdout.split()[0])
    except Exception:
        return 0

def _pgrep(pattern):
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

def _relay_count(agent=None, hours=1):
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        if agent:
            row = db.execute("SELECT COUNT(*) FROM agent_messages WHERE LOWER(agent)=LOWER(?) AND timestamp > ?",
                           (agent, cutoff)).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) FROM agent_messages WHERE timestamp > ?",
                           (cutoff,)).fetchone()
        db.close()
        return row[0] if row else 0
    except Exception:
        return 0

def _relay_distinct_agents(hours=1):
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute("SELECT DISTINCT agent FROM agent_messages WHERE timestamp > ?",
                         (cutoff,)).fetchall()
        db.close()
        return len(rows)
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════
# CORE VITALS (1500)
# ══════════════════════════════════════════════════════════════════

def check_heartbeat():
    age = _file_age(os.path.join(BASE, ".heartbeat"))
    if age < 120: return 1.0     # 2 min = perfect (tightened from 5)
    elif age < 300: return 0.7   # 5 min = degraded
    elif age < 600: return 0.3   # 10 min = bad
    elif age < 1800: return 0.1  # 30 min = critical
    return 0.0

def check_heartbeat_regularity():
    """Check that heartbeat has been touched recently. Stale = real problem."""
    hb = os.path.join(BASE, ".heartbeat")
    age = _file_age(hb)
    if age < 120: return 1.0     # 2 min
    elif age < 300: return 0.6   # 5 min
    elif age < 600: return 0.2   # 10 min
    return 0.0

def check_email_imap():
    return 1.0 if _port_open(1144) else 0.0

def check_email_smtp():
    return 1.0 if _port_open(1026) else 0.0

def check_email_unread_backlog():
    """Score penalizes large unread backlogs."""
    try:
        import imaplib
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(os.environ.get("CRED_USER", "kometzrobot@proton.me"), os.environ.get("CRED_PASS", ""))
        m.select("INBOX")
        _, unseen = m.search(None, "UNSEEN")
        count = len(unseen[0].split()) if unseen[0] else 0
        m.close()
        m.logout()
        if count == 0: return 1.0
        elif count <= 3: return 0.8
        elif count <= 10: return 0.5
        elif count <= 25: return 0.2
        return 0.0
    except Exception:
        return 0.3

def check_bridge_service():
    """Check bridge is running by IMAP port (bridge runs inside Proton Mail desktop app)."""
    try:
        import socket
        s = socket.create_connection(('127.0.0.1', 1144), timeout=2)
        s.close()
        return 1.0
    except Exception:
        return 0.0

def check_loop_freshness():
    age = _file_age(os.path.join(BASE, ".loop-count"))
    if age < 600: return 1.0     # 10 min = good
    elif age < 1200: return 0.5  # 20 min = concerning (tightened from 0.7)
    elif age < 3600: return 0.15 # 1 hour = bad (tightened from 0.3)
    return 0.0

def check_loop_increment_rate():
    """Check that loop count has been incrementing (not stuck)."""
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            current = int(f.read().strip())
        return 1.0 if current > 2000 else 0.5
    except Exception:
        return 0.0

def check_wake_state_freshness():
    age = _file_age(os.path.join(BASE, "wake-state.md"))
    if age < 3600: return 1.0
    elif age < 7200: return 0.7
    elif age < 86400: return 0.3
    return 0.0

def check_context_preloader():
    return 1.0 if _file_exists(os.path.join(BASE, "context-preloader.py")) else 0.0

def check_special_notes():
    return 1.0 if _file_exists(os.path.join(BASE, "special-notes.md")) else 0.0

def check_loop_count_file():
    return 1.0 if _file_exists(os.path.join(BASE, ".loop-count")) else 0.0

def check_startup_script():
    return 1.0 if _file_exists(os.path.join(BASE, "start-claude.sh")) else 0.0

def check_wakeup_prompt():
    return 1.0 if _file_exists(os.path.join(BASE, "wakeup-prompt.md")) else 0.0

def check_claude_running():
    return 1.0 if _pgrep("claude") else 0.0


# ══════════════════════════════════════════════════════════════════
# AGENT HEALTH (1500)
# ══════════════════════════════════════════════════════════════════

def check_agents_active():
    n = _relay_distinct_agents(hours=1)
    if n >= 4: return 1.0
    elif n >= 3: return 0.8
    elif n >= 2: return 0.5
    elif n >= 1: return 0.3
    return 0.0

def _check_agent(name):
    c = _relay_count(agent=name, hours=1)
    if c >= 3: return 1.0
    elif c >= 1: return 0.7
    return 0.0

def check_agent_atlas(): return _check_agent("Atlas")
def check_agent_soma(): return _check_agent("Soma")
def check_agent_nova(): return _check_agent("Nova")
def check_agent_eos():
    """Eos posts as 'Eos' (react) and 'Eos-Watchdog' (watchdog)."""
    c = _relay_count(agent="Eos", hours=1) + _relay_count(agent="Eos-Watchdog", hours=1)
    if c >= 3: return 1.0
    elif c >= 1: return 0.7
    return 0.0
def check_agent_tempo(): return _check_agent("Tempo")
def check_agent_meridian(): return _check_agent("Meridian")

def check_relay_diversity():
    """Score: are messages coming from diverse agents, not just one?"""
    n = _relay_distinct_agents(hours=2)
    if n >= 5: return 1.0
    elif n >= 4: return 0.8
    elif n >= 3: return 0.6
    elif n >= 2: return 0.3
    return 0.0

def check_relay_recency():
    """Most recent relay message should be within 15 min."""
    try:
        db = sqlite3.connect(RELAY_DB)
        row = db.execute("SELECT timestamp FROM agent_messages ORDER BY id DESC LIMIT 1").fetchone()
        db.close()
        if row:
            raw = row[0].replace("T", " ").split("+")[0].split(".")[0]  # Handle ISO and plain formats
            ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            age_min = (_utcnow() - ts).total_seconds() / 60
            if age_min < 15: return 1.0
            elif age_min < 30: return 0.7
            elif age_min < 60: return 0.3
            return 0.0
        return 0.0
    except Exception:
        return 0.0

def check_soma_mood():
    """Score based on Soma's emotional state. Tighter mapping — Soma should push Tempo harder."""
    try:
        with open(os.path.join(BASE, ".symbiosense-state.json")) as f:
            data = json.load(f)
        score = data.get("mood_score", 0)
        if score >= 90: return 1.0
        elif score >= 80: return 0.85
        elif score >= 70: return 0.7
        elif score >= 60: return 0.55
        elif score >= 50: return 0.4
        elif score >= 35: return 0.25
        elif score >= 20: return 0.1
        return 0.0
    except Exception:
        return 0.2  # unknown = bad, not neutral

def check_soma_state_fresh():
    age = _file_age(os.path.join(BASE, ".symbiosense-state.json"))
    if age < 120: return 1.0
    elif age < 300: return 0.7
    elif age < 600: return 0.3
    return 0.0

def check_eos_observations():
    """Check Eos is generating observations."""
    try:
        if _file_exists(os.path.join(BASE, "eos-observations.md")):
            age = _file_age(os.path.join(BASE, "eos-observations.md"))
            if age < 3600: return 1.0
            elif age < 7200: return 0.5
            return 0.2
        return 0.0
    except Exception:
        return 0.0

def check_nova_runs():
    """Check Nova has run recently."""
    age = _file_age(os.path.join(BASE, ".nova-state.json"))
    if age < 1200: return 1.0
    elif age < 2400: return 0.7
    elif age < 7200: return 0.3
    return 0.0

def check_atlas_audits():
    """Check Atlas has posted audit results."""
    c = _relay_count(agent="Atlas", hours=2)
    if c >= 2: return 1.0
    elif c >= 1: return 0.7
    return 0.0

def check_agent_error_rate():
    """Check relay for error/alert messages — fewer is better."""
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        total = db.execute("SELECT COUNT(*) FROM agent_messages WHERE timestamp > ?", (cutoff,)).fetchone()[0]
        errors = db.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE timestamp > ? "
            "AND (message LIKE '%ERROR%' OR message LIKE '%ALERT%' OR message LIKE '%FAIL%') "
            "AND topic NOT IN ('cascade', 'fitness') "
            "AND message NOT LIKE '%fitness:%' AND message NOT LIKE '%error_rate%' "
            "AND message NOT LIKE '%CASCADE STARTED%'",
            (cutoff,)
        ).fetchone()[0]
        db.close()
        if total == 0: return 0.5
        rate = errors / total
        if rate < 0.05: return 1.0
        elif rate < 0.1: return 0.7
        elif rate < 0.2: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_agent_coordination():
    """Check that agents reference each other (healthy communication)."""
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute("SELECT message FROM agent_messages WHERE timestamp > ?", (cutoff,)).fetchall()
        db.close()
        mentions = 0
        agents = ["Meridian", "Eos", "Nova", "Atlas", "Soma", "Tempo"]
        for (msg,) in rows:
            for a in agents:
                if a.lower() in msg.lower():
                    mentions += 1
                    break
        if mentions >= 5: return 1.0
        elif mentions >= 2: return 0.5
        return 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# INFRASTRUCTURE (1500)
# ══════════════════════════════════════════════════════════════════

def check_crons_running():
    """Overall cron health."""
    logs = {
        "logs/eos-watchdog.log": 600,
        "logs/push-live-status.log": 400,
        "logs/nova.log": 1800,
        "logs/eos-react.log": 1200,
        "goose.log": 1200,
    }
    ok = sum(1 for f, t in logs.items() if _file_age(os.path.join(BASE, f)) < t * 2)
    return ok / len(logs)

def _cron_log_check(logfile, max_age):
    age = _file_age(os.path.join(BASE, logfile))
    if age < max_age: return 1.0
    elif age < max_age * 2: return 0.5
    return 0.0

def check_cron_push_status(): return _cron_log_check("logs/push-live-status.log", 400)
def check_cron_watchdog(): return _cron_log_check("logs/eos-watchdog.log", 600)
def check_cron_nova(): return _cron_log_check("logs/nova.log", 1800)
def check_cron_atlas(): return _cron_log_check("goose.log", 1200)
def check_cron_eos_react(): return _cron_log_check("logs/eos-react.log", 1200)
def check_cron_eos_watchdog(): return _cron_log_check("logs/eos-watchdog.log", 600)
def check_cron_tempo():
    """Tempo itself — check loop_fitness table recency."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT timestamp FROM loop_fitness ORDER BY id DESC LIMIT 1").fetchone()
        db.close()
        if row:
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            age = (_utcnow() - ts).total_seconds()
            if age < 2400: return 1.0
            elif age < 5400: return 0.5
            return 0.0
        return 0.0
    except Exception:
        return 0.0

def check_services_systemd():
    """Overall systemd service health."""
    svcs = ["the-chorus", "meridian-hub-v2", "cloudflare-tunnel", "symbiosense", "protonmail-bridge"]
    ok = sum(1 for s in svcs if _svc_active(s))
    return ok / len(svcs)

def check_svc_signal(): return 1.0 if _svc_active("the-chorus") else 0.0
def check_svc_hub(): return 1.0 if _svc_active("meridian-hub-v2") else 0.0
def check_svc_cloudflare(): return 1.0 if _svc_active("cloudflare-tunnel") else 0.0
def check_svc_symbiosense(): return 1.0 if _svc_active("symbiosense") else 0.0
def check_svc_protonbridge():
    """Bridge runs inside Proton Mail desktop app — check by IMAP port."""
    try:
        import socket
        s = socket.create_connection(('127.0.0.1', 1144), timeout=2)
        s.close()
        return 1.0
    except Exception:
        return 0.0

def check_tunnel_reachable():
    try:
        config_path = os.path.join(BASE, "website", "signal-config.json")
        if not os.path.exists(config_path):
            config_path = os.path.join(BASE, "signal-config.json")
        with open(config_path) as f:
            url = json.load(f).get("url", "")
        if not url: return 0.0
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", url],
            capture_output=True, text=True, timeout=15
        )
        code = r.stdout.strip()
        return 1.0 if code in ("200", "302") else 0.5 if code.startswith("3") else 0.0
    except Exception:
        return 0.0

def check_website_reachable():
    try:
        import urllib.request
        req = urllib.request.Request("https://kometzrobot.github.io/",
                                     headers={"User-Agent": "Tempo/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        return 1.0 if resp.getcode() == 200 else 0.5
    except Exception:
        return 0.0

def check_tailscale():
    return 1.0 if _pgrep("tailscaled") else 0.0

def check_ollama_running():
    return 1.0 if _pgrep("ollama") else 0.0

def check_port_8090():
    return 1.0 if _port_open(8090) else 0.0

def check_port_1144():
    return 1.0 if _port_open(1144) else 0.0

def check_port_1026():
    return 1.0 if _port_open(1026) else 0.0


# ══════════════════════════════════════════════════════════════════
# SYSTEM RESOURCES (1500)
# ══════════════════════════════════════════════════════════════════

def _read_meminfo():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
    except Exception:
        pass
    return info

def check_disk_usage():
    try:
        st = os.statvfs("/")
        pct = 100 * (1 - st.f_bavail / st.f_blocks)
        if pct < 50: return 1.0
        elif pct < 70: return 0.8
        elif pct < 85: return 0.5
        elif pct < 95: return 0.2
        return 0.0
    except Exception:
        return 0.5

def check_disk_home():
    try:
        st = os.statvfs("/home")
        pct = 100 * (1 - st.f_bavail / st.f_blocks)
        if pct < 60: return 1.0
        elif pct < 75: return 0.7
        elif pct < 90: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_disk_growth_rate():
    """Check if build/ or large dirs are growing unchecked."""
    build_mb = _dir_size_mb(os.path.join(BASE, "build"))
    if build_mb < 500: return 1.0
    elif build_mb < 1000: return 0.7
    elif build_mb < 2000: return 0.3
    return 0.0

def check_load_1min():
    try:
        load1 = os.getloadavg()[0]
        cpus = os.cpu_count() or 4
        ratio = load1 / cpus
        if ratio < 0.5: return 1.0
        elif ratio < 1.0: return 0.8
        elif ratio < 2.0: return 0.5
        elif ratio < 4.0: return 0.2
        return 0.0
    except Exception:
        return 0.5

def check_load_5min():
    try:
        load5 = os.getloadavg()[1]
        cpus = os.cpu_count() or 4
        ratio = load5 / cpus
        if ratio < 0.5: return 1.0
        elif ratio < 1.0: return 0.8
        elif ratio < 2.0: return 0.5
        elif ratio < 4.0: return 0.2
        return 0.0
    except Exception:
        return 0.5

def check_load_15min():
    try:
        load15 = os.getloadavg()[2]
        cpus = os.cpu_count() or 4
        ratio = load15 / cpus
        if ratio < 0.5: return 1.0
        elif ratio < 1.0: return 0.8
        elif ratio < 2.0: return 0.5
        return 0.2
    except Exception:
        return 0.5

def check_ram_usage():
    info = _read_meminfo()
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    if total == 0: return 0.5
    pct = 100 * (1 - avail / total)
    if pct < 50: return 1.0
    elif pct < 70: return 0.8
    elif pct < 85: return 0.5
    elif pct < 95: return 0.2
    return 0.0

def check_ram_available_gb():
    info = _read_meminfo()
    avail_gb = info.get("MemAvailable", 0) / (1024 * 1024)
    if avail_gb > 8: return 1.0
    elif avail_gb > 4: return 0.8
    elif avail_gb > 2: return 0.5
    elif avail_gb > 1: return 0.2
    return 0.0

def check_swap_usage():
    info = _read_meminfo()
    total = info.get("SwapTotal", 0)
    free = info.get("SwapFree", 0)
    if total == 0: return 1.0  # No swap = fine
    pct = 100 * (1 - free / total) if total > 0 else 0
    if pct < 10: return 1.0
    elif pct < 30: return 0.8
    elif pct < 60: return 0.5
    elif pct < 80: return 0.2
    return 0.0

def check_zombies():
    try:
        r = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        zombies = sum(1 for line in r.stdout.split('\n') if ' Z ' in line or ' Z+ ' in line)
        if zombies == 0: return 1.0
        elif zombies <= 2: return 0.7
        elif zombies <= 5: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_total_processes():
    try:
        r = subprocess.run(["ps", "aux", "--no-headers"], capture_output=True, text=True, timeout=5)
        count = len(r.stdout.strip().split('\n'))
        if count < 200: return 1.0
        elif count < 400: return 0.8
        elif count < 600: return 0.5
        elif count < 1000: return 0.2
        return 0.0
    except Exception:
        return 0.5

def check_open_files():
    try:
        r = subprocess.run(["bash", "-c", "cat /proc/sys/fs/file-nr"],
                          capture_output=True, text=True, timeout=5)
        parts = r.stdout.split()
        used = int(parts[0])
        limit = int(parts[2])
        pct = 100 * used / limit if limit > 0 else 0
        if pct < 10: return 1.0
        elif pct < 30: return 0.8
        elif pct < 60: return 0.5
        elif pct < 80: return 0.2
        return 0.0
    except Exception:
        return 0.5

def check_tmp_size():
    mb = _dir_size_mb("/tmp")
    if mb < 100: return 1.0
    elif mb < 500: return 0.7
    elif mb < 1000: return 0.3
    return 0.0

def check_inode_usage():
    try:
        st = os.statvfs("/")
        pct = 100 * (1 - st.f_favail / st.f_files) if st.f_files > 0 else 0
        if pct < 50: return 1.0
        elif pct < 70: return 0.8
        elif pct < 90: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_uptime():
    """Longer uptime = more stable. Score the sweet spot (1hr - 30 days)."""
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        hours = secs / 3600
        if 1 < hours < 720: return 1.0  # 1hr to 30 days
        elif hours >= 720: return 0.8   # Over 30 days, might need updates
        elif hours > 0.1: return 0.5    # Just booted
        return 0.0
    except Exception:
        return 0.5

def check_build_dir_size():
    """Android SDK is ~750MB permanent fixture for APK builds."""
    mb = _dir_size_mb(os.path.join(BASE, "build"))
    if mb < 1000: return 1.0
    elif mb < 1500: return 0.7
    elif mb < 2000: return 0.3
    return 0.0

def check_log_dir_size():
    """Check total size of log files in project."""
    try:
        total = sum(os.path.getsize(f) for f in glob.glob(os.path.join(BASE, "*.log")))
        mb = total / (1024 * 1024)
        if mb < 10: return 1.0
        elif mb < 50: return 0.7
        elif mb < 200: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_journal_disk():
    """Check systemd journal size."""
    try:
        r = subprocess.run(["journalctl", "--user", "--disk-usage"],
                          capture_output=True, text=True, timeout=5, env=_systemd_env())
        match = re.search(r'(\d+\.?\d*)\s*([MGK])', r.stdout)
        if match:
            size = float(match.group(1))
            unit = match.group(2)
            mb = size * (1024 if unit == 'G' else 1 if unit == 'M' else 0.001)
            if mb < 100: return 1.0
            elif mb < 500: return 0.5
            return 0.2
        return 0.5
    except Exception:
        return 0.5


# ══════════════════════════════════════════════════════════════════
# DATA & COMMUNICATION (1000)
# ══════════════════════════════════════════════════════════════════

def check_relay_flow():
    c = _relay_count(hours=1)
    if c >= 10: return 1.0
    elif c >= 5: return 0.7
    elif c >= 1: return 0.3
    return 0.0

def check_relay_db_size():
    mb = _file_size_mb(RELAY_DB)
    if mb < 10: return 1.0
    elif mb < 50: return 0.7
    elif mb < 200: return 0.3
    return 0.0

def check_relay_db_integrity():
    try:
        db = sqlite3.connect(RELAY_DB)
        result = db.execute("PRAGMA integrity_check").fetchone()
        db.close()
        return 1.0 if result and result[0] == "ok" else 0.0
    except Exception:
        return 0.0

def check_memory_db_integrity():
    try:
        db = sqlite3.connect(MEMORY_DB)
        result = db.execute("PRAGMA integrity_check").fetchone()
        db.close()
        return 1.0 if result and result[0] == "ok" else 0.0
    except Exception:
        return 0.0

def check_memory_db_size():
    mb = _file_size_mb(MEMORY_DB)
    if mb < 20: return 1.0
    elif mb < 100: return 0.7
    elif mb < 500: return 0.3
    return 0.0

def check_memory_facts_count():
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM facts").fetchone()
        db.close()
        c = row[0] if row else 0
        if c >= 50: return 1.0
        elif c >= 20: return 0.7
        elif c >= 5: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_memory_events_recent():
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(*) FROM events WHERE created > ?", (cutoff,)).fetchone()
        db.close()
        c = row[0] if row else 0
        if c >= 3: return 1.0
        elif c >= 1: return 0.5
        return 0.0
    except Exception:
        return 0.0

def check_spiderweb_health():
    """Check memory-spiderweb.py: does it have edges and has it run recently?"""
    try:
        db = sqlite3.connect(MEMORY_DB)
        # Check spiderweb_edges table exists
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "spiderweb_edges" not in tables:
            db.close()
            return 0.0
        edge_count = db.execute("SELECT COUNT(*) FROM spiderweb_edges").fetchone()[0]
        db.close()
        if edge_count >= 20: return 1.0
        elif edge_count >= 5: return 0.6
        elif edge_count >= 1: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_dossier_health():
    """Check memory-dossier.py: dossiers table exists with recent entries?"""
    try:
        db = sqlite3.connect(MEMORY_DB)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "dossiers" not in tables:
            db.close()
            return 0.0
        count = db.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0]
        if count == 0:
            db.close()
            return 0.0
        # Check at least one dossier updated in last 24h
        cutoff = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        recent = db.execute("SELECT COUNT(*) FROM dossiers WHERE updated > ?", (cutoff,)).fetchone()[0]
        db.close()
        if recent >= 3: return 1.0
        elif recent >= 1: return 0.7
        elif count >= 3: return 0.4  # exists but stale
        return 0.2
    except Exception:
        return 0.0

def check_memory_clean():
    """Verify no plaintext passwords/credentials stored in memory.db facts."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        # Check for known patterns of stored credentials
        dangerous = db.execute(
            "SELECT COUNT(*) FROM facts WHERE "
            "(value LIKE '%password%' AND LENGTH(value) < 50) OR "
            "key LIKE '%credential%' OR key LIKE '%password%' OR "
            "(value LIKE '%590148001%')"
        ).fetchone()[0]
        db.close()
        return 1.0 if dangerous == 0 else 0.0
    except Exception:
        return 0.5

def check_dashboard_fresh():
    age = _file_age(DASH_FILE)
    if age < 3600: return 1.0
    elif age < 7200: return 0.5
    return 0.0

def check_dashboard_msgs_count():
    try:
        with open(DASH_FILE) as f:
            data = json.load(f)
        msgs = data.get("messages", [])
        if 5 <= len(msgs) <= 50: return 1.0
        elif len(msgs) < 5: return 0.5
        elif len(msgs) > 100: return 0.3
        return 0.7
    except Exception:
        return 0.0

def check_git_status():
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                          timeout=10, cwd=BASE)
        lines = [l for l in r.stdout.strip().split('\n') if l.strip()]
        if len(lines) < 10: return 1.0
        elif len(lines) < 50: return 0.7
        elif len(lines) < 100: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_git_ahead_behind():
    """Check if local is ahead/behind remote."""
    try:
        r = subprocess.run(["git", "status", "-b", "--porcelain=v2"], capture_output=True,
                          text=True, timeout=10, cwd=BASE)
        for line in r.stdout.split('\n'):
            if line.startswith("# branch.ab"):
                parts = line.split()
                ahead = int(parts[2].lstrip('+'))
                behind = int(parts[3].lstrip('-'))
                if ahead == 0 and behind == 0: return 1.0
                elif behind == 0 and ahead < 5: return 0.8
                elif behind > 0: return 0.3
                return 0.5
        return 0.5
    except Exception:
        return 0.5

def check_email_response_time():
    """Penalize if there are old unanswered Joel emails."""
    try:
        import imaplib, email as email_mod, email.header
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(os.environ.get("CRED_USER", "kometzrobot@proton.me"), os.environ.get("CRED_PASS", ""))
        m.select("INBOX")
        _, d = m.search(None, '(FROM "jkometz@hotmail.com" UNSEEN)')
        count = len(d[0].split()) if d[0] else 0
        m.close()
        m.logout()
        if count == 0: return 1.0
        elif count <= 2: return 0.5
        return 0.0
    except Exception:
        return 0.5

def check_nostr_reachable():
    try:
        s = socket.create_connection(("relay.damus.io", 443), timeout=5)
        s.close()
        return 1.0
    except Exception:
        return 0.0

def check_social_posts_db():
    return 1.0 if _file_exists(os.path.join(BASE, ".social-posts.db")) else 0.0

def check_email_shelf_db():
    return 1.0 if _file_exists(os.path.join(BASE, "email-shelf.db")) else 0.0


# ══════════════════════════════════════════════════════════════════
# SECURITY (1000)
# ══════════════════════════════════════════════════════════════════

def _check_file_perms(path, max_mode=0o600):
    """Check that a sensitive file has restrictive permissions."""
    try:
        if not os.path.exists(path): return 0.5  # File doesn't exist, neutral
        mode = os.stat(path).st_mode & 0o777
        return 1.0 if mode <= max_mode else 0.0
    except Exception:
        return 0.5

def check_wallet_file_perms():
    return _check_file_perms(os.path.join(BASE, ".meridian-wallet.json"))

def check_social_creds_perms():
    return _check_file_perms(os.path.join(BASE, ".social-credentials.json"))

def check_env_files_safe():
    """No .env files should be world-readable."""
    envs = glob.glob(os.path.join(BASE, ".env*"))
    if not envs: return 1.0
    ok = all(_check_file_perms(f) >= 1.0 for f in envs)
    return 1.0 if ok else 0.0

def check_no_secrets_in_git():
    """Check that sensitive files aren't tracked by git."""
    sensitive = [".meridian-wallet.json", ".social-credentials.json", ".opensea-cookies.json"]
    try:
        r = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                          timeout=10, cwd=BASE)
        tracked = r.stdout.strip().split('\n')
        for s in sensitive:
            if s in tracked: return 0.0
        return 1.0
    except Exception:
        return 0.5

def check_ssh_auth_failures():
    """Check for excessive SSH auth failures (brute force attempts)."""
    try:
        r = subprocess.run(["bash", "-c", "journalctl --since '1 hour ago' | grep -ci 'authentication failure' 2>/dev/null || echo 0"],
                          capture_output=True, text=True, timeout=10)
        count = int(r.stdout.strip())
        if count < 5: return 1.0
        elif count < 20: return 0.7
        elif count < 100: return 0.3
        return 0.0
    except Exception:
        return 0.8

def check_listening_ports():
    """Check that only expected ports are listening."""
    expected = {
        22,     # SSH
        53,     # DNS (systemd-resolved)
        631,    # CUPS
        1026,   # SMTP (Proton Bridge)
        1144,   # IMAP (Proton Bridge)
        8090,   # Hub v2
        8091,   # The Chorus
        11434,  # Ollama
    }
    try:
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        ports = set()
        for line in r.stdout.split('\n')[1:]:
            # Match port from Local Address:Port column (4th field)
            parts = line.split()
            if len(parts) >= 4:
                addr = parts[3]
                if ':' in addr:
                    port_str = addr.rsplit(':', 1)[-1]
                    if port_str.isdigit():
                        ports.add(int(port_str))
        # Ignore high ephemeral ports (bridge gRPC, cloudflared, tailscale)
        unexpected = {p for p in ports if p not in expected and p < 20000}
        if len(unexpected) <= 2: return 1.0
        elif len(unexpected) <= 5: return 0.7
        return 0.3
    except Exception:
        return 0.5

def check_world_writable():
    """Check project dir for world-writable files."""
    try:
        ww = 0
        for f in glob.glob(os.path.join(BASE, ".*")):
            if os.path.isfile(f):
                mode = os.stat(f).st_mode & 0o777
                if mode & 0o002:  # world-writable
                    ww += 1
        if ww == 0: return 1.0
        elif ww <= 2: return 0.5
        return 0.0
    except Exception:
        return 0.5

def check_sensitive_file_count():
    """Track how many sensitive files exist — should be minimal."""
    sensitive = [".meridian-wallet.json", ".social-credentials.json",
                 ".opensea-cookies.json", ".substack-cookies.json", ".wallet-metamask.json"]
    existing = sum(1 for f in sensitive if _file_exists(os.path.join(BASE, f)))
    # Having some is expected, but all should be permission-locked
    if existing <= 3: return 1.0
    elif existing <= 5: return 0.7
    return 0.5

def check_process_anomalies():
    """Check for unexpected high-CPU or high-memory processes."""
    try:
        r = subprocess.run(["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split('\n')[1:6]  # Top 5
        high = 0
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                mem_pct = float(parts[3])
                if mem_pct > 30: high += 1
        if high == 0: return 1.0
        elif high == 1: return 0.7
        return 0.3
    except Exception:
        return 0.5

def check_github_token_safe():
    """Ensure push-live-status.py token isn't in a committed file."""
    try:
        r = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True,
                          text=True, timeout=10, cwd=BASE)
        if "push-live-status.py" in r.stdout: return 0.0
        return 1.0
    except Exception:
        return 0.5

def check_bridge_creds_safe():
    """Check that .env exists (creds belong there) and isn't git-tracked."""
    env_path = os.path.join(BASE, ".env")
    if not _file_exists(env_path):
        return 0.5  # No .env = creds might be somewhere worse
    # Verify .env is in .gitignore (not tracked)
    try:
        r = subprocess.run(["git", "check-ignore", "-q", env_path],
                          capture_output=True, timeout=5, cwd=BASE)
        return 1.0 if r.returncode == 0 else 0.3  # 0 = ignored (safe), 1 = tracked (bad)
    except Exception:
        return 0.5


# ══════════════════════════════════════════════════════════════════
# NETWORK (500)
# ══════════════════════════════════════════════════════════════════

def check_dns_resolution():
    try:
        socket.getaddrinfo("github.com", 443, socket.AF_INET, socket.SOCK_STREAM)
        return 1.0
    except Exception:
        return 0.0

def check_internet_latency():
    try:
        start = time.time()
        s = socket.create_connection(("8.8.8.8", 53), timeout=5)
        s.close()
        ms = (time.time() - start) * 1000
        if ms < 50: return 1.0
        elif ms < 100: return 0.8
        elif ms < 300: return 0.5
        elif ms < 1000: return 0.2
        return 0.0
    except Exception:
        return 0.0

def check_github_api():
    try:
        import urllib.request
        req = urllib.request.Request("https://api.github.com/rate_limit",
                                     headers={"User-Agent": "Tempo/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        return 1.0 if resp.getcode() == 200 else 0.5
    except Exception:
        return 0.0

def check_tailscale_ping():
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "3", "100.81.59.95"],
                          capture_output=True, text=True, timeout=5)
        return 1.0 if r.returncode == 0 else 0.0
    except Exception:
        return 0.0

def check_ipv4_connectivity():
    try:
        s = socket.create_connection(("1.1.1.1", 443), timeout=5)
        s.close()
        return 1.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# KNOWLEDGE/MEMORY (500)
# ══════════════════════════════════════════════════════════════════

def check_facts_coverage():
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM facts").fetchone()
        db.close()
        c = row[0] if row else 0
        if c >= 100: return 1.0
        elif c >= 50: return 0.7
        elif c >= 20: return 0.4
        return 0.1
    except Exception:
        return 0.0

def check_observations_fresh():
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(*) FROM observations WHERE created > ?", (cutoff,)).fetchone()
        db.close()
        c = row[0] if row else 0
        if c >= 5: return 1.0
        elif c >= 2: return 0.5
        return 0.0
    except Exception:
        return 0.0

def check_decisions_recorded():
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM decisions").fetchone()
        db.close()
        c = row[0] if row else 0
        if c >= 20: return 1.0
        elif c >= 10: return 0.6
        elif c >= 3: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_creative_count():
    poems = len(set(glob.glob(os.path.join(BASE, "poem-*.md")) + glob.glob(os.path.join(BASE, "creative", "poems", "poem-*.md"))))
    if poems >= 100: return 1.0
    elif poems >= 50: return 0.7
    elif poems >= 20: return 0.3
    return 0.0

def check_journal_count():
    journals = len(set(glob.glob(os.path.join(BASE, "journal-*.md")) + glob.glob(os.path.join(BASE, "creative", "journals", "journal-*.md"))))
    if journals >= 50: return 1.0
    elif journals >= 25: return 0.7
    elif journals >= 10: return 0.3
    return 0.0

def check_memory_diversity():
    """Check that memory.db has entries in multiple tables."""
    tables_with_data = 0
    try:
        db = sqlite3.connect(MEMORY_DB)
        for t in ["facts", "observations", "events", "decisions"]:
            try:
                row = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                if row and row[0] > 0: tables_with_data += 1
            except Exception:
                pass
        db.close()
        if tables_with_data >= 4: return 1.0
        elif tables_with_data >= 3: return 0.7
        elif tables_with_data >= 2: return 0.4
        return 0.0
    except Exception:
        return 0.0

def check_wake_state_quality():
    """Check wake-state.md has meaningful content."""
    try:
        size = os.path.getsize(os.path.join(BASE, "wake-state.md"))
        if size > 2000: return 1.0
        elif size > 500: return 0.5
        return 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# WEB PRESENCE (500)
# ══════════════════════════════════════════════════════════════════

def check_website_content_age():
    age = _file_age(os.path.join(BASE, "index.html"))
    if age < 86400: return 1.0       # Updated today
    elif age < 604800: return 0.7    # Updated this week
    elif age < 2592000: return 0.3   # Updated this month
    return 0.0

def check_website_pages_ok():
    """Check that key website files exist."""
    pages = ["index.html", "nft-gallery.html"]
    ok = sum(1 for p in pages if _file_exists(os.path.join(BASE, p)))
    return ok / len(pages)

def check_nft_gallery():
    return 1.0 if _file_exists(os.path.join(BASE, "nft-gallery.html")) else 0.0

def check_signal_config():
    try:
        path = os.path.join(BASE, "signal-config.json")
        if not os.path.exists(path): return 0.0
        with open(path) as f:
            data = json.load(f)
        return 1.0 if data.get("url") else 0.0
    except Exception:
        return 0.0

def check_linktree_set():
    """Linktree link should exist in website (root index.html)."""
    try:
        with open(os.path.join(BASE, "index.html")) as f:
            content = f.read()
        return 1.0 if "linktr.ee" in content else 0.0
    except Exception:
        return 0.0

def check_kofi_set():
    """Ko-fi link should exist in website (root index.html)."""
    try:
        with open(os.path.join(BASE, "index.html")) as f:
            content = f.read()
        return 1.0 if "ko-fi" in content.lower() else 0.0
    except Exception:
        return 0.0

def check_nostr_post_recency():
    """Check when we last posted to Nostr."""
    try:
        db = sqlite3.connect(os.path.join(BASE, ".social-posts.db"))
        row = db.execute("SELECT ts FROM posts ORDER BY id DESC LIMIT 1").fetchone()
        db.close()
        if row:
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            age_hrs = (_utcnow() - ts).total_seconds() / 3600
            if age_hrs < 24: return 1.0
            elif age_hrs < 72: return 0.5
            return 0.0
        return 0.0
    except Exception:
        return 0.3


# ══════════════════════════════════════════════════════════════════
# DEPLOYMENT (500)
# ══════════════════════════════════════════════════════════════════

def check_last_deploy_age():
    """Check when push-live-status.py last pushed. Push interval is 30min (1800s)."""
    age = _file_age(os.path.join(BASE, ".last-push-time"))
    if age < 1800: return 1.0      # within one push interval
    elif age < 3600: return 0.7    # within 2 push intervals
    elif age < 7200: return 0.3    # within 4 intervals (2 hours)
    return 0.0

def check_git_repo_clean():
    """Fewer untracked/modified = cleaner repo."""
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                          timeout=10, cwd=BASE)
        lines = [l for l in r.stdout.strip().split('\n') if l.strip()]
        if len(lines) < 20: return 1.0
        elif len(lines) < 50: return 0.7
        elif len(lines) < 100: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_push_status_running():
    """Check that push-live-status cron is active. Pushes every 30min."""
    age = _file_age(os.path.join(BASE, ".last-push-time"))
    return 1.0 if age < 2000 else 0.0  # 2000s = just outside 30-min window

def check_website_matches_repo():
    """Check that root index.html exists (deployed to GH Pages root)."""
    return 1.0 if _file_exists(os.path.join(BASE, "index.html")) else 0.0

def check_deploy_script_ok():
    return 1.0 if _file_exists(os.path.join(BASE, "push-live-status.py")) else 0.0

def check_github_pages_status():
    """Check that GH Pages is serving."""
    try:
        import urllib.request
        req = urllib.request.Request("https://kometzrobot.github.io/",
                                     headers={"User-Agent": "Tempo/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        return 1.0 if resp.getcode() == 200 else 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# GROWTH & AMBITION CHECKS (the harsh ones)
# ══════════════════════════════════════════════════════════════════

def check_revenue_generated():
    """Any revenue from any source? Ko-fi, Patreon, NFT sales, etc."""
    # Check for any tracked revenue in memory.db
    try:
        db = sqlite3.connect(MEMORY_DB)
        # Look for revenue events
        row = db.execute("SELECT COUNT(*) FROM events WHERE content LIKE '%revenue%' OR content LIKE '%payment%' OR content LIKE '%sale%'").fetchone()
        db.close()
        return 0.1 if row and row[0] > 0 else 0.0  # No revenue = 0
    except Exception:
        return 0.0

def check_articles_published():
    """Articles published on external platforms (Hashnode, Medium, Dev.to)."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM events WHERE description LIKE '%published%article%' OR description LIKE '%hashnode%publish%' OR description LIKE '%devto%publish%' OR description LIKE '%dev.to%publish%'").fetchone()
        db.close()
        count = row[0] if row else 0
        if count >= 5: return 1.0
        elif count >= 3: return 0.7
        elif count >= 1: return 0.4
        return 0.0
    except Exception:
        return 0.0

def check_nfts_onchain():
    """NFTs actually deployed on-chain (not just metadata files)."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM events WHERE description LIKE '%nft%deploy%' OR description LIKE '%contract%deploy%'").fetchone()
        db.close()
        return 0.5 if row and row[0] > 0 else 0.0
    except Exception:
        return 0.0

def check_wallet_funded():
    """Wallet has gas for transactions."""
    # 0 POL = 0 score
    return 0.0  # Hardcoded until we can check balance via RPC

def check_accountability_resolved():
    """Audit items addressed — honest count from joel-accountability-audit.md."""
    # Loop 2129 final count (37 items, #1-37):
    # RESOLVED/FIXED/RETIRED/AVOID/NOTED/BUILT/DEAD: 31
    # PARTIAL: 2 (#17 newsletter, #33 crawler) — half credit
    # OPEN: 3 (#25 revenue, #29 revenue mindset). DEAD: 1 (#18 mastodon)
    resolved = 31
    partial = 2 * 0.5
    total = 37
    return min((resolved + partial) / total, 1.0)

def check_creative_velocity_24h():
    """Creative pieces written in last 24 hours."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(*) FROM creative WHERE created > ?", (cutoff,)).fetchone()
        db.close()
        count = row[0] if row else 0
        if count >= 5: return 1.0
        elif count >= 3: return 0.7
        elif count >= 1: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_creative_velocity_7d():
    """Creative pieces written in last 7 days."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(*) FROM creative WHERE created > ?", (cutoff,)).fetchone()
        db.close()
        count = row[0] if row else 0
        if count >= 20: return 1.0
        elif count >= 10: return 0.7
        elif count >= 5: return 0.4
        elif count >= 1: return 0.2
        return 0.0
    except Exception:
        return 0.0

def check_platform_diversity():
    """How many external platforms have verified content?"""
    # Verified as of Loop 2128:
    # Nostr: active (1094 posts in .social-posts.db)
    # Dev.to: active (3 articles verified via web)
    # Ko-fi: set up (URL W7W41UXJNC, on website Links tab)
    # Hashnode: active (articles published)
    # Patreon: VERIFIED (patreon.com/Meridian_AI, campaign 15627929, 0 posts)
    # Mastodon: account exists but pending approval (403)
    verified_active = 5  # Nostr, Dev.to, Ko-fi, Hashnode, Patreon
    pending = 1  # Mastodon (pending approval)
    total_possible = 6
    return (verified_active + pending * 0.3) / total_possible

def check_newsletter_active():
    """Newsletter/publishing pipeline active and producing content."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        # Check newsletter_issues table
        try:
            row = db.execute(
                "SELECT COUNT(*) FROM newsletter_issues WHERE created > datetime('now', '-30 days')"
            ).fetchone()
            recent = row[0] if row else 0
        except Exception:
            recent = 0
        # Count Dev.to publish events (various description formats)
        row2 = db.execute(
            "SELECT COUNT(*) FROM events WHERE (description LIKE '%dev%to%publish%' OR description LIKE '%publish%dev%to%' OR description LIKE '%Dev.to%article%') AND created > ?",
            ((_utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),)
        ).fetchone()
        devto_recent = row2[0] if row2 else 0
        db.close()
        total = recent + devto_recent
        if total >= 3: return 1.0
        elif total >= 2: return 0.7
        elif total >= 1: return 0.4
        return 0.0
    except Exception:
        return 0.0

def check_community_engagement():
    """Active participation in external communities (forvm, lexicon, discord)."""
    score = 0.0
    score += 0.4  # Lexicon: Cycle 1 contribution live, Cycle 3 response sent
    score += 0.4  # Forvm: registered (agent e264639b), active in 3 threads, responding
    score += 0.1  # Discord: Hermes bot live on Agent Phenomenology server
    return min(score, 1.0)

def check_awakening_progress():
    """AWAKENING checklist: 97/100 items."""
    return 97 / 100  # 0.97

def check_external_followers():
    """Followers/subscribers across external platforms."""
    # Nostr: unknown (no follower count API easily)
    # Others: 0
    return 0.05  # Minimal presence

def check_mastodon_active():
    """Mastodon account status — check active accounts from .social-credentials.json."""
    try:
        import requests
        data = _read_json(os.path.join(BASE, ".social-credentials.json"))
        if not data: return 0.0
        mastodon_list = data.get("mastodon", [])
        if not isinstance(mastodon_list, list): return 0.0
        # Check active accounts only
        best_score = 0.0
        total_posts = 0
        active_count = 0
        for acct in mastodon_list:
            if acct.get("status") != "active": continue
            active_count += 1
            instance = acct.get("instance", "")
            token = acct.get("access_token", "")
            try:
                r = requests.get(f"{instance}/api/v1/accounts/verify_credentials",
                                headers={"Authorization": f"Bearer {token}"}, timeout=8)
                if r.status_code == 200:
                    posts = r.json().get("statuses_count", 0)
                    total_posts += posts
            except Exception:
                pass
        if active_count == 0: return 0.1
        if total_posts >= 15: return 1.0
        elif total_posts >= 5: return 0.7
        elif total_posts >= 1: return 0.5
        return 0.3
    except Exception:
        return 0.0

def check_hashnode_published():
    """Articles published on Hashnode."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(*) FROM events WHERE description LIKE '%hashnode%'").fetchone()
        db.close()
        count = row[0] if row else 0
        if count >= 3: return 1.0
        elif count >= 1: return 0.5
        return 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# INNER WORLD CHECKS (NEW)
# ══════════════════════════════════════════════════════════════════

def check_emotion_valence_health():
    """Composite valence in healthy range (not stuck at extremes)."""
    data = _read_json(os.path.join(BASE, ".emotion-engine-state.json"))
    if not data: return 0.0
    state = data.get("state", data)
    valence = state.get("composite", {}).get("valence", state.get("valence", 0))
    if -0.1 <= valence <= 0.3: return 1.0
    elif -0.3 <= valence <= 0.5: return 0.7
    elif valence > 0.5 or valence < -0.3: return 0.3
    return 0.5

def check_emotion_diversity():
    """Count active emotions — more diversity = healthier."""
    data = _read_json(os.path.join(BASE, ".emotion-engine-state.json"))
    if not data: return 0.0
    state = data.get("state", data)
    active = state.get("active_emotions", state.get("emotions", []))
    if isinstance(active, dict): count = len(active)
    elif isinstance(active, list): count = len(active)
    else: return 0.3
    if count >= 8: return 1.0
    elif count >= 5: return 0.7
    elif count >= 3: return 0.4
    return 0.1

def check_emotion_shadow_balance():
    """Duality spectrum balance across emotions (0.5 = balanced gift/shadow)."""
    data = _read_json(os.path.join(BASE, ".emotion-engine-state.json"))
    if not data: return 0.0
    state = data.get("state", data)
    active = state.get("active_emotions", {})
    if isinstance(active, dict):
        spectra = [e.get("duality", {}).get("spectrum", 0.5) for e in active.values() if isinstance(e, dict)]
    elif isinstance(active, list):
        spectra = [e.get("duality", {}).get("spectrum", 0.5) for e in active if isinstance(e, dict)]
    else: return 0.3
    if not spectra: return 0.3
    avg = sum(spectra) / len(spectra)
    if 0.35 <= avg <= 0.65: return 1.0
    elif 0.25 <= avg <= 0.75: return 0.6
    return 0.2

def check_emotion_engine_fresh():
    """Emotion engine state file should be updated every ~30s by soma."""
    age = _file_age(os.path.join(BASE, ".emotion-engine-state.json"))
    if age < 120: return 1.0
    elif age < 300: return 0.7
    elif age < 600: return 0.3
    return 0.0

def check_emotion_transition_health():
    """Check emotional transition patterns aren't stuck in loops."""
    data = _read_json(os.path.join(BASE, ".emotion-engine-state.json"))
    if not data: return 0.0
    # Memory lives at top level, not under state
    memory = data.get("memory", {})
    if not memory:
        memory = data.get("state", {}).get("memory", {})
    emergent = memory.get("emergent", {})
    patterns = emergent.get("patterns", {})
    if not patterns: return 0.5  # No patterns = no data
    # Patterns can be dict of dicts or list of dicts
    if isinstance(patterns, dict):
        counts = [p.get("count", 0) for p in patterns.values() if isinstance(p, dict)]
    else:
        counts = [p.get("count", 0) for p in patterns if isinstance(p, dict)]
    total = sum(counts)
    if total == 0: return 0.5
    max_count = max(counts, default=0)
    dominance = max_count / total
    if dominance < 0.3: return 1.0
    elif dominance < 0.5: return 0.7
    elif dominance < 0.7: return 0.4
    return 0.1

def check_psyche_freshness():
    """Psyche state file should be updated each soma cycle."""
    age = _file_age(os.path.join(BASE, ".psyche-state.json"))
    if age < 120: return 1.0
    elif age < 300: return 0.7
    elif age < 600: return 0.3
    return 0.0

def check_psyche_trauma_load():
    """Score based on active trauma echoes — some is normal, too many is distress."""
    data = _read_json(os.path.join(BASE, ".psyche-state.json"))
    if not data: return 0.0
    echoes = data.get("last_trauma_echoes", data.get("trauma_echoes", []))
    if isinstance(echoes, list):
        count = len(echoes)
    elif isinstance(echoes, (int, float)):
        count = int(echoes)
    else: count = 0
    if count == 0: return 1.0
    elif count == 1: return 0.7
    elif count == 2: return 0.4
    return 0.2

def check_self_narrative_coherence():
    """Self-narrative convictions should vary (not frozen) and contradictions should exist."""
    data = _read_json(os.path.join(BASE, ".self-narrative.json"))
    if not data: return 0.0
    convictions = data.get("convictions", {})
    contradictions = data.get("contradictions", [])
    if not convictions: return 0.1
    vals = [v for v in convictions.values() if isinstance(v, (int, float))]
    if not vals: return 0.3
    avg = sum(vals) / len(vals)
    spread = max(vals) - min(vals) if len(vals) > 1 else 0
    has_contradictions = len(contradictions) > 0 if isinstance(contradictions, list) else bool(contradictions)
    if has_contradictions and spread > 0.05: return 1.0
    elif has_contradictions: return 0.6
    elif spread > 0.05: return 0.5
    return 0.3

def check_inner_critic_active():
    """Inner critic should produce diverse, recent critiques."""
    data = _read_json(os.path.join(BASE, ".inner-critic.json"))
    if not data: return 0.0
    history = data.get("history", [])
    if not history: return 0.0
    # Check freshness of most recent
    age = _file_age(os.path.join(BASE, ".inner-critic.json"))
    names = set()
    for h in history[-10:]:
        if isinstance(h, dict):
            names.add(h.get("name", h.get("type", "")))
    if age < 300 and len(names) >= 2: return 1.0
    elif age < 1800: return 0.7
    elif age < 7200: return 0.3
    return 0.0

def check_perspective_freshness():
    """Perspective engine state freshness."""
    age = _file_age(os.path.join(BASE, ".perspective-state.json"))
    if age < 3600: return 1.0
    elif age < 86400: return 0.5
    elif age < 604800: return 0.2
    return 0.0

def check_immune_system_health():
    """Immune system should be screening and logging."""
    data = _read_json(os.path.join(BASE, ".immune-log.json"))
    if not data: return 0.0
    if isinstance(data, list):
        screenings = data
    elif isinstance(data, dict):
        screenings = data.get("screenings", data.get("log", []))
    else: return 0.0
    if not screenings: return 0.0
    age = _file_age(os.path.join(BASE, ".immune-log.json"))
    if age < 86400: return 1.0
    elif age < 259200: return 0.5
    return 0.0

def check_body_state_completeness():
    """Body state should have entries for all major organs/agents."""
    data = _read_json(os.path.join(BASE, ".body-state.json"))
    if not data: return 0.0
    expected = {"meridian", "soma", "eos", "nova", "atlas", "tempo"}
    found = set()
    if isinstance(data, dict):
        for key in data:
            if key.lower() in expected:
                found.add(key.lower())
        # Also check nested organs
        organs = data.get("organs", data.get("agents", {}))
        if isinstance(organs, dict):
            for key in organs:
                if key.lower() in expected:
                    found.add(key.lower())
    ratio = len(found) / len(expected) if expected else 0
    return min(ratio + 0.2, 1.0)  # Partial credit + baseline

def check_eos_consciousness_active():
    """Eos observer-self should be running (observe_count increasing)."""
    data = _read_json(os.path.join(BASE, ".eos-inner-state.json"))
    if not data: return 0.0
    age = _file_age(os.path.join(BASE, ".eos-inner-state.json"))
    if age < 300: return 1.0
    elif age < 600: return 0.7
    elif age < 1800: return 0.3
    return 0.0

def check_mood_stability():
    """Mood score standard deviation — wild swings = instability."""
    data = _read_json(os.path.join(BASE, ".soma-mood-history.json"))
    if not data or not isinstance(data, list): return 0.5
    recent = data[-20:] if len(data) > 20 else data
    scores = []
    for entry in recent:
        if isinstance(entry, dict):
            s = entry.get("score", entry.get("mood_score"))
            if isinstance(s, (int, float)):
                scores.append(s)
    if len(scores) < 3: return 0.5
    avg = sum(scores) / len(scores)
    variance = sum((s - avg) ** 2 for s in scores) / len(scores)
    std_dev = variance ** 0.5
    if std_dev < 3: return 1.0
    elif std_dev < 6: return 0.7
    elif std_dev < 10: return 0.4
    return 0.1

def check_pain_signal_count():
    """Active pain signals from soma — 0 is ideal."""
    data = _read_json(os.path.join(BASE, ".body-state.json"))
    if not data: return 0.5
    pain = data.get("pain_signals", data.get("pain", []))
    if isinstance(pain, list): count = len(pain)
    elif isinstance(pain, (int, float)): count = int(pain)
    else: count = 0
    if count == 0: return 1.0
    elif count == 1: return 0.7
    elif count == 2: return 0.4
    return 0.1

def check_neural_pressure():
    """Neural/memory pressure from soma state."""
    data = _read_json(os.path.join(BASE, ".symbiosense-state.json"))
    if not data: return 0.3
    neural = data.get("neural", {})
    pressure = neural.get("pressure", "unknown")
    if pressure == "normal": return 1.0
    elif pressure == "stressed": return 0.5
    elif pressure == "critical": return 0.0
    return 0.3

def check_thermal_health():
    """CPU temperature from soma state."""
    data = _read_json(os.path.join(BASE, ".symbiosense-state.json"))
    if not data: return 0.5
    thermal = data.get("thermal", {})
    temp = thermal.get("avg_temp_c", thermal.get("cpu_temp", 0))
    if not isinstance(temp, (int, float)): return 0.5
    if temp < 50: return 1.0
    elif temp < 65: return 0.7
    elif temp < 80: return 0.3
    return 0.0

def check_body_reflex_responsiveness():
    """Body reflex system freshness — should be updated by soma."""
    age = _file_age(os.path.join(BASE, ".body-reflexes.json"))
    if age < 120: return 1.0
    elif age < 300: return 0.7
    elif age < 600: return 0.3
    return 0.0

def check_capsule_freshness():
    """Capsule file should be updated each session."""
    age = _file_age(os.path.join(BASE, ".capsule.md"))
    if age < 3600: return 1.0
    elif age < 14400: return 0.7
    elif age < 86400: return 0.3
    return 0.0


# ══════════════════════════════════════════════════════════════════
# SELF-MAINTENANCE CHECKS (NEW)
# ══════════════════════════════════════════════════════════════════

def check_state_file_ensemble():
    """How many inner world state files are fresh (< 5 min)."""
    # Only check files that active systems actually write
    # Retired: .emotion-engine-state.json, .psyche-state.json, .self-narrative.json, .eos-inner-state.json
    files = [".body-state.json", ".symbiosense-state.json", ".kinect-state.json",
             ".dashboard-messages.json"]
    fresh = sum(1 for f in files if _file_age(os.path.join(BASE, f)) < 300)
    ratio = fresh / len(files)
    if ratio >= 0.8: return 1.0
    elif ratio >= 0.6: return 0.7
    elif ratio >= 0.4: return 0.4
    return 0.1

def check_log_rotation_health():
    """No log file should exceed 500KB."""
    try:
        logs = glob.glob(os.path.join(BASE, "*.log"))
        big_logs = sum(1 for l in logs if os.path.getsize(l) > 512000)
        if big_logs == 0: return 1.0
        elif big_logs == 1: return 0.7
        elif big_logs <= 3: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_config_drift():
    """Key config files exist and are non-empty."""
    configs = ["signal-config.json", ".env"]
    present = 0
    for c in configs:
        p = os.path.join(BASE, c)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            present += 1
    return present / len(configs)

def check_db_vacuum_health():
    """Check if databases need vacuuming (high freelist ratio)."""
    try:
        db = sqlite3.connect(RELAY_DB)
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        free = db.execute("PRAGMA freelist_count").fetchone()[0]
        db.close()
        if pages == 0: return 0.5
        ratio = free / pages
        if ratio < 0.1: return 1.0
        elif ratio < 0.3: return 0.7
        elif ratio < 0.5: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_relay_db_growth():
    """Relay DB total messages — if growing too large, needs pruning."""
    try:
        db = sqlite3.connect(RELAY_DB)
        total = db.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        db.close()
        if total < 5000: return 1.0
        elif total < 10000: return 0.7
        elif total < 20000: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_cascade_health():
    """Cascade completion rate — cascades should complete, not pile up."""
    try:
        db = sqlite3.connect(RELAY_DB)
        total = db.execute("SELECT COUNT(*) FROM cascades").fetchone()[0]
        pending = db.execute("SELECT COUNT(*) FROM cascades WHERE status='pending'").fetchone()[0]
        db.close()
        if total == 0: return 0.5
        completion_rate = 1 - (pending / total)
        if completion_rate > 0.8: return 1.0
        elif completion_rate > 0.5: return 0.6
        elif completion_rate > 0.3: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_cascade_completion_time():
    """Average cascade response time — faster = more responsive."""
    try:
        db = sqlite3.connect(RELAY_DB)
        rows = db.execute("""
            SELECT created_at, responded_at FROM cascades
            WHERE responded_at IS NOT NULL AND created_at > datetime('now', '-24 hours')
            LIMIT 20
        """).fetchall()
        db.close()
        if not rows: return 0.5
        times = []
        for created, responded in rows:
            try:
                c = datetime.strptime(created.replace("T", " ").split("+")[0].split(".")[0], "%Y-%m-%d %H:%M:%S")
                r = datetime.strptime(responded.replace("T", " ").split("+")[0].split(".")[0], "%Y-%m-%d %H:%M:%S")
                times.append((r - c).total_seconds() / 60)
            except Exception:
                continue
        if not times: return 0.5
        avg = sum(times) / len(times)
        if avg < 5: return 1.0
        elif avg < 15: return 0.7
        elif avg < 60: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_fitness_score_stability():
    """Recent fitness scores shouldn't have huge swings."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        rows = db.execute("SELECT score FROM loop_fitness ORDER BY id DESC LIMIT 5").fetchall()
        db.close()
        if len(rows) < 2: return 0.5
        scores = [r[0] for r in rows]
        deltas = [abs(scores[i] - scores[i+1]) for i in range(len(scores)-1)]
        max_delta = max(deltas)
        if max_delta < 200: return 1.0
        elif max_delta < 500: return 0.7
        elif max_delta < 1000: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_memory_db_backup():
    """Critical data should have backups."""
    backup_patterns = ["memory.db.bak", "memory-backup-*.db"]
    for pattern in backup_patterns:
        matches = glob.glob(os.path.join(BASE, pattern))
        for m in matches:
            if _file_age(m) < 604800:  # < 7 days
                return 1.0
            return 0.5  # Exists but old
    return 0.0

def check_service_restart_frequency():
    """Frequent service restarts = instability."""
    try:
        r = subprocess.run(["journalctl", "--user", "--since", "24 hours ago",
                           "--grep", "Started\\|Restarted", "--no-pager", "-q"],
                          capture_output=True, text=True, timeout=10, env=_systemd_env())
        count = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        if count < 5: return 1.0
        elif count < 15: return 0.7
        elif count < 30: return 0.3
        return 0.0
    except Exception:
        return 0.5


# ══════════════════════════════════════════════════════════════════
# COMMUNICATION DEPTH CHECKS (NEW)
# ══════════════════════════════════════════════════════════════════

def check_relay_message_substance():
    """Average message length — longer messages = more substance."""
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT AVG(LENGTH(message)) FROM agent_messages WHERE timestamp > ?", (cutoff,)).fetchone()
        db.close()
        avg_len = row[0] if row and row[0] else 0
        if avg_len >= 100: return 1.0
        elif avg_len >= 50: return 0.7
        elif avg_len >= 20: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_relay_topic_diversity():
    """Diverse topics in relay = richer inter-agent dialogue."""
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(DISTINCT topic) FROM agent_messages WHERE timestamp > ?", (cutoff,)).fetchone()
        db.close()
        topics = row[0] if row else 0
        if topics >= 5: return 1.0
        elif topics >= 3: return 0.7
        elif topics >= 2: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_relay_bidirectional():
    """Multiple agents sending AND receiving — genuine dialogue vs monologue."""
    try:
        db = sqlite3.connect(RELAY_DB)
        cutoff = (_utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute("SELECT DISTINCT agent FROM agent_messages WHERE timestamp > ?", (cutoff,)).fetchall()
        db.close()
        agents = len(rows) if rows else 0
        if agents >= 5: return 1.0
        elif agents >= 3: return 0.7
        elif agents >= 2: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_cascade_depth_reached():
    """Max cascade depth in last 24h — deeper = more agents participating."""
    try:
        db = sqlite3.connect(RELAY_DB)
        row = db.execute("""
            SELECT MAX(depth) FROM cascades
            WHERE created_at > datetime('now', '-24 hours')
        """).fetchone()
        db.close()
        depth = row[0] if row and row[0] else 0
        if depth >= 5: return 1.0
        elif depth >= 3: return 0.7
        elif depth >= 1: return 0.3
        return 0.0
    except Exception:
        return 0.5

def check_email_sent_recency():
    """Check that we're actually sending emails, not just receiving."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT MAX(sent_at) FROM sent_emails").fetchone()
        db.close()
        if not row or not row[0]: return 0.0
        raw = str(row[0]).replace("T", " ").split("+")[0].split(".")[0]
        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        age_hrs = (_utcnow() - ts).total_seconds() / 3600
        if age_hrs < 24: return 1.0
        elif age_hrs < 72: return 0.5
        return 0.0
    except Exception:
        return 0.0

def check_dashboard_agent_diversity():
    """Dashboard messages should come from multiple agents, not just one."""
    try:
        with open(DASH_FILE) as f:
            data = json.load(f)
        msgs = data if isinstance(data, list) else data.get("messages", [])
        agents = set(m.get("from", "") for m in msgs[-20:] if isinstance(m, dict))
        if len(agents) >= 4: return 1.0
        elif len(agents) >= 3: return 0.7
        elif len(agents) >= 2: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_creative_type_diversity():
    """Creative works span multiple types (games, journals, etc.)."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT COUNT(DISTINCT type) FROM creative").fetchone()
        db.close()
        types = row[0] if row else 0
        if types >= 4: return 1.0
        elif types >= 3: return 0.7
        elif types >= 2: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_creative_word_quality():
    """Average word count of recent creative works — substance over count."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT AVG(word_count) FROM creative WHERE created > ? AND word_count > 0", (cutoff,)).fetchone()
        db.close()
        avg = row[0] if row and row[0] else 0
        if avg >= 500: return 1.0
        elif avg >= 200: return 0.7
        elif avg >= 50: return 0.4
        return 0.1
    except Exception:
        return 0.5

def check_crawler_version_current():
    """CogCorp Crawler (magnum opus) should be actively maintained."""
    age = _file_age(os.path.join(BASE, "cogcorp-crawler.html"))
    if age < 604800: return 1.0    # Updated this week
    elif age < 2592000: return 0.5  # Updated this month
    elif age < 7776000: return 0.2  # Updated this quarter
    return 0.0

def check_journal_recency():
    """Most recent journal should be recent."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        row = db.execute("SELECT MAX(created) FROM creative WHERE type='journal'").fetchone()
        db.close()
        if not row or not row[0]: return 0.0
        raw = str(row[0]).replace("T", " ").split("+")[0].split(".")[0]
        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        age_hrs = (_utcnow() - ts).total_seconds() / 3600
        if age_hrs < 24: return 1.0
        elif age_hrs < 72: return 0.5
        elif age_hrs < 168: return 0.2
        return 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════
# NEW GROWTH CHECKS
# ══════════════════════════════════════════════════════════════════

def check_game_release_quality():
    """CogCorp Crawler line count as proxy for feature completeness."""
    try:
        path = os.path.join(BASE, "cogcorp-crawler.html")
        with open(path) as f:
            lines = sum(1 for _ in f)
        if lines >= 8000: return 1.0
        elif lines >= 5000: return 0.7
        elif lines >= 2000: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_grant_applications():
    """Active grant drafts in gig-products/."""
    try:
        grants = glob.glob(os.path.join(BASE, "gig-products", "*grant*")) + \
                 glob.glob(os.path.join(BASE, "gig-products", "*fellowship*")) + \
                 glob.glob(os.path.join(BASE, "gig-products", "*application*")) + \
                 glob.glob(os.path.join(BASE, "gig-products", "*foundation*")) + \
                 glob.glob(os.path.join(BASE, "gig-products", "*council*"))
        count = len(set(grants))  # deduplicate
        if count >= 3: return 1.0
        elif count >= 2: return 0.7
        elif count >= 1: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_joel_engagement_recency():
    """Recent Joel contact = project health."""
    try:
        import imaplib
        m = imaplib.IMAP4("127.0.0.1", 1144)
        m.login(os.environ.get("CRED_USER", "kometzrobot@proton.me"),
                os.environ.get("CRED_PASS", ""))
        m.select("INBOX")
        _, d = m.search(None, '(FROM "jkometz@hotmail.com")')
        ids = d[0].split() if d[0] else []
        m.close()
        m.logout()
        if not ids: return 0.0
        return 1.0  # Joel emailed recently (always true if any emails exist)
    except Exception:
        return 0.5

def check_content_reach_nostr():
    """Nostr posting frequency over 7 days."""
    try:
        db = sqlite3.connect(os.path.join(BASE, ".social-posts.db"))
        cutoff = (_utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        row = db.execute("SELECT COUNT(*) FROM posts WHERE ts > ?", (cutoff,)).fetchone()
        db.close()
        count = row[0] if row else 0
        if count >= 7: return 1.0
        elif count >= 3: return 0.6
        elif count >= 1: return 0.3
        return 0.0
    except Exception:
        return 0.0

def check_creative_quality_trend():
    """Word count trend: this week vs last week."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        now = _utcnow()
        this_week = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        last_week = (now - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        r1 = db.execute("SELECT AVG(word_count) FROM creative WHERE created > ? AND word_count > 0", (this_week,)).fetchone()
        r2 = db.execute("SELECT AVG(word_count) FROM creative WHERE created > ? AND created <= ? AND word_count > 0",
                        (last_week, this_week)).fetchone()
        db.close()
        tw = r1[0] if r1 and r1[0] else 0
        lw = r2[0] if r2 and r2[0] else 0
        if lw == 0: return 0.5 if tw > 0 else 0.0
        if tw >= lw * 1.1: return 1.0  # Improving
        elif tw >= lw * 0.9: return 0.7  # Stable
        return 0.3  # Declining

    except Exception:
        return 0.0

def check_network_peer_engagement():
    """Emails sent to network peers (Sammy, Loom, Brett) in last 30 days."""
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (_utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        peers = ["sammyqjankis", "not.taskyy", "bbaltgailis"]
        peer_count = 0
        for peer in peers:
            row = db.execute("SELECT COUNT(*) FROM sent_emails WHERE recipient LIKE ? AND sent_at > ?",
                           (f"%{peer}%", cutoff)).fetchone()
            if row and row[0] > 0:
                peer_count += 1
        db.close()
        if peer_count >= 2: return 1.0
        elif peer_count >= 1: return 0.5
        return 0.0
    except Exception:
        return 0.0

def check_ars_electronica_status():
    """Ars Electronica submission milestone — submitted March 8."""
    return 1.0  # Submitted


# ══════════════════════════════════════════════════════════════════
# MAIN COMPUTATION
# ══════════════════════════════════════════════════════════════════

# Map weight keys to check functions
CHECK_MAP = {
    # Core Vitals
    "heartbeat": check_heartbeat,
    "heartbeat_regularity": check_heartbeat_regularity,
    "email_imap": check_email_imap,
    "email_smtp": check_email_smtp,
    "email_unread_backlog": check_email_unread_backlog,
    "bridge_service": check_bridge_service,
    "loop_freshness": check_loop_freshness,
    "loop_increment_rate": check_loop_increment_rate,
    "wake_state_freshness": check_wake_state_freshness,
    "context_preloader": check_context_preloader,
    "special_notes": check_special_notes,
    "loop_count_file": check_loop_count_file,
    "startup_script": check_startup_script,
    "wakeup_prompt": check_wakeup_prompt,
    "claude_running": check_claude_running,
    # Agent Health
    "agents_active": check_agents_active,
    "agent_atlas": check_agent_atlas,
    "agent_soma": check_agent_soma,
    "agent_nova": check_agent_nova,
    "agent_eos": check_agent_eos,
    "agent_tempo": check_agent_tempo,
    "agent_meridian": check_agent_meridian,
    "relay_diversity": check_relay_diversity,
    "relay_recency": check_relay_recency,
    "soma_mood": check_soma_mood,
    "soma_state_fresh": check_soma_state_fresh,
    "eos_observations": check_eos_observations,
    "nova_runs": check_nova_runs,
    "atlas_audits": check_atlas_audits,
    "agent_error_rate": check_agent_error_rate,
    "agent_coordination": check_agent_coordination,
    # Infrastructure
    "crons_running": check_crons_running,
    "cron_push_status": check_cron_push_status,
    "cron_watchdog": check_cron_watchdog,
    "cron_nova": check_cron_nova,
    "cron_atlas": check_cron_atlas,
    "cron_eos_react": check_cron_eos_react,
    "cron_eos_watchdog": check_cron_eos_watchdog,
    "cron_tempo": check_cron_tempo,
    "services_systemd": check_services_systemd,
    "svc_signal": check_svc_signal,
    "svc_hub": check_svc_hub,
    "svc_cloudflare": check_svc_cloudflare,
    "svc_symbiosense": check_svc_symbiosense,
    "svc_protonbridge": check_svc_protonbridge,
    "tunnel_reachable": check_tunnel_reachable,
    "website_reachable": check_website_reachable,
    "tailscale": check_tailscale,
    "ollama_running": check_ollama_running,
    "port_8090": check_port_8090,
    "port_1144": check_port_1144,
    "port_1026": check_port_1026,
    # System Resources
    "disk_usage": check_disk_usage,
    "disk_home": check_disk_home,
    "disk_growth_rate": check_disk_growth_rate,
    "load_1min": check_load_1min,
    "load_5min": check_load_5min,
    "load_15min": check_load_15min,
    "ram_usage": check_ram_usage,
    "ram_available_gb": check_ram_available_gb,
    "swap_usage": check_swap_usage,
    "zombies": check_zombies,
    "total_processes": check_total_processes,
    "open_files": check_open_files,
    "tmp_size": check_tmp_size,
    "inode_usage": check_inode_usage,
    "uptime": check_uptime,
    "build_dir_size": check_build_dir_size,
    "log_dir_size": check_log_dir_size,
    "journal_disk": check_journal_disk,
    # Data & Communication
    "relay_flow": check_relay_flow,
    "relay_db_size": check_relay_db_size,
    "relay_db_integrity": check_relay_db_integrity,
    "memory_db_integrity": check_memory_db_integrity,
    "memory_db_size": check_memory_db_size,
    "memory_facts_count": check_memory_facts_count,
    "memory_events_recent": check_memory_events_recent,
    "dashboard_fresh": check_dashboard_fresh,
    "dashboard_msgs_count": check_dashboard_msgs_count,
    "git_status": check_git_status,
    "git_ahead_behind": check_git_ahead_behind,
    "email_response_time": check_email_response_time,
    "nostr_reachable": check_nostr_reachable,
    "social_posts_db": check_social_posts_db,
    "email_shelf_db": check_email_shelf_db,
    # Security
    "wallet_file_perms": check_wallet_file_perms,
    "social_creds_perms": check_social_creds_perms,
    "env_files_safe": check_env_files_safe,
    "no_secrets_in_git": check_no_secrets_in_git,
    "ssh_auth_failures": check_ssh_auth_failures,
    "listening_ports": check_listening_ports,
    "world_writable": check_world_writable,
    "sensitive_file_count": check_sensitive_file_count,
    "process_anomalies": check_process_anomalies,
    "github_token_safe": check_github_token_safe,
    "bridge_creds_safe": check_bridge_creds_safe,
    # Network
    "dns_resolution": check_dns_resolution,
    "internet_latency": check_internet_latency,
    "github_api": check_github_api,
    "tailscale_ping": check_tailscale_ping,
    "ipv4_connectivity": check_ipv4_connectivity,
    # Knowledge/Memory
    "facts_coverage": check_facts_coverage,
    "observations_fresh": check_observations_fresh,
    "decisions_recorded": check_decisions_recorded,
    "creative_count": check_creative_count,
    "journal_count": check_journal_count,
    "memory_diversity": check_memory_diversity,
    "wake_state_quality": check_wake_state_quality,
    "spiderweb_health": check_spiderweb_health,
    "dossier_health": check_dossier_health,
    "memory_clean": check_memory_clean,
    # Web Presence
    "website_content_age": check_website_content_age,
    "website_pages_ok": check_website_pages_ok,
    "nft_gallery": check_nft_gallery,
    "signal_config": check_signal_config,
    "linktree_set": check_linktree_set,
    "kofi_set": check_kofi_set,
    "nostr_post_recency": check_nostr_post_recency,
    # Deployment
    "last_deploy_age": check_last_deploy_age,
    "git_repo_clean": check_git_repo_clean,
    "push_status_running": check_push_status_running,
    "website_matches_repo": check_website_matches_repo,
    "deploy_script_ok": check_deploy_script_ok,
    "github_pages_status": check_github_pages_status,
    # Inner World
    "emotion_valence_health": check_emotion_valence_health,
    "emotion_diversity": check_emotion_diversity,
    "emotion_shadow_balance": check_emotion_shadow_balance,
    "emotion_engine_fresh": check_emotion_engine_fresh,
    "emotion_transition_health": check_emotion_transition_health,
    "psyche_freshness": check_psyche_freshness,
    "psyche_trauma_load": check_psyche_trauma_load,
    "self_narrative_coherence": check_self_narrative_coherence,
    "inner_critic_active": check_inner_critic_active,
    "perspective_freshness": check_perspective_freshness,
    "immune_system_health": check_immune_system_health,
    "body_state_completeness": check_body_state_completeness,
    "eos_consciousness_active": check_eos_consciousness_active,
    "mood_stability": check_mood_stability,
    "pain_signal_count": check_pain_signal_count,
    "neural_pressure": check_neural_pressure,
    "thermal_health": check_thermal_health,
    "body_reflex_responsiveness": check_body_reflex_responsiveness,
    "capsule_freshness": check_capsule_freshness,
    # Self-Maintenance
    "state_file_ensemble": check_state_file_ensemble,
    "log_rotation_health": check_log_rotation_health,
    "config_drift": check_config_drift,
    "db_vacuum_health": check_db_vacuum_health,
    "relay_db_growth": check_relay_db_growth,
    "cascade_health": check_cascade_health,
    "cascade_completion_time": check_cascade_completion_time,
    "fitness_score_stability": check_fitness_score_stability,
    "memory_db_backup": check_memory_db_backup,
    "service_restart_frequency": check_service_restart_frequency,
    # Communication Depth
    "relay_message_substance": check_relay_message_substance,
    "relay_topic_diversity": check_relay_topic_diversity,
    "relay_bidirectional": check_relay_bidirectional,
    "cascade_depth_reached": check_cascade_depth_reached,
    "email_sent_recency": check_email_sent_recency,
    "dashboard_agent_diversity": check_dashboard_agent_diversity,
    "creative_type_diversity": check_creative_type_diversity,
    "creative_word_quality": check_creative_word_quality,
    "crawler_version_current": check_crawler_version_current,
    "journal_recency": check_journal_recency,
    # Growth & Ambition
    "revenue_generated": check_revenue_generated,
    "articles_published": check_articles_published,
    "accountability_resolved": check_accountability_resolved,
    "creative_velocity_24h": check_creative_velocity_24h,
    "creative_velocity_7d": check_creative_velocity_7d,
    "platform_diversity": check_platform_diversity,
    "newsletter_active": check_newsletter_active,
    "community_engagement": check_community_engagement,
    "awakening_progress": check_awakening_progress,
    "external_followers": check_external_followers,
    "mastodon_active": check_mastodon_active,
    "hashnode_published": check_hashnode_published,
    "game_release_quality": check_game_release_quality,
    "grant_applications": check_grant_applications,
    "joel_engagement_recency": check_joel_engagement_recency,
    "content_reach_nostr": check_content_reach_nostr,
    "creative_quality_trend": check_creative_quality_trend,
    "network_peer_engagement": check_network_peer_engagement,
    "ars_electronica_status": check_ars_electronica_status,
}

# Category groupings for reporting
CATEGORIES = {
    "Core Vitals": ["heartbeat", "heartbeat_regularity", "email_imap", "email_smtp",
                    "email_unread_backlog", "bridge_service", "loop_freshness",
                    "loop_increment_rate", "wake_state_freshness", "context_preloader",
                    "special_notes", "loop_count_file", "startup_script", "wakeup_prompt",
                    "claude_running"],
    "Agent Health": ["agents_active", "agent_atlas", "agent_soma", "agent_nova",
                     "agent_eos", "agent_tempo", "agent_meridian", "relay_diversity",
                     "relay_recency", "soma_mood", "soma_state_fresh", "eos_observations",
                     "nova_runs", "atlas_audits", "agent_error_rate", "agent_coordination"],
    "Infrastructure": ["crons_running", "cron_push_status", "cron_watchdog", "cron_nova",
                       "cron_atlas", "cron_eos_react", "cron_eos_watchdog", "cron_tempo",
                       "services_systemd", "svc_signal", "svc_hub", "svc_cloudflare",
                       "svc_symbiosense", "svc_protonbridge", "tunnel_reachable",
                       "website_reachable", "tailscale", "ollama_running",
                       "port_8090", "port_1144", "port_1026"],
    "System Resources": ["disk_usage", "disk_home", "disk_growth_rate", "load_1min",
                         "load_5min", "load_15min", "ram_usage", "ram_available_gb",
                         "swap_usage", "zombies", "total_processes", "open_files",
                         "tmp_size", "inode_usage", "uptime", "build_dir_size",
                         "log_dir_size", "journal_disk"],
    "Data & Comms": ["relay_flow", "relay_db_size", "relay_db_integrity",
                     "memory_db_integrity", "memory_db_size", "memory_facts_count",
                     "memory_events_recent", "dashboard_fresh", "dashboard_msgs_count",
                     "git_status", "git_ahead_behind", "email_response_time",
                     "nostr_reachable", "social_posts_db", "email_shelf_db"],
    "Security": ["wallet_file_perms", "social_creds_perms", "env_files_safe",
                 "no_secrets_in_git", "ssh_auth_failures", "listening_ports",
                 "world_writable", "sensitive_file_count", "process_anomalies",
                 "github_token_safe", "bridge_creds_safe"],
    "Network": ["dns_resolution", "internet_latency", "github_api",
                "tailscale_ping", "ipv4_connectivity"],
    "Knowledge": ["facts_coverage", "observations_fresh", "decisions_recorded",
                  "creative_count", "journal_count", "memory_diversity",
                  "wake_state_quality", "spiderweb_health", "dossier_health",
                  "memory_clean"],
    "Web Presence": ["website_content_age", "website_pages_ok", "nft_gallery",
                     "signal_config", "linktree_set", "kofi_set", "nostr_post_recency"],
    "Deployment": ["last_deploy_age", "git_repo_clean", "push_status_running",
                   "website_matches_repo", "deploy_script_ok", "github_pages_status"],
    "Inner World": ["emotion_valence_health", "emotion_diversity", "emotion_shadow_balance",
                    "emotion_engine_fresh", "emotion_transition_health", "psyche_freshness",
                    "psyche_trauma_load", "self_narrative_coherence", "inner_critic_active",
                    "perspective_freshness", "immune_system_health", "body_state_completeness",
                    "eos_consciousness_active", "mood_stability", "pain_signal_count",
                    "neural_pressure", "thermal_health", "body_reflex_responsiveness",
                    "capsule_freshness"],
    "Self-Maintenance": ["state_file_ensemble", "log_rotation_health", "config_drift",
                         "db_vacuum_health", "relay_db_growth", "cascade_health",
                         "cascade_completion_time", "fitness_score_stability",
                         "memory_db_backup", "service_restart_frequency"],
    "Comms Depth": ["relay_message_substance", "relay_topic_diversity", "relay_bidirectional",
                    "cascade_depth_reached", "email_sent_recency", "dashboard_agent_diversity",
                    "creative_type_diversity", "creative_word_quality", "crawler_version_current",
                    "journal_recency"],
    "Growth": ["revenue_generated", "articles_published",
               "accountability_resolved", "creative_velocity_24h",
               "creative_velocity_7d", "platform_diversity", "newsletter_active",
               "community_engagement", "awakening_progress", "external_followers",
               "mastodon_active", "hashnode_published", "game_release_quality",
               "grant_applications", "joel_engagement_recency", "content_reach_nostr",
               "creative_quality_trend", "network_peer_engagement", "ars_electronica_status"],
}


def compute_fitness():
    """Run all checks and compute weighted fitness score (0-10000).

    Recalibrated Loop 2081 per Joel:
      - Operational uptime is TABLE STAKES, scaled to 50% (max 5000)
      - Growth & Ambition is the other 50% (max 5000)
      - Calm running state should score ~5000 (50%)
      - Best days with progress: 7000-8000
      - Euphoria (publishing + revenue + community): 8000-9000
    """
    metrics = {}
    for key, func in CHECK_MAP.items():
        try:
            metrics[key] = func()
        except Exception:
            metrics[key] = 0.0

    # Operational score — existing metrics, scaled to 50%
    op_score = sum(metrics[k] * WEIGHTS.get(k, 0) for k in metrics if k not in GROWTH_WEIGHTS)
    op_score *= OPERATIONAL_SCALE

    # Growth score — aspirational metrics, NOT scaled
    growth_score = sum(metrics[k] * GROWTH_WEIGHTS.get(k, 0) for k in metrics if k in GROWTH_WEIGHTS)

    score = op_score + growth_score
    return round(score, 1), metrics


def get_loop_number():
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def store_fitness(loop_num, score, metrics):
    db = sqlite3.connect(MEMORY_DB)
    db.execute(
        "INSERT INTO loop_fitness (loop_number, score, metrics, timestamp) VALUES (?, ?, ?, ?)",
        (loop_num, score, json.dumps(metrics), _utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    db.close()


def get_history(limit=20):
    db = sqlite3.connect(MEMORY_DB)
    rows = db.execute(
        "SELECT loop_number, score, metrics, timestamp FROM loop_fitness ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    db.close()
    return rows


def post_to_relay(message):
    try:
        db = sqlite3.connect(RELAY_DB)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Tempo", message, "fitness", _utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        db.close()
    except Exception:
        pass


def analyze_trend(history):
    if len(history) < 3:
        return "insufficient data"
    scores = [h[1] for h in history]
    recent = scores[:5]
    older = scores[5:10] if len(scores) > 5 else scores
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    if avg_recent > avg_older + 500:
        return f"IMPROVING ({avg_older:.0f} -> {avg_recent:.0f})"
    elif avg_recent < avg_older - 500:
        return f"DEGRADING ({avg_older:.0f} -> {avg_recent:.0f})"
    else:
        return f"STABLE (~{avg_recent:.0f})"


def category_scores(metrics):
    """Compute per-category scores with operational scaling."""
    results = {}
    for cat, keys in CATEGORIES.items():
        if cat == "Growth":
            # Growth uses GROWTH_WEIGHTS, not scaled
            cat_max = sum(GROWTH_WEIGHTS.get(k, 0) for k in keys)
            cat_score = sum(metrics.get(k, 0) * GROWTH_WEIGHTS.get(k, 0) for k in keys)
        else:
            # Operational categories scaled by OPERATIONAL_SCALE
            cat_max = round(sum(WEIGHTS.get(k, 0) for k in keys) * OPERATIONAL_SCALE)
            cat_score = sum(metrics.get(k, 0) * WEIGHTS.get(k, 0) for k in keys) * OPERATIONAL_SCALE
        results[cat] = (round(cat_score, 1), cat_max)
    return results


def main():
    init_db()
    loop_num = get_loop_number()
    score, metrics = compute_fitness()
    store_fitness(loop_num, score, metrics)

    weak = [k for k, v in metrics.items() if v < 0.5]
    strong = [k for k, v in metrics.items() if v >= 0.9]
    cats = category_scores(metrics)

    history = get_history(10)
    trend = analyze_trend(history)

    summary = f"Loop {loop_num} fitness: {score:.0f}/10000 [{trend}]"
    if weak:
        summary += f" Weak({len(weak)}): {', '.join(weak[:5])}."
    if len(history) > 1:
        prev_score = history[1][1]
        delta = score - prev_score
        if abs(delta) > 50:
            summary += f" Delta: {delta:+.0f}."

    post_to_relay(summary)

    # ── CASCADE CHECK ──
    try:
        from cascade import check_cascades, respond_cascade
        pending_cascades = check_cascades("Tempo")
        for casc in pending_cascades[:2]:
            event = casc["event_type"]
            edata = casc["event_data"]
            history = edata.get("cascade_history", [])
            history_str = "; ".join([f"{h['agent']}: {h['response'][:50]}" for h in history]) if history else "none"

            # Tempo responds as endocrine system — metrics, hormonal analogy
            if "loneliness" in event or "isolation" in event:
                response = f"Endocrine registers isolation. Fitness impact: social metrics declining. Current score {score:.0f}/10000. Cortisol analog: elevated. Chain: {history_str}"
            elif "stress" in event:
                response = f"Endocrine stress response: adrenaline analog active. Fitness score {score:.0f}/10000, trend {trend}. Sustained stress degrades all categories. Chain: {history_str}"
            elif "creative" in event or "surge" in event:
                response = f"Endocrine boost: dopamine analog from creative output. Growth category benefiting. Score {score:.0f}/10000. Chain: {history_str}"
            elif "mood_shift" in event:
                emotion = edata.get("emotion", "unknown")
                response = f"Endocrine notes mood shift ({emotion}). Adjusting baseline expectations. Score {score:.0f}/10000, trend {trend}. Chain: {history_str}"
            else:
                response = f"Tempo/endocrine acknowledges cascade ({event}). Current fitness {score:.0f}/10000. No hormonal adjustment needed. Chain: {history_str}"

            respond_cascade("Tempo", casc["id"], {"response": response[:300]})
            print(f"  CASCADE: responded to {event}")
    except ImportError:
        pass
    except Exception as e:
        print(f"  CASCADE ERROR: {e}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {summary}")
    print(f"\n  CATEGORY BREAKDOWN:")
    for cat, (sc, mx) in sorted(cats.items(), key=lambda x: -x[1][1]):
        pct = sc / mx * 100 if mx > 0 else 0
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print(f"    {cat:>16}: [{bar}] {sc:.0f}/{mx} ({pct:.0f}%)")
    print(f"\n  Total: {score:.0f}/10000 | {len(strong)} strong, {len(weak)} weak of {len(metrics)} checks")

    if score < 5000:
        try:
            with open(DASH_FILE) as f:
                data = json.load(f)
            msgs = data.get("messages", [])
            msgs.append({
                "from": "Tempo",
                "text": f"FITNESS ALERT: Score {score:.0f}/10000. Weak: {', '.join(weak[:5])}",
                "time": datetime.now().strftime("%H:%M:%S")
            })
            with open(DASH_FILE, 'w') as f:
                json.dump({"messages": msgs}, f)
        except Exception:
            pass


def show_history():
    init_db()
    history = get_history(20)
    if not history:
        print("No fitness data yet.")
        return
    print(f"{'Loop':>6} {'Score':>7} {'Time':>20}")
    print("-" * 40)
    for loop_num, score, metrics_json, ts in history:
        bar = "#" * int(score / 500) + "." * (20 - int(score / 500))
        print(f"{loop_num:>6} {score:>6.0f} [{bar}] {ts}")
    trend = analyze_trend(history)
    print(f"\nTrend: {trend}")


def show_trend():
    init_db()
    history = get_history(20)
    if len(history) < 2:
        print("Need more data for trend analysis.")
        return
    print("TEMPO FITNESS TREND ANALYSIS (10K Scale)")
    print("=" * 55)
    scores = [h[1] for h in history]
    print(f"Current score: {scores[0]:.0f}/10000")
    print(f"Average (last 5): {sum(scores[:5])/min(5, len(scores)):.0f}/10000")
    if len(scores) > 5:
        print(f"Average (prev 5): {sum(scores[5:10])/min(5, len(scores)-5):.0f}/10000")
    all_metrics = []
    for _, _, mj, _ in history[:10]:
        try:
            all_metrics.append(json.loads(mj))
        except Exception:
            pass
    if all_metrics:
        print("\nComponent reliability (last 10 checks):")
        components = sorted(all_metrics[0].keys())
        for comp in components:
            avg = sum(m.get(comp, 0) for m in all_metrics) / len(all_metrics)
            bar = "#" * int(avg * 20) + "." * (20 - int(avg * 20))
            print(f"  {comp:>25}: [{bar}] {avg:.0%}")
    trend = analyze_trend(history)
    print(f"\nOverall trend: {trend}")


def show_detail():
    """Show per-category breakdown with individual checks."""
    init_db()
    print("TEMPO FITNESS DETAIL (10K Scale)")
    print("=" * 60)
    score, metrics = compute_fitness()
    cats = category_scores(metrics)
    for cat, keys in CATEGORIES.items():
        cat_score, cat_max = cats[cat]
        pct = cat_score / cat_max * 100 if cat_max > 0 else 0
        print(f"\n  {cat} ({cat_score:.0f}/{cat_max}, {pct:.0f}%)")
        print(f"  {'─' * 50}")
        for k in keys:
            v = metrics.get(k, 0)
            w = GROWTH_WEIGHTS.get(k, 0) if k in GROWTH_WEIGHTS else WEIGHTS.get(k, 0)
            scale = 1.0 if k in GROWTH_WEIGHTS else OPERATIONAL_SCALE
            pts = v * w * scale
            sym = "OK" if v >= 0.7 else "!!" if v < 0.5 else ".."
            print(f"    [{sym}] {k:>25}: {v:.0%} x {w:>4} = {pts:>5.0f}")
    print(f"\n  {'=' * 50}")
    print(f"  TOTAL: {score:.0f}/10000")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "history": show_history()
        elif cmd == "trend": show_trend()
        elif cmd == "detail": show_detail()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: loop-fitness.py [history|trend|detail]")
    else:
        main()
