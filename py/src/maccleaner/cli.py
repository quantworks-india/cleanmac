"""argparse dispatcher for maccleaner subcommands.

Global flags: --dry-run (default) and --commit (explicit opt-in to delete).
Subcommands: app, dup, disk, mem, hidden.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from maccleaner import __version__
from maccleaner.core import AUDIT_DIR, LOG_DIR, Auditor, Deleter, Sudo

RUN_ID = time.strftime("%Y%m%d-%H%M%S")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleanmac",
        description="Free CLI replacement for MacCleaner Pro.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview only, delete nothing (default).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually delete. Without this, nothing is removed.",
    )
    sub = parser.add_subparsers(dest="tool", required=True)

    # ── app ─────────────────────────────────────────────────────────
    app = sub.add_parser("app", help="App Cleaner & Uninstaller")
    app_sub = app.add_subparsers(dest="app_cmd", required=True)
    app_sub.add_parser("list", help="List installed apps with bundle id + size")
    rem = app_sub.add_parser("remove", help="Remove an app and its leftovers")
    rem.add_argument("app", help="App name or bundle id")
    rem.add_argument("--force", action="store_true", help="Allow short/dangerous names")
    rst = app_sub.add_parser("reset", help="Reset app settings (keeps app)")
    rst.add_argument("app", help="App name or bundle id")
    st = app_sub.add_parser("startup", help="Manage startup programs")
    st.add_argument("action", choices=["list", "disable"])
    st.add_argument("label", nargs="?", help="LaunchAgent label to disable")
    app_sub.add_parser("extensions", help="List browser extensions")
    app_sub.add_parser("update", help="Check for outdated apps (mas/brew)")

    # ── dup ─────────────────────────────────────────────────────────
    dup = sub.add_parser("dup", help="Duplicate File Finder")
    dup_sub = dup.add_subparsers(dest="dup_cmd", required=True)
    sc = dup_sub.add_parser("scan", help="Find duplicate files")
    sc.add_argument("dir")
    sc.add_argument("--min-size", default="1M", help="Minimum file size (default 1M)")
    sc.add_argument("--hash", default="sha256", choices=["sha256", "md5"])
    sp = dup_sub.add_parser("similar-photos", help="Find similar photos")
    sp.add_argument("dir", help="Directory to scan")
    mf = dup_sub.add_parser("merge-folders", help="Merge two folders")
    mf.add_argument("a")
    mf.add_argument("b")

    # ── disk ────────────────────────────────────────────────────────
    disk = sub.add_parser("disk", help="Disk Space Analyzer")
    disk_sub = disk.add_subparsers(dest="disk_cmd", required=True)
    ds = disk_sub.add_parser("scan", help="Scan directory sizes")
    ds.add_argument("dir")
    disk_sub.add_parser("top", help="Top 25 largest files/folders")
    disk_sub.add_parser("summary", help="Top-level directory sizes")
    disk_sub.add_parser("system-data", help="Break down system data")
    rep = disk_sub.add_parser("report", help="Generate HTML treemap report")
    rep.add_argument("dir")
    rep.add_argument("--out", default="disk-report.html")

    # ── mem ─────────────────────────────────────────────────────────
    mem = sub.add_parser("mem", help="Memory Cleaner")
    mem_sub = mem.add_subparsers(dest="mem_cmd", required=True)
    mem_sub.add_parser("free", help="Purge inactive RAM (sudo)")
    mem_sub.add_parser("heavy", help="List top CPU/RAM consumers")

    # ── hidden ──────────────────────────────────────────────────────
    hidden = sub.add_parser("hidden", help="Toggle hidden files in Finder")
    hidden.add_argument("action", choices=["show", "hide"])

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    mode = "live" if args.commit else "dry-run"
    auditor = Auditor(RUN_ID, mode=mode)
    deleter = Deleter(auditor, commit=args.commit)
    sudo = Sudo()

    try:
        if args.tool == "app":
            return _run_app(args, deleter, sudo)
        if args.tool == "dup":
            return _run_dup(args, deleter)
        if args.tool == "disk":
            return _run_disk(args)
        if args.tool == "mem":
            return _run_mem(args, sudo)
        if args.tool == "hidden":
            return _run_hidden(args)
        return 2
    finally:
        auditor.close()


def _run_app(args, deleter: Deleter, sudo: Sudo) -> int:
    from maccleaner import app_uninstaller

    return app_uninstaller.run(args, deleter, sudo)


def _run_dup(args, deleter: Deleter) -> int:
    from maccleaner import duplicates

    return duplicates.run(args, deleter)


def _run_disk(args) -> int:
    from maccleaner import disk_analyzer

    return disk_analyzer.run(args)


def _run_mem(args, sudo: Sudo) -> int:
    from maccleaner import memory

    return memory.run(args, sudo)


def _run_hidden(args) -> int:
    from maccleaner import hidden_files

    return hidden_files.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
