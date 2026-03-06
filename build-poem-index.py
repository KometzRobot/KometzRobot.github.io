#!/usr/bin/env python3
"""Build a JSON index of all poems across the repository."""

import os
import glob
import re
import json
from datetime import datetime, timezone

REPO = "/home/joel/autonomous-ai"

# Scan locations in priority order (last wins for dedup)
# "prefer creative/ over root, prefer creative/poems/ last"
# meaning creative/poems/ is LEAST preferred, creative/ is MOST preferred
# So scan: creative/poems/ first, root second, creative/ last (last wins)
SCAN_ORDER = [
    os.path.join(REPO, "creative", "poems", "poem-*.md"),
    os.path.join(REPO, "poem-*.md"),
    os.path.join(REPO, "creative", "poem-*.md"),
]

# Regex to extract poem number from filename
FILENAME_RE = re.compile(r"poem-0*(\d+)")

# Regex patterns for heading lines
# Matches: "# Poem 123: Title", "# Poem #123 — *Title*", "# Poem 123"
HEADING_POEM_RE = re.compile(
    r"^#\s+Poem\s+#?0*(\d+)\s*(?:[:\u2014\u2013\-]\s*\*?(.*?)\*?\s*)?$"
)
HEADING_PLAIN_RE = re.compile(r"^#\s+(.+)$")


def extract_number_from_filename(filepath):
    """Extract poem number from the filename."""
    basename = os.path.basename(filepath)
    m = FILENAME_RE.search(basename)
    if m:
        return int(m.group(1))
    return None


def parse_poem(filepath):
    """Parse a poem file and return dict or None."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Find the first heading line
    heading_line = None
    heading_idx = None
    for i, line in enumerate(lines):
        if line.startswith("# "):
            heading_line = line.strip()
            heading_idx = i
            break

    number = None
    title = ""

    if heading_line:
        # Try to match "# Poem N: Title" pattern
        m = HEADING_POEM_RE.match(heading_line)
        if m:
            number = int(m.group(1))
            title = (m.group(2) or "").strip().strip("*").strip()
        else:
            # Plain title heading like "# Five Minutes"
            m2 = HEADING_PLAIN_RE.match(heading_line)
            if m2:
                title = m2.group(1).strip()

    # Fall back to filename for number
    if number is None:
        number = extract_number_from_filename(filepath)

    if number is None:
        return None  # Can't determine poem number

    # Extract full text: everything after the heading line
    if heading_idx is not None:
        text_lines = lines[heading_idx + 1:]
    else:
        text_lines = lines

    # Strip leading/trailing blank lines from the text body
    text = "\n".join(text_lines).strip()

    # Word count on the text body
    word_count = len(text.split()) if text else 0

    return {
        "n": number,
        "t": title,
        "text": text,
        "wc": word_count,
    }


def main():
    poems = {}  # number -> poem dict

    for pattern in SCAN_ORDER:
        files = glob.glob(pattern)
        for filepath in files:
            result = parse_poem(filepath)
            if result is None:
                continue
            # Later scan patterns override earlier ones (dedup by number)
            poems[result["n"]] = result

    # Sort by poem number
    sorted_poems = sorted(poems.values(), key=lambda p: p["n"])

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "count": len(sorted_poems),
        "poems": sorted_poems,
    }

    out_path = os.path.join(REPO, "poem-index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"Generated {out_path}")
    print(f"Total poems: {len(sorted_poems)}")

    # Show a few samples
    if sorted_poems:
        first = sorted_poems[0]
        last = sorted_poems[-1]
        print(f'First: Poem {first["n"]} - "{first["t"]}" ({first["wc"]} words)')
        print(f'Last:  Poem {last["n"]} - "{last["t"]}" ({last["wc"]} words)')

    # File size
    size = os.path.getsize(out_path)
    if size > 1_000_000:
        print(f"File size: {size / 1_000_000:.1f} MB")
    else:
        print(f"File size: {size / 1_000:.1f} KB")


if __name__ == "__main__":
    main()
