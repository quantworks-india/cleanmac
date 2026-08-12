"""Memory Cleaner — free inactive RAM and list heavy processes."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

from maccleaner.core import Sudo, confirm, size_human


@dataclass
class Proc:
    pid: int
    rss: int
    comm: str


def _parse_vm_stat(output: str) -> int:
    page_size = 16384
    free_pages = 0
    for line in output.splitlines():
        low = line.lower()
        if "page size of" in low:
            m = re.search(r"page size of (\d+) bytes", line)
            if m:
                page_size = int(m.group(1))
        if low.startswith("pages free"):
            m = re.search(r"pages free:\s+(\d+)", low)
            if m:
                free_pages += int(m.group(1))
        if low.startswith("pages speculative"):
            m = re.search(r"pages speculative:\s+(\d+)", low)
            if m:
                free_pages += int(m.group(1))
    return free_pages * page_size


def _free_bytes() -> int:
    r = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return 0
    return _parse_vm_stat(r.stdout)


def _run_free(sudo: Sudo) -> int:
    if not sudo.ensure():
        print("sudo is required to purge memory")
        return 1
    before = _free_bytes()
    r = sudo.run(["purge"])
    if r.returncode != 0:
        print(f"purge failed: {r.stderr.strip()}")
        return 1
    after = _free_bytes()
    before_kb = before // 1024
    after_kb = after // 1024
    print(f"Free memory before: {size_human(before_kb)}")
    print(f"Free memory after:  {size_human(after_kb)}")
    print(f"Freed:              {size_human(abs(after_kb - before_kb))}")
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


def _run_heavy() -> int:
    r = subprocess.run(
        ["ps", "-eo", "pid,rss,comm"], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        print(f"ps failed: {r.stderr.strip()}")
        return 1
    procs = _parse_ps(r.stdout)
    procs.sort(key=lambda p: p.rss, reverse=True)
    print(f"{'PID':>8} {'RSS':>10} COMMAND")
    for p in procs[:10]:
        print(f"{p.pid:>8} {size_human(p.rss):>10} {p.comm}")
    if sys.stdin.isatty() and confirm("Quit a process by PID?"):
        try:
            pid_str = input("PID to kill: ").strip()
        except EOFError:
            return 0
        try:
            pid = int(pid_str)
        except ValueError:
            print(f"Invalid PID: {pid_str}")
            return 0
        kr = subprocess.run(["kill", str(pid)], capture_output=True, text=True, check=False)
        if kr.returncode == 0:
            print(f"  ✓ sent TERM to {pid}")
        else:
            print(f"  ✗ failed: {kr.stderr.strip()}")
    return 0


def run(args, sudo: Sudo) -> int:
    if args.mem_cmd == "free":
        return _run_free(sudo)
    if args.mem_cmd == "heavy":
        return _run_heavy()
    return 2
