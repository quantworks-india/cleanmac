"""Tests for helper→parent attribution from Apple's attributions.plist.

`attributions.plist` maps launchd labels / program paths to the parent app's
associated bundle identifiers. We load it with plistlib and expose a small,
testable lookup — no brand dictionaries, no regex.
"""

from __future__ import annotations

import plistlib

import pytest

from maccleaner import attributions


# Minimal, PII-free attributions plist.
FIXTURE = {
    "com.example.foohelper": {
        "AssociatedBundleIdentifiers": ["com.example.foo"],
        "Attribution": "Example Foo",
        "TeamIdentifier": "TEAM123",
    },
    "com.example.baragent": {
        "AssociatedBundleIdentifiers": ["com.example.bar", "com.example.foo"],
        "Attribution": "Example Bar",
    },
}


@pytest.fixture
def fake_attributions(tmp_path, monkeypatch):
    p = tmp_path / "attributions.plist"
    with p.open("wb") as f:
        plistlib.dump(FIXTURE, f)
    monkeypatch.setattr(attributions, "_ATTRIBUTIONS_PATH", str(p))
    attributions.reset_cache()
    yield p
    attributions.reset_cache()


def test_parents_for_label(fake_attributions):
    parents = attributions.parents_for_label("com.example.foohelper")
    assert "com.example.foo" in parents


def test_parents_for_unknown_label_is_empty(fake_attributions):
    assert attributions.parents_for_label("com.unknown.thing") == set()


def test_team_id_lookup(fake_attributions):
    assert attributions.parents_for_team("0123") == set()
    assert attributions.parents_for_team("TEAM123") == {"com.example.foo"}


def test_missing_file_returns_empty(monkeypatch):
    monkeypatch.setattr(attributions, "_ATTRIBUTIONS_PATH", "/nonexistent/attributions.plist")
    attributions.reset_cache()
    assert attributions.parents_for_label("anything") == set()


def test_malformed_file_returns_empty(tmp_path, monkeypatch):
    bad = tmp_path / "attributions.plist"
    bad.write_bytes(b"not a plist")
    monkeypatch.setattr(attributions, "_ATTRIBUTIONS_PATH", str(bad))
    attributions.reset_cache()
    assert attributions.parents_for_label("anything") == set()


def test_cache_hits_same_parsed_map(fake_attributions):
    """parents_for_label and parents_for_team reuse one loaded map."""
    assert attributions.parents_for_label("com.example.foohelper") == {"com.example.foo"}
    assert attributions.parents_for_team("TEAM123") == {"com.example.foo"}
    # The loader uses lru_cache; a repeated call must not raise and must agree.
    assert attributions.parents_for_label("com.example.foohelper") == {"com.example.foo"}
