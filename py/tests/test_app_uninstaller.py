"""Tests for app_uninstaller — leftover discovery, bundle-ID matching, safety."""

from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from maccleaner import app_uninstaller as au


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
    rc = au._run_remove(type("A", (), {"app": "myapp", "force": False})(), d, None)
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
        type("A", (), {"app": "myapp", "force": False})(), d, TrackingSudo()
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
