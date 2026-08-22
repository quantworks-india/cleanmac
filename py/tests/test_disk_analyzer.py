"""Tests for disk_analyzer — iterative scan, size rollup, HTML report."""

from __future__ import annotations

import os

import pytest

from maccleaner import disk_analyzer as da


@pytest.fixture
def tree(tmp_path):
    """Create a small nested tree with known sizes."""
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "file1.txt").write_bytes(b"x" * 100)
    (tmp_path / "a" / "b" / "file2.bin").write_bytes(b"y" * 200)
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "file3.log").write_bytes(b"z" * 50)
    return tmp_path


def test_scan_total_size(tree):
    sizes, total = da.scan(str(tree))
    assert total == 350  # 100 + 200 + 50
    assert sizes[str(tree / "a")] == 300  # 100 + 200
    assert sizes[str(tree / "a" / "b")] == 200
    assert sizes[str(tree / "c")] == 50


def test_walk_skips_symlink_loop(tree):
    (tree / "loop").symlink_to(tree, target_is_directory=True)
    _sizes, total = da.scan(str(tree))
    assert total == 350  # symlink loop not followed


def test_top_largest(tree):
    sizes, _ = da.scan(str(tree))
    top = da.top_largest(sizes, 3)
    assert top[0][1] == 350  # root
    assert top[1][0] == str(tree / "a")


def test_report_creates_self_contained_html(tree, tmp_path):
    out = tmp_path / "report.html"
    args = type("A", (), {"dir": str(tree), "out": str(out)})()
    rc = da._run_report(args)
    assert rc == 0
    assert out.exists()
    content = out.read_text()
    assert "<!DOCTYPE html>" in content
    assert '<div id="map">' in content
    assert "Disk Treemap" in content
    # treemap JSON includes all nodes (files + dir) as tiles
    assert "file1.txt" in content


def test_scan_tolerates_missing_dir(tmp_path):
    with pytest.raises(SystemExit):
        da.scan(str(tmp_path / "nope"))


def test_treemap_handles_deep_paths(tmp_path):
    """Iterative treemap builder must not hit RecursionError on deep trees."""
    root = str(tmp_path / "deep")
    sizes: dict[str, int] = {root: 0}
    path = root
    for i in range(3000):
        child = os.path.join(path, f"level{i}")
        sizes[child] = 10
        path = child

    treemap = da._build_treemap_json(sizes, root)

    assert treemap["name"] == "deep"
    assert len(treemap["children"]) == 1
