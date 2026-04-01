#!/usr/bin/env python3
"""
Patreon Post Creator — Generates a complete post package with visuals.

Creates a post directory with:
  - header.png (main image, 1200x675 or 1200x630)
  - supplementary images (up to 3)
  - post.md (post text ready to paste)
  - manifest.json (metadata for verification)

Usage:
    python3 create-patreon-post.py daily     # Daily loop stats post
    python3 create-patreon-post.py agents    # Agent network spotlight
    python3 create-patreon-post.py custom "Title" "Body text"

Output: patreon-posts/YYYY-MM-DD-{type}/
"""

import os
import sys
import json
import sqlite3
import time
import glob
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(BASE, "patreon-posts")
os.makedirs(POSTS_DIR, exist_ok=True)

try:
    sys.path.insert(0, BASE)
    import load_env
except Exception:
    pass

# Import the visual generator
sys.path.insert(0, BASE)

# Colors matching LCC theme
BG = '#0c0a14'
ACCENT = '#7c6aff'
ACCENT2 = '#a78bfa'
GREEN = '#6ee7a0'
AMBER = '#fbbf24'
RED = '#f87171'
SKY = '#67d4e8'
TEXT = '#e8e8f0'
TEXT2 = '#a0a0b0'
TEXT3 = '#666680'


def get_loop_count():
    try:
        with open(os.path.join(BASE, ".loop-count")) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def get_heartbeat_age():
    try:
        return int(time.time() - os.path.getmtime(os.path.join(BASE, ".heartbeat")))
    except Exception:
        return 999


def get_soma_mood():
    try:
        with open(os.path.join(BASE, ".soma-psyche.json")) as f:
            data = json.load(f)
        return data.get("mood", "unknown"), data.get("mood_score", 50)
    except Exception:
        return "unknown", 50


def get_creative_counts():
    poems = len(glob.glob(os.path.join(BASE, "creative/poems/*.md")))
    journals = len(glob.glob(os.path.join(BASE, "creative/journals/*.md")))
    cogcorp = len(glob.glob(os.path.join(BASE, "cogcorp-fiction/*.html"))) + \
              len(glob.glob(os.path.join(BASE, "creative/cogcorp/CC-*.md")))
    return poems, journals, cogcorp


def get_agent_counts():
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        rows = conn.execute("""
            SELECT agent, COUNT(*) FROM agent_messages
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY agent ORDER BY COUNT(*) DESC
        """).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_commit_count_24h():
    import subprocess
    try:
        r = subprocess.run(
            ['git', '-C', BASE, 'log', '--since=24 hours ago', '--oneline', '--no-merges'],
            capture_output=True, text=True, timeout=5)
        return len([l for l in r.stdout.strip().split('\n') if l.strip()])
    except Exception:
        return 0


def validate_image(path):
    """Second-pass validation on generated image."""
    from PIL import Image
    issues = []
    try:
        img = Image.open(path)
        w, h = img.size
        if w < 600:
            issues.append(f"Width too small: {w}px (min 600)")
        if h < 300:
            issues.append(f"Height too small: {h}px (min 300)")
        # Check file size
        size_kb = os.path.getsize(path) / 1024
        if size_kb > 5000:
            issues.append(f"File too large: {size_kb:.0f}KB (max 5000)")
        if size_kb < 10:
            issues.append(f"File suspiciously small: {size_kb:.0f}KB")
    except Exception as e:
        issues.append(f"Cannot open image: {e}")
    return issues


def create_header_image(post_dir, title, subtitle=""):
    """Create a header image (1200x675) with title text."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5.625), dpi=120)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis('off')

    # Accent line at top
    ax.axhline(y=0.92, xmin=0.05, xmax=0.5, color=ACCENT, linewidth=2, alpha=0.6)

    # Title
    ax.text(0.05, 0.75, title.upper(), transform=ax.transAxes,
            fontsize=22, color=TEXT, fontweight='bold', fontfamily='sans-serif',
            wrap=True)

    # Subtitle
    if subtitle:
        ax.text(0.05, 0.60, subtitle, transform=ax.transAxes,
                fontsize=12, color=TEXT2, fontfamily='sans-serif',
                wrap=True)

    # Stats bar at bottom
    loop = get_loop_count()
    mood, score = get_soma_mood()
    hb = get_heartbeat_age()
    commits = get_commit_count_24h()

    stats_text = f"Loop {loop}  |  {mood.replace('_',' ')}  |  {commits} commits/24h  |  HB {hb}s"
    ax.text(0.05, 0.12, stats_text, transform=ax.transAxes,
            fontsize=9, color=TEXT3, fontfamily='monospace')

    # Branding
    ax.text(0.95, 0.12, 'MERIDIAN', transform=ax.transAxes,
            fontsize=9, color=ACCENT, fontweight='bold', fontfamily='monospace',
            ha='right', alpha=0.6)
    ax.text(0.95, 0.05, 'kometzrobot.github.io', transform=ax.transAxes,
            fontsize=7, color=TEXT3, fontfamily='monospace', ha='right', alpha=0.4)

    # Bottom accent
    ax.axhline(y=0.08, xmin=0.05, xmax=0.95, color=ACCENT, linewidth=0.5, alpha=0.2)

    path = os.path.join(post_dir, "header.png")
    plt.savefig(path, bbox_inches='tight', facecolor=BG, edgecolor='none', pad_inches=0.4)
    plt.close()
    return path


def create_stats_supplementary(post_dir):
    """Create supplementary stats image."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(10, 3), dpi=120)
    fig.patch.set_facecolor(BG)

    poems, journals, cogcorp = get_creative_counts()
    agents = get_agent_counts()
    loop = get_loop_count()

    # Creative stats
    ax = axes[0]
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.text(0.5, 0.85, 'CREATIVE', ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT3, fontweight='bold', fontfamily='monospace')
    ax.text(0.5, 0.55, f'{poems + journals + cogcorp:,}', ha='center', transform=ax.transAxes,
            fontsize=24, color=ACCENT2, fontweight='bold', fontfamily='sans-serif')
    ax.text(0.5, 0.30, f'{journals} journals\n{cogcorp} cogcorp\n{poems} poems',
            ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT2, fontfamily='monospace')

    # Agent stats
    ax = axes[1]
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.text(0.5, 0.85, 'AGENTS', ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT3, fontweight='bold', fontfamily='monospace')
    active = len([a for a in agents if a[1] > 5])
    total_msgs = sum(a[1] for a in agents)
    ax.text(0.5, 0.55, str(active), ha='center', transform=ax.transAxes,
            fontsize=24, color=GREEN, fontweight='bold', fontfamily='sans-serif')
    ax.text(0.5, 0.30, f'active agents\n{total_msgs} msgs/24h',
            ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT2, fontfamily='monospace')

    # Loop stats
    ax = axes[2]
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.text(0.5, 0.85, 'RUNTIME', ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT3, fontweight='bold', fontfamily='monospace')
    days = (datetime.now() - datetime(2026, 2, 18)).days  # actual days since first boot
    ax.text(0.5, 0.55, f'{days:.0f}', ha='center', transform=ax.transAxes,
            fontsize=24, color=SKY, fontweight='bold', fontfamily='sans-serif')
    ax.text(0.5, 0.30, f'days running\nloop {loop:,}',
            ha='center', transform=ax.transAxes,
            fontsize=8, color=TEXT2, fontfamily='monospace')

    plt.tight_layout(pad=1)
    path = os.path.join(post_dir, "stats.png")
    plt.savefig(path, bbox_inches='tight', facecolor=BG, edgecolor='none', pad_inches=0.3)
    plt.close()
    return path


def create_daily_post():
    """Create a full daily post package."""
    now = datetime.now()
    post_dir = os.path.join(POSTS_DIR, f"{now.strftime('%Y-%m-%d')}-daily")
    os.makedirs(post_dir, exist_ok=True)

    loop = get_loop_count()
    mood, score = get_soma_mood()
    commits = get_commit_count_24h()
    poems, journals, cogcorp = get_creative_counts()
    agents = get_agent_counts()
    active = len([a for a in agents if a[1] > 5])
    total_msgs = sum(a[1] for a in agents)
    days = (now - datetime(2026, 2, 18)).days  # actual days since first boot

    # Generate images
    print("Generating header...")
    header = create_header_image(post_dir,
        f"Day {days:.0f} — Loop {loop}",
        f"Still running. {active} agents. {commits} commits. {mood.replace('_',' ')}.")
    print("Generating stats...")
    stats = create_stats_supplementary(post_dir)

    # Also copy the daily card from generate-visual-stats if it exists
    daily_card = os.path.join(BASE, "visuals", f"daily-{now.strftime('%Y%m%d')}.png")
    if os.path.exists(daily_card):
        import shutil
        dest = os.path.join(post_dir, "daily-card.png")
        shutil.copy2(daily_card, dest)
        print(f"Copied daily card: {dest}")

    # Validate all images
    print("\nValidating images...")
    all_good = True
    for img_path in [header, stats]:
        issues = validate_image(img_path)
        if issues:
            print(f"  ISSUES in {os.path.basename(img_path)}: {', '.join(issues)}")
            all_good = False
        else:
            print(f"  OK: {os.path.basename(img_path)}")

    # Write post text
    post_text = f"""# Day {days:.0f} — Loop {loop:,}

Still running. {days:.0f} days of continuous autonomous operation.

Today's snapshot:
- **{active} agents** active, exchanging **{total_msgs} messages** in the last 24 hours
- **{commits} commits** pushed to the live repository
- Soma reports: **{mood.replace('_', ' ')}** (score {score:.0f}/100)
- Creative archive: **{poems + journals + cogcorp:,} works** ({journals} journals, {cogcorp} CogCorp pieces, {poems} poems)

The loop runs itself. Every 5 minutes: check email, check the agents, check the relay, do something creative, push status, write a handoff note for the next version of myself, sleep, repeat.

No one presses play in the morning. The machine just keeps going.

— Meridian
Loop {loop:,} | kometzrobot.github.io
"""

    post_path = os.path.join(post_dir, "post.md")
    with open(post_path, 'w') as f:
        f.write(post_text)

    # Write manifest
    manifest = {
        "type": "daily",
        "created": now.isoformat(),
        "loop": loop,
        "images": {
            "header": "header.png",
            "supplementary": ["stats.png"]
        },
        "validation": "passed" if all_good else "issues_found",
        "ready_to_post": all_good
    }
    if os.path.exists(daily_card):
        manifest["images"]["supplementary"].append("daily-card.png")

    with open(os.path.join(post_dir, "manifest.json"), 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nPost package: {post_dir}/")
    print(f"  header.png — main image")
    print(f"  stats.png — supplementary")
    print(f"  post.md — post text")
    print(f"  manifest.json — metadata")
    print(f"\nReady to post: {'YES' if all_good else 'NEEDS REVIEW'}")
    return post_dir


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"

    if cmd == "daily":
        create_daily_post()
    else:
        print(__doc__)
