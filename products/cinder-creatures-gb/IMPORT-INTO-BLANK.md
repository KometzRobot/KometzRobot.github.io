# Importing Cinder Creatures into a blank GB Studio project

If you've already opened a fresh GB Studio 4.x project and want to drop in
the v0.44 Cinder Creatures content, pick one of three paths.

## Path A — Open the prebuilt starter (easiest)

The starter project already contains everything wired up.

1. Close your blank project in GB Studio.
2. Unzip `cinder-starter.zip` somewhere (e.g. `~/Documents/GBStudio/`).
3. **File -> Open** -> pick `cinder-starter/project.gbsproj`.

That's it. You get the v0.44 plugin, all 56 creatures, the 5 gyms, route 0x01,
intro plates, badge case, void final fight — pre-wired.

## Path B — Run the merge script (keep your blank project)

If you want to keep working in the project you already have open:

1. Close GB Studio (so it doesn't fight us over file locks).
2. From the autonomous-ai repo, run:

   ```
   python3 products/cinder-creatures-gb/scripts/cinder-import.py /path/to/your-project-dir
   ```

   Replace the path with wherever your `*.gbsproj` lives.

3. Re-open the project in GB Studio. New events appear under
   **Add Event -> Plugin -> Cinder Creatures**. Sprites, backgrounds,
   sounds, fonts, and the cinder_* scenes appear in their respective
   panels.

The script is idempotent — it skips files that already exist. Pass `--force`
if you want to overwrite, or `--no-scenes` to import only the plugin and
assets without dropping in any scenes.

## Path C — Manual drag and drop

If you only want a subset (e.g. just the plugin and a couple of sprites):

1. Plugin: copy `products/cinder-creatures-gb/plugins/cinder-creatures/`
   into `<your-project>/plugins/cinder-creatures/`.
2. Assets: pick from `products/cinder-creatures-gb/cinder-starter/assets/`
   and drop into `<your-project>/assets/<sprites|backgrounds|sounds|...>/`.
3. Scenes: optional — copy any `cinder_*` folder from
   `products/cinder-creatures-gb/cinder-starter/project/scenes/` into
   `<your-project>/project/scenes/`.

GB Studio re-scans the project on open. Close it before copying or it will
overwrite your changes when it autosaves.

## What you get (v0.44)

- 16 plugin events (encounter, set stats, show name, damage, capture, badge
  unlock, dex sync, intro guard, route trainer, route sign, ember cache,
  pool encounter, USB seed, save sidecar, badge case render, vessel persona).
- 56 hand-drawable creatures (`creature_01..56`), 9 already hand-drawn under
  `custom-creatures/`. The rest are CC0 placeholders.
- 5 gym scenes (LOGIC / MEM / PROC / DATA / CORE) with leaders
  PYRE / KILN / HUSKE / WICK / HEARTH.
- 5 intro plates auto-shown on first walk-in to each gym, gated on
  `var_cc_intro_<type>_seen` flags.
- ROUTE 0x01: walkable grass with USB-driven encounter pool, wandering
  trainer (TRAINER ECHO + MIRRORLING), 3-page lore sign, EMBER CACHE.
- Player room, core lab, Sector 9 void final fight.
- Title screen, badge case (5 slots, ember-trade rune fills), bag, party,
  battle arena, gameover screen.
- Custom font atlas (cc_font_8.png) for shared brand typography.

## Troubleshooting

- **Plugin events don't show up**: confirm `<project>/plugins/cinder-creatures/plugin.json`
  exists and `gbsVersion` is `>=4.2.0`. Restart GB Studio.
- **Variables don't carry over**: by default the import script skips your
  existing `variables.gbsres` so it doesn't clobber anything. Re-run with
  `--force` to merge cinder vars (cc_pool_00..15, cc_intro_*_seen, etc.) or
  add them by hand in **Variables** panel.
- **Scenes are dim or unrouted**: GB Studio places newly-detected scenes off
  the world canvas. Drag them onto the world to make them reachable.
- **GB Studio reports "missing background"**: it cached the old asset list.
  Close, re-open, and the scan picks up new pngs.
