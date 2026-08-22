"""Disk Space Analyzer.

Iterative (non-recursive) traversal so deep trees never hit RecursionError.
Skips sockets/fifos/devices, network mounts, and SIP-protected entries.
Generates a self-contained HTML treemap report.
"""

from __future__ import annotations

import html
import json
import os
import stat
import subprocess
from pathlib import Path

NETWORK_MOUNT_TYPES = {"nfs", "smbfs", "afpfs", "webdav", "autofs", "cifs"}


def _network_mount_points() -> set[str]:
    """Set of mount points on network filesystems (via mount(8))."""
    mounts: set[str] = set()
    try:
        out = subprocess.run(
            ["mount"], capture_output=True, text=True, check=False, timeout=5
        )
        for line in out.stdout.splitlines():
            parts = line.split(" on ")
            if len(parts) < 2:
                continue
            fstype = (
                parts[0].split(",")[-1] if "," in parts[0] else parts[0].split()[-1]
            )
            if any(t in fstype for t in NETWORK_MOUNT_TYPES):
                mp = parts[1].split(" (")[0].strip()
                mounts.add(mp)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return mounts


def _walk(root: str) -> list[dict]:
    """Iterative scan. Returns list of {path, size, is_dir} for every entry.

    Uses an explicit stack (no recursion). Skips symlinks, non-regular
    entries, network mounts, and swallows permission errors per-entry.
    """
    root = os.path.realpath(root)
    net_mounts = _network_mount_points()
    results: list[dict] = []
    stack: list[str] = [root]

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            results.append({"path": current, "size": 0, "is_dir": True, "error": True})
            continue

        for entry in entries:
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            # skip symlinks entirely
            if stat.S_ISLNK(st.st_mode):
                continue
            is_dir = stat.S_ISDIR(st.st_mode)
            if is_dir:
                # skip network mounts
                if entry.path in net_mounts:
                    continue
                stack.append(entry.path)
                results.append({"path": entry.path, "size": st.st_size, "is_dir": True})
            elif stat.S_ISREG(st.st_mode):
                results.append(
                    {"path": entry.path, "size": st.st_size, "is_dir": False}
                )
            # sockets/fifos/devices: skip
    return results


def dir_sizes(root: str) -> dict[str, int]:
    """Map of dir path → total size (sum of all descendants).

    Every entry (file or dir) accumulates its size into its parent.
    Deepest-first ensures a child's total is complete before it rolls
    into its parent. Root is seeded at 0 so it accumulates correctly.
    """
    root = os.path.realpath(root)
    entries = _walk(root)
    sizes: dict[str, int] = {root: 0}
    for e in entries:
        sizes[e["path"]] = 0 if e["is_dir"] else e["size"]
    for e in sorted(entries, key=lambda x: len(x["path"]), reverse=True):
        parent = os.path.dirname(e["path"])
        sizes[parent] = sizes.get(parent, 0) + sizes[e["path"]]
    return sizes


def scan(root: str) -> tuple[dict[str, int], int]:
    """Return (dir→size map, total bytes)."""
    if not os.path.isdir(root):
        raise SystemExit(f"Not a directory: {root}")
    sizes = dir_sizes(root)
    return sizes, sizes.get(os.path.realpath(root), 0)


def top_largest(sizes: dict[str, int], n: int = 25) -> list[tuple[str, int]]:
    return sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:n]


def _size_b(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f}K"
    if b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f}M"
    return f"{b / (1024 * 1024 * 1024):.2f}G"


def _run_scan(args) -> int:
    sizes, total = scan(args.dir)
    print(f"Scan of {args.dir}: {_size_b(total)}")
    for path, size in top_largest(sizes, 10):
        if path == os.path.realpath(args.dir):
            continue
        print(f"  {_size_b(size):>10}  {path}")
    return 0


def _run_top(args) -> int:
    # top requires a scan; default to home
    target = getattr(args, "dir", None) or str(Path.home())
    sizes, _ = scan(target)
    print(f"Top 25 largest under {target}:")
    for i, (path, size) in enumerate(top_largest(sizes, 25), 1):
        if size == 0:
            continue
        print(f"  {i:>2}. {_size_b(size):>10}  {path}")
    return 0


def _run_summary(args) -> int:
    target = getattr(args, "dir", None) or str(Path.home())
    sizes, _ = scan(target)
    root = os.path.realpath(target)
    top = sorted(
        ((p, s) for p, s in sizes.items() if os.path.dirname(p) == root and s > 0),
        key=lambda kv: kv[1],
        reverse=True,
    )
    print(f"Top-level breakdown of {target} ({_size_b(sum(s for _, s in top))}):")
    for path, size in top:
        print(f"  {_size_b(size):>10}  {os.path.basename(path) or path}")
    return 0


def _run_system_data(args) -> int:
    home = Path(os.environ.get("CLEANMAC_HOME", Path.home()))
    targets = {
        "User caches": home / "Library/Caches",
        "User logs": home / "Library/Logs",
        "Containers": home / "Library/Containers",
        "Application Support": home / "Library/Application Support",
        "Trash": home / ".Trash",
        "Docker": home / "Library/Containers/com.docker.docker",
        "Xcode DerivedData": home / "Library/Developer/Xcode/DerivedData",
        "npm cache": home / ".npm",
        "pip cache": home / "Library/Caches/pip",
        "iOS backups": home / "Library/Application Support/MobileSync/Backup",
    }
    print("System data breakdown:")
    total = 0
    for label, p in targets.items():
        if not p.exists():
            continue
        # size via du (fast, handles symlinks/SIP)
        try:
            out = subprocess.run(
                ["du", "-sk", str(p)], capture_output=True, text=True, check=False
            )
            kb = int(out.stdout.split()[0]) if out.returncode == 0 else 0
        except (OSError, ValueError, IndexError):
            kb = 0
        if kb > 0:
            total += kb
            print(f"  {_size_b(kb * 1024):>10}  {label}  ({p})")
    print(f"  Total: {_size_b(total * 1024)}")
    return 0


def _build_treemap_json(sizes: dict[str, int], root: str) -> dict:
    """Build nested treemap structure from flat dir→size map."""
    root_real = os.path.realpath(root)

    def node(path: str) -> dict:
        children: list[dict] = []
        for child_path, child_size in sizes.items():
            if (
                os.path.dirname(child_path) == path
                and child_size > 0
                and (sizes.get(child_path, 0) > 0 or os.path.isdir(child_path))
            ):
                children.append(node(child_path))
        return {
            "name": os.path.basename(path) or path,
            "path": path,
            "size": sizes.get(path, 0),
            "children": children,
        }

    return node(root_real)


def _run_report(args) -> int:
    sizes, _ = scan(args.dir)
    treemap = _build_treemap_json(sizes, args.dir)
    # simple squarified-ish treemap in JS, self-contained
    data_json = json.dumps(treemap)
    out = args.out
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Disk Treemap — {html.escape(args.dir)}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #1e1e1e; color: #ddd; }}
  h1 {{ font-size: 18px; }}
  #map {{ width: 100%; height: 80vh; border: 1px solid #333; }}
  .tile {{ position: absolute; overflow: hidden; box-sizing: border-box;
           border: 1px solid #1e1e1e; cursor: pointer; font-size: 10px; }}
  .tile:hover {{ border-color: #fff; }}
  #info {{ margin-top: 10px; font-size: 13px; font-family: monospace; }}
</style>
</head>
<body>
<h1>Disk Treemap — {html.escape(args.dir)}</h1>
<div id="map"></div>
<div id="info">Hover a tile for details. Click to drill down.</div>
<script>
const data = {data_json};
const map = document.getElementById('map');
const info = document.getElementById('info');
let root = data;

function colorFor(name, size, parentSize) {{
  const hue = (hash(name) * 137.508) % 360;
  const frac = parentSize ? Math.sqrt(size / parentSize) : 0.5;
  const light = 25 + frac * 35;
  return `hsl(${{hue}}, 60%, ${{light}}%)`;
}}
function hash(s) {{ let h = 0; for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i); return Math.abs(h); }}

function render(node) {{
  map.innerHTML = '';
  const rect = map.getBoundingClientRect();
  layout(node, 0, 0, rect.width, rect.height, rect.width);
}}

function layout(node, x, y, w, h) {{
  const div = document.createElement('div');
  div.className = 'tile';
  div.style.left = x + 'px'; div.style.top = y + 'px';
  div.style.width = w + 'px'; div.style.height = h + 'px';
  div.style.background = colorFor(node.name, node.size, root.size);
  div.textContent = node.name + ' (' + fmt(node.size) + ')';
  div.title = node.path + ' — ' + fmt(node.size);
  div.onmouseenter = () => info.textContent = node.path + ' — ' + fmt(node.size);
  div.onclick = (e) => {{ e.stopPropagation();
    if (node.children && node.children.length) {{ root = node; render(root); }}
    else {{ info.textContent = node.path + ' (leaf)'; }}
  }};
  map.appendChild(div);

  if (!node.children || !node.children.length) return;
  const kids = [...node.children].sort((a, b) => b.size - a.size);
  let i = 0;
  for (const child of kids) {{
    if (w >= h) {{
      const cw = (w * child.size) / node.size;
      layout(child, x + i * cw, y, cw, h); i += (w * child.size) / node.size;
    }} else {{
      const ch = (h * child.size) / node.size;
      layout(child, x, y + i * ch, w, ch); i += (h * child.size) / node.size;
    }}
  }}
}}
function fmt(b) {{
  if (b >= 1e9) return (b/1e9).toFixed(2)+'G';
  if (b >= 1e6) return (b/1e6).toFixed(1)+'M';
  if (b >= 1e3) return (b/1e3).toFixed(1)+'K';
  return b+'B';
}}
render(root);
</script>
</body>
</html>"""
    Path(out).write_text(html_body, encoding="utf-8")
    print(f"Report written to {out}")
    return 0


def run(args) -> int:
    if args.disk_cmd == "scan":
        return _run_scan(args)
    if args.disk_cmd == "top":
        return _run_top(args)
    if args.disk_cmd == "summary":
        return _run_summary(args)
    if args.disk_cmd == "system-data":
        return _run_system_data(args)
    if args.disk_cmd == "report":
        return _run_report(args)
    return 2
