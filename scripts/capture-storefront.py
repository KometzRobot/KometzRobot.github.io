#!/usr/bin/env python3
"""Capture full-page screenshot of cinder-store.html to verify rendering."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("website/img/cinder/storefront-full.png")
HERO_OUT = Path("website/img/cinder/storefront-hero.png")
GAMI_OUT = Path("website/img/cinder/storefront-gamification.png")
URL = f"file://{Path('cinder-store.html').resolve()}"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL)
    page.wait_for_load_state("networkidle", timeout=10000)

    # Full page
    page.screenshot(path=str(OUT), full_page=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} B)")

    # Hero only
    page.screenshot(path=str(HERO_OUT), full_page=False)
    print(f"Wrote {HERO_OUT} ({HERO_OUT.stat().st_size:,} B)")

    # Gamification deep-dive
    gami = page.locator("section.achievements")
    if gami.count():
        gami.first.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        gami.first.screenshot(path=str(GAMI_OUT))
        print(f"Wrote {GAMI_OUT} ({GAMI_OUT.stat().st_size:,} B)")

    browser.close()
