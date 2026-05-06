#!/usr/bin/env python3
"""Detect duplicate systemd unit definitions across system + user scope.

When a service is defined in both /etc/systemd/system/ and ~/.config/systemd/user/,
both attempt to bind the same port and one ends up in a restart-fail loop.
Hit this twice in Loop 9226 (hub-v2 and the-chorus). Run periodically to catch it.

Exit codes:
  0 — no duplicates
  1 — duplicates found (printed to stdout)
"""
import subprocess
import sys
from pathlib import Path

SYSTEM_DIRS = [Path("/etc/systemd/system"), Path("/lib/systemd/system")]
USER_DIRS = [Path.home() / ".config/systemd/user"]


def list_units(dirs):
    units = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.service"):
            if f.is_symlink():
                continue
            units.setdefault(f.name, []).append(str(f))
    return units


def systemctl_state(name, user=False):
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    enabled = subprocess.run(cmd + ["is-enabled", name], capture_output=True, text=True).stdout.strip() or "?"
    active = subprocess.run(cmd + ["is-active", name], capture_output=True, text=True).stdout.strip() or "?"
    return enabled, active


def main():
    sys_units = list_units(SYSTEM_DIRS)
    user_units = list_units(USER_DIRS)

    overlap = sorted(set(sys_units) & set(user_units))
    if not overlap:
        print("OK: no duplicate system+user unit definitions")
        return 0

    risky = []
    for name in overlap:
        s_en, s_act = systemctl_state(name, user=False)
        u_en, u_act = systemctl_state(name, user=True)
        both_enabled = s_en == "enabled" and u_en == "enabled"
        both_active = s_act == "active" and u_act == "active"
        flag = both_enabled or both_active
        if flag:
            risky.append((name, s_en, s_act, u_en, u_act, sys_units[name], user_units[name]))

    print(f"Found {len(overlap)} dual-scope unit file(s); {len(risky)} actively conflicting.\n")
    for name in overlap:
        s_en, s_act = systemctl_state(name, user=False)
        u_en, u_act = systemctl_state(name, user=True)
        marker = "CONFLICT" if (s_en == "enabled" and u_en == "enabled") or (s_act == "active" and u_act == "active") else "ok"
        print(f"  [{marker}] {name}")
        print(f"    system: enabled={s_en}, active={s_act}  ({sys_units[name][0]})")
        print(f"    user:   enabled={u_en}, active={u_act}  ({user_units[name][0]})")

    if risky:
        print("\nFix: pick one scope, disable the other:")
        print("  sudo systemctl disable <name>          # remove system-level")
        print("  systemctl --user disable <name>        # remove user-level")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
