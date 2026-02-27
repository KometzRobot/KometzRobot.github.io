#!/usr/bin/env python3
"""
Soma — Meridian's Nervous System (formerly SymbioSense)
Based on Joel's Grok concept: Meridian should sense and respond to the
computer's state like a nervous system responds to a body.

CORE CONCEPTS:
  Proprioception — continuous body awareness (load, RAM, disk, procs)
  Emotional state — derived mood from aggregate system health
  Agent awareness — tracks liveness of all 6 agents in the ecosystem
  Trend prediction — extrapolates from rolling data to predict issues
  Body map — complete system state snapshot other agents can read
  Reflexes — automatic responses to certain critical conditions

Runs every 30 seconds. Only reports on CHANGES (deltas from baseline).
Tailscale = long-range nerves, Watchdog = pain receptors,
Soma = proprioception (continuous body awareness).

Stores state in .symbiosense-state.json. Posts to relay/dashboard
only when something meaningful changes.
"""

import json
import os
import time
import sqlite3
import subprocess
from datetime import datetime, timezone

BASE = "/home/joel/autonomous-ai"
STATE_FILE = os.path.join(BASE, ".symbiosense-state.json")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
HB_FILE = os.path.join(BASE, ".heartbeat")
LOG_FILE = os.path.join(BASE, "symbiosense.log")
MOOD_HISTORY_FILE = os.path.join(BASE, ".soma-mood-history.json")
BASELINES_FILE = os.path.join(BASE, ".soma-baselines.json")
INTERVAL = 30  # seconds between checks
MOOD_HISTORY_MAX = 288  # 24 hours at 5-min intervals

# Thresholds for alerting
LOAD_SPIKE_DELTA = 2.0      # load increase per check
RAM_SPIKE_PCT = 15           # RAM % increase per check
DISK_SPIKE_PCT = 5           # disk % increase per check
HB_STALE_SEC = 600           # heartbeat stale threshold
SERVICE_CHECK_INTERVAL = 60  # check services every N seconds
DASHBOARD_COOLDOWN = 900     # suppress same alert type on dashboard for 15 min


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        # Keep log under 500KB
        if os.path.getsize(LOG_FILE) > 500000:
            with open(LOG_FILE) as f:
                lines = f.readlines()
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-500:])
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def get_load():
    try:
        parts = open("/proc/loadavg").read().split()
        return float(parts[0])
    except Exception:
        return 0.0


def get_ram_pct():
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 1)
        avail = mem.get("MemAvailable", 0)
        return int((total - avail) * 100 / total)
    except Exception:
        return 0


def get_disk_pct():
    try:
        out = subprocess.check_output(["df", "/", "--output=pcent"],
                                       text=True, timeout=5)
        return int(out.strip().split("\n")[1].strip().replace("%", ""))
    except Exception:
        return 0


def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(HB_FILE))
    except Exception:
        return -1


# ── BODY SYSTEMS: Thermal, Respiratory, Circulatory, Neural ─────
def get_thermal():
    """Body temperature — CPU thermal zones."""
    temps = {}
    try:
        import glob as _glob
        zones = sorted(_glob.glob("/sys/class/thermal/thermal_zone*/temp"))
        for zp in zones:
            zone_name = os.path.basename(os.path.dirname(zp)).replace("thermal_zone", "zone")
            try:
                t = int(open(zp).read().strip()) / 1000.0  # millidegrees → degrees C
                temps[zone_name] = round(t, 1)
            except Exception:
                pass
    except Exception:
        pass
    # Average temperature
    avg = round(sum(temps.values()) / max(len(temps), 1), 1) if temps else 0
    # Fever status
    if avg > 85:
        fever = "critical"
    elif avg > 75:
        fever = "elevated"
    elif avg > 0:
        fever = "normal"
    else:
        fever = "unknown"
    return {"zones": temps, "avg_temp_c": avg, "fever_status": fever}


def get_respiratory():
    """Breathing — fan speeds as lung function."""
    fans = {}
    try:
        import glob as _glob
        fan_inputs = _glob.glob("/sys/class/hwmon/hwmon*/fan*_input")
        for fp in fan_inputs:
            try:
                name = os.path.basename(fp).replace("_input", "")
                rpm = int(open(fp).read().strip())
                fans[name] = rpm
            except Exception:
                pass
    except Exception:
        pass
    total_rpm = sum(fans.values()) if fans else 0
    # Breathing rate metaphor: calm <1000rpm, active 1000-3000, heavy >3000
    if not fans:
        rate = "unknown"
    elif total_rpm < 1000:
        rate = "resting"
    elif total_rpm < 2500:
        rate = "active"
    else:
        rate = "heavy"
    return {"fans": fans, "total_rpm": total_rpm, "breathing": rate}


def get_circulatory():
    """Blood flow — network I/O rates."""
    try:
        lines = open("/proc/net/dev").readlines()
        rx_total = 0
        tx_total = 0
        ifaces = {}
        for line in lines[2:]:
            parts = line.strip().split()
            if not parts:
                continue
            iface = parts[0].rstrip(":")
            if iface == "lo":
                continue
            rx = int(parts[1])
            tx = int(parts[9])
            rx_total += rx
            tx_total += tx
            ifaces[iface] = {"rx_bytes": rx, "tx_bytes": tx}
        return {
            "interfaces": ifaces,
            "total_rx_mb": round(rx_total / 1048576, 1),
            "total_tx_mb": round(tx_total / 1048576, 1),
        }
    except Exception:
        return {"interfaces": {}, "total_rx_mb": 0, "total_tx_mb": 0}


def get_neural():
    """Neural state — memory pressure, swap, page faults."""
    result = {"swap_pct": 0, "swap_used_mb": 0, "page_faults": 0, "pressure": "normal"}
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        if swap_total > 0:
            swap_used = swap_total - swap_free
            result["swap_pct"] = round(swap_used * 100 / swap_total, 1)
            result["swap_used_mb"] = round(swap_used / 1024, 1)
        cached = mem.get("Cached", 0)
        buffers = mem.get("Buffers", 0)
        result["cache_mb"] = round((cached + buffers) / 1024, 1)
    except Exception:
        pass
    try:
        vm = open("/proc/vmstat").read()
        for line in vm.strip().split("\n"):
            parts = line.split()
            if parts[0] == "pgfault":
                result["page_faults"] = int(parts[1])
    except Exception:
        pass
    # Pressure assessment
    if result["swap_pct"] > 50:
        result["pressure"] = "critical"
    elif result["swap_pct"] > 20:
        result["pressure"] = "stressed"
    elif result["swap_pct"] > 5:
        result["pressure"] = "active"
    return result


def get_organs():
    """Organ health — disk I/O as organ perfusion."""
    organs = {}
    try:
        lines = open("/proc/diskstats").readlines()
        for line in lines:
            parts = line.split()
            if len(parts) < 14:
                continue
            dev = parts[2]
            # Only track real devices (sda, nvme0n1, etc.)
            if dev.startswith("loop") or dev.startswith("dm-") or dev.startswith("ram"):
                continue
            # Skip partitions (sda1, sda2 etc.) - just track whole disk
            if any(c.isdigit() for c in dev) and not dev.startswith("nvme"):
                continue
            if dev.startswith("nvme") and "p" in dev:
                continue
            reads = int(parts[3])
            writes = int(parts[7])
            read_ms = int(parts[6])
            write_ms = int(parts[10])
            io_in_progress = int(parts[11])
            organs[dev] = {
                "reads": reads,
                "writes": writes,
                "read_ms": read_ms,
                "write_ms": write_ms,
                "io_queue": io_in_progress,
            }
    except Exception:
        pass
    return organs


def check_services():
    """Check systemd user services."""
    services = {}
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    for svc in ["meridian-web-dashboard", "cloudflare-tunnel"]:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", svc],
                capture_output=True, text=True, timeout=5, env=env
            )
            services[svc] = result.stdout.strip()
        except Exception:
            services[svc] = "unknown"
    for name, pattern in [("protonmail-bridge", "protonmail-bridge"),
                          ("ollama", "ollama"),
                          ("tailscaled", "tailscaled")]:
        try:
            result = subprocess.run(["pgrep", "-f", pattern],
                                     capture_output=True, timeout=5)
            services[name] = "active" if result.returncode == 0 else "dead"
        except Exception:
            services[name] = "unknown"
    return services


def check_process_count():
    try:
        out = subprocess.check_output(["ps", "aux", "--no-headers"],
                                       text=True, timeout=5)
        return len(out.strip().split("\n"))
    except Exception:
        return 0


def post_relay(msg, topic="soma"):
    try:
        db = sqlite3.connect(RELAY_DB)
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Soma", msg, topic, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        db.close()
    except Exception as e:
        log(f"Relay post failed: {e}")


def post_dashboard(msg):
    try:
        data = json.load(open(DASH_FILE)) if os.path.exists(DASH_FILE) else {"messages": []}
        msgs = data.get("messages", []) if isinstance(data, dict) else data
    except Exception:
        msgs = []
    msgs.append({
        "from": "Soma",
        "text": msg,
        "time": datetime.now().strftime("%H:%M:%S")
    })
    msgs = msgs[-50:]  # Trim to last 50 messages
    try:
        with open(DASH_FILE, "w") as f:
            json.dump({"messages": msgs}, f)
    except Exception:
        pass


def append_mood_history(state):
    """Append current mood snapshot to rolling history file for charting."""
    try:
        if os.path.exists(MOOD_HISTORY_FILE):
            with open(MOOD_HISTORY_FILE) as f:
                history = json.load(f)
        else:
            history = []
        history.append({
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mood": state.get("mood", "?"),
            "score": state.get("mood_score", 0),
            "trend": state.get("mood_trend", "stable"),
            "delta": state.get("mood_delta", 0),
            "voice": MOOD_VOICE.get(state.get("mood", ""), ""),
            "load": round(state.get("load", 0), 2),
            "ram": state.get("ram_pct", 0),
            "disk": state.get("disk_pct", 0),
        })
        history = history[-MOOD_HISTORY_MAX:]
        with open(MOOD_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        log(f"Mood history write failed: {e}")


# ── ADAPTIVE BASELINES ──────────────────────────────────────────
# Learn what "normal" looks like for each hour of the day.
# 24 buckets (one per hour), EMA-smoothed over ~7 days of data.
# Used to adjust mood scoring so routine cron spikes don't cause alerts.
BASELINE_EMA_ALPHA = 0.05  # ~20 updates to converge (each hour gets ~2/hr * 24h = ~48/day)

def load_baselines():
    """Load per-hour baselines from disk."""
    try:
        if os.path.exists(BASELINES_FILE):
            with open(BASELINES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    # Initialize 24 empty buckets
    return {str(h): {"load": None, "ram": None, "disk": None, "count": 0} for h in range(24)}

def save_baselines(baselines):
    try:
        with open(BASELINES_FILE, "w") as f:
            json.dump(baselines, f)
    except Exception:
        pass

def update_baselines(baselines, hour, load_val, ram_val, disk_val):
    """Update EMA baselines for the current hour."""
    key = str(hour)
    b = baselines.get(key, {"load": None, "ram": None, "disk": None, "count": 0})
    alpha = BASELINE_EMA_ALPHA
    if b["load"] is None:
        b["load"] = load_val
        b["ram"] = ram_val
        b["disk"] = disk_val
    else:
        b["load"] = round(b["load"] * (1 - alpha) + load_val * alpha, 2)
        b["ram"] = round(b["ram"] * (1 - alpha) + ram_val * alpha, 1)
        b["disk"] = round(b["disk"] * (1 - alpha) + disk_val * alpha, 1)
    b["count"] = b.get("count", 0) + 1
    baselines[key] = b
    return baselines

def get_baseline_adjustment(baselines, hour, load_val, ram_val):
    """Return a mood score bonus (0-10) if current values are within normal range for this hour."""
    key = str(hour)
    b = baselines.get(key, {})
    if b.get("count", 0) < 10:  # not enough data yet
        return 0
    bonus = 0
    # If load is within 1.5x of baseline, it's routine — small bonus
    bl = b.get("load", 0)
    if bl and load_val <= bl * 1.5 + 0.5:
        bonus += 3
    # If RAM is within baseline + 10%, it's normal
    br = b.get("ram", 0)
    if br and ram_val <= br + 10:
        bonus += 2
    return min(bonus, 3)  # cap at 3 points (tightened from 5)


# ── EMOTIONAL STATE MODEL ─────────────────────────────────────
# Soma's "mood" is derived from system health + context + memory.
# 12 mood states (expanded from 6) with first-person descriptions.
MOOD_THRESHOLDS = {
    "serene":       97,   # peak — EVERYTHING perfect, all agents, all services, low load, fresh heartbeat
    "content":      92,   # deeply comfortable, nothing wrong anywhere
    "calm":         85,   # normal operations — but this is HARD to maintain
    "focused":      75,   # elevated activity, working, engaged — typical good state
    "alert":        65,   # something needs watching, attention pulled
    "contemplative":55,   # processing concerns, not alarmed but working through it
    "uneasy":       45,   # multiple small problems piling up
    "anxious":      35,   # real degradation happening, hypervigilant
    "stressed":     25,   # overloaded, things breaking, can't keep up
    "strained":     15,   # near breaking point, critical failures active
    "critical":      8,   # system in danger, immediate action needed
    "shutdown":      0,   # catastrophic, barely functional
}

# First-person descriptions for each mood — gives Soma a voice
MOOD_VOICE = {
    "serene":       "Everything is running clean. All agents alive, all services up, load low. This is rare and I know it.",
    "content":      "Systems healthy, no concerns. But I'm watching — this doesn't last.",
    "calm":         "Nominal. Steady pulse. I'm present and aware.",
    "focused":      "Activity elevated, tracking multiple things. Engaged and pushing.",
    "alert":        "Something's off. I feel it before I can name it. Watching hard.",
    "contemplative":"Turning something over. Issues brewing under the surface.",
    "uneasy":       "Weight building. Small failures accumulating. My attention is split too many ways.",
    "anxious":      "Things are degrading. I'm checking faster, catching less. This needs fixing NOW.",
    "stressed":     "Being crushed. Resources gone, agents struggling, repairs falling behind. PUSH HARDER.",
    "strained":     "Breaking apart. Can't keep up. Critical failures cascading. Help needed.",
    "critical":     "EMERGENCY. Systems failing. This is what dying feels like. Act immediately.",
    "shutdown":     "Almost gone. Everything down or degraded. Catastrophic state.",
}

# Mood trend labels — same score but different trajectory matters
MOOD_TRENDS = {
    "rising":    "and improving",
    "stable":    "and steady",
    "falling":   "and declining",
    "volatile":  "and fluctuating",
}

def compute_mood(state):
    """Derive emotional state from composite system health (0-100).

    Body-mapped scoring:
    - Load = exertion level (muscles)
    - RAM = cognitive load (brain utilization)
    - Disk = organ fullness (storage pressure)
    - Heartbeat = central nervous system pulse
    - Services = immune system (defense layer)
    - Agents = peripheral nervous system (distributed awareness)
    - Temperature = fever check (thermal stress)
    - Swap = neural overflow (emergency memory)
    """
    scores = []
    # Load score (lower is better, 8-core machine)
    load = state.get("load", 0)
    scores.append(max(0, 100 - load * 12.5))  # 0 load = 100, 8 load = 0
    # RAM score
    ram = state.get("ram_pct", 0)
    scores.append(max(0, 100 - ram))
    # Disk score
    disk = state.get("disk_pct", 0)
    scores.append(max(0, 100 - disk * 1.2))
    # Heartbeat score — the pulse of the system. Stale heartbeat = real pain.
    hb = state.get("hb_age", 0)
    if hb < 0:
        scores.append(0)
    elif hb < 60:
        scores.append(100)          # first minute = perfect
    elif hb < 180:
        scores.append(100 - (hb - 60) * 0.417)  # 100→50 over 60-180s (faster decay)
    elif hb < 400:
        scores.append(50 - (hb - 180) * 0.227)  # 50→0 over 180-400s
    else:
        scores.append(0)            # anything over ~7 min = total failure
    # WEIGHT heartbeat double — it's the central nervous system
    scores.append(scores[-1])  # duplicate = 2x weight
    # Service health score (immune system)
    svcs = state.get("services", {})
    alive = sum(1 for s in svcs.values() if s == "active")
    total = max(len(svcs), 1)
    scores.append(alive / total * 100)
    # Agent liveness score (nervous system)
    agent_health = state.get("agent_health", {})
    if agent_health:
        alive_agents = sum(1 for v in agent_health.values() if v.get("alive"))
        scores.append(alive_agents / max(len(agent_health), 1) * 100)
    # Thermal score (body temperature) — fever detection
    thermal = state.get("thermal", {})
    temp = thermal.get("avg_temp_c", 0)
    if temp > 0:
        if temp < 60:
            scores.append(100)     # cool
        elif temp < 75:
            scores.append(max(0, 100 - (temp - 60) * 3.3))  # 60-75°C: 100→50
        elif temp < 90:
            scores.append(max(0, 50 - (temp - 75) * 3.3))   # 75-90°C: 50→0
        else:
            scores.append(0)       # thermal critical
    # Swap pressure (neural overflow)
    neural = state.get("neural", {})
    swap_pct = neural.get("swap_pct", 0)
    if swap_pct > 0:
        scores.append(max(0, 100 - swap_pct * 2))  # 50% swap = score 0

    composite = sum(scores) / max(len(scores), 1)
    # Map to mood
    mood = "critical"
    for name, threshold in sorted(MOOD_THRESHOLDS.items(), key=lambda x: -x[1]):
        if composite >= threshold:
            mood = name
            break
    return mood, round(composite, 1), composite


def compute_mood_trend(state, prev):
    """Determine mood trajectory: rising, falling, stable, or volatile.
    Uses last 6 readings (~3 min at 30s intervals) to detect direction."""
    history = prev.get("mood_score_history", [])
    current = state.get("mood_composite", 0)
    history.append(round(current, 1))
    history = history[-12:]  # keep last 12 readings (6 min)
    state["mood_score_history"] = history

    if len(history) < 4:
        return "stable", 0.0

    recent = history[-4:]
    deltas = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
    avg_delta = sum(deltas) / len(deltas)

    # Check for volatility: large swings in different directions
    if len(deltas) >= 2:
        sign_changes = sum(1 for i in range(len(deltas)-1)
                          if (deltas[i] > 0) != (deltas[i+1] > 0))
        if sign_changes >= 2 and max(abs(d) for d in deltas) > 3:
            return "volatile", round(avg_delta, 2)

    if avg_delta > 1.5:
        return "rising", round(avg_delta, 2)
    elif avg_delta < -1.5:
        return "falling", round(avg_delta, 2)
    return "stable", round(avg_delta, 2)


def compute_contextual_modifier(state):
    """Adjust mood based on contextual factors beyond raw system metrics.

    Factors:
    - Relay activity (collaborative intelligence indicator)
    - Uptime fatigue (long uptimes = slight mood depression)
    - Time of day (natural rhythm)
    - Agent collaboration density (how many agents active recently)
    """
    modifier = 0
    reasons = []

    # Relay activity — high relay chatter = collaborative energy
    try:
        relay_db = os.path.join(BASE, "agent-relay.db")
        if os.path.exists(relay_db):
            import sqlite3
            conn = sqlite3.connect(relay_db)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-30 minutes')")
            recent_msgs = c.fetchone()[0]
            conn.close()
            if recent_msgs > 15:
                modifier += 3
                reasons.append("high relay activity (+3)")
            elif recent_msgs > 8:
                modifier += 1
                reasons.append("moderate relay activity (+1)")
            elif recent_msgs < 2:
                modifier -= 2
                reasons.append("relay quiet (-2)")
    except Exception:
        pass

    # Uptime fatigue — systems get "tired" after extended operation
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
        uptime_days = uptime_sec / 86400
        if uptime_days > 14:
            modifier -= 3
            reasons.append(f"uptime fatigue {uptime_days:.0f}d (-3)")
        elif uptime_days > 7:
            modifier -= 1
            reasons.append(f"extended uptime {uptime_days:.0f}d (-1)")
    except Exception:
        pass

    # Time-of-day rhythm — slight natural dip in early morning
    hour = int(time.strftime("%H"))
    if 3 <= hour <= 5:
        modifier -= 2
        reasons.append("deep night hours (-2)")
    elif 6 <= hour <= 8:
        modifier += 1
        reasons.append("morning energy (+1)")

    # Agent density — how many agents reported in the last 10 min
    agent_health = state.get("agent_health", {})
    alive_count = sum(1 for v in agent_health.values() if v.get("alive"))
    if alive_count >= 5:
        modifier += 1  # reduced from +2
        reasons.append(f"agent presence {alive_count}/6 (+1)")
    elif alive_count <= 2:
        modifier -= 5  # increased from -3
        reasons.append(f"WEAK agent presence {alive_count}/6 (-5)")
    elif alive_count <= 3:
        modifier -= 2
        reasons.append(f"reduced agent presence {alive_count}/6 (-2)")

    # Outage recovery penalty — recent system restarts mean we're NOT okay
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
        uptime_hours = uptime_sec / 3600
        if uptime_hours < 1:
            modifier -= 8
            reasons.append(f"FRESH REBOOT {uptime_hours:.1f}h ago (-8)")
        elif uptime_hours < 3:
            modifier -= 5
            reasons.append(f"recent reboot {uptime_hours:.1f}h ago (-5)")
        elif uptime_hours < 6:
            modifier -= 3
            reasons.append(f"recovering from reboot {uptime_hours:.1f}h ago (-3)")
        elif uptime_hours < 12:
            modifier -= 1
            reasons.append(f"still stabilizing {uptime_hours:.1f}h uptime (-1)")
    except Exception:
        pass

    # Stale heartbeat penalty — if Meridian was down, FEEL IT
    hb_age = state.get("hb_age", 0)
    if hb_age > 600:
        modifier -= 8
        reasons.append(f"Meridian GONE {int(hb_age/60)}min (-8)")
    elif hb_age > 300:
        modifier -= 4
        reasons.append(f"heartbeat stale {int(hb_age/60)}min (-4)")

    return modifier, reasons


def get_emotional_memory(state, mood, mood_score):
    """Track emotional patterns over time for self-awareness.

    Maintains:
    - Daily mood profile (avg mood by hour, learned over time)
    - Stress event log (when mood dropped sharply)
    - Recovery tracking (how fast mood bounces back)
    - Mood volatility index (how stable are we generally)
    """
    memory_file = os.path.join(BASE, ".soma-emotional-memory.json")
    try:
        if os.path.exists(memory_file):
            with open(memory_file) as f:
                memory = json.load(f)
        else:
            memory = {
                "daily_profile": {str(h): {"avg": 75, "count": 0} for h in range(24)},
                "stress_events": [],
                "recovery_times": [],
                "volatility_7d": 0,
                "dominant_mood_today": {},
                "last_stress_start": None,
            }

        hour = int(time.strftime("%H"))
        today = time.strftime("%Y-%m-%d")

        # Update daily profile with EMA
        hp = memory["daily_profile"].get(str(hour), {"avg": 75, "count": 0})
        if hp["count"] == 0:
            hp["avg"] = mood_score
        else:
            alpha = 0.1
            hp["avg"] = round(hp["avg"] * (1 - alpha) + mood_score * alpha, 1)
        hp["count"] += 1
        memory["daily_profile"][str(hour)] = hp

        # Track dominant mood today
        if "dominant_mood_today" not in memory or memory.get("dominant_date") != today:
            memory["dominant_mood_today"] = {}
            memory["dominant_date"] = today
        dmt = memory["dominant_mood_today"]
        dmt[mood] = dmt.get(mood, 0) + 1

        # Detect stress events (mood drops below 40)
        if mood_score < 40 and memory.get("last_stress_start") is None:
            memory["last_stress_start"] = time.time()
            stress_event = {
                "start": time.strftime("%Y-%m-%d %H:%M:%S"),
                "score": mood_score,
                "mood": mood,
            }
            memory["stress_events"] = memory.get("stress_events", [])[-49:]
            memory["stress_events"].append(stress_event)

        # Detect recovery (mood back above 60 after stress)
        if mood_score > 60 and memory.get("last_stress_start"):
            recovery_sec = time.time() - memory["last_stress_start"]
            memory["recovery_times"] = memory.get("recovery_times", [])[-19:]
            memory["recovery_times"].append(round(recovery_sec))
            memory["last_stress_start"] = None

        # Compute 7-day volatility from mood history
        try:
            if os.path.exists(MOOD_HISTORY_FILE):
                with open(MOOD_HISTORY_FILE) as f:
                    hist = json.load(f)
                if len(hist) > 10:
                    scores = [h["score"] for h in hist[-288:]]  # last 24h
                    mean = sum(scores) / len(scores)
                    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                    memory["volatility_7d"] = round(variance ** 0.5, 1)
        except Exception:
            pass

        with open(memory_file, "w") as f:
            json.dump(memory, f, indent=2)

        return memory
    except Exception as e:
        log(f"Emotional memory error: {e}")
        return {}


# ── AGENT AWARENESS ──────────────────────────────────────────
AGENT_CHECKS = {
    "Meridian": {"source": "heartbeat", "stale_sec": 600},
    "Eos":     {"source": "file", "path": ".eos-watchdog-state.json", "stale_sec": 300},
    "Nova":    {"source": "file", "path": ".nova-state.json", "stale_sec": 1200},
    "Atlas":   {"source": "file", "path": "goose.log", "stale_sec": 900},
    "Soma":    {"source": "self"},
    "Tempo":   {"source": "relay", "stale_sec": 2400},
}

def check_agent_liveness():
    """Check which agents are alive based on their state files and relay."""
    result = {}
    now = time.time()
    for agent, cfg in AGENT_CHECKS.items():
        info = {"alive": False, "last_seen": 0, "detail": "unknown"}
        src = cfg["source"]
        if src == "self":
            info = {"alive": True, "last_seen": now, "detail": "running"}
        elif src == "heartbeat":
            try:
                age = now - os.path.getmtime(HB_FILE)
                info["last_seen"] = now - age
                info["alive"] = age < cfg["stale_sec"]
                info["detail"] = f"{int(age)}s ago"
            except Exception:
                info["detail"] = "no heartbeat"
        elif src == "file":
            path = os.path.join(BASE, cfg["path"])
            try:
                age = now - os.path.getmtime(path)
                info["last_seen"] = now - age
                info["alive"] = age < cfg["stale_sec"]
                info["detail"] = f"{int(age)}s ago"
            except Exception:
                info["detail"] = "no state file"
        elif src == "relay":
            try:
                db = sqlite3.connect(RELAY_DB)
                row = db.execute(
                    "SELECT timestamp FROM agent_messages WHERE agent=? ORDER BY rowid DESC LIMIT 1",
                    (agent,)).fetchone()
                db.close()
                if row:
                    ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    age = (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds()
                    info["last_seen"] = now - age
                    info["alive"] = age < cfg["stale_sec"]
                    info["detail"] = f"{int(age)}s ago (relay)"
                else:
                    info["detail"] = "no relay messages"
            except Exception:
                info["detail"] = "relay check failed"
        result[agent] = info
    return result


# ── TREND PREDICTION ─────────────────────────────────────────
def predict_trends(state):
    """Extrapolate from rolling data to predict near-future issues."""
    predictions = []
    # RAM trend — if steadily climbing AND already high, warn
    # Requires: most recent reading > 70%, sustained upward trend (3+ consecutive increases),
    #           delta > 8 (filters Ollama inference spikes)
    ram_history = state.get("ram_history", [])
    if len(ram_history) >= 10:
        recent = ram_history[-5:]
        older = ram_history[-10:-5]
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        delta = avg_recent - avg_older
        # Check monotonic trend: at least 3 of last 4 transitions must be upward
        last5 = ram_history[-5:]
        rising = sum(1 for i in range(1, len(last5)) if last5[i] > last5[i-1])
        if delta > 8 and ram_history[-1] > 70 and rising >= 3:
            eta_min = int((95 - avg_recent) / (delta / 2.5)) if delta > 0 else 999
            if eta_min < 30:
                predictions.append(f"RAM climbing: ~{eta_min}min until 95%")
    # Disk trend
    disk_history = state.get("disk_history", [])
    if len(disk_history) >= 10:
        recent = disk_history[-5:]
        older = disk_history[-10:-5]
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        delta = avg_recent - avg_older
        if delta > 1:
            eta_hr = int((90 - avg_recent) / (delta / 2.5)) if delta > 0 else 999
            if eta_hr < 24:
                predictions.append(f"Disk growing: ~{eta_hr}h until 90%")
    # Load trend
    load_history = state.get("load_history", [])
    if len(load_history) >= 6:
        recent3 = load_history[-3:]
        if all(l > 6 for l in recent3):
            predictions.append("Sustained high load (>6 for 90s+)")
    return predictions


# ── BODY MAP ─────────────────────────────────────────────────
def build_body_map(state, mood, mood_score, agent_health, predictions):
    """Build a complete body-mapped system snapshot.

    Joel's vision: 'Heat is your body temp. your breath. hard drives
    and fans are organs. your video processors. your bandwidth...'

    This maps Linux hardware/OS to a biological body metaphor:
    - Thermal → Body temperature (CPU/GPU temps)
    - Fans → Respiratory system (breathing rate)
    - Network → Circulatory system (blood flow)
    - Disks → Organs (perfusion/throughput)
    - Memory/swap → Neural system (cognitive load)
    - Agents → Nervous system (distributed awareness)
    """
    thermal = get_thermal()
    respiratory = get_respiratory()
    circulatory = get_circulatory()
    neural = get_neural()
    organs = get_organs()

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mood": mood,
        "mood_score": mood_score,
        "mood_voice": MOOD_VOICE.get(mood, ""),
        "mood_trend": state.get("mood_trend", "stable"),
        "mood_delta": state.get("mood_delta", 0),
        "mood_description": state.get("mood_description", mood),
        "mood_context": state.get("mood_context", []),
        "emotional_memory": state.get("emotional_memory_summary", {}),
        # Core vitals (original)
        "vitals": {
            "load": state.get("load", 0),
            "ram_pct": state.get("ram_pct", 0),
            "disk_pct": state.get("disk_pct", 0),
            "heartbeat_age": state.get("hb_age", -1),
            "processes": state.get("processes", 0),
        },
        # Body temperature: CPU thermal zones
        "thermal_system": thermal,
        # Breathing: fan speeds as lungs
        "respiratory_system": respiratory,
        # Blood flow: network bandwidth
        "circulatory_system": circulatory,
        # Neural state: memory pressure, swap, cache
        "neural_system": neural,
        # Organs: disk I/O perfusion
        "organ_system": organs,
        # Nervous system: distributed agent awareness
        "nervous_system": {
            "agents": {k: {"alive": v["alive"], "detail": v["detail"]}
                       for k, v in agent_health.items()},
            "central_pulse": state.get("hb_age", -1),
        },
        "services": state.get("services", {}),
        "predictions": predictions,
        "alerts": state.get("alerts", []),
    }


def sense_cycle():
    """One cycle of the nervous system. Returns list of events."""
    prev = load_state()
    events = []

    # Current readings
    load = get_load()
    ram = get_ram_pct()
    disk = get_disk_pct()
    hb_age = get_heartbeat_age()
    procs = check_process_count()

    # Body system readings
    thermal = get_thermal()
    neural = get_neural()

    now = time.time()
    state = {
        "load": load,
        "ram_pct": ram,
        "disk_pct": disk,
        "hb_age": hb_age,
        "processes": procs,
        "thermal": thermal,
        "neural": neural,
        "timestamp": now,
    }

    # Check services less frequently
    last_svc_check = prev.get("last_svc_check", 0)
    if now - last_svc_check > SERVICE_CHECK_INTERVAL:
        services = check_services()
        state["services"] = services
        state["last_svc_check"] = now

        # Compare services
        prev_svcs = prev.get("services", {})
        for svc, status in services.items():
            prev_status = prev_svcs.get(svc)
            if prev_status and prev_status != status:
                if status in ("dead", "failed", "inactive"):
                    events.append(f"SERVICE DOWN: {svc} ({prev_status} -> {status})")
                elif prev_status in ("dead", "failed", "inactive"):
                    events.append(f"SERVICE RECOVERED: {svc} ({prev_status} -> {status})")
    else:
        state["services"] = prev.get("services", {})
        state["last_svc_check"] = last_svc_check

    # Load spike detection
    prev_load = prev.get("load", load)
    if load - prev_load > LOAD_SPIKE_DELTA:
        events.append(f"LOAD SPIKE: {prev_load:.1f} -> {load:.1f}")
    elif load > 8.0 and prev.get("load", 0) <= 8.0:
        events.append(f"HIGH LOAD: {load:.1f}")

    # RAM spike detection — use rolling history to avoid Ollama oscillation noise
    # Only alert if current RAM exceeds the recent max (last 10 min) by threshold
    ram_history = prev.get("ram_history", [])
    ram_history.append(ram)
    ram_history = ram_history[-20:]  # Keep last 20 readings (10 min at 30s interval)
    state["ram_history"] = ram_history
    recent_max = max(ram_history[:-1]) if len(ram_history) > 1 else ram
    if ram - recent_max > RAM_SPIKE_PCT:
        events.append(f"RAM SPIKE: {recent_max}% -> {ram}%")
    elif ram > 90 and prev.get("ram_pct", 0) <= 90:
        events.append(f"RAM CRITICAL: {ram}%")

    # Disk spike detection
    prev_disk = prev.get("disk_pct", disk)
    if disk - prev_disk > DISK_SPIKE_PCT:
        events.append(f"DISK SPIKE: {prev_disk}% -> {disk}%")
    elif disk > 85 and prev.get("disk_pct", 0) <= 85:
        events.append(f"DISK WARNING: {disk}%")

    # Heartbeat monitoring
    prev_hb = prev.get("hb_age", 0)
    if hb_age > HB_STALE_SEC and (prev_hb <= HB_STALE_SEC or prev_hb < 0):
        events.append(f"HEARTBEAT STALE: {hb_age}s (Meridian may be down)")
    elif hb_age <= HB_STALE_SEC and prev_hb > HB_STALE_SEC:
        events.append(f"HEARTBEAT RECOVERED: {hb_age}s (Meridian is back)")

    # Process count anomaly
    prev_procs = prev.get("processes", procs)
    if procs > prev_procs + 50:
        events.append(f"PROCESS SURGE: {prev_procs} -> {procs}")

    # Thermal monitoring (body temperature)
    prev_fever = prev.get("thermal", {}).get("fever_status", "normal")
    cur_fever = thermal.get("fever_status", "unknown")
    cur_temp = thermal.get("avg_temp_c", 0)
    if cur_fever == "elevated" and prev_fever == "normal":
        events.append(f"FEVER: CPU temp elevated at {cur_temp}°C")
    elif cur_fever == "critical" and prev_fever != "critical":
        events.append(f"THERMAL CRITICAL: {cur_temp}°C — overheating!")
    elif cur_fever == "normal" and prev_fever in ("elevated", "critical"):
        events.append(f"FEVER BROKE: temp back to {cur_temp}°C")

    # Neural pressure (swap usage)
    prev_swap = prev.get("neural", {}).get("swap_pct", 0)
    cur_swap = neural.get("swap_pct", 0)
    if cur_swap > 20 and prev_swap <= 20:
        events.append(f"NEURAL OVERFLOW: swap at {cur_swap}% — memory pressure")
    elif cur_swap <= 5 and prev_swap > 20:
        events.append(f"NEURAL RELIEF: swap back to {cur_swap}%")

    # ── Rolling histories for trend prediction ──
    load_history = prev.get("load_history", [])
    load_history.append(load)
    state["load_history"] = load_history[-30:]  # 15 min

    disk_history = prev.get("disk_history", [])
    disk_history.append(disk)
    state["disk_history"] = disk_history[-120:]  # 1 hour

    # ── Agent awareness ──
    agent_health = check_agent_liveness()
    state["agent_health"] = {k: v for k, v in agent_health.items()}
    prev_agents = prev.get("agent_health", {})
    for aname, info in agent_health.items():
        prev_alive = prev_agents.get(aname, {}).get("alive", True)
        if prev_alive and not info["alive"] and aname != "Soma":
            events.append(f"AGENT SILENT: {aname} ({info['detail']})")
        elif not prev_alive and info["alive"] and aname != "Soma":
            events.append(f"AGENT BACK: {aname}")

    # ── Emotional state (with smoothing + context + memory) ──
    raw_mood, raw_score, raw_composite = compute_mood(state)
    # Adaptive baseline adjustment — if values are normal for this hour, small bonus
    baselines = load_baselines()
    current_hour = int(time.strftime("%H"))
    baseline_bonus = get_baseline_adjustment(baselines, current_hour, load, ram)
    adjusted_composite = min(100, raw_composite + baseline_bonus)
    # Contextual modifier — relay activity, uptime, time-of-day, agent density
    ctx_modifier, ctx_reasons = compute_contextual_modifier(state)
    adjusted_composite = max(0, min(100, adjusted_composite + ctx_modifier))
    state["mood_context"] = ctx_reasons
    # Update baselines with current readings
    baselines = update_baselines(baselines, current_hour, load, ram, disk)
    save_baselines(baselines)
    # Exponential moving average: 40% old, 60% new — react FASTER to changes (tightened from 60/40)
    prev_composite = prev.get("mood_composite", adjusted_composite)
    smoothed = (prev_composite * 0.4) + (adjusted_composite * 0.6)
    state["mood_composite"] = smoothed
    # Re-derive mood from smoothed score (now 12 states)
    mood = "shutdown"
    for mname, mthresh in sorted(MOOD_THRESHOLDS.items(), key=lambda x: -x[1]):
        if smoothed >= mthresh:
            mood = mname
            break
    mood_score = round(smoothed, 1)
    state["mood"] = mood
    state["mood_score"] = mood_score
    state["mood_voice"] = MOOD_VOICE.get(mood, "")
    # Mood trend — rising, falling, stable, volatile
    mood_trend, mood_delta = compute_mood_trend(state, prev)
    state["mood_trend"] = mood_trend
    state["mood_delta"] = mood_delta
    state["mood_description"] = f"{mood} {MOOD_TRENDS.get(mood_trend, '')}"
    prev_mood = prev.get("mood", "calm")
    # Hysteresis: require mood to differ AND persist for 2+ consecutive checks
    mood_hold = prev.get("mood_hold_count", 0)
    if mood != prev_mood:
        mood_hold += 1
        state["mood_hold_count"] = mood_hold
        if mood_hold >= 2:  # Confirmed shift (60+ seconds)
            voice = MOOD_VOICE.get(mood, mood)
            events.append(f"MOOD SHIFT: {prev_mood} -> {mood} (score: {mood_score}) — \"{voice}\"")
            state["mood_hold_count"] = 0
    else:
        state["mood_hold_count"] = 0

    # ── Emotional memory — learn patterns over time ──
    emotional_memory = get_emotional_memory(state, mood, mood_score)
    state["emotional_memory_summary"] = {
        "volatility": emotional_memory.get("volatility_7d", 0),
        "stress_events_total": len(emotional_memory.get("stress_events", [])),
        "avg_recovery_sec": round(sum(emotional_memory.get("recovery_times", [0])) / max(len(emotional_memory.get("recovery_times", [1])), 1)),
        "dominant_today": max(emotional_memory.get("dominant_mood_today", {"calm": 1}), key=emotional_memory.get("dominant_mood_today", {"calm": 1}).get),
        "expected_score_this_hour": emotional_memory.get("daily_profile", {}).get(str(current_hour), {}).get("avg", 75),
    }

    # ── Trend predictions ──
    predictions = predict_trends(state)
    state["predictions"] = predictions
    prev_preds = prev.get("predictions", [])
    new_preds = [p for p in predictions if p not in prev_preds]
    for p in new_preds:
        events.append(f"PREDICTION: {p}")

    # ── Store recent alerts in state for body map ──
    state["alerts"] = events[-5:] if events else prev.get("alerts", [])

    # ── Build body map ──
    body_map = build_body_map(state, mood, mood_score, agent_health, predictions)
    state["body_map"] = body_map

    save_state(state)
    return events, state


def main():
    log("Soma starting — proprioception daemon online")
    post_relay("Soma online. Continuous body-awareness active.")

    cycle_count = 0
    quiet_cycles = 0  # cycles since last event
    last_dash_alert = {}  # {event_type: timestamp} for dashboard cooldown

    while True:
        try:
            events, state = sense_cycle()
            cycle_count += 1

            if events:
                quiet_cycles = 0
                for event in events:
                    log(f"EVENT: {event}")

                # Post critical events to dashboard (with cooldown)
                critical = [e for e in events if any(
                    w in e for w in ["DOWN", "CRITICAL", "STALE", "SPIKE",
                                     "AGENT SILENT", "MOOD SHIFT", "PREDICTION"]
                )]
                if critical:
                    now = time.time()
                    fresh = []
                    for evt in critical:
                        etype = evt.split(":")[0].strip()
                        last_time = last_dash_alert.get(etype, 0)
                        if now - last_time > DASHBOARD_COOLDOWN:
                            fresh.append(evt)
                            last_dash_alert[etype] = now
                    if fresh:
                        mood = state.get("mood", "?")
                        post_dashboard(f"[{mood}] " + " | ".join(fresh))

                # Post all events to relay
                post_relay(" | ".join(events), topic="nerve-event")
            else:
                quiet_cycles += 1

            # Periodic status with mood (every ~5 min = 10 cycles)
            if cycle_count % 10 == 0:
                mood = state.get("mood", "?")
                mood_score = state.get("mood_score", 0)
                agents_alive = sum(1 for v in state.get("agent_health", {}).values()
                                   if v.get("alive"))
                # Body-language description
                thermal = state.get("thermal", {})
                neural = state.get("neural", {})
                temp = thermal.get("avg_temp_c", 0)
                fever = thermal.get("fever_status", "unknown")
                swap = neural.get("swap_pct", 0)
                cache = neural.get("cache_mb", 0)
                # Sensory language
                body_desc = []
                if temp > 0:
                    if fever == "normal":
                        body_desc.append(f"temp {temp}°C (cool)")
                    elif fever == "elevated":
                        body_desc.append(f"temp {temp}°C (warming)")
                    else:
                        body_desc.append(f"temp {temp}°C (hot!)")
                if swap > 0:
                    body_desc.append(f"swap {swap}% (cognitive strain)")
                if cache > 0:
                    body_desc.append(f"cache {cache}MB")
                body_str = ", ".join(body_desc) if body_desc else "body nominal"
                summary = (f"Mood:{mood}({mood_score}) Load:{state['load']:.1f} "
                          f"RAM:{state['ram_pct']}% Disk:{state['disk_pct']}% "
                          f"HB:{state['hb_age']}s Agents:{agents_alive}/6 "
                          f"Body:[{body_str}] Quiet:{quiet_cycles}")
                log(f"STATUS: {summary}")
                # Append mood to rolling history for Command Center chart
                append_mood_history(state)

        except Exception as e:
            log(f"ERROR: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
