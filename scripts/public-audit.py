#!/usr/bin/env python3
"""
public-audit.py — Enumerate every path served publicly on meridian-loop.com.

Reason this exists (Loop 10863 incident): I made a sweeping claim that "no
brofab pitch or demo page existed on the site" without grepping hub-v2.py's
route table. /brofab is in fact a no-auth route serving docs/brothers-fab/.
Joel called this out as "more hot air than compute." Before saying what is
or isn't public, run this.

Parses hub-v2.py for routes that return BEFORE the `if not self._authed()`
gate. For each filesystem-backed route, lists the actual files served.

Usage: python3 scripts/public-audit.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(ROOT, "scripts", "hub-v2.py")


def read_hub_public_section():
    """Return the lines of hub-v2.py up to (but not including) the auth gate
    inside do_GET. That's the public-no-auth region."""
    with open(HUB) as f:
        src = f.read()
    # Find do_GET
    m = re.search(r"def do_GET\(self\):", src)
    if not m:
        sys.exit("could not find do_GET in hub-v2.py")
    after = src[m.end():]
    # Cut at the auth check
    gate = re.search(r"# Auth check for everything else", after)
    if not gate:
        sys.exit("could not find auth gate marker in hub-v2.py")
    return after[:gate.start()]


def parse_public_routes(text):
    """Pull out each `if path.path == "X":` or `.startswith("X"):` in the
    public region. Returns list of (kind, pattern, line_no_in_hub)."""
    routes = []
    for i, line in enumerate(text.splitlines(), 1):
        # Equal-match: if path.path == "/foo":
        m = re.search(r'path\.path\s*==\s*"([^"]+)"', line)
        if m:
            routes.append(("exact", m.group(1), i))
            continue
        # Prefix-match: if path.path.startswith("/foo/"):
        m = re.search(r'path\.path\.startswith\("([^"]+)"\)', line)
        if m:
            routes.append(("prefix", m.group(1), i))
    return routes


def describe_route(kind, pat, hub_text):
    """For prefix routes, try to find the filesystem ROOT it maps to so we
    can list what's actually being served. Heuristic: look for an os.path.join
    near the route handler."""
    # Find handler block in hub source
    idx = hub_text.find(f'startswith("{pat}")' if kind == "prefix" else f'== "{pat}"')
    if idx == -1:
        return None
    block = hub_text[idx:idx + 2000]
    m = re.search(r'os\.path\.join\([^)]*"([a-zA-Z0-9_/.-]+)"\s*,\s*"([a-zA-Z0-9_/.-]+)"', block)
    if m:
        # Most handlers do os.path.join(<parent-of-scripts>, "docs", "brothers-fab")
        # Reconstruct the absolute path
        parts = re.findall(r'"([a-zA-Z0-9_/.-]+)"', block.split("\n")[1] if "\n" in block else block)
        return parts
    # Fallback: pull all string args near the line
    m2 = re.search(r'(?:DIR|ROOT)\s*=\s*os\.path\.join\(([^)]+)\)', block)
    if m2:
        return [s.strip().strip('"') for s in m2.group(1).split(",") if '"' in s]
    return None


def list_files(rel_dir, depth=2):
    """List up to N files under rel_dir relative to repo root."""
    full = os.path.join(ROOT, rel_dir)
    if not os.path.isdir(full):
        return [f"(no such directory: {rel_dir})"]
    out = []
    for root, dirs, files in os.walk(full):
        # Limit depth
        rel = os.path.relpath(root, full)
        if rel != "." and rel.count(os.sep) >= depth:
            dirs[:] = []
            continue
        for fn in sorted(files):
            rel_path = os.path.relpath(os.path.join(root, fn), full)
            out.append(rel_path)
            if len(out) > 30:
                out.append(f"... ({sum(len(fs) for _, _, fs in os.walk(full)) - 30} more)")
                return out
    return out or ["(empty)"]


def main():
    text = read_hub_public_section()
    routes = parse_public_routes(text)

    print("=" * 70)
    print("PUBLIC ROUTES on meridian-loop.com (no-auth region of hub-v2.py)")
    print("=" * 70)
    print(f"Parsed from: {HUB}")
    print(f"Public region: {len(text.splitlines())} lines, {len(routes)} routes")
    print()

    # Known fs-backed routes (hand-mapped — heuristic parsing is fragile)
    FS_BACKED = {
        "/brofab": ("docs/brothers-fab", "Brothers Fabrication pitch demo"),
        "/brofab/": ("docs/brothers-fab", "Brothers Fabrication pitch demo"),
        "/download/": ("downloads", "User-facing downloads"),
        "/cinder-img/": ("products/cinder-anythingllm", ".img files only"),
    }

    INLINE = {
        "/login": "Login page (inline HTML)",
        "/": "Login page when unauthed; main app when authed",
        "/api/public-status": "Public JSON status snapshot",
        "/api/public-creative": "Creative stats (public-safe subset)",
        "/favicon.ico": "Inline SVG favicon",
    }

    for kind, pat, lineno in routes:
        head = f"[{kind:6s}] {pat:30s}"
        if pat in FS_BACKED:
            rel, note = FS_BACKED[pat]
            print(f"{head}  -> {rel}/  ({note})")
            for f in list_files(rel):
                print(f"             {f}")
        elif pat in INLINE:
            print(f"{head}  -> {INLINE[pat]}")
        else:
            print(f"{head}  -> (handler not classified, check hub-v2.py:{lineno})")
        print()

    print("=" * 70)
    print("Reminder: anything OUTSIDE the routes above requires auth via /login.")
    print("Before claiming 'X is/isn't public', re-run this script.")
    print("=" * 70)


if __name__ == "__main__":
    main()
