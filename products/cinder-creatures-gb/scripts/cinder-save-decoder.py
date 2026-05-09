#!/usr/bin/env python3
"""
Cinder Creatures — GB Studio save -> Cinder companion-app JSON sidecar.

Two paths in:
  1. `--sav PATH` (or default `/CINDER/games/cinder-creatures.sav`) — parse a
     real save battery dump emitted by the ROM. Binary parser is a stub until
     the ROM is built and we have variable offsets from the GB Studio compiler;
     parse_sav still emits the schema with save_present=True so the reader
     wakes up.
  2. `--shim PATH` — read a hand-authored JSON file in the sidecar schema. Used
     for dev so we can exercise companion-app unlocks (first_catch, badges,
     full dex, beat VOID) before a real ROM .sav exists. Strictly validated
     against KNOWN_KEYS so a typo in the shim doesn't silently disable a
     template.

One path out: write `cinder-creatures.json` to wherever `--out` points. Default
target is the AnythingLLM-fork public folder so `/cinder/cinder-creatures.json`
serves it to the React app. Override `--out` for the USB target.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

USB_GAMES_DIR_DEFAULT = "/CINDER/games"
SAVE_NAME = "cinder-creatures.sav"
JSON_NAME = "cinder-creatures.json"

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPANION_PUBLIC_CINDER = REPO_ROOT / "products" / "cinder-anythingllm" / "frontend" / "public" / "cinder"

KNOWN_KEYS = {
    "schema_version", "trainer", "playtime_minutes", "current_scene",
    "party", "dex", "badges", "items", "save_present", "raw_size",
}
KNOWN_DEX_KEYS = {"caught", "seen"}
VALID_BADGES = {"LOGIC", "MEM", "PROC", "DATA", "CORE"}


def empty_save_payload() -> dict:
    return {
        "schema_version": "1.0",
        "trainer": None,
        "playtime_minutes": 0,
        "current_scene": None,
        "party": [],
        "dex": {"caught": [], "seen": []},
        "badges": [],
        "items": {},
        "save_present": False,
    }


def parse_sav(sav_bytes: bytes) -> dict:
    payload = empty_save_payload()
    payload["save_present"] = True
    payload["raw_size"] = len(sav_bytes)
    return payload


def parse_shim(shim_bytes: bytes) -> dict:
    """Validate a hand-authored sidecar shim and merge it onto the empty payload.

    Strict on unknown keys (typos shouldn't silently fail a template gate) and
    on dex/badge value shapes (the React side trusts the schema)."""
    raw = json.loads(shim_bytes)
    if not isinstance(raw, dict):
        raise ValueError("shim must be a JSON object")

    unknown = set(raw.keys()) - KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown keys in shim: {sorted(unknown)}")

    payload = empty_save_payload()
    payload.update(raw)

    if "dex" in raw:
        dex = raw["dex"]
        if not isinstance(dex, dict):
            raise ValueError("dex must be an object")
        unknown_dex = set(dex.keys()) - KNOWN_DEX_KEYS
        if unknown_dex:
            raise ValueError(f"unknown dex keys: {sorted(unknown_dex)}")
        for k in ("caught", "seen"):
            if k in dex and not all(isinstance(x, int) for x in dex[k]):
                raise ValueError(f"dex.{k} must be a list of int creature IDs")

    if "badges" in raw:
        if not isinstance(raw["badges"], list):
            raise ValueError("badges must be a list")
        bad = [b for b in raw["badges"] if b not in VALID_BADGES]
        if bad:
            raise ValueError(f"unknown badges: {bad} (valid: {sorted(VALID_BADGES)})")

    payload["save_present"] = bool(raw.get("save_present", True))
    return payload


def decode(sav_path: Path | None, shim_path: Path | None) -> dict:
    if shim_path is not None:
        if not shim_path.exists():
            raise FileNotFoundError(f"shim not found: {shim_path}")
        return parse_shim(shim_path.read_bytes())
    if sav_path is not None and sav_path.exists():
        return parse_sav(sav_path.read_bytes())
    return empty_save_payload()


def default_out_path() -> Path:
    return COMPANION_PUBLIC_CINDER / JSON_NAME


def main():
    ap = argparse.ArgumentParser(description="Emit Cinder Creatures sidecar JSON")
    ap.add_argument("--sav", default=None, help="path to .sav file (default: <usb>/cinder-creatures.sav)")
    ap.add_argument("--usb", default=None, help="USB games dir (default: /CINDER/games)")
    ap.add_argument("--shim", default=None, help="JSON shim file to use instead of a .sav (dev)")
    ap.add_argument("--out", default=None, help=f"output JSON path (default: {default_out_path()})")
    ap.add_argument("--print", action="store_true", help="print to stdout instead of writing")
    ap.add_argument("--quiet", action="store_true", help="suppress wrote-path message")
    args = ap.parse_args()

    if args.sav and args.shim:
        print("error: pass --sav OR --shim, not both", file=sys.stderr)
        sys.exit(2)

    sav_path: Path | None = None
    if args.shim is None:
        if args.sav:
            sav_path = Path(args.sav)
        else:
            base = Path(args.usb) if args.usb else Path(USB_GAMES_DIR_DEFAULT)
            sav_path = base / SAVE_NAME

    shim_path = Path(args.shim) if args.shim else None
    payload = decode(sav_path, shim_path)
    text = json.dumps(payload, indent=2)

    if args.print:
        print(text)
        return

    out_path = Path(args.out) if args.out else default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    if not args.quiet:
        source = f"shim={shim_path}" if shim_path else f"sav={sav_path}"
        print(f"wrote {out_path} (save_present={payload['save_present']}, {source})")


if __name__ == "__main__":
    main()
