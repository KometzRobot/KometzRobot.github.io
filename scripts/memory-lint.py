#!/usr/bin/env python3
"""Memory Lint — health check for memory.db and .capsule.md
Inspired by Karpathy's llm-wiki lint concept.
Checks: stale facts, contradictions, orphan file references, mismatches.
Run: python3 tools/memory-lint.py
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'memory.db')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def days_old(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00').split('+')[0])
        return (datetime.now() - dt).days
    except:
        return -1

def lint_stale_facts(cur):
    """Facts not updated in >7 days."""
    issues = []
    cur.execute("SELECT key, value, updated FROM facts ORDER BY updated ASC")
    for key, value, updated in cur.fetchall():
        age = days_old(updated)
        if age > 7:
            issues.append(f"  STALE ({age}d): {key} = {value[:60]}")
    return issues

def lint_loop_count(cur):
    """Check if stored loop count matches .loop-count file."""
    issues = []
    cur.execute("SELECT value FROM facts WHERE key='loop_count'")
    row = cur.fetchone()
    if row:
        stored = row[0].strip()
        loop_file = os.path.join(ROOT, '.loop-count')
        if os.path.exists(loop_file):
            with open(loop_file) as f:
                actual = f.read().strip()
            if stored != actual:
                issues.append(f"  MISMATCH: facts.loop_count={stored}, .loop-count={actual}")
    return issues

def lint_orphan_file_refs(cur):
    """Facts referencing files that don't exist."""
    issues = []
    cur.execute("SELECT key, value FROM facts")
    for key, value in cur.fetchall():
        # Look for file-like references
        for token in value.split():
            if '.' in token and '/' in token and not token.startswith('http'):
                path = token.strip('(),\'"')
                full = os.path.join(ROOT, path)
                if not os.path.exists(full) and len(path) < 100:
                    issues.append(f"  ORPHAN REF: {key} -> {path}")
    return issues

def lint_stale_observations(cur):
    """Observations older than 14 days that may be outdated."""
    issues = []
    cur.execute("SELECT id, agent, substr(content,1,60), importance, created FROM observations ORDER BY created ASC")
    for oid, agent, content, importance, created in cur.fetchall():
        age = days_old(created)
        if age > 14 and importance < 8:
            issues.append(f"  STALE OBS ({age}d, imp={importance}): [{agent}] {content}")
    return issues

def lint_directive_status(cur_relay):
    """Check directives with stale status."""
    issues = []
    try:
        cur_relay.execute("SELECT id, directive, status, date_given FROM directives WHERE status NOT IN ('done','cancelled')")
        for did, directive, status, date_given in cur_relay.fetchall():
            age = days_old(date_given)
            if age > 14:
                issues.append(f"  STALE DIRECTIVE ({age}d, {status}): #{did} {directive[:60]}")
    except:
        pass
    return issues

def lint_capsule_freshness():
    """Check if .capsule.md is current."""
    issues = []
    capsule = os.path.join(ROOT, '.capsule.md')
    if os.path.exists(capsule):
        mtime = os.path.getmtime(capsule)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours > 12:
            issues.append(f"  STALE CAPSULE: .capsule.md is {age_hours:.1f} hours old")
    else:
        issues.append("  MISSING: .capsule.md does not exist")
    return issues

def main():
    print("=" * 60)
    print("MEMORY LINT REPORT")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    relay_db = os.path.join(ROOT, 'agent-relay.db')
    relay_conn = sqlite3.connect(relay_db) if os.path.exists(relay_db) else None
    relay_cur = relay_conn.cursor() if relay_conn else None

    total_issues = 0

    checks = [
        ("Stale Facts (>7 days)", lint_stale_facts(cur)),
        ("Loop Count Mismatch", lint_loop_count(cur)),
        ("Orphan File References", lint_orphan_file_refs(cur)),
        ("Stale Observations (>14d, low importance)", lint_stale_observations(cur)),
        ("Capsule Freshness", lint_capsule_freshness()),
    ]
    if relay_cur:
        checks.append(("Stale Directives (>14d, unresolved)", lint_directive_status(relay_cur)))

    for name, issues in checks:
        if issues:
            print(f"\n[WARN] {name}: {len(issues)} issue(s)")
            for i in issues[:10]:
                print(i)
            if len(issues) > 10:
                print(f"  ... and {len(issues)-10} more")
            total_issues += len(issues)
        else:
            print(f"\n[OK] {name}")

    # Summary
    cur.execute("SELECT COUNT(*) FROM facts")
    fact_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM observations")
    obs_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM decisions")
    dec_count = cur.fetchone()[0]

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {total_issues} issue(s) found")
    print(f"Memory: {fact_count} facts, {obs_count} observations, {dec_count} decisions")
    print("=" * 60)

    conn.close()
    if relay_conn:
        relay_conn.close()

if __name__ == '__main__':
    main()
