"""Spotlight-based orphan leftover scan.

``mdfind "kMDItemCFBundleIdentifier == '<bundle>'"`` is Apple's structured
way to find every file indexed against a bundle id. Used by the uninstall
flow BEFORE deleting the ``.app`` so we capture all leftovers.

Note: once an ``.app`` is gone, Spotlight stops indexing files under its
bundle id (the orphan dirs lose ``kMDItemCFBundleIdentifier``). So this
must run while the app is still installed.
"""

from __future__ import annotations

import re
import subprocess


_SAFE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def find_bundle_paths(bundle_id: str, *, timeout: float = 30.0) -> list[str]:
    """Return every Spotlight-indexed path owned by ``bundle_id``.

    Empty list if ``mdfind`` is missing, the bundle has no records, or the
    bundle id is unsafe (rejects shell injection in the predicate).
    """
    if not bundle_id or not _SAFE_RE.fullmatch(bundle_id):
        return []
    mdfind = "/usr/bin/mdfind"
    try:
        r = subprocess.run(
            [mdfind, f'kMDItemCFBundleIdentifier == "{bundle_id}"'],
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0 or not r.stdout:
        return []
    return sorted({p for p in r.stdout.splitlines() if p})


def is_safe_to_delete(path: str) -> bool:
    """Restrict Spotlight hits to user-writable, non-system roots."""
    from maccleaner.core import is_safe_path

    return is_safe_path(path)
