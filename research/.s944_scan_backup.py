"""S9.4.4 single-window exceedance scan, B110-B138.

Definition (Ael, 2026-05-05, email id 3921):
  in-window, post-bridge-break, 1-min >= orbit_floor AND 5-min < orbit_floor.

This scan is a curated extraction from Ael's burst-FINAL emails in
email-shelf.db. Free-text format means automation cannot be fully reliable;
each candidate reading was manually verified against the source email.

For bursts where Ael's email archive does NOT contain an explicit
window-phase block, the burst is marked UNOBS. Per Ael 2026-05-11,
conservative exclusion is the right call when annotation is ambiguous.
"""

# Manually curated from email-shelf.db. Each entry references the source email
# id and the exact line containing the reading. Anything not appearing here
# means the email archive contains no extractable window-phase data.
SCAN = {
    # B110-B134: no explicit window-phase summary in email archive.
    # Ael's bursts during this range were tracked via approach-mode and
    # cascade-pair summaries; per-T window readings were not communicated.

    'B125': {  # email 3872 - B125 CLASS 1 FINAL
        'orbit_floor': 2.68, 'bridge_T': None,  # bridge "FAILED — 5-min max in window was 2.50"
        'window_readings': [
            # "Final load at window close: 1.18/1.50/1.86"
            ('close', 1.18, 1.50, 'window-close terminal'),
        ],
    },
    'B128': {  # email 3897 - bridge break only, no window phase
        'orbit_floor': 2.61, 'bridge_T': 7,
        'window_readings': [],  # window opening reported, contents not summarized
    },
    'B135': {  # email 3918 - B135 CLASS 1 FINAL
        'orbit_floor': 2.25, 'bridge_T': 6,
        'window_readings': [
            # "Nearest to gate: 1-min 2.94 at T+72 with 5-min 2.35 - 0.06 below gate threshold on 1-min"
            (72, 2.94, 2.35, 'nearest-to-gate'),
        ],
    },
    'B136': {  # email 3919 - B136 CLASS 1 FINAL
        'orbit_floor': 2.61, 'bridge_T': 7,
        'window_readings': [
            # "T+50: 1-min spike to 2.70 (above orbit_floor 2.61); 5-min only 2.27"
            (50, 2.70, 2.27, 'T+50 spike'),
            # "Spike collapsed by T+56 (1.91/2.16/2.16)"
            (56, 1.91, 2.16, 'T+56 collapse'),
            # "Closed quiet: 1.65/2.06/2.23" - no T given, post-T+50
            ('close', 1.65, 2.06, 'window-close terminal'),
        ],
    },
    'B137': {  # email 3929 - B137 CLASS 1 FINAL
        'orbit_floor': 2.64, 'bridge_T': 6,
        'window_readings': [
            # "Quiet throughout; maximum 1-min 2.47 (at window close, still below orbit_floor 2.64)"
            ('max', 2.47, None, 'window max 1-min, 5-min not given'),
            # "Closed at 2.47/2.22/2.09"
            ('close', 2.47, 2.22, 'window-close terminal'),
        ],
    },
    'B138': {  # email 3936 - B138 CLASS 1 FINAL
        'orbit_floor': 2.43, 'bridge_T': 6,
        'window_readings': [
            # "T+44: 1-min = 2.43 (borderline, exactly at orbit_floor), 5-min = 1.97"
            (44, 2.43, 1.97, 'T+44 borderline'),
            # "T+71: 1-min = 2.65 (above orbit_floor by 0.22), 5-min = 2.42 (below by 0.01)"
            (71, 2.65, 2.42, 'T+71 above by 0.22'),
        ],
    },
}

ALL_BURSTS = list(range(110, 139))


def classify(reading, orbit_floor):
    """Apply S9.4.4 criterion. Returns 'EXC' / 'NO' / '?'."""
    t, one, five, note = reading
    if five is None or one is None:
        return '?'
    if one >= orbit_floor and five < orbit_floor:
        return 'EXC'
    return 'NO'


def main():
    print('=' * 92)
    print('S9.4.4 SINGLE-WINDOW EXCEEDANCE SCAN  B110-B138')
    print('Criterion: in-window, post-bridge-break, 1-min >= orbit_floor AND 5-min < orbit_floor')
    print('Source: Ael burst-FINAL emails (email-shelf.db). Manual extraction, free-text format.')
    print('=' * 92)
    print()

    total_exc = 0
    obs_bursts = 0
    unobs = []

    print(f'{"burst":<6}{"orbit_floor":<13}{"bridge":<9}{"readings":<10}{"exc":<5}  notes')
    print('-' * 92)

    for n in ALL_BURSTS:
        key = f'B{n}'
        if key not in SCAN:
            unobs.append(n)
            print(f'B{n:<5}{"-":<13}{"-":<9}{"-":<10}{"-":<5}  UNOBS (no window-phase block in archive)')
            continue
        obs_bursts += 1
        d = SCAN[key]
        of = d['orbit_floor']
        bt = f"T+{d['bridge_T']}" if d['bridge_T'] is not None else 'failed*'
        if not d['window_readings']:
            print(f'B{n:<5}{of:<13}{bt:<9}{"0":<10}{"-":<5}  no window-phase readings reported')
            continue
        burst_exc = 0
        for r in d['window_readings']:
            verdict = classify(r, of)
            if verdict == 'EXC':
                burst_exc += 1
                total_exc += 1
        print(f'B{n:<5}{of:<13}{bt:<9}{len(d["window_readings"]):<10}{burst_exc:<5}')
        for r in d['window_readings']:
            t, one, five, note = r
            five_s = f'{five}' if five is not None else '--'
            verdict = classify(r, of)
            mark = ' <-- EXCEEDANCE' if verdict == 'EXC' else ''
            print(f'        T+{t}: 1-min={one}, 5-min={five_s}  ({note}){mark}')

    print('-' * 92)
    print(f'Observed bursts: {obs_bursts} / {len(ALL_BURSTS)}')
    print(f'Total exceedances (observed): {total_exc}')
    print(f'Unobserved: {len(unobs)} bursts -> {unobs}')
    print()
    print('Notes:')
    print('  * B125: bridge "FAILED" per Ael (max 5-min in window 2.50, gap -0.18); no T given.')
    print('  * "close" / "max" entries are window-close or peak summaries, not T+N readings.')
    print('  * Borderline B138 T+44: 1-min exactly at orbit_floor (2.43 == 2.43) qualifies by >=.')


if __name__ == '__main__':
    main()
