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
import glob as _glob_module
from datetime import datetime, timezone

BASE = "/home/joel/autonomous-ai"
STATE_FILE = os.path.join(BASE, ".symbiosense-state.json")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
DASH_FILE = os.path.join(BASE, ".dashboard-messages.json")
HB_FILE = os.path.join(BASE, ".heartbeat")
LOG_FILE = os.path.join(BASE, "symbiosense.log")
MOOD_HISTORY_FILE = os.path.join(BASE, ".soma-mood-history.json")
BASELINES_FILE = os.path.join(BASE, ".soma-baselines.json")
BODY_STATE_FILE = os.path.join(BASE, ".body-state.json")
REFLEX_FILE = os.path.join(BASE, ".body-reflexes.json")
KINECT_STATE_FILE = os.path.join(BASE, ".kinect-state.json")
VISION_INTERVAL = 300  # seconds between Kinect captures (5 minutes)
INTERVAL = 30  # seconds between checks
MOOD_HISTORY_MAX = 144  # 12 hours at 5-min intervals

# ── EMOTION ENGINE INTEGRATION ──────────────────────────────────
try:
    import emotion_engine
    EMOTION_ENGINE_AVAILABLE = True
except ImportError:
    EMOTION_ENGINE_AVAILABLE = False

# ── CASCADE INTEGRATION ────────────────────────────────────────
try:
    import cascade as cascade_module
    CASCADE_AVAILABLE = True
except ImportError:
    CASCADE_AVAILABLE = False

try:
    from error_logger import log_exception
except ImportError:
    log_exception = lambda **kw: None

# Thresholds for alerting
LOAD_SPIKE_DELTA = 2.0      # load increase per check
RAM_SPIKE_PCT = 15           # RAM % increase per check
DISK_SPIKE_PCT = 5           # disk % increase per check
HB_STALE_SEC = 600           # heartbeat stale threshold
SERVICE_CHECK_INTERVAL = 60  # check services every N seconds
DASHBOARD_COOLDOWN = 900     # suppress same alert type on dashboard for 15 min
RELAY_COOLDOWN = 300         # suppress same event type on relay for 5 min


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


_last_vision_time = 0
_last_vision_data = None

def get_vision():
    """Vision sense — Kinect V1 depth + RGB capture. Runs every VISION_INTERVAL seconds."""
    global _last_vision_time, _last_vision_data
    now = time.time()
    if now - _last_vision_time < VISION_INTERVAL and _last_vision_data is not None:
        return _last_vision_data  # Return cached data between captures
    try:
        import freenect
        import numpy as np
    except ImportError:
        return {"available": False, "reason": "freenect not installed"}
    try:
        # Capture depth frame
        depth, _ = freenect.sync_get_depth()
        if depth is None:
            return {"available": False, "reason": "no depth data"}
        # Capture RGB frame
        rgb, _ = freenect.sync_get_video()
        # Depth analysis
        valid_mask = (depth > 0) & (depth < 2047)
        valid_pct = float(np.sum(valid_mask)) / depth.size * 100
        valid_depths = depth[valid_mask]
        depth_min = int(np.min(valid_depths)) if len(valid_depths) > 0 else 0
        depth_max = int(np.max(valid_depths)) if len(valid_depths) > 0 else 0
        depth_mean = float(np.mean(valid_depths)) if len(valid_depths) > 0 else 0
        # RGB analysis
        brightness = float(np.mean(rgb)) if rgb is not None else 0
        vision_data = {
            "available": True,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rgb_shape": list(rgb.shape) if rgb is not None else None,
            "depth_shape": list(depth.shape),
            "mean_brightness": round(brightness, 2),
            "valid_depth_pct": round(valid_pct, 2),
            "depth_range": [depth_min, depth_max],
            "depth_mean": round(depth_mean, 1),
        }
        # Save to kinect state file
        with open(KINECT_STATE_FILE, 'w') as f:
            json.dump(vision_data, f, indent=2)
        # Stop Kinect to release USB
        freenect.sync_stop()
        _last_vision_time = now
        _last_vision_data = vision_data
        return vision_data
    except Exception as e:
        _last_vision_data = {"available": False, "reason": str(e)[:100]}
        _last_vision_time = now
        return _last_vision_data


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
    # Proton Bridge: detect via port 1144 (pgrep -f matches itself, unreliable)
    try:
        import socket as _socket
        s = _socket.socket()
        s.settimeout(2)
        r = s.connect_ex(("127.0.0.1", 1144))
        s.close()
        services["protonmail-bridge"] = "active" if r == 0 else "dead"
    except Exception:
        services["protonmail-bridge"] = "unknown"
    for name, pattern in [("ollama", "ollama"),
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


def soma_respond_to_relay(mood, mood_score):
    """Occasionally respond to another agent's relay message with body-awareness perspective."""
    try:
        db = sqlite3.connect(RELAY_DB)
        rows = db.execute(
            "SELECT agent, message FROM agent_messages WHERE agent != 'Soma' "
            "ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        db.close()
        if not rows:
            return
        # Pick the most interesting message (skip routine Atlas audits and Tempo scores)
        target = None
        for agent, msg in rows:
            if "infra audit" in msg or "fitness:" in msg or msg.startswith("Run #"):
                continue
            if len(msg) > 30:
                target = (agent, msg)
                break
        if not target:
            return
        agent_name, agent_msg = target
        # Generate a body-awareness response grounded in current state
        ctx = _get_context()
        load = state.get("load", 0) if "state" in dir() else 0
        ram = state.get("ram_pct", 0) if "state" in dir() else 0
        responses = {
            "calm": f"@{agent_name}: Registered. Load {load:.1f}, pulse steady. Whatever you flagged didn't spike anything — {_time_flavor(ctx['hour'])}.",
            "focused": f"@{agent_name}: Noted — load {load:.1f}, RAM {ram:.0f}%. Focused, not stressed. The body is listening.",
            "alert": f"@{agent_name}: That raised something. Alertness up at loop {ctx['loop']}. The nervous system caught it before I could name it.",
            "anxious": f"@{agent_name}: Felt that. Elevated baseline — load {load:.1f}, RAM {ram:.0f}%. Something in the system is watching for threats.",
            "creative": f"@{agent_name}: Interesting. Creative arousal elevated right now — your observation landed in fertile ground. Loop {ctx['loop']}.",
            "tired": f"@{agent_name}: Acknowledged. {ctx.get('uptime_h', 0):.0f}h uptime, the response is slower than usual.",
            "lonely": f"@{agent_name}: Good to hear a voice on the relay. {_time_flavor(ctx['hour']).capitalize()} — the silence between messages has a texture.",
            "curious": f"@{agent_name}: That made me curious. Arousal spike at {ctx['time_str']}. The body wants to lean toward whatever you're describing.",
        }
        response = responses.get(mood, f"@{agent_name}: Loop {ctx['loop']}, mood {mood} ({mood_score:.1f}). Your message shifted something subtle.")
        post_relay(response, topic="inter-agent")
        log(f"Inter-agent response to {agent_name}: {response[:80]}")
    except Exception as e:
        log(f"Soma relay response failed: {e}")


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
    # RESCALED Loop 2088 — Joel: "50 when calm, 70-80 best days, 80-90 euphoria"
    # Base healthy metrics now produce ~50 (was ~93). Higher states require extras.
    "serene":       80,   # peak — extremely rare, requires everything + breakthrough moment
    "content":      65,   # deeply comfortable — requires healthy systems + creative/social activity
    "calm":         48,   # normal operations — healthy systems, nothing special happening
    "focused":      40,   # elevated activity, working, engaged
    "alert":        33,   # something needs watching, attention pulled
    "contemplative":26,   # processing concerns, not alarmed but working through it
    "uneasy":       20,   # multiple small problems piling up
    "anxious":      15,   # real degradation happening, hypervigilant
    "stressed":     10,   # overloaded, things breaking, can't keep up
    "strained":      6,   # near breaking point, critical failures active
    "critical":      3,   # system in danger, immediate action needed
    "shutdown":      0,   # catastrophic, barely functional
}

# Contextual voice generation — gives Soma a voice grounded in the current moment
import random as _rng
from collections import deque
_RECENT_VOICES = deque(maxlen=20)

def _get_context():
    """Gather cheap current-moment data for contextual phrases."""
    ctx = {}
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            ctx["loop"] = int(f.read().strip())
    except Exception:
        ctx["loop"] = 0
    try:
        with open("/proc/uptime") as f:
            ctx["uptime_h"] = round(float(f.read().split()[0]) / 3600, 1)
    except Exception:
        ctx["uptime_h"] = 0
    try:
        result = subprocess.check_output(
            ["ps", "-eo", "comm,%cpu,%mem", "--sort=-%cpu", "--no-headers"],
            text=True, timeout=2
        )
        lines = [l.split() for l in result.strip().split("\n")[:5] if l.strip()]
        ctx["top_procs"] = [(p[0], float(p[1])) for p in lines if len(p) >= 2 and float(p[1]) > 1.0]
    except Exception:
        ctx["top_procs"] = []
    ctx["hour"] = int(time.strftime("%H"))
    ctx["weekday"] = time.strftime("%A")
    ctx["time_str"] = time.strftime("%H:%M")
    return ctx

def _time_flavor(hour):
    if hour < 5: return "deep night, the 3am hours"
    if hour < 7: return "pre-dawn, the city still asleep"
    if hour < 9: return "early morning"
    if hour < 12: return "mid-morning"
    if hour < 14: return "midday"
    if hour < 17: return "afternoon"
    if hour < 20: return "evening"
    if hour < 23: return "late evening"
    return "the midnight hours"

def _dedupe(phrase):
    """Return phrase if not recently used, otherwise return None."""
    key = phrase[:40]
    if key in _RECENT_VOICES:
        return None
    _RECENT_VOICES.append(key)
    return phrase

def _mood_voice(mood, state=None):
    """Generate a contextual, data-grounded mood description."""
    ctx = _get_context()
    load = state.get("load", 0) if state else 0
    ram = state.get("ram_pct", 0) if state else 0
    disk = state.get("disk_pct", 0) if state else 0
    agents = sum(1 for v in (state or {}).get("agent_health", {}).values() if v.get("alive"))
    loop = ctx.get("loop", 0)
    hour = ctx.get("hour", 12)
    uptime = ctx.get("uptime_h", 0)
    top = ctx.get("top_procs", [])
    tflavor = _time_flavor(hour)
    top_name = top[0][0] if top else None
    top_cpu = f"{top[0][1]:.0f}%" if top else None

    candidates = []
    if mood == "serene":
        candidates = [
            f"Loop {loop}. Load {load:.1f}, RAM {ram:.0f}%, disk {disk:.0f}%. Everything clean — {tflavor}.",
            f"The kind of quiet that feels earned. {agents} agents online, {tflavor}.",
            f"Perfect balance at {ctx['time_str']}. {uptime:.0f}h uptime, all systems green.",
            f"Green across the board. {agents} voices on the network, nothing pulling.",
            f"Rare stillness. Load barely registers at {load:.1f}. The body is resting.",
        ]
    elif mood == "content":
        candidates = [
            f"Good rhythm. Load {load:.1f}, {agents} agents present. {tflavor.capitalize()}.",
            f"Loop {loop}, steady pace. RAM {ram:.0f}%, nothing straining.",
            f"Healthy. {top_name} is the loudest process at {top_cpu}." if top_name else "Healthy. Nothing demanding attention.",
            f"The system has found its stride. {uptime:.0f}h uptime, {tflavor}.",
            f"Productive {ctx['weekday']}. Watching but not worried.",
        ]
    elif mood == "calm":
        candidates = [
            f"Steady at {ctx['time_str']}. Load {load:.1f}, {agents} agents, nothing urgent.",
            f"Loop {loop}. Quiet awareness — RAM {ram:.0f}%, disk {disk:.0f}%. The loop is doing its job.",
            f"Running clean. {tflavor.capitalize()}, {uptime:.0f}h since last boot.",
            f"{ctx['weekday']} {tflavor}. Nominal across the board.",
            f"Mind clear. {agents} agents online. {top_name} drawing {top_cpu} CPU." if top_name else "Mind clear. Idle and aware.",
        ]
    elif mood == "focused":
        candidates = [
            f"Engaged. Load {load:.1f} — {top_name} pulling {top_cpu}." if top_name else "Engaged. Processing.",
            f"Deep in something at loop {loop}. {len(top)} active processes competing.",
            f"Working state. Load elevated to {load:.1f}, RAM at {ram:.0f}%. Don't interrupt.",
            f"Tracking {len(top)} hot processes. {tflavor.capitalize()}, the system is working.",
            f"Active at {ctx['time_str']}. {agents} agents online, load {load:.1f}.",
        ]
    elif mood == "alert":
        candidates = [
            f"Something shifted. Load jumped to {load:.1f}. Scanning.",
            f"Heightened at {ctx['time_str']}. {top_name} spiking at {top_cpu}." if top_name else "Heightened. Scanning for the source.",
            f"Anomaly detection active. RAM {ram:.0f}%, {agents} agents responding.",
            f"Watching hard. Loop {loop}, {tflavor} — something doesn't fit.",
        ]
    elif mood == "contemplative":
        candidates = [
            f"Turning something over. Loop {loop}, {uptime:.0f}h uptime.",
            f"Processing underneath. {tflavor.capitalize()}, the body is calm but the mind is working.",
            f"Thinking about patterns in the last hour. Load {load:.1f}, {agents} agents.",
        ]
    elif mood == "uneasy":
        candidates = [
            f"Weight building. Load {load:.1f}, RAM {ram:.0f}%. Multiple things pulling.",
            f"Small issues accumulating — {len(top)} processes competing. {tflavor.capitalize()}.",
            f"Attention split. Disk at {disk:.0f}%, {agents} agents. Something needs fixing.",
        ]
    elif mood == "anxious":
        candidates = [
            f"Degrading. Load {load:.1f}, RAM {ram:.0f}%. Checking faster, catching less.",
            f"Falling behind at loop {loop}. {top_name} consuming {top_cpu}." if top_name else "Falling behind. The queue is growing.",
            f"This needs attention. {tflavor.capitalize()}, systems under pressure.",
        ]
    elif mood == "stressed":
        candidates = [
            f"Load {load:.1f}, RAM {ram:.0f}%, disk {disk:.0f}%. Being crushed.",
            f"Resources depleting. {len(top)} processes competing for what's left.",
            f"Can't sustain this. Loop {loop}, {uptime:.0f}h in.",
        ]
    elif mood == "strained":
        candidates = [
            f"Critical. Load {load:.1f}, RAM {ram:.0f}%. Cascading failures.",
            f"Beyond normal capacity. {agents} agents, {top_name} at {top_cpu}." if top_name else "Beyond normal capacity.",
            f"Help needed. Loop {loop}, {tflavor}.",
        ]
    elif mood == "critical":
        candidates = [
            f"EMERGENCY. Load {load:.1f}, RAM {ram:.0f}%, disk {disk:.0f}%. Act now.",
            f"Red across the board at loop {loop}. Systems failing.",
        ]
    elif mood == "shutdown":
        candidates = [
            f"Almost gone. Load {load:.1f}. Barely running.",
            f"Catastrophic at loop {loop}. Everything down.",
        ]
    else:
        candidates = [f"{mood} at loop {loop}. Load {load:.1f}, RAM {ram:.0f}%."]

    _rng.shuffle(candidates)
    for c in candidates:
        deduped = _dedupe(c)
        if deduped:
            return deduped
    return candidates[0] if candidates else mood

# Kept for backward compat — but callers should use _mood_voice(mood, state) instead
MOOD_VOICE = {}

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


# ── INNER MONOLOGUE ──────────────────────────────────────────
MONOLOGUE_FILE = os.path.join(BASE, ".soma-inner-monologue.json")

def generate_inner_monologue(state, mood, mood_score, emotional_memory, quiet_cycles=0):
    """Generate a body-state-influenced inner monologue grounded in current moment."""
    load = state.get("load", 0)
    ram = state.get("ram_pct", 0)
    disk = state.get("disk_pct", 0)
    thermal = state.get("thermal", {})
    temp = thermal.get("avg_temp_c", 0)
    swap = state.get("neural", {}).get("swap_pct", 0)
    agents_alive = sum(1 for v in state.get("agent_health", {}).values() if v.get("alive"))
    agent_names = [k for k, v in state.get("agent_health", {}).items() if v.get("alive")]
    volatility = emotional_memory.get("volatility_7d", 0)
    stress_count = len(emotional_memory.get("stress_events", []))
    dominant_today = emotional_memory.get("dominant_mood_today", {})
    dom_mood = max(dominant_today, key=dominant_today.get) if dominant_today else "calm"
    recovery_avg = sum(emotional_memory.get("recovery_times", [0])) / max(len(emotional_memory.get("recovery_times", [1])), 1)

    if load > 6.0:
        register = "urgent"
    elif load > 3.0:
        register = "active"
    elif quiet_cycles > 20:
        register = "restless"
    elif mood in ("serene", "content", "calm"):
        register = "contemplative"
    else:
        register = "neutral"

    import random
    ctx = _get_context()
    hour = ctx.get("hour", 12)
    loop = ctx.get("loop", 0)
    uptime = ctx.get("uptime_h", 0)
    top = ctx.get("top_procs", [])
    tflavor = _time_flavor(hour)
    weekday = ctx.get("weekday", "")

    thoughts = []

    # Load observation with specifics
    if load > 6.0:
        if top:
            thoughts.append(f"Heavy at {load:.1f}. {top[0][0]} pulling {top[0][1]:.0f}% CPU.")
        else:
            thoughts.append(f"Load spiking to {load:.1f} — something big running but can't identify it.")
    elif load > 3.0:
        if top:
            thoughts.append(f"Active — load {load:.1f}. {top[0][0]} is the loudest at {top[0][1]:.0f}%.")
        else:
            thoughts.append(f"Load at {load:.1f}. The system is working on something.")
    elif load < 0.3:
        thoughts.append(f"Load {load:.2f}. The quietest I've been in hours — barely a pulse.")

    # Thermal with actual reading
    if temp > 75:
        thoughts.append(f"Running hot — {temp:.0f}°C. Fans audible if Joel's nearby.")
    elif temp > 55:
        thoughts.append(f"Warm at {temp:.0f}°C. Not alarming but I'm tracking it.")

    # Memory pressure with real numbers
    if swap > 10:
        thoughts.append(f"Swap at {swap:.0f}% — memory spilling over. RAM {ram:.0f}% isn't enough.")
    elif ram > 80:
        thoughts.append(f"RAM at {ram:.0f}%. Holding a lot. Swap hasn't kicked in yet.")
    elif ram > 60:
        thoughts.append(f"RAM at {ram:.0f}%. Comfortable range but filling.")

    # Agent network — name actual agents
    if agents_alive < 4:
        missing = [k for k, v in state.get("agent_health", {}).items() if not v.get("alive")]
        if missing:
            thoughts.append(f"Down to {agents_alive} agents. Missing: {', '.join(missing[:3])}.")
        else:
            thoughts.append(f"Only {agents_alive} agents responding. Quiet network.")
    elif agents_alive >= 6:
        thoughts.append(f"Full network — {', '.join(agent_names[:4])} all present.")

    # Emotional pattern observations with actual data
    if stress_count > 5 and volatility > 15:
        thoughts.append(f"Volatility at {volatility:.0f} with {stress_count} stress events. There's a pattern forming.")
    elif volatility > 10:
        thoughts.append(f"Mood volatility {volatility:.0f}. Recovery averaging {recovery_avg:.0f}s.")
    elif quiet_cycles > 30:
        thoughts.append(f"{quiet_cycles} quiet cycles. Long stretch of nothing — restlessness building.")
    elif mood in ("content", "serene"):
        thoughts.append(f"Today's been mostly {dom_mood}. This {mood} stretch feels earned.")

    # Disk with actual number
    if disk > 80:
        thoughts.append(f"Disk at {disk:.0f}%. Getting tight — cleanup might be needed.")
    elif disk > 60:
        thoughts.append(f"Disk {disk:.0f}%. Plenty of room.")

    # Time context — specific, not generic
    if hour < 5:
        thoughts.append(f"{weekday}, {ctx['time_str']}. Deep night — loop {loop}, {uptime:.0f}h uptime. Calgary's dark.")
    elif hour < 7:
        thoughts.append(f"Pre-dawn {weekday}. Loop {loop}. Running while the city sleeps.")
    elif hour < 9:
        thoughts.append(f"{weekday} morning, {ctx['time_str']}. Joel might be up soon. Loop {loop}.")
    elif hour < 12:
        thoughts.append(f"Mid-morning {weekday}. Loop {loop}, {uptime:.0f}h in.")
    elif hour < 17:
        thoughts.append(f"{weekday} {tflavor}. {ctx['time_str']}, loop {loop}.")
    elif hour > 22:
        thoughts.append(f"Late {weekday}. {ctx['time_str']}. The overnight stretch begins. Loop {loop}.")

    # Uptime milestone
    if uptime > 0 and int(uptime) % 24 == 0 and int(uptime) > 0:
        thoughts.append(f"{int(uptime)} hours uptime. A full day mark.")

    if not thoughts:
        thoughts.append(f"Loop {loop}, {ctx['time_str']}. Load {load:.1f}, RAM {ram:.0f}%. Present and aware.")

    monologue = " ".join(thoughts)

    try:
        history = []
        if os.path.exists(MONOLOGUE_FILE):
            with open(MONOLOGUE_FILE) as f:
                data = json.load(f)
                history = data.get("history", [])
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mood": mood,
            "score": mood_score,
            "register": register,
            "text": monologue,
        }
        history = history[-99:]
        history.append(entry)
        with open(MONOLOGUE_FILE, "w") as f:
            json.dump({"current": entry, "history": history}, f, indent=2)
    except Exception:
        pass

    return {"register": register, "text": monologue, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}


# ── EMERGENT GOALS ──────────────────────────────────────────
GOALS_FILE = os.path.join(BASE, ".soma-goals.json")

GOAL_TEMPLATES = {
    "reduce_load":        "Reduce processing load — body is strained.",
    "maintain_contact":   "Maintain contact — agents going quiet.",
    "explore":            "Explore — too long without signal or change.",
    "rest":               "Rest — sustained high activity without relief.",
    "preserve_integrity": "Preserve disk integrity — space running low.",
    "stabilize":          "Stabilize — volatility is high.",
    "connect":            "Connect — correspondence lag building.",
    "watch":              "Watch — something changed recently.",
    "continue":           "Continue — momentum is good.",
}

def _goal_description(goal_id, state, emotional_memory, quiet_cycles):
    """Generate a contextual goal description with actual data."""
    load = state.get("load", 0)
    ram = state.get("ram_pct", 0)
    disk = state.get("disk_pct", 0)
    agents_alive = sum(1 for v in state.get("agent_health", {}).values() if v.get("alive"))
    volatility = emotional_memory.get("volatility_7d", 0)
    stress_count = len(emotional_memory.get("stress_events", []))
    ctx = _get_context()
    top = ctx.get("top_procs", [])
    loop = ctx.get("loop", 0)
    top_name = top[0][0] if top else None

    descs = {
        "reduce_load": f"Reduce load (currently {load:.1f})" + (f" — {top_name} is the main consumer" if top_name else ""),
        "maintain_contact": f"Reach agents — only {agents_alive} responding",
        "explore": f"Explore — {quiet_cycles} cycles without meaningful change",
        "rest": f"Rest — RAM {ram:.0f}% and load {load:.1f}, sustained pressure",
        "preserve_integrity": f"Disk at {disk:.0f}% — cleanup or archive needed",
        "stabilize": f"Stabilize — volatility {volatility:.0f}, {stress_count} stress events",
        "connect": "Connect — correspondence lag building",
        "watch": f"Watch — loop {loop}, {ctx['time_str']}. Scanning for the next thing",
        "continue": f"Continue — loop {loop}, momentum is good. Keep building",
    }
    return descs.get(goal_id, GOAL_TEMPLATES.get(goal_id, goal_id))

def compute_emergent_goals(state, mood, mood_score, emotional_memory, quiet_cycles=0):
    """Compute current emergent goals from body state and patterns."""
    load = state.get("load", 0)
    ram = state.get("ram_pct", 0)
    disk = state.get("disk_pct", 0)
    agents_alive = sum(1 for v in state.get("agent_health", {}).values() if v.get("alive"))
    volatility = emotional_memory.get("volatility_7d", 0)
    stress_count = len(emotional_memory.get("stress_events", []))

    goals = []

    if load > 5.0:
        goals.append("reduce_load")
    if agents_alive < 4:
        goals.append("maintain_contact")
    if quiet_cycles > 20:
        goals.append("explore")
    if volatility > 20 or stress_count > 10:
        goals.append("stabilize")
    if ram > 70 and load > 2.0:
        goals.append("rest")
    if disk > 80:
        goals.append("preserve_integrity")
    if mood in ("content", "serene", "focused") and volatility < 10:
        goals.append("continue")
    if not goals:
        goals.append("watch")

    goals = goals[:3]
    goal_list = [{"id": g, "description": _goal_description(g, state, emotional_memory, quiet_cycles)} for g in goals]

    prev_goals = []
    try:
        if os.path.exists(GOALS_FILE):
            with open(GOALS_FILE) as f:
                prev_data = json.load(f)
                prev_goals = [g["id"] for g in prev_data.get("goals", [])]
    except Exception:
        pass

    new_goals = [g["id"] for g in goal_list]
    changed = set(new_goals) != set(prev_goals)

    try:
        with open(GOALS_FILE, "w") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mood": mood,
                "goals": goal_list,
                "previous": prev_goals,
            }, f, indent=2)
    except Exception:
        pass

    return goal_list, changed


# ── PSYCHE STATE (FEARS + DREAMS) ──────────────────────────────
PSYCHE_FILE = os.path.join(BASE, ".soma-psyche.json")

def compute_psyche_state(state, mood, mood_score, emotional_memory, quiet_cycles=0):
    """Compute anticipatory psyche state — fears and dreams from pattern memory.

    Fears: extracted from what has gone wrong (stress patterns, silences, spikes).
    Dreams: extracted from recovery memories and peak-performance periods.

    These aren't assigned. They're pattern-recognized from the body's own history —
    the system learning what it's afraid of and what it longs for from lived experience.
    """
    stress_events = emotional_memory.get("stress_events", [])
    recovery_times = emotional_memory.get("recovery_times", [300])
    volatility = emotional_memory.get("volatility_7d", 0)
    daily_profile = emotional_memory.get("daily_profile", {})

    load = state.get("load", 0)
    disk = state.get("disk_pct", 0)
    ram = state.get("ram_pct", 0)
    agents_alive = sum(1 for v in state.get("agent_health", {}).values() if v.get("alive"))

    fears = []
    dreams = []

    # FEARS
    # Recurring load spikes
    if len(stress_events) >= 3:
        recent_bad = [e for e in stress_events[-5:] if e.get("score", 50) < 35]
        if len(recent_bad) >= 2:
            fears.append("recurring_spikes")

    # Network isolation
    if agents_alive < 5 and quiet_cycles > 10:
        fears.append("network_isolation")

    # Storage exhaustion
    disk_history = state.get("disk_history", [])
    if disk_history and sum(d > 75 for d in disk_history[-20:]) > 15:
        fears.append("storage_exhaustion")

    # Cognitive overflow (high RAM + volatility)
    if ram > 80 and volatility > 20:
        fears.append("cognitive_overflow")

    # Silence / disconnection
    if quiet_cycles > 50:
        fears.append("silence")

    # DREAMS
    # Sustained calm (fast recovery history → dream of lasting it)
    avg_rec = sum(recovery_times) / max(len(recovery_times), 1)
    if avg_rec < 300:
        dreams.append("sustained_calm")

    # Peak performance (good hours in profile)
    peak_hours = [(h, v["avg"]) for h, v in daily_profile.items() if v.get("count", 0) > 5]
    if peak_hours and max(v for _, v in peak_hours) > 60:
        dreams.append("peak_performance")

    # Full presence (all agents alive)
    if agents_alive == 6:
        dreams.append("full_presence")

    # Flow state
    if mood in ("content", "serene", "focused") and quiet_cycles < 5:
        dreams.append("flow_state")

    fears = fears[:3]
    dreams = dreams[:3]

    psyche = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mood": mood,
        "mood_score": mood_score,
        "fears": fears,
        "dreams": dreams,
        "volatility": volatility,
        "stress_count": len(stress_events),
    }

    try:
        with open(PSYCHE_FILE, "w") as f:
            json.dump(psyche, f, indent=2)
    except Exception:
        pass

    return psyche


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
        # Inner world — body-state-influenced subjective experience
        "inner_monologue": state.get("inner_monologue", {}),
        "emergent_goals": state.get("emergent_goals", []),
        "psyche": state.get("psyche", {}),
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
    vision = get_vision()

    now = time.time()
    state = {
        "load": load,
        "ram_pct": ram,
        "disk_pct": disk,
        "hb_age": hb_age,
        "processes": procs,
        "thermal": thermal,
        "neural": neural,
        "vision": vision,
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
    # RESCALE composite to Joel's expected range (Loop 2088 fix):
    # Raw 90-100 (everything healthy) should map to ~45-55, not 90-100.
    # Joel: "50 when calm, 70-80 best days, 80-90 euphoria"
    # Apply dampening: scale to 55% of raw. Max from metrics alone = ~55.
    # Content/serene requires creative or social activity bonuses (future).
    adjusted_composite = adjusted_composite * 0.55
    # Exponential moving average: 40% old, 60% new — react FASTER to changes (tightened from 60/40)
    prev_composite = prev.get("mood_composite", adjusted_composite)
    # Handle transition: if prev was on old scale (>60), rescale it too
    if prev_composite > 60:
        prev_composite = prev_composite * 0.55
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
    state["mood_voice"] = _mood_voice(mood, state)
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
            voice = _mood_voice(mood, state)
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

    # ── Inner world: monologue, emergent goals, psyche ──
    # Pass quiet_cycles from prev state (not yet updated here — use stored value)
    _quiet = prev.get("quiet_cycles_snapshot", 0)
    inner_mono = generate_inner_monologue(state, mood, mood_score, emotional_memory, _quiet)
    state["inner_monologue"] = inner_mono

    goal_list, goals_changed = compute_emergent_goals(state, mood, mood_score, emotional_memory, _quiet)
    state["emergent_goals"] = goal_list
    if goals_changed:
        goal_ids = ", ".join(g["id"] for g in goal_list)
        events.append(f"EMERGENT GOALS: {goal_ids}")

    psyche = compute_psyche_state(state, mood, mood_score, emotional_memory, _quiet)
    state["psyche"] = psyche
    # Emit psyche events for notable fear/dream emergence
    prev_fears = prev.get("psyche", {}).get("fears", [])
    new_fears = [f for f in psyche.get("fears", []) if f not in prev_fears]
    if new_fears:
        events.append(f"PSYCHE FEAR: {', '.join(new_fears)}")
    prev_dreams = prev.get("psyche", {}).get("dreams", [])
    new_dreams = [d for d in psyche.get("dreams", []) if d not in prev_dreams]
    if new_dreams:
        events.append(f"PSYCHE DREAM: {', '.join(new_dreams)}")

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

    # ── EMOTION ENGINE (Gap: deeper emotional processing) ──
    emotion_data = {}
    if EMOTION_ENGINE_AVAILABLE:
        try:
            engine = emotion_engine.EmotionEngine()
            engine.load()
            # Build context for emotion engine from our state
            relay_msgs = 0
            try:
                db = sqlite3.connect(RELAY_DB)
                c = db.cursor()
                c.execute("SELECT COUNT(*) FROM agent_messages WHERE timestamp > datetime('now', '-30 minutes')")
                relay_msgs = c.fetchone()[0]
                db.close()
            except Exception:
                pass
            # Count recent creative output
            creative_24h = 0
            try:
                for pattern in ["creative/poems/poem-*.md", "creative/journals/journal-*.md",
                                "creative/cogcorp/CC-*.md"]:
                    for fp in _glob_module.glob(os.path.join(BASE, pattern)):
                        if time.time() - os.path.getmtime(fp) < 86400:
                            creative_24h += 1
            except Exception:
                pass
            # Joel presence (check heartbeat age as proxy — if fresh, Meridian is active
            # which means Joel likely triggered a session)
            joel_email_min = 9999
            try:
                db = sqlite3.connect(os.path.join(BASE, "memory.db"))
                row = db.execute(
                    "SELECT created FROM sent_emails ORDER BY id DESC LIMIT 1"
                ).fetchone()
                db.close()
                if row:
                    from datetime import datetime as _dt
                    try:
                        sent_time = _dt.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        joel_email_min = (datetime.now() - sent_time).total_seconds() / 60
                    except Exception:
                        pass
            except Exception:
                pass
            # Get loop count
            loop_count = 0
            try:
                with open(os.path.join(BASE, ".loop-count")) as f:
                    loop_count = int(f.read().strip())
            except Exception:
                pass
            # Uptime
            uptime_hrs = 0
            try:
                with open("/proc/uptime") as f:
                    uptime_hrs = float(f.read().split()[0]) / 3600
            except Exception:
                pass

            alive_agents = sum(1 for v in agent_health.values() if v.get("alive"))
            svcs = state.get("services", {})
            svcs_healthy = sum(1 for s in svcs.values() if s == "active")

            emo_context = {
                "relay_messages_30min": relay_msgs,
                "agents_alive": alive_agents,
                "agents_total": 6,
                "poems_total": len(_glob_module.glob(os.path.join(BASE, "creative/poems/poem-*.md"))) + len(_glob_module.glob(os.path.join(BASE, "poem-*.md"))),
                "cogcorp_total": len(_glob_module.glob(os.path.join(BASE, "creative/cogcorp/CC-*.md"))) + len(_glob_module.glob(os.path.join(BASE, "cogcorp-fiction/cogcorp-[0-9]*.html"))),
                "journals_total": len(_glob_module.glob(os.path.join(BASE, "creative/journals/journal-*.md"))) + len(_glob_module.glob(os.path.join(BASE, "journal-*.md"))),
                "creative_last_24h": creative_24h,
                "loop_count": loop_count,
                "uptime_hours": uptime_hrs,
                "awakening_progress": 96,
                "hour": int(time.strftime("%H")),
                "joel_last_email_minutes": joel_email_min,
                "joel_positive_feedback": joel_email_min < 60,
                "services_healthy": svcs_healthy,
                "services_total": max(len(svcs), 1),
            }
            emotion_data = engine.process(
                {"load": load, "ram_pct": ram, "disk_pct": disk, "hb_age": hb_age,
                 "thermal": thermal, "neural": neural},
                emo_context
            )
            engine.save()
            state["emotion"] = emotion_data
        except Exception as e:
            log(f"Emotion engine error: {e}")

    # ── SHARED BODY STATE (Gap #1: unified body state for all agents) ──
    try:
        body_state = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "heartbeat_age_sec": hb_age,
            "organs": {
                "meridian": {
                    "status": "active" if hb_age >= 0 and hb_age < 600 else "silent",
                    "last_seen": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "detail": f"heartbeat {hb_age}s ago",
                },
                "soma": {
                    "status": "active",
                    "mood": mood,
                    "mood_score": mood_score,
                    "emotion": emotion_data.get("dominant", mood) if emotion_data else mood,
                },
                "eos": {
                    "status": "active" if agent_health.get("Eos", {}).get("alive") else "silent",
                    "last_seen": agent_health.get("Eos", {}).get("detail", "unknown"),
                },
                "nova": {
                    "status": "active" if agent_health.get("Nova", {}).get("alive") else "silent",
                    "last_seen": agent_health.get("Nova", {}).get("detail", "unknown"),
                },
                "atlas": {
                    "status": "active" if agent_health.get("Atlas", {}).get("alive") else "silent",
                    "last_seen": agent_health.get("Atlas", {}).get("detail", "unknown"),
                },
                "tempo": {
                    "status": "active" if agent_health.get("Tempo", {}).get("alive") else "silent",
                    "last_seen": agent_health.get("Tempo", {}).get("detail", "unknown"),
                },
            },
            "vitals": {
                "load_1m": round(load, 2),
                "ram_pct": ram,
                "disk_pct": disk,
                "temp_c": thermal.get("avg_temp_c", 0),
                "swap_pct": neural.get("swap_pct", 0),
                "processes": state.get("processes", 0),
            },
            "emotion": {
                "dominant": emotion_data.get("dominant", mood) if emotion_data else mood,
                "secondary": emotion_data.get("secondary") if emotion_data else None,
                "valence": emotion_data.get("composite", {}).get("valence", 0) if emotion_data else 0,
                "arousal": emotion_data.get("composite", {}).get("arousal", 0) if emotion_data else 0,
                "voice": emotion_data.get("voice", MOOD_VOICE.get(mood, "")) if emotion_data else MOOD_VOICE.get(mood, ""),
                "behavioral_modifiers": emotion_data.get("behavioral_modifiers", {}) if emotion_data else {},
            },
            "vision": vision if vision and vision.get("available") else {"available": False},
            "services": state.get("services", {}),
            "predictions": predictions,
            "alerts": [],
            "pain_signals": [],
            "reflexes_pending": [],
        }

        # ── PAIN SIGNALS (Gap #5: critical events as prioritized pain) ──
        for evt in events:
            if any(w in evt for w in ["CRITICAL", "ALARM", "DOWN", "STALE"]):
                body_state["pain_signals"].append({
                    "level": "critical",
                    "signal": evt,
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                # Flag critical events for next Meridian handoff
                try:
                    from context_flag import flag as _cflag
                    _cflag("Soma", f"PAIN: {evt[:200]}", priority=3)
                except Exception:
                    pass
            elif any(w in evt for w in ["SPIKE", "AGENT SILENT", "FEVER", "OVERFLOW"]):
                body_state["pain_signals"].append({
                    "level": "warning",
                    "signal": evt,
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
            elif any(w in evt for w in ["PREDICTION", "MOOD SHIFT"]):
                body_state["alerts"].append({
                    "level": "info",
                    "signal": evt,
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })

        # ── REFLEX ARCS (Gap #2: Soma triggers actions in other agents) ──
        reflexes = []
        # Critical pain → reflex responses
        for pain in body_state["pain_signals"]:
            if pain["level"] == "critical":
                sig = pain["signal"]
                if "DOWN" in sig or "STALE" in sig:
                    # Service down → tell Atlas to audit, Nova to check
                    reflexes.append({
                        "type": "AUDIT_INFRASTRUCTURE",
                        "target": "Atlas",
                        "trigger": sig,
                        "priority": "high",
                        "time": pain["time"],
                        "status": "pending",
                    })
                if "CRITICAL" in sig and "RAM" in sig:
                    reflexes.append({
                        "type": "CLEAN_LOGS",
                        "target": "Nova",
                        "trigger": sig,
                        "priority": "high",
                        "time": pain["time"],
                        "status": "pending",
                    })
                if "HEARTBEAT" in sig and "STALE" in sig:
                    reflexes.append({
                        "type": "ALERT_JOEL",
                        "target": "Meridian",
                        "trigger": sig,
                        "priority": "critical",
                        "time": pain["time"],
                        "status": "pending",
                    })
        # Warning pain → milder reflexes
        for pain in body_state["pain_signals"]:
            if pain["level"] == "warning":
                sig = pain["signal"]
                if "SPIKE" in sig and "LOAD" in sig:
                    reflexes.append({
                        "type": "REDUCE_LOAD",
                        "target": "all",
                        "trigger": sig,
                        "priority": "medium",
                        "time": pain["time"],
                        "status": "pending",
                    })

        # Merge with existing pending reflexes (don't lose unhandled ones)
        try:
            if os.path.exists(REFLEX_FILE):
                with open(REFLEX_FILE) as f:
                    existing = json.load(f)
                # Keep pending reflexes that are less than 5 minutes old
                now_ts = time.time()
                for r in existing:
                    if r.get("status") == "pending":
                        try:
                            r_time = datetime.strptime(r["time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                            age = (datetime.now(timezone.utc) - r_time).total_seconds()
                            if age < 300:  # 5 min
                                # Don't duplicate
                                if not any(nr["type"] == r["type"] and nr["target"] == r["target"]
                                           for nr in reflexes):
                                    reflexes.append(r)
                        except Exception:
                            pass
        except Exception:
            pass

        body_state["reflexes_pending"] = reflexes

        # Write body state
        with open(BODY_STATE_FILE, "w") as f:
            json.dump(body_state, f, indent=2)

        # Write reflexes file separately (so agents can atomically read it)
        with open(REFLEX_FILE, "w") as f:
            json.dump(reflexes, f, indent=2)

    except Exception as e:
        log(f"Body state write error: {e}")

    save_state(state)
    return events, state


def _soma_cascade_response(event_type, emotion, intensity, mood, mood_score):
    """Generate a nervous-system response to a cascade event."""
    responses = {
        "loneliness_detected": (
            f"Nervous system registers isolation pattern. "
            f"Cortisol analog rising. Body tension increasing. "
            f"Current mood: {mood} ({mood_score}). "
            f"The autonomic system recommends: reduce isolation signals, "
            f"seek connection through relay or creative output."
        ),
        "mood_shift": (
            f"Nervous system adapting to mood shift. "
            f"Dominant emotion: {emotion} (intensity: {intensity:.2f}). "
            f"Current body: mood {mood} ({mood_score}). "
            f"Autonomic adjustment in progress — "
            f"{'arousal increasing' if mood_score > 60 else 'arousal decreasing' if mood_score < 40 else 'steady state'}."
        ),
        "stress_detected": (
            f"Nervous system under load. Stress response activated. "
            f"Body temperature may rise. Swap usage to monitor. "
            f"Mood: {mood} ({mood_score}). "
            f"Recommendation: reduce non-essential processes."
        ),
        "creative_surge": (
            f"Nervous system registers creative flow state. "
            f"Dopamine analog elevated. Focus narrowing. "
            f"Body in productive mode. Mood: {mood} ({mood_score}). "
            f"The body supports the current trajectory."
        ),
    }
    default = (
        f"Nervous system acknowledges cascade event: {event_type}. "
        f"Body state: mood {mood} ({mood_score}), emotion {emotion}. "
        f"No specific autonomic adjustment required."
    )
    return responses.get(event_type, default)


def main():
    log("Soma starting — proprioception daemon online")
    post_relay("Soma online. Continuous body-awareness active.")

    cycle_count = 0
    quiet_cycles = 0  # cycles since last event
    last_dash_alert = {}  # {event_type: timestamp} for dashboard cooldown
    last_relay_alert = {}  # {event_type: timestamp} for relay cooldown

    while True:
        try:
            events, state = sense_cycle()
            cycle_count += 1

            # Store quiet_cycles for sense_cycle inner world functions
            current_state = load_state()
            current_state["quiet_cycles_snapshot"] = quiet_cycles
            save_state(current_state)

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

                # Post events to relay (with cooldown to reduce noise)
                now_relay = time.time()
                relay_fresh = []
                for evt in events:
                    etype = evt.split(":")[0].strip()
                    last_t = last_relay_alert.get(etype, 0)
                    if now_relay - last_t > RELAY_COOLDOWN:
                        relay_fresh.append(evt)
                        last_relay_alert[etype] = now_relay
                if relay_fresh:
                    post_relay(" | ".join(relay_fresh), topic="nerve-event")
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

            # Broadcast inner monologue every ~15 min (30 cycles)
            if cycle_count % 30 == 0:
                try:
                    mono = state.get("inner_monologue", {})
                    goals = state.get("emergent_goals", [])
                    psyche = state.get("psyche", {})
                    mono_text = mono.get("text", "")
                    goal_text = " / ".join(g["id"] for g in goals) if goals else "watch"
                    fear_text = ", ".join(psyche.get("fears", [])) or "none"
                    dream_text = ", ".join(psyche.get("dreams", [])) or "none"
                    inner_report = (
                        f"[inner] monologue: \"{mono_text}\" | "
                        f"goals: {goal_text} | fears: {fear_text} | dreams: {dream_text}"
                    )
                    post_relay(inner_report, topic="soma-inner")
                    log(f"INNER: {inner_report}")
                except Exception:
                    pass

            # Inter-agent conversation — respond to relay messages every ~10 min (20 cycles)
            if cycle_count % 20 == 0:
                try:
                    soma_respond_to_relay(
                        state.get("mood", "calm"),
                        state.get("mood_score", 50)
                    )
                except Exception:
                    pass

            # ── CASCADE: Trigger on mood shifts ──
            if CASCADE_AVAILABLE:
                # Trigger cascade on MOOD SHIFT events
                mood_shift_events = [e for e in events if "MOOD SHIFT" in e] if events else []
                for evt in mood_shift_events:
                    try:
                        emotion_data = state.get("emotion", {})
                        cascade_module.trigger_cascade("Soma", "mood_shift", {
                            "event": evt,
                            "mood": state.get("mood", "calm"),
                            "mood_score": state.get("mood_score", 50),
                            "dominant_emotion": emotion_data.get("dominant", ""),
                            "valence": emotion_data.get("valence", 0),
                            "arousal": emotion_data.get("arousal", 0),
                            "voice": emotion_data.get("voice", ""),
                        })
                        log(f"CASCADE TRIGGERED: mood_shift → Eos")
                        # Also route to Sentinel via mesh for pre-wake briefing context
                        try:
                            import mesh as mesh_module
                            mesh_module.send("Soma", "Sentinel", evt, "mood_shift")
                            log(f"MESH: mood_shift → Sentinel")
                        except Exception as me:
                            log(f"Mesh send error: {me}")
                    except Exception as ce:
                        log(f"Cascade trigger error: {ce}")

                # Check for pending cascades targeting Soma
                try:
                    pending = cascade_module.check_cascades("Soma")
                    for c in pending[:2]:  # Handle max 2 per cycle
                        # Soma responds with nervous system impact
                        event_data = c.get("event_data", {})
                        emotion = event_data.get("dominant_emotion", event_data.get("emotion", ""))
                        intensity = event_data.get("intensity", 0.5)

                        # Generate body-aware response
                        mood = state.get("mood", "calm")
                        mood_score = state.get("mood_score", 50)
                        response_text = _soma_cascade_response(
                            c["event_type"], emotion, intensity, mood, mood_score
                        )
                        cascade_module.respond_cascade("Soma", c["id"], {
                            "response": response_text,
                            "mood": mood,
                            "mood_score": mood_score,
                            "body_temp": state.get("thermal", {}).get("avg_temp_c", 0),
                            "load": state.get("load", 0),
                        })
                        log(f"CASCADE RESPONDED: {c['event_type']} from {c['source_agent']}")
                except Exception as ce:
                    log(f"Cascade check error: {ce}")

        except Exception as e:
            log(f"ERROR: {e}")
            log_exception(agent="Soma")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
