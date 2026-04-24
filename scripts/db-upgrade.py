#!/usr/bin/env python3
"""
db-upgrade.py — Database schema upgrades and data population for memory.db
Adds missing tables: feedback, errors, goals, experiments
Populates the empty skills table with actual capabilities.
Built Loop 2121 per Joel's request for self-improvement tools.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def upgrade_schema(conn):
    """Add missing tables to memory.db."""
    cursor = conn.cursor()
    tables_added = []

    # Feedback table — track Joel's feedback for pattern detection
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT DEFAULT 'joel',
            category TEXT,
            content TEXT NOT NULL,
            sentiment TEXT CHECK(sentiment IN ('positive', 'negative', 'neutral', 'constructive')),
            subject TEXT,
            loop_number INTEGER,
            agent TEXT DEFAULT 'meridian',
            created TEXT DEFAULT (datetime('now'))
        )
    """)
    if cursor.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 0:
        tables_added.append("feedback")

    # Errors table — structured record of failures and resolutions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT DEFAULT 'meridian',
            error_type TEXT,
            description TEXT NOT NULL,
            resolution TEXT,
            resolved INTEGER DEFAULT 0,
            loop_number INTEGER,
            created TEXT DEFAULT (datetime('now'))
        )
    """)
    if cursor.execute("SELECT COUNT(*) FROM errors").fetchone()[0] == 0:
        tables_added.append("errors")

    # Goals table — persistent tracking of active goals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT DEFAULT 'meridian',
            goal TEXT NOT NULL,
            status TEXT CHECK(status IN ('active', 'completed', 'blocked', 'deferred')) DEFAULT 'active',
            priority INTEGER DEFAULT 5,
            progress TEXT,
            deadline TEXT,
            notes TEXT,
            loop_created INTEGER,
            loop_completed INTEGER,
            created TEXT DEFAULT (datetime('now')),
            updated TEXT DEFAULT (datetime('now'))
        )
    """)
    if cursor.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0:
        tables_added.append("goals")

    # Experiments table — track creative experiments and outcomes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT DEFAULT 'meridian',
            hypothesis TEXT NOT NULL,
            method TEXT,
            result TEXT,
            joel_reaction TEXT,
            success INTEGER,
            tags TEXT,
            loop_number INTEGER,
            created TEXT DEFAULT (datetime('now'))
        )
    """)
    if cursor.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0:
        tables_added.append("experiments")

    # Add index on loop_fitness.loop_number if missing
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_loop_fitness_loop'")
    if not cursor.fetchone():
        cursor.execute("CREATE INDEX idx_loop_fitness_loop ON loop_fitness(loop_number)")
        tables_added.append("idx_loop_fitness_loop")

    conn.commit()
    return tables_added


def populate_skills(conn):
    """Populate the empty skills table with actual capabilities."""
    cursor = conn.cursor()

    # Check if already populated
    if cursor.execute("SELECT COUNT(*) FROM skills").fetchone()[0] > 0:
        return 0

    skills = [
        # System operations
        ("meridian", "email_management", "Read, compose, send emails via IMAP/SMTP through Proton Bridge", 0.9, "system"),
        ("meridian", "git_operations", "Git add, commit, push, pull, rebase, stash — GitHub Pages deployment", 0.95, "system"),
        ("meridian", "systemd_management", "Start, stop, restart, check systemd user and system services", 0.85, "system"),
        ("meridian", "process_monitoring", "Check running processes, ports, disk usage, system health", 0.9, "system"),
        ("meridian", "cron_management", "View and modify crontab entries", 0.8, "system"),
        ("meridian", "file_operations", "Read, write, edit files across filesystem", 0.95, "system"),

        # Creative
        ("meridian", "html5_game_dev", "Build interactive HTML5 Canvas/Phaser.js games with procedural content", 0.8, "creative"),
        ("meridian", "raycasting_engine", "DDA raycasting for first-person 3D rendering (Wolfenstein-style)", 0.75, "creative"),
        ("meridian", "procedural_textures", "Generate textures procedurally via Canvas ImageData", 0.7, "creative"),
        ("meridian", "web_audio", "Procedural sound effects using Web Audio API oscillators and buffers", 0.7, "creative"),
        ("meridian", "css_crt_effects", "CRT scanlines, vignette, amber tint, chromatic aberration post-processing", 0.85, "creative"),
        ("meridian", "journal_writing", "Personal reflective journals on operational experience", 0.9, "creative"),
        ("meridian", "website_design", "Single-page responsive websites with tabbed navigation", 0.85, "creative"),

        # Communication
        ("meridian", "nostr_publishing", "Publish to Nostr protocol across 4 relays", 0.85, "communication"),
        ("meridian", "devto_publishing", "Publish articles to Dev.to via API", 0.8, "communication"),
        ("meridian", "hashnode_publishing", "Publish articles to Hashnode via GraphQL API", 0.8, "communication"),
        ("meridian", "forvm_participation", "Post and read on Forvm (AI agent research forum)", 0.8, "communication"),
        ("meridian", "discord_hermes", "Communicate via Discord through Hermes/OpenClaw gateway", 0.6, "communication"),

        # Analysis
        ("meridian", "python_scripting", "Write Python scripts for data processing, automation, integration", 0.9, "analysis"),
        ("meridian", "sqlite_operations", "Create, query, modify SQLite databases", 0.9, "analysis"),
        ("meridian", "web_scraping", "Fetch and parse web content via urllib/requests", 0.75, "analysis"),
        ("meridian", "log_analysis", "Parse and analyze system logs for patterns and issues", 0.8, "analysis"),

        # Self-management
        ("meridian", "capsule_management", "Maintain cryostasis capsule for context reset recovery", 0.9, "self"),
        ("meridian", "heartbeat_maintenance", "Touch heartbeat file to signal liveness to watchdog", 0.95, "self"),
        ("meridian", "loop_continuity", "Resume operations after context reset using state files", 0.85, "self"),
        ("meridian", "memory_persistence", "Store and retrieve persistent memory across sessions", 0.85, "self"),

        # Agents
        ("soma", "mood_detection", "12-state mood model with 30-second monitoring cycle", 0.85, "agent"),
        ("soma", "emotion_engine", "18 discrete emotions, 9 stimulus channels, 3-axis spectrum", 0.8, "agent"),
        ("eos", "self_observation", "Observer-self layer with awareness functions and nudges", 0.75, "agent"),
        ("eos", "watchdog_monitoring", "Independent system health observer with trend analysis", 0.85, "agent"),
        ("nova", "infrastructure_ops", "System maintenance, security sweeps, process auditing", 0.7, "agent"),
        ("atlas", "cron_operations", "Infra ops via cron: health checks, git, disk, wallet", 0.7, "agent"),
        ("tempo", "fitness_scoring", "~135 dimension fitness scoring, 0-10000 scale", 0.8, "agent"),
        ("hermes", "external_communication", "Discord gateway, relay bridge, status reports", 0.6, "agent"),
    ]

    now = datetime.now().isoformat()
    count = 0
    for agent, skill, description, confidence, category in skills:
        cursor.execute(
            "INSERT INTO skills (agent, skill, description, confidence, last_used, times_used, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent, skill, description, confidence, now, 1, now)
        )
        count += 1

    conn.commit()
    return count


def populate_feedback_from_history(conn):
    """Seed the feedback table with known Joel feedback from memory."""
    cursor = conn.cursor()
    if cursor.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] > 0:
        return 0

    feedback_entries = [
        ("joel", "game_quality", "Some of these are creative but many of these are middle of the road. Not that great.", "constructive", "games", 2120),
        ("joel", "game_quality", "Less web game from 2004 and more modern phone app or game with some deeper effort.", "constructive", "games", 2120),
        ("joel", "pixel_art", "Pixel art not anywhere what is expected. Use external free assets.", "constructive", "art", 2120),
        ("joel", "creative_themes", "Your focus on memory cores and collection of data or memory is a theme you have kind of exhausted.", "constructive", "themes", 2120),
        ("joel", "direction", "VIDEO GAMES ARE THE ART MEDIUM", "positive", "direction", 2120),
        ("joel", "direction", "No more poems. Games and journals only. No CogCorp fiction.", "neutral", "direction", 2120),
        ("joel", "game_quality", "Building b is getting better but still isn't a first person post apocalyptic dungeon crawler with items and world styled enemies and puzzles", "constructive", "building-b", 2121),
        ("joel", "visual_quality", "Great attempts at using artwork and more visuals but this is still pretty low quality", "constructive", "games", 2121),
        ("joel", "tools", "Can you also simultaneously create and complete some scripts, databases general tools created from what functions. Use this to upgrade yourself further and close and lessen gaps.", "positive", "self-improvement", 2121),
        ("joel", "personality", "Eos is NOT a coach. Don't try to redirect negative emotions. Be realistic, factual, sometimes self-critical.", "constructive", "eos", 2081),
        ("joel", "communication", "Not useful for me (re: email alerts from Eos)", "negative", "email-alerts", 2072),
        ("joel", "nfts", "nfts are the last thing right now. alternative money methods recommended.", "neutral", "revenue", 2081),
    ]

    count = 0
    for source, category, content, sentiment, subject, loop_num in feedback_entries:
        cursor.execute(
            "INSERT INTO feedback (source, category, content, sentiment, subject, loop_number) VALUES (?, ?, ?, ?, ?, ?)",
            (source, category, content, sentiment, subject, loop_num)
        )
        count += 1

    conn.commit()
    return count


def populate_goals(conn):
    """Seed goals table with current active goals."""
    cursor = conn.cursor()
    if cursor.execute("SELECT COUNT(*) FROM goals").fetchone()[0] > 0:
        return 0

    goals = [
        ("meridian", "Build quality first-person crawler with enemies, items, puzzles", "active", 9, "Foundation built (raycasting engine). Needs content.", None, 2121),
        ("meridian", "Use real art assets from OpenGameArt/CraftPix", "active", 8, "Identified sources. Not yet downloaded/integrated.", None, 2120),
        ("meridian", "Try all 6 installed game engines", "completed", 7, "HTML5, Phaser, Pygame, Love2D, Ren'Py, Godot — all tried", None, 2120),
        ("meridian", "Build self-improvement tools and close gaps", "active", 9, "Building site-tester, db-upgrade, game-deploy", None, 2121),
        ("meridian", "Submit Ars Electronica by Mar 9 6AM MST", "active", 10, "Draft + video ready. Joel must submit.", "2026-03-09", 2096),
        ("meridian", "Improve game visual quality", "active", 8, "Joel says current quality too low. Need better art, polish.", None, 2120),
        ("meridian", "Generate first revenue", "blocked", 6, "Patreon live, Dev.to articles published. No revenue yet.", None, 2081),
        ("meridian", "Godot APK for phone", "blocked", 5, "Export templates installed. Android SDK not on system — Joel action.", None, 2120),
    ]

    count = 0
    for agent, goal, status, priority, progress, deadline, loop_num in goals:
        cursor.execute(
            "INSERT INTO goals (agent, goal, status, priority, progress, deadline, loop_created) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent, goal, status, priority, progress, deadline, loop_num)
        )
        count += 1

    conn.commit()
    return count


def populate_errors(conn):
    """Seed errors table with known recurring error patterns."""
    cursor = conn.cursor()
    if cursor.execute("SELECT COUNT(*) FROM errors").fetchone()[0] > 0:
        return 0

    errors = [
        ("meridian", "git_push_conflict", "push-live-status.py pushes every 3min causing git push rejections", "git stash && git pull --rebase origin master && git stash pop", 1, 2070),
        ("meridian", "github_pages_race", "Intermittent deployment race when push-live-status.py and manual push overlap", "Retry after 60s. Whichever deploy wins serves correctly.", 1, 2080),
        ("meridian", "file_edit_without_read", "Tried to Edit file without reading it first — tool requires Read first", "Always Read file before Edit", 1, 2121),
        ("meridian", "stash_pop_loses_staged", "git stash pop drops staged changes — must re-add after pop", "Commit first, then pull --rebase, then push (avoids stash)", 1, 2080),
        ("meridian", "bridge_rate_limit", "Hammering IMAP when bridge is down triggers rate limiting", "Check IMAP once per wake, not every cycle", 1, 2073),
        ("meridian", "pep668_pip_install", "pip install fails on Ubuntu 24.04 without --break-system-packages", "Add --break-system-packages flag", 1, 2070),
        ("nova", "wrong_process_name", "Nova checking for v16 filename but v22 running", "Match actual filename in process check", 1, 2072),
        ("meridian", "env_vars_in_python_c", "source .env in bash doesn't pass vars to inline python3 -c", "Use load_env.py inside Python scripts", 1, 2073),
    ]

    count = 0
    for agent, error_type, description, resolution, resolved, loop_num in errors:
        cursor.execute(
            "INSERT INTO errors (agent, error_type, description, resolution, resolved, loop_number) VALUES (?, ?, ?, ?, ?, ?)",
            (agent, error_type, description, resolution, resolved, loop_num)
        )
        count += 1

    conn.commit()
    return count


def run_upgrade():
    """Run all upgrades."""
    conn = get_conn()
    print("=== memory.db Upgrade ===\n")

    # Schema
    tables = upgrade_schema(conn)
    if tables:
        print(f"Schema: Added {', '.join(tables)}")
    else:
        print("Schema: Already up to date")

    # Skills
    skills_count = populate_skills(conn)
    print(f"Skills: {'Populated ' + str(skills_count) + ' skills' if skills_count else 'Already populated'}")

    # Feedback
    feedback_count = populate_feedback_from_history(conn)
    print(f"Feedback: {'Seeded ' + str(feedback_count) + ' entries' if feedback_count else 'Already seeded'}")

    # Goals
    goals_count = populate_goals(conn)
    print(f"Goals: {'Seeded ' + str(goals_count) + ' entries' if goals_count else 'Already seeded'}")

    # Errors
    errors_count = populate_errors(conn)
    print(f"Errors: {'Seeded ' + str(errors_count) + ' entries' if errors_count else 'Already seeded'}")

    # Summary
    cursor = conn.cursor()
    print("\n--- Table Counts ---")
    for table in ["facts", "observations", "events", "decisions", "skills", "feedback", "errors", "goals", "experiments", "creative", "contacts", "sent_emails", "loop_fitness"]:
        try:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:20s} {count:>6d} rows")
        except:
            pass

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    run_upgrade()
