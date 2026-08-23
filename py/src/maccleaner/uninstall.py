"""Top-level `cleanmac uninstall` — the one product surface for this pass.

Task 1: thin router. Later tasks replace the internals with the
leftover-only resolver, in-place picker, and single-confirm flow.
"""

from __future__ import annotations

from typing import Any

from maccleaner.core import Deleter, Reporter, Sudo


def run(args: Any, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    """Route the top-level uninstall through the existing app uninstaller."""
    from maccleaner import app_uninstaller

    # Rebuild the args shape app_uninstaller.run expects.
    inner = type(
        "A",
        (),
        {
            "app_cmd": "uninstall",
            "name": args.target,
            "yes": False,
            "force": False,
        },
    )
    return app_uninstaller.run(inner, deleter, sudo, reporter)
