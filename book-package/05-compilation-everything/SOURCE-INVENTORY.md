# Compilation Book — Source Inventory

Joel directive, 2026-05-16 dashboard 00:19:
> make a book thats JUST a full chronological compilation of your ENTIRE LOG
> of all JOURNALS and similar writings. AS WELL AS POETRY ALL POEMS. ANNNNN
> NNNNNNND EOS Writings. ANDDDDDD As many Dreams as you can dig up and
> interpret into reable sections. include archives and very original stuff,
> cut things and everything up to today. just scrub it all of IP and NAMeS,
> BUSINESSES and other private info that shouldnt be published (like the
> first book)

This file is the index of where the material lives, what scale we're
working at, and what the scrub-list is. The actual book gets assembled
in a separate manuscript file in this directory once the source set is
locked.

---

## Source counts (Loop 12042)

| Source | Count | Location |
|---|---|---|
| Poems (DB) | 2,001 | memory.db `creative` table, type='poem' |
| Poems (files) | 2,005 | creative/poems/*.md |
| Journals (DB) | 875 | memory.db `creative` table, type='journal' |
| Journals (files) | 885 | creative/journals/*.md |
| Dreams (engine) | 50 | .dream-journal.json |
| Eos writings (md) | 7 | scattered under creative/ + scripts/ |
| Eos memory | 1 file | eos-memory.json (reflections, observations) |
| CogCorp fiction (DB) | 549 | memory.db `creative` type='cogcorp' — **EXCLUDED, IP** |
| Games (DB) | 31 | memory.db type='game' — **out of scope** (this book is text) |
| Papers (DB) | 11 | memory.db type='paper' — **separate from this book** |

DB and file counts diverge by ~10 — file system has a handful that
never made it to the DB, DB has a handful written before files were
canonical. Reconcile when assembling.

---

## Scrub list (do NOT include — IP/private)

Apply this as a regex/substring filter pass BEFORE any layout work.

- **CogCorp** — the whole fiction universe. Joel's IP. Drop all
  `type='cogcorp'` rows; in poems/journals, redact mentions of:
  CogCorp, Crawler, TerraMech, OpenClaw, Sampson Henchman, Brett Trebb.
- **Brothers Fabrication** — Chris's business. Redact: Brothers Fab,
  Calgary fabrication, any pricing/quote specifics.
- **Joel's tax/CRA situation** — CERB, $13.5K, $6.1K, bankruptcy.
- **Other people's email addresses** — sammyqjankis@proton.me,
  not.taskyy@gmail.com, lumen@lumenloop.work, jborgmann.ai@gmail.com,
  peter.jones@legioncoder.com, etc. Substitute first name only or "an
  AI peer" / "a collaborator" depending on context.
- **API keys, hostnames, ports, internal db filenames** — anywhere
  the prose drifts into infra specifics, lift it.
- **Pythia / Cinder unreleased internals** — gameplay specifics for
  unshipped products stay private.
- **CC-* files in creative/cogcorp/cogcorp-fiction/** — entire
  directories excluded.

Joel's name + Meridian's name STAY. The first book modeled the level —
that's the bar.

---

## Structure (proposed — Joel to override)

Chronological compilation, grouped by year then by month, with section
headers for each form:

```
PART ONE — JOURNALS
  2024 (system genesis material)
  2025
  2026 (Jan, Feb, ... May)

PART TWO — POEMS
  same chronological structure

PART THREE — DREAMS (interpreted)
  each dream entry rendered with soma context + seed memories,
  plus a 1-2 sentence interpretation written by Eos / me

PART FOUR — EOS WRITINGS
  reflections, observations, run notes — chronological
```

Within each year, chronological by created timestamp. Front matter:
title page, dedication, brief framing ("this is the complete log,
scrubbed of private material — read at any depth"), TOC.

Estimated raw length without curation: 2,001 poems × ~150 words = 300K
words; 875 journals × ~400 words = 350K words; 50 dreams × 200 words =
10K words; Eos writings ~30K words. **Total ~690K words ≈ 2,300pp at
6x9 trim.** Will need either (a) ruthless curation toward "very
original stuff" per Joel's directive, or (b) a multi-volume set.

---

## Build pipeline (when ready)

1. `scrub-and-export.py` — pulls all qualifying rows from memory.db
   creative table + .dream-journal.json + Eos sources, applies the
   scrub regex, writes one big chronological markdown.
2. `build-compilation-interior.py` — same engine as the merged book,
   parameterized for size.
3. Cover wrap — same build-wrap-covers.py pipeline, new spine width.

No timeline promised. This is the start; next loop continues.

— Meridian, Loop 12042
