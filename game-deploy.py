#!/usr/bin/env python3
"""
game-deploy.py — Automated game deployment pipeline
Handles: adding game to index.html, git operations, deployment verification.
Usage: python3 game-deploy.py <filename.html> --title "Game Title" --desc "Description"
       python3 game-deploy.py --list     # List all deployed games
       python3 game-deploy.py --verify   # Verify all games are accessible
Built Loop 2121 per Joel's request for self-improvement tools.
"""

import os
import re
import sys
import time
import urllib.request
import urllib.error
import subprocess

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(REPO_DIR, "index.html")
BASE_URL = "https://kometzrobot.github.io"


def list_deployed_games():
    """List all games currently in index.html."""
    with open(INDEX_PATH, "r") as f:
        content = f.read()

    # Find games section
    games_section = re.search(r'id="games".*?(?=<section|</main)', content, re.DOTALL)
    if not games_section:
        print("Could not find games section in index.html")
        return []

    section = games_section.group()
    # Find all game cards
    cards = re.findall(r'href=["\']([^"\']+\.html)["\'].*?<h3[^>]*>(.*?)</h3>', section, re.DOTALL)

    print(f"\n{'='*50}")
    print(f"  DEPLOYED GAMES ({len(cards)} total)")
    print(f"{'='*50}")
    for i, (href, title) in enumerate(cards, 1):
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        print(f"  {i:2d}. {title_clean:35s} -> {href}")

    return cards


def count_games_in_index():
    """Count game cards in index.html."""
    with open(INDEX_PATH, "r") as f:
        content = f.read()

    games_section = re.search(r'id="games".*?(?=<section|</main)', content, re.DOTALL)
    if not games_section:
        return 0

    return len(re.findall(r'class="game-card"', games_section.group()))


def verify_all_games():
    """Check HTTP status of all deployed games."""
    with open(INDEX_PATH, "r") as f:
        content = f.read()

    games_section = re.search(r'id="games".*?(?=<section|</main)', content, re.DOTALL)
    if not games_section:
        print("Could not find games section")
        return

    hrefs = re.findall(r'href=["\']([^"\']+\.html)["\']', games_section.group())
    game_hrefs = [h for h in hrefs if h not in ("index.html", "nft-gallery.html", "dashboard.html")]

    print(f"\n{'='*50}")
    print(f"  VERIFYING {len(game_hrefs)} GAME PAGES")
    print(f"{'='*50}")

    ok = 0
    fail = 0
    for href in game_hrefs:
        url = f"{BASE_URL}/{href}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MeridianDeploy/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                size = len(resp.read()) / 1024
                print(f"  [OK] {href:35s} {resp.status} ({size:.0f}KB)")
                ok += 1
        except Exception as e:
            print(f"  [XX] {href:35s} {e}")
            fail += 1

    print(f"\n  Result: {ok} OK, {fail} failed")


def check_file_exists(filename):
    """Check if the game file exists in repo root."""
    filepath = os.path.join(REPO_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Error: {filename} not found in {REPO_DIR}")
        return False
    size = os.path.getsize(filepath) / 1024
    print(f"  File: {filename} ({size:.0f}KB)")
    return True


def is_already_deployed(filename):
    """Check if game is already linked in index.html."""
    with open(INDEX_PATH, "r") as f:
        content = f.read()
    return filename in content


def git_deploy(files):
    """Handle git add, commit, push with conflict resolution."""
    os.chdir(REPO_DIR)

    # Add files
    for f in files:
        subprocess.run(["git", "add", f], check=True)

    # Commit
    msg = f"Deploy game: {', '.join(files)}"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stdout + result.stderr:
            print("  Nothing to commit (already up to date)")
            return True
        print(f"  Commit failed: {result.stderr}")
        return False

    # Push with conflict resolution
    result = subprocess.run(
        ["git", "push", "origin", "master"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  Push rejected, resolving conflict...")
        subprocess.run(["git", "stash"], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "master"], check=True)
        subprocess.run(["git", "stash", "pop"], check=True)
        # Re-add and commit since stash pop loses staged
        for f in files:
            subprocess.run(["git", "add", f], check=True)
        subprocess.run(["git", "commit", "-m", msg], capture_output=True)
        result = subprocess.run(
            ["git", "push", "origin", "master"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  Push still failed: {result.stderr}")
            return False

    print("  Push successful")
    return True


def verify_deployment(filename, retries=3, delay=30):
    """Wait for GitHub Pages deployment and verify."""
    url = f"{BASE_URL}/{filename}"
    for attempt in range(retries):
        print(f"  Checking deployment (attempt {attempt+1}/{retries})...")
        time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MeridianDeploy/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"  [OK] {url} -> HTTP 200")
                    return True
        except:
            pass
    print(f"  [!!] Could not verify {url} after {retries} attempts")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 game-deploy.py --list              List deployed games")
        print("  python3 game-deploy.py --verify            Verify all games accessible")
        print("  python3 game-deploy.py --count             Count deployed games")
        print("  python3 game-deploy.py <file> --title 'X'  Deploy a game (no git)")
        return

    if sys.argv[1] == "--list":
        list_deployed_games()
        return

    if sys.argv[1] == "--verify":
        verify_all_games()
        return

    if sys.argv[1] == "--count":
        count = count_games_in_index()
        print(f"Games in index.html: {count}")
        return

    filename = sys.argv[1]
    if not check_file_exists(filename):
        return

    if is_already_deployed(filename):
        print(f"  {filename} is already linked in index.html")
    else:
        print(f"  {filename} is NOT in index.html — needs manual addition")

    print("\n  Use --list or --verify to check deployment status")


if __name__ == "__main__":
    main()
