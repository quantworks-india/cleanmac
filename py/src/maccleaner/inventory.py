"""Installed-app inventory from `system_profiler SPApplicationsDataType -json`.

Uses the structured JSON Apple's profiler emits (no regex, no `.app` glob in
the happy path) so non-standard installs and /System apps are captured. Cached
once per process; `reset_cache()` is available for tests.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

APP_DIRS = ["/Applications", str(Path.home() / "Applications")]


@dataclass(frozen=True)
class App:
    name: str
    path: str


def _load_system_profiler_json() -> dict:
    """Run system_profiler and return the parsed JSON (empty dict on failure)."""
    try:
        out = subprocess.run(
            ["system_profiler", "SPApplicationsDataType", "-json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip())
        data = json.loads(out.stdout)
        if not isinstance(data, dict):
            raise RuntimeError("unexpected system_profiler shape")
        return data
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"system_profiler unavailable: {e}") from e


def _parse(data: dict) -> tuple[list[App], set[str]]:
    apps: list[App] = []
    names: set[str] = set()
    for entry in data.get("SPApplicationsDataType", []):
        name = entry.get("_name", "")
        path = entry.get("path", "")
        if not path:
            continue
        apps.append(App(name=name or path, path=path))
        # Installed-name contract: basename of the .app bundle, lowercased
        # (e.g. "zoom.us.app"), matching the previous glob-based API.
        basename = Path(path).name.lower()
        if basename.endswith(".app"):
            names.add(basename)
        elif name:
            names.add(name.lower())
    return apps, names


@lru_cache(maxsize=1)
def _inventory() -> tuple[list[App], set[str]]:
    try:
        return _parse(_load_system_profiler_json())
    except RuntimeError:
        return _parse(_fallback_glob())


def _fallback_glob() -> dict:
    """Minimal directory-glob fallback (only if system_profiler is missing)."""
    apps = []
    for base in APP_DIRS:
        if not os.path.isdir(base):
            continue
        for p in sorted(Path(base).glob("*.app")):
            if (p / "Contents" / "Info.plist").is_file():
                apps.append({"_name": p.name[:-4], "path": str(p)})
    return {"SPApplicationsDataType": apps}


def reset_cache() -> None:
    _inventory.cache_clear()


def list_installed_apps() -> list[App]:
    return list(_inventory()[0])


def installed_app_names() -> set[str]:
    return set(_inventory()[1])
