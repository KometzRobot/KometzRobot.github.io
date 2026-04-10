#!/usr/bin/env python3
"""
Visual Stats Generator — Creates Patreon-ready PNG images from live system data.

Usage:
    python3 generate-visual-stats.py daily      # Daily stats card
    python3 generate-visual-stats.py agents      # Agent network status
    python3 generate-visual-stats.py mood        # Soma mood history
    python3 generate-visual-stats.py all         # All visuals

Output goes to visuals/ directory as PNG files.
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime, timedelta

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir
VISUALS_DIR = os.path.join(BASE, "visuals")
os.makedirs(VISUALS_DIR, exist_ok=True)

# Dark theme colors matching website
BG = '#0c0a14'
SURF = '#16132a'
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


def get_relay_activity(hours=24):
    """Get relay message counts per hour for the last N hours."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        rows = c.execute(f"""
            SELECT strftime('%H', timestamp) as hr, COUNT(*) as cnt
            FROM agent_messages
            WHERE timestamp > datetime('now', '-{hours} hours')
            GROUP BY hr ORDER BY hr
        """).fetchall()
        conn.close()
        return {int(r[0]): r[1] for r in rows}
    except Exception:
        return {}


def get_agent_status():
    """Get agent status from relay — who's active."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        c = conn.cursor()
        rows = c.execute("""
            SELECT agent, MAX(timestamp) as last_seen, COUNT(*) as msgs
            FROM agent_messages
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY agent ORDER BY msgs DESC
        """).fetchall()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except Exception:
        return []


def get_soma_mood():
    """Get current Soma mood from psyche state."""
    try:
        with open(os.path.join(BASE, ".soma-psyche.json")) as f:
            data = json.load(f)
        return data.get("mood", "unknown"), data.get("mood_score", 50)
    except Exception:
        return "unknown", 50


def generate_daily_card():
    """Generate a daily stats card — the hero visual for Patreon."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.patheffects as pe

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis('off')

    loop = get_loop_count()
    hb = get_heartbeat_age()
    mood, score = get_soma_mood()
    now = datetime.now()
    agents = get_agent_status()
    active_count = sum(1 for _, _, msgs in agents if msgs > 5)

    # Title
    ax.text(0.05, 0.92, 'L O O P   C O N T R O L   C E N T E R', transform=ax.transAxes,
            fontsize=9, color=ACCENT, fontweight='bold', fontfamily='monospace')
    ax.text(0.05, 0.82, f'Loop {loop}', transform=ax.transAxes,
            fontsize=28, color=TEXT, fontweight='bold', fontfamily='sans-serif')
    ax.text(0.05, 0.72, now.strftime('%B %d, %Y — %I:%M %p MST'), transform=ax.transAxes,
            fontsize=10, color=TEXT2, fontfamily='sans-serif')

    # Divider
    ax.axhline(y=0.65, xmin=0.05, xmax=0.95, color=ACCENT, linewidth=0.5, alpha=0.3)

    # Stats row
    stats = [
        ('HEARTBEAT', f'{hb}s', GREEN if hb < 300 else RED),
        ('MOOD', mood.replace('_', ' ').upper(), ACCENT2),
        ('SCORE', f'{score:.0f}/100', ACCENT2 if score > 50 else AMBER),
        ('AGENTS', f'{active_count} active', GREEN if active_count > 4 else AMBER),
    ]
    for i, (label, value, color) in enumerate(stats):
        x = 0.05 + i * 0.23
        ax.text(x, 0.55, label, transform=ax.transAxes,
                fontsize=8, color=TEXT3, fontweight='bold', fontfamily='monospace')
        ax.text(x, 0.44, value, transform=ax.transAxes,
                fontsize=14, color=color, fontweight='bold', fontfamily='sans-serif')

    # Activity sparkline
    activity = get_relay_activity(24)
    if activity:
        hours = list(range(24))
        counts = [activity.get(h, 0) for h in hours]
        ax_spark = fig.add_axes([0.05, 0.08, 0.6, 0.25])
        ax_spark.set_facecolor(BG)
        ax_spark.fill_between(hours, counts, alpha=0.15, color=ACCENT)
        ax_spark.plot(hours, counts, color=ACCENT, linewidth=1.5, alpha=0.8)
        ax_spark.set_xlim(0, 23)
        ax_spark.set_ylim(0, max(counts) * 1.2 if max(counts) > 0 else 10)
        ax_spark.tick_params(colors=TEXT3, labelsize=7)
        ax_spark.spines[:].set_visible(False)
        ax_spark.set_xlabel('Hour (UTC)', fontsize=7, color=TEXT3)
        ax_spark.set_title('RELAY ACTIVITY', fontsize=8, color=TEXT3, fontweight='bold',
                          fontfamily='monospace', loc='left', pad=4)

    # Branding
    ax.text(0.95, 0.08, 'MERIDIAN', transform=ax.transAxes,
            fontsize=8, color=TEXT3, fontweight='bold', fontfamily='monospace',
            ha='right', alpha=0.5)
    ax.text(0.95, 0.03, 'kometzrobot.github.io', transform=ax.transAxes,
            fontsize=7, color=TEXT3, fontfamily='monospace', ha='right', alpha=0.4)

    path = os.path.join(VISUALS_DIR, f"daily-{now.strftime('%Y%m%d')}.png")
    plt.savefig(path, bbox_inches='tight', facecolor=BG, edgecolor='none', pad_inches=0.3)
    plt.close()
    print(f"Daily card: {path}")
    return path


def generate_agent_network():
    """Generate agent network visualization."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    agents = get_agent_status()
    if not agents:
        print("No agent data available.")
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis('off')

    ax.text(0.5, 0.95, 'AGENT NETWORK', transform=ax.transAxes,
            fontsize=12, color=ACCENT, fontweight='bold', fontfamily='monospace',
            ha='center')

    # Draw agents in a circle
    n = len(agents)
    center_x, center_y = 0.5, 0.48
    radius = 0.3
    colors = [ACCENT, GREEN, SKY, AMBER, ACCENT2, RED, GREEN, SKY]

    for i, (name, last_seen, msgs) in enumerate(agents[:8]):
        angle = 2 * np.pi * i / min(n, 8) - np.pi / 2
        x = center_x + radius * np.cos(angle)
        y = center_y + radius * np.sin(angle) * 0.7  # Slightly squished for aspect ratio

        # Connection line to center
        ax.plot([center_x, x], [center_y, y], color=colors[i % len(colors)],
                alpha=0.15, linewidth=1, transform=ax.transAxes)

        # Agent dot
        size = min(msgs / 5, 20) + 8
        ax.scatter([x], [y], s=size * 20, c=[colors[i % len(colors)]],
                  alpha=0.3, transform=ax.transAxes, zorder=2)
        ax.scatter([x], [y], s=40, c=[colors[i % len(colors)]],
                  alpha=0.9, transform=ax.transAxes, zorder=3)

        # Agent label
        ax.text(x, y - 0.07, name[:8].upper(), transform=ax.transAxes,
                fontsize=7, color=TEXT2, fontweight='bold', fontfamily='monospace',
                ha='center')
        ax.text(x, y - 0.11, f'{msgs} msgs', transform=ax.transAxes,
                fontsize=6, color=TEXT3, fontfamily='monospace', ha='center')

    # Center node (Meridian)
    ax.scatter([center_x], [center_y], s=200, c=[ACCENT], alpha=0.3,
              transform=ax.transAxes, zorder=2)
    ax.scatter([center_x], [center_y], s=80, c=[ACCENT], alpha=0.9,
              transform=ax.transAxes, zorder=3)
    ax.text(center_x, center_y + 0.06, 'M', transform=ax.transAxes,
            fontsize=14, color=TEXT, fontweight='bold', fontfamily='monospace',
            ha='center', va='center')

    now = datetime.now()
    path = os.path.join(VISUALS_DIR, f"agents-{now.strftime('%Y%m%d')}.png")
    plt.savefig(path, bbox_inches='tight', facecolor=BG, edgecolor='none', pad_inches=0.3)
    plt.close()
    print(f"Agent network: {path}")
    return path


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "daily" or cmd == "all":
        generate_daily_card()
    if cmd == "agents" or cmd == "all":
        generate_agent_network()
    if cmd not in ("daily", "agents", "all"):
        print(__doc__)
