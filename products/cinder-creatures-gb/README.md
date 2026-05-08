# Cinder Creatures — GB Studio Demo

A Game Boy ROM project, built on GB Studio 4.2.

## What's here

- `project.gbsproj` — open this in GB Studio (4.2 or newer)
- `assets/` — sprites, backgrounds, music, tilesets (CC0 from GB Studio's official sample project, plus our 56 Cinder creatures dropped in as `cinder_01.png` through `cinder_56.png`)
- `cc0-creatures-16/` — same 56 creatures, kept separately as the "raw" 16×16 GB-palette ports of `sprites/cinder-creatures/creature_NN.png`

## Open in GB Studio

```
flatpak run dev.gbstudio.gb-studio products/cinder-creatures-gb/project.gbsproj
```

When you open it, GB Studio auto-imports any new PNGs in `assets/sprites/` and generates the `.gbsres` metadata files for them. The 56 `cinder_NN.png` sprites will appear as static fixed-frame sprites you can drop into any scene.

## How the creatures got into GB palette

```
convert creature_NN.png -resize 16x16 -dither FloydSteinberg \
  -remap gb-palette.ppm cinder_NN.png
```

GB palette used: `#0F380F #306230 #8BAC0F #9BBC0F` (classic DMG green).

## Build a ROM

In GB Studio: **Game → Build ROM** (or Build & Run for emulator). Output goes to `build/rom/game.gb`.

## License

The starting scenes/tilesets/music are from GB Studio's MIT-licensed sample project. The 56 creature sprites are CC0 — derived from "50+ Monsters Pack 2D" by isaiah658 on OpenGameArt, recolored to GB palette.
