"""Duplicate File Finder — Phase 3.

Size-first grouping, stream hashing, hard-link/symlink skipping, SQLite
incremental cache, dHash similar-photo grouping, and folder merging.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import stat
import struct
import subprocess
import tempfile
from pathlib import Path

from maccleaner import core
from maccleaner.core import Deleter

HASH_BUFFER = 1024 * 1024
DHASH_THRESHOLD = 10
PHOTO_EXTS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".webp",
        ".raw",
    }
)


def _parse_size(s: str) -> int:
    s = s.strip()
    if not s:
        raise ValueError("empty size")
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3}
    suffix = s[-1].upper()
    if suffix in units:
        return int(float(s[:-1]) * units[suffix])
    return int(float(s))


def _size_b(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    if b < 1024**2:
        return f"{b / 1024:.1f}K"
    if b < 1024**3:
        return f"{b / 1024**2:.1f}M"
    return f"{b / 1024**3:.2f}G"


def _iter_files(root: str):
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                continue
            if not stat.S_ISREG(mode):
                continue
            yield path, st


def _index_path() -> Path:
    return core.STATE_DIR / "dup-index.db"


def _open_index() -> sqlite3.Connection | None:
    try:
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(_index_path()))
        db.execute(
            """CREATE TABLE IF NOT EXISTS file_hashes (
                path TEXT PRIMARY KEY,
                st_ino INTEGER,
                st_dev INTEGER,
                st_mtime_ns INTEGER,
                st_size INTEGER,
                hash TEXT
            )"""
        )
        db.commit()
        return db
    except (OSError, sqlite3.Error):
        return None


def _compute_hash(path: str, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(HASH_BUFFER)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _hash_file(path: str, st: os.stat_result, algo: str, db) -> str | None:
    if db is not None:
        row = db.execute(
            "SELECT st_ino, st_dev, st_mtime_ns, st_size, hash FROM file_hashes WHERE path = ?",
            (path,),
        ).fetchone()
        if row:
            st_ino, st_dev, st_mtime_ns, st_size, h = row
            if (
                st_ino == st.st_ino
                and st_dev == st.st_dev
                and st_mtime_ns == st.st_mtime_ns
                and st_size == st.st_size
            ):
                return h
    h = _compute_hash(path, algo)
    if db is not None:
        try:
            db.execute(
                "INSERT OR REPLACE INTO file_hashes "
                "(path, st_ino, st_dev, st_mtime_ns, st_size, hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (path, st.st_ino, st.st_dev, st.st_mtime_ns, st.st_size, h),
            )
            db.commit()
        except sqlite3.Error:
            pass
    return h


def _run_scan(args, deleter: Deleter) -> int:
    root = args.dir
    if not os.path.isdir(root):
        raise SystemExit(f"Not a directory: {root}")
    min_size = _parse_size(args.min_size)
    algo = args.hash

    by_size: dict[int, list[tuple[str, os.stat_result]]] = {}
    seen_inodes: set[tuple[int, int]] = set()
    for path, st in _iter_files(root):
        if st.st_size < min_size:
            continue
        if st.st_nlink > 1:
            inode_key = (st.st_dev, st.st_ino)
            if inode_key in seen_inodes:
                continue
            seen_inodes.add(inode_key)
        by_size.setdefault(st.st_size, []).append((path, st))

    db = _open_index()
    groups: list[list[str]] = []
    for files in by_size.values():
        if len(files) < 2:
            continue
        by_hash: dict[str, list[str]] = {}
        for path, st in files:
            h = _hash_file(path, st, algo, db)
            if h is not None:
                by_hash.setdefault(h, []).append(path)
        for h, group in by_hash.items():
            if len(group) >= 2:
                groups.append(group)
    if db is not None:
        db.close()

    total_dupes = 0
    total_reclaimable = 0
    for group in groups:
        paths_with_mtime = sorted(group, key=lambda p: os.stat(p).st_mtime)
        keep = paths_with_mtime[0]
        to_delete = paths_with_mtime[1:]
        reclaimable = sum(os.stat(p).st_size for p in to_delete)
        total_dupes += len(to_delete)
        total_reclaimable += reclaimable
        print(
            f"\nDuplicate group ({len(group)} files, "
            f"{_size_b(reclaimable)} reclaimable):"
        )
        print(f"  keep:    {keep}")
        for p in to_delete:
            print(f"  delete:  {p}")
        deleter.delete("dup_scan", to_delete)

    print(
        f"\n{len(groups)} duplicate groups, {total_dupes} redundant files, "
        f"{_size_b(total_reclaimable)} reclaimable"
    )
    return 0


def _dhash_pillow(path: str) -> int | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("L")
    except Exception:  # noqa: BLE001
        return None
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    img = img.resize((9, 8), resample)
    px = img.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            idx = row * 9 + col
            if px[idx] > px[idx + 1]:
                bits |= 1 << (row * 8 + col)
    return bits


def _dhash_sips(path: str) -> int | None:
    with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
        tmp = f.name
    try:
        r = subprocess.run(
            ["sips", "-z", "8", "9", path, "--out", tmp, "-s", "format", "bmp"],
            capture_output=True,
            check=False,
        )
        if r.returncode != 0:
            return None
        with open(tmp, "rb") as f:
            data = f.read()
        if len(data) < 54 or data[0:2] != b"BM":
            return None
        pix_offset = struct.unpack("<I", data[10:14])[0]
        width = struct.unpack("<i", data[18:22])[0]
        height = struct.unpack("<i", data[22:26])[0]
        bpp = struct.unpack("<H", data[28:30])[0]
        if bpp not in (24, 32):
            return None
        bpp_bytes = bpp // 8
        top_down = height < 0
        h = abs(height)
        row_stride = ((width * bpp_bytes + 3) // 4) * 4
        gray: list[list[int]] = []
        for y in range(h):
            row_idx = y if top_down else (h - 1 - y)
            off = pix_offset + row_idx * row_stride
            vals = []
            for x in range(width):
                idx = off + x * bpp_bytes
                b, g, r = data[idx], data[idx + 1], data[idx + 2]
                vals.append(int(0.299 * r + 0.587 * g + 0.114 * b))
            gray.append(vals)
        bits = 0
        for row in range(8):
            for col in range(8):
                if gray[row][col] > gray[row][col + 1]:
                    bits |= 1 << (row * 8 + col)
        return bits
    except (OSError, struct.error, IndexError):
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _group_similar(
    hashes: list[tuple[str, int]], threshold: int = DHASH_THRESHOLD
) -> list[list[str]]:
    n = len(hashes)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if _hamming(hashes[i][1], hashes[j][1]) <= threshold:
                union(i, j)

    groups: dict[int, list[str]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(hashes[i][0])
    return list(groups.values())


def _run_similar_photos(args, deleter: Deleter) -> int:
    root = args.dir
    if not os.path.isdir(root):
        raise SystemExit(f"Not a directory: {root}")

    hashes: list[tuple[str, int]] = []
    for path, _st in _iter_files(root):
        ext = os.path.splitext(path)[1].lower()
        if ext not in PHOTO_EXTS:
            continue
        h = _dhash_pillow(path)
        if h is None:
            h = _dhash_sips(path)
        if h is not None:
            hashes.append((path, h))

    groups = _group_similar(hashes)
    printed = 0
    for group in groups:
        if len(group) < 2:
            continue
        printed += 1
        print(f"\nSimilar photo group ({len(group)} images):")
        for p in group:
            print(f"  {p}")
    if printed == 0:
        print("No similar photos found.")
    return 0


def _run_merge_folders(args, deleter: Deleter) -> int:
    a = args.a
    b = args.b
    if not os.path.isdir(a):
        raise SystemExit(f"Not a directory: {a}")
    if not os.path.isdir(b):
        raise SystemExit(f"Not a directory: {b}")

    moved = 0
    conflicts = 0
    for dirpath, _dirnames, filenames in os.walk(b):
        rel = os.path.relpath(dirpath, b)
        for name in filenames:
            src = os.path.join(dirpath, name)
            if os.path.islink(src):
                continue
            dst = os.path.join(a, rel, name) if rel != "." else os.path.join(a, name)
            if os.path.exists(dst):
                print(f"  conflict: {src} <-> {dst}")
                conflicts += 1
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                print(f"  moved: {src} -> {dst}")
                moved += 1
    print(f"\n{moved} moved, {conflicts} conflicts")
    return 0


def run(args, deleter: Deleter) -> int:
    if args.dup_cmd == "scan":
        return _run_scan(args, deleter)
    if args.dup_cmd == "similar-photos":
        return _run_similar_photos(args, deleter)
    if args.dup_cmd == "merge-folders":
        return _run_merge_folders(args, deleter)
    return 2
