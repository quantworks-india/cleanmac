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

    # 2. Build the full fingerprint: leftover paths + owned launch items.
    fp = au._build_fingerprint_for_target(target)
    user = list(fp.get("leftovers", []))
    sys_paths = list(fp.get("system_paths", []))
    launch = list(fp.get("launch_paths", []))

    reporter.info(
        "uninstall_plan",
        name=target.name,
        bundle_id=target.bundle_id or "",
        app_installed=target.app_installed,
        bundle_path=target.path or "",
        leftover_count=len(user),
        system_count=len(sys_paths),
        launch_count=len(launch),
    )
    for p in user + sys_paths:
        reporter.info("uninstall_target", path=p)

    # 3. One yes/no gate. This is the only confirmation.
    if not confirm_yes("Delete all of this?"):
        reporter.warn("uninstall_aborted")
        return 0

    deleter.commit = True
    deleter.confirm_fn = lambda _p: True
    if target.app_installed and target.path:
        deleter.delete("uninstall", [target.path])
    deleter.delete("uninstall", user)
    deleter.delete("uninstall", sys_paths, sudo=sudo)

    # 4. Quarantine owned launch plists (never hard-delete).

    for label, path in zip(fp.get("launch_labels", []), launch):
        if path:
            au._quarantine_launch(label, path, deleter, sudo, reporter)

    reporter.info("uninstall_complete", name=target.name)
    return 0


def resolve(query: str):
    """Resolve a name or bundle id to an uninstall target."""
    from maccleaner import app_uninstaller as au

    return au.resolve(query)
