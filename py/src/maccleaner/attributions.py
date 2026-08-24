"""Helper→parent attribution from Apple's attributions.plist.

Apple ships a plist that maps helper executables / launchd labels to the
parent app's associated bundle identifiers and team id. We load it once with
plistlib and expose small lookups. No brand dictionaries, no regex.
"""

from __future__ import annotations

import plistlib
from functools import lru_cache

# Apple-documented location (PrivateFrameworks, BackgroundTaskManagement).
_ATTRIBUTIONS_PATH = (
    "/System/Library/PrivateFrameworks/"
    "BackgroundTaskManagement.framework/Versions/A/Resources/attributions.plist"
)


@lru_cache(maxsize=1)
def _load_attributions() -> dict:
    try:
        with open(_ATTRIBUTIONS_PATH, "rb") as f:
            data = plistlib.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, plistlib.InvalidFileException):
        return {}


def reset_cache() -> None:
    _load_attributions.cache_clear()


def parents_for_label(label: str) -> set[str]:
    """Associated bundle identifiers for a launchd label."""
    entry = _load_attributions().get(label)
    if not isinstance(entry, dict):
        return set()
    ids = entry.get("AssociatedBundleIdentifiers", [])
    return {str(i) for i in ids if isinstance(i, str)}


def parents_for_team(team_id: str) -> set[str]:
    """Associated bundle identifiers whose entry carries a given team id."""
    result: set[str] = set()
    for entry in _load_attributions().values():
        if not isinstance(entry, dict):
            continue
        if entry.get("TeamIdentifier") == team_id:
            ids = entry.get("AssociatedBundleIdentifiers", [])
            result.update(str(i) for i in ids if isinstance(i, str))
    return result
