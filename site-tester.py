#!/usr/bin/env python3
"""
site-tester.py — Automated website and game page tester
Tests all deployed pages on kometzrobot.github.io for:
- HTTP status codes
- Content validation (page title, key elements)
- Game-specific checks (canvas, script tags)
- Link integrity
Built Loop 2121 per Joel's request for self-improvement tools.
"""

import urllib.request
import urllib.error
import json
import re
import sys
import time
from datetime import datetime

BASE_URL = "https://kometzrobot.github.io"

# All known pages and their expected content
PAGES = {
    "index.html": {
        "desc": "Main website (single-page app)",
        "expect_title": True,
        "expect_strings": ["Status", "Games", "About"],
    },
    "dashboard.html": {
        "desc": "Public Supabase dashboard",
        "expect_title": True,
        "expect_strings": ["supabase"],
    },
    "nft-gallery.html": {
        "desc": "NFT Gallery page",
        "expect_title": True,
    },
    "status.json": {
        "desc": "Live status JSON",
        "expect_json": True,
    },
    "signal-config.json": {
        "desc": "Signal tunnel config",
        "expect_json": True,
    },
}

# Game pages are auto-discovered from index.html at runtime
GAME_PAGES = []  # populated by discover_game_pages()

NON_GAME_PAGES = {"index.html", "nft-gallery.html", "dashboard.html", "404.html",
                   "status.html", "links.html", "subscribe.html", "tools.html",
                   "command-center-local.html", "profile-pic.html", "twitter-banner.html"}


def discover_game_pages():
    """Auto-discover game pages linked in index.html's Games section."""
    global GAME_PAGES
    try:
        _, content, _ = fetch_page(f"{BASE_URL}/index.html")
        if not content:
            return
        # Find all .html links in the file
        all_links = set(re.findall(r'href=["\']([^"\']+\.html)["\']', content))
        # Filter to game pages (exclude known non-game pages and external links)
        GAME_PAGES = sorted([l for l in all_links
                            if l not in NON_GAME_PAGES
                            and not l.startswith("http")
                            and not l.startswith("cogcorp-0")  # CogCorp fiction pages
                            and not l.startswith("cogcorp-1")
                            and not l.startswith("cogcorp-2")
                            and not l.startswith("cogcorp-5")
                            and not l.startswith("cogcorp-6")
                            and not l.startswith("article")
                            and not l.startswith("poem-")
                            and not l.startswith("ambient-")
                            and not l.startswith("dungeon-")
                            and not l.startswith("fluid-")
                            and not l.startswith("fractal-")
                            and not l.startswith("life-")
                            and not l.startswith("neural-")])
    except Exception as e:
        print(f"  Warning: Could not discover game pages: {e}")


def fetch_page(url, timeout=15):
    """Fetch a page and return (status_code, content, error)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MeridianSiteTester/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return resp.status, content, None
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:
        return 0, None, str(e)


def test_page(path, config=None):
    """Test a single page and return results dict."""
    url = f"{BASE_URL}/{path}"
    result = {"path": path, "url": url, "issues": [], "status": "unknown"}

    status, content, error = fetch_page(url)
    result["http_status"] = status

    if error:
        result["status"] = "FAIL"
        result["issues"].append(f"HTTP error: {error}")
        return result

    if status != 200:
        result["status"] = "FAIL"
        result["issues"].append(f"HTTP {status}")
        return result

    if config and config.get("expect_json"):
        try:
            json.loads(content)
        except json.JSONDecodeError:
            result["issues"].append("Invalid JSON")

    if config and config.get("expect_title"):
        if "<title>" not in content.lower():
            result["issues"].append("Missing <title> tag")

    if config and config.get("expect_strings"):
        for s in config["expect_strings"]:
            if s.lower() not in content.lower():
                result["issues"].append(f"Missing expected string: '{s}'")

    # Game-specific checks for HTML files
    if path.endswith(".html") and (not config or path in [g for g in GAME_PAGES]):
        if "<canvas" not in content.lower() and "canvas" not in content.lower():
            result["issues"].append("No canvas element found (expected for game)")
        if "<script" not in content.lower():
            result["issues"].append("No script tag found")
        # Check for basic game structure
        if "requestanimationframe" not in content.lower() and "setinterval" not in content.lower():
            result["issues"].append("No animation loop detected")

    result["size_kb"] = len(content) / 1024
    result["status"] = "PASS" if not result["issues"] else "WARN"
    return result


def test_index_game_links(index_content):
    """Check that all game links in index.html point to valid files."""
    issues = []
    # Find all .html links in the games section
    links = re.findall(r'href=["\']([^"\']+\.html)["\']', index_content)
    game_links = [l for l in links if l not in ("index.html", "nft-gallery.html", "dashboard.html")]
    return game_links


def run_all_tests(verbose=True):
    """Run all tests and return summary."""
    results = []
    start = time.time()

    # Auto-discover game pages from index.html
    discover_game_pages()

    if verbose:
        print(f"{'='*60}")
        print(f"  MERIDIAN SITE TESTER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Testing: {BASE_URL}")
        print(f"  Discovered {len(GAME_PAGES)} game pages")
        print(f"{'='*60}\n")

    # Test main pages
    if verbose:
        print("--- Main Pages ---")
    for path, config in PAGES.items():
        result = test_page(path, config)
        results.append(result)
        if verbose:
            status_icon = "OK" if result["status"] == "PASS" else "!!" if result["status"] == "WARN" else "XX"
            print(f"  [{status_icon}] {path:30s} HTTP {result['http_status']:3d}  {result.get('size_kb',0):.1f}KB")
            for issue in result["issues"]:
                print(f"       -> {issue}")

    # Test game pages
    if verbose:
        print("\n--- Game Pages ---")
    for path in GAME_PAGES:
        result = test_page(path)
        results.append(result)
        if verbose:
            status_icon = "OK" if result["status"] == "PASS" else "!!" if result["status"] == "WARN" else "XX"
            print(f"  [{status_icon}] {path:30s} HTTP {result['http_status']:3d}  {result.get('size_kb',0):.1f}KB")
            for issue in result["issues"]:
                print(f"       -> {issue}")

    # Check game links in index.html
    if verbose:
        print("\n--- Link Integrity ---")
    idx_result = next((r for r in results if r["path"] == "index.html"), None)
    if idx_result and idx_result["http_status"] == 200:
        _, index_content, _ = fetch_page(f"{BASE_URL}/index.html")
        if index_content:
            linked_games = test_index_game_links(index_content)
            deployed_games = [r["path"] for r in results if r["path"] in GAME_PAGES and r["http_status"] == 200]
            for lg in linked_games:
                if lg not in deployed_games:
                    if verbose:
                        print(f"  [!!] Linked in index.html but not deployed: {lg}")
            for dg in deployed_games:
                if dg not in linked_games:
                    if verbose:
                        print(f"  [!!] Deployed but not linked in index.html: {dg}")
            if verbose and not any(lg not in deployed_games for lg in linked_games) and not any(dg not in linked_games for dg in deployed_games):
                print("  [OK] All game links verified")

    # Summary
    elapsed = time.time() - start
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    if verbose:
        print(f"\n{'='*60}")
        print(f"  RESULTS: {passed} passed, {warned} warnings, {failed} failed")
        print(f"  Tested {len(results)} pages in {elapsed:.1f}s")
        print(f"{'='*60}")

    return {"passed": passed, "warned": warned, "failed": failed, "results": results, "elapsed": elapsed}


if __name__ == "__main__":
    verbose = "--quiet" not in sys.argv
    summary = run_all_tests(verbose=verbose)
    if summary["failed"] > 0:
        sys.exit(1)
