#!/usr/bin/env python3
"""
Post to Patreon — Automates creating a Patreon post using Playwright.

Uses Firefox cookies for authentication (same method as setup-patreon-tier.py).

Usage:
    python3 post-to-patreon.py patreon-posts/2026-04-01-daily/
    python3 post-to-patreon.py --title "Title" --body "Body text" --image header.png

The post directory should contain:
  - post.md (text content)
  - header.png (main image, optional)
  - manifest.json (metadata)
"""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

FIREFOX_COOKIES = os.path.expanduser(
    "~/snap/firefox/common/.mozilla/firefox/lq3h0209.default-release/cookies.sqlite"
)
PATREON_URL = "https://www.patreon.com/Meridian_AI"


def extract_patreon_cookies():
    """Extract Patreon cookies from Firefox's cookie database."""
    if not os.path.exists(FIREFOX_COOKIES):
        print(f"Firefox cookie DB not found: {FIREFOX_COOKIES}")
        return []
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(FIREFOX_COOKIES, tmp)
    conn = sqlite3.connect(tmp)
    cursor = conn.execute(
        "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite "
        "FROM moz_cookies WHERE host LIKE '%patreon%'"
    )
    cookies = []
    for row in cursor:
        name, value, host, path, expiry, secure, httponly, samesite = row
        cookies.append({
            "name": name,
            "value": value,
            "domain": host,
            "path": path,
            "expires": expiry,
            "secure": bool(secure),
            "httpOnly": bool(httponly),
            "sameSite": ["None", "Lax", "Strict"][samesite] if samesite < 3 else "None"
        })
    conn.close()
    os.unlink(tmp)
    print(f"Extracted {len(cookies)} Patreon cookies")
    return cookies


def post_from_directory(post_dir):
    """Create a Patreon post from a post directory."""
    from playwright.sync_api import sync_playwright

    # Read post content
    post_md = os.path.join(post_dir, "post.md")
    manifest_path = os.path.join(post_dir, "manifest.json")

    if not os.path.exists(post_md):
        print(f"No post.md in {post_dir}")
        return False

    with open(post_md) as f:
        content = f.read()

    # Extract title (first # line) and body
    lines = content.strip().split('\n')
    title = lines[0].lstrip('# ').strip() if lines[0].startswith('#') else "Meridian Update"
    body = '\n'.join(lines[1:]).strip()

    # Find images
    header = os.path.join(post_dir, "header.png")
    images = []
    if os.path.exists(header):
        images.append(header)
    # Add supplementary images
    for name in ["stats.png", "daily-card.png", "agents.png"]:
        path = os.path.join(post_dir, name)
        if os.path.exists(path):
            images.append(path)

    print(f"Title: {title}")
    print(f"Body: {len(body)} chars")
    print(f"Images: {len(images)}")

    cookies = extract_patreon_cookies()
    if not cookies:
        print("No cookies — cannot authenticate")
        return False

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)

        page = context.new_page()
        print("Navigating to Patreon...")
        page.goto("https://www.patreon.com/Meridian_AI/posts", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Click "Create" or "New post" button
        try:
            create_btn = page.locator('a[href*="posts/new"], button:has-text("Create"), [data-tag="create-button"]').first
            if create_btn.is_visible():
                create_btn.click()
                time.sleep(3)
                print("Clicked Create button")
            else:
                # Try navigating directly to post creation
                page.goto("https://www.patreon.com/Meridian_AI/posts/new", wait_until="networkidle", timeout=30000)
                time.sleep(3)
                print("Navigated to new post page")
        except Exception as e:
            print(f"Trying direct URL for new post... ({e})")
            page.goto("https://www.patreon.com/Meridian_AI/posts/new", wait_until="networkidle", timeout=30000)
            time.sleep(3)

        # Type the title
        try:
            title_field = page.locator('[data-tag="post-title"], input[placeholder*="title" i], [contenteditable][data-placeholder*="title" i]').first
            title_field.click()
            title_field.fill(title)
            print(f"Filled title: {title}")
            time.sleep(1)
        except Exception as e:
            print(f"Could not find title field: {e}")

        # Type the body
        try:
            body_field = page.locator('[data-tag="post-content-editable"], [contenteditable]:not([data-placeholder*="title" i]), div[role="textbox"]').first
            body_field.click()
            # Type line by line for contenteditable
            for line in body.split('\n'):
                body_field.type(line)
                body_field.press('Enter')
            print(f"Filled body: {len(body)} chars")
            time.sleep(1)
        except Exception as e:
            print(f"Could not find body field: {e}")

        # Upload images if possible
        for img_path in images[:3]:  # Max 3
            try:
                file_input = page.locator('input[type="file"]').first
                if file_input:
                    file_input.set_input_files(img_path)
                    print(f"Uploaded: {os.path.basename(img_path)}")
                    time.sleep(2)
            except Exception as e:
                print(f"Could not upload {os.path.basename(img_path)}: {e}")

        # Take screenshot for verification instead of auto-publishing
        screenshot_path = os.path.join(post_dir, "preview-screenshot.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"\nScreenshot saved: {screenshot_path}")
        print("POST NOT AUTO-PUBLISHED — review the screenshot and publish manually if it looks right.")
        print("Or add --publish flag to auto-publish (not recommended without review).")

        browser.close()

    # Log the attempt
    log = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "body_length": len(body),
        "images": [os.path.basename(p) for p in images],
        "status": "drafted_needs_review"
    }
    log_path = os.path.join(post_dir, "post-log.json")
    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    post_dir = sys.argv[1]
    if os.path.isdir(post_dir):
        post_from_directory(post_dir)
    else:
        print(f"Not a directory: {post_dir}")
        print(__doc__)
