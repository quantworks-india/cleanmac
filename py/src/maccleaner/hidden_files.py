"""Hidden files toggle — show/hide hidden files in Finder."""

from __future__ import annotations

import subprocess

from maccleaner.core import Reporter


def _toggle(value: bool, reporter: Reporter) -> int:
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
        reporter.error("defaults_write_failed", stderr=r.stderr.strip())
        return 1
    kr = subprocess.run(
        ["killall", "Finder"], capture_output=True, text=True, check=False
    )
    if kr.returncode != 0:
        reporter.error("killall_finder_failed", stderr=kr.stderr.strip())
        return 1
    state = "shown" if value else "hidden"
    reporter.info("hidden_files_toggled", state=state)
    return 0


def run(args, reporter: Reporter) -> int:
    if args.action == "show":
        return _toggle(True, reporter)
    if args.action == "hide":
        return _toggle(False, reporter)
    return 2
