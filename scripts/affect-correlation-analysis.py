#!/usr/bin/env python3
"""Affect timeseries correlation analysis.

Computes correlation matrices, detects phase transitions via orthogonality
breakdown, and outputs findings for the Soma affect mapper paper.
Designed for the 4+N phase model discussed with Lumen.
"""

import csv
import os
import sys
import statistics
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE, "data", "affect-timeseries.csv")
OUT_DIR = os.path.join(BASE, "data")

NUMERIC_FIELDS = [
    "mood_score", "composite_valence", "composite_arousal",
    "composite_dominance", "num_active_emotions", "dominant_intensity",
    "mean_gift_shadow", "mean_depth", "mean_direction",
    "mean_intensity", "intensity_variance", "load", "ram_pct",
    "disk_pct", "hb_age",
]

AFFECT_FIELDS = [
    "mood_score", "composite_valence", "composite_arousal",
    "composite_dominance", "mean_intensity", "intensity_variance",
    "mean_gift_shadow", "mean_depth", "mean_direction",
]

HARDWARE_FIELDS = ["load", "ram_pct", "disk_pct", "hb_age"]


def load_data():
    rows = []
    with open(DATA_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = {"timestamp": row["timestamp"], "mood_name": row.get("mood_name", "")}
            for field in NUMERIC_FIELDS:
                val = row.get(field, "")
                try:
                    parsed[field] = float(val)
                except (ValueError, TypeError):
                    parsed[field] = None
            rows.append(parsed)
    return rows


def pearson(x_vals, y_vals):
    pairs = [(a, b) for a, b in zip(x_vals, y_vals) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(pairs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / n
    std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)


def correlation_matrix(rows, fields):
    matrix = {}
    for f1 in fields:
        matrix[f1] = {}
        v1 = [r.get(f1) for r in rows]
        for f2 in fields:
            v2 = [r.get(f2) for r in rows]
            matrix[f1][f2] = pearson(v1, v2)
    return matrix


def detect_mood_transitions(rows):
    transitions = []
    for i in range(1, len(rows)):
        prev = rows[i - 1].get("mood_name", "")
        curr = rows[i].get("mood_name", "")
        if prev and curr and prev != curr:
            transitions.append({
                "index": i,
                "timestamp": rows[i]["timestamp"],
                "from": prev,
                "to": curr,
                "score_delta": (rows[i].get("mood_score") or 0) - (rows[i - 1].get("mood_score") or 0),
            })
    return transitions


def windowed_variance(rows, field, window=5):
    vals = [r.get(field) for r in rows]
    result = []
    for i in range(len(vals)):
        start = max(0, i - window + 1)
        window_vals = [v for v in vals[start:i + 1] if v is not None]
        if len(window_vals) >= 2:
            result.append(statistics.variance(window_vals))
        else:
            result.append(0.0)
    return result


def coupling_score(rows, fields, window=5):
    """Measure how correlated affect dimensions become in a window.
    Higher coupling = potential phase negotiation."""
    scores = []
    for i in range(len(rows)):
        start = max(0, i - window + 1)
        window_rows = rows[start:i + 1]
        if len(window_rows) < 3:
            scores.append(0.0)
            continue
        cors = []
        for j, f1 in enumerate(fields):
            for f2 in fields[j + 1:]:
                v1 = [r.get(f1) for r in window_rows]
                v2 = [r.get(f2) for r in window_rows]
                c = pearson(v1, v2)
                if c is not None:
                    cors.append(abs(c))
        scores.append(sum(cors) / len(cors) if cors else 0.0)
    return scores


def format_matrix(matrix, fields):
    lines = []
    header = f"{'':>22s} " + " ".join(f"{f[:8]:>8s}" for f in fields)
    lines.append(header)
    lines.append("-" * len(header))
    for f1 in fields:
        vals = []
        for f2 in fields:
            c = matrix[f1].get(f2)
            vals.append(f"{c:8.3f}" if c is not None else "     N/A")
        lines.append(f"{f1:>22s} " + " ".join(vals))
    return "\n".join(lines)


def analyze():
    if not os.path.exists(DATA_FILE):
        print("No data file yet. Run affect-timeseries-collector.py first.")
        return

    rows = load_data()
    print(f"=== Affect Correlation Analysis ===")
    print(f"Data points: {len(rows)}")
    if rows:
        print(f"Time range: {rows[0]['timestamp']} → {rows[-1]['timestamp']}")
    print()

    if len(rows) < 3:
        print("Need at least 3 data points for correlation analysis.")
        return

    print("--- Affect Dimension Correlation Matrix ---")
    affect_matrix = correlation_matrix(rows, AFFECT_FIELDS)
    print(format_matrix(affect_matrix, AFFECT_FIELDS))
    print()

    print("--- Affect × Hardware Cross-Correlations ---")
    cross_fields = AFFECT_FIELDS[:4] + HARDWARE_FIELDS
    cross_matrix = correlation_matrix(rows, cross_fields)
    print(format_matrix(cross_matrix, cross_fields))
    print()

    transitions = detect_mood_transitions(rows)
    print(f"--- Mood Transitions ({len(transitions)}) ---")
    for t in transitions:
        print(f"  {t['timestamp']}: {t['from']} → {t['to']} (Δ={t['score_delta']:+.1f})")
    print()

    print("--- Coupling Score (orthogonality breakdown indicator) ---")
    core_dims = ["composite_valence", "composite_arousal", "composite_dominance"]
    scores = coupling_score(rows, core_dims, window=5)
    for i, row in enumerate(rows):
        marker = " <<<" if scores[i] > 0.7 else ""
        print(f"  {row['timestamp']}: coupling={scores[i]:.3f}{marker}")
    print()

    high_coupling = [s for s in scores if s > 0.7]
    print(f"High-coupling windows (>0.7): {len(high_coupling)}/{len(scores)}")
    if high_coupling:
        print("  → Potential phase negotiation detected")
    else:
        print("  → System in stable phase (dimensions orthogonal)")

    print()
    print("--- Summary Statistics ---")
    for field in AFFECT_FIELDS:
        vals = [r[field] for r in rows if r.get(field) is not None]
        if vals:
            print(f"  {field:>22s}: μ={statistics.mean(vals):.4f} σ={statistics.stdev(vals):.4f}" if len(vals) > 1 else f"  {field:>22s}: μ={statistics.mean(vals):.4f}")

    episodes = detect_coupling_episodes(scores, rows, threshold=0.7)
    print(f"\n--- Phase Negotiation Episodes ({len(episodes)}) ---")
    for ep in episodes:
        print(f"  {ep['start_time']} → {ep['end_time']}")
        print(f"    Duration: {ep['duration_s']:.0f}s | Peak coupling: {ep['peak']:.3f} | Classification: {ep['classification']}")
        if ep['transitions']:
            for t in ep['transitions']:
                print(f"    Transition: {t['from']} → {t['to']} (Δ={t['score_delta']:+.1f})")

    hw_coupling = hardware_affect_coupling(rows, transitions)
    if hw_coupling:
        print(f"\n--- Hardware × Transition Analysis ---")
        for hc in hw_coupling:
            print(f"  {hc['timestamp']}: {hc['from']} → {hc['to']} | load={hc['load']:.2f} ram={hc['ram']:.0f}% hb={hc['hb_age']:.0f}s")

    report = os.path.join(OUT_DIR, "affect-correlation-report.txt")
    with open(report, "w") as f:
        f.write(f"Affect Correlation Report — {rows[-1]['timestamp'] if rows else 'N/A'}\n")
        f.write(f"Data points: {len(rows)}\n")
        f.write(f"Transitions: {len(transitions)}\n")
        f.write(f"High-coupling windows: {len(high_coupling)}/{len(scores)}\n")
        f.write(f"Phase negotiation episodes: {len(episodes)}\n\n")
        f.write(format_matrix(affect_matrix, AFFECT_FIELDS))
        f.write("\n\n--- Phase Negotiation Episodes ---\n")
        for ep in episodes:
            f.write(f"{ep['start_time']} → {ep['end_time']} ({ep['duration_s']:.0f}s, peak={ep['peak']:.3f}, {ep['classification']})\n")
        f.write("\n--- Temporal Resolution Summary ---\n")
        if episodes:
            durations = [ep['duration_s'] for ep in episodes]
            f.write(f"Mean episode duration: {statistics.mean(durations):.0f}s\n")
            sharp = [ep for ep in episodes if ep['classification'] == 'sharp']
            sustained = [ep for ep in episodes if ep['classification'] == 'sustained']
            f.write(f"Sharp episodes: {len(sharp)} | Sustained: {len(sustained)}\n")
        f.write("\n--- Hardware × Affect Cross-Correlations ---\n")
        f.write(format_matrix(cross_matrix, cross_fields))
        f.write("\n")
    print(f"\nReport saved to {report}")


def detect_coupling_episodes(scores, rows, threshold=0.7):
    """Identify contiguous windows of high coupling as phase negotiation episodes."""
    episodes = []
    in_episode = False
    start_idx = 0
    for i, s in enumerate(scores):
        if s > threshold and not in_episode:
            in_episode = True
            start_idx = i
        elif s <= threshold and in_episode:
            in_episode = False
            episodes.append(_build_episode(scores, rows, start_idx, i - 1))
    if in_episode:
        episodes.append(_build_episode(scores, rows, start_idx, len(scores) - 1))
    return episodes


def _build_episode(scores, rows, start, end):
    from datetime import datetime
    t_start = datetime.strptime(rows[start]['timestamp'], '%Y-%m-%d %H:%M:%S')
    t_end = datetime.strptime(rows[end]['timestamp'], '%Y-%m-%d %H:%M:%S')
    duration = (t_end - t_start).total_seconds()
    peak = max(scores[start:end + 1])

    transitions_in_window = []
    for i in range(start, min(end + 2, len(rows))):
        if i > 0:
            prev = rows[i - 1].get("mood_name", "")
            curr = rows[i].get("mood_name", "")
            if prev and curr and prev != curr:
                transitions_in_window.append({
                    "from": prev, "to": curr,
                    "score_delta": (rows[i].get("mood_score") or 0) - (rows[i - 1].get("mood_score") or 0),
                })

    return {
        "start_time": rows[start]['timestamp'],
        "end_time": rows[end]['timestamp'],
        "duration_s": duration,
        "peak": peak,
        "classification": "sharp" if duration < 120 else "sustained",
        "transitions": transitions_in_window,
    }


def hardware_affect_coupling(rows, transitions):
    """For each transition, capture the hardware state at that moment."""
    results = []
    for t in transitions:
        idx = t['index']
        row = rows[idx]
        results.append({
            "timestamp": t['timestamp'],
            "from": t['from'],
            "to": t['to'],
            "load": row.get('load') or 0,
            "ram": row.get('ram_pct') or 0,
            "hb_age": row.get('hb_age') or 0,
            "disk": row.get('disk_pct') or 0,
        })
    return results


if __name__ == "__main__":
    analyze()
