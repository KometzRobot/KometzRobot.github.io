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

- **Cinder: random encounter** — picks a random creature ID in `min..max` (default 1..12; raise max to 56 for full roster) into a variable.
- **Cinder: show name** — shows "A wild FORKLING appeared!" style dialogue based on a creature ID variable.
- **Cinder: set stats** — writes HP/ATK/DEF into three target variables based on a creature ID variable.
- **Cinder: roll damage** — rolls a random damage value into a variable (min..max).

Typical battle setup:
```
$encounterId$ = (Cinder: random encounter 1..12)
Cinder: show name from $encounterId$
Cinder: set stats from $encounterId$ -> $foeHp$ $foeAtk$ $foeDef$
... your battle loop ...
Cinder: roll damage 2..8 -> $hit$
$foeHp$ -= $hit$
```

## Species roster (1..56, all named)

Tier 1 — starter pool (default random encounter range):

| ID | Name      | Type  | HP | ATK | DEF |
|----|-----------|-------|----|-----|-----|
| 1  | FORKLING  | PROC  | 18 | 6   | 4   |
| 2  | DAEMONET  | PROC  | 22 | 5   | 5   |
| 3  | KERNITE   | CORE  | 30 | 4   | 8   |
| 4  | RECURSE   | LOGIC | 16 | 9   | 3   |
| 5  | MUTEXEL   | LOGIC | 20 | 6   | 6   |
| 6  | BYTEFLY   | DATA  | 12 | 4   | 2   |
| 7  | SEMAFOX   | LOGIC | 19 | 7   | 4   |
| 8  | REGEXEL   | DATA  | 17 | 7   | 3   |
| 9  | SCOPEWVR  | MEM   | 21 | 5   | 6   |
| 10 | ALLOCROC  | MEM   | 28 | 8   | 5   |
| 11 | NULLPUP   | MEM   | 14 | 3   | 2   |
| 12 | CACHEBIT  | DATA  | 16 | 5   | 4   |

Tier 2 — extended roster:

| ID | Name      | Type  | HP | ATK | DEF |
|----|-----------|-------|----|-----|-----|
| 13 | THREDLE   | PROC  | 17 | 6   | 3   |
| 14 | ZYBORG    | PROC  | 24 | 6   | 4   |
| 15 | PIDGON    | PROC  | 19 | 5   | 4   |
| 16 | SIGNAUR   | PROC  | 22 | 7   | 3   |
| 17 | NICEKIT   | PROC  | 14 | 5   | 3   |
| 18 | SCHEDOG   | PROC  | 20 | 6   | 5   |
| 19 | ARMOTE    | CORE  | 28 | 5   | 7   |
| 20 | RISKIT    | CORE  | 25 | 5   | 7   |
| 21 | CISCOTL   | CORE  | 32 | 4   | 9   |
| 22 | PIPELYNX  | CORE  | 26 | 6   | 6   |
| 23 | CYCLOOM   | CORE  | 30 | 5   | 8   |
| 24 | NANDORE   | LOGIC | 18 | 8   | 4   |
| 25 | NORWEN    | LOGIC | 17 | 7   | 5   |
| 26 | XORHARE   | LOGIC | 16 | 9   | 3   |
| 27 | ANDOWL    | LOGIC | 19 | 6   | 5   |
| 28 | BOOLEM    | LOGIC | 18 | 7   | 4   |
| 29 | IFFROG    | LOGIC | 17 | 6   | 4   |
| 30 | ELSEEL    | LOGIC | 19 | 7   | 3   |
| 31 | SWITCRAB  | LOGIC | 21 | 6   | 5   |
| 32 | JSONIA    | DATA  | 14 | 5   | 3   |
| 33 | CSVOLE    | DATA  | 13 | 4   | 2   |
| 34 | YAMOLE    | DATA  | 15 | 4   | 3   |
| 35 | TOMLT     | DATA  | 14 | 5   | 3   |
| 36 | INTGAR    | DATA  | 18 | 5   | 4   |
| 37 | FLOATFIN  | DATA  | 13 | 6   | 2   |
| 38 | STRTERM   | DATA  | 16 | 5   | 3   |
| 39 | BOOLBIRD  | DATA  | 12 | 4   | 2   |
| 40 | STACKAT   | MEM   | 22 | 5   | 6   |
| 41 | HEAPYR    | MEM   | 27 | 4   | 8   |
| 42 | MALLOCK   | MEM   | 24 | 7   | 5   |
| 43 | FREEDA    | MEM   | 18 | 5   | 4   |
| 44 | PAGYL     | MEM   | 20 | 4   | 6   |
| 45 | CACHEY    | MEM   | 19 | 5   | 5   |
| 46 | BUFFROG   | MEM   | 22 | 5   | 6   |
| 47 | LINKAR    | DATA  | 15 | 6   | 3   |
| 48 | NODILLO   | DATA  | 18 | 5   | 5   |
| 49 | TREEKIN   | DATA  | 17 | 6   | 4   |
| 50 | GRAFTLE   | DATA  | 19 | 5   | 5   |
| 51 | HASHARE   | DATA  | 14 | 8   | 2   |
| 52 | QUEUL     | MEM   | 18 | 5   | 5   |
| 53 | DEQUEEL   | MEM   | 19 | 5   | 5   |
| 54 | SETTER    | LOGIC | 16 | 6   | 4   |
| 55 | ITERATX   | LOGIC | 17 | 7   | 4   |
| 56 | PARSEY    | LOGIC | 18 | 7   | 3   |

Boss: **CINDER** (CORE, HP 80 / ATK 12 / DEF 8) — "the system itself, finally turned around."

## License

Sprites: CC0 (derived from "50+ Monsters Pack 2D" by isaiah658 on
OpenGameArt, recolored to GB DMG palette).
Code & data: MIT.
