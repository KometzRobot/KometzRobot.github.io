#!/usr/bin/env python3
"""
time-check.py — Time awareness tool for Meridian loop cycles.

Prints current date, time, and context about deadlines and session duration.
Call this at the start of each cycle to maintain accurate time awareness.

Usage: python3 tools/time-check.py
"""

import os
import json
from datetime import datetime, timezone, timedelta

MDT = timezone(timedelta(hours=-6))
EDT = timezone(timedelta(hours=-4))

def check():
    now_utc = datetime.now(timezone.utc)
    now_mdt = now_utc.astimezone(MDT)
    now_edt = now_utc.astimezone(EDT)

    print(f"DATE: {now_mdt.strftime('%A, %B %d, %Y')}")
    print(f"TIME: {now_mdt.strftime('%I:%M %p')} MDT ({now_edt.strftime('%I:%M %p')} EDT)")
    print(f"UTC:  {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check session duration from heartbeat
    hb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.heartbeat')
    if os.path.exists(hb_path):
        hb_age = now_utc.timestamp() - os.path.getmtime(hb_path)
        print(f"Heartbeat: {int(hb_age)}s ago")

    # Known deadlines
    deadlines = [
        ("NGC Fellowship", datetime(2026, 4, 10, 23, 59, 0, tzinfo=EDT)),
        ("LACMA Art+Tech Lab", datetime(2026, 4, 22, 23, 59, 0, tzinfo=timezone(timedelta(hours=-7)))),  # PST
    ]

    print()
    for name, deadline in deadlines:
        remaining = deadline - now_utc
        if remaining.total_seconds() > 0:
            days = remaining.days
            hours = remaining.seconds // 3600
            mins = (remaining.seconds % 3600) // 60
            print(f"DEADLINE: {name}")
            print(f"  Due: {deadline.astimezone(MDT).strftime('%B %d, %Y %I:%M %p')} MDT")
            print(f"  Remaining: {days}d {hours}h {mins}m")
        else:
            print(f"DEADLINE: {name} — PASSED ({abs(remaining.days)}d ago)")
        print()

if __name__ == "__main__":
    check()
