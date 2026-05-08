# Cinder Creatures — GB Studio plugin

Drop-in plugin for GB Studio 4.x. Adds 56 CC0 creature sprites + four
custom script events under a new "Cinder Creatures" event group.

## Install (works in any GB Studio project, including a blank one)

1. Open your GB Studio project folder in your file explorer.
2. If there is no `plugins/` folder next to your `.gbsproj` file, create one.
3. Copy this whole `cinder-creatures/` folder into `plugins/`.
4. In GB Studio: **File → Reload Project** (or close and reopen).
5. The 56 sprite PNGs will appear in the sprites panel as `creature_01`..`creature_56`.
6. In any script, click "Add Event" → look for the new **Cinder Creatures** group.

That's it — no project import needed.

## Custom events

- **Cinder: random encounter** — picks a random creature ID 1..12 into a variable.
- **Cinder: show name** — shows "A wild FORKLING appeared!" style dialogue based on a creature ID variable.
- **Cinder: set stats** — writes HP/ATK/DEF into three target variables based on a creature ID variable.
- **Cinder: roll damage** — rolls a random damage value into a variable (min..max).

Typical battle setup:
```
$encounterId$ = (Cinder: random encounter)
Cinder: show name from $encounterId$
Cinder: set stats from $encounterId$ -> $foeHp$ $foeAtk$ $foeDef$
... your battle loop ...
Cinder: roll damage 2..8 -> $hit$
$foeHp$ -= $hit$
```

## Species (IDs 1..12)

| ID | Name      | Type  | HP | ATK | DEF |
|----|-----------|-------|----|----|-----|
| 1  | FORKLING  | PROC  | 18 | 6  | 4   |
| 2  | DAEMONET  | PROC  | 22 | 5  | 5   |
| 3  | KERNITE   | CORE  | 30 | 4  | 8   |
| 4  | RECURSE   | LOGIC | 16 | 9  | 3   |
| 5  | MUTEXEL   | LOGIC | 20 | 6  | 6   |
| 6  | BYTEFLY   | DATA  | 12 | 4  | 2   |
| 7  | SEMAFOX   | LOGIC | 19 | 7  | 4   |
| 8  | REGEXEL   | DATA  | 17 | 7  | 3   |
| 9  | SCOPEWVR  | MEM   | 21 | 5  | 6   |
| 10 | ALLOCROC  | MEM   | 28 | 8  | 5   |
| 11 | NULLPUP   | MEM   | 14 | 3  | 2   |
| 12 | CACHEBIT  | DATA  | 16 | 5  | 4   |

The remaining sprites (13..56) are bonus creatures you can name yourself.

## License

Sprites: CC0 (derived from "50+ Monsters Pack 2D" by isaiah658 on
OpenGameArt, recolored to GB DMG palette).
Code & data: MIT.
