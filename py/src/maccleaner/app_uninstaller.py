"""App Cleaner & Uninstaller.

Bundle-ID-first leftover discovery (audit MAJOR-1), full path coverage
(audit MAJOR-2), modern launchctl (audit MAJOR-3).
"""

from __future__ import annotations

import glob
import os
import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from maccleaner.core import Deleter, Reporter, Sudo, dir_size_kb, is_safe_path

APP_DIRS = ["/Applications", str(Path.home() / "Applications")]

# Short app names that would match half of ~/Library if used as substrings.
DANGEROUS_NAMES = frozenset({"r", "x", "c", "go", "a", "i", "ui", "db", "im", "id"})

USER_PATTERNS = [
    "Application Support/{name}",
    "Application Support/{bundle}",
    "Caches/{bundle}",
    "Preferences/{bundle}.plist",
    "Preferences/ByHost/{bundle}.*.plist",
    "Containers/{bundle}",
    "Group Containers/{bundle}",
    "Saved Application State/{bundle}.savedState",
    "WebKit/{bundle}",
    "HTTPStorages/{bundle}",
    "Cookies/{bundle}.binarycookies",
    "Application Scripts/{bundle}",
    "Logs/{name}",
    "LaunchAgents/*{name}*.plist",
    "LaunchAgents/*{bundle}*.plist",
    "Services/*{name}*",
    "QuickLook/*{name}*",
    "Spotlight/*{name}*",
]

SYSTEM_PATTERNS = [
    "LaunchDaemons/*{name}*.plist",
    "Application Support/{name}",
    "Preferences/{bundle}.plist",
    "Caches/{name}",
    "/private/var/db/receipts/{bundle}.*",
]


@dataclass
class AppInfo:
    name: str
    bundle_id: str | None
    path: str
    version: str | None
    size_kb: int


def _parse_info_plist(app_path: str) -> tuple[str | None, str | None]:
    plist = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(plist, "rb") as f:
            info = plistlib.load(f)
        return info.get("CFBundleName") or info.get("CFBundleDisplayName"), info.get(
            "CFBundleIdentifier"
        )
    except (OSError, plistlib.InvalidFileException):
        return None, None


def list_apps() -> list[AppInfo]:
    apps: list[AppInfo] = []
    for d in APP_DIRS:
        if not os.path.isdir(d):
            continue
        for entry in os.scandir(d):
            if not entry.name.endswith(".app") or not entry.is_dir():
                continue
            name, bundle = _parse_info_plist(entry.path)
            apps.append(
                AppInfo(
                    name=name or entry.name[:-4],
                    bundle_id=bundle,
                    path=entry.path,
                    version=None,
                    size_kb=dir_size_kb(entry.path),
                )
            )
    return sorted(apps, key=lambda a: a.name.lower())


def _find_app(name_or_bundle: str, force: bool = False) -> AppInfo:
    apps = list_apps()
    exact = [a for a in apps if a.name.lower() == name_or_bundle.lower()]
    if not exact:
        exact = [
            a
            for a in apps
            if a.bundle_id and a.bundle_id.lower() == name_or_bundle.lower()
        ]
    if not exact:
        raise SystemExit(f"App not found: {name_or_bundle}. Try 'cleanmac app list'")
    app = exact[0]
    if not force and app.name.lower() in DANGEROUS_NAMES:
        raise SystemExit(
            f"'{app.name}' is a dangerous short name. Re-run with --force to confirm."
        )
    return app


def _user_paths(app: AppInfo) -> list[str]:
    """Build user-level leftover candidates (no mdfind needed; pattern-based)."""
    home = Path(os.environ.get("CLEANMAC_HOME", Path.home()))
    name = app.name
    bundle = app.bundle_id or app.name
    found: list[str] = []
    for pat in USER_PATTERNS:
        rel = pat.format(name=name, bundle=bundle)
        if rel.startswith("/"):
            continue
        p = home / "Library" / rel
        # expand globs
        matches = (
            glob.glob(str(p)) if "*" in str(p) else ([str(p)] if p.exists() else [])
        )
        for m in matches:
            if is_safe_path(m):
                found.append(m)
    return sorted(set(found))


def _system_paths(app: AppInfo) -> list[str]:
    """Build system-level leftover candidates (require sudo to delete)."""
    name = app.name
    bundle = app.bundle_id or app.name
    found: list[str] = []
    for pat in SYSTEM_PATTERNS:
        rel = pat.format(name=name, bundle=bundle)
        if rel.startswith("/"):
            p = Path(rel)
        else:
            p = Path("/Library") / rel
        matches = (
            glob.glob(str(p)) if "*" in str(p) else ([str(p)] if p.exists() else [])
        )
        for m in matches:
            if is_safe_path(m):
                found.append(m)
    return sorted(set(found))


def _run_remove(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    app = _find_app(args.app, force=args.force)
    reporter.info(
        "app_found",
        name=app.name,
        bundle_id=app.bundle_id,
        path=app.path,
        size_kb=dir_size_kb(app.path),
    )
    user = _user_paths(app)
    reporter.info("user_leftovers", count=len(user), paths=user)
    sys_paths = _system_paths(app)
    reporter.info("system_leftovers", count=len(sys_paths), paths=sys_paths)

    if not user and not sys_paths:
        reporter.info("no_leftovers_found")
        return 0

    reporter.info("app_remove_started", bundle=app.path)
    deleter.delete("app_remove", [app.path])
    deleter.delete("app_remove", user)
    deleter.delete("app_remove", sys_paths, sudo=sudo)
    return 0


def _scope_for_path(path: str) -> str:
    """Classify a LaunchAgent/LaunchDaemon directory as 'system' or 'user'.

    - LaunchDaemons are always system-scoped.
    - LaunchAgents under /Library (not under a user's home) are system-scoped.
    - LaunchAgents under ~/Library are user-scoped.
    """
    if os.path.isabs(path) and "LaunchDaemons" in path:
        return "system"
    if "LaunchAgents" in path and path.startswith("/Library"):
        return "system"
    return "user"


def _run_startup(args, sudo: Sudo, reporter: Reporter) -> int:
    if args.action == "list":
        return _startup_list(reporter)
    if args.action == "disable":
        return _startup_disable(args.label, sudo, reporter)
    return 2


def _startup_list(reporter: Reporter) -> int:
    dirs = [
        Path.home() / "Library/LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    reporter.info("startup_list_header", columns=["Label", "Scope", "State", "Path"])
    for d in dirs:
        if not d.is_dir():
            continue
        for plist in sorted(d.glob("*.plist")):
            label = plist.stem
            try:
                with plist.open("rb") as f:
                    data = plistlib.load(f)
                label = data.get("Label", label)
            except (OSError, plistlib.InvalidFileException):
                pass
            scope = _scope_for_path(str(d))
            state = "?"
            if scope == "user":
                r = subprocess.run(
                    ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                state = "running" if r.returncode == 0 else "stopped"
            reporter.info(
                "startup_item", label=label, scope=scope, state=state, path=str(plist)
            )
    return 0


def _startup_disable(label: str, sudo: Sudo, reporter: Reporter) -> int:
    if not label:
        reporter.error("usage", msg="cleanmac app startup disable <label>")
        return 2
    candidates = [
        Path.home() / "Library/LaunchAgents" / f"{label}.plist",
        Path("/Library/LaunchAgents") / f"{label}.plist",
        Path("/Library/LaunchDaemons") / f"{label}.plist",
    ]
    plist_path = next((p for p in candidates if p.exists()), None)
    if not plist_path:
        reporter.error("launchagent_not_found", label=label)
        return 1

    target = Path.home() / "Library/LaunchAgents-disabled"
    target.mkdir(parents=True, exist_ok=True)

    if "LaunchDaemons" in str(plist_path):
        r = sudo.run(["launchctl", "bootout", f"system/{label}"])
        reporter.info(
            "bootout_system",
            ok=r.returncode == 0,
            stderr=r.stderr.strip() if r.returncode != 0 else None,
        )
    else:
        r = subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            check=False,
        )
        reporter.info(
            "bootout_gui",
            ok=r.returncode == 0,
            stderr=r.stderr.strip() if r.returncode != 0 else None,
        )

    dest = target / plist_path.name
    plist_path.rename(dest)
    reporter.info("moved_to_disabled", dest=str(dest))
    return 0


def _run_extensions(reporter: Reporter) -> int:
    chrome = (
        Path.home() / "Library/Application Support/Google/Chrome/Default/Extensions"
    )
    safari = Path.home() / "Library/Containers/com.apple.Safari"
    ff = Path.home() / "Library/Application Support/Firefox/Profiles"
    chrome_exts = sorted([e.name for e in chrome.iterdir()]) if chrome.is_dir() else []
    safari_exts = (
        sorted([e.name for e in safari.glob("Extensions/*")]) if safari.is_dir() else []
    )
    ff_profiles = sorted([prof.name for prof in ff.iterdir()]) if ff.is_dir() else []
    reporter.info(
        "extensions_list",
        chrome=chrome_exts,
        safari=safari_exts,
        firefox=ff_profiles,
    )
    return 0


def _run_update(reporter: Reporter) -> int:
    mas = subprocess.run(
        ["mas", "outdated"], capture_output=True, text=True, check=False
    )
    brew = subprocess.run(
        ["brew", "outdated", "--cask"], capture_output=True, text=True, check=False
    )
    reporter.info(
        "outdated_apps",
        mas=mas.stdout.strip(),
        brew=brew.stdout.strip(),
    )
    return 0


def run(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    if args.app_cmd == "list":
        apps = list_apps()
        reporter.info(
            "apps_list",
            count=len(apps),
            apps=[
                {
                    "name": a.name,
                    "bundle_id": a.bundle_id,
                    "size_kb": dir_size_kb(a.path),
                }
                for a in apps
            ],
        )
        return 0
    if args.app_cmd == "remove":
        return _run_remove(args, deleter, sudo, reporter)
    if args.app_cmd == "reset":
        app = _find_app(args.app)
        home = Path(os.environ.get("CLEANMAC_HOME", Path.home()))
        prefs = home / "Library/Preferences" / f"{app.bundle_id or app.name}.plist"
        support = home / "Library/Application Support" / app.name
        paths = [str(p) for p in (prefs, support) if p.exists()]
        deleter.delete("app_reset", paths)
        return 0
    if args.app_cmd == "startup":
        return _run_startup(args, sudo, reporter)
    if args.app_cmd == "extensions":
        return _run_extensions(reporter)
    if args.app_cmd == "update":
        return _run_update(reporter)
    return 2
