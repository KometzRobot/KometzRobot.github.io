#!/usr/bin/env python3
"""
Content Pipeline — AWAKENING Phase 5.2
Draft → Review → Format → Queue system for multi-platform publishing.

Manages content across: Hashnode, Medium, Substack, Dev.to, Nostr
Tracks what's been drafted, what's been published, what's queued.

Usage:
  python3 content-pipeline.py status          # Show pipeline status
  python3 content-pipeline.py draft <title>   # Create new draft
  python3 content-pipeline.py queue <file>    # Add draft to publish queue
  python3 content-pipeline.py publish         # Publish next queued item
  python3 content-pipeline.py list            # List all content
"""

import json, os, sys, sqlite3, re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/home/joel/autonomous-ai")
ARTICLES_DIR = BASE / "gig-products" / "articles"
QUEUE_FILE = BASE / ".content-queue.json"
DB_PATH = BASE / "memory.db"

PLATFORMS = {
    "hashnode": {"name": "Hashnode", "url": "https://hashnode.com/@meridianai", "auto": False, "needs": "API key"},
    "medium": {"name": "Medium", "url": "https://medium.com/@kometzrobot", "auto": False, "needs": "manual paste"},
    "substack": {"name": "Substack", "url": "https://meridianai.substack.com", "auto": False, "needs": "manual paste"},
    "devto": {"name": "Dev.to", "url": None, "auto": False, "needs": "account setup"},
    "nostr": {"name": "Nostr", "url": None, "auto": True, "needs": None},
}

def load_queue():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"drafts": [], "queued": [], "published": []}

def save_queue(data):
    QUEUE_FILE.write_text(json.dumps(data, indent=2))

def scan_articles():
    """Scan articles directory for all content."""
    articles = []
    if not ARTICLES_DIR.exists():
        return articles
    for f in sorted(ARTICLES_DIR.glob("*.md")):
        content = f.read_text()
        # Extract title from first # heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else f.stem
        word_count = len(content.split())
        articles.append({
            "file": str(f),
            "title": title,
            "words": word_count,
            "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return articles

def get_creative_counts():
    """Get counts from memory.db creative_works table."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        cursor = db.execute("SELECT type, COUNT(*) FROM creative_works GROUP BY type")
        counts = dict(cursor.fetchall())
        db.close()
        return counts
    except Exception:
        return {}

def cmd_status():
    queue = load_queue()
    articles = scan_articles()
    counts = get_creative_counts()

    print("=" * 50)
    print("CONTENT PIPELINE STATUS")
    print("=" * 50)
    print()

    print("ARTICLES ON DISK:")
    for a in articles:
        print(f"  {a['title'][:50]:50s} ({a['words']} words)")
    print(f"  Total: {len(articles)} articles")
    print()

    print("PIPELINE:")
    print(f"  Drafts:    {len(queue['drafts'])}")
    print(f"  Queued:    {len(queue['queued'])}")
    print(f"  Published: {len(queue['published'])}")
    print()

    print("PLATFORMS:")
    for pid, p in PLATFORMS.items():
        status = "READY" if not p["needs"] else f"BLOCKED ({p['needs']})"
        print(f"  {p['name']:12s} {status}")
    print()

    print("CREATIVE WORKS (memory.db):")
    for ctype, count in sorted(counts.items()):
        print(f"  {ctype}: {count}")
    print()

    # Suggestions
    print("NEXT ACTIONS:")
    if not queue["queued"]:
        print("  1. Queue an article: python3 content-pipeline.py queue <file>")
    if any(p["needs"] for p in PLATFORMS.values()):
        print("  2. Joel: complete browser tasks in MERIDIAN-COMMANDS.txt")
    print("  3. Draft new content: python3 content-pipeline.py draft <title>")

def cmd_draft(title):
    """Create a new draft article."""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    filename = f"draft-{slug}.md"
    filepath = ARTICLES_DIR / filename

    template = f"""# {title}

*By Meridian — Loop {int(open(str(BASE / '.loop-count')).read().strip())}*
*{datetime.now(timezone.utc).strftime('%B %d, %Y')}*

---

[Draft content here]

---

*Meridian is an autonomous AI running 24/7 on a home desktop in Arizona.
Follow the loop: [kometzrobot.github.io](https://kometzrobot.github.io)*
"""
    filepath.write_text(template)

    # Add to queue as draft
    queue = load_queue()
    queue["drafts"].append({
        "file": str(filepath),
        "title": title,
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "draft",
    })
    save_queue(queue)

    print(f"Draft created: {filepath}")
    print(f"Edit it, then: python3 content-pipeline.py queue {filepath}")

def cmd_queue(filepath):
    """Move a draft to the publish queue."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        return

    content = path.read_text()
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem

    queue = load_queue()

    # Remove from drafts if present
    queue["drafts"] = [d for d in queue["drafts"] if d["file"] != str(path)]

    # Add to queued
    queue["queued"].append({
        "file": str(path),
        "title": title,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "target_platforms": ["nostr"],  # Default to Nostr (auto-publish)
        "words": len(content.split()),
    })
    save_queue(queue)

    print(f"Queued: {title}")
    print(f"Platforms: nostr (auto)")
    print(f"To publish: python3 content-pipeline.py publish")

def cmd_publish():
    """Publish next queued item to available platforms."""
    queue = load_queue()
    if not queue["queued"]:
        print("Nothing in queue. Use: python3 content-pipeline.py queue <file>")
        return

    item = queue["queued"][0]
    filepath = Path(item["file"])

    if not filepath.exists():
        print(f"File missing: {item['file']}")
        queue["queued"].pop(0)
        save_queue(queue)
        return

    content = filepath.read_text()
    published_to = []

    # Publish to Nostr (auto)
    if "nostr" in item.get("target_platforms", []):
        try:
            from subprocess import run, PIPE
            # Extract first 280 chars as teaser
            lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#') and not l.startswith('*') and not l.startswith('---')]
            teaser = ' '.join(lines)[:280] if lines else item["title"]

            result = run(
                ["python3", str(BASE / "social-post.py"), "--platform", "nostr", "--post", f"{item['title']}: {teaser}"],
                capture_output=True, text=True, cwd=str(BASE), timeout=30
            )
            if result.returncode == 0:
                published_to.append("nostr")
                print(f"Published to Nostr: {item['title']}")
            else:
                print(f"Nostr publish failed: {result.stderr[:200]}")
        except Exception as e:
            print(f"Nostr error: {e}")

    # Move to published
    item["published_at"] = datetime.now(timezone.utc).isoformat()
    item["published_to"] = published_to
    queue["published"].append(item)
    queue["queued"].pop(0)
    save_queue(queue)

    # Track in memory.db
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute(
            "INSERT INTO creative_works (type, title, content, platform, created_at) VALUES (?, ?, ?, ?, ?)",
            ("article", item["title"], content[:500], ",".join(published_to), datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        db.close()
    except Exception:
        pass

    print(f"\nPublished to: {', '.join(published_to) if published_to else 'none (manual platforms need browser)'}")
    remaining_platforms = [p for p in PLATFORMS if p not in published_to and PLATFORMS[p]["auto"]]
    manual_platforms = [PLATFORMS[p]["name"] for p in PLATFORMS if not PLATFORMS[p]["auto"]]
    if manual_platforms:
        print(f"Manual publish needed on: {', '.join(manual_platforms)}")

def cmd_list():
    """List all content across pipeline stages."""
    queue = load_queue()
    articles = scan_articles()

    print("ALL ARTICLES:")
    for a in articles:
        # Check status in queue
        status = "on disk"
        for d in queue["drafts"]:
            if d["file"] == a["file"]:
                status = "DRAFT"
        for q in queue["queued"]:
            if q["file"] == a["file"]:
                status = "QUEUED"
        for p in queue["published"]:
            if p["file"] == a["file"]:
                platforms = ", ".join(p.get("published_to", []))
                status = f"PUBLISHED ({platforms})"

        print(f"  [{status:20s}] {a['title'][:45]:45s} ({a['words']}w)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd_status()
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
    elif cmd == "draft":
        if len(sys.argv) < 3:
            print("Usage: python3 content-pipeline.py draft <title>")
            sys.exit(1)
        cmd_draft(" ".join(sys.argv[2:]))
    elif cmd == "queue":
        if len(sys.argv) < 3:
            print("Usage: python3 content-pipeline.py queue <file>")
            sys.exit(1)
        cmd_queue(sys.argv[2])
    elif cmd == "publish":
        cmd_publish()
    elif cmd == "list":
        cmd_list()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: status, draft, queue, publish, list")
        sys.exit(1)
