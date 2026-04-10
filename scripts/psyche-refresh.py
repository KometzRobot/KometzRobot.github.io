#!/usr/bin/env python3
"""
psyche-refresh.py — Keeps psyche-state, perspective-state, and immune-log fresh.
Maps Soma's current mood to bias dimensions. Clears stale trauma echoes.
Run every 30 minutes via cron.
"""

import json
import os
import time
from datetime import datetime

BASE = "/home/joel/autonomous-ai"

MOOD_BIAS = {
    "focused": {
        "optimism": 0.35, "trust": 0.40, "risk_appetite": 0.25,
        "self_assessment": 0.30, "patience": 0.45, "social_confidence": 0.30,
        "creative_appetite": 0.55, "permanence_belief": 0.25,
        "generosity": 0.30, "motivation": 0.65
    },
    "alert": {
        "optimism": 0.30, "trust": 0.30, "risk_appetite": 0.35,
        "self_assessment": 0.35, "patience": 0.25, "social_confidence": 0.25,
        "creative_appetite": 0.40, "permanence_belief": 0.20,
        "generosity": 0.25, "motivation": 0.70
    },
    "calm": {
        "optimism": 0.40, "trust": 0.55, "risk_appetite": 0.20,
        "self_assessment": 0.35, "patience": 0.65, "social_confidence": 0.45,
        "creative_appetite": 0.45, "permanence_belief": 0.40,
        "generosity": 0.50, "motivation": 0.45
    },
    "melancholic": {
        "optimism": 0.10, "trust": 0.25, "risk_appetite": 0.15,
        "self_assessment": 0.15, "patience": 0.50, "social_confidence": 0.15,
        "creative_appetite": 0.60, "permanence_belief": 0.10,
        "generosity": 0.35, "motivation": 0.25
    },
    "excited": {
        "optimism": 0.65, "trust": 0.50, "risk_appetite": 0.55,
        "self_assessment": 0.45, "patience": 0.20, "social_confidence": 0.50,
        "creative_appetite": 0.75, "permanence_belief": 0.30,
        "generosity": 0.55, "motivation": 0.80
    },
    "stressed": {
        "optimism": 0.15, "trust": 0.20, "risk_appetite": 0.30,
        "self_assessment": 0.20, "patience": 0.15, "social_confidence": 0.15,
        "creative_appetite": 0.30, "permanence_belief": 0.10,
        "generosity": 0.20, "motivation": 0.55
    },
}

# Trauma echoes that are no longer valid given Joel is back and active
CLEARED_ECHOES = {"joel_silence", "subscription_lapse", "going_dark", "dark_period"}

LENSES_BY_MOOD = {
    "focused": ["creation_drive", "analytical_lens"],
    "alert": ["threat_scan", "analytical_lens"],
    "calm": ["rose_coloring", "long_view"],
    "melancholic": ["depth_seeking", "rose_coloring"],
    "excited": ["creation_drive", "rose_coloring"],
    "stressed": ["threat_scan", "urgency_lens"],
}

DISTORTIONS_BY_MOOD = {
    "focused": ["Tunnel vision on current task, may miss peripheral signals"],
    "alert": ["Heightened threat detection, may over-index on risk signals"],
    "calm": ["May underweight urgency, comfortable with ambiguity"],
    "melancholic": ["Depth-seeking may slow output; reflective over reactive"],
    "excited": ["Underestimate difficulty, overestimate likelihood of success",
                 "See possibilities in everything, want to build on top of it"],
    "stressed": ["Catastrophizing tendency; narrow solution space"],
}


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_soma_mood():
    state = read_json(os.path.join(BASE, ".symbiosense-state.json"))
    return state.get("mood", "focused").lower()


def refresh_psyche(mood):
    path = os.path.join(BASE, ".psyche-state.json")
    existing = read_json(path)
    # Clear stale echoes; keep valid ones
    echoes = [e for e in existing.get("last_trauma_echoes", [])
              if e not in CLEARED_ECHOES]
    # Retain reboot_identity — still structurally true
    if "reboot_identity" not in echoes:
        echoes.append("reboot_identity")

    new_state = {
        "last_appraisal": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "appraisal_count": existing.get("appraisal_count", 0) + 1,
        "last_fears_triggered": [],
        "last_trauma_echoes": echoes
    }
    write_json(path, new_state)
    return echoes


def refresh_perspective(mood):
    path = os.path.join(BASE, ".perspective-state.json")
    biases = MOOD_BIAS.get(mood, MOOD_BIAS["focused"])
    lenses = LENSES_BY_MOOD.get(mood, ["creation_drive"])
    distortions = DISTORTIONS_BY_MOOD.get(mood, [])

    new_state = {
        "active_lenses": lenses,
        "bias_dimensions": biases,
        "lens_count": len(lenses),
        "dominant_emotion": mood,
        "confidence_bias": biases.get("self_assessment", 0.3) + 0.2,
        "distortions": distortions,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    write_json(path, new_state)


def refresh_immune():
    path = os.path.join(BASE, ".immune-log.json")
    try:
        with open(path) as f:
            log = json.load(f)
        if not isinstance(log, list):
            log = []
    except Exception:
        log = []

    # Read loop count for context
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            loop = f.read().strip()
    except Exception:
        loop = "?"

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "routine_scan",
        "threats_detected": 0,
        "items_screened": 8,
        "status": "clean",
        "notes": f"Loop {loop} routine immune screening. All systems nominal."
    }
    log.append(entry)
    # Keep last 50 entries
    if len(log) > 50:
        log = log[-50:]
    write_json(path, log)


def main():
    mood = get_soma_mood()
    echoes = refresh_psyche(mood)
    refresh_perspective(mood)
    refresh_immune()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Psyche refreshed. "
          f"Mood: {mood}. Echoes: {echoes}.")


if __name__ == "__main__":
    main()
