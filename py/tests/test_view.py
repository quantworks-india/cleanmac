"""Tests for the display-layer primitives (stdlib, no third-party deps)."""

from __future__ import annotations


from maccleaner import view


def test_table_aligns_columns():
    out = view.table(
        ["Name", "Size"],
        [["Alpha", "1.2 GB"], ["A much longer name", "12 B"]],
    )
    lines = out.splitlines()
    assert "Name" in lines[0]
    # Column 2 (data) aligns: header 'Size', '1.2 GB', '12 B' same x
    x = lines[0].index("Size")
    assert x == lines[2].index("1.2 GB")
    assert x == lines[3].index("12 B")


def test_table_empty_rows_renders_none():
    out = view.table(["Name", "Size"], [])
    assert "(none)" in out


def test_section_renders_header():
    out = view.section("Uninstall Code")
    assert "Uninstall Code" in out


def test_status_line():
    assert view.status("ok", "Cleaned 3 items", enabled=False) == "ok  Cleaned 3 items"


def test_human_size():
    assert view.human_size(0) == "0 B"
    assert view.human_size(1536) == "1.5 KB"
    assert view.human_size(2 * 1024 * 1024) == "2.0 MB"


def test_color_wrap_noop_when_disabled():
    assert view.color("bold", "hi", enabled=False) == "hi"
    assert "\x1b" not in view.color("red", "x", enabled=False)


def test_color_wrap_emits_ansi_when_enabled():
    assert "\x1b[" in view.color("red", "x", enabled=True)


def test_dryrun_banner():
    out = view.dryrun_banner()
    assert "dry-run" in out.lower()
