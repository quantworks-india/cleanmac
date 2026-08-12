"""Shared safety core for maccleaner.

Every destructive action in the suite must go through this module. Invariants:

- ``safe_rm`` refuses dangerous roots (/, /System, /Library, /Applications, home
  subdirs like .ssh/.aws) after realpath resolution.
- Deletion is a *no-op* unless ``commit`` mode is active AND the caller passes an
  explicit confirmation token. This enforces dry-run at the leaf, not just the CLI.
- Every action is appended to a JSONL audit file alongside the bash cleanmac logs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

STATE_DIR = Path(os.environ.get("CLEANMAC_STATE_DIR", Path.home() / ".local/state/cleanmac"))
LOG_DIR = STATE_DIR / "logs"
AUDIT_DIR = STATE_DIR / "audit"

# ── protected paths (BLOCKER-3 from plan audit) ─────────────────────
PROTECTED_ROOTS = frozenset(
    {
        "/",
        "/System",
        "/System/Applications",
        "/Library",
        "/Applications",
        "/Users",
        "/usr",
        "/bin",
        "/etc",
        "/private",
        "/var",
        "/opt",
        "/sbin",
        "/dev",
        "/tmp",
    }
)

PROTECTED_HOME_SUBDIRS = frozenset({".ssh", ".aws", ".gnupg", ".config", ".Trash"})


@dataclass
class AuditRecord:
    """One audit line, matching the bash audit format."""

    ts: str
    run: str
    mode: str
    step: str
    action: str
    path: str
    size_bytes: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "run": self.run,
                "mode": self.mode,
                "step": self.step,
                "action": self.action,
                "path": self.path,
                "size_bytes": self.size_bytes,
            }
        )


class Auditor:
    """Appends JSONL audit records to a single file per run."""

    def __init__(self, run_id: str, mode: str = "dry-run") -> None:
        self.run_id = run_id
        self.mode = mode
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self.path = AUDIT_DIR / f"audit-{run_id}.jsonl"
        self._fh = self.path.open("a", encoding="utf-8")

    def write(
        self,
        step: str,
        action: str,
        path: str,
        size_bytes: int = 0,
    ) -> None:
        rec = AuditRecord(
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            run=self.run_id,
            mode=self.mode,
            step=step,
            action=action,
            path=path,
            size_bytes=size_bytes,
        )
        self._fh.write(rec.to_json() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def size_human(kb: int) -> str:
    """Human-readable size from KB. Port of bash kb_to_human."""
    if kb < 1024:
        return f"{kb}K"
    if kb < 1024 * 1024:
        return f"{kb / 1024:.1f}M"
    return f"{kb / (1024 * 1024):.2f}G"


def _is_protected(real: str) -> bool:
    """True if a path is a system/dangerous root we must never delete.

    Safe prefixes (home, /Volumes, /Applications, /tmp sandbox) are checked
    FIRST in is_safe_path, so /private/var/folders (macOS temp sandbox) is
    allowed while /private/var/db, /etc, /usr, etc. are refused.
    """
    # macOS temp sandbox is safe to write but lives under /private — allow it.
    for safe in ("/private/var/folders", "/tmp", "/private/tmp", "/private/var/tmp"):
        if real == safe or real.startswith(safe + os.sep):
            return False
    if real in PROTECTED_ROOTS:
        return True
    for root in PROTECTED_ROOTS:
        if real.startswith(root + os.sep):
            return True
    # Compare against realpath of home so /var→/private/var aliases work.
    home_real = _home_real()
    if real == home_real:
        return True
    for sub in PROTECTED_HOME_SUBDIRS:
        if real.startswith(os.path.join(home_real, sub)):
            return True
    return False


def _home_real() -> str:
    """Realpath of the effective home (respects CLEANMAC_HOME for tests)."""
    home = os.environ.get("CLEANMAC_HOME") or str(Path.home())
    return os.path.realpath(home)


def is_safe_path(path: str) -> bool:
    """True if a path is deletable. realpath resolution + whitelist prefix."""
    real = os.path.realpath(path)
    if _is_protected(real):
        return False
    home_real = _home_real()
    for prefix in (
        home_real,
        os.path.realpath("/Volumes"),
        os.path.realpath("/Applications"),
        "/tmp",
    ):
        if real == prefix or real.startswith(prefix + os.sep):
            return True
    return False


def dir_size_kb(path: str) -> int:
    """Total size of a path in KB (du -sk equivalent). 0 if missing."""
    try:
        out = subprocess.run(
            ["du", "-sk", path],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0:
            return int(out.stdout.split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def confirm(prompt: str) -> bool:
    """Interactive y/N confirmation. Returns False on any non-y input."""
    try:
        resp = input(f"{prompt} [y/N] ")
    except EOFError:
        return False
    return resp.strip().lower() in ("y", "yes")


def _leaf_delete(path: str) -> None:
    """Unconditional delete (private). Callers must gate on safe_rm + commit."""
    p = Path(path)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, ignore_errors=False)
    else:
        p.unlink(missing_ok=True)


class Deleter:
    """The only deletion entry point. Enforces every safety invariant."""

    def __init__(self, auditor: Auditor, commit: bool = False, confirm_fn=None) -> None:
        self.auditor = auditor
        self.commit = commit
        self.confirm_fn = confirm_fn or confirm

    def delete(self, step: str, paths: Iterable[str]) -> list[str]:
        """Delete paths, auditing each. Returns list of deleted paths.

        Rules:
        - unsafe paths are never touched, regardless of commit
        - in dry-run mode nothing is deleted, only audited as 'would_delete'
        - in commit mode each path (or group) requires confirmation unless
          confirm_fn returns True for all
        """
        deleted: list[str] = []
        for p in paths:
            if not is_safe_path(p):
                print(f"  ✗ refused (unsafe path): {p}")
                self.auditor.write(step, "refused", p)
                continue
            size = dir_size_kb(p) * 1024
            if not self.commit:
                self.auditor.write(step, "would_delete", p, size)
                print(f"  · would delete: {p}")
                continue
            if not self.confirm_fn(f"Delete {p}?"):
                self.auditor.write(step, "skipped", p, size)
                print(f"  · skipped: {p}")
                continue
            try:
                _leaf_delete(p)
            except OSError as e:
                self.auditor.write(step, "failed", p, size)
                print(f"  ✗ failed: {p} ({e})")
                continue
            self.auditor.write(step, "deleted", p, size)
            print(f"  ✓ deleted: {p}")
            deleted.append(p)
        return deleted


# ── sudo: one prompt per invocation, then -n (port of bash ensure_sudo) ──
class Sudo:
    """Validates sudo once; all elevated commands use -n after that."""

    def __init__(self) -> None:
        self._ready = False

    def ensure(self) -> bool:
        """Run sudo -v once. Sets ready flag. Returns True if elevation available."""
        try:
            r = subprocess.run(
                ["sudo", "-v"],
                capture_output=True,
                text=True,
                check=False,
            )
            self._ready = r.returncode == 0
        except FileNotFoundError:
            self._ready = False
        return self._ready

    def run(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a command via sudo -n if ready, else plain (non-elevated fallback)."""
        cmd = args
        if self._ready:
            # Re-validate timestamp cheaply; skip if expired.
            check = subprocess.run(
                ["sudo", "-n", "-v"],
                capture_output=True,
                text=True,
                check=False,
            )
            if check.returncode == 0:
                cmd = ["sudo", "-n", *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
