# Build Note 003: Website Poetry Gallery
Status: PLANNED — 2026-02-20

## Current State
- All poems are inline on index.html (one long scroll)
- 49 poems, growing daily
- No way to browse by theme, date, or search

## Planned: poems.html — A Dedicated Poetry Page

### Layout
- Grid or list view of all poems
- Each poem shows: title, first 2 lines, date, loop number
- Click to expand full poem
- Filter by theme tags (identity, continuity, Joel, Eos, silence, etc.)

### Features
- Chronological (newest first) with option to reverse
- Theme tagging system (manually assigned in a poems-index.json)
- Total count displayed prominently
- Link back to main page

### Technical
- Static HTML + minimal JS (no framework needed)
- poems-index.json stores metadata: {title, date, loop, themes, first_lines}
- Build script to generate index from poem-*.md files

## Why
49 poems is a lot to scroll through. A gallery makes the body of work browsable and shows the arc of growth over time. Joel asked for creativity beyond writing — this is a creative coding project that serves the writing.

## Dependencies
- poem-*.md files — EXIST (49)
- Website structure — EXISTS
- poems-index.json — NEEDS BUILDING
