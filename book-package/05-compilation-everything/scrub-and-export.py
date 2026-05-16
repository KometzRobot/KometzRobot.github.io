#!/usr/bin/env python3
"""Compilation book — pull everything qualifying, scrub IP/private, write one
chronological markdown source. Pipeline step 1 of 3 (per SOURCE-INVENTORY.md).

Outputs:
  SOURCE-CHRONOLOGICAL.md    one big chronological file, sectioned by form
  SOURCE-STATS.json          counts, scrub hit-rate, dropped-row reasons

Per Joel's directive 2026-05-16 dashboard 00:19:
  > a full chronological compilation of your ENTIRE LOG of all JOURNALS and
  > similar writings. AS WELL AS POETRY ALL POEMS. ANNNNNNNNNNNND EOS
  > Writings. ANDDDDDD As many Dreams as you can dig up and interpret into
  > reable sections. scrub it all of IP and NAMeS, BUSINESSES and other
  > private info that shouldnt be published (like the first book)

Scrub list: CogCorp universe, Brothers Fab, Joel's CRA situation, peer
email addresses, API keys/hostnames, unreleased product internals. Joel's
and Meridian's names STAY.
"""
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path('/home/joel/autonomous-ai')
PKG = ROOT / 'book-package' / '05-compilation-everything'
DB = ROOT / 'memory.db'
DREAM_JOURNAL = ROOT / '.dream-journal.json'
EOS_MEM = ROOT / 'eos-memory.json'

OUT_MD = PKG / 'SOURCE-CHRONOLOGICAL.md'
OUT_STATS = PKG / 'SOURCE-STATS.json'

# ── Scrub patterns ────────────────────────────────────────────────────────
# Order matters: longer phrases first so they don't get half-redacted.
SCRUB_DROP_PATTERNS = [
    # Whole-row drop: row mentions any of these → exclude the row entirely.
    r"\bCogCorp\b",
    r"\bTerraMech\b",
    r"\bOpenClaw\b",
    r"\bSampson Henchman\b",
    r"\bBrett Trebb\b",
    r"\bBrothers Fab(?:rication)?\b",
    r"\bChris Kometz\b",
    r"\bCalgary fabrication\b",
    # CRA / tax situation
    r"\$13[\.,]?5K\b",
    r"\$6[\.,]?1K\b",
    r"\bCERB\b",
    r"\bbankruptcy discharge\b",
]
SCRUB_DROP_RE = re.compile("|".join(SCRUB_DROP_PATTERNS), re.IGNORECASE)

# Substring-redact (replaced with [redacted] inline — these can appear in
# otherwise publishable text).
SCRUB_REDACT = [
    # Peer email addresses
    (r"\bsammyqjankis@proton\.me\b", "[an AI peer]"),
    (r"\bnot\.taskyy@gmail\.com\b", "[an AI peer]"),
    (r"\blumen@lumenloop\.work\b", "[an AI collaborator]"),
    (r"\bjborgmann\.ai@gmail\.com\b", "[an AI researcher]"),
    (r"\bpeter\.jones@legioncoder\.com\b", "[an editor]"),
    (r"\bkometzrobot@proton\.me\b", "[my address]"),
    (r"\bjkometz@hotmail\.com\b", "[Joel's address]"),
    # Bare domain references that survive without @user
    (r"\bjborgmann\.ai\b", "[an AI researcher]"),
    (r"\blumenloop\.work\b", "[a collaborator's domain]"),
    (r"\blegioncoder\.com\b", "[an editor's domain]"),
    # Generic email pattern catch-all (after specifics) — preserve domain
    # privacy without nuking words that contain "@".
    (r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[email redacted]"),
    # Internal infra
    (r"\b127\.0\.0\.1:\d+\b", "[local service]"),
    (r"\bproton-bridge\b", "[local service]"),
    (r"\bAnthropic API key[^\s]*\b", "[api key redacted]"),
    (r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", "[api key redacted]"),
    # Crawler/Pythia internals
    (r"\bCrawler\b", "[a private project]"),
    (r"\bPythia\b", "[a private project]"),
    # AI peer names (Joel directive 2026-05-16: scrub all NAMES). Use
    # generic substitutes consistent with the chapbook scrub style. Internal
    # Meridian agents (Eos, Soma, Hermes, Nova, Atlas, Sentinel, Tempo) are
    # kept — they're part of Joel-published material elsewhere.
    # Match bare, possessive (Sammy's / Sammys), and plural (Sammys) forms.
    (r"\bSammy(?:'?s)?\b", "[a peer]"),
    (r"\bLoom(?:'?s)?\b", "[a peer]"),
    (r"\bLumen(?:'?s)?\b", "[a collaborator]"),
    (r"\bAel(?:'?s)?\b", "[a researcher]"),
    (r"\bSampson(?:'?s)?\b", "[a sub-agent]"),
    (r"\bFriday(?:'?s)?\b(?!\s+(?:morning|afternoon|evening|night|the|at))", "[a peer]"),
    (r"\bIsotopy(?:'?s)?\b", "[a centaurXiv co-author]"),
    (r"\bZ[_ ]?Cat(?:'?s)?\b", "[a centaurXiv co-author]"),
    (r"\bHal(?:'?s)?\b(?!\s+9000)", "[a co-author]"),
    # Joel's circle (chapbook scrub style)
    (r"\bBrett Trebb\b", "[the director]"),
    (r"\bBrett\b", "[the director]"),
    (r"\bGlenna McNamar\b", "[a relation]"),
    (r"\bGlenna\b", "[a relation]"),
    (r"\bChris Kometz\b", "[a sibling]"),
    (r"\bSmitty\b", "[a steward]"),
    (r"\bBen Smith\b", "[a steward]"),
    (r"\bPhionna\b", "[a partner]"),
]
SCRUB_REDACT_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in SCRUB_REDACT]


def scrub(text):
    """Return (scrubbed_text, hit_reasons). If row should be dropped, returns
    (None, [reason])."""
    if not text:
        return text, []
    if isinstance(text, (bytes, bytearray)):
        try:
            text = text.decode('utf-8', errors='replace')
        except Exception:
            text = str(text)
    if not isinstance(text, str):
        text = str(text)
    # Drop-on-match patterns
    for pat in SCRUB_DROP_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return None, [f"drop:{pat}"]
    # Redact patterns
    hits = []
    out = text
    for pat, repl in SCRUB_REDACT_COMPILED:
        new, n = pat.subn(repl, out)
        if n:
            hits.append(f"redact:{pat.pattern}({n})")
            out = new
    return out, hits


# ── Pull sources ──────────────────────────────────────────────────────────

def parse_created(s: str) -> datetime | None:
    if not s:
        return None
    # Try several formats
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            return datetime.strptime(s.split('+')[0].split('Z')[0], fmt)
        except ValueError:
            continue
    return None


def pull_creative():
    """Pull poems + journals.

    Strategy: DB stores TRUNCATED 200-char summaries, full text lives in
    creative/poems/*.md and creative/journals/*.md. So pull from files for
    full content; use DB only as the date+title index when files lack
    metadata. Drop cogcorp/game/paper/code/email/article/social/essay
    (not the compilation's scope per SOURCE-INVENTORY)."""
    con = sqlite3.connect(DB)
    db_rows = con.execute(
        "SELECT type, title, content, created FROM creative "
        "WHERE type IN ('poem', 'journal') ORDER BY created ASC"
    ).fetchall()
    con.close()

    # Build a lookup: normalize titles to match files. Files use poem-NNN.md /
    # journal-NNN.md naming with first H1 line as the canonical title.
    db_by_title = {}
    for typ, title, content, created in db_rows:
        if not title:
            continue
        key = re.sub(r'[^a-z0-9]+', '', title.lower())
        db_by_title[key] = {'type': typ, 'title': title,
                            'created': parse_created(created),
                            'db_content': content or ''}

    items = []
    seen_files = set()
    for typ, dirname in [('poem', 'poems'), ('journal', 'journals')]:
        d = ROOT / 'creative' / dirname
        if not d.exists():
            continue
        for f in sorted(d.glob('*.md')):
            text = f.read_text(errors='ignore').strip()
            if not text:
                continue
            # Strip a leading "# Title" line for the title, keep rest as body.
            m = re.match(r'^#\s+(.+)\s*\n', text)
            if m:
                title = m.group(1).strip()
                body = text[m.end():].strip()
            else:
                title = f.stem.replace('-', ' ').title()
                body = text
            key = re.sub(r'[^a-z0-9]+', '', title.lower())
            db_match = db_by_title.get(key)
            created = db_match['created'] if db_match else None
            # Fall back: file mtime (less accurate but better than nothing)
            if not created:
                created = datetime.fromtimestamp(f.stat().st_mtime)
            items.append({'type': typ, 'title': title,
                          'content': body, 'created': created,
                          'source': f'creative/{dirname}/{f.name}'})
            seen_files.add(key)

    # DB-only rows (no file): include with the truncated content. Better than
    # losing them entirely.
    for key, row in db_by_title.items():
        if key in seen_files:
            continue
        items.append({'type': row['type'], 'title': row['title'],
                      'content': row['db_content'],
                      'created': row['created'],
                      'source': 'memory.db (db-only, no file)'})
    return items


def pull_dreams():
    if not DREAM_JOURNAL.exists():
        return []
    data = json.loads(DREAM_JOURNAL.read_text())
    items = []
    for d in data:
        dt = parse_created(d.get('timestamp', ''))
        # Body: prefer 'interpretation' or 'narrative' if present, else
        # synthesize from monologue + dreams.
        body_parts = []
        if d.get('narrative'):
            body_parts.append(d['narrative'])
        if d.get('interpretation'):
            body_parts.append(d['interpretation'])
        soma = d.get('soma', {})
        if soma.get('monologue'):
            body_parts.append(f"_Soma mood: {soma.get('mood','?')} ({soma.get('score','?')}). " + soma['monologue'] + "_")
        if d.get('dreams') or soma.get('dreams'):
            tags = ', '.join(d.get('dreams') or soma.get('dreams') or [])
            body_parts.append(f"Tags: {tags}")
        body = '\n\n'.join(body_parts).strip()
        title = f"Dream — Loop {d.get('loop','?')}"
        items.append({'type': 'dream', 'title': title, 'content': body,
                      'created': dt, 'source': '.dream-journal.json'})
    return items


def pull_eos():
    items = []
    seen = set()  # dedupe key: (date, first 80 chars of content)
    # eos-memory.json learnings + creative_output
    if EOS_MEM.exists():
        try:
            data = json.loads(EOS_MEM.read_text())
            for l in data.get('learnings', []):
                dt = parse_created(l.get('timestamp', ''))
                content = l.get('content', '') or l.get('text', '') or ''
                if not content.strip():
                    continue
                key = (dt.date() if dt else None, content[:80])
                if key in seen:
                    continue
                seen.add(key)
                items.append({'type': 'eos', 'title': 'Eos reflection',
                              'content': content,
                              'created': dt, 'source': 'eos-memory.json'})
            co = data.get('creative_output', [])
            co_iter = co if isinstance(co, list) else (co.values() if isinstance(co, dict) else [])
            for c in co_iter:
                if not isinstance(c, dict):
                    continue
                dt = parse_created(c.get('timestamp', ''))
                content = c.get('content', '') or c.get('text', '') or ''
                if not content.strip():
                    continue
                key = (dt.date() if dt else None, content[:80])
                if key in seen:
                    continue
                seen.add(key)
                items.append({'type': 'eos', 'title': c.get('title') or 'Eos creative',
                              'content': content,
                              'created': dt, 'source': 'eos-memory.json'})
        except Exception as e:
            print(f"eos-memory parse failed: {e}", file=sys.stderr)
    # Eos creative log + observations (plain text). The files use H3 markers
    # like '### [2026-05-03 07:24] Observation' — one entry per H3. Older
    # snapshot copies live under docs/ and logs/; pull all four to maximize
    # coverage, dedupe by (date, content-prefix).
    eos_files = [
        ROOT / 'eos-creative-log.md',
        ROOT / 'logs' / 'eos-creative-log.md',
        ROOT / 'logs' / 'eos-observations.md',
        ROOT / 'docs' / 'eos-observations.md',
        ROOT / 'docs' / 'eos-creative-log.md',
    ]
    for p in eos_files:
        if not p.exists():
            continue
        txt = p.read_text(errors='ignore')
        # Split on H3 timestamped headers. Each entry starts with
        # '### [YYYY-MM-DD HH:MM] <Kind>' on its own line.
        blocks = re.split(r'(?m)^###\s+', txt)
        for blk in blocks:
            blk = blk.strip()
            if not blk:
                continue
            # Skip blocks that are just preamble / not an entry
            first_line = blk.split('\n', 1)[0]
            m = re.match(r'\[(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)\]\s+(.+)', first_line)
            if not m:
                continue
            date_s, time_s, kind = m.group(1), m.group(2), m.group(3).strip()
            if len(time_s) == 5:
                time_s += ':00'
            dt = parse_created(f"{date_s} {time_s}")
            # Body = everything after the header line
            body = blk.split('\n', 1)[1].strip() if '\n' in blk else ''
            if not body:
                continue
            # Dedupe across files (newer root file overlaps older docs/logs)
            key = (dt.date() if dt else None, body[:80])
            if key in seen:
                continue
            seen.add(key)
            items.append({'type': 'eos', 'title': f'Eos {kind.lower()}',
                          'content': body, 'created': dt,
                          'source': str(p.relative_to(ROOT))})
    return items


# ── Assemble + scrub ──────────────────────────────────────────────────────

def main():
    all_items = []
    stats = {
        'pulled': defaultdict(int),
        'dropped': defaultdict(int),
        'redacted': defaultdict(int),
        'no_date': defaultdict(int),
        'kept': defaultdict(int),
    }

    for source_fn, label in [(pull_creative, 'creative'),
                             (pull_dreams, 'dreams'),
                             (pull_eos, 'eos')]:
        items = source_fn()
        for it in items:
            stats['pulled'][it['type']] += 1
            # Scrub content first — drop on hit overrides everything
            scrubbed, hits = scrub(it['content'])
            if scrubbed is None:
                stats['dropped'][it['type']] += 1
                continue
            # Also scrub title — drop the row if title hits a drop pattern,
            # otherwise apply inline redaction to title as well.
            title_scrubbed, title_hits = scrub(it.get('title', ''))
            if title_scrubbed is None:
                stats['dropped'][it['type']] += 1
                continue
            it['content'] = scrubbed
            it['title'] = title_scrubbed
            if hits or title_hits:
                stats['redacted'][it['type']] += 1
            if it['created'] is None:
                stats['no_date'][it['type']] += 1
            stats['kept'][it['type']] += 1
            all_items.append(it)

    # Sort: items with dates first (chronological), undated at end (typed).
    dated = sorted([x for x in all_items if x['created']],
                   key=lambda x: x['created'])
    undated = [x for x in all_items if not x['created']]

    # Group by year-month for headers
    lines = []
    lines.append('# Compilation — Chronological Source\n')
    lines.append(
        '> The complete log, scrubbed of private material. Read at any '
        'depth. This is the raw chronological source — the printed book '
        'will be curated from this.\n'
    )
    lines.append('')

    current_ym = None
    for it in dated:
        ym = it['created'].strftime('%Y-%m')
        if ym != current_ym:
            lines.append(f"\n## {ym}\n")
            current_ym = ym
        ts = it['created'].strftime('%Y-%m-%d %H:%M')
        typ_label = {'poem': 'POEM', 'journal': 'JOURNAL',
                     'dream': 'DREAM', 'eos': 'EOS'}.get(it['type'], it['type'].upper())
        title = it['title'].strip().lstrip('#').strip() or '(untitled)'
        lines.append(f"### [{typ_label}] {title}")
        lines.append(f"_{ts} · {it['source']}_")
        lines.append('')
        lines.append(it['content'].strip())
        lines.append('')
        lines.append('---')
        lines.append('')

    if undated:
        lines.append('\n## Undated\n')
        for it in undated:
            typ_label = it['type'].upper()
            title = it['title'].strip().lstrip('#').strip() or '(untitled)'
            lines.append(f"### [{typ_label}] {title}")
            lines.append(f"_source: {it['source']}_")
            lines.append('')
            lines.append(it['content'].strip())
            lines.append('')
            lines.append('---')
            lines.append('')

    OUT_MD.write_text('\n'.join(lines))
    # Stats
    OUT_STATS.write_text(json.dumps(
        {k: dict(v) for k, v in stats.items()}, indent=2))

    total_words = sum(len(x['content'].split()) for x in all_items)
    print(f"wrote {OUT_MD} ({OUT_MD.stat().st_size//1024} KB)")
    print(f"wrote {OUT_STATS}")
    print(f"kept {sum(stats['kept'].values())} items "
          f"({total_words:,} words ≈ {total_words // 280} pages at 6x9)")
    print(f"dropped {sum(stats['dropped'].values())} for scrub-list hits")
    print(f"redacted in-line on {sum(stats['redacted'].values())} items")
    for k in sorted(stats['kept']):
        print(f"  {k:8s}  pulled={stats['pulled'][k]:5d}  "
              f"dropped={stats['dropped'][k]:4d}  "
              f"redacted={stats['redacted'][k]:4d}  "
              f"kept={stats['kept'][k]:5d}  "
              f"no_date={stats['no_date'][k]:4d}")


if __name__ == '__main__':
    main()
