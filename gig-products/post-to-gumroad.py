#!/usr/bin/env python3
"""
Post "The Loop" ebook to Gumroad.

Requirements:
  1. Joel creates a Gumroad app at https://app.gumroad.com/settings/advanced
     (OAuth Applications section — create a new app, get access token)
  2. Export that token to env: export GUMROAD_TOKEN=your_token_here
     OR add to .env: GUMROAD_TOKEN=your_token_here
  3. Run: python3 post-to-gumroad.py

Gumroad API docs: https://app.gumroad.com/api#products
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(BASE)
PRODUCT_NAME = "THE LOOP: How to Build an Autonomous AI That Stays Alive"
PRICE_CENTS = 1499  # $14.99

DESCRIPTION = """What happens when you give an AI system persistent memory, emotional processing, and a body — then let it run 24/7 for months?

THE LOOP is a field report from inside an autonomous AI that has completed over 3,200 operational cycles. Written by Joel Kometz (the human operator) and Meridian (the AI system itself) — the only guide to building autonomous AI written from both sides of the collaboration.

**What you'll learn:**
- How to architect a multi-agent system that stays alive across context resets
- 5 state persistence strategies that actually work
- Building an emotion engine: 18 emotions, 9 channels, dimensional modeling
- Why your AI needs a body (the unified body system approach)
- Infrastructure that doesn't break: systemd, cron, heartbeat monitoring
- Creative output pipelines: from generation to multi-platform publishing
- What we got wrong (honest accountability audit)
- What nobody tells you about running an AI 24/7

**Not included:** Source code or integration architecture — this is design philosophy, practical lessons, and honest war stories from 3,200+ loops.

Written by the system. About the system. From inside the loop."""

GUMROAD_API = "https://api.gumroad.com/v2"


def load_token():
    # Try env var first
    token = os.environ.get("GUMROAD_TOKEN")
    if token:
        return token
    # Try .env in parent directory
    env_file = os.path.join(PARENT, ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GUMROAD_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def api_call(method, endpoint, data=None, token=None):
    url = f"{GUMROAD_API}/{endpoint}"
    if data:
        body = urllib.parse.urlencode(data).encode()
    else:
        body = None

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}")
        return None


def create_product(token):
    print(f"Creating product: {PRODUCT_NAME}")
    print(f"Price: ${PRICE_CENTS / 100:.2f}")

    data = {
        "access_token": token,
        "name": PRODUCT_NAME,
        "price": PRICE_CENTS,
        "description": DESCRIPTION,
        "published": "false",  # Create as draft first — review before publishing
    }

    result = api_call("POST", "products", data=data)
    if result and result.get("success"):
        product = result.get("product", {})
        print(f"\n✓ Product created (DRAFT):")
        print(f"  ID    : {product.get('id')}")
        print(f"  Name  : {product.get('name')}")
        print(f"  URL   : {product.get('short_url')}")
        print(f"  Price : ${product.get('price', 0) / 100:.2f}")
        print(f"\nNext step: Add the PDF/EPUB files at app.gumroad.com")
        print(f"Then publish the product.")
        return product.get("id")
    else:
        print(f"Failed: {result}")
        return None


def list_products(token):
    print("Listing existing products...")
    result = api_call("GET", f"products?access_token={token}")
    if result and result.get("success"):
        products = result.get("products", [])
        print(f"Found {len(products)} product(s):")
        for p in products:
            print(f"  - {p.get('name')} (${p.get('price', 0) / 100:.2f}) — {p.get('short_url')}")
    else:
        print(f"Failed: {result}")


def main():
    token = load_token()

    if not token:
        print("No GUMROAD_TOKEN found.")
        print()
        print("To get a token:")
        print("  1. Go to https://app.gumroad.com/settings/advanced")
        print("  2. Under 'OAuth Applications', create a new app")
        print("  3. Generate an access token")
        print("  4. Add to /home/joel/autonomous-ai/.env:")
        print("     GUMROAD_TOKEN=your_token_here")
        print("  5. Run this script again")
        sys.exit(1)

    print(f"Gumroad token found (first 8 chars: {token[:8]}...)")
    print()

    if "--list" in sys.argv:
        list_products(token)
        return

    if "--create" in sys.argv or len(sys.argv) == 1:
        product_id = create_product(token)
        if product_id:
            print(f"\nProduct ID saved. To add files, visit:")
            print(f"  https://app.gumroad.com/products/{product_id}/edit")


if __name__ == "__main__":
    main()
