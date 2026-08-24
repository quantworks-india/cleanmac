"""Tests for memory — free RAM and heavy process listing."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

from maccleaner import memory
from maccleaner.core import Reporter

PS_OUTPUT = """\
  PID   RSS COMMAND
    1  1234 /sbin/launchd
  123  5678 /usr/libexec/syslogd
  456    42 /bin/sh
"""


class FakeSudo:
    def __init__(self) -> None:
        self.ensured = False
        self.runs: list[list[str]] = []

    def ensure(self) -> bool:
        self.ensured = True
        return True

    def run(self, args: list[str]) -> CompletedProcess:
        self.runs.append(list(args))
        return CompletedProcess(args, 0, "", "")


def test_free_bytes_sums_free_and_speculative_pages(monkeypatch):
    """Free bytes = (free + speculative) * page_size, read via sysctl ints."""
    monkeypatch.setattr(
        memory,
        "_sysctl_int",
        lambda key: {
            "hw.pagesize": 16384,
            "vm.page_free_count": 100,
            "vm.page_speculative_count": 10,
        }[key],
    )
    assert memory.free_bytes() == (100 + 10) * 16384


def test_free_bytes_respects_page_size(monkeypatch):
    monkeypatch.setattr(
        memory,
        "_sysctl_int",
        lambda key: {
            "hw.pagesize": 4096,
            "vm.page_free_count": 100,
            "vm.page_speculative_count": 10,
        }[key],
    )
    assert memory.free_bytes() == (100 + 10) * 4096


def test_free_bytes_queries_expected_sysctl_keys(monkeypatch):
    seen: list[str] = []

    def fake(key):
        seen.append(key)
        return 4096

    monkeypatch.setattr(memory, "_sysctl_int", fake)
    memory.free_bytes()
    assert seen == ["hw.pagesize", "vm.page_free_count", "vm.page_speculative_count"]


def test_free_bytes_defaults_on_sysctl_failure(monkeypatch):
    def fail(key):
        raise OSError("no sysctl")

    monkeypatch.setattr(memory, "_sysctl_int", fail)
    assert memory.free_bytes() == 0


def test_parse_vm_stat_no_longer_exists(monkeypatch):
    """The regex vm_stat parser is gone; module exposes free_bytes() instead."""
    assert not hasattr(memory, "_parse_vm_stat")



def test_parse_ps_skips_header_and_parses_fields():
    procs = memory._parse_ps(PS_OUTPUT)
    assert len(procs) == 3
    assert procs[0].pid == 1
    assert procs[0].rss == 1234
    assert procs[0].comm == "/sbin/launchd"


def test_parse_ps_handles_spaces_in_command():
    procs = memory._parse_ps("  PID   RSS COMMAND\n  789  100 Google Chrome Helper")
    assert len(procs) == 1
    assert procs[0].pid == 789
    assert procs[0].comm == "Google Chrome Helper"


def test_heavy_lists_processes(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "ps":
            return CompletedProcess(cmd, 0, PS_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    monkeypatch.setattr(memory, "confirm", lambda *a, **kw: False)

    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    out = capsys.readouterr().out

    assert rc == 0
    assert ["ps", "-eo", "pid,rss,comm"] in calls
    assert "/sbin/launchd" in out or "launchd" in out
    assert "syslogd" in out


def test_free_calls_sudo_and_shows_before_after(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_sysctl(key):
        calls.append(["sysctl", "-n", key])
        return {"hw.pagesize": 16384, "vm.page_free_count": 100, "vm.page_speculative_count": 10}[key]

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory, "_sysctl_int", fake_sysctl)
    monkeypatch.setattr(memory.subprocess, "run", fake_run)

    sudo = FakeSudo()
    args = type("A", (), {"mem_cmd": "free"})()
    rc = memory.run(args, sudo, Reporter())
    out = capsys.readouterr().out

    assert rc == 0
    assert sudo.ensured
    assert sudo.runs == [["purge"]]
    assert "sysctl" in str(calls)
    assert "before" in out
    assert "after" in out


def test_free_fails_without_sudo():
    sudo = FakeSudo()
    sudo.ensure = lambda: False
    args = type("A", (), {"mem_cmd": "free"})()
    rc = memory.run(args, sudo, Reporter())
    assert rc == 1
    assert sudo.runs == []


@pytest.mark.parametrize("pid_str", ["0", "1", "2"])
def test_heavy_refuses_kill_of_critical_pid(pid_str, monkeypatch, capsys):
    """Critical PIDs (0=init, 1=launchd, 2=kernel) must never be killed."""
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "ps":
            return CompletedProcess(cmd, 0, PS_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    monkeypatch.setattr(memory, "confirm", lambda *a, **kw: True)
    monkeypatch.setattr(memory.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: pid_str)

    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    out = capsys.readouterr().out

    assert rc == 0
    kill_calls = [c for c in calls if c[0] == "kill"]
    assert kill_calls == [], f"kill was called for protected PID {pid_str}"
    assert "refused" in out.lower() or "protected" in out.lower()


def test_heavy_kills_normal_pid(monkeypatch, capsys):
    """A non-critical PID should be passed to kill()."""
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "ps":
            return CompletedProcess(cmd, 0, PS_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    monkeypatch.setattr(memory, "confirm", lambda *a, **kw: True)
    monkeypatch.setattr(memory.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "12345")

    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    out = capsys.readouterr().out

    assert rc == 0
    assert ["kill", "12345"] in calls
    assert "kill_sent" in out


def test_heavy_invalid_pid_returns_zero(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "ps":
            return CompletedProcess(cmd, 0, PS_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    monkeypatch.setattr(memory, "confirm", lambda *a, **kw: True)
    monkeypatch.setattr(memory.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "not-a-pid")

    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    out = capsys.readouterr().out

    assert rc == 0
    assert not any(c[0] == "kill" for c in calls)
    assert "invalid_pid" in out


def test_heavy_no_tty_skips_kill_prompt(monkeypatch):
    """When stdin is not a TTY, the kill prompt must not appear."""
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "ps":
            return CompletedProcess(cmd, 0, PS_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    monkeypatch.setattr(memory, "confirm", lambda *a, **kw: True)
    monkeypatch.setattr(memory.sys.stdin, "isatty", lambda: False)

    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    assert rc == 0
    assert not any(c[0] == "kill" for c in calls)


def test_ps_failure_returns_1(monkeypatch, capsys):
    def fake_run(cmd, *args, **kw):
        return CompletedProcess(cmd, 1, "", "ps failed")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    args = type("A", (), {"mem_cmd": "heavy"})()
    rc = memory.run(args, FakeSudo(), Reporter())
    out = capsys.readouterr().out
    assert rc == 1
    assert "ps failed" in out


def test_purge_failure_returns_1(monkeypatch, capsys):
    def fake_sysctl(key):
        return {"hw.pagesize": 16384, "vm.page_free_count": 100, "vm.page_speculative_count": 10}[key]

    monkeypatch.setattr(memory, "_sysctl_int", fake_sysctl)

    class FailingSudo:
        def ensure(self) -> bool:
            return True

        def run(self, args: list[str]) -> CompletedProcess:
            return CompletedProcess(args, 1, "", "purge denied")

    args = type("A", (), {"mem_cmd": "free"})()
    rc = memory.run(args, FailingSudo(), Reporter())
    out = capsys.readouterr().out
    assert rc == 1
    assert "purge denied" in out
