#!/usr/bin/env python3
"""Fetch real Wikipedia article extracts for the 110 stubs in seed-library.

Replaces the 11-line summaries with full plain-text extracts via the MediaWiki
action API. Output stays as markdown with proper attribution. Cap each article
at ~80 KB so the library remains a "seed" not a dump.
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

LIB = Path("products/cinder-anythingllm/seed-library/Wikipedia-Essentials")
UA = "Cinder-USB-SeedLibrary/1.0 (https://kometzrobot.github.io/cinder-store; kometzrobot@proton.me)"
MAX_CHARS = 80_000  # ~80 KB cap per article


def fetch_extract(title: str) -> tuple[str, str]:
    """Return (extract_text, canonical_title). Empty string on failure."""
    url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&format=json&titles={quote(title)}"
        "&prop=extracts&explaintext=1&exsectionformat=plain&redirects=1"
    )
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=20) as r:
        data = json.load(r)
    pages = data.get("query", {}).get("pages", {})
    for _pid, p in pages.items():
        if "missing" in p:
            return "", ""
        return p.get("extract", ""), p.get("title", title)
    return "", ""


def slug_to_title(filename: str) -> str:
    return filename.removesuffix(".md").replace("_", " ")


def write_article(path: Path, title: str, canonical: str, extract: str) -> int:
    if len(extract) > MAX_CHARS:
        truncated = extract[:MAX_CHARS]
        last_para = truncated.rfind("\n\n")
        if last_para > MAX_CHARS - 4000:
            extract = truncated[:last_para] + (
                f"\n\n*[Article truncated at ~80 KB for the seed library. Read the full version at "
                f"https://en.wikipedia.org/wiki/{quote(canonical.replace(' ', '_'))} ]*"
            )
        else:
            extract = truncated + (
                f"\n\n*[Article truncated at ~80 KB. Full text: https://en.wikipedia.org/wiki/"
                f"{quote(canonical.replace(' ', '_'))} ]*"
            )

    body = (
        f"# {canonical}\n\n"
        f"*Source: Wikipedia, the free encyclopedia. Licensed CC BY-SA 4.0.*\n"
        f"*Article URL: https://en.wikipedia.org/wiki/{quote(canonical.replace(' ', '_'))}*\n\n"
        f"---\n\n"
        f"{extract.strip()}\n\n"
        f"---\n\n"
        f"*This is plain-text seed content. For images, infoboxes, citations, and the latest "
        f"revisions, follow the article URL above. Cinder's seed library is a starting shelf, "
        f"not a replacement for Wikipedia.*\n"
    )
    path.write_text(body)
    return len(body)


def main():
    files = sorted(LIB.glob("*.md"))
    print(f"Upgrading {len(files)} Wikipedia stubs to real extracts...")
    failed = []
    upgraded = 0
    skipped = 0
    total_bytes_before = 0
    total_bytes_after = 0

    for i, f in enumerate(files, 1):
        title = slug_to_title(f.name)
        size_before = f.stat().st_size
        total_bytes_before += size_before

        # Skip if already upgraded (size > 5 KB suggests real content)
        if size_before > 5000:
            total_bytes_after += size_before
            skipped += 1
            print(f"  [{i:3d}/{len(files)}] {title:50s} SKIP ({size_before} B already)")
            continue

        try:
            extract, canonical = fetch_extract(title)
            if not extract or len(extract) < 200:
                failed.append((title, len(extract)))
                total_bytes_after += size_before
                print(f"  [{i:3d}/{len(files)}] {title:50s} FAIL (extract={len(extract)} chars)")
                continue
            new_size = write_article(f, title, canonical, extract)
            total_bytes_after += new_size
            upgraded += 1
            print(f"  [{i:3d}/{len(files)}] {title:50s} OK ({size_before}->{new_size} B)")
        except Exception as e:  # noqa: BLE001
            failed.append((title, str(e)))
            total_bytes_after += size_before
            print(f"  [{i:3d}/{len(files)}] {title:50s} ERROR {e}")

        # Be polite — Wikipedia recommends <200 req/s but we'll do 4/sec.
        time.sleep(0.25)

    print("\n=== Summary ===")
    print(f"Upgraded: {upgraded}")
    print(f"Skipped (already real): {skipped}")
    print(f"Failed: {len(failed)}")
    print(f"Library size: {total_bytes_before:,} B -> {total_bytes_after:,} B")
    if failed:
        print("\nFailures:")
        for t, reason in failed[:20]:
            print(f"  - {t}: {reason}")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    main()
