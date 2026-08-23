"""Tests for BBA (Background App Activity) detection.

Mocks `sfltool dumpbtm` so tests are deterministic and don't need macOS.
"""

from __future__ import annotations


import pytest

from maccleaner import bba


SAMPLE_DUMPBTM = """\
========================
 Records for UID 501 : C35DD71D-7B6B-4521-9DE7-617ED61C8D21
========================

 Items:

 #1:
                 UUID: AAAA-1111
                Name: Zoom
      Developer Name: Zoom
     Team Identifier: BJ4HAAB9B3
                Type: legacy daemon (0x10010)
               Flags: [ legacy ] (0x1)
         Disposition: [enabled, allowed, notified] (0xb)
            Identifier: 16.us.zoom.ZoomDaemon
                 URL: /Library/LaunchDaemons/us.zoom.ZoomDaemon.plist
     Executable Path: /Library/PrivilegedHelperTools/us.zoom.ZoomDaemon

 #2:
                 UUID: BBBB-2222
                Name: Hermes
      Developer Name: Nous Research
                Type: app (0x2)
               Flags: [  ] (0x0)
         Disposition: [enabled, allowed, notified] (0xb)
            Identifier: 8.com.nousresearch.hermes
                 URL: /Users/test/.hermes/Hermes.app
     Executable Path: /Users/test/.hermes/Hermes.app/Contents/MacOS/Hermes

 #3:
                 UUID: CCCC-3333
                Name: Avast Hub
      Developer Name: Avast
                Type: legacy agent (0x10008)
               Flags: [ legacy ] (0x1)
         Disposition: [enabled, allowed, notified] (0xb)
            Identifier: 8.com.avast.hub
                 URL: /Library/LaunchAgents/com.avast.hub.plist
     Executable Path: /Library/Application Support/AvastHUB/com.avast.hub.app/Contents/MacOS/com.avast.hub
 Assoc. Bundle IDs: [ com.avast.helper ]

 #4:
                 UUID: DDDD-4444
                Name: Broken Weather
      Developer Name: (null)
                Type: developer (0x20)
               Flags: [  ] (0x0)
         Disposition: [enabled, allowed, notified] (0xb)
            Identifier: 16.com.apple.weather.menu
                 URL: Contents/Library/LoginItems/WeatherMenu.app
     Executable Path: (null)
"""


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Sandbox with a real installed 'hermes.app' for positive matching."""
    home = tmp_path / "home"
    (home / "Applications").mkdir(parents=True)
    monkeypatch.setenv("CLEANMAC_HOME", str(home))

    # Real bundle with Info.plist
    bundle = home / "Applications" / "Hermes.app" / "Contents"
    bundle.mkdir(parents=True)
    (bundle / "Info.plist").write_text("placeholder")

    return home


@pytest.fixture
def stub_sfltool(monkeypatch):
    """Replace the actual sfltool call with our canned dump."""
    monkeypatch.setattr(bba, "_run_sfltool_dumpbtm", lambda: SAMPLE_DUMPBTM)


def test_parse_dumpbtm_extracts_all_items(stub_sfltool):
    items = bba.list_all_bba_items()
    assert len(items) == 4
    labels = {it.label for it in items}
    assert labels == {
        "us.zoom.ZoomDaemon",
        "com.nousresearch.hermes",
        "com.avast.hub",
        "com.apple.weather.menu",
    }


def test_parse_dumpbtm_extracts_bundle_ids(stub_sfltool):
    items = bba.list_all_bba_items()
    avast = next(it for it in items if it.label == "com.avast.hub")
    assert avast.associated_bundle_ids == ["com.avast.helper"]


def test_parse_dumpbtm_extracts_scope(stub_sfltool):
    items = bba.list_all_bba_items()
    by_label = {it.label: it for it in items}
    assert by_label["us.zoom.ZoomDaemon"].scope == "system"
    assert by_label["com.nousresearch.hermes"].scope == "user"
    assert by_label["com.apple.weather.menu"].scope == "system"  # 16.* = system


def test_find_bba_orphans_flags_uninstalled_app(fake_home, monkeypatch, tmp_path):
    """Avast exe/plist missing in sandbox -> orphan."""
    # Point Avast's exe at a nonexistent sandbox path (no real /Library leak).
    dump = SAMPLE_DUMPBTM.replace(
        "Executable Path: /Library/Application Support/AvastHUB/com.avast.hub.app/Contents/MacOS/com.avast.hub",
        f"Executable Path: {tmp_path}/no-avast-hub",
    )
    monkeypatch.setattr(bba, "_run_sfltool_dumpbtm", lambda: dump)
    monkeypatch.setattr(bba, "fetch_state", lambda it: "?")
    # Isolate installed inventory (empty so no name-match rescues Avast).
    monkeypatch.setattr(bba.inventory, "installed_app_names", lambda: set())
    orphans = bba.find_bba_orphans()
    labels = {o.label for o in orphans}
    assert "com.avast.hub" in labels


def test_find_bba_orphans_keeps_live_app(fake_home, monkeypatch, tmp_path):
    """Hermes is live when its executable exists on disk (mechanical)."""
    hermes_exe = tmp_path / "Hermes"
    hermes_exe.write_text("x")
    dump = SAMPLE_DUMPBTM.replace(
        "Executable Path: /Users/test/.hermes/Hermes.app/Contents/MacOS/Hermes",
        f"Executable Path: {hermes_exe}",
    )
    monkeypatch.setattr(bba, "_run_sfltool_dumpbtm", lambda: dump)
    monkeypatch.setattr(bba, "fetch_state", lambda it: "?")
    monkeypatch.setattr(bba.inventory, "installed_app_names", lambda: set())
    orphans = bba.find_bba_orphans()
    labels = {o.label for o in orphans}
    assert "com.nousresearch.hermes" not in labels


def test_find_bba_orphans_flags_broken_relative_plist(stub_sfltool, fake_home, monkeypatch):
    """com.apple.weather.menu has a relative plist URL -> not a real path -> orphan."""
    monkeypatch.setattr(bba, "fetch_state", lambda it: "?")
    monkeypatch.setattr(bba.inventory, "installed_app_names", lambda: set())
    orphans = bba.find_bba_orphans()
    labels = {o.label for o in orphans}
    assert "com.apple.weather.menu" in labels


def test_find_bba_orphans_keeps_zoom(stub_sfltool, fake_home, monkeypatch, tmp_path):
    """Zoom's plist/exe exists on disk -> not orphan."""
    zoom_exe = tmp_path / "us.zoom.ZoomDaemon"
    zoom_exe.write_text("x")
    dump = SAMPLE_DUMPBTM.replace(
        "Executable Path: /Library/PrivilegedHelperTools/us.zoom.ZoomDaemon",
        f"Executable Path: {zoom_exe}",
    )
    monkeypatch.setattr(bba, "_run_sfltool_dumpbtm", lambda: dump)
    monkeypatch.setattr(bba, "fetch_state", lambda it: "?")
    monkeypatch.setattr(bba.inventory, "installed_app_names", lambda: set())
    orphans = bba.find_bba_orphans()
    labels = {o.label for o in orphans}
    assert "us.zoom.ZoomDaemon" not in labels


def test_sfltool_not_found_raises(tmp_path, monkeypatch):
    """If sfltool isn't on PATH, surface a clear error."""
    monkeypatch.setattr(bba.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="sfltool"):
        bba._run_sfltool_dumpbtm()


def test_run_sfltool_failure_raises(monkeypatch):
    """Non-zero exit from sfltool -> RuntimeError with stderr."""
    class FakeRun:
        returncode = 1
        stderr = "boom"
    monkeypatch.setattr(bba.shutil, "which", lambda _name: "/usr/bin/sfltool")
    monkeypatch.setattr(
        bba.subprocess, "run",
        lambda *a, **kw: FakeRun(),
    )
    with pytest.raises(RuntimeError, match="sfltool dumpbtm failed"):
        bba._run_sfltool_dumpbtm()


# ── Task 5: line-state parser, no regex ─────────────────────────────

def test_bba_module_does_not_import_re():
    """bba.py must not depend on the re module for dumpbtm parsing."""
    assert not hasattr(bba, "re"), "bba.py still imports re"


def test_orphan_uses_attributions_not_brands(monkeypatch):
    """A helper with no attributions parent and no live exe/plist is orphan,
    regardless of brand name. No ORPHAN_BRANDS lookup."""
    item = bba.BbaItem(
        name="Generic Helper",
        developer="Acme",
        identifier="16.com.acme.helper",
        plist_url="",
        executable_path="",
        disposition="",
    )
    assert bba._is_bba_orphan(item, set()) is True
    assert not hasattr(bba, "ORPHAN_BRANDS")


def test_orphan_live_when_attribution_installed(monkeypatch):
    """If attributions maps the helper's bundle to an installed app, it's live."""
    item = bba.BbaItem(
        name="Foo Helper",
        developer="Foo",
        identifier="8.com.foo.helper",
        plist_url="",
        executable_path="",
        disposition="",
        associated_bundle_ids=["com.example.foo"],
    )
    # installed_apps contains the parent bundle id name
    installed = {"com.example.foo.app", "other.app"}
    assert bba._is_bba_orphan(item, installed) is False


def test_orphan_live_when_exe_exists(monkeypatch, tmp_path):
    exe = tmp_path / "bin"
    exe.mkdir()
    exe_file = exe / "helper"
    exe_file.write_text("x")
    item = bba.BbaItem(
        name="H",
        developer="",
        identifier="8.com.h.helper",
        plist_url="",
        executable_path=str(exe_file),
        disposition="",
    )
    assert bba._is_bba_orphan(item, set()) is False


def test_orphan_flagged_when_exe_missing(monkeypatch, tmp_path):
    item = bba.BbaItem(
        name="Gone",
        developer="",
        identifier="8.com.gone.helper",
        plist_url="",
        executable_path=str(tmp_path / "missing" / "bin"),
        disposition="",
    )
    assert bba._is_bba_orphan(item, set()) is True


def test_find_bba_orphans_mechanical_no_brands(monkeypatch, tmp_path):
    """find_bba_orphans is mechanical: file existence decides, not brand names.

    Avast's exe/plist don't exist in the sandbox -> orphan even though we
    DON'T hardcode Avast. An item whose exe exists -> not orphan.
    """
    # Point every item's exe at a sandbox path so no real /Library leaks in.
    dump = SAMPLE_DUMPBTM
    # Zoom gets a live executable in the sandbox -> NOT orphan.
    zoom_exe = tmp_path / "us.zoom.ZoomDaemon"
    zoom_exe.write_text("x")
    # Avast exe -> sandbox path that does NOT exist -> orphan.
    dump = dump.replace(
        "Executable Path: /Library/PrivilegedHelperTools/us.zoom.ZoomDaemon",
        f"Executable Path: {zoom_exe}",
    )
    dump = dump.replace(
        "Executable Path: /Library/Application Support/AvastHUB/com.avast.hub.app/Contents/MacOS/com.avast.hub",
        f"Executable Path: {tmp_path}/no-such-avast-hub",
    )
    monkeypatch.setattr(bba, "_run_sfltool_dumpbtm", lambda: dump)
    monkeypatch.setattr(bba, "fetch_state", lambda it: "?")
    monkeypatch.setattr(bba.inventory, "installed_app_names",
                        lambda: {"hermes.app", "zoom.us.app"})
    orphans = bba.find_bba_orphans()
    labels = {o.label for o in orphans}
    # Avast exe missing -> orphan (no brand map needed).
    assert "com.avast.hub" in labels
    assert "com.apple.weather.menu" in labels  # relative plist -> orphan
    # Zoom exe exists -> not orphan.
    assert "us.zoom.ZoomDaemon" not in labels



def test_parse_field_line_uses_partition(stub_sfltool):
    """A Key: value line is parsed via partition(':'), not a regex."""
    line = "                 Identifier: 16.us.zoom.ZoomDaemon"
    key, sep, val = bba._split_field_line(line)
    assert sep == ":"
    assert key == "Identifier"
    assert val == "16.us.zoom.ZoomDaemon"
