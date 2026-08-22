"""Tests for core safety library (safe_rm, audit, Deleter)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from maccleaner import core
from maccleaner.core import (
    Auditor,
    Deleter,
    is_safe_path,
    size_human,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Redirect home + state dir to a temp sandbox for every test."""
    home = tmp_path
    monkeypatch.setattr(core, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(core, "AUDIT_DIR", tmp_path / "state" / "audit")
    monkeypatch.setattr(core, "LOG_DIR", tmp_path / "state" / "logs")
    monkeypatch.setenv("CLEANMAC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLEANMAC_HOME", str(home))
    return tmp_path


def test_safe_path_refuses_protected_roots(tmp_path):
    for root in ["/", "/System", "/Library", "/Applications", "/Users", "/usr"]:
        assert not is_safe_path(root), root
        assert not is_safe_path(root + "/anything"), root


def test_safe_path_allows_home_and_volumes(isolated_home):
    home = str(isolated_home)
    assert is_safe_path(home)
    assert is_safe_path(os.path.join(home, "Library", "Caches"))
    assert is_safe_path("/Volumes/Backup/foo")


def test_safe_path_refuses_protected_home_subdirs(isolated_home, monkeypatch):
    # simulate the real home being /Users/sandeep
    fake_real_home = "/Users/sandeep"
    monkeypatch.setenv("CLEANMAC_HOME", fake_real_home)
    for sub in [".ssh", ".aws", ".gnupg", ".config"]:
        assert not is_safe_path(f"{fake_real_home}/{sub}"), sub


def test_safe_path_realpath_resolves_symlink(isolated_home):
    home = isolated_home
    target = Path("/etc")
    link = home / "evil_link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("cannot create symlink")
    assert not is_safe_path(str(link))


def test_size_human():
    assert size_human(500) == "500K"
    assert size_human(1024) == "1.0M"
    assert size_human(1048576) == "1.00G"


def test_auditor_writes_valid_jsonl(isolated_home):
    aud = Auditor("test-run-1", mode="dry-run")
    aud.write("step1", "would_delete", "/tmp/foo", 1234)
    aud.close()
    lines = (core.AUDIT_DIR / "audit-test-run-1.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["run"] == "test-run-1"
    assert rec["mode"] == "dry-run"
    assert rec["step"] == "step1"
    assert rec["path"] == "/tmp/foo"
    assert rec["size_bytes"] == 1234


def test_deleter_dry_run_deletes_nothing(isolated_home):
    target = isolated_home / "foo.txt"
    target.write_text("hello")
    aud = Auditor("dry", mode="dry-run")
    d = Deleter(aud, commit=False)
    deleted = d.delete("t", [str(target)])
    assert deleted == []
    assert target.exists()
    aud.close()


def test_deleter_commit_with_confirm_deletes(isolated_home):
    target = isolated_home / "foo.txt"
    target.write_text("hello")
    aud = Auditor("live", mode="live")
    d = Deleter(aud, commit=True, confirm_fn=lambda p: True)
    deleted = d.delete("t", [str(target)])
    assert deleted == [str(target)]
    assert not target.exists()
    aud.close()


def test_deleter_refuses_unsafe_path_even_in_commit(isolated_home):
    aud = Auditor("live", mode="live")
    d = Deleter(aud, commit=True, confirm_fn=lambda p: True)
    deleted = d.delete("t", ["/etc/passwd"])
    assert deleted == []
    assert os.path.exists("/etc/passwd")
    aud.close()
