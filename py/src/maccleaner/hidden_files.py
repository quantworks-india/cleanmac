"""Hidden files toggle — show/hide hidden files in Finder."""

from __future__ import annotations

import subprocess


def _toggle(value: bool) -> int:
    r = subprocess.run(
        [
            "defaults",
            "write",
            "com.apple.finder",
            "AppleShowAllFiles",
            "-bool",
            str(value).lower(),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        print(f"defaults write failed: {r.stderr.strip()}")
        return 1
    kr = subprocess.run(["killall", "Finder"], capture_output=True, text=True, check=False)
    if kr.returncode != 0:
        print(f"killall Finder failed: {kr.stderr.strip()}")
        return 1
    state = "shown" if value else "hidden"
    print(f"Hidden files are now {state} in Finder.")
    return 0


def run(args) -> int:
    if args.action == "show":
        return _toggle(True)
    if args.action == "hide":
        return _toggle(False)
    return 2
