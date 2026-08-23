"""Tests for Reporter human-mode rendering through view.

JSON contract is covered in test_core.py and must stay frozen. These tests
cover the human (default) path: readable output, no `[info] k=v` debug dump.
"""

from __future__ import annotations

from maccleaner.core import Reporter


def test_human_status_line_readable(capsys):
    r = Reporter(json_mode=False, verbose=False, color=False)
    r.info("scan_complete", files=42)
    out = capsys.readouterr().out
    assert "[info]" not in out
    assert "scan_complete" in out
    assert "42" in out


def test_human_table_renders_aligned_table(capsys):
    r = Reporter(json_mode=False, verbose=False, color=False)
    r.table("apps_list", ["Name", "Size"], [["Alpha", "1.2 GB"], ["Beta", "3 MB"]])
    out = capsys.readouterr().out
    assert "Alpha" in out
    assert "1.2 GB" in out
    assert "3 MB" in out
    assert "-" in out  # separator


def test_human_table_json_unchanged(capsys):
    import json

    r = Reporter(json_mode=True, verbose=False)
    r.table("apps_list", ["Name"], [["Alpha"]])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "apps_list"
    assert rec["headers"] == ["Name"]
    assert rec["rows"] == [["Alpha"]]


def test_human_unknown_event_falls_back_cleanly(capsys):
    r = Reporter(json_mode=False, verbose=False, color=False)
    r.warn("some_unknown_event", path="/x")
    out = capsys.readouterr().out
    assert "some_unknown_event" in out
    assert "[warn" not in out


def test_human_debug_still_suppressed_without_verbose(capsys):
    r = Reporter(json_mode=False, verbose=False, color=False)
    r.debug("hashing", path="/a")
    assert capsys.readouterr().out == ""
