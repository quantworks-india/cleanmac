"""Top-level `cleanmac uninstall` — the one product surface for this pass.

Flow: resolve the target -> print the full plan -> one `Delete all of
this? [y/N]`. Yes sets commit on the deleter and removes the bundle
(if still present) plus every leftover, owned launch item, and BAA
item. No / empty deletes nothing.
"""

from __future__ import annotations

import sys
from typing import Any

from maccleaner.core import Deleter, Reporter, Sudo, confirm


def confirm_yes(prompt: str) -> bool:
    """One yes/no gate for the whole uninstall."""
    return confirm(prompt)


def _pick_from_tty(reporter: Reporter) -> str | None:
    from maccleaner import app_uninstaller as au

    return au._pick_app_interactive(reporter)


def run(args: Any, deleter: Deleter, sudo: Sudo | None, reporter: Reporter) -> int:
    from maccleaner import app_uninstaller as au

    # 1. Resolve the target. No target: picker on a TTY, else usage error.
    target_text = getattr(args, "target", None)
    if not target_text:
        if sys.stdin.isatty():
            picked = _pick_from_tty(reporter)
            if not picked:
                reporter.warn("uninstall_cancelled")
                return 0
            target_text = picked
        else:
            reporter.error("usage", msg="give an app name or bundle id (or run in a Terminal)")
            return 2

    target = resolve(target_text)

    # 2. Build the full fingerprint + boolean matrix.
    fp = au._build_fingerprint_for_target(target)
    user = list(fp.get("leftovers", []))
    sys_paths = list(fp.get("system_paths", []))
    launch = list(fp.get("launch_paths", []))
    brew = list(fp.get("brew", []))
    helpers = list(fp.get("helpers", []))
    bba_items = list(fp.get("bba", []))  # (label, plist_url)
    matrix = au._build_matrix(target, fp)

    reporter.info(
        "uninstall_plan",
        name=target.name,
        bundle_id=target.bundle_id or "",
        app_installed=target.app_installed,
        bundle_path=target.path or "",
        matrix=matrix,
        leftover_count=len(user),
        system_count=len(sys_paths),
        launch_count=len(launch),
        brew_count=len(brew),
        helpers_count=len(helpers),
        bba_count=len(bba_items),
    )
    if not reporter.json_mode:
        cols = [
            "app", "mas", "pkg", "brew", "support", "cache", "prefs",
            "container", "saved", "agents", "daemons", "helpers", "kext", "btm",
        ]
        print("  " + "  ".join(f"{c:>10}" for c in cols))
        print("  " + "  ".join(f"{matrix.get(c, '—'):>10}" for c in cols))
    for p in user + sys_paths + brew + helpers:
        reporter.info("uninstall_target", path=p)
    for label, plist_url in bba_items:
        reporter.info("uninstall_bba_target", label=label, plist=plist_url)

    # 3. One yes/no gate. This is the only confirmation.
    if not confirm_yes("Delete all of this?"):
        reporter.warn("uninstall_aborted")
        return 0

    needs_root = bool(helpers) or any(
        au._is_system_launch(p)
        for p in launch + sys_paths + [plist for _lbl, plist in bba_items if plist]
    )
    if needs_root and sudo is not None:
        if not sudo.ensure():
            reporter.warn("sudo_unavailable", msg="system items will be skipped")

    deleter.commit = True
    deleter.confirm_fn = lambda _p: True
    if target.app_installed and target.path:
        deleter.delete("uninstall", [target.path])
    deleter.delete("uninstall", user)
    deleter.delete("uninstall", sys_paths, sudo=sudo)
    deleter.delete("uninstall", brew)
    deleter.delete("uninstall", helpers, sudo=sudo)

    # 4. Quarantine owned launch plists (never hard-delete).
    for label, path in zip(fp.get("launch_labels", []), launch):
        if path:
            au._quarantine_launch(label, path, deleter, sudo, reporter)

    # 5. Quarantine BAA plists for the same bundle.
    for label, plist_url in bba_items:
        if plist_url:
            au._quarantine_launch(label, plist_url, deleter, sudo, reporter)

    reporter.info("uninstall_complete", name=target.name)
    return 0


def resolve(query: str):
    """Resolve a name or bundle id to an uninstall target."""
    from maccleaner import app_uninstaller as au

    return au.resolve(query)
