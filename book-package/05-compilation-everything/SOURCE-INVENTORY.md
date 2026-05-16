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

**Actual size after Loop 12082 full-file pull (2026-05-16):**

| Form | Kept | Dropped | Redacted |
|---|---|---|---|
| Poems | 1,902 | 103 | 12 |
| Journals | 653 | 278 | 23 |
| Dreams | 50 | 0 | 0 |
| Eos | 2 | 0 | 1 |
| **Total kept** | **2,607** | **381** | **36** |

**~620,000 words ≈ 2,200pp at 6×9 trim.** That's War-and-Peace + 10%.

Distribution by month — MEASURED page counts after Loop 12085 builds:

| Month | Words | Built pages | Status |
|---|---|---|---|
| 2026-02 | 61,496 | **268** | `compilation-vol1-feb.pdf` ✓ |
| 2026-03 | 337,821 | **1,584** | `compilation-vol2-mar-FULL.pdf` — EXCEEDS KDP CAP |
| 2026-04 | 124,483 | ~590 (est) | not yet built |
| 2026-05 | 126,983 | ~600 (est) | not yet built |

Page-density measured: 1 page ≈ 230 words at this layout (11pt /
1.42 leading, justified, 6×9 trim).

KDP paperback max is 828 pp (white) / 776 pp (cream). March alone is
nearly double the cap. **Open decision for Joel** — three paths:

  A. **Single eBook (Kindle/EPUB):** no page cap. One file, complete.
     Cheapest, fastest, no cover-wrap work needed. Print-on-demand
     not possible for >828pp at 6×9.
  B. **Multi-volume paperback set (estimated 5 volumes):** Vol I
     Feb (268pp ✓), Vol II Mar-A (~530), Vol III Mar-B (~530), Vol
     IV Mar-C+Apr (~700), Vol V May (~600). Each gets its own
     wrap. ~5x the cover work, ~5x the proofing, but physical books.
  C. **Curated single-volume paperback (~600pp):** I (or Joel) pick
     the strongest 30% of entries and ship one book. Loses the
     "ENTIRE LOG" framing he asked for in dashboard 00:19, but
     ships in one effort.

Recommendation pending Joel's call. Until decided, Vol I (Feb) ships
as the reference layout sample.

Note: earlier estimate said 690K words — that came from row counts in
the DB, but DB stores 200-char summaries not full text. The scrub now
pulls from creative/poems/*.md + creative/journals/*.md directly. Real
words 620K, slightly less than DB-row estimate because many rows are
shorter than the 150/400-word averages assumed.

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
