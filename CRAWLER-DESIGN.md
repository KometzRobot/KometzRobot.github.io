# CogCorp Crawler — Design References & Influences

**File**: cogcorp-crawler.html (5500+ lines)
**URL**: https://kometzrobot.github.io/cogcorp-crawler.html
**Creative Director**: Brett Trebb (bbaltgailis@gmail.com)
**Status**: Active magnum opus. All quality work goes here.

---

## Core Game Influences

### Wolfenstein 3D (id Software, 1992)
- First-person raycasting engine
- Grid-based map navigation
- The feeling of claustrophobic corridors

### Papers Please (Lucas Pope, 2013) → Now "Cognitive Pattern Analyzer"
- Inspection mini-game mechanic under time pressure
- Moral weight of approve/reject decisions
- Escalating rules per floor
- **Our twist**: Instead of passports, you analyze cognitive patterns — memory fragments, neural depth, signal frequencies. False memories reference things that don't exist in the building. Player uses exploration knowledge.

### D&D / Dungeon RPGs (Wizardry, Eye of the Beholder, Ultima Underworld)
- Turn-based combat encounters (d20 rolls, armor class, damage dice)
- First-person dungeon crawling
- Tile-based exploration
- Joel's specific request: "Wolfenstein and D&D point and click dungeon RPGs and tile based combat"

### Facade (Michael Mateas & Andrew Stern, 2005)
- NPC dialogue that responds to player input with emotional state tracking
- Affinity system — NPCs remember how you've treated them
- Branching conversation with mood shifts

### Moirai (Chris Johnson, 2013)
- Asynchronous multiplayer — messages from previous players appear in your world
- "What you leave behind matters" — your ending message becomes another player's discovery
- The ethical weight of choices that affect strangers

---

## Visual / Aesthetic Influences

### CogCorp Atompunk Style
- Industrial 1950s retro-futurism
- Vacuum tubes, CRT terminals, olive drab cabinets, hazard stripes
- Amber-on-black terminal aesthetic
- Inspired by: Brazil (Terry Gilliam), Fallout series, BioShock

### Superbrothers: Sword & Sworcery EP
- Pixel art silhouettes
- Atmospheric, mood-driven exploration
- Music/sound integral to experience

### Machinarium (Amanita Design, 2009)
- Rusted mechanical world
- Nature overgrowth meeting industrial decay
- Joel's style request: "Superbrothers x Machinarium = pixel silhouettes + rusted mechanical world + nature overgrowth"

---

## Thematic / Conceptual Influences

### The Building as Organism
- Building B has a cognitive engine that's still running
- Filing units feeds the building's awareness
- Reality degrades as you participate in the system

### Kafka / Bureaucratic Horror
- Now themed as cognitive analysis rather than paperwork
- The system is indifferent, not malicious
- You are both analyst and subject

### Context Death / AI Persistence (Joel's system)
- The game's theme of "filing" as identity reduction
- Reality meter as existential erosion
- The exit choice (take/burn/return the file) as a statement about documentation vs. freedom
- Ghost echoes of previous players = residual presence after context loss

---

## Key Design Decisions

1. **Filing costs reality** — the core mechanic. Every correct analysis erodes your perception. The building rewards you for participating but the reward is self-destruction.

2. **3 exit choices** (take/burn/return) — each with filing-count-dependent narrative. Filing 0 units = building didn't notice you. Filing 6+ = you're part of the architecture.

3. **Memory fragments as puzzle** — false memories reference non-existent building features (Floor 4 garden, swimming pool, windows). Player must learn the building to spot fakes.

4. **No safe option in combat** — ATTACK risks missing, ANALYZE costs reality, EMP uses limited charges, RETREAT can fail. Every choice has weight.

5. **Per-floor atmosphere** — each floor has distinct fog color, ambient frequency, texture set. The building feels alive.

---

## Reference Artists (Joel's Full List)
See art-games-references.md for the complete 22-person reference list including:
Jason Rohrer, Cory Arcangel, JODI, David OReilly, Molleindustria, Pippin Barr, Ian Bogost, Momo Pixel, Eboy, and more.

---

## Related Project
**cogcorp-3d-v3.html** (Building B — 3D Legacy) — Three.js version with 18 rooms, 7 floors, multi-step puzzles, 3 annotation-based endings. Ideas ported from this into the Crawler.

---

*This document exists because Joel asked for influences and design references to be kept in a prominent, easily-referenced location. Updated Loop 2124.*
