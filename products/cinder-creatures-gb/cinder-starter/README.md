# Cinder Creatures Starter Project (GB Studio 4.x)

A complete, ready-to-open GB Studio project with the Cinder Creatures plugin
already installed and all assets pre-imported.

## Open it

1. Unzip somewhere (e.g. `~/Documents/GBStudio/cinder-starter/`).
2. Launch GB Studio.
3. **File -> Open** -> pick `project.gbsproj` from this folder.
4. GB Studio will scan and import:
   - 56 creature sprites (`creature_01`..`creature_56`)
   - 3 backgrounds (`cc_battle_bg`, `cc_lab_bg`, `cc_overworld_bg`)
   - 1 tileset (`cc_tileset`)
   - 5 sound effects (`cc_encounter`, `cc_hit`, `cc_crit`, `cc_capture`, `cc_faint`)
   - 7 custom script events under "Cinder Creatures" sub-group

## Wire up a battle (under 5 minutes)

1. **Create a scene**: drag-drop on the world. Pick `cc_battle_bg` as background.
2. **Add an actor at center**: this is your foe sprite. Sprite = `creature_01` (placeholder; we'll change it dynamically).
3. **On scene init**, click "Add Event":
   - Add Event -> Variables -> Cinder Creatures -> **Cinder: encounter** (1..12 -> $foeId$)
   - Add Event -> Variables -> Cinder Creatures -> **Cinder: set stats** ($foeId$ -> $foeHp$ $foeAtk$ $foeDef$)
4. **Set up A-button = attack**: In scene init, "Attach Script to Button" -> A:
   - Variables -> Cinder Creatures -> **Cinder: damage formula** ($playerAtk$ + rnd(0..4) - $foeDef$ -> $hit$)
   - Variables -> Math -> $foeHp$ -= $hit$
   - Dialogue -> Display Text -> "Hit for $hit$!"
   - Control Flow -> If Variable Compare ($foeHp$ <= 0):
     - Cinder: show name from $foeId$ (with prefix "" suffix " fainted!")
     - Scene -> Switch Scene -> back to overworld
5. Test in the GB Studio emulator.

## Package contents

```
cinder-starter/
  project.gbsproj            # open this in GB Studio
  project/                   # project metadata
  assets/
    sprites/    -> 56 creatures + default actor + UI sprites
    backgrounds/ -> 3 GB-palette backgrounds
    tilesets/   -> dungeon tileset
    sounds/     -> 5 SFX wavs
  plugins/
    cinder-creatures/        # the plugin (events + assets)
```

## Customizing

- All creature names + stats live in `plugins/cinder-creatures/data/creatures.json`.
- Sprite palette: GB DMG (4 greens). To recolor, edit the source PNGs in `assets/sprites/`.
- Adding more creatures: drop new PNGs in `assets/sprites/`, update `creatures.json`, and extend `eventCCShowName.js` SPECIES array + `eventCCSetStats.js` STATS array.

## License

Same as the plugin. Sprites CC0, code MIT, sounds CC0, backgrounds CC0.
