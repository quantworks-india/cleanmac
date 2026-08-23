"""Tests for the boolean uninstall matrix (Task 3)."""

from __future__ import annotations

from maccleaner import app_uninstaller as au


def _matrix(target, fp=None):
    if fp is None:
        fp = {
            "leftovers": [],
            "system_paths": [],
            "launch_paths": [],
            "launch_labels": [],
            "brew": [],
            "helpers": [],
            "bba": [],
        }
    return au._build_matrix(target, fp)


def test_matrix_flags_app_installed():
    t = au.UninstallTarget("MyApp", "com.example.myapp", "/Applications/MyApp.app", True, "MyApp")
    fp = {"leftovers": [], "system_paths": [], "brew": [], "helpers": [],
          "launch_paths": [], "launch_labels": []}
    m = au._build_matrix(t, fp)
    assert m["app"] == "Y"
    assert m["mas"] == "Y"  # receipt lives in the live bundle


def test_matrix_mas_is_dash_when_gone():
    t = au.UninstallTarget("MyApp", "com.example.myapp", "", False, "MyApp")
    m = _matrix(t)
    assert m["app"] == "N"
    assert m["mas"] == "—"


def test_matrix_counts_leftovers_by_kind():
    t = au.UninstallTarget("MyApp", "com.example.myapp", "", False, "MyApp")
    fp = {
        "leftovers": ["/h/Library/Application Support/MyApp"],
        "system_paths": [],
        "brew": ["/opt/homebrew/Caskroom/myapp"],
        "helpers": ["/Library/PrivilegedHelperTools/com.example.myapp.helper"],
        "launch_paths": [],
        "launch_labels": [],
    }
    m = au._build_matrix(t, fp)
    assert m["support"] == "Y"
    assert m["brew"] == "Y"
    assert m["helpers"] == "Y"


def test_matrix_kext_and_btm_are_never_touched():
    t = au.UninstallTarget("MyApp", "com.example.myapp", "", False, "MyApp")
    m = _matrix(t)
    assert m["kext"] == "—"
    assert m["btm"] == "—"
