"""Tests for duplicates — scan, similar-photos, merge-folders."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from maccleaner import core
from maccleaner import duplicates as dup
from maccleaner.core import Auditor, Deleter


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(core, "AUDIT_DIR", tmp_path / "state" / "audit")
    monkeypatch.setattr(core, "LOG_DIR", tmp_path / "state" / "logs")
    monkeypatch.setenv("CLEANMAC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLEANMAC_HOME", str(tmp_path))
    return tmp_path


def _scan_args(directory: str, min_size: str = "1B") -> object:
    return type(
        "A",
        (),
        {"dup_cmd": "scan", "dir": directory, "min_size": min_size, "hash": "sha256"},
    )()


# ── scan ───────────────────────────────────────────────────────────────


def test_scan_finds_identical_files(isolated_home, capsys):
    d = isolated_home / "data"
    d.mkdir()
    (d / "a.txt").write_bytes(b"hello world" * 100)
    (d / "b.txt").write_bytes(b"hello world" * 100)
    (d / "c.txt").write_bytes(b"different content" * 100)

    aud = Auditor("scan1", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    rc = dup.run(_scan_args(str(d)), deleter)
    assert rc == 0
    out = capsys.readouterr().out
    assert "a.txt" in out
    assert "b.txt" in out
    assert "c.txt" not in out
    aud.close()


def test_scan_ignores_different_files(isolated_home, capsys):
    d = isolated_home / "data"
    d.mkdir()
    (d / "x.txt").write_bytes(b"unique content one" * 50)
    (d / "y.txt").write_bytes(b"unique content two" * 50)
    (d / "z.txt").write_bytes(b"unique content three" * 50)

    aud = Auditor("scan2", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    rc = dup.run(_scan_args(str(d)), deleter)
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 duplicate groups" in out
    aud.close()


def test_scan_respects_min_size(isolated_home, capsys):
    d = isolated_home / "data"
    d.mkdir()
    (d / "small1.txt").write_bytes(b"x" * 50)
    (d / "small2.txt").write_bytes(b"x" * 50)
    (d / "large1.txt").write_bytes(b"y" * 200)
    (d / "large2.txt").write_bytes(b"y" * 200)

    aud = Auditor("scan3", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    dup.run(_scan_args(str(d), min_size="100B"), deleter)
    out = capsys.readouterr().out
    assert "large1" in out
    assert "large2" in out
    assert "small1" not in out
    assert "small2" not in out
    aud.close()


def test_scan_skips_hard_links(isolated_home, capsys):
    d = isolated_home / "data"
    d.mkdir()
    (d / "original.txt").write_bytes(b"content" * 100)
    os.link(str(d / "original.txt"), str(d / "hardlink.txt"))

    aud = Auditor("scan4", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    dup.run(_scan_args(str(d)), deleter)
    out = capsys.readouterr().out
    assert "0 duplicate groups" in out
    aud.close()


def test_scan_skips_symlinks(isolated_home, capsys):
    d = isolated_home / "data"
    d.mkdir()
    (d / "real.txt").write_bytes(b"content" * 100)
    os.symlink(str(d / "real.txt"), str(d / "link.txt"))

    aud = Auditor("scan5", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    dup.run(_scan_args(str(d)), deleter)
    out = capsys.readouterr().out
    assert "0 duplicate groups" in out
    aud.close()


def test_scan_dry_run_deletes_nothing(isolated_home):
    d = isolated_home / "data"
    d.mkdir()
    (d / "a.txt").write_bytes(b"content" * 100)
    (d / "b.txt").write_bytes(b"content" * 100)

    aud = Auditor("scan6", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    rc = dup.run(_scan_args(str(d)), deleter)
    assert rc == 0
    assert (d / "a.txt").exists()
    assert (d / "b.txt").exists()
    aud.close()


def test_scan_commit_deletes_redundant(isolated_home):
    d = isolated_home / "data"
    d.mkdir()
    (d / "keep.txt").write_bytes(b"content" * 100)
    (d / "dup.txt").write_bytes(b"content" * 100)
    os.utime(str(d / "keep.txt"), (0, 0))
    os.utime(str(d / "dup.txt"), (1000000000, 1000000000))

    aud = Auditor("scan7", mode="live")
    deleter = Deleter(aud, commit=True, confirm_fn=lambda p: True)
    rc = dup.run(_scan_args(str(d)), deleter)
    assert rc == 0
    assert (d / "keep.txt").exists()
    assert not (d / "dup.txt").exists()
    aud.close()


# ── merge-folders ──────────────────────────────────────────────────────


def test_merge_folders_moves_and_reports_conflicts(isolated_home, capsys):
    a = isolated_home / "a"
    b = isolated_home / "b"
    a.mkdir()
    b.mkdir()
    (a / "existing.txt").write_text("from a")
    (b / "existing.txt").write_text("from b")
    (b / "new.txt").write_text("new file")

    args = type("A", (), {"dup_cmd": "merge-folders", "a": str(a), "b": str(b)})()
    aud = Auditor("merge1", mode="live")
    deleter = Deleter(aud, commit=True, confirm_fn=lambda p: True)
    rc = dup.run(args, deleter)
    assert rc == 0

    assert (a / "new.txt").exists()
    assert not (b / "new.txt").exists()
    assert (a / "existing.txt").read_text() == "from a"
    out = capsys.readouterr().out
    assert "conflict" in out.lower()
    assert "moved" in out.lower()
    aud.close()


def test_merge_folders_nested_subdirs(isolated_home):
    a = isolated_home / "a"
    b = isolated_home / "b"
    a.mkdir()
    (b / "sub").mkdir(parents=True)
    (b / "sub" / "deep.txt").write_text("deep")

    args = type("A", (), {"dup_cmd": "merge-folders", "a": str(a), "b": str(b)})()
    aud = Auditor("merge2", mode="live")
    deleter = Deleter(aud, commit=True, confirm_fn=lambda p: True)
    rc = dup.run(args, deleter)
    assert rc == 0
    assert (a / "sub" / "deep.txt").exists()
    aud.close()


# ── similar-photos ─────────────────────────────────────────────────────


def test_similar_photos_groups_similar(isolated_home, capsys):
    pytest.importorskip("PIL")
    from PIL import Image

    d = isolated_home / "photos"
    d.mkdir()

    def make_photo(path: Path, pattern: str = "horizontal", seed: int = 42) -> None:
        import random

        rng = random.Random(seed)
        img = Image.new("L", (200, 200))
        for x in range(200):
            for y in range(200):
                if pattern == "horizontal":
                    val = int((x / 200) * 255 + rng.randint(-2, 2))
                else:
                    val = int(255 - (x / 200) * 255 + rng.randint(-2, 2))
                img.putpixel((x, y), max(0, min(255, val)))
        img.save(str(path))

    make_photo(d / "img1.png", "horizontal", seed=42)
    img2 = Image.open(str(d / "img1.png")).copy()
    img2.putpixel((100, 100), 0)
    img2.save(str(d / "img2.png"))
    make_photo(d / "img3.png", "inverted", seed=42)

    args = type("A", (), {"dup_cmd": "similar-photos", "dir": str(d)})()
    aud = Auditor("photos1", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    rc = dup.run(args, deleter)
    assert rc == 0
    out = capsys.readouterr().out
    assert "img1" in out
    assert "img2" in out
    assert "img3" not in out
    aud.close()


def test_scan_reuses_stat_from_walk(isolated_home, monkeypatch):
    """_run_scan should not call os.stat again on files already lstat'd in the walk."""
    d = isolated_home / "data"
    d.mkdir()
    (d / "a.txt").write_bytes(b"hello world" * 100)
    (d / "b.txt").write_bytes(b"hello world" * 100)

    stat_calls: list[str] = []
    original_stat = os.stat

    def counting_stat(p, *args, **kw):
        stat_calls.append(p)
        return original_stat(p, *args, **kw)

    monkeypatch.setattr(dup.os, "stat", counting_stat)

    aud = Auditor("scan-stat", mode="dry-run")
    deleter = Deleter(aud, commit=False)
    rc = dup.run(_scan_args(str(d)), deleter)
    assert rc == 0
    aud.close()

    file_stats = [c for c in stat_calls if "a.txt" in str(c) or "b.txt" in str(c)]
    assert file_stats == [], (
        f"os.stat called again on already-walked files: {file_stats}"
    )


def test_group_similar_docstring_notes_complexity():
    """_group_similar is O(n²); the docstring should say so."""
    doc = dup._group_similar.__doc__ or ""
    assert any(w in doc.lower() for w in ("o(n²)", "quadratic", "pairwise"))
