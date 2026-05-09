# GB Studio Asset Workflow

Three tools, three steps. Run from repo root.

## 1. Curate (Loop 9706)
`python3 scripts/gb-asset-curator.py`

Scans `~/Downloads`, categorizes archives into `asset-library/<cat>/` symlinks,
extracts detected GB Studio plugins into `extracted/`. Idempotent.

## 2. Extract (Loop 9707)
`python3 scripts/gb-asset-extractor.py`

Unpacks every non-plugin zip/rar into `<cat>/_unpacked/<pack>/` so PNGs and
sound files are browsable as files instead of archives. Skips packs already
unpacked. Some `.rar` archives use compression methods 7z 23.x can't read —
those fail loudly and are listed in `EXTRACTOR.json`.

`python3 scripts/gb-asset-extractor.py --list` — show every unpacked pack with
file counts, grouped by category. Use this to pick names for step 3.

## 3. Drop into a project (Loop 9707)
`scripts/gb-pack-copy.sh /path/to/your-gbsproj-dir <pack-name> [<pack-name>...]`

Copies `<cat>/_unpacked/<pack>/` into `<project>/assets/<gb-cat>/<pack>/`. GB
Studio shows nested folders inside `assets/` as collapsible groups, so a pack
stays organized rather than dumping 200 PNGs in a flat list. Re-open the
project to refresh. Whole-category shortcuts:

```
scripts/gb-pack-copy.sh ~/MyGame --all-fonts
scripts/gb-pack-copy.sh ~/MyGame --all-ui
```

## Plugins separately
`scripts/cinder-gb-import.sh /path/to/your-gbsproj-dir`

Drops the cinder-creatures plugin and every detected community plugin into
`<project>/plugins/`. This is plugins-only — assets go through the pack-copy
script above.

## Disk note
`_unpacked/` directories are gitignored (third-party content). Sprite packs
like `PokemanTCGAA` and `TalesOfFantAsia_ND-AA` unpack to ~700MB each (RPG
Maker AI generated combinatorial frames). They're useful as raw material but
not GB-Studio-ready out of the box — most need palette reduction first.
