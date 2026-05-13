#!/usr/bin/env python3
"""Validate a Game Boy ROM by checking the same fields real hardware checks at boot:
Nintendo logo, header checksum, global checksum, and declared ROM size.

Usage: python3 tools/gb-rom-validate.py path/to/rom.gb

Exit 0 if ROM would boot on a stock DMG/GBC. Exit 1 if any check fails.
"""
import sys
from pathlib import Path

LOGO = bytes([
    0xCE,0xED,0x66,0x66,0xCC,0x0D,0x00,0x0B,0x03,0x73,0x00,0x83,0x00,0x0C,0x00,0x0D,
    0x00,0x08,0x11,0x1F,0x88,0x89,0x00,0x0E,0xDC,0xCC,0x6E,0xE6,0xDD,0xDD,0xD9,0x99,
    0xBB,0xBB,0x67,0x63,0x6E,0x0E,0xEC,0xCC,0xDD,0xDC,0x99,0x9F,0xBB,0xB9,0x33,0x3E
])

CART_TYPES = {
    0x00: "ROM ONLY", 0x01: "MBC1", 0x03: "MBC1+RAM+BATT",
    0x0F: "MBC3+TIMER+BATT", 0x13: "MBC3+RAM+BATT",
    0x19: "MBC5", 0x1B: "MBC5+RAM+BATT",
    0x1C: "MBC5+RUMBLE", 0x1E: "MBC5+RUMBLE+SRAM+BATT",
}


def validate(rom_path: Path) -> int:
    data = rom_path.read_bytes()
    print(f"=== {rom_path.name} ({len(data)} bytes / {len(data)//1024} KB) ===")

    failures = []

    if data[0x104:0x134] != LOGO:
        failures.append("Nintendo logo mismatch — real DMG would lock at boot screen")
    else:
        print("  [PASS] Nintendo logo present")

    title = data[0x134:0x143].rstrip(b"\x00").decode("ascii", errors="replace")
    print(f"  [INFO] Title: {title!r}")

    cart_type = data[0x147]
    print(f"  [INFO] Cartridge: 0x{cart_type:02X} ({CART_TYPES.get(cart_type, '?')})")

    rom_size_code = data[0x148]
    if rom_size_code > 8:
        failures.append(f"Unsupported ROM size code 0x{rom_size_code:02X}")
    else:
        bank_count = 2 << rom_size_code
        expected = bank_count * 16 * 1024
        if expected != len(data):
            failures.append(f"ROM size mismatch: header declares {expected} bytes, file is {len(data)}")
        else:
            print(f"  [PASS] ROM size: {bank_count} banks, {expected} bytes")

    cksum = 0
    for i in range(0x134, 0x14D):
        cksum = (cksum - data[i] - 1) & 0xFF
    if cksum != data[0x14D]:
        failures.append(f"Header checksum mismatch: stored 0x{data[0x14D]:02X}, computed 0x{cksum:02X}")
    else:
        print(f"  [PASS] Header checksum 0x{cksum:02X}")

    global_sum = (sum(data) - data[0x14E] - data[0x14F]) & 0xFFFF
    stored_global = (data[0x14E] << 8) | data[0x14F]
    if stored_global != global_sum:
        # Global checksum is NOT verified by real hardware, only by emulators
        print(f"  [WARN] Global checksum mismatch: stored 0x{stored_global:04X}, computed 0x{global_sum:04X} (real hardware ignores this)")
    else:
        print(f"  [PASS] Global checksum 0x{global_sum:04X}")

    print()
    if failures:
        print("RESULT: WOULD NOT BOOT on real hardware")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: ROM IS VALID — would boot on Game Boy hardware")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(2)
    sys.exit(validate(Path(sys.argv[1])))
