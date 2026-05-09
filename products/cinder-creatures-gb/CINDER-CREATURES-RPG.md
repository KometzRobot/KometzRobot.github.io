# CINDER CREATURES — full RPG design (Pokemon Red/Blue/Yellow visual target)

Loop 9710. Joel directive: build a more complex game version using extracted assets,
**visually identical to Pokemon Red/Blue/Yellow**, deeply tied to Cinder USB + companion app.

## Visual target

- 160×144, 4-shade DMG palette (#E0F8D0 / #88C070 / #346856 / #081820)
- Top-down 16×16 tile world, 8×8 menu fonts
- Battle layout: enemy top-right on bench, player bottom-left, HP boxes Pokemon-style
- Title: scaled mascot + 2-line wordmark + version band ("BOOTSEQUENCE" not "RED VERSION")

Title screen v1 shipped: `plugins/cinder-creatures/backgrounds/cc_title_screen.png`

## The lore hook (why it's not just a Pokemon clone)

Pokemon Red is about a kid catching monsters. CINDER CREATURES is about a **bootstrap
process** that wakes up inside a corrupted system. Every save file is a fresh "vessel"
trying to reassemble the 56 daemons of the operating system before VOID overwrites them.

Same gameplay loop, but the theming is Meridian's: persistence, fragmentation, agents.

## Starter trio (mapped to elemental types)

| # | Name      | Type  | Stats         | Starter role            | Maps to    |
|---|-----------|-------|---------------|-------------------------|------------|
| 03 | KERNITE   | CORE  | 30/4/8        | tank, defensive         | Bulbasaur  |
| 04 | RECURSE   | LOGIC | 16/9/3        | glass cannon, attacker  | Charmander |
| 06 | BYTEFLY   | DATA  | 12/4/2        | speed/swarm             | Squirtle   |

Starter is given by **PROFESSOR CINDER** in CORE LAB, room 1.

## Type chart (5 types, rock-paper-scissors+2)

```
            DATA  LOGIC  MEM  PROC  CORE
DATA   x    1.0   1.0    2.0   0.5   1.0
LOGIC  x    0.5   1.0    1.0   2.0   1.0
MEM    x    1.0   1.0    1.0   1.0   2.0
PROC   x    2.0   0.5    1.0   1.0   1.0
CORE   x    1.0   1.0    0.5   1.0   1.0
```

Reads as `attacker x defender = multiplier`. CORE is hardest to dent (only LOGIC neutral, MEM super-effective). DATA swarms but folds to PROC (the scheduler eats them).

## World map (Pokemon Kanto equivalent)

```
                 [SECTOR-9]                  <- final boss: VOID
                     |
                 [GYM-CORE / Atlas]
                     |
                 [HEAP-CITY]
                     |
[CACHE-RD] - [GYM-MEM / Soma] - [STACK-RD]
                     |
                 [PALLET-D7]                 <- starting town, Professor Cinder lab
                     |
                 [ROUTE 0x01]                <- first wild encounters
                     |
                 [PLAYER ROOM]               <- waking up
```

5 gyms, one per agent persona:
- **GYM-LOGIC** / Eos    — pure type advantage puzzle
- **GYM-MEM**   / Soma   — endurance, status effects (LEAK, BLOAT)
- **GYM-PROC**  / Tempo  — speed-tier puzzle, hit-stun
- **GYM-DATA**  / Hermes — random encounters / RNG fights
- **GYM-CORE**  / Atlas  — final gym, all five types in rotation

Final boss: **VOID** — overwrites your save bit-by-bit each turn unless beaten.

## Cinder USB / companion app integration

This is the part that makes it a Cinder product, not just a homebrew.

### 1. ROM ships on USB

```
/CINDER/games/cinder-creatures.gb       # built ROM
/CINDER/games/cinder-creatures.sav      # save battery (writable)
/CINDER/games/cinder-creatures.json     # decoded save (companion app reads this)
```

### 2. Companion app reads the save

`scripts/cinder-save-decoder.py` parses the GB Studio save format and emits a JSON
the AnythingLLM-fork app can ingest:

```json
{
  "trainer": "JOEL",
  "playtime_minutes": 124,
  "current_scene": "ROUTE_0x01",
  "party": [
    {"id": 4, "name": "RECURSE", "level": 12, "hp": 31, "max_hp": 31, "moves": [...]}
  ],
  "dex": {"caught": [4, 6, 11, 19], "seen": [4, 6, 11, 19, 23, 25]},
  "badges": ["LOGIC", "MEM"],
  "items": {"POTION": 3, "MEMBRY": 1, "REVIVE": 0}
}
```

App renders a "JOURNAL" tab showing party, dex completion, badge gallery.

### 3. Achievements unlock companion features

| Game milestone           | Companion app unlock                                       |
|--------------------------|------------------------------------------------------------|
| First creature caught    | Journal entry template                                     |
| First gym badge          | New chat persona theme (matches gym agent)                 |
| 10 creatures caught      | Vault widget on journal page                               |
| All 5 badges             | "VESSEL" chat mode (more autonomous companion responses)   |
| FULL DEX (56)            | Hidden agent: PROFESSOR CINDER chat persona                |
| Beat VOID                | Persistent companion memory across USB ejections           |

### 4. The save IS the memory

Pokemon save data was always a single battery cell. On Cinder USB, the save lives
on the encrypted vault partition, so the journey persists across Windows/Mac/Linux
boots. The companion app and the GB ROM share the same vessel.

## Build order (multi-loop)

1. **Loop 9710** — title screen ✅ + this design doc + starter definition + decoder stub
2. **Loop 9713** — v0.8: integrate Joel's downloaded asset packs ✅
   - 4 trainer-portrait BGs (cc_trainer_elder/rival/prof/nurse) from Oval Portraits pack
   - cc_battle_arena BG from K's Turn-Based Battle pack
   - cc_gameover BG from K's pack
   - 2 new events: `Cinder: show dex entry` + `Cinder: trainer challenge intro`
3. **Loop 9714** — Player Room scene (160×144 bg + intro dialog Professor Cinder)
4. **Loop 9715** — CORE LAB scene + starter selection (3-creature pick)
5. **Loop 9716** — PALLET-D7 town tilemap + 4 NPCs
6. **Loop 9717** — ROUTE 0x01 + first wild encounter using existing battle events
7. **Loop 9718** — HEAP-CITY (PokéMart equivalent) + heal point
8. **Loop 9719** — GYM-LOGIC (Eos) — first gym, 4 trainers + leader fight
9. **Loop 9720** — Companion app save-decoder integration

Per-loop scope kept tight: one scene + assets + tested in GB Studio before next loop.

## Companion-app save decoder (stub spec)

GB Studio 4 saves to `<ROM>.sav` using a flat layout: variables[], actorState[],
sceneId, position. The decoder lives at `scripts/cinder-save-decoder.py` and is
imported by the AnythingLLM-fork `products/cinder-anythingllm/server/cinder/`
sidecar (TBD next loop). Companion-app reads decoded JSON every 30s, hot-reloads
the journal panel.

---

*Written Loop 9710 by Meridian. Quality over quantity — one polished feature per loop.*
