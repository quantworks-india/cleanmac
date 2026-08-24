"""Tests for the brew + helpers scanners (Task 1 & 2)."""

from __future__ import annotations


import pytest

from maccleaner import app_uninstaller as au


def _fake_brew(tmp_path, monkeypatch, *, casks=(), cellars=(), prefix=None):
    """Create a fake Homebrew prefix with the given Caskroom/Cellar trees."""
    pfx = tmp_path / ("brew" + (("-" + prefix) if prefix else ""))
    monkeypatch.setenv("CLEANMAC_BREW_PREFIX", str(pfx))
    if casks:
        (pfx / "Caskroom").mkdir(parents=True, exist_ok=True)
        for name in casks:
            (pfx / "Caskroom" / name).mkdir(parents=True, exist_ok=True)
    if cellars:
        (pfx / "Cellar").mkdir(parents=True, exist_ok=True)
        for name in cellars:
            (pfx / "Cellar" / name).mkdir(parents=True, exist_ok=True)
    return pfx


@pytest.mark.parametrize("has_brew", [True, False])
def test_brew_paths_uses_prefix_or_empty(tmp_path, monkeypatch, has_brew):
    """brew_paths follows _brew_prefix(); empty prefix -> no paths."""
    monkeypatch.setattr(au, "_brew_prefix", lambda: str(tmp_path / "brew") if has_brew else "")
    if not has_brew:
        assert au.brew_paths("com.example.myapp", "MyApp") == []
        return
    pfx = tmp_path / "brew"
    (pfx / "Caskroom").mkdir(parents=True, exist_ok=True)
    (pfx / "Caskroom" / "myapp").mkdir(parents=True, exist_ok=True)
    got = au.brew_paths("com.example.myapp", "MyApp")
    assert any("Caskroom/myapp" in p for p in got)


def test_brew_paths_never_returns_brew_roots(tmp_path, monkeypatch):
    """An empty/None name or bundle id must not match the Caskroom/Cellar
    roots themselves (bundle_id.split[-1] of '' is '', and os.path.join
    collapses to the root — a whole-Homebrew deletion bug)."""
    _fake_brew(tmp_path, monkeypatch, casks=["myapp"], cellars=["myapp"])
    assert au.brew_paths("", "Chrome") == []
    assert au.brew_paths("com.google.Chrome", "") == []
    assert au.brew_paths("", "") == []


def test_list_apps_includes_brew_cask_bundles(tmp_path, monkeypatch):
    """Apps installed as brew casks (in Caskroom) appear in list_apps even
    when their /Applications symlink is broken or absent."""
    pfx = tmp_path / "brew"
    ck = pfx / "Caskroom" / "google-chrome" / "1.0"
    ck.mkdir(parents=True)
    bundle = ck / "Google Chrome.app" / "Contents"
    bundle.mkdir(parents=True)
    (bundle / "Info.plist").write_bytes(
        __import__("plistlib").dumps({
            "CFBundleName": "Google Chrome",
            "CFBundleIdentifier": "com.google.Chrome",
        })
    )
    monkeypatch.setattr(au, "_brew_prefix", lambda: str(pfx))
    # No /Applications symlink; Caskroom is the only source.
    monkeypatch.setattr(au, "_candidate_dirs", lambda: [])
    apps = au.list_apps()
    assert any(a.name == "Google Chrome" for a in apps)
    assert any("Caskroom" in a.path for a in apps)


def test_brew_paths_matches_cask_and_cellar(tmp_path, monkeypatch):
    """Returns both the Caskroom app and the matching Cellar formula."""
    _fake_brew(tmp_path, monkeypatch, casks=["myapp", "other"], cellars=["myapp"])
    got = au.brew_paths("com.example.myapp", "MyApp")
    assert any("Caskroom/myapp" in p for p in got)
    assert any("Cellar/myapp" in p for p in got)
    assert not any("other" in p for p in got)


def test_brew_paths_no_match(tmp_path, monkeypatch):
    _fake_brew(tmp_path, monkeypatch, casks=["unrelated"])
    assert au.brew_paths("com.example.myapp", "MyApp") == []


def test_helpers_paths_matches_vendor_prefix(tmp_path, monkeypatch):
    """PrivilegedHelperTools entries matching the vendor prefix are found."""
    d = tmp_path / "helpers"
    d.mkdir(parents=True, exist_ok=True)
    (d / "us.zoom.ZoomDaemon").write_text("x")
    (d / "com.other.thing").write_text("x")
    monkeypatch.setattr(au, "_helper_dir", lambda: str(d))
    got = au.helper_paths("us.zoom.xos", "zoom.us")
    assert any("us.zoom.ZoomDaemon" in p for p in got)
    assert not any("com.other" in p for p in got)


def test_helpers_paths_no_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "_helper_dir", lambda: str(tmp_path / "nonexistent"))
    assert au.helper_paths("us.zoom.xos", "zoom.us") == []
