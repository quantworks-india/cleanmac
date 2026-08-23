"""Background App Activity (BAA) detection via Apple's public tools.

Uses ``sfltool dumpbtm`` as the authoritative source (same data Apple uses
to render the Background App Activity UI). No binary parsing, no regex on
NSKeyedArchiver blobs — sfltool already does that for us and emits plain
text.

Pair ``find_bba_orphans()`` with ``launchctl print`` to surface live state
(running / stopped / not running) alongside the static BTM record.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from maccleaner import inventory


@dataclass
class BbaItem:
    """One record from sfltool dumpbtm (one background item)."""
    name: str
    developer: str
    identifier: str       # e.g. "16.com.google.keystone.daemon" or "8.ai.hermes.gateway"
    plist_url: str        # absolute path to the plist (may be empty)
    executable_path: str  # resolved binary path (may be empty)
    disposition: str      # raw "enabled, allowed, notified" etc.
    uid: int | None = None
    uuid: str = ""
    last_use: str = ""
    associated_bundle_ids: list[str] = field(default_factory=list)
    parent_identifier: str = ""
    state: str = ""  # populated by fetch_state() if requested

    @property
    def label(self) -> str:
        """Strip the launchd prefix (8. / 16. / 2.) to get a plain label."""
        return self.identifier.split(".", 1)[-1] if self.identifier else ""

    @property
    def scope(self) -> str:
        """system | user | unknown, derived from identifier prefix."""
        if self.identifier.startswith("16.") or self.identifier.startswith("2."):
            return "system"
        if self.identifier.startswith("8."):
            return "user"
        return "unknown"


def _run_sfltool_dumpbtm() -> str:
    """Call Apple's sfltool dumpbtm. Returns its plain-text dump."""
    sfltool = shutil.which("sfltool")
    if not sfltool:
        raise RuntimeError("sfltool not found on PATH (macOS only)")
    r = subprocess.run(
        [sfltool, "dumpbtm"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"sfltool dumpbtm failed: {r.stderr.strip()}")
    return r.stdout


def _split_field_line(line: str) -> tuple[str, str, str]:
    """Split a 'Key: value' line on the first ':'.

    Returns (key, sep, value). sep is ':' on success, '' if no colon.
    """
    head, sep, val = line.strip().partition(":")
    return head, sep, val.strip()


def _parse_dumpbtm(dump: str) -> list[BbaItem]:
    """Parse the plain-text output of sfltool dumpbtm into BbaItem records.

    Uses a line-state machine (splitlines + startswith/partition), no regex.
    Structure:

        ========================
         Records for UID <n>
        ========================
         Items:
         #1:
                         UUID: ...
                        Name: ...
                  Identifier: ...
    """
    items: list[BbaItem] = []
    uid_val: int | None = None
    in_items = False
    current: dict[str, str] | None = None

    def _flush() -> None:
        nonlocal current
        if current:
            item = _build_item(current, uid_val)
            if item:
                items.append(item)
            current = None

    for raw in dump.splitlines():
        line = raw.strip()

        if line.startswith("Records for UID"):
            # e.g. "Records for UID 501 : UUID"
            _flush()
            uid_val = _parse_uid(line)
            in_items = False
            continue

        if line.startswith("Items:"):
            in_items = True
            continue

        if not in_items:
            continue

        if line.startswith("#") and line.endswith(":"):
            # new item header
            _flush()
            current = {}
            continue

        if current is None:
            continue

        key, sep, val = _split_field_line(line)
        if not sep:
            continue
        if key == "Assoc. Bundle IDs":
            # value is "[ com.a, com.b ]"
            current["Assoc. Bundle IDs"] = val
            continue
        # Last occurrence wins for repeated keys (e.g. Embedded Item IDs).
        current[key] = val

    _flush()

    return items


def _parse_uid(line: str) -> int | None:
    """Extract the numeric UID from 'Records for UID N : ...'."""
    rest = line.replace("Records for UID", "", 1).strip()
    rest = rest.split(":", 1)[0].strip()
    try:
        return int(rest)
    except ValueError:
        return None


def _build_item(fields: dict[str, str], uid: int | None) -> BbaItem | None:
    """Build a BbaItem from a collected field dict, or None for parent rows."""
    identifier = fields.get("Identifier", "")
    # Skip parent entries that don't reference a specific plist job
    # (no numeric launchd prefix in identifier).
    if not identifier or not identifier[0].isdigit():
        return None

    associated: list[str] = []
    assoc_raw = fields.get("Assoc. Bundle IDs", "")
    if assoc_raw:
        inner = assoc_raw.strip()
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        associated = [s.strip() for s in inner.split(",") if s.strip()]

    return BbaItem(
        name=fields.get("Name", "") or "",
        developer=fields.get("Developer Name", "") or "",
        identifier=identifier,
        plist_url=fields.get("URL", "") if fields.get("URL") != "(null)" else "",
        executable_path=fields.get("Executable Path", "") if fields.get("Executable Path") != "(null)" else "",
        disposition=fields.get("Disposition", ""),
        uid=uid,
        uuid=fields.get("UUID", ""),
        last_use=fields.get("Last Use", ""),
        associated_bundle_ids=associated,
        parent_identifier=fields.get("Parent Identifier", ""),
    )


def fetch_state(item: BbaItem) -> str:
    """Query launchctl for the live state of this item (running/stopped/etc.)."""
    label = item.label
    if not label:
        return "unknown"
    domain = "system" if item.scope == "system" else f"gui/{item.uid or 0}"
    target = f"{domain}/{label}"
    r = subprocess.run(
        ["launchctl", "print", target],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return "not registered"
    # Parse "state = ..." line via startswith/partition (no regex).
    for raw in r.stdout.splitlines():
        line = raw.strip()
        if line.startswith("state"):
            head, sep, val = line.partition("=")
            if sep and val.strip():
                return val.strip()
    return "unknown"


def _is_bba_orphan(item: BbaItem, installed_apps: set[str]) -> bool:
    """True if this BBA item's app/daemon is gone or stub.

    Mechanical rule (no hardcoded vendor/brand dictionary):

    1. If any associated bundle ID matches an installed app → live.
    2. If the item's name/developer/parent matches an installed app's name
       (e.g. "Zoom", "WhatsApp", "Google Drive") → live.
    3. If the helper's executable still exists on disk → live.
    4. If the helper's plist URL still exists on disk → live.
    5. Otherwise → orphan.

    ``installed_apps`` is a set of lowercase `.app` basenames (e.g.
    ``"zoom.us.app"``) from the inventory module.
    """
    # 1. Associated bundle IDs (the parent app attribution)
    for bid in item.associated_bundle_ids:
        if _bundle_installed(bid, installed_apps):
            return False

    # 2. Name / developer / parent identifier matches an installed app
    for s in (item.name, item.developer, item.parent_identifier):
        if s and _name_installed(s, installed_apps):
            return False

    # 3. Live executable on disk
    if item.executable_path and Path(item.executable_path).exists():
        return False

    # 4. Live plist on disk (absolute only; relative URL is a broken item)
    if item.plist_url and item.plist_url.startswith("/") and Path(item.plist_url).exists():
        return False

    return True


def _name_installed(s: str, installed_apps: set[str]) -> bool:
    """True if a display name / developer matches an installed app."""
    s = s.strip().lower()
    if not s:
        return False
    for app in installed_apps:
        stem = app[:-4] if app.endswith(".app") else app
        stem = stem.lower()
        if stem and (s == stem or s in stem or stem in s):
            return True
    return False


def _bundle_installed(bundle_id: str, installed_apps: set[str]) -> bool:
    """True if a bundle id maps to an installed app bundle."""
    bid = bundle_id.lower()
    for app in installed_apps:
        stem = app[:-4] if app.endswith(".app") else app
        stem = stem.lower()
        # e.g. "com.google.Chrome" vs "google chrome.app" -> both contain
        # the last meaningful token. Compare last dot-segment to stem.
        tail = bid.rsplit(".", 1)[-1]
        if tail and (tail in stem or stem in tail):
            return True
    # Direct `.app` directory lookup by bundle-id-derived name.
    for base in (Path("/Applications"), Path.home() / "Applications"):
        for name in (bundle_id, bundle_id.replace(".", " ")):
            if (base / f"{name}.app").is_dir():
                return True
    return False


def find_bba_orphans(*, include_state: bool = False) -> list[BbaItem]:
    """Find Background App Activity items whose app/daemon is uninstalled.

    Args:
        include_state: If True, also call ``launchctl print`` for each item
            (slower; needed only if you want to display running/stopped).

    Returns:
        List of BbaItem that look orphaned.
    """
    dump = _run_sfltool_dumpbtm()
    all_items = _parse_dumpbtm(dump)
    installed = inventory.installed_app_names()
    orphans = []
    for item in all_items:
        if _is_bba_orphan(item, installed):
            if include_state:
                item.state = fetch_state(item)
            orphans.append(item)
    return orphans


def list_all_bba_items() -> list[BbaItem]:
    """Return every BAA item (for inspection / debugging)."""
    dump = _run_sfltool_dumpbtm()
    return _parse_dumpbtm(dump)