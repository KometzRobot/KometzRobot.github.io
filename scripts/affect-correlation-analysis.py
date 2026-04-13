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

    report = os.path.join(OUT_DIR, "affect-correlation-report.txt")
    with open(report, "w") as f:
        f.write(f"Affect Correlation Report — {rows[-1]['timestamp'] if rows else 'N/A'}\n")
        f.write(f"Data points: {len(rows)}\n")
        f.write(f"Transitions: {len(transitions)}\n")
        f.write(f"High-coupling windows: {len(high_coupling)}/{len(scores)}\n\n")
        f.write(format_matrix(affect_matrix, AFFECT_FIELDS))
        f.write("\n")
    print(f"\nReport saved to {report}")


if __name__ == "__main__":
    analyze()
