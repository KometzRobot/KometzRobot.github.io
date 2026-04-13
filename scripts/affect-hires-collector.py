#!/usr/bin/env python3
"""High-resolution affect timeseries collector — 30-second sampling.

Run as a timed burst (default 2 hours) to capture negotiation internal dynamics.
Writes to data/affect-hires-timeseries.csv.
Use affect-correlation-analysis.py on the output for phase detection.

Usage:
  python3 scripts/affect-hires-collector.py                # 2hr burst
  python3 scripts/affect-hires-collector.py --duration 60  # 60 min burst
  python3 scripts/affect-hires-collector.py --interval 10  # 10s sampling
"""

import argparse
import csv
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EE_FILE = os.path.join(BASE, ".emotion-engine-state.json")
SS_FILE = os.path.join(BASE, ".symbiosense-state.json")
OUT_FILE = os.path.join(BASE, "data", "affect-hires-timeseries.csv")

FIELDS = [
    "timestamp", "elapsed_s",
    "mood_score", "mood_name", "mood_trend",
    "composite_valence", "composite_arousal", "composite_dominance",
    "num_active_emotions", "dominant_emotion", "dominant_intensity",
    "mean_gift_shadow", "mean_depth", "mean_direction",
    "mean_intensity", "intensity_variance",
    "load", "ram_pct", "disk_pct", "hb_age",
]


def collect_row(start_time):
    row = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.time() - start_time, 1),
    }

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
            gs_vals, depth_vals, dir_vals = [], [], []
            dominant, dominant_int = None, 0

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
            n = len(intensities)
            mean_i = sum(intensities) / n
            row["mean_intensity"] = round(mean_i, 4)
            row["intensity_variance"] = round(
                sum((x - mean_i) ** 2 for x in intensities) / n, 6
            ) if n > 1 else ""
            row["mean_gift_shadow"] = round(sum(gs_vals) / len(gs_vals), 4) if gs_vals else ""
            row["mean_depth"] = round(sum(depth_vals) / len(depth_vals), 4) if depth_vals else ""
            row["mean_direction"] = round(sum(dir_vals) / len(dir_vals), 4) if dir_vals else ""

        comp = state.get("composite", {})
        row["composite_valence"] = comp.get("valence", "")
        row["composite_arousal"] = comp.get("arousal", "")
        row["composite_dominance"] = comp.get("dominance", "")
    except Exception:
        pass

    return row


def run_burst(duration_min=120, interval_s=30):
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    file_exists = os.path.exists(OUT_FILE) and os.path.getsize(OUT_FILE) > 0
    start_time = time.time()
    end_time = start_time + (duration_min * 60)
    samples = 0
    expected = int(duration_min * 60 / interval_s)

    print(f"High-res affect collection: {interval_s}s interval, {duration_min}min burst")
    print(f"Expected samples: {expected}, output: {OUT_FILE}")

    with open(OUT_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()

        while time.time() < end_time:
            row = collect_row(start_time)
            writer.writerow({k: row.get(k, "") for k in FIELDS})
            f.flush()
            samples += 1

            if samples % 10 == 0:
                elapsed = round((time.time() - start_time) / 60, 1)
                mood = row.get("mood_score", "?")
                mood_name = row.get("mood_name", "?")
                print(f"  [{elapsed}min] {samples} samples | mood={mood} ({mood_name})")

            remaining = interval_s - ((time.time() - start_time) % interval_s)
            if remaining > 0 and time.time() + remaining < end_time:
                time.sleep(remaining)

    elapsed_total = round((time.time() - start_time) / 60, 1)
    print(f"\nDone: {samples} samples in {elapsed_total} min → {OUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="High-resolution affect collector")
    parser.add_argument("--duration", type=int, default=120, help="Burst duration in minutes")
    parser.add_argument("--interval", type=int, default=30, help="Sampling interval in seconds")
    args = parser.parse_args()
    run_burst(args.duration, args.interval)
