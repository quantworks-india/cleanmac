"""Tests for hidden_files — show/hide hidden files in Finder."""

from __future__ import annotations

from subprocess import CompletedProcess

from maccleaner import hidden_files


def _capture_factory():
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        return CompletedProcess(cmd, 0, "", "")

    return calls, fake_run


def test_show_runs_correct_commands(monkeypatch):
    calls, fake_run = _capture_factory()
    monkeypatch.setattr(hidden_files.subprocess, "run", fake_run)

    args = type("A", (), {"action": "show"})()
    rc = hidden_files.run(args)

    assert rc == 0
    assert [
        "defaults",
        "write",
        "com.apple.finder",
        "AppleShowAllFiles",
        "-bool",
        "true",
    ] in calls
    assert ["killall", "Finder"] in calls
    assert calls.index(["killall", "Finder"]) > calls.index(
        [
            "defaults",
            "write",
            "com.apple.finder",
            "AppleShowAllFiles",
            "-bool",
            "true",
        ]
    )


def test_hide_runs_correct_commands(monkeypatch):
    calls, fake_run = _capture_factory()
    monkeypatch.setattr(hidden_files.subprocess, "run", fake_run)

    args = type("A", (), {"action": "hide"})()
    rc = hidden_files.run(args)

    assert rc == 0
    assert [
        "defaults",
        "write",
        "com.apple.finder",
        "AppleShowAllFiles",
        "-bool",
        "false",
    ] in calls
    assert ["killall", "Finder"] in calls
