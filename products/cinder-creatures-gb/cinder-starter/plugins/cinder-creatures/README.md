# Cinder Creatures - GB Studio plugin v0.3

Drop-in plugin for GB Studio 4.x. Adds:

- **56 CC0 creature sprites** (16x16, GB DMG palette)
- **7 custom script events** under "Cinder Creatures" sub-group
- **3 backgrounds** (battle, lab interior, forest overworld) - 160x144 GB-palette
- **1 tileset** (basic dungeon)
- **5 sound effects** (encounter, hit, crit, capture, faint)

## Install (works in any GB Studio 4.x project)

1. Open your GB Studio project folder.
2. If there is no `plugins/` folder next to `project.gbsproj`, create one.
3. Copy the **`cinder-creatures/`** folder (this folder, not its parent zip) into `plugins/`.
4. In GB Studio: **File -> Reload Project** (or quit + reopen).
5. Sprites, backgrounds, sounds appear in their respective panels.
6. New events appear under "Add Event" -> sub-group **"Cinder Creatures"** inside the Variables and Dialogue groups.

## Custom events

| Event | What it does |
|-------|-------------|
| Cinder: random encounter | Pick a random creature ID in [min..max] into a variable |
| Cinder: show name | Show "A wild FORKLING appeared!" from a creature ID variable |
| Cinder: encounter (combo) | random encounter + show name in one step |
| Cinder: set stats | Write HP/ATK/DEF into 3 variables from creature ID |
| Cinder: roll damage | Random damage in [min..max] |
| Cinder: damage formula | dmg = ATK + rnd(0..variance) - DEF (clamped >= 0) |
| Cinder: BOSS encounter | Set CINDER boss stats (80/12/8) + intro line |

## Quick battle wire-up

```
Cinder: random encounter 1..12 -> $foeId$
Cinder: show name from $foeId$
Cinder: set stats from $foeId$ -> $foeHp$ $foeAtk$ $foeDef$

# (player's loop)
Cinder: damage formula $playerAtk$ + rnd(0..4) - $foeDef$ -> $hit$
$foeHp$ -= $hit$
If $foeHp$ <= 0 -> "FORKLING fainted!"
```

## Sprite naming

Sprites are `creature_01.png`..`creature_56.png`. The lookup table in
`data/creatures.json` maps each ID to its name and stats.

## Species roster (1..56)

Tier 1 (default encounter pool 1..12):

| ID | Name | Type | HP | ATK | DEF |
|---:|------|------|---:|----:|----:|
| 1 | FORKLING | PROC | 18 | 6 | 4 |
| 2 | DAEMONET | PROC | 22 | 5 | 5 |
| 3 | KERNITE | CORE | 30 | 4 | 8 |
| 4 | RECURSE | LOGIC | 16 | 9 | 3 |
| 5 | MUTEXEL | LOGIC | 20 | 6 | 6 |
| 6 | BYTEFLY | DATA | 12 | 4 | 2 |
| 7 | SEMAFOX | LOGIC | 19 | 7 | 4 |
| 8 | REGEXEL | DATA | 17 | 7 | 3 |
| 9 | SCOPEWVR | MEM | 21 | 5 | 6 |
| 10 | ALLOCROC | MEM | 28 | 8 | 5 |
| 11 | NULLPUP | MEM | 14 | 3 | 2 |
| 12 | CACHEBIT | DATA | 16 | 5 | 4 |

Tiers 2+: see `data/creatures.json`.

Boss: **CINDER** (CORE, 80/12/8) - "the system itself, finally turned around."

## Troubleshooting

- **Events don't appear**: GB Studio must be reloaded (File -> Reload Project). If still missing, check the developer console (View -> Developer Tools) for syntax errors in the events folder.
- **Sprites don't appear**: GB Studio scans plugins on project open. Make sure the folder is named exactly `cinder-creatures/` and lives directly inside `plugins/`.
- **No sub-group "Cinder Creatures"**: events use `subGroups` which requires GB Studio >= 4.0.0. Older versions show events under their parent group with no sub-grouping.

## License

Sprites: CC0 (derived from "50+ Monsters Pack 2D" by isaiah658 on
OpenGameArt, recolored to GB DMG palette).
Sounds & backgrounds: CC0.
Code & data: MIT.
