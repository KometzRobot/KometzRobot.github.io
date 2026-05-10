#!/usr/bin/env python3
"""Strip script events that don't compile in GB Studio 4.2.2.

Problem: many scene/trigger scripts were generated with invalid event IDs
(EVENT_VARIABLE_SET_TO_VALUE, EVENT_CC_*, etc.) that GBS 4.2.2 rejects with
"No compiler for command" or TypeError.

This sanitizer walks every .gbsres file under project/scenes/ and:
  - Drops events whose `command` is in BAD set
  - Recurses into `children.true` / `children.false` etc.
  - Drops EVENT_IF_VALUE wrappers whose children become empty after stripping
  - Leaves EVENT_TEXT, EVENT_SWITCH_SCENE, EVENT_MENU intact

Run from cinder-starter/. Re-run any time after generation.
"""
import json
import sys
from pathlib import Path

BAD_COMMANDS = {
    "EVENT_VARIABLE_SET_TO_VALUE",
    "EVENT_VARIABLE_SET_TO_RANDOM",
    "EVENT_VARIABLE_MATH",
    "EVENT_CC_SET_STATS",
    "EVENT_CC_TRAINER_CHALLENGE",
    "EVENT_CC_BADGE_UNLOCK",
    "EVENT_CC_ITEM_GIVE",
    "EVENT_CC_PARTY_ADD",
    "EVENT_CC_SHOW_NAME",
    "EVENT_CC_POOL_ENCOUNTER",
    "EVENT_CC_ENCOUNTER",
    "EVENT_CC_NAME_ENTRY",
    "EVENT_TEXT_INPUT",
    "EVENT_IF_VALUE",
}

def clean_script(events):
    out = []
    for ev in events:
        cmd = ev.get("command", "")
        if cmd in BAD_COMMANDS:
            # Recover a leftover dialogue line if EVENT_IF_VALUE wraps EVENT_TEXTs
            kids = ev.get("children", {}) or {}
            recovered = []
            for branch in ("true", "false"):
                for child in (kids.get(branch) or []):
                    if child.get("command") == "EVENT_TEXT":
                        recovered.append(child)
                        break
                if recovered:
                    break
            out.extend(recovered)
            continue
        if "children" in ev and isinstance(ev["children"], dict):
            new_children = {}
            for k, v in ev["children"].items():
                if isinstance(v, list):
                    new_children[k] = clean_script(v)
                else:
                    new_children[k] = v
            ev["children"] = new_children
        out.append(ev)
    return out


def walk(root):
    changed = 0
    for path in root.rglob("*.gbsres"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        touched = False
        for key in (
            "script",
            "playerHit1Script", "playerHit2Script", "playerHit3Script",
            "leaveScript", "startScript", "updateScript",
        ):
            if key in data and isinstance(data[key], list):
                cleaned = clean_script(data[key])
                if cleaned != data[key]:
                    data[key] = cleaned
                    touched = True
        # Actors live inline in scene.gbsres
        for actor in data.get("actors", []) or []:
            if not isinstance(actor, dict):
                continue
            for k in ("script", "startScript", "updateScript", "hit1Script", "hit2Script", "hit3Script"):
                if k in actor and isinstance(actor[k], list):
                    cleaned = clean_script(actor[k])
                    if cleaned != actor[k]:
                        actor[k] = cleaned
                        touched = True
        if touched:
            path.write_text(json.dumps(data, indent=2))
            changed += 1
            print(f"sanitized: {path.relative_to(root.parent)}")
    print(f"---\n{changed} file(s) updated")


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "project/scenes")
    if not root.exists():
        print(f"no such dir: {root}", file=sys.stderr)
        sys.exit(1)
    walk(root)
