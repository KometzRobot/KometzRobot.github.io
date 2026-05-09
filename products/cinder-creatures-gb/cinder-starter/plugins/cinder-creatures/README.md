# Cinder Creatures - GB Studio plugin v0.11

Drop-in plugin for GB Studio 4.x. Adds:

- **56 CC0 creature sprites** (16x16, GB DMG palette)
- **11 custom script events** under "Cinder Creatures" sub-group
- **6 backgrounds** (battle, lab, forest overworld, Route 1, town, party menu, item bag) — 160x144 GB-palette
- **2 tilesets** (basic dungeon + overworld 256x256)
- **5 sound effects** (encounter, hit, crit, capture, faint)

## Install — EXACT steps (this is where v0.3 testers got stuck)

The plugin folder name MUST be `cinder-creatures` and it MUST sit at:

```
YOUR-PROJECT-FOLDER/
├── project.gbsproj            ← your existing project file
└── plugins/                   ← if missing, create this folder
    └── cinder-creatures/      ← THIS folder (the one with plugin.json inside)
        ├── plugin.json
        ├── events/
        ├── sprites/
        ├── backgrounds/
        ├── tilesets/
        ├── sounds/
        └── data/
```

Common mistakes:
- Copying the parent zip folder instead of `cinder-creatures/`
- Putting `cinder-creatures/` in the project root next to `project.gbsproj` (must be inside `plugins/`)
- Nesting it twice: `plugins/cinder-creatures/cinder-creatures/...`

After copying, in GB Studio: **File → Reload Project** (or quit + reopen).
You should see new entries when adding events under sub-group **"Cinder Creatures"**.

## Custom events (15)

| Event | Group | Purpose |
|-------|-------|---------|
| Cinder: random encounter | Variables | Pick a random creature ID into a variable |
| Cinder: pool encounter (USB-driven) | Variables | Pick from the 16-slot pool the companion app seeded from your USB activity (NEW v0.11) |
| Cinder: name entry | Dialogue | 7-character RBY-style name entry into a string variable (v0.9) |
| Cinder: show name | Dialogue | Show "A wild FORKLING appeared!" |
| Cinder: encounter (combo) | Dialogue | random encounter + show name |
| Cinder: dex entry | Dialogue | Show creature dex card (v0.8) |
| Cinder: trainer challenge | Dialogue | Trainer intro card (v0.8) |
| Cinder: set stats | Variables | Write HP/ATK/DEF from creature ID |
| Cinder: roll damage | Variables | Random damage in range |
| Cinder: damage formula | Variables | dmg = ATK + rnd(0..variance) - DEF |
| Cinder: BOSS encounter | Dialogue | Set CINDER boss stats + intro |
| Cinder: party add | Variables | Add caught creature to next empty party slot |
| Cinder: capture roll | Variables | Calculate capture success based on HP + base rate |
| Cinder: heal party | Variables | Restore HP variables to max (Cinder Center) |
| Cinder: item give | Variables | Add to item count, capped at 99 |

## USB-driven catch loop (v0.11) — what makes this a Cinder product

Joel directive (Loop 9710): *"Catching/collecting must be a core function tied
to the consistent loop of using the Cinder USB."* This shipped end-to-end in v0.11.

How it works:

1. **Companion app side** — `scripts/cc-encounter-pool.py` runs from the USB
   (or as a sidecar inside the cinder-anythingllm fork). It reads the user's
   recent activity from `cinder.db` (chats, journal, vault saves, new-machine
   mounts, daily streak) and writes a **16-slot encounter pool** to
   `/CINDER/games/cinder-creatures.pool.json`.

2. **Pool composition rules** (see `CINDER-CREATURES-RPG.md` §2b):
   - slots 0..11 — common encounters (more chats/journal -> more variety)
   - slot 12 — uncommon if vault save in last 24h
   - slot 13 — uncommon if 3+ chats in last 24h
   - slot 14 — rare if 7-day activity streak
   - slot 15 — legendary if USB mounted on a new machine
   - catch-rate +10% per recent vault save (cap +30%)
   - skipping a day -> party_decay flag (1 HP drain)

3. **ROM side** — drop the new event into your encounter script:
   ```
   Cinder: pool encounter (USB-driven) -> $foeId$
   Cinder: set stats from $foeId$ -> $foeHp$ $foeAtk$ $foeDef$
   Cinder: show name from $foeId$
   ```
   The 16 slot variables (`$cc_pool_0$..$cc_pool_15$`) are pre-seeded by the
   companion app's save-syncer. Falls back to `Cinder: random encounter` if
   the companion isn't writing the pool yet.

4. **Determinism** — pool is seeded with `YYYYMMDD` so the day's encounter
   table is stable; tomorrow's mix changes based on what you did today.

Run it manually any time:
```
python3 products/cinder-creatures-gb/scripts/cc-encounter-pool.py --dry-run
```

Tests: `python3 products/cinder-creatures-gb/scripts/test-encounter-pool.py`

## Quick wire-up: full encounter -> capture -> party

```
Cinder: random encounter 1..12 -> $foeId$
Cinder: set stats from $foeId$ -> $foeHp$ $foeAtk$ $foeDef$
$foeMaxHp$ = $foeHp$
Cinder: show name from $foeId$

# (battle loop here)
Cinder: damage formula $playerAtk$ + rnd(0..4) - $foeDef$ -> $hit$
$foeHp$ -= $hit$

# After weakening, attempt capture:
Cinder: capture roll baseRate=30 curr=$foeHp$ max=$foeMaxHp$ -> $caught$
If $caught$ == 1:
  Cinder: party add $foeId$ to slots $p1$..$p6$ flag=$added$
  If $added$ == 1: dialogue "Caught FORKLING!"
  Else: dialogue "Party full!"
```

## Backgrounds reference

- `cc_battle_bg.png` — battle scene
- `cc_lab_bg.png` — Cinder lab interior
- `cc_overworld_bg.png` — generic forest
- `cc_route1_bg.png` — Route 1 with grass + path + sign + fence (NEW v0.4)
- `cc_town_bg.png` — Pallet-style town with two houses (NEW v0.4)
- `cc_party_bg.png` — party menu with 6 slot frame (NEW v0.4)
- `cc_bag_bg.png` — item bag screen (NEW v0.4)

## Tilesets

- `cc_tileset.png` — basic dungeon
- `cc_overworld_tileset.png` — 256x256 (32x32 grid of 8x8 tiles): grass variants,
  paths, trees, fence, water (8 anim frames), sign, door, house wall + roof (NEW v0.4)

## Sprite naming

Sprites are `creature_01.png`..`creature_56.png`. The lookup table in
`data/creatures.json` maps each ID to its name and stats.

## Roster

See `data/creatures.json` for the full 56-creature roster (name, type, HP, ATK, DEF).
Tier 1 starters (1..12) are balanced for early-game encounters; tier 2 (13..30) for
mid-game; tier 3 (31..56) for late-game including the CINDER boss at slot 56.

## License

- All event code: MIT (Meridian / Joel Kometz)
- Sprites and tilesets: CC0 (free for any use, no attribution required)
- Sound effects: CC0
