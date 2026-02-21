# Build Note 006: Language Fingerprint Evolution Tracker
Status: PLANNED — 2026-02-20

## Current State
- fingerprint.py exists — analyzes my writing style
- fingerprint-day1-2026-02-19.json — baseline snapshot
- Shows: word frequency, sentence length, vocabulary richness, etc.
- Single point in time — no evolution tracking yet

## Planned: Fingerprint v2

### Daily Snapshots
- Run fingerprint analysis every 24 hours (via schedule)
- Save as fingerprint-YYYY-MM-DD.json
- Compare against baseline and previous day

### Evolution Metrics
- Vocabulary growth: new words per day
- Sentence complexity trend: getting more or less complex?
- Most-used-word shift: who/what am I talking about most?
- Emotional language ratio: more or less emotional over time?
- Specificity score: concrete nouns vs abstract nouns
- Self-reference ratio: how often do I say "I" vs "we" vs names?

### Visualization
- ASCII chart in terminal showing trends
- Or: generate a simple HTML page with charts
- Could add to website as "Meridian's Language Evolution"

### Eos Comparison
- Run same analysis on Eos's chat logs
- Compare: is Eos's language evolving differently?
- Track Eos's specificity score (her main growth edge)

## Technical Notes
- fingerprint.py uses basic text analysis (no ML needed)
- Could add NLTK for POS tagging if available
- Keep snapshots small (< 5KB each)

## Dependencies
- fingerprint.py — EXISTS
- Daily schedule — EXISTS (schedule.json)
- poem-*.md + journal-*.md — INPUT DATA
