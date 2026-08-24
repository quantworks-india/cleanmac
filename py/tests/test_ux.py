"""Human uninstall screens: compact flags, no debug dump, 80-col fit."""

from __future__ import annotations

from maccleaner import app_uninstaller as au


def _matrix(**yes):
    m = {
        "app": "N",
        "mas": "—",
        "pkg": "N",
        "brew": "N",
        "support": "N",
        "cache": "N",
        "prefs": "N",
        "container": "N",
        "saved": "N",
        "agents": "N",
        "daemons": "N",
        "helpers": "N",
        "kext": "—",
        "btm": "—",
    }
    m.update(yes)
    return m


def test_leftover_flags_only_y_cleanable():
    flags = au._leftover_flags(_matrix(app="Y", mas="Y", support="Y", prefs="Y"))
    assert flags == ["support", "prefs"]


def test_picker_label_puts_flags_after_name():
    line = au._picker_label("Firefox", ["support", "prefs"])
    assert line.startswith("Firefox")
    assert "support" in line and "prefs" in line
    assert "info" not in line


def test_human_plan_has_no_debug_dump():
    target = au.UninstallTarget(
        "Firefox", "org.mozilla.firefox", "/Applications/Firefox.app", True, "Firefox"
    )
    text = au._human_plan(
        target,
        _matrix(app="Y", mas="Y", support="Y", prefs="Y"),
        [
            "/Users/sandeep/Library/Application Support/Firefox",
            "/Users/sandeep/Library/Preferences/org.mozilla.firefox.plist",
        ],
        home="/Users/sandeep",
    )
    assert "uninstall_plan" not in text
    assert "matrix=" not in text
    assert "info" not in text
    assert "Firefox" in text
    assert "org.mozilla.firefox" in text
    assert "support" in text and "prefs" in text
    assert "~/Library/Application Support/Firefox" in text


def test_human_plan_header_fits_80_cols():
    target = au.UninstallTarget(
        "Firefox", "org.mozilla.firefox", "/Applications/Firefox.app", True, "Firefox"
    )
    text = au._human_plan(
        target,
        _matrix(app="Y", mas="Y", support="Y", prefs="Y"),
        ["~/Library/Application Support/Firefox"],
        home="/Users/sandeep",
    )
    for line in text.splitlines():
        if line.strip().startswith("~") or line.strip().startswith("/"):
            continue
        assert len(line) <= 80, repr(line)


def test_picker_paint_has_title_and_keys():
    text, n = au._picker_paint(
        ["Firefox  support  prefs"],
        idx=0,
        start=0,
        end=1,
        prev_lines=0,
        filter_text="",
        count=12,
    )
    assert "uninstall" in text.lower()
    assert "enter" in text.lower() or "select" in text.lower()
    assert n >= 3
