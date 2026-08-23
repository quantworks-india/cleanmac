"""Memory Cleaner — free inactive RAM and list heavy processes."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from maccleaner.core import Reporter, Sudo, confirm, size_human

# PIDs that must never be killed — init (0), launchd (1), kernel (2).
PROTECTED_PIDS = frozenset({0, 1, 2})


@dataclass
class Proc:
    pid: int
    rss: int
    comm: str


def _sysctl_int(key: str) -> int:
    """Read an integer sysctl via `sysctl -n`. Raises OSError on failure."""
    r = subprocess.run(
        ["sysctl", "-n", key], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise OSError(r.stderr.strip() or f"sysctl {key} failed")
    return int(r.stdout.strip())


def free_bytes() -> int:
    """Free memory in bytes = (free + speculative pages) * page size.

    Uses sysctl integers only — no vm_stat text parsing.
    Returns 0 if sysctl is unavailable.
    """
    try:
        page_size = _sysctl_int("hw.pagesize")
        free_pages = _sysctl_int("vm.page_free_count")
        speculative = _sysctl_int("vm.page_speculative_count")
    except (OSError, ValueError):
        return 0
    return (free_pages + speculative) * page_size


def _free_bytes() -> int:
    return free_bytes()


def _run_free(sudo: Sudo, reporter: Reporter) -> int:
    if not sudo.ensure():
        reporter.error("sudo_required")
        return 1
    before = _free_bytes()
    r = sudo.run(["purge"])
    if r.returncode != 0:
        reporter.error("purge_failed", stderr=r.stderr.strip())
        return 1
    after = _free_bytes()
    before_kb = before // 1024
    after_kb = after // 1024
    reporter.info(
        "mem_free",
        before=size_human(before_kb),
        after=size_human(after_kb),
        freed=size_human(abs(after_kb - before_kb)),
    )
    return 0


def _parse_ps(output: str) -> list[Proc]:
    procs: list[Proc] = []
    for line in output.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
            rss = int(parts[1])
        except ValueError:
            continue
        comm = parts[2] if len(parts) > 2 else ""
        procs.append(Proc(pid, rss, comm))
    return procs


def _run_heavy(reporter: Reporter) -> int:
    r = subprocess.run(
        ["ps", "-eo", "pid,rss,comm"], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        reporter.error("ps_failed", stderr=r.stderr.strip())
        return 1
    procs = _parse_ps(r.stdout)
    procs.sort(key=lambda p: p.rss, reverse=True)
    reporter.info("heavy_header", columns=["PID", "RSS", "COMMAND"])
    for p in procs[:10]:
        reporter.info("heavy_row", pid=p.pid, rss=size_human(p.rss), comm=p.comm)
    if sys.stdin.isatty() and confirm("Quit a process by PID?"):
        try:
            pid_str = input("PID to kill: ").strip()
        except EOFError:
            return 0
        try:
            pid = int(pid_str)
        except ValueError:
            reporter.warn("invalid_pid", value=pid_str)
            return 0
        if pid in PROTECTED_PIDS:
            reporter.warn("protected_pid", pid=pid)
            return 0
        kr = subprocess.run(
            ["kill", str(pid)], capture_output=True, text=True, check=False
        )
        if kr.returncode == 0:
            reporter.info("kill_sent", pid=pid)
        else:
            reporter.error("kill_failed", pid=pid, stderr=kr.stderr.strip())
    return 0


def run(args, sudo: Sudo, reporter: Reporter) -> int:
    if args.mem_cmd == "free":
        return _run_free(sudo, reporter)
    if args.mem_cmd == "heavy":
        return _run_heavy(reporter)
    return 2
