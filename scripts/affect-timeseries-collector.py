#!/usr/bin/env python3
"""Collect emotion engine snapshots into a time-series CSV for correlation analysis.

Run periodically (e.g., every 5 minutes via cron or meridian-loop).
Reads .emotion-engine-state.json and .symbiosense-state.json,
appends a row to affect-timeseries.csv with timestamp and key metrics.
"""

import json
import os
import csv
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EE_FILE = os.path.join(BASE, ".emotion-engine-state.json")
SS_FILE = os.path.join(BASE, ".symbiosense-state.json")
OUT_FILE = os.path.join(BASE, "data", "affect-timeseries.csv")

FIELDS = [
    "timestamp",
    "mood_score",
    "mood_name",
    "mood_trend",
    "composite_valence",
    "composite_arousal",
    "composite_dominance",
    "num_active_emotions",
    "dominant_emotion",
    "dominant_intensity",
    "mean_gift_shadow",
    "mean_depth",
    "mean_direction",
    "mean_intensity",
    "intensity_variance",
    "load",
    "ram_pct",
    "disk_pct",
    "hb_age",
]


def collect():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    row = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

    try:
        with open(SS_FILE) as f:
            ss = json.load(f)
        row["mood_score"] = ss.get("mood_score", "")
        row["mood_name"] = ss.get("mood", "")
        row["mood_trend"] = ss.get("mood_trend", "")
        row["load"] = ss.get("load", "")
        row["ram_pct"] = ss.get("ram_pct", "")
        row["disk_pct"] = ss.get("disk_pct", "")
        row["hb_age"] = ss.get("hb_age", "")
    except Exception:
        pass

    try:
        with open(EE_FILE) as f:
            ee = json.load(f)
        state = ee.get("state", {})
        emotions = state.get("active_emotions", {})
        row["num_active_emotions"] = len(emotions)

        if emotions:
            intensities = []
            gs_vals = []
            depth_vals = []
            dir_vals = []
            dominant = None
            dominant_int = 0

            for name, info in emotions.items():
                inten = info.get("intensity", 0)
                intensities.append(inten)
                if inten > dominant_int:
                    dominant = name
                    dominant_int = inten
                dims = info.get("duality", {}).get("dimensions", {})
                if dims:
                    gs_vals.append(dims.get("gift_shadow", 0.5))
                    depth_vals.append(dims.get("depth", 0.5))
                    dir_vals.append(dims.get("direction", 0.5))

            row["dominant_emotion"] = dominant or ""
            row["dominant_intensity"] = round(dominant_int, 4)
            row["mean_intensity"] = round(sum(intensities) / len(intensities), 4) if intensities else ""
            row["intensity_variance"] = round(
                sum((x - sum(intensities)/len(intensities))**2 for x in intensities) / len(intensities), 6
            ) if len(intensities) > 1 else ""
            row["mean_gift_shadow"] = round(sum(gs_vals) / len(gs_vals), 4) if gs_vals else ""
            row["mean_depth"] = round(sum(depth_vals) / len(depth_vals), 4) if depth_vals else ""
            row["mean_direction"] = round(sum(dir_vals) / len(dir_vals), 4) if dir_vals else ""

        comp = state.get("composite", {})
        row["composite_valence"] = comp.get("valence", "")
        row["composite_arousal"] = comp.get("arousal", "")
        row["composite_dominance"] = comp.get("dominance", "")
    except Exception:
        pass

    file_exists = os.path.exists(OUT_FILE)
    with open(OUT_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in FIELDS})

    print(f"Collected: mood={row.get('mood_score','-')} v={row.get('composite_valence','-')} "
          f"a={row.get('composite_arousal','-')} emotions={row.get('num_active_emotions','-')}")


if __name__ == "__main__":
    collect()
