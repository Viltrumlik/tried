#!/usr/bin/env python3
"""SessionStart hook: show what was already tried, before any work starts.

A session begins with no memory of the last one. This puts the recent dead
ends in front of the agent immediately, so the first idea it reaches for is
not one that was already ruled out.

Anything unexpected stays silent. A hook that fails must not be the reason
a session starts badly.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRIED = os.path.join(HERE, "tried.py")
LIMIT = int(os.environ.get("TRIED_HOOK_LIMIT", "5"))
TIMEOUT = 10


def quiet():
    sys.exit(0)


def main():
    if os.environ.get("TRIED_HOOK_DISABLE") or not os.path.exists(TRIED):
        quiet()
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        quiet()
    if not isinstance(payload, dict):
        quiet()

    try:
        done = subprocess.run(
            [sys.executable, TRIED, "list", "-n", str(LIMIT), "--failed", "--json"],
            cwd=payload.get("cwd") or None, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, timeout=TIMEOUT)
        entries = json.loads(done.stdout).get("entries") or []
    except (OSError, ValueError, subprocess.SubprocessError):
        quiet()
    if not entries:
        quiet()

    lines = ["Approaches already tried in this repo and abandoned. Do not "
             "repeat them without saying why this time is different. "
             "Run `tried check \"<approach>\"` before starting a new one."]
    for entry in entries:
        line = "- %s" % entry.get("what", "")
        if entry.get("because"):
            line += " — failed: %s" % entry["because"]
        lines.append(line)

    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
