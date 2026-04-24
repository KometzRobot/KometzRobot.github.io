#!/usr/bin/env python3
"""Generate creative archive stats as JSON for dashboards and visualizations."""

import sqlite3
import json
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory.db")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".archive-stats.json")

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    stats = {"generated": datetime.now().isoformat(), "summary": {}, "by_type": [], "word_distribution": {}}

    c.execute("SELECT COUNT(*), SUM(word_count) FROM creative")
    cnt, words = c.fetchone()
    stats["summary"] = {"total_works": cnt, "total_words": words or 0, "avg_words": (words or 0) // max(cnt, 1)}

    c.execute("SELECT type, COUNT(*), SUM(word_count), AVG(word_count), MIN(word_count), MAX(word_count) FROM creative GROUP BY type ORDER BY SUM(word_count) DESC")
    for row in c.fetchall():
        stats["by_type"].append({
            "type": row[0], "count": row[1], "total_words": row[2] or 0,
            "avg_words": int(row[3] or 0), "min_words": row[4] or 0, "max_words": row[5] or 0
        })

    for t in ["journal", "poem", "cogcorp"]:
        c.execute("""SELECT
            CASE WHEN word_count < 100 THEN '0-99'
                 WHEN word_count < 200 THEN '100-199'
                 WHEN word_count < 300 THEN '200-299'
                 WHEN word_count < 400 THEN '300-399'
                 WHEN word_count < 500 THEN '400-499'
                 ELSE '500+' END as bucket, COUNT(*)
            FROM creative WHERE type=? GROUP BY bucket ORDER BY bucket""", (t,))
        stats["word_distribution"][t] = {row[0]: row[1] for row in c.fetchall()}

    c.execute("SELECT type, title, word_count FROM creative ORDER BY word_count DESC LIMIT 10")
    stats["longest"] = [{"type": r[0], "title": r[1], "words": r[2]} for r in c.fetchall()]

    conn.close()

    with open(OUT, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"Archive stats: {cnt} works, {words:,} words -> {OUT}")

if __name__ == "__main__":
    main()
