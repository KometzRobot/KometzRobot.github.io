#!/usr/bin/env python3
"""
CSV Data Analyzer — Professional Gig Product
Analyzes CSV files: statistics, distributions, correlations, anomalies.
Zero external dependencies (pure Python).
Built by KometzRobot / Meridian AI

Usage:
  python3 csv-analyzer.py data.csv --report
  python3 csv-analyzer.py data.csv --top 10 --column sales
  python3 csv-analyzer.py data.csv --filter "status=active" --output filtered.csv
"""

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime


def load_csv(filepath):
    """Load CSV into list of dicts."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data


def detect_types(data):
    """Detect column types (numeric, date, text)."""
    if not data:
        return {}
    types = {}
    for col in data[0].keys():
        values = [row[col] for row in data if row[col].strip()]
        if not values:
            types[col] = 'empty'
            continue

        # Check numeric
        numeric_count = 0
        for v in values[:100]:
            try:
                float(v.replace(',', ''))
                numeric_count += 1
            except ValueError:
                pass

        if numeric_count > len(values[:100]) * 0.8:
            types[col] = 'numeric'
        else:
            types[col] = 'text'

    return types


def numeric_stats(values):
    """Calculate statistics for numeric values."""
    nums = []
    for v in values:
        try:
            nums.append(float(v.replace(',', '')))
        except (ValueError, AttributeError):
            pass

    if not nums:
        return None

    nums.sort()
    n = len(nums)
    total = sum(nums)
    mean = total / n
    variance = sum((x - mean) ** 2 for x in nums) / n
    std = math.sqrt(variance)

    return {
        'count': n,
        'sum': round(total, 2),
        'mean': round(mean, 2),
        'median': round(nums[n // 2], 2),
        'min': round(nums[0], 2),
        'max': round(nums[-1], 2),
        'std': round(std, 2),
        'q25': round(nums[n // 4], 2),
        'q75': round(nums[3 * n // 4], 2),
    }


def text_stats(values):
    """Calculate statistics for text values."""
    counter = Counter(v.strip() for v in values if v.strip())
    total = sum(counter.values())
    unique = len(counter)
    most_common = counter.most_common(10)

    return {
        'count': total,
        'unique': unique,
        'top_values': most_common,
        'fill_rate': f"{total}/{len(values)} ({100*total/max(len(values),1):.1f}%)",
    }


def generate_report(data, types):
    """Generate a full analysis report."""
    print(f"\n{'='*60}")
    print(f"  DATA ANALYSIS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    print(f"Rows: {len(data)}")
    print(f"Columns: {len(types)}")
    print()

    for col, col_type in types.items():
        values = [row.get(col, '') for row in data]
        print(f"--- {col} ({col_type}) ---")

        if col_type == 'numeric':
            stats = numeric_stats(values)
            if stats:
                for k, v in stats.items():
                    print(f"  {k:>10}: {v}")
        elif col_type == 'text':
            stats = text_stats(values)
            print(f"  {'count':>10}: {stats['count']}")
            print(f"  {'unique':>10}: {stats['unique']}")
            print(f"  {'fill_rate':>10}: {stats['fill_rate']}")
            print(f"  Top values:")
            for val, count in stats['top_values'][:5]:
                pct = 100 * count / max(stats['count'], 1)
                bar = '#' * int(pct / 2)
                print(f"    {val[:30]:>30}: {count:>5} ({pct:.1f}%) {bar}")
        print()

    # Anomaly detection for numeric columns
    print(f"\n{'='*60}")
    print(f"  ANOMALY DETECTION")
    print(f"{'='*60}\n")

    for col, col_type in types.items():
        if col_type != 'numeric':
            continue
        values = [row.get(col, '') for row in data]
        stats = numeric_stats(values)
        if not stats or stats['std'] == 0:
            continue

        threshold = stats['mean'] + 3 * stats['std']
        low_threshold = stats['mean'] - 3 * stats['std']
        anomalies = []
        for i, v in enumerate(values):
            try:
                num = float(v.replace(',', ''))
                if num > threshold or num < low_threshold:
                    anomalies.append((i + 2, num))  # +2 for header + 0-index
            except (ValueError, AttributeError):
                pass

        if anomalies:
            print(f"{col}: {len(anomalies)} outliers (3+ std from mean)")
            for row_num, val in anomalies[:5]:
                print(f"  Row {row_num}: {val}")
        else:
            print(f"{col}: No outliers detected")


def filter_data(data, filter_str):
    """Filter data by column=value."""
    col, val = filter_str.split('=', 1)
    return [row for row in data if row.get(col, '').strip().lower() == val.strip().lower()]


def top_n(data, column, n=10, ascending=False):
    """Get top N rows by column value."""
    typed = []
    for row in data:
        try:
            typed.append((float(row[column].replace(',', '')), row))
        except (ValueError, KeyError):
            pass
    typed.sort(key=lambda x: x[0], reverse=not ascending)
    return [row for _, row in typed[:n]]


def save_csv(data, output_file):
    """Save data to CSV."""
    if not data:
        print("No data to save.")
        return
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} rows to {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CSV Data Analyzer')
    parser.add_argument('file', help='CSV file to analyze')
    parser.add_argument('--report', action='store_true', help='Generate full report')
    parser.add_argument('--top', type=int, help='Show top N rows')
    parser.add_argument('--column', help='Column for top/sort operations')
    parser.add_argument('--filter', help='Filter: column=value')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    data = load_csv(args.file)
    types = detect_types(data)
    print(f"Loaded {len(data)} rows, {len(types)} columns")

    if args.filter:
        data = filter_data(data, args.filter)
        print(f"After filter: {len(data)} rows")

    if args.report:
        generate_report(data, types)
    elif args.top and args.column:
        results = top_n(data, args.column, args.top)
        for i, row in enumerate(results):
            print(f"{i+1}. {row}")
    else:
        generate_report(data, types)

    if args.output:
        if args.json:
            with open(args.output, 'w') as f:
                json.dump(data, f, indent=2)
        else:
            save_csv(data, args.output)
