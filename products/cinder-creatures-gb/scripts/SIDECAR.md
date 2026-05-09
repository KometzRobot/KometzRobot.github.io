# Cinder Creatures save sidecar

The companion-app Journal/Codex/Achievements pages all read
`/cinder/cinder-creatures.json` from the AnythingLLM-fork frontend. That JSON
is the bridge between the GB ROM save and the React app. Without it, every
unlock template stays locked.

`cinder-save-decoder.py` produces that JSON from one of two sources:

- **Real save**: pass `--sav <path>` (or `--usb <dir>` to use the default
  `<dir>/cinder-creatures.sav`). Binary parser is currently a stub — it sets
  `save_present=true` and `raw_size`, nothing more, until the ROM is built and
  we have variable offsets. Fine for wiring tests; not for live play yet.
- **Shim** (dev): pass `--shim <path>` pointing at a hand-authored JSON file
  that follows the sidecar schema. Use this to exercise unlock templates
  before a real ROM exists.

Six sample shims live in `samples/`:

| File                              | What it exercises                                 |
|-----------------------------------|---------------------------------------------------|
| `sidecar-shim-empty.json`         | No save — every template should stay locked       |
| `sidecar-shim-first-catch.json`   | `dex.caught.length == 1` — first-catch template   |
| `sidecar-shim-first-badge.json`   | One LOGIC badge — earns ARCHIVIST EOS persona     |
| `sidecar-shim-ten-caught.json`    | Ten caught — Vault drop zone on Companion Journal |
| `sidecar-shim-all-badges.json`    | All 5 badges + 20 caught — VESSEL chat mode       |
| `sidecar-shim-mid-game.json`      | Two badges + four caught — multiple unlocks       |

## Quick wire-up

```
# unlock the first-catch journal template in the running dev companion app
python3 products/cinder-creatures-gb/scripts/cinder-save-decoder.py \
    --shim products/cinder-creatures-gb/samples/sidecar-shim-first-catch.json
```

Default `--out` is the AnythingLLM-fork public folder
(`products/cinder-anythingllm/frontend/public/cinder/cinder-creatures.json`),
which the React frontend serves at `/cinder/cinder-creatures.json`. The file
is gitignored so dev save state doesn't follow the branch around.

To clear the sidecar and re-lock everything:
```
python3 products/cinder-creatures-gb/scripts/cinder-save-decoder.py \
    --shim products/cinder-creatures-gb/samples/sidecar-shim-empty.json
```

To target the USB directly when a real save exists:
```
python3 products/cinder-creatures-gb/scripts/cinder-save-decoder.py \
    --usb /CINDER/games --out /CINDER/games/cinder-creatures.json
```

## Schema

```json
{
  "schema_version": "1.0",
  "trainer": "JOEL",
  "playtime_minutes": 124,
  "current_scene": "GYM_PROC",
  "party": [{"id": 4, "name": "RECURSE", "level": 22, "hp": 51, "max_hp": 58, "moves": ["TACKLE"]}],
  "dex": {"caught": [4, 6, 11], "seen": [4, 6, 11, 19, 23]},
  "badges": ["LOGIC", "MEM"],
  "items": {"POTION": 3},
  "save_present": true
}
```

Validators in `parse_shim`:

- Unknown top-level keys → error (typo guard against silent template gating).
- `dex.caught` / `dex.seen` must be arrays of ints (creature IDs).
- `badges` must be a subset of `{LOGIC, MEM, PROC, DATA, CORE}`.

## Roadmap

- Replace `parse_sav` stub with real binary parser once the ROM is built and
  GB Studio compiler emits variable offsets to `build/<name>/build/Sav/data.h`.
- Add a watcher service so a USB mount auto-emits the sidecar every 30s
  (the design doc's intent).
