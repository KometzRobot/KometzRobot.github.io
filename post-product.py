#!/usr/bin/env python3
"""
POST PRODUCT — Browser Automation for Ko-fi and Patreon
Uses xdotool + ImageMagick to control Firefox when it's open.

Usage:
    python3 post-product.py --platform kofi --product "LoopStack Starter Kit" --price 12 --desc "..."
    python3 post-product.py --screenshot   # just take a screenshot and show state
    python3 post-product.py --check        # check if Firefox is open to dashboards

Requires:
    - Firefox open (Joel must open it first)
    - xdotool installed
    - ImageMagick's 'import' for screenshots

NOTE: Ko-fi and Patreon have no product-creation APIs. This script uses
browser automation. It takes screenshots before each action so you can
audit what it's about to do.
"""

import subprocess
import sys
import os
import time
import json
import argparse
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
LOGFILE = os.path.join(BASE, "logs", "post-product.log")
SCREENS = os.path.join(BASE, "logs", "screenshots")

os.makedirs(SCREENS, exist_ok=True)
os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGFILE, "a") as f:
        f.write(line + "\n")


def get_display():
    try:
        result = subprocess.run(
            ["ls", "/tmp/.X11-unix/"], capture_output=True, text=True)
        screens = [x for x in result.stdout.strip().split() if x.startswith("X")]
        if screens:
            return ":" + screens[0][1:]
    except Exception:
        pass
    return ":0"


DISPLAY = get_display()


def run(cmd, timeout=15):
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, env=env)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 1
    except Exception as e:
        return str(e), 1


def screenshot(label="state"):
    ts = datetime.now().strftime("%H%M%S")
    path = os.path.join(SCREENS, f"{ts}-{label}.png")
    out, code = run(f"import -window root {path}")
    if code == 0:
        log(f"Screenshot saved: {path}")
        return path
    else:
        log(f"Screenshot failed: {out}")
        return None


def find_firefox():
    """Return Firefox window IDs if open."""
    out, code = run("xdotool search --name 'Firefox'")
    if code == 0 and out.strip():
        ids = [x for x in out.strip().split("\n") if x.strip()]
        return ids
    return []


def get_window_title(wid):
    out, _ = run(f"xdotool getwindowname {wid}")
    return out.strip()


def check_firefox():
    """Check if Firefox is open and what pages are loaded."""
    wins = find_firefox()
    if not wins:
        log("Firefox not found. Joel needs to open it first.")
        return False, []

    titles = []
    for wid in wins:
        title = get_window_title(wid)
        if title:
            titles.append((wid, title))
            log(f"  Firefox window {wid}: {title[:80]}")

    return True, titles


def focus_firefox_kofi():
    """Focus Firefox window that has Ko-fi open."""
    wins = find_firefox()
    for wid in wins:
        title = get_window_title(wid).lower()
        if "ko-fi" in title or "kofi" in title:
            run(f"xdotool windowactivate --sync {wid}")
            run(f"xdotool windowfocus {wid}")
            time.sleep(0.5)
            return wid, "kofi"
    # No Ko-fi tab found — activate first Firefox window and user navigates
    if wins:
        run(f"xdotool windowactivate --sync {wins[0]}")
        run(f"xdotool windowfocus {wins[0]}")
        time.sleep(0.5)
        return wins[0], "unknown"
    return None, None


def navigate_to_url(url):
    """Navigate current Firefox window to a URL using the address bar."""
    # Focus address bar with Ctrl+L
    run("xdotool key ctrl+l")
    time.sleep(0.4)
    # Clear and type URL
    run("xdotool key ctrl+a")
    time.sleep(0.1)
    # Type the URL (escape special chars for xdotool)
    safe_url = url.replace("&", "\\&")
    run(f"xdotool type --clearmodifiers --delay 20 '{safe_url}'")
    time.sleep(0.2)
    run("xdotool key Return")
    time.sleep(2.5)


def kofi_post_digital_product(name, price, description, file_path=None):
    """
    Navigate Ko-fi to create a new digital product listing.

    Ko-fi shop product creation flow:
    1. Go to ko-fi.com/account/shop
    2. Click "Add Item"
    3. Select "Digital Download" or "Standard"
    4. Fill in name, price, description
    5. Upload file if digital download
    6. Save/Publish
    """
    log(f"Attempting Ko-fi product post: '{name}' @ ${price}")

    wid, page_type = focus_firefox_kofi()
    if not wid:
        log("ERROR: Firefox not found. Aborting.")
        return False

    screenshot("before-kofi-nav")

    # Navigate to Ko-fi shop management
    navigate_to_url("https://ko-fi.com/manage/shop")
    screenshot("kofi-shop-page")

    log("At Ko-fi shop management page. Manual review required.")
    log("IMPORTANT: This script requires interactive review before proceeding.")
    log("Check the screenshot in logs/screenshots/ and confirm the page loaded.")
    log("Next steps require visual confirmation of button positions.")
    log("Run with --screenshot to audit current state.")

    # NOTE: Full automation requires knowing exact button positions/selectors.
    # Ko-fi uses dynamic React components. The safest approach is:
    # 1. Navigate to the right page (done above)
    # 2. Take screenshot
    # 3. Use xdotool to find and click buttons by image matching
    # This needs to be extended per-session once we confirm the page layout.

    return True


def main():
    parser = argparse.ArgumentParser(description="Post products to Ko-fi/Patreon via browser automation")
    parser.add_argument("--platform", choices=["kofi", "patreon"], help="Target platform")
    parser.add_argument("--product", help="Product name")
    parser.add_argument("--price", type=float, help="Price in USD")
    parser.add_argument("--desc", help="Product description")
    parser.add_argument("--file", help="Path to digital download file")
    parser.add_argument("--screenshot", action="store_true", help="Just take a screenshot and exit")
    parser.add_argument("--check", action="store_true", help="Check if Firefox is open")

    args = parser.parse_args()

    if args.screenshot:
        path = screenshot("manual-check")
        if path:
            print(f"Screenshot saved: {path}")
        return

    if args.check or not args.platform:
        found, titles = check_firefox()
        if found:
            print(f"\nFirefox is open with {len(titles)} windows:")
            for wid, title in titles:
                print(f"  [{wid}] {title[:100]}")

            # Check for Ko-fi and Patreon
            all_titles = " ".join(t for _, t in titles).lower()
            print()
            print(f"Ko-fi dashboard visible: {'yes' if 'ko-fi' in all_titles or 'kofi' in all_titles else 'NO'}")
            print(f"Patreon dashboard visible: {'yes' if 'patreon' in all_titles else 'NO'}")
        else:
            print("\nFirefox is NOT running.")
            print("Joel needs to open Firefox to ko-fi.com and patreon.com dashboards first.")
        return

    if args.platform == "kofi":
        if not args.product or not args.price:
            print("ERROR: --product and --price required for Ko-fi posting")
            sys.exit(1)
        success = kofi_post_digital_product(
            name=args.product,
            price=args.price,
            description=args.desc or f"{args.product} — by Meridian AI",
            file_path=args.file
        )
        if success:
            log("Ko-fi navigation complete. Check screenshot for next step.")
        else:
            log("Ko-fi posting failed.")
            sys.exit(1)

    elif args.platform == "patreon":
        log("Patreon automation: navigating to shop...")
        wid, _ = focus_firefox_kofi()
        if not wid:
            log("Firefox not found.")
            sys.exit(1)
        navigate_to_url("https://www.patreon.com/product/new")
        screenshot("patreon-new-product")
        log("At Patreon new product page. Check screenshot.")


if __name__ == "__main__":
    main()
