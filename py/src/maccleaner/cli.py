"""argparse dispatcher for maccleaner subcommands.

Global flags: --dry-run (default) and --commit (explicit opt-in to delete).
Subcommands: app, dup, disk, mem, hidden.
"""

from __future__ import annotations

import argparse
import time

from maccleaner import __version__
from maccleaner.core import LOG_DIR, Auditor, Deleter, Reporter, Sudo

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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON events to stdout (one per line).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print debug-level details (file-by-file progress, counters).",
    )
    sub = parser.add_subparsers(dest="tool", required=True)

    # ── app ─────────────────────────────────────────────────────────
    app = sub.add_parser("app", help="App Cleaner & Uninstaller")
    app_sub = app.add_subparsers(dest="app_cmd", required=True)
    app_sub.add_parser("list", help="List installed apps with bundle id + size")
    rem = app_sub.add_parser("remove", help="Remove an app and its leftovers")
    rem.add_argument("app", help="App name or bundle id")
    rem.add_argument("--force", action="store_true", help="Allow short/dangerous names")
    uni = app_sub.add_parser("uninstall", help="Deep uninstall: app + leftovers + launch agents (interactive picker)")
    uni.add_argument("--name", help="App name or bundle id (skip interactive picker)")
    uni.add_argument("--yes", action="store_true", help="Skip confirmation prompts (with --commit)")
    uni.add_argument("--force", action="store_true", help="Allow short/dangerous names")
    rst = app_sub.add_parser("reset", help="Reset app settings (keeps app)")
    rst.add_argument("app", help="App name or bundle id")
    st = app_sub.add_parser("startup", help="Manage startup programs")
    st.add_argument("action", choices=["list", "disable"])
    st.add_argument("label", nargs="?", help="LaunchAgent label to disable")
    st.add_argument("--orphans-only", action="store_true", help="Show only orphaned items (agents from uninstalled apps)")
    orp = app_sub.add_parser("orphans", help="List/purge orphaned background agents from uninstalled apps")
    orp_sub = orp.add_subparsers(dest="orphans_action", required=True)
    orp_sub.add_parser("list", help="List orphaned LaunchAgents/LaunchDaemons (dry)")
    pp = orp_sub.add_parser("purge", help="Bootout + quarantine orphaned launch items")
    pp.add_argument("--yes", action="store_true", help="Skip per-item confirmation (only used with --commit)")
    bba = app_sub.add_parser("bba", help="Background App Activity: items sfltool dumpbtm reports as orphaned")
    bba_sub = bba.add_subparsers(dest="bba_action", required=True)
    bba_sub.add_parser("list", help="List BAA items whose app/daemon is uninstalled (dry)")
    pb = bba_sub.add_parser("purge", help="Bootout + quarantine BAA orphans")
    pb.add_argument("--yes", action="store_true", help="Skip per-item confirmation (only used with --commit)")
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
    reporter = Reporter(json_mode=args.json, verbose=args.verbose)

    # Validate sudo once up front when committing. This means at most ONE
    # password prompt for the entire invocation regardless of how many
    # sub-commands end up touching /Library. The stamp lasts ~5 min by default.
    if args.commit and _needs_sudo(args):
        sudo.ensure()

    try:
        if args.tool == "app":
            return _run_app(args, deleter, sudo, reporter)
        if args.tool == "dup":
            return _run_dup(args, deleter, reporter)
        if args.tool == "disk":
            return _run_disk(args, reporter)
        if args.tool == "mem":
            return _run_mem(args, sudo, reporter)
        if args.tool == "hidden":
            return _run_hidden(args, reporter)
        return 2
    finally:
        auditor.close()


def _needs_sudo(args) -> bool:
    """True if this invocation may touch system-scope paths (LaunchDaemons,
    PrivilegedHelperTools, /Library state, etc.) — i.e. needs sudo at least
    once during execution.
    """
    if args.tool == "mem":
        return args.mem_cmd == "free"
    if args.tool == "app":
        # Any app command that may remove system-scope items.
        if getattr(args, "app_cmd", None) in ("remove", "startup", "orphans", "bba"):
            return True
    return False


def _run_app(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    from maccleaner import app_uninstaller

    return app_uninstaller.run(args, deleter, sudo, reporter)


def _run_dup(args, deleter: Deleter, reporter: Reporter) -> int:
    from maccleaner import duplicates

    return duplicates.run(args, deleter, reporter)


def _run_disk(args, reporter: Reporter) -> int:
    from maccleaner import disk_analyzer

    return disk_analyzer.run(args, reporter)


def _run_mem(args, sudo: Sudo, reporter: Reporter) -> int:
    from maccleaner import memory

    return memory.run(args, sudo, reporter)


def _run_hidden(args, reporter: Reporter) -> int:
    from maccleaner import hidden_files

    return hidden_files.run(args, reporter)


if __name__ == "__main__":
    raise SystemExit(main())
