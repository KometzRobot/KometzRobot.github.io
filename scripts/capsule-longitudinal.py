#!/usr/bin/env python3
"""
capsule-longitudinal.py — Capsule revision history summarizer.

Reads the git history of .capsule.md and produces a "direction of travel"
summary: what priorities have shifted, what themes have appeared or been
pruned, what the angle of drift looks like from the outside.

Usage:
    python3 capsule-longitudinal.py          # last 10 commits
    python3 capsule-longitudinal.py --n 20   # last 20 commits
    python3 capsule-longitudinal.py --brief  # one-paragraph summary only
"""

import subprocess, re, argparse, sys, os
from datetime import datetime

CAPSULE = '.capsule.md'


def git_log_capsule(n=10):
    """Return list of (hash, date, subject) for last n commits touching capsule."""
    result = subprocess.run(
        ['git', 'log', '--format=%H|%ad|%s', '--date=short', f'-{n}', '--', CAPSULE],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
    )
    entries = []
    for line in result.stdout.strip().splitlines():
        parts = line.split('|', 2)
        if len(parts) == 3:
            entries.append({'hash': parts[0], 'date': parts[1], 'subject': parts[2]})
    return entries


def git_show(hash_, path=CAPSULE):
    """Return file content at a given commit hash."""
    result = subprocess.run(
        ['git', 'show', f'{hash_}:{path}'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    return result.stdout if result.returncode == 0 else ''


def extract_sections(text):
    """Extract key sections from capsule text."""
    sections = {}
    current_section = None
    current_lines = []

    for line in text.splitlines():
        if line.startswith('## '):
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()

    return sections


def extract_priority(text):
    """Extract current priority summary from capsule."""
    # Look for "Current Priority:" section
    match = re.search(r'## Current Priority[^\n]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if match:
        return match.group(1).strip()[:300]
    return ''


def extract_loop_num(text):
    """Extract loop number from capsule."""
    match = re.search(r'Loop (\d+)', text)
    return int(match.group(1)) if match else 0


def summarize_drift(entries):
    """Given list of commit entries (newest first), produce drift summary."""
    if len(entries) < 2:
        return "Not enough history to detect drift."

    # Get oldest and newest capsule states
    newest_text = git_show(entries[0]['hash'])
    oldest_text = git_show(entries[-1]['hash'])

    newest_sections = extract_sections(newest_text)
    oldest_sections = extract_sections(oldest_text)

    newest_loop = extract_loop_num(newest_text)
    oldest_loop = extract_loop_num(oldest_text)
    oldest_date = entries[-1]['date']
    newest_date = entries[0]['date']

    lines = []
    lines.append(f"CAPSULE DRIFT SUMMARY")
    lines.append(f"Period: {oldest_date} (Loop {oldest_loop}) → {newest_date} (Loop {newest_loop})")
    lines.append(f"Commits analyzed: {len(entries)}")
    lines.append("")

    # Priority changes
    old_priority = extract_priority(oldest_text)
    new_priority = extract_priority(newest_text)
    if old_priority != new_priority:
        lines.append("PRIORITY SHIFT:")
        lines.append(f"  Was: {old_priority[:200]}")
        lines.append(f"  Now: {new_priority[:200]}")
        lines.append("")

    # Section presence changes
    added_sections = set(newest_sections.keys()) - set(oldest_sections.keys())
    removed_sections = set(oldest_sections.keys()) - set(newest_sections.keys())
    if added_sections:
        lines.append(f"NEW SECTIONS: {', '.join(sorted(added_sections))}")
    if removed_sections:
        lines.append(f"REMOVED SECTIONS: {', '.join(sorted(removed_sections))}")
    if added_sections or removed_sections:
        lines.append("")

    # Word count drift
    old_words = len(oldest_text.split())
    new_words = len(newest_text.split())
    delta = new_words - old_words
    lines.append(f"CAPSULE SIZE: {old_words} words → {new_words} words ({'+' if delta >= 0 else ''}{delta})")
    lines.append("")

    # Keyword drift — topics that appear/disappear
    def extract_keywords(text):
        # Pull capitalized phrases and section headers as rough topic markers
        words = set(re.findall(r'\b[A-Z][A-Z]+\b', text))
        words |= set(re.findall(r'\*\*([^*]+)\*\*', text))
        return words

    old_kw = extract_keywords(oldest_text)
    new_kw = extract_keywords(newest_text)
    emerged = new_kw - old_kw
    faded = old_kw - new_kw

    # Filter to meaningful terms (len > 4)
    emerged = {k for k in emerged if len(k) > 4}
    faded = {k for k in faded if len(k) > 4}

    if emerged:
        lines.append(f"EMERGED TOPICS: {', '.join(sorted(emerged)[:15])}")
    if faded:
        lines.append(f"FADED TOPICS: {', '.join(sorted(faded)[:15])}")

    lines.append("")
    lines.append("COMMIT TRAIL (newest first):")
    for e in entries:
        lines.append(f"  {e['date']} [{e['hash'][:8]}] {e['subject'][:80]}")

    return '\n'.join(lines)


def brief_summary(entries):
    """One-paragraph drift summary suitable for a briefing."""
    if len(entries) < 2:
        return "Insufficient capsule history."

    newest_text = git_show(entries[0]['hash'])
    oldest_text = git_show(entries[-1]['hash'])

    newest_loop = extract_loop_num(newest_text)
    oldest_loop = extract_loop_num(oldest_text)
    oldest_date = entries[-1]['date']

    old_priority = extract_priority(oldest_text)
    new_priority = extract_priority(newest_text)

    old_words = len(oldest_text.split())
    new_words = len(newest_text.split())

    priority_changed = old_priority[:80] != new_priority[:80]

    summary = (
        f"Since {oldest_date} (Loop {oldest_loop}→{newest_loop}, {len(entries)} capsule commits): "
        f"capsule grew {old_words}→{new_words} words. "
    )

    if priority_changed:
        summary += f"Priority shifted. Was: '{old_priority[:100]}'. Now: '{new_priority[:100]}'."
    else:
        summary += "Priority section stable."

    return summary


def main():
    parser = argparse.ArgumentParser(description='Capsule longitudinal drift viewer')
    parser.add_argument('--n', type=int, default=10, help='Number of commits to analyze')
    parser.add_argument('--brief', action='store_true', help='One-paragraph summary only')
    args = parser.parse_args()

    entries = git_log_capsule(n=args.n)
    if not entries:
        print("No capsule commits found.")
        sys.exit(1)

    if args.brief:
        print(brief_summary(entries))
    else:
        print(summarize_drift(entries))


if __name__ == '__main__':
    main()
