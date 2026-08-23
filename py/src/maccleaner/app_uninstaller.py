"""App Cleaner & Uninstaller.

Bundle-ID-first leftover discovery (audit MAJOR-1), full path coverage
(audit MAJOR-2), modern launchctl (audit MAJOR-3).
"""

from __future__ import annotations

import glob
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from maccleaner import view
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


@dataclass
class UninstallTarget:
    """What we are removing. A live .app, leftover-only, or a name/id.

    ``app_installed`` is False when the bundle is already gone but the
    target still resolves by name or bundle id for leftover cleanup.
    """

    name: str
    bundle_id: str | None
    path: str  # empty "" when the .app is no longer present
    app_installed: bool
    query: str


def _scan_apps_in(directory: str) -> list[AppInfo]:
    """List .app bundles directly under ``directory`` (does not recurse)."""
    apps: list[AppInfo] = []
    if not os.path.isdir(directory):
        return apps
    for entry in os.scandir(directory):
        if not entry.name.endswith(".app") or not entry.is_dir():
            continue
        name, bundle = _parse_info_plist(entry.path)
        apps.append(
            AppInfo(
                name=name or entry.name[:-4],
                bundle_id=bundle,
                path=entry.path,
                version=None,
                size_kb=0,
            )
        )
    return apps


def _candidate_dirs() -> list[str]:
    """Directories to scan for installed apps (respects CLEANMAC_HOME)."""
    home = os.environ.get("CLEANMAC_HOME") or str(Path.home())
    return ["/Applications", os.path.join(home, "Applications")]


def resolve(query: str) -> UninstallTarget:
    """Resolve a name or bundle id to an uninstall target.

    Matches display name, bundle id, and .app basename. If no live app
    matches but the query itself is a plausible name/bundle, returns a
    leftover-only target so cleanup can still run.
    """
    q = query.strip()
    if not q:
        raise SystemExit("Uninstall needs an app name or bundle id.")

    apps: list[AppInfo] = []
    for d in _candidate_dirs():
        apps.extend(_scan_apps_in(d))

    lowered = q.lower()
    for a in apps:
        if (
            a.name.lower() == lowered
            or (a.bundle_id and a.bundle_id.lower() == lowered)
            or os.path.splitext(os.path.basename(a.path))[0].lower() == lowered
        ):
            return UninstallTarget(
                name=a.name,
                bundle_id=a.bundle_id,
                path=a.path,
                app_installed=True,
                query=q,
            )

    # No live app: leftover-only target. Bundle id if it looks like one,
    # otherwise treat the query as a display/name hint.
    looks_like_bundle = "." in q
    return UninstallTarget(
        name=q,
        bundle_id=q if looks_like_bundle else None,
        path="",
        app_installed=False,
        query=q,
    )


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


def list_apps(*, include_size: bool = False) -> list[AppInfo]:
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
                    size_kb=dir_size_kb(entry.path) if include_size else 0,
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


def _build_fingerprint(app: AppInfo, home: Path | None = None) -> dict:
    """Find every launch plist + leftover owned by ``app``.

    Mechanical ownership: a launch item belongs to the app if its label equals
    the app's bundle id, or its executable lives inside the app bundle. No
    substring/brand guessing.
    """
    home = home or Path(os.environ.get("CLEANMAC_HOME", Path.home()))
    bundle = app.bundle_id or ""
    app_dir = os.path.dirname(app.path)

    launch_dirs = [
        home / "Library" / "LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    launch_labels: list[str] = []
    launch_paths: list[str] = []
    for d in launch_dirs:
        if not d.is_dir():
            continue
        for plist in d.glob("*.plist"):
            label = plist.stem
            exe = None
            try:
                with plist.open("rb") as f:
                    data = plistlib.load(f)
                label = data.get("Label", label)
                prog = data.get("Program")
                args = data.get("ProgramArguments") or []
                exe = str(prog or (args[0] if args else ""))
            except (OSError, plistlib.InvalidFileException, PermissionError):
                pass
            owned = False
            if bundle and label.lower() == bundle.lower():
                owned = True
            if exe and app_dir and exe.startswith(app_dir):
                owned = True
            if owned:
                launch_labels.append(label)
                launch_paths.append(str(plist))

    # User leftovers (Application Support, Caches, Containers, Preferences...)
    leftovers = _user_paths(app) if home else []

    return {
        "launch_labels": launch_labels,
        "launch_paths": launch_paths,
        "leftovers": leftovers,
    }


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


def spotlight_orphan_paths(bundle_id: str) -> list[str]:
    """Live (pre-delete) Spotlight hits for ``bundle_id``.

    Captures every path Apple has indexed against this bundle, used to
    print a precise list before the ``.app`` is removed. After deletion,
    Spotlight loses the metadata — this is intentional.
    """
    from maccleaner import spotlight as sp

    raw = sp.find_bundle_paths(bundle_id)
    return [p for p in raw if is_safe_path(p)]


def _leftover_paths_for_bundle(bundle_id: str) -> list[str]:
    """Leftover paths an already-uninstalled app leaves behind.

    Combines the existing pattern-based scanner with a heuristic sweep
    of the most likely sibling dirs in ``~/Library`` (Application
    Support, Caches, Containers, HTTPStorages, Preferences, Saved
    Application State). Apple's Launch Services retains the bundle id
    after the ``.app`` is gone, but Spotlight's bundle-id index does
    not — so we cannot rely on ``mdfind`` here.
    """
    if not bundle_id:
        return []
    parts = bundle_id.split(".")
    candidates: set[str] = {
        parts[-1],                       # VSCode
        ".".join(parts[-2:]),            # microsoft.VSCode
        parts[-2] if len(parts) >= 2 else "",  # microsoft
    }
    home = Path(os.environ.get("CLEANMAC_HOME", Path.home()))
    likely_roots = (
        "Application Support",
        "Caches",
        "Containers",
        "HTTPStorages",
        "Preferences",
        "Saved Application State",
        "Logs",
        "Group Containers",
    )
    found: list[str] = []
    seen_paths: set[str] = set()
    # 1) Run the pattern scanner against each candidate name.
    seen_names: set[str] = set()
    for name in candidates:
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        app = AppInfo(name=name, bundle_id=bundle_id, path="", version=None, size_kb=0)
        for p in _user_paths(app):
            if p not in seen_paths:
                seen_paths.add(p)
                found.append(p)
    # 2) Heuristic sweep: exact bundle id and lowercase prefix under likely
    # Library roots (Apple apps store under both names depending on build).
    for root in likely_roots:
        base = home / "Library" / root
        if not base.is_dir():
            continue
        for probe in (bundle_id, bundle_id.lower(), parts[-1], parts[-1].lower()):
            if not probe:
                continue
            cand = base / probe
            if cand.exists() and str(cand) not in seen_paths:
                seen_paths.add(str(cand))
                found.append(str(cand))
    return found


def _run_uninstall(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    """Deep uninstall: app bundle + leftovers + owned launch plists.

    Dry-run by default. On --commit it deletes the bundle and leftovers via
    the Deleter, then bootout + quarantines any launch plist owned by the app.
    """
    app = _find_app(args.name, force=args.force if hasattr(args, "force") else False)
    reporter.info(
        "uninstall_app",
        name=app.name,
        bundle_id=app.bundle_id,
        path=app.path,
    )
    # Capture Spotlight hits BEFORE deletion (Spotlight loses the index
    # entry once the .app is gone). This is the authoritative leftover
    # list; pattern scanning is the fallback.
    if app.bundle_id:
        spotlight_hits = spotlight_orphan_paths(app.bundle_id)
        reporter.info("uninstall_spotlight", count=len(spotlight_hits))
    else:
        spotlight_hits = []
    fp = _build_fingerprint(app)
    user = list(dict.fromkeys(spotlight_hits + fp["leftovers"]))
    sys_paths = _system_paths(app)
    reporter.info(
        "uninstall_fingerprint",
        launch_labels=fp["launch_labels"],
        launch_paths=fp["launch_paths"],
        user_count=len(user),
        system_count=len(sys_paths),
    )

    if not deleter.commit:
        reporter.info("uninstall_dryrun", app=app.name, count=len(fp["launch_labels"]))
        reporter.dryrun()
        return 0

    # 1. Remove app bundle + user/system leftovers
    if getattr(args, "yes", False):
        deleter.confirm_fn = lambda _p: True
    deleter.delete("app_uninstall", [app.path])
    deleter.delete("app_uninstall", user)
    deleter.delete("app_uninstall", sys_paths, sudo=sudo)

    # 2. Bootout + quarantine owned launch plists
    orphans = [
        Orphan(
            label=label,
            path=path,
            exe=None,
            scope="system" if "LaunchDaemons" in path or "/Library/LaunchAgents" in path else "user",
        )
        for label, path in zip(fp["launch_labels"], fp["launch_paths"])
    ]
    return _orphans_purge(orphans, deleter, sudo, reporter, yes=getattr(args, "yes", False))


def _run_purge_by_id(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    """Wipe leftovers of an already-uninstalled app by bundle id.

    Uses the existing pattern scanner (Application Support, Caches, etc.)
    and the in-process Spotlight cache; both ignore the missing ``.app``
    bundle. Dry-run by default.
    """
    bundle = args.bundle
    reporter.info("purge_by_id", bundle=bundle)
    leftovers = _leftover_paths_for_bundle(bundle)
    if not deleter.commit:
        for path in leftovers:
            reporter.info("purge_by_id_target", path=path)
        reporter.info(
            "purge_by_id_dryrun",
            bundle=bundle,
            count=len(leftovers),
        )
        return 0
    if getattr(args, "yes", False):
        deleter.confirm_fn = lambda _p: True
    deleter.delete("app_uninstall", leftovers)
    reporter.info("purge_by_id_complete", bundle=bundle, count=len(leftovers))
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

    Default list skips system_profiler and per-plist launchctl (those are
    the slow path). Orphan detection still uses inventory when requested.
    """
    dirs = [
        Path.home() / "Library/LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    installed_apps: set[str] = set()
    if orphans_only:
        from maccleaner import inventory

        installed_apps = inventory.installed_app_names()
    rows: list[list[str]] = []

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
            orphaned = _is_item_orphan(label, exe, installed_apps) if orphans_only else False

            if orphans_only and not orphaned:
                continue

            rows.append([label, scope, state, "yes" if orphaned else "no", str(plist)])
            shown += 1

    event = "startup_orphans_list" if orphans_only else "startup_list"
    reporter.table(
        event,
        ["Label", "Scope", "State", "Orphaned", "Path"],
        rows,
    )
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
        rows = [
            [
                it.label,
                it.scope,
                it.state or "?",
                it.name,
                it.developer,
                ",".join(it.associated_bundle_ids),
                it.plist_url or "",
            ]
            for it in items
        ]
        reporter.table(
            "bba_orphans_list",
            ["Label", "Scope", "State", "Name", "Developer", "BundleIds", "Plist"],
            rows,
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


def _parse_key(data: bytes) -> str:
    """Map a raw terminal byte sequence to a semantic key.

    Supports arrow keys (ESC [ A/B/C/D), Enter (\r or \n), and cancel
    (q, ESC, Ctrl-C). Plain printable bytes map to themselves.
    """
    if data in (b"\x1b[A", b"\x1bOA"):
        return "up"
    if data in (b"\x1b[B", b"\x1bOB"):
        return "down"
    if data in (b"\x1b[C", b"\x1bOC"):
        return "right"
    if data in (b"\x1b[D", b"\x1bOD"):
        return "left"
    if data in (b"\r", b"\n"):
        return "enter"
    if data in (b"\x1b", b"q", b"Q", b"\x03"):
        return "cancel"
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _move_cursor(idx: int, key: str, total: int) -> int:
    """Move the selection index up/down, clamped to [0, total)."""
    if key == "down":
        return min(idx + 1, total - 1)
    if key == "up":
        return max(idx - 1, 0)
    return idx


def _pick_app_interactive(reporter: Reporter) -> str | None:
    """Show an arrow-key navigable list of apps; return the chosen name.

    Up/Down to move, Enter to select, q / Esc / Ctrl-C to cancel. Uses only
    stdlib termios/tty/ANSI escapes — no third-party dependency.
    """
    apps = list_apps()
    if not apps:
        reporter.warn("no_apps_installed")
        return None

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        idx = 0
        while True:
            # Redraw the list from the current cursor position.
            rows = []
            for i, a in enumerate(apps):
                marker = "▸" if i == idx else " "
                rows.append(f" {marker} {a.name}  {a.bundle_id or ''}")
            block = "\x1b[?25l" + "\n".join(rows) + "\x1b[0m"
            sys.stdout.write("\x1b[H\x1b[J" + block + "\n")
            sys.stdout.flush()

            chunk = os.read(fd, 1)
            if chunk == b"\x1b":
                # read the rest of an escape sequence
                more = os.read(fd, 2)
                key = _parse_key(chunk + more)
            else:
                key = _parse_key(chunk)

            if key == "down":
                idx = _move_cursor(idx, "down", len(apps))
            elif key == "up":
                idx = _move_cursor(idx, "up", len(apps))
            elif key == "enter":
                chosen = apps[idx].name
                sys.stdout.write("\x1b[K" + "\x1b[0m" + f"\nSelected: {chosen}\n")
                sys.stdout.flush()
                return chosen
            elif key == "cancel":
                sys.stdout.write("\x1b[0m\n")
                sys.stdout.flush()
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run(args, deleter: Deleter, sudo: Sudo, reporter: Reporter) -> int:
    if args.app_cmd == "list":
        apps = list_apps(include_size=True)
        rows = [
            [a.name, a.bundle_id or "", view.human_size(a.size_kb * 1024)]
            for a in apps
        ]
        reporter.table("apps_list", ["Name", "Bundle ID", "Size"], rows)
        return 0
    if args.app_cmd == "remove":
        return _run_remove(args, deleter, sudo, reporter)
    if args.app_cmd == "uninstall":
        # Interactive picker when no --name given and stdin is a TTY.
        if not getattr(args, "name", None):
            if sys.stdin.isatty():
                picked = _pick_app_interactive(reporter)
                if not picked:
                    reporter.warn("uninstall_cancelled")
                    return 0
                args = type("B", (), {**vars(args), "name": picked})()
            else:
                reporter.error("usage", msg="use --name <app> when not interactive")
                return 2
        return _run_uninstall(args, deleter, sudo, reporter)
    if args.app_cmd == "purge-by-id":
        return _run_purge_by_id(args, deleter, sudo, reporter)
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
