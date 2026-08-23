"""Background App Activity (BAA) detection via Apple's public tools.

Uses ``sfltool dumpbtm`` as the authoritative source (same data Apple uses
to render the Background App Activity UI). No binary parsing, no regex on
NSKeyedArchiver blobs — sfltool already does that for us and emits plain
text.

Pair ``find_bba_orphans()`` with ``launchctl print`` to surface live state
(running / stopped / not running) alongside the static BTM record.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from maccleaner.app_uninstaller import get_installed_app_names


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


def _parse_dumpbtm(dump: str) -> list[BbaItem]:
    """Parse the plain-text output of sfltool dumpbtm into BbaItem records.

    The output is structured as:

        ========================
         Records for UID <n>
        ========================

         Items:

         #1:
                         UUID: ...
                        Name: ...
              Developer Name: ...
                  Identifier: ...
                       URL: ...
            Executable Path: ...

    We split on UID sections, then walk each item block.
    """
    items: list[BbaItem] = []
    # Each "Records for UID N" section
    uid_sections = re.split(r"^={20,}\s*$\s*Records for UID\s+(-?\d+)\s*:.*?\n={20,}\s*$",
                            dump, flags=re.MULTILINE)
    # uid_sections[0] is preamble (empty), then alternating uid, content, uid, content...
    for i in range(1, len(uid_sections), 2):
        uid_str = uid_sections[i]
        body = uid_sections[i + 1]
        try:
            uid_val = int(uid_str)
        except ValueError:
            continue
        items.extend(_parse_uid_section(uid_val, body))
    return items


def _parse_uid_section(uid_val: int, body: str) -> list[BbaItem]:
    out: list[BbaItem] = []
    # Find each item block starting with "#<n>:" at line start
    # Split on lines that start with "^ #\d+:" at column 0
    blocks = re.split(r"(?m)^ #(\d+):\s*$", body)
    # blocks[0] = preamble (e.g. " Items: ..."), then alternating num, content, num, content
    for j in range(1, len(blocks), 2):
        content = blocks[j + 1]
        item = _parse_item_block(uid_val, content)
        if item is not None:
            out.append(item)
    return out


def _parse_item_block(uid_val: int, content: str) -> BbaItem | None:
    """Extract fields from one item block."""
    fields: dict[str, str] = {}
    # Each field: "  <Key>: <Value>"  — value may be "(null)" or list
    # Lines look like: "                 UUID: 1577B2B7-..."
    for line in content.splitlines():
        m = re.match(r"^\s+([A-Za-z][A-Za-z ]*?):\s+(.*)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            # Last occurrence wins (for Embedded Item Identifiers etc.)
            fields[key] = val

    identifier = fields.get("Identifier", "")
    # Skip the "parent" entries that don't reference a specific plist job
    # (they have "(null)" URL and no numeric prefix in identifier).
    if not identifier:
        return None
    # Skip records whose Identifier is itself a developer name (e.g. "Zoom",
    # "Google LLC") — those are parent entries; their child entries follow.
    if not identifier[0].isdigit():
        return None

    associated = []
    # "Assoc. Bundle IDs: [ com.google.Chrome, com.google.drivefs ]"
    m = re.search(r"Assoc\. Bundle IDs:\s*\[\s*([^\]]+?)\s*\]", content)
    if m:
        associated = [s.strip() for s in m.group(1).split(",")]

    return BbaItem(
        name=fields.get("Name", "") or "",
        developer=fields.get("Developer Name", "") or "",
        identifier=identifier,
        plist_url=fields.get("URL", "") if fields.get("URL") != "(null)" else "",
        executable_path=fields.get("Executable Path", "") if fields.get("Executable Path") != "(null)" else "",
        disposition=fields.get("Disposition", ""),
        uid=uid_val,
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
    # Parse "state = ..." line
    m = re.search(r"^\s*state\s*=\s*(.+?)\s*$", r.stdout, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "unknown"


def _is_bba_orphan(item: BbaItem, installed_apps: set[str]) -> bool:
    """True if this BBA item's app/daemon is gone or stub.

    Decision tree (any positive match means live):

    - Associated bundle IDs match an installed app by name or by ``.app``
      directory lookup.
    - Developer name or parent identifier substring matches an installed app.
    - Plist URL points under a path that contains an installed app's name
      (e.g. ``/Users/x/.hermes/.../Hermes.app/...``).

    Otherwise we declare orphan if:
    - Executable path is missing
    - Plist URL is missing
    - Developer / name matches a known-bad-uninstaller brand AND no
      installed app contains that brand.
    """
    # ── Live signals ──────────────────────────────────────────────
    def _name_in_installed(s: str) -> bool:
        s = s.lower()
        return any(s in a or s.replace(".app", "") in a for a in installed_apps)

    # 1. Associated bundle IDs
    for bid in item.associated_bundle_ids:
        if _name_in_installed(bid):
            return False
        if (Path("/Applications") / f"{bid}.app").is_dir():
            return False
        if (Path.home() / "Applications" / f"{bid}.app").is_dir():
            return False

    # 2. Developer name or parent identifier
    for s in (item.developer, item.parent_identifier, item.name):
        if s and _name_in_installed(s):
            return False

    # 3. Plist URL contains an installed app name (e.g. Hermes.app nested
    # under a non-standard install path).
    if item.plist_url:
        plist_lower = item.plist_url.lower()
        for app in installed_apps:
            stem = app.replace(".app", "").strip()
            if stem and stem in plist_lower:
                return False

    # 4. Executable path contains an installed app name (login items
    # nested inside an app bundle, etc.)
    if item.executable_path:
        exe_lower = item.executable_path.lower()
        for app in installed_apps:
            stem = app.replace(".app", "").strip()
            if stem and stem in exe_lower:
                return False

    # ── Orphan signals ─────────────────────────────────────────────
    # Executable missing
    if item.executable_path and not Path(item.executable_path).exists():
        return True
    # Plist missing
    if item.plist_url and not Path(item.plist_url).exists():
        return True

    # 5. Known-bad-uninstaller brand + no installed match
    from maccleaner.app_uninstaller import ORPHAN_BRANDS
    haystack = " ".join(
        str(x or "").lower() for x in (item.developer, item.name, item.parent_identifier)
    )
    for brand, triggers in ORPHAN_BRANDS.items():
        if any(t in haystack for t in triggers):
            if not any(brand in a or any(t in a for t in triggers) for a in installed_apps):
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
    installed = get_installed_app_names()
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