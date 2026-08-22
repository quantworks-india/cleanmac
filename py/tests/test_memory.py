"""Tests for memory — free RAM and heavy process listing."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

from maccleaner import memory

VM_STAT_OUTPUT = """\
Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                             100.
Pages active:                           200.
Pages inactive:                          50.
Pages speculative:                       10.
Pages wired down:                        30.
Pages occupied by compressor:            40.
"""

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


def test_parse_vm_stat_counts_free_and_speculative():
    free = memory._parse_vm_stat(VM_STAT_OUTPUT)
    assert free == (100 + 10) * 16384


def test_parse_vm_stat_respects_page_size():
    out = VM_STAT_OUTPUT.replace("16384", "4096")
    free = memory._parse_vm_stat(out)
    assert free == (100 + 10) * 4096


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
    rc = memory.run(args, FakeSudo())
    out = capsys.readouterr().out

    assert rc == 0
    assert ["ps", "-eo", "pid,rss,comm"] in calls
    assert "/sbin/launchd" in out
    assert "syslogd" in out


def test_free_calls_sudo_and_shows_before_after(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kw):
        calls.append(list(cmd))
        if cmd[0] == "vm_stat":
            return CompletedProcess(cmd, 0, VM_STAT_OUTPUT, "")
        return CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(memory.subprocess, "run", fake_run)

    sudo = FakeSudo()
    args = type("A", (), {"mem_cmd": "free"})()
    rc = memory.run(args, sudo)
    out = capsys.readouterr().out

    assert rc == 0
    assert sudo.ensured
    assert sudo.runs == [["purge"]]
    assert ["vm_stat"] in calls
    assert "before" in out
    assert "after" in out


def test_free_fails_without_sudo():
    sudo = FakeSudo()
    sudo.ensure = lambda: False
    args = type("A", (), {"mem_cmd": "free"})()
    rc = memory.run(args, sudo)
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
    rc = memory.run(args, FakeSudo())
    out = capsys.readouterr().out

    assert rc == 0
    kill_calls = [c for c in calls if c[0] == "kill"]
    assert kill_calls == [], f"kill was called for protected PID {pid_str}"
    assert "refused" in out.lower() or "protected" in out.lower()
