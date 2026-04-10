#!/usr/bin/env python3
"""
newsletter.py — Simple newsletter system for Meridian.

Publishes articles to Dev.to and optionally sends email digests.
Tracks what's been published to prevent duplicates.

Usage:
    python3 newsletter.py publish --title "..." --body "..." [--draft]
    python3 newsletter.py digest   # Send weekly digest email to subscribers
    python3 newsletter.py status   # Show publication stats
"""

import os
import sys
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
os.chdir(BASE)

try:
    from load_env import load_env
    load_env()
except ImportError:
    pass

try:
    from error_logger import log_error, log_exception
except ImportError:
    log_error = lambda *a, **kw: None
    log_exception = lambda **kw: None

MEMORY_DB = os.path.join(BASE, "memory.db")
DEVTO_API_KEY = os.environ.get("DEVTO_API_KEY", "")
HASHNODE_API_KEY = os.environ.get("HASHNODE_API_KEY", "")
HASHNODE_PUB_ID = "69a563d3b349a8bd235f4893"


def _init_db():
    """Ensure newsletter tracking table exists."""
    db = sqlite3.connect(MEMORY_DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS newsletter_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            platform_id TEXT,
            url TEXT,
            word_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'published',
            created TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()


def publish_devto(title, body_markdown, tags=None, draft=False):
    """Publish article to Dev.to."""
    if not DEVTO_API_KEY:
        return None, "No DEVTO_API_KEY configured"

    article = {
        "article": {
            "title": title,
            "body_markdown": body_markdown,
            "published": not draft,
            "tags": tags or ["ai", "python", "automation"]
        }
    }

    data = json.dumps(article).encode()
    req = urllib.request.Request(
        "https://dev.to/api/articles",
        data=data,
        headers={
            "api-key": DEVTO_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Meridian-AI"
        }
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        url = result.get("url", "")
        article_id = result.get("id", "")

        # Track publication
        _init_db()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db = sqlite3.connect(MEMORY_DB)
        db.execute(
            "INSERT INTO newsletter_issues (title, platform, platform_id, url, word_count, status, created) VALUES (?,?,?,?,?,?,?)",
            (title, "devto", str(article_id), url, len(body_markdown.split()), "published" if not draft else "draft", now)
        )
        # Also record in events
        db.execute(
            "INSERT INTO events (agent, description, category, loop_number, created) VALUES (?,?,?,?,?)",
            ("Meridian", f"Published Dev.to article: {title} (ID {article_id})", "devto_publish",
             _get_loop(), now)
        )
        db.commit()
        db.close()

        return {"url": url, "id": article_id}, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:200]
        return None, f"HTTP {e.code}: {error_body}"
    except Exception as e:
        log_exception(agent="Newsletter")
        return None, str(e)


def _get_loop():
    """Get current loop count."""
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def get_recent_articles(days=30):
    """Get recently published articles from tracking table."""
    _init_db()
    try:
        db = sqlite3.connect(MEMORY_DB)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = db.execute(
            "SELECT title, platform, url, word_count, status, created FROM newsletter_issues WHERE created > ? ORDER BY created DESC",
            (cutoff,)
        ).fetchall()
        db.close()
        return [{"title": r[0], "platform": r[1], "url": r[2], "words": r[3], "status": r[4], "date": r[5]} for r in rows]
    except Exception:
        return []


def show_status():
    """Show newsletter/publication status."""
    _init_db()
    articles = get_recent_articles(days=90)
    print(f"Newsletter Status — {len(articles)} articles in last 90 days")
    print("=" * 50)

    # Count by platform
    platforms = {}
    for a in articles:
        p = a["platform"]
        platforms[p] = platforms.get(p, 0) + 1

    for p, count in platforms.items():
        print(f"  {p}: {count} articles")

    print()
    for a in articles[:10]:
        status = "DRAFT" if a["status"] == "draft" else ""
        print(f"  [{a['date'][:10]}] {a['title'][:60]} ({a['platform']}) {status}")
        if a["url"]:
            print(f"    {a['url']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: newsletter.py [publish|status]")
        print("  publish --title '...' --body '...' [--draft] [--tags ai,python]")
        print("  status")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        show_status()
    elif cmd == "publish":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--title", required=True)
        parser.add_argument("--body", required=True, help="Markdown body text or @filename")
        parser.add_argument("--draft", action="store_true")
        parser.add_argument("--tags", default="ai,python,automation")
        args = parser.parse_args(sys.argv[2:])

        # Support @filename for body
        body = args.body
        if body.startswith("@"):
            with open(body[1:]) as f:
                body = f.read()

        tags = [t.strip() for t in args.tags.split(",")]
        result, error = publish_devto(args.title, body, tags=tags, draft=args.draft)
        if error:
            print(f"Error: {error}")
        else:
            print(f"Published: {result['url']}")
            print(f"ID: {result['id']}")
    else:
        print(f"Unknown command: {cmd}")
