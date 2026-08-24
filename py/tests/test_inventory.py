"""Tests for the installed-app inventory built from system_profiler JSON.

The inventory must come from structured JSON, not a `*.app` glob, so that
non-standard installs (e.g. Hermes under ~/.hermes) and /System apps are
captured. No regex, no filesystem glob in the happy path.
"""

from __future__ import annotations


import pytest

from maccleaner import inventory


# Minimal, PII-free sample of `system_profiler SPApplicationsDataType -json`.
SAMPLE_JSON = {
    "SPApplicationsDataType": [
        {
            "_name": "Safari",
            "path": "/System/Applications/Safari.app",
            "obtained_from": "apple",
        },
        {
            "_name": "Zoom",
            "path": "/Users/tester/Applications/zoom.us.app",
            "obtained_from": "downloaded",
        },
        {
            "_name": "Visual Studio Code",
            "path": "/Applications/Visual Studio Code.app",
            "obtained_from": "downloaded",
        },
        {
            "_name": "Hermes",
            "path": "/Users/tester/.hermes/Hermes.app",
            "obtained_from": "downloaded",
        },
    ]
}


@pytest.fixture
def fake_profiler(monkeypatch):
    """Route the inventory loader to canned system_profiler output."""
    def _load() -> dict:
        return SAMPLE_JSON

    monkeypatch.setattr(inventory, "_load_system_profiler_json", _load)
    inventory.reset_cache()
    yield
    inventory.reset_cache()


def test_installed_app_names_from_json(fake_profiler):
    names = inventory.installed_app_names()
    assert "zoom.us.app" in names
    assert "safari.app" in names
    assert "visual studio code.app" in names
    assert "hermes.app" in names


def test_names_are_lowercase(fake_profiler):
    names = inventory.installed_app_names()
    assert all(n == n.lower() for n in names)


def test_paths_expose_app_dir(fake_profiler):
    apps = inventory.list_installed_apps()
    assert any(a.name == "Zoom" and a.path.endswith("zoom.us.app") for a in apps)


def test_inventory_is_cached_across_calls(fake_profiler, monkeypatch):
    calls = {"n": 0}
    orig = inventory._load_system_profiler_json

    def counting() -> dict:
        calls["n"] += 1
        return orig()

    monkeypatch.setattr(inventory, "_load_system_profiler_json", counting)
    inventory.reset_cache()
    inventory.installed_app_names()
    inventory.installed_app_names()
    assert calls["n"] == 1, "profiler should only be queried once per process"


def test_reset_cache_forces_refetch(fake_profiler, monkeypatch):
    calls = {"n": 0}
    orig = inventory._load_system_profiler_json

    def counting() -> dict:
        calls["n"] += 1
        return orig()

    monkeypatch.setattr(inventory, "_load_system_profiler_json", counting)
    inventory.reset_cache()
    inventory.installed_app_names()
    inventory.reset_cache()
    inventory.installed_app_names()
    assert calls["n"] == 2, "reset_cache should force a fresh fetch"


def test_fallback_glob_when_profiler_missing(monkeypatch, tmp_path):
    """If system_profiler fails, fall back to a directory glob (no crash)."""
    app_dir = tmp_path / "Applications"
    (app_dir / "Sample.app" / "Contents").mkdir(parents=True)
    (app_dir / "Sample.app" / "Contents" / "Info.plist").write_text("x")

    monkeypatch.setattr(
        inventory, "_load_system_profiler_json", lambda: (_ for _ in ()).throw(RuntimeError("no profiler"))
    )
    monkeypatch.setattr(inventory, "APP_DIRS", [str(app_dir)])
    inventory.reset_cache()
    names = inventory.installed_app_names()
    assert "sample.app" in names
    inventory.reset_cache()


def test_empty_profiler_result_yields_no_names(monkeypatch):
    monkeypatch.setattr(inventory, "_load_system_profiler_json", lambda: {})
    inventory.reset_cache()
    assert inventory.installed_app_names() == set()
    inventory.reset_cache()
