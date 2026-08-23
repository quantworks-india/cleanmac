"""Tests for Spotlight-based orphan leftover scan."""

from __future__ import annotations

from maccleaner import spotlight as sp


def test_find_bundle_paths_returns_list():
    items = sp.find_bundle_paths("dev.zcode.app")
    assert isinstance(items, list)
    # ZCode.app is installed; Spotlight must find at least the bundle itself.
    path_strs = "\n".join(items)
    assert "ZCode.app" in path_strs


def test_find_bundle_paths_empty_bundle_returns_empty():
    items = sp.find_bundle_paths("definitely.does.not.exist.x123")
    assert items == []


def test_find_bundle_paths_invalid_input_returns_empty():
    assert sp.find_bundle_paths("") == []
    assert sp.find_bundle_paths("a;b|rm -rf /") == []
