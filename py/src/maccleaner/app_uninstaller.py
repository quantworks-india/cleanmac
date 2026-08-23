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

@dataclass
class Orphan:
    """One launch item that appears to belong to an uninstalled app."""
    label: str
    path: str
    exe: str | None
    scope: str  # "user" or "system"



def _run_startup(args, sudo: Sudo, reporter: Reporter) -> int:
    if args.action == "list":
        return _startup_list(reporter, orphans_only=getattr(args, "orphans_only", False))
    if args.action == "disable":
        return _startup_disable(args.label, sudo, reporter)
    return 2


def _startup_list(reporter: Reporter, orphans_only: bool = False) -> int:
    """List every launch item, with a per-item orphan flag (or filter to orphans).

    Orphan is mechanical: the item is a leftover if its executable is missing
    AND its label doesn't match an installed app (via the shared inventory).
    """
    from maccleaner import inventory

    dirs = [
        Path.home() / "Library/LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    installed_apps = inventory.installed_app_names()
    header = "startup_orphans_header" if orphans_only else "startup_list_header"
    reporter.info(header, columns=["Label", "Scope", "State", "Orphaned", "Path"])

    shown = 0
    for d in dirs:
        if not d.is_dir():
            continue
        for plist in sorted(d.glob("*.plist")):
            label = plist.stem
            data = {}
            exe = None
            try:
                with plist.open("rb") as f:
                    data = plistlib.load(f)
                label = data.get("Label", label)
                prog = data.get("Program")
                args = data.get("ProgramArguments") or []
                exe = str(prog or (args[0] if args else "")).strip() or None
            except (OSError, plistlib.InvalidFileException, PermissionError):
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

            orphaned = _is_item_orphan(label, exe, installed_apps)

            if orphans_only and not orphaned:
                continue

            reporter.info(
                "startup_item",
                label=label,
                scope=scope,
                state=state,
                orphaned=orphaned,
                path=str(plist),
            )
            shown += 1

    if orphans_only:
        reporter.info("startup_orphans_complete", count=shown)
    return 0


def _is_item_orphan(label: str, exe: str | None, installed_apps: set[str]) -> bool:
    """Mechanical orphan check for a launch item.

    An item is orphan iff its executable is missing AND no installed app
    name matches the launch label. No brand dictionary.
    """
    # Label matches an installed app -> live.
    label_l = label.lower()
    for app in installed_apps:
        stem = app[:-4] if app.endswith(".app") else app
        stem = stem.lower()
        if stem and (label_l == stem or label_l in stem or stem in label_l):
            return False
    # Executable still present -> live.
    if exe and os.path.exists(exe):
        return False
    return True



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


def _orphans_purge(
    orphans: list[Orphan],
    deleter: Deleter,
    sudo: Sudo,
    reporter: Reporter,
    yes: bool = False,
) -> int:
    """Disable (bootout) + remove orphaned launch items.

    Each plist is moved into ~/Library/LaunchAgents-disabled/ so the action
    is reversible. System-scope plists use sudo. Every action is audited.
    """
    if not orphans:
        reporter.info("orphans_purge_empty")
        return 0

    # Honor CLEANMAC_HOME so tests can sandbox the quarantine dir.
    target_root = Path(os.environ.get("CLEANMAC_HOME", Path.home()))
    target = target_root / "Library/LaunchAgents-disabled"

    if not deleter.commit:
        # Dry-run: enumerate only. No bootout, no move.
        reporter.info(
            "orphans_purge_dryrun",
            count=len(orphans),
            items=[o.__dict__ for o in orphans],
            target=str(target),
        )
        return 0

    target.mkdir(parents=True, exist_ok=True)
    reporter.info("orphans_purge_started", count=len(orphans), target=str(target))
    purged = 0
    for o in orphans:
        plist = Path(o.path)
        if not plist.exists():
            reporter.warn("orphan_missing", label=o.label, path=o.path)
            continue

        # 1. Bootout first (idempotent — ok if not loaded)
        if o.scope == "system":
            r = sudo.run(["launchctl", "bootout", f"system/{o.label}"])
            reporter.info(
                "orphan_bootout_system",
                label=o.label,
                ok=r.returncode == 0,
                stderr=r.stderr.strip() if r.returncode != 0 else None,
            )
        else:
            r = subprocess.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}/{o.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            reporter.info(
                "orphan_bootout_gui",
                label=o.label,
                ok=r.returncode == 0,
                stderr=r.stderr.strip() if r.returncode != 0 else None,
            )

        # 2. Move plist to quarantine (reversible)
        dest = target / plist.name
        if dest.exists():
            stem = dest.stem
            i = 1
            while dest.exists():
                dest = target / f"{stem}-{i}.plist"
                i += 1
        try:
            if o.scope == "system":
                # root-owned plist — need sudo mv
                r = sudo.run(["mv", str(plist), str(dest)])
                if r.returncode != 0:
                    reporter.error(
                        "orphan_move_failed",
                        label=o.label,
                        stderr=r.stderr.strip(),
                    )
                    deleter.auditor.write(
                        "orphan_purge", "failed", str(plist)
                    )
                    continue
            else:
                plist.rename(dest)
            reporter.info("orphan_moved", label=o.label, dest=str(dest))
            deleter.auditor.write(
                "orphan_purge", "deleted", str(plist), 0
            )
            purged += 1
        except OSError as e:
            reporter.error("orphan_move_failed", label=o.label, error=str(e))
            deleter.auditor.write("orphan_purge", "failed", str(plist))

    reporter.info("orphans_purge_complete", purged=purged, total=len(orphans))
    # Return 0 unless something failed — missing plists are not failures.
    return 0


def _run_orphans(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    """Dispatch for `app orphans`. Aliases the single BBA/sfltool engine."""
    # Map orphans_action -> bba_action (same verbs).
    bba_args = type("B", (), {"bba_action": args.orphans_action,
                              "commit": getattr(args, "commit", False),
                              "yes": getattr(args, "yes", False)})()
    return _run_bba(bba_args, deleter, sudo, reporter)


def _run_bba(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    """Dispatch for the `app bba` subcommand (Background App Activity)."""
    from maccleaner import bba as bba_mod

    if args.bba_action == "list":
        items = bba_mod.find_bba_orphans(include_state=True)
        reporter.info(
            "bba_orphans_header",
            columns=["Label", "Scope", "State", "Name", "Developer", "BundleIds", "Plist"],
        )
        for it in items:
            reporter.info(
                "bba_orphan",
                label=it.label,
                scope=it.scope,
                state=it.state or "?",
                name=it.name,
                developer=it.developer,
                bundle_ids=",".join(it.associated_bundle_ids),
                plist=it.plist_url or "",
            )
        reporter.info("bba_orphans_complete", count=len(items))
        return 0

    if args.bba_action == "purge":
        items = bba_mod.find_bba_orphans(include_state=False)
        if not items:
            reporter.info("bba_orphans_none")
            return 0

        reporter.info(
            "bba_orphans_found",
            count=len(items),
            items=[
                {
                    "label": it.label,
                    "scope": it.scope,
                    "plist": it.plist_url,
                    "exe": it.executable_path,
                    "developer": it.developer,
                }
                for it in items
            ],
        )
        if not deleter.commit:
            reporter.info("bba_purge_dryrun", count=len(items))
            return 0

        if args.yes:
            deleter.confirm_fn = lambda _p: True

        # Convert BbaItem -> Orphan so we reuse _orphans_purge
        orphans = [
            Orphan(
                label=it.label,
                path=it.plist_url,
                exe=it.executable_path or None,
                scope=it.scope if it.scope in ("system", "user") else "user",
            )
            for it in items
            if it.plist_url
        ]
        return _orphans_purge(orphans, deleter, sudo, reporter, yes=args.yes)
    return 2


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
    if args.app_cmd == "orphans":
        return _run_orphans(args, deleter, sudo, reporter)
    if args.app_cmd == "bba":
        return _run_bba(args, deleter, sudo, reporter)
    if args.app_cmd == "extensions":
        return _run_extensions(reporter)
    if args.app_cmd == "update":
        return _run_update(reporter)
    return 2
