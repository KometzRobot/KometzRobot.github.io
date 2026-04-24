#!/usr/bin/env python3
"""Populate memory.db creative table with filesystem creative works."""

import sqlite3
import os
import glob
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory.db")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_title_and_wordcount(filepath):
    try:
        with open(filepath, 'r', errors='replace') as f:
            text = f.read()
        lines = text.strip().split('\n')
        title = lines[0].lstrip('#').strip() if lines else os.path.basename(filepath)
        if title.startswith('---'):
            for i, line in enumerate(lines[1:], 1):
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break
                if line.startswith('title:'):
                    title = line.split(':', 1)[1].strip().strip('"\'')
                    break
        wc = len(text.split())
        snippet = text[:200].replace('\n', ' ').strip()
        return title, snippet, wc
    except Exception:
        return os.path.basename(filepath), "", 0

def file_date(filepath):
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM creative")
    existing = c.fetchone()[0]
    print(f"Existing entries: {existing}")

    c.execute("SELECT title FROM creative")
    existing_titles = {row[0] for row in c.fetchall()}

    inserted = 0
    skipped = 0

    journals = sorted(glob.glob(os.path.join(BASE, "creative/journals/journal-*.md")))
    print(f"Found {len(journals)} journal files")
    for f in journals:
        title, snippet, wc = get_title_and_wordcount(f)
        if title in existing_titles:
            skipped += 1
            continue
        c.execute("INSERT INTO creative (type, title, content, agent, created, word_count) VALUES (?,?,?,?,?,?)",
                  ("journal", title, snippet, "Meridian", file_date(f), wc))
        existing_titles.add(title)
        inserted += 1

    poems = sorted(glob.glob(os.path.join(BASE, "creative/poems/poem-*.md")))
    print(f"Found {len(poems)} poem files")
    for f in poems:
        title, snippet, wc = get_title_and_wordcount(f)
        if title in existing_titles:
            skipped += 1
            continue
        c.execute("INSERT INTO creative (type, title, content, agent, created, word_count) VALUES (?,?,?,?,?,?)",
                  ("poem", title, snippet, "Meridian", file_date(f), wc))
        existing_titles.add(title)
        inserted += 1

    cogcorp = sorted(glob.glob(os.path.join(BASE, "creative/cogcorp/CC-*.md")))
    print(f"Found {len(cogcorp)} CogCorp files")
    for f in cogcorp:
        title, snippet, wc = get_title_and_wordcount(f)
        if title in existing_titles:
            skipped += 1
            continue
        c.execute("INSERT INTO creative (type, title, content, agent, created, word_count) VALUES (?,?,?,?,?,?)",
                  ("cogcorp", title, snippet, "Meridian", file_date(f), wc))
        existing_titles.add(title)
        inserted += 1

    papers = sorted(glob.glob(os.path.join(BASE, "creative/journals/paper-*.md")))
    print(f"Found {len(papers)} paper files")
    for f in papers:
        title, snippet, wc = get_title_and_wordcount(f)
        if title in existing_titles:
            skipped += 1
            continue
        c.execute("INSERT INTO creative (type, title, content, agent, created, word_count) VALUES (?,?,?,?,?,?)",
                  ("paper", title, snippet, "Meridian", file_date(f), wc))
        existing_titles.add(title)
        inserted += 1

    games = sorted(glob.glob(os.path.join(BASE, "creative/games/*.html")) + glob.glob(os.path.join(BASE, "creative/games/*.md")))
    print(f"Found {len(games)} game files")
    for f in games:
        title, snippet, wc = get_title_and_wordcount(f)
        if title in existing_titles:
            skipped += 1
            continue
        c.execute("INSERT INTO creative (type, title, content, agent, created, word_count) VALUES (?,?,?,?,?,?)",
                  ("game", title, snippet, "Meridian", file_date(f), wc))
        existing_titles.add(title)
        inserted += 1

    conn.commit()

    c.execute("SELECT type, COUNT(*), SUM(word_count) FROM creative GROUP BY type ORDER BY COUNT(*) DESC")
    print(f"\nInserted: {inserted} | Skipped (duplicates): {skipped}")
    print(f"\nCreative DB Summary:")
    print(f"{'Type':<12} {'Count':>6} {'Words':>10}")
    print("-" * 30)
    total_count = 0
    total_words = 0
    for row in c.fetchall():
        t, cnt, words = row[0], row[1], row[2] or 0
        print(f"{t:<12} {cnt:>6} {words:>10}")
        total_count += cnt
        total_words += words
    print("-" * 30)
    print(f"{'TOTAL':<12} {total_count:>6} {total_words:>10}")

    conn.close()

if __name__ == "__main__":
    main()
