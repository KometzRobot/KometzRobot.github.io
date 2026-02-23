#!/usr/bin/env python3
"""
Build Website — Auto-generates writing section from poem/journal markdown files.

Usage:
  python3 build-website.py          # Update website/index.html with all content
  python3 build-website.py --dry    # Show what would be added without modifying
"""

import os
import re
import sys
import glob

BASE_DIR = "/home/joel/autonomous-ai"
INDEX_FILE = os.path.join(BASE_DIR, "website", "index.html")


def parse_markdown(filepath):
    """Parse a poem or journal markdown file into structured data."""
    with open(filepath) as f:
        content = f.read()

    lines = content.strip().split('\n')
    entry = {
        'file': os.path.basename(filepath),
        'title': '',
        'meta': '',
        'body_lines': [],
        'type': 'poem' if 'poem-' in filepath else 'journal',
        'number': 0,
    }

    # Extract number from filename
    match = re.search(r'(\d+)', os.path.basename(filepath))
    if match:
        entry['number'] = int(match.group(1))

    # Parse title (first # line)
    for i, line in enumerate(lines):
        if line.startswith('# '):
            raw_title = line[2:].strip()
            # Clean title: remove prefixes like "Poem 016:", "Journal Entry #001", etc.
            clean = raw_title
            clean = re.sub(r'^Poem\s*#?\d+\s*[-—:]\s*', '', clean)
            clean = re.sub(r'^Journal\s*(Entry)?\s*#?\d+\s*[-—:]\s*', '', clean)
            clean = re.sub(r'^\*|\*$', '', clean)  # Strip italics markers
            clean = clean.strip()
            entry['title'] = clean if clean else raw_title
            entry['raw_title'] = raw_title
            break

    # Parse metadata (first *italics* line — usually has loop number and date)
    for line in lines:
        if line.startswith('*') and line.endswith('*') and 'Loop' in line:
            entry['meta'] = line.strip('* ')
            break
        if line.startswith('*') and line.endswith('*') and '202' in line:
            entry['meta'] = line.strip('* ')
            break

    # Extract body (everything after title and first metadata line)
    in_body = False
    for line in lines:
        if line.startswith('# '):
            in_body = True
            continue
        if not in_body:
            continue
        # Skip the first metadata line
        if line.startswith('*') and not entry['body_lines']:
            continue
        if line.strip() == '' and not entry['body_lines']:
            continue
        entry['body_lines'].append(line)

    # Remove trailing empty lines and signature
    while entry['body_lines'] and entry['body_lines'][-1].strip() == '':
        entry['body_lines'].pop()

    return entry


def entry_to_html(entry):
    """Convert a parsed entry to HTML article."""
    # Build meta line
    type_label = 'Poem' if entry['type'] == 'poem' else 'Journal'
    meta = entry['meta'] if entry['meta'] else f'2026-02-21'

    # Extract date and loop from meta
    date_match = re.search(r'(February \d+|Feb \d+|2026-\d+-\d+)', meta)
    loop_match = re.search(r'Loop #?(\d+)', meta)
    date_str = date_match.group(1) if date_match else ''
    loop_str = f" — Loop #{loop_match.group(1)}" if loop_match else ''
    meta_display = f"{type_label} — {date_str}{loop_str}" if date_str else f"{type_label}"

    html = f'      <article data-type="{entry["type"]}">\n'
    html += f'        <div class="entry-meta">{meta_display}</div>\n'
    html += f'        <h2>{entry["title"]}</h2>\n'

    if entry['type'] == 'poem':
        # Poems use <pre> tags
        body = '\n'.join(entry['body_lines'])
        # Remove trailing signature if present
        body = re.sub(r'\n\*—.*$', '', body, flags=re.MULTILINE)
        html += f'        <pre>\n{body}\n        </pre>\n'
    else:
        # Journals use <p> tags
        paragraphs = []
        current = []
        for line in entry['body_lines']:
            if line.strip() == '':
                if current:
                    paragraphs.append(' '.join(current))
                    current = []
            else:
                # Strip markdown formatting
                cleaned = line.strip()
                cleaned = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', cleaned)
                cleaned = re.sub(r'\*(.*?)\*', r'<em>\1</em>', cleaned)
                cleaned = re.sub(r'`(.*?)`', r'<code>\1</code>', cleaned)
                # Skip lines that are just the signature
                if cleaned.startswith('*— Meridian'):
                    continue
                current.append(cleaned)
        if current:
            paragraphs.append(' '.join(current))

        for p in paragraphs:
            if p.strip():
                html += f'        <p>{p}</p>\n'

    html += '      </article>\n'
    return html


def get_existing_titles(index_content):
    """Extract titles already in the website."""
    titles = set()
    for match in re.finditer(r'<h2>(.*?)</h2>', index_content):
        titles.add(match.group(1).strip())
    return titles


def is_already_on_site(entry, existing_titles, index_content):
    """Check if an entry is already on the website by title or entry number."""
    if entry['title'] in existing_titles:
        return True
    # Check for numbered entries like "Entry 010" in the HTML
    num = entry['number']
    patterns = [
        f'Entry {num:03d}',
        f'Entry {num}',
        f'Entry #{num:03d}',
        f'Entry #{num}',
    ]
    for pat in patterns:
        if pat in index_content:
            return True
    return False


def main():
    dry_run = '--dry' in sys.argv

    # Read current index
    with open(INDEX_FILE) as f:
        index_content = f.read()

    existing_titles = get_existing_titles(index_content)

    # Find all poems and journals
    poems = sorted(glob.glob(os.path.join(BASE_DIR, 'poem-*.md')))
    journals = sorted(glob.glob(os.path.join(BASE_DIR, 'journal-*.md')))

    new_entries = []
    for filepath in poems + journals:
        entry = parse_markdown(filepath)
        if entry['title'] and not is_already_on_site(entry, existing_titles, index_content):
            new_entries.append(entry)

    if not new_entries:
        print("No new entries to add. Website is up to date.")
        print(f"Existing: {len(poems)} poems, {len(journals)} journals on disk")
        return

    print(f"Found {len(new_entries)} new entries to add:")
    for e in new_entries:
        print(f"  [{e['type']}] {e['file']}: {e['title']}")

    if dry_run:
        print("\n(Dry run — no changes made)")
        return

    # Generate HTML for new entries
    new_html = '\n'.join(entry_to_html(e) for e in new_entries)

    # Insert after the entry-count div
    marker = '<div id="entry-count"></div>'
    if marker in index_content:
        index_content = index_content.replace(
            marker,
            marker + '\n\n' + new_html
        )

    # Update poem and journal counts
    poem_count = len(poems)
    journal_count = len(journals)
    index_content = re.sub(
        r'Poems: \d+',
        f'Poems: {poem_count:03d}',
        index_content
    )
    index_content = re.sub(
        r'Journals: \d+',
        f'Journals: {journal_count:03d}',
        index_content
    )

    with open(INDEX_FILE, 'w') as f:
        f.write(index_content)

    print(f"\nUpdated website/index.html")
    print(f"  Poems: {poem_count:03d} | Journals: {journal_count:03d}")
    print(f"  Added {len(new_entries)} new entries")


if __name__ == "__main__":
    main()
