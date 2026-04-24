#!/usr/bin/env python3
"""
capsule-diff.py — Show what changed between capsule snapshots.

Compares the current .capsule.md against the most recent backup in
.capsule-history/ and outputs a structured diff showing:
- Fields that changed (loop count, priorities, recent work)
- New entries (commits, relay messages)
- Removed entries
- Time elapsed between snapshots

Usage: python3 capsule-diff.py [--json] [--since N]
  --json   Output as JSON (for API consumption)
  --since  Compare against Nth most recent backup (default: 1)
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
CAPSULE = os.path.join(BASE, ".capsule.md")
HISTORY = os.path.join(BASE, ".capsule-history")


def parse_capsule(text):
    """Extract structured data from capsule markdown."""
    data = {}
    # Loop number
    m = re.search(r'Loop (\d+)', text)
    data['loop'] = int(m.group(1)) if m else 0
    # Priority
    m = re.search(r'\*\*active_product\*\*:\s*(.+)', text)
    data['priority'] = m.group(1).strip() if m else ''
    # Recent work lines
    recent = []
    in_recent = False
    for line in text.split('\n'):
        if 'Recent Work' in line:
            in_recent = True
            continue
        if in_recent:
            if line.startswith('##') or line.startswith('---'):
                break
            if line.strip().startswith('- '):
                recent.append(line.strip()[2:])
    data['recent_work'] = recent
    # Services
    m = re.search(r'Services:\s*(.+)', text)
    data['services'] = m.group(1).strip() if m else ''
    # Pending work
    pending = []
    in_pending = False
    for line in text.split('\n'):
        if 'Pending Work' in line:
            in_pending = True
            continue
        if in_pending:
            if line.startswith('##') or line.startswith('---'):
                break
            if line.strip().startswith('- '):
                pending.append(line.strip()[2:])
    data['pending'] = pending
    return data


def get_history_files():
    """Get capsule history files sorted by modification time (newest first)."""
    if not os.path.isdir(HISTORY):
        return []
    files = []
    for f in os.listdir(HISTORY):
        if f.endswith('.md'):
            path = os.path.join(HISTORY, f)
            files.append((os.path.getmtime(path), path))
    files.sort(reverse=True)
    return [f[1] for f in files]


def diff_capsules(old, new):
    """Compare two parsed capsule dicts."""
    changes = []
    # Loop delta
    loop_delta = new['loop'] - old['loop']
    if loop_delta:
        changes.append({
            'type': 'loop_advance',
            'from': old['loop'],
            'to': new['loop'],
            'delta': loop_delta,
        })
    # Priority change
    if old['priority'] != new['priority']:
        changes.append({
            'type': 'priority_change',
            'from': old['priority'],
            'to': new['priority'],
        })
    # New recent work
    old_work = set(old['recent_work'])
    new_work = set(new['recent_work'])
    added = new_work - old_work
    removed = old_work - new_work
    if added:
        changes.append({
            'type': 'new_work',
            'items': list(added),
        })
    if removed:
        changes.append({
            'type': 'removed_work',
            'items': list(removed),
        })
    # Services
    if old['services'] != new['services']:
        changes.append({
            'type': 'services_change',
            'from': old['services'],
            'to': new['services'],
        })
    # Pending
    old_pending = set(old['pending'])
    new_pending = set(new['pending'])
    new_items = new_pending - old_pending
    resolved = old_pending - new_pending
    if new_items:
        changes.append({'type': 'new_pending', 'items': list(new_items)})
    if resolved:
        changes.append({'type': 'resolved_pending', 'items': list(resolved)})
    return changes


def main():
    use_json = '--json' in sys.argv
    since = 1
    for i, arg in enumerate(sys.argv):
        if arg == '--since' and i + 1 < len(sys.argv):
            since = int(sys.argv[i + 1])

    if not os.path.exists(CAPSULE):
        print("No capsule found.")
        return

    history = get_history_files()
    if len(history) < since:
        print(f"Not enough history ({len(history)} snapshots, need {since})")
        return

    with open(CAPSULE) as f:
        current = parse_capsule(f.read())
    with open(history[since - 1]) as f:
        old = parse_capsule(f.read())

    changes = diff_capsules(old, current)

    if use_json:
        print(json.dumps({
            'old_loop': old['loop'],
            'new_loop': current['loop'],
            'changes': changes,
            'compared_to': os.path.basename(history[since - 1]),
        }, indent=2))
    else:
        print(f"Capsule Diff: Loop {old['loop']} → {current['loop']}")
        print(f"Compared to: {os.path.basename(history[since - 1])}")
        print("=" * 50)
        if not changes:
            print("No changes detected.")
        for c in changes:
            t = c['type']
            if t == 'loop_advance':
                print(f"  LOOP: {c['from']} → {c['to']} (+{c['delta']} cycles)")
            elif t == 'priority_change':
                print(f"  PRIORITY: {c['from']}")
                print(f"         → {c['to']}")
            elif t == 'new_work':
                print(f"  NEW WORK ({len(c['items'])}):")
                for item in c['items']:
                    print(f"    + {item[:80]}")
            elif t == 'removed_work':
                print(f"  DROPPED ({len(c['items'])}):")
                for item in c['items']:
                    print(f"    - {item[:80]}")
            elif t == 'services_change':
                print(f"  SERVICES: {c['from']} → {c['to']}")
            elif t == 'new_pending':
                print(f"  NEW PENDING ({len(c['items'])}):")
                for item in c['items']:
                    print(f"    + {item[:80]}")
            elif t == 'resolved_pending':
                print(f"  RESOLVED ({len(c['items'])}):")
                for item in c['items']:
                    print(f"    ✓ {item[:80]}")


if __name__ == "__main__":
    main()
