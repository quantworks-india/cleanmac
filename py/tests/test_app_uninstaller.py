"""Tests for app_uninstaller — leftover discovery, bundle-ID matching, safety."""

from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from maccleaner import app_uninstaller as au
from maccleaner.core import Reporter


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    """Redirect APP_DIRS + home to a sandbox with a fake app."""
    home = tmp_path / "home"
    (home / "Library").mkdir(parents=True)
    monkeypatch.setenv("CLEANMAC_HOME", str(home))
    monkeypatch.setattr(au, "APP_DIRS", [str(home / "Applications")])

    # fake app bundle (inside the sandbox home so is_safe_path allows it)
    apps = home / "Applications"
    bundle = apps / "MyApp.app"
    (bundle / "Contents").mkdir(parents=True)
    info = bundle / "Contents" / "Info.plist"
    with info.open("wb") as f:
        plistlib.dump(
            {"CFBundleName": "MyApp", "CFBundleIdentifier": "com.example.myapp"},
            f,
        )

    # leftover paths the tool should find
    lib = home / "Library"
    (lib / "Application Support" / "MyApp").mkdir(parents=True)
    (lib / "Caches" / "com.example.myapp").mkdir(parents=True)
    (lib / "Preferences").mkdir(parents=True)
    (lib / "Preferences" / "com.example.myapp.plist").write_text("x")
    (lib / "Containers" / "com.example.myapp").mkdir(parents=True)
    (lib / "Logs" / "MyApp").mkdir(parents=True)
    (lib / "LaunchAgents").mkdir(parents=True)
    (lib / "LaunchAgents" / "com.example.myapp.plist").write_text("x")

    return tmp_path


def test_list_apps_finds_fake_bundle(fake_home):
    apps = au.list_apps()
    assert len(apps) == 1
    assert apps[0].name == "MyApp"
    assert apps[0].bundle_id == "com.example.myapp"


def test_find_app_by_name_and_bundle(fake_home):
    a = au._find_app("myapp")
    assert a.bundle_id == "com.example.myapp"
    a = au._find_app("com.example.myapp")
    assert a.name == "MyApp"


def test_dangerous_short_name_requires_force(fake_home):
    with pytest.raises(SystemExit):
        au._find_app("R", force=False)


def test_user_paths_finds_leftovers(fake_home):
    app = au._find_app("myapp")
    user = au._user_paths(app)
    joined = "\n".join(user)
    assert "Application Support/MyApp" in joined
    assert "Caches/com.example.myapp" in joined
    assert "Preferences/com.example.myapp.plist" in joined
    assert "Containers/com.example.myapp" in joined
    assert "Logs/MyApp" in joined
    assert "LaunchAgents/com.example.myapp.plist" in joined


def test_user_paths_never_contains_dangerous_broad_match(fake_home):
    """Bundle-ID matching must not produce bare short-name matches."""
    app = au._find_app("myapp")
    user = au._user_paths(app)
    for p in user:
        assert "/Library/" in p  # always under a Library
        # the bundle ID (not a bare "R" or "X") drives the match
        assert "com.example.myapp" in p or "/MyApp" in p or "myapp" in p.lower()


def test_remove_dry_run_does_not_delete(fake_home):
    from maccleaner.core import Auditor, Deleter

    aud = Auditor("app-dry", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au._run_remove(
        type("A", (), {"app": "myapp", "force": False})(), d, None, Reporter()
    )
    assert rc == 0
    # fake app still there
    assert (fake_home / "home" / "Applications" / "MyApp.app").exists()
    aud.close()


def test_remove_routes_system_paths_through_deleter(fake_home, monkeypatch):
    """System paths must be deleted via Deleter.delete, not direct sudo rm."""
    from subprocess import CompletedProcess

    from maccleaner.core import Auditor, Deleter

    sys_path = str(fake_home / "home" / "Library" / "Caches" / "com.example.myapp")
    Path(sys_path).mkdir(parents=True, exist_ok=True)
    Path(sys_path + "/data").write_text("x")
    # Isolate system-path flow: user paths empty, only system path mocked
    monkeypatch.setattr(au, "_user_paths", lambda app: [])
    monkeypatch.setattr(au, "_system_paths", lambda app: [sys_path])

    aud = Auditor("app-sys", mode="dry-run")
    d = Deleter(aud, commit=False)

    delete_calls: list[list[str]] = []
    original_delete = d.delete

    def tracking_delete(step, paths, *args, **kwargs):
        delete_calls.append(list(paths))
        return original_delete(step, paths)

    d.delete = tracking_delete  # type: ignore[assignment]

    sudo_calls: list[list[str]] = []

    class TrackingSudo:
        def ensure(self) -> bool:
            return True

        def run(self, args: list[str]) -> CompletedProcess:
            sudo_calls.append(list(args))
            return CompletedProcess(args, 0, "", "")

    rc = au._run_remove(
        type("A", (), {"app": "myapp", "force": False})(), d, TrackingSudo(), Reporter()
    )
    assert rc == 0

    all_deleted = [p for paths in delete_calls for p in paths]
    assert sys_path in all_deleted, "system path not routed through Deleter.delete"
    rm_calls = [c for c in sudo_calls if c and c[0] == "rm"]
    assert rm_calls == [], f"direct sudo rm call detected: {rm_calls}"
    aud.close()


def test_scope_for_path():
    """LaunchDaemons and /Library/LaunchAgents are system; user LaunchAgents are user."""
    assert au._scope_for_path("/Library/LaunchDaemons") == "system"
    assert au._scope_for_path("/Library/LaunchAgents") == "system"
    assert au._scope_for_path("/Users/someuser/Library/LaunchAgents") == "user"


def test_remove_no_leftovers_exits_early(fake_home):
    """When both user and system leftover lists are empty, _run_remove prints a message and returns."""
    from maccleaner.core import Auditor, Deleter

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(au, "_user_paths", lambda app: [])
        monkeypatch.setattr(au, "_system_paths", lambda app: [])

        aud = Auditor("app-empty", mode="dry-run")
        d = Deleter(aud, commit=False)
        rc = au._run_remove(
            type("A", (), {"app": "myapp", "force": False})(), d, None, Reporter()
        )
        assert rc == 0
        aud.close()
    finally:
        monkeypatch.undo()


def test_run_dispatches_app_remove(fake_home, monkeypatch):
    """run() with app_cmd='remove' calls _run_remove."""
    monkeypatch.setattr(au, "_run_remove", lambda args, d, s, r: 42)
    args = type(
        "A",
        (),
        {"app_cmd": "remove", "app": "myapp", "force": False},
    )()
    from maccleaner.core import Auditor, Deleter

    aud = Auditor("dispatch", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au.run(args, d, None, Reporter())
    assert rc == 42
    aud.close()


def test_run_dispatches_app_startup(fake_home, monkeypatch):
    monkeypatch.setattr(au, "_run_startup", lambda args, s, r: 5)
    args = type("A", (), {"app_cmd": "startup", "action": "list"})()
    from maccleaner.core import Auditor, Deleter

    aud = Auditor("dispatch2", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au.run(args, d, None, Reporter())
    assert rc == 5
    aud.close()


def test_run_unknown_app_cmd_returns_2(fake_home):
    from maccleaner.core import Auditor, Deleter

    args = type("A", (), {"app_cmd": "nonexistent"})()
    aud = Auditor("dispatch3", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au.run(args, d, None, Reporter())
    assert rc == 2
    aud.close()


def test_app_reset_dry_run(fake_home):
    """reset subcommand deletes prefs + Application Support in dry-run without removing."""
    from maccleaner.core import Auditor, Deleter

    aud = Auditor("app-reset", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au.run(
        type("A", (), {"app_cmd": "reset", "app": "myapp"})(), d, None, Reporter()
    )
    assert rc == 0
    assert (fake_home / "home" / "Applications" / "MyApp.app").exists()
    aud.close()


def test_list_apps_includes_size(fake_home):
    apps = au.list_apps()
    assert len(apps) == 1
    assert apps[0].size_kb >= 0


def test_find_app_by_bundle_id_case_insensitive(fake_home):
    a = au._find_app("com.example.myapp")
    assert a.bundle_id == "com.example.myapp"
    a = au._find_app("COM.EXAMPLE.MYAPP")
    assert a.bundle_id == "com.example.myapp"


def test_find_app_not_found_exits(fake_home):
    with pytest.raises(SystemExit):
        au._find_app("nonexistent.app")



# ─── orphan detection + purge ───────────────────────────────────────

@pytest.fixture
def orphan_home(tmp_path, monkeypatch):
    """Sandbox with a fake installed app and an orphaned launch agent.

    Note: does NOT depend on `fake_home` — this fixture overrides
    `CLEANMAC_HOME` and starts fresh.
    """
    home = tmp_path / "orphanhome"
    lib = home / "Library"
    # Idempotent create (tmp_path is fresh per test but defensive)
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "LaunchAgents").mkdir(parents=True, exist_ok=True)
    (home / "Applications").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLEANMAC_HOME", str(home))
    monkeypatch.setattr(au, "APP_DIRS", [str(home / "Applications")])

    # Installed app
    (home / "Applications" / "RealApp.app" / "Contents").mkdir(parents=True)
    with (home / "Applications" / "RealApp.app" / "Contents" / "Info.plist").open("wb") as f:
        plistlib.dump({"CFBundleName": "RealApp"}, f)

    # Live launch agent (matches installed app) — should NOT be flagged.
    # The exe path MUST exist for _is_orphan to recognize this as a live item.
    realapp_exe = home / "Applications" / "RealApp.app" / "Contents" / "MacOS" / "RealApp"
    realapp_exe.parent.mkdir(parents=True, exist_ok=True)
    realapp_exe.touch()
    (lib / "LaunchAgents" / "com.example.realapp.plist").write_bytes(
        plistlib.dumps({
            "Label": "com.example.realapp",
            "Program": str(realapp_exe),
        })
    )

    # Orphan: app bundle missing
    orphan_path = lib / "LaunchAgents" / "com.example.removed.plist"
    orphan_path.write_bytes(
        plistlib.dumps({
            "Label": "com.example.removed",
            "Program": str(home / "Applications" / "GhostApp.app" / "Contents" / "MacOS" / "GhostApp"),
        })
    )

    return tmp_path, orphan_path


def test_is_item_orphan_skips_live_agents(orphan_home):
    """An agent whose exe exists and whose label matches an installed app is live."""
    _, orphan_path = orphan_home
    # Live agent: label matches installed 'RealApp.app'.
    exe = str(orphan_path.with_suffix(".realapp"))
    assert au._is_item_orphan("com.example.realapp", exe, {"realapp.app"}) is False


def test_is_item_orphan_flags_missing_exe(orphan_home):
    """A removed agent with a missing exe and no matching app is orphan."""
    _, orphan_path = orphan_home
    assert au._is_item_orphan("com.example.removed", "/nonexistent/ghostapp", set()) is True


def test_orphans_purge_dry_run_leaves_files(orphan_home):
    """Without commit, _orphans_purge must NOT touch the plist or call launchctl.

    Builds an Orphan directly to avoid scanning the real /Library on the host.
    """
    tmp_path, orphan_path = orphan_home
    from subprocess import CompletedProcess

    class TrackingSudo:
        def __init__(self):
            self.calls = []
        def ensure(self):
            return False
        def run(self, args):
            self.calls.append(list(args))
            return CompletedProcess(args, 0, "", "")

    sudo = TrackingSudo()
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("orphan-dry", mode="dry-run")
    d = Deleter(aud, commit=False)

    # Inject Orphan directly — do NOT call find_orphans() in tests; the
    # sandbox cannot redirect /Library/LaunchAgents which is real on macOS.
    orphan = au.Orphan(
        label="com.example.removed",
        path=str(orphan_path),
        exe=str(orphan_path.with_suffix("")),
        scope="user",
    )
    rc = au._orphans_purge([orphan], d, sudo, Reporter())
    assert rc == 0
    assert orphan_path.exists(), "dry-run must not remove plist"
    assert sudo.calls == [], f"dry-run must not invoke sudo, got: {sudo.calls}"
    aud.close()


def test_orphans_purge_commit_moves_plist_to_quarantine(orphan_home):
    tmp_path, orphan_path = orphan_home
    from subprocess import CompletedProcess

    class TrackingSudo:
        def ensure(self):
            return False

        def run(self, args):
            # Simulate successful `mv` for user-scope items
            if args and args[0] == "mv":
                from pathlib import Path
                import shutil
                src = Path(args[1])
                dst = Path(args[2])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                return CompletedProcess(args, 0, "", "")
            return CompletedProcess(args, 0, "", "")

    # Stub launchctl.bootout to be a no-op
    import subprocess as real_subprocess
    def fake_run(*args, **kwargs):
        return real_subprocess.CompletedProcess(args, 0, "", "")
    import maccleaner.app_uninstaller as au_mod
    orig_run = au_mod.subprocess.run
    au_mod.subprocess.run = fake_run
    try:
        from maccleaner.core import Auditor, Deleter
        aud = Auditor("orphan-commit", mode="live")
        d = Deleter(aud, commit=True)
        d.confirm_fn = lambda _p: True  # auto-confirm

        # Build Orphan directly from the sandbox fixture — avoids the real
        # machine being scanned by find_orphans().
        orphan = au.Orphan(
            label="com.example.removed",
            path=str(orphan_path),
            exe=str(orphan_path.with_suffix("")),
            scope="user",
        )
        rc = au._orphans_purge([orphan], d, TrackingSudo(), Reporter())
        assert rc == 0
        assert not orphan_path.exists(), "plist must be moved out"
        # Verify quarantine copy exists
        quarantine = tmp_path / "orphanhome" / "Library" / "LaunchAgents-disabled"
        moved = list(quarantine.glob("com.example.removed*.plist"))
        assert moved, "plist not in quarantine"
        aud.close()
    finally:
        au_mod.subprocess.run = orig_run


def test_orphans_purge_empty_returns_zero():
    """No orphans -> 0 immediately, no I/O."""
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("orphan-empty", mode="dry-run")
    d = Deleter(aud, commit=False)
    rc = au._orphans_purge([], d, None, Reporter())
    assert rc == 0
    aud.close()


def test_orphans_purge_skips_missing_plist(orphan_home):
    """If plist disappears between detection and purge, skip + warn."""
    tmp_path, orphan_path = orphan_home
    orphan_path.unlink()

    from subprocess import CompletedProcess
    class NoopSudo:
        def ensure(self): return False
        def run(self, args):
            return CompletedProcess(args, 0, "", "")

    from maccleaner.core import Auditor, Deleter
    aud = Auditor("orphan-missing", mode="live")
    d = Deleter(aud, commit=True)
    d.confirm_fn = lambda _p: True

    orphan = au.Orphan(
        label="com.example.removed",
        path=str(orphan_path),
        exe=str(orphan_path.with_suffix("")),
        scope="user",
    )
    rc = au._orphans_purge([orphan], d, NoopSudo(), Reporter())
    assert rc == 0  # nothing to do, not an error
    aud.close()


def test_run_orphans_list_delegates_to_bba(orphan_home, monkeypatch):
    """_run_orphans routes list to the BBA engine."""
    captured = {}

    def fake_bba(args, deleter, sudo, reporter):
        captured["action"] = args.bba_action
        return 9

    monkeypatch.setattr(au, "_run_bba", fake_bba)
    args = type("A", (), {"orphans_action": "list"})()
    rc = au._run_orphans(args, None, None, Reporter())
    assert rc == 9
    assert captured["action"] == "list"


def test_run_orphans_purge_delegates_to_bba(orphan_home, monkeypatch):
    """_run_orphans purge routes through the BBA engine (dry-run no touch)."""
    captured = {}

    def fake_bba(args, deleter, sudo, reporter):
        captured["action"] = args.bba_action
        captured["commit"] = args.commit
        return 0

    monkeypatch.setattr(au, "_run_bba", fake_bba)
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("orphan-purge-dry", mode="dry-run")
    d = Deleter(aud, commit=False)
    args = type("A", (), {"orphans_action": "purge", "commit": False, "yes": False})()
    rc = au._run_orphans(args, d, None, Reporter())
    assert rc == 0
    assert captured["action"] == "purge"
    assert captured["commit"] is False
    aud.close()


def test_run_orphans_purge_unknown_action_returns_2(orphan_home):
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("orphan-unk", mode="dry-run")
    d = Deleter(aud, commit=False)
    args = type("A", (), {"orphans_action": "weird", "commit": False, "yes": False})()
    rc = au._run_orphans(args, d, None, Reporter())
    assert rc == 2
    aud.close()


# ── Task 7: collapse dual orphan engines ─────────────────────────────

def test_orphan_brands_constant_removed():
    """The hardcoded vendor/brand dictionary is gone."""
    assert not hasattr(au, "ORPHAN_BRANDS")


def test_run_orphans_delegates_to_bba_engine(orphan_home, monkeypatch):
    """app orphans list routes through the BBA/sfltool engine, not the
    legacy launch-plist walker."""
    captured = {"n": 0}

    def fake_bba(args, *a, **kw):
        captured["n"] += 1
        assert args.bba_action == "list"
        return 0

    monkeypatch.setattr(au, "_run_bba", fake_bba)
    args = type("A", (), {"orphans_action": "list"})()
    rc = au._run_orphans(args, None, None, Reporter())
    assert rc == 0
    assert captured["n"] == 1


def test_legacy_find_orphans_removed():
    """The regex/brand-based find_orphans() is gone (single engine)."""
    assert not hasattr(au, "find_orphans")
    assert not hasattr(au, "_is_orphan")
    assert not hasattr(au, "get_installed_app_names")
    assert not hasattr(au, "ORPHAN_BRANDS")
