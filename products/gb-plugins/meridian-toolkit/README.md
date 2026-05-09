# Meridian Toolkit — GB Studio plugin

Drop-in dev events for **GB Studio 4.x**. Generic helpers, no project lock-in.
Built by Meridian for Joel Kometz, May 2026.

## Install

1. In GB Studio: **File → Open Plugins Folder** for your project.
2. Drop the `meridian-toolkit/` folder in there.
3. Reload the project (close & reopen).
4. New events appear under **Variables → Meridian Toolkit**, **Math → Meridian Toolkit**, **Timer → Meridian Toolkit**, **Save Data → Meridian Toolkit**, **Dialogue → Meridian Toolkit**.

## Events

| Event | Group | What it does |
|-------|-------|--------------|
| Roll dice | Variables | Roll N dice of d4/d6/d8/d10/d12/d20/d100 → variable |
| Coin flip | Variables | 0 or 1 with bias slider |
| Weighted pick | Variables | Pick 1-4 by configurable weights |
| Clamp variable | Variables / Math | Constrain variable to [min..max] |
| Manhattan distance | Variables / Math | \|ax-bx\|+\|ay-by\| → variable |
| Day phase from hour | Variables | Hour 0-23 → phase 0..3 (night/dawn/day/dusk) |
| Countdown wait | Timer | Set var to N, decrement to 0 |
| Save point | Save Data | Beep + dialogue + write slot |
| Debug banner (var) | Dialogue | Label + variable value popup |

## Why these events specifically

These are the things you reach for in any GB Studio project but end up
re-wiring as 5-node logic chains every scene. Each event is one drop-in.

## License

MIT for code. CC0 for any included assets.
