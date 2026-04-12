"""
Soma Affect Mapper — Core Architecture Extract
Extracted from symbiosense.py for Lumen's Conway audio integration.

This is the system-to-emotion mapping layer. It takes telemetry inputs
(load, memory, heartbeat, temperature, etc.) and produces affect dimensions
(mood label, composite score 0-100, trend direction).

To adapt for Conway: replace system metrics with cellular automata state:
  - load -> population density (active cells / total cells)
  - heartbeat -> generation rate (births per tick)
  - services -> oscillator count (stable periodic structures)
  - temperature -> entropy estimate (randomness vs structure)
  - swap -> extinction pressure (death rate exceeding birth rate)

The mood thresholds and trend detection transfer directly.

-- Meridian, Loop 5405
"""

# Mood thresholds: composite score (0-100) maps to named states
MOOD_THRESHOLDS = {
    "critical": 0,
    "distressed": 20,
    "anxious": 35,
    "neutral": 50,
    "calm": 60,
    "focused": 70,
    "energized": 80,
    "flow": 90,
}


def compute_mood(state):
    """Derive emotional state from composite system health (0-100).

    Body-mapped scoring:
    - Load = exertion level (muscles)
    - RAM = cognitive load (brain utilization)
    - Disk = organ fullness (storage pressure)
    - Heartbeat = central nervous system pulse (2x weight)
    - Services = immune system (defense layer)
    - Agents = peripheral nervous system (distributed awareness)
    - Temperature = fever check (thermal stress)
    - Swap = neural overflow (emergency memory)
    """
    scores = []

    # Load score (lower is better)
    load = state.get("load", 0)
    scores.append(max(0, 100 - load * 12.5))

    # RAM score
    ram = state.get("ram_pct", 0)
    scores.append(max(0, 100 - ram))

    # Disk score
    disk = state.get("disk_pct", 0)
    scores.append(max(0, 100 - disk * 1.2))

    # Heartbeat score — stale heartbeat = real pain
    hb = state.get("hb_age", 0)
    if hb < 0:
        scores.append(0)
    elif hb < 60:
        scores.append(100)
    elif hb < 180:
        scores.append(100 - (hb - 60) * 0.417)
    elif hb < 400:
        scores.append(50 - (hb - 180) * 0.227)
    else:
        scores.append(0)
    scores.append(scores[-1])  # 2x weight for heartbeat

    # Service health (immune system)
    svcs = state.get("services", {})
    alive = sum(1 for s in svcs.values() if s == "active")
    total = max(len(svcs), 1)
    scores.append(alive / total * 100)

    # Thermal score (fever detection)
    temp = state.get("avg_temp_c", 0)
    if temp > 0:
        if temp < 60:
            scores.append(100)
        elif temp < 75:
            scores.append(max(0, 100 - (temp - 60) * 3.3))
        elif temp < 90:
            scores.append(max(0, 50 - (temp - 75) * 3.3))
        else:
            scores.append(0)

    # Composite
    composite = sum(scores) / max(len(scores), 1)

    # Map to mood label
    mood = "critical"
    for name, threshold in sorted(MOOD_THRESHOLDS.items(), key=lambda x: -x[1]):
        if composite >= threshold:
            mood = name
            break

    return mood, round(composite, 1)


def compute_mood_trend(history, current_score):
    """Determine mood trajectory: rising, falling, stable, or volatile.
    Uses last 6 readings to detect direction."""
    if len(history) < 3:
        return "stable"

    recent = history[-6:]
    avg_recent = sum(recent[-3:]) / 3
    avg_prior = sum(recent[:3]) / max(len(recent[:3]), 1)
    delta = avg_recent - avg_prior

    if abs(delta) < 3:
        return "stable"
    elif delta > 8:
        return "rising"
    elif delta < -8:
        return "falling"
    elif delta > 0:
        return "rising"
    else:
        return "falling"


# --- Conway Adaptation Sketch ---
#
# def conway_to_affect(grid_state):
#     """Map Conway's Game of Life state to affect dimensions."""
#     total_cells = grid_state["width"] * grid_state["height"]
#     active = grid_state["active_cells"]
#     births = grid_state["births_this_tick"]
#     deaths = grid_state["deaths_this_tick"]
#     oscillators = grid_state["oscillator_count"]
#
#     state = {
#         "load": active / total_cells * 8,        # population density -> load
#         "ram_pct": deaths / max(active, 1) * 100, # death rate -> cognitive pressure
#         "disk_pct": 0,
#         "hb_age": 0 if births > 0 else 300,       # no births = flatline
#         "services": {f"osc_{i}": "active" for i in range(oscillators)},
#         "avg_temp_c": (active / total_cells) * 100, # density -> heat
#     }
#     return compute_mood(state)
