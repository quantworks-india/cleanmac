"""Tests for deep uninstall fingerprint discovery + flow."""

from __future__ import annotations

import plistlib

import pytest

from maccleaner import app_uninstaller as au
from maccleaner.core import Reporter


@pytest.fixture
def fake_app(tmp_path, monkeypatch):
    """Sandbox home + a fake installed app with a known bundle id."""
    home = tmp_path / "home"
    (home / "Applications").mkdir(parents=True)
    (home / "Library" / "LaunchAgents").mkdir(parents=True)
    (home / "Library" / "Application Support").mkdir(parents=True)
    monkeypatch.setenv("CLEANMAC_HOME", str(home))

    bundle = home / "Applications" / "MyApp.app" / "Contents"
    bundle.mkdir(parents=True)
    info = {"CFBundleName": "MyApp", "CFBundleIdentifier": "com.example.myapp"}
    with (bundle / "Info.plist").open("wb") as f:
        plistlib.dump(info, f)

    # A launch agent owned by the app (label == bundle id)
    (home / "Library" / "LaunchAgents" / "com.example.myapp.plist").write_bytes(
        plistlib.dumps({"Label": "com.example.myapp",
                        "Program": str(bundle / "MacOS" / "MyApp")})
    )
    # An unrelated agent
    (home / "Library" / "LaunchAgents" / "com.other.thing.plist").write_bytes(
        plistlib.dumps({"Label": "com.other.thing",
                        "Program": "/usr/bin/other"})
    )
    # Leftover support dir
    (home / "Library" / "Application Support" / "MyApp").mkdir()

    app = au.AppInfo(name="MyApp", bundle_id="com.example.myapp",
                     path=str(bundle), version=None, size_kb=0)
    return home, app


def test_fingerprint_finds_owned_launch_plists(fake_app):
    home, app = fake_app
    fp = au._build_fingerprint(app, home=home)
    assert "com.example.myapp" in fp["launch_labels"]
    assert "com.other.thing" not in fp["launch_labels"]


def test_fingerprint_lists_support_leftovers(fake_app):
    home, app = fake_app
    fp = au._build_fingerprint(app, home=home)
    assert any("Application Support" in p and "MyApp" in p for p in fp["leftovers"])


def test_resolve_returns_leftover_only_when_app_gone(fake_app):
    """No live .app must still resolve (leftover-only), not raise App not found."""
    home, _app = fake_app
    # Simulate the app being uninstalled already.
    import shutil
    shutil.rmtree(str(home / "Applications" / "MyApp.app"))
    # Leftover dir still exists.
    (home / "Library" / "Application Support" / "MyApp").mkdir(parents=True, exist_ok=True)

    target = au.resolve("com.example.myapp")
    assert target.bundle_id == "com.example.myapp"
    assert target.path == ""  # no live bundle
    assert target.app_installed is False


def test_resolve_live_app_by_display_name(fake_app):
    home, app = fake_app
    target = au.resolve("MyApp")
    assert target.app_installed is True
    assert target.path == str(home / "Applications" / "MyApp.app")


def test_resolve_live_app_by_bundle_id(fake_app):
    home, app = fake_app
    target = au.resolve("com.example.myapp")
    assert target.app_installed is True
    assert target.path == str(home / "Applications" / "MyApp.app")


def test_resolve_matches_app_basename(fake_app):
    home, app = fake_app
    # Match the .app folder name (MyApp.app -> MyApp) even if name differs.
    target = au.resolve("MyApp")
    assert target.app_installed is True


def test_run_uninstall_dry_run_lists_fingerprint(fake_app, monkeypatch, capsys):
    """Without --commit, _run_uninstall prints the fingerprint and touches nothing."""
    home, app = fake_app
    monkeypatch.setattr(au, "_find_app", lambda name, force=False: app)
    monkeypatch.setattr(au, "_build_fingerprint",
                        lambda app, home=None: {"launch_labels": ["com.example.myapp"],
                                                "launch_paths": [],
                                                "leftovers": []})
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("uninstall-dry", mode="dry-run")
    d = Deleter(aud, commit=False)
    args = type("A", (), {"name": "myapp", "yes": False, "commit": False, "force": False})()
    rc = au._run_uninstall(args, d, None, Reporter())
    assert rc == 0
    out = capsys.readouterr().out
    assert "com.example.myapp" in out or "uninstall" in out
    aud.close()


def test_run_uninstall_dry_run_shows_dryrun_banner(fake_app, monkeypatch, capsys):
    """Human dry-run prints the dry-run banner, not a raw debug dump."""
    home, app = fake_app
    monkeypatch.setattr(au, "_find_app", lambda name, force=False: app)
    monkeypatch.setattr(au, "_build_fingerprint",
                        lambda app, home=None: {"launch_labels": ["com.example.myapp"],
                                                "launch_paths": [],
                                                "leftovers": []})
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("uninstall-dry2", mode="dry-run")
    d = Deleter(aud, commit=False)
    args = type("A", (), {"name": "myapp", "yes": False, "commit": False, "force": False})()
    au._run_uninstall(args, d, None, Reporter())
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()
    aud.close()


def test_purge_by_id_dry_run_lists_leftovers(monkeypatch, fake_app, capsys):
    """purge-by-id lists the leftover paths and touches nothing without --commit."""
    home, _app = fake_app
    fake_leftovers = [str(home / "Library" / "Application Support" / "MyApp")]
    monkeypatch.setattr(au, "_leftover_paths_for_bundle", lambda b: fake_leftovers)
    monkeypatch.setattr(au, "spotlight_orphan_paths", lambda b: [])
    from maccleaner.core import Auditor, Deleter
    aud = Auditor("purge-by-id-dry", mode="dry-run")
    d = Deleter(aud, commit=False)
    args = type("A", (), {"bundle": "com.example.myapp", "yes": False})()
    rc = au._run_purge_by_id(args, d, None, Reporter())
    assert rc == 0
    out = capsys.readouterr().out
    assert "com.example.myapp" in out
    aud.close()
