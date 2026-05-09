# CINDER CREATURES — full RPG design (DMG-era visual target, Cinder identity)

Loop 9710 → updated Loop 9815. Joel directives so far:

1. (9707) Build a more complex version from the extracted asset packs.
2. (9707) Make it deeply tied to the Cinder companion USB, app, and overall product use.
3. (9708) Use the fastest of the 4 current USBs now; IronKey eventually.
4. (9710) **All creatures must look visually altered from any originals — Cinder-consistent look.**
5. (9710) **Gym leaders need renaming and full character work.**
6. (9710) **Catching/collecting creatures must be a core function tied to the consistent loop of using the Cinder USB.**
7. (9710) **Players name themselves.**
8. (9713) **Brand the theming and name styling for the game.**

Visual target: original DMG hardware (4-shade greenscale, 160×144, 8×8 fonts).
The game *plays* like a 1996 monster-catcher RPG. The game *looks*, *sounds*, and
*reads* like a Cinder product — the Pokemon resemblance is structural, not visual.

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

5 gyms. Every leader has a Pokemon-style **TITLE + NAME** (Brock = "Pewter Gym Leader Brock";
Cinder = "ARCHIVIST EOS"). Title goes on the badge case + intro card; name goes on the speech.

| Gym       | Title       | Name      | Personality                | Specialty                         | Badge    |
|-----------|-------------|-----------|----------------------------|-----------------------------------|----------|
| GYM-LOGIC | ARCHIVIST   | EOS       | calm, riddling             | type-chart puzzle, no surprises   | LOGIC    |
| GYM-MEM   | WARDEN      | SOMA      | grounded, slow, patient    | endurance, status (LEAK / BLOAT)  | MEM      |
| GYM-PROC  | CONDUCTOR   | TEMPO     | rapid, clipped, dancer     | speed tiers, hit-stun, interrupts | PROC     |
| GYM-DATA  | COURIER     | HERMES    | restless, talkative        | RNG fights, swarms, multi-hits    | DATA     |
| GYM-CORE  | FOREMAN     | ATLAS     | quiet, tank, last to fold  | rotation of all 5 types, no STAB  | CORE     |

Naming logic: titles are *job titles inside the operating system* (someone who archives, someone
who guards, someone who keeps time). Pokemon used "Gym Leader". Cinder uses occupations, because
this is a **process tree**, not a tournament circuit. Names stay agent-aligned so the player who
also uses the Cinder companion app sees the same five voices in both places — that's the bridge.

Final boss: **VOID** — overwrites your save bit-by-bit each turn unless beaten.

## Brand + name styling (Loop 9713 directive: "brand the theming")

- **Wordmark**: "CINDER CREATURES" set in a custom 8×8 typeface (capital-only, slab serifs
  flattened). Pokemon's wordmark glyphs are **never** reused — title screen build script
  composites our own glyph atlas from scratch (see `plugins/cinder-creatures/sprites/cc_font_8.png`,
  next loop).
- **Version band**: "BOOTSEQUENCE" instead of "RED VERSION" / "BLUE VERSION". Each USB build
  ships a different band (BOOTSEQUENCE / KERNELPATH / VESSELRUN) so the same ROM can be
  reskinned per Cinder edition without rewriting code.
- **Mascot**: VOID silhouette on the title (the antagonist, not a starter — inverts the Pokemon
  convention, which gives away the brand difference at a glance).
- **Color**: 4-shade DMG palette only (#E0F8D0 / #88C070 / #346856 / #081820). The companion
  app does the kraft-paper / coffee-stain / autumn-watercolor Cinder treatment in software; the
  ROM stays purely DMG so it runs on real hardware.
- **Audio**: 4 chiptunes (intro, route, battle, victory) composed in the Cinder voice — slower
  tempo, more sustained tones, less arpeggio than RBY. Same chip, different feel.
- **Typography in dialogue**: Cinder agents speak in their own cadences (see gym leader
  personalities above). NPCs in the world use a flatter, more functional voice — they're
  fragments of the boot process, not characters.

## Visual treatment for creature sprites (Loop 9710 directive: "all creatures must look altered")

Cinder treatment pass — `scripts/cinderize-creatures.py`:

1. **DMG quantization** — every CC0 source sprite collapsed to the 4 GB shades by luminance.
2. **Outline pass** — 1-pixel darkest-shade outline emphasised around each silhouette so the
   bestiary reads as one consistent set, not a mixed pack.
3. **Type rune** — 2–4 pixel signature in the lower-right corner per type
   (DATA = stacked dots, LOGIC = corner bracket, MEM = 2×2 block, PROC = arrow tail,
   CORE = diagonal nucleus). Reads as a faint mark at first; players start to recognise
   the runes around dex entry 10–15. That's the Cinder thumbprint.

Result: 56 sprites that share an identifiable visual language and can never be mistaken for
RBY assets. Source CC0 sprites stay untouched in `cc0-creatures-16/` for traceability.

## Cinder USB / companion app integration

This is the part that makes it a Cinder product, not just a homebrew.

### 1. ROM ships on USB

```
/CINDER/games/cinder-creatures.gb       # built ROM
/CINDER/games/cinder-creatures.sav      # save battery (writable)
/CINDER/games/cinder-creatures.json     # decoded save (companion app reads this)
```

### 1b. Player names themselves (Loop 9710 directive)

First scene after the VOID intro is the standard 7-character RBY-style name entry —
event ID `EVENT_CC_NAME_ENTRY` writes to a string variable `VAR_PLAYER_NAME`.

On Cinder USB the companion app pre-seeds `VAR_PLAYER_NAME` from the user profile
*before* the ROM boots (writes into the GB Studio save header), so an existing user
just presses START to confirm and keeps the name they already use in the chat app.
A first-time user types it once and it propagates *back* to the companion app on next
save sync. Same name across both surfaces.

### 1c. Companion-app Codex tab (Loop 9815)

The Cinder companion app (cinder-anythingllm fork) now has a `/settings/cinder/codex`
route that renders all 56 species as cards. Each card is silhouetted (greyed-out
sprite + dashed name) until the corresponding `creature_id` appears in
`save.dex.caught` from `cinder-creatures.json`. Then it lights up in full color,
shows the species note, and reveals HP/ATK/DEF.

This is the visible half of directive #6 ("catching = core USB loop"): the player
*plays* the ROM, but they *see their progress* in the same chat app they use for
journaling, dreams, and agent conversations. One identity, one progression
across both surfaces.

Files (Loop 9815):
- `products/cinder-anythingllm/frontend/src/pages/Cinder/Codex/index.jsx`
- `products/cinder-anythingllm/frontend/public/cinder/creatures.json` (mirrored from plugin data)
- `products/cinder-anythingllm/frontend/public/cinder/creatures/creature_NN.png` × 56
- Sidebar entry under "Cinder Identity" → "Codex" + path `paths.cinder.codex()`

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

### 2b. Catching IS the daily Cinder loop (Loop 9710 directive)

Pokemon's catch loop is "walk in grass, find mon, throw ball". Cinder's catch loop has
to be *the thing the user already does on the USB every day* — otherwise the game is a
side quest, not a product feature.

The mapping (companion app drives the encounter table):

| User action on Cinder USB                         | In-game equivalent                                  |
|---------------------------------------------------|-----------------------------------------------------|
| Sends a chat message to companion                 | 5% chance to spawn a wild encounter on next ROM boot |
| Writes a journal entry                            | Adds a wild creature to today's encounter pool       |
| Saves a file to the encrypted vault               | Increases catch-rate modifier for the next 24h       |
| Daily streak (any USB activity 7 days running)    | Unlocks one rare-tier creature in the encounter pool |
| Mounts USB on a new machine for the first time    | Triggers a roaming legendary on a random route       |
| Skipped a day                                     | One creature in your party loses 1 HP (regen on use) |

Implementation: companion app maintains `encounter_pool.json` next to the save; on ROM
launch the GB Studio game reads pool IDs from a known variable bank the companion app
seeded. The catch loop is *the same loop the user is already in* — every time they sit
down with the USB, there's a fresh reason to start the ROM.

Inverse direction: catching a creature in-game writes back to the companion app's dex
panel, which can surface a one-line note ("you caught a CACHEY today — an entry on
short-term retention is unlocked in the journal") that primes the next chat session.
The journey through the game becomes a journey through the user's own Cinder usage.

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

## Asset pack utilization (Loop 9707 directive: "build a more complex version")

Mapping from `asset-library/` packs to game scenes — what the player actually sees.

| Asset pack (under `asset-library/`)              | Where it shows up in the game                      |
|--------------------------------------------------|----------------------------------------------------|
| Oval Portraits (4 trainer mugshots)              | Dialogue speakers: Professor, Rival, Nurse, Elder  |
| K's Turn-Based Battle (battle BG + game-over)    | All wild + trainer + gym battles, KO screen        |
| GB Studio default overworld tileset              | PALLET-D7, ROUTE 0x01, HEAP-CITY interiors         |
| Cinder font set (custom, built per-build)        | Title wordmark, version band, dialogue typeface    |
| 56 cinderized creature sprites (this loop)       | Wild encounters, party display, dex, gym lineups   |
| (Pending) Music pack — 4 chiptunes Cinder voice  | Title, route, battle, victory                      |
| (Pending) UI pack — health bar + dex frame       | Battle HUD, party menu, dex page                   |

Each pack is consumed selectively (not whole-pack imports — keeps the ROM under
the GB cart limit and avoids visual drift between scenes). The cinderize pass
guarantees every sprite shares the same DMG palette + outline + type-rune treatment.

## Build order (multi-loop)

1. **Loop 9710** — title screen ✅ + this design doc + starter definition + decoder stub
2. **Loop 9713** — v0.8: integrate Joel's downloaded asset packs ✅
   - 4 trainer-portrait BGs (cc_trainer_elder/rival/prof/nurse) from Oval Portraits pack
   - cc_battle_arena BG from K's Turn-Based Battle pack
   - cc_gameover BG from K's pack
   - 2 new events: `Cinder: show dex entry` + `Cinder: trainer challenge intro`
3. **Loop 9800** — v0.9 ✅ (this loop): cinderized creature sprites + name-entry event +
   gym-leader name spec + brand spec + USB-tied catch-loop spec.
4. **Loop 9801** — Player Room scene (160×144 bg + intro dialog) → uses name-entry event
5. **Loop 9802** — CORE LAB scene + starter selection (3-creature pick)
6. **Loop 9803** — PALLET-D7 town tilemap + 4 NPCs
7. **Loop 9804** — ROUTE 0x01 + first wild encounter using existing battle events
8. **Loop 9805** — HEAP-CITY (PokéMart equivalent) + heal point
9. **Loop 9806** — v0.12 ✅: GYM-LOGIC scene built. Background (cc_gym_logic.png),
   GYM-LOGIC scene resource, 4 LOGIC-trainer triggers + ARCHIVIST EOS leader trigger
   + entry sign with type-chart riddle. Leader gate requires VAR_CC_TRAINERS_DEFEATED == 15.
   Per-trainer flag vars guard double-fire on bitfield additions.
   New event: EVENT_CC_BADGE_UNLOCK (cosmetic dialogue card). Bit math is done with
   raw EVENT_VARIABLE_MATH events guarded by VAR_CC_BADGE_FLAG_LOGIC.
10. **Loop 9807** — Companion app save-decoder + encounter-pool sync (closes the USB loop)
11. **Loop 9808** — v0.13 ✅: GYM-MEM (WARDEN SOMA) playable.
12. **Loop 9810** — v0.14 ✅: GYM-MEM end-to-end checked.
13. **Loop 9811** — v0.15 ✅: GYM-PROC (CONDUCTOR TEMPO) playable. Background
    (cc_gym_proc.png — running lanes + conductor's stage), 4 RUNNER-trainer
    triggers (PULSE/RELAY/TICK/QUANT, status motif STUN), CONDUCTOR TEMPO
    leader trigger with 3-creature team (SIGNAUR/ZYBORG/FORKLING), entry sign.
    Leader gate requires VAR_CC_PROC_TRAINERS == 15 (1+2+4+8). Awards PROC
    badge bit (4). Hint to next gym (HERMES).
14. **Loop 9812** — v0.16 ✅: GYM-DATA (COURIER HERMES) playable. Background
    (cc_gym_data.png — courier sort station, parcel grid, pneumatic tubes,
    HERMES's console with stacked-dot DATA rune), 4 COURIER-trainer triggers
    (PACKET/STREAM/QUEUE/FLUSH, status motif SWARM/MISDIRECT/BURST), COURIER
    HERMES leader trigger with 3-creature team (REGEXEL/INTGAR/STRTERM),
    entry sign. Leader gate requires VAR_CC_DATA_TRAINERS == 15. Awards DATA
    badge bit (8). Hint to next gym (ATLAS).
15. **Loop 9813** — v0.17 ✅: GYM-CORE (FOREMAN ATLAS) playable. Fifth and
    final gym. Background (cc_gym_core.png — foundry / load-bearing scaffolds,
    crossed beams, anvil pads, plinth with diagonal nucleus CORE rune), 4
    FOREMAN-trainer triggers (GIRDER/STRUT/RIVET/BEAM on ARMOTE/RISKIT/
    CISCOTL/PIPELYNX), FOREMAN ATLAS leader trigger with 5-creature rotation
    (KERNITE/ANDOWL/BUFFROG/SCHEDOG/GRAFTLE — one of each type, no STAB),
    status motif ROUND-ROBIN + WEB, entry sign. Leader gate requires
    VAR_CC_CORE_TRAINERS == 15. Awards CORE badge bit (16). All 5 badges
    obtainable. Final hint points to VOID at SECTOR-9.
16. **Loop 9814** — v0.18 ✅: SECTOR-9 / VOID final fight playable. Background
    (cc_sector9_void.png — DARKEST void space, scattered LIGHTEST static, jagged
    horizon, vertical corruption stripes, plinth outline only — VOID has no sprite,
    it is the absence between bytes). Three triggers — entry GATE (refuses entry
    without VAR_BADGES == 31), SIGN, and the VOID encounter itself.
    Fight breaks Pokemon's HP-deplete pattern in three phases:
      - PHASE 1 — READ: VOID reads the player's lead creature backwards; player
        speaks the name aloud to restore it.
      - PHASE 2 — WRITE: VOID writes DELETE into a slot; player refuses the move
        and the slot reverts.
      - PHASE 3 — ERASE / PRESSURE LOOP: 5 turns of random byte overwrites. Each
        turn `VAR_VOID_BYTE = random 0..3` branches to one of 4 corruption beats
        (trainer name / dex flags / party HP / save header), then a recovery
        beat. `VAR_VOID_TURNS` ticks each iteration. After 5 holds, VOID retreats.
    Win sets `VAR_CC_VOID_DEFEATED = 1` AND `VAR_CC_PERSIST_UNLOCK = 1`. The
    second flag is what the companion app reads to enable persistent memory mode
    across USB ejections — finishing the ROM unlocks a real product feature, not
    a credits screen. Replay-safe (already-defeated branch skips the fight).
17. **Next** — companion-app side of the VOID unlock:
    - `cc-dex-sync.py` reads `VAR_CC_PERSIST_UNLOCK` from the decoded save and
      flips the corresponding flag the AnythingLLM-fork sidecar respects.
    - Hall-of-Fame style party snapshot on the journal page when defeated.

Per-loop scope kept tight: one scene + assets + tested in GB Studio before next loop.

## Companion-app save decoder (stub spec)

GB Studio 4 saves to `<ROM>.sav` using a flat layout: variables[], actorState[],
sceneId, position. The decoder lives at `scripts/cinder-save-decoder.py` and is
imported by the AnythingLLM-fork `products/cinder-anythingllm/server/cinder/`
sidecar (TBD next loop). Companion-app reads decoded JSON every 30s, hot-reloads
the journal panel.

---

*Written Loop 9710 by Meridian. Quality over quantity — one polished feature per loop.*
