#!/usr/bin/env python3
"""
Cinder Creatures — GB Studio save -> Cinder companion-app JSON decoder (stub).

Reads /CINDER/games/cinder-creatures.sav (32KB SRAM dump from emulator/cart) and
emits /CINDER/games/cinder-creatures.json that the AnythingLLM-fork sidecar
consumes to render the JOURNAL tab.

The full save format depends on how the GB ROM lays out variables. This stub
defines the schema and a no-rom fallback so the companion app can render an
empty journal pre-game. Real binary parser ships once the ROM is built and we
can read the actual variable offsets from the GB Studio compiler output.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

USB_GAMES_DIR_DEFAULT = "/CINDER/games"
SAVE_NAME = "cinder-creatures.sav"
JSON_NAME = "cinder-creatures.json"

EMPTY_DEX = {"caught": [], "seen": []}
EMPTY_PARTY: list = []


def empty_save_payload() -> dict:
    """Schema returned when no save exists yet — companion app renders blank journal."""
    return {
        "schema_version": "1.0",
        "trainer": None,
        "playtime_minutes": 0,
        "current_scene": None,
        "party": EMPTY_PARTY,
        "dex": EMPTY_DEX,
        "badges": [],
        "items": {},
        "save_present": False,
    }


def parse_sav(sav_bytes: bytes) -> dict:
    """Parse a GB Studio 4 save battery dump.

    Real implementation (TODO once ROM built):
      - Read variable region using offsets emitted by GB Studio compiler
        (build/<name>/build/Sav/data.h) into a dict.
      - Map vCC_PARTY_*, vCC_DEX_*, vCC_BADGE_* into the schema.

    Stub: returns empty payload with save_present=True so we can wire up the
    companion-app reader without blocking on the binary format.
    """
    payload = empty_save_payload()
    payload["save_present"] = True
    payload["raw_size"] = len(sav_bytes)
    return payload


def decode(usb_root: str | None = None) -> dict:
    base = Path(usb_root) if usb_root else Path(USB_GAMES_DIR_DEFAULT)
    sav_path = base / SAVE_NAME
    if sav_path.exists():
        return parse_sav(sav_path.read_bytes())
    return empty_save_payload()


def main():
    ap = argparse.ArgumentParser(description="Decode Cinder Creatures GB save")
    ap.add_argument("--usb", default=None, help="USB games dir (default: /CINDER/games)")
    ap.add_argument("--out", default=None, help="Output JSON path (default: <usb>/cinder-creatures.json)")
    ap.add_argument("--print", action="store_true", help="Print to stdout instead of writing")
    args = ap.parse_args()

    payload = decode(args.usb)

    text = json.dumps(payload, indent=2)
    if args.print:
        print(text)
        return

    out_path = Path(args.out) if args.out else (
        Path(args.usb if args.usb else USB_GAMES_DIR_DEFAULT) / JSON_NAME
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"wrote {out_path} (save_present={payload['save_present']})")


if __name__ == "__main__":
    main()
