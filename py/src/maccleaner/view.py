"""Display primitives for human-readable CLI output.

Pure string formatters — no I/O, no third-party deps. Color only when
explicitly enabled (callers gate on isatty()/NO_COLOR).
"""

from __future__ import annotations

# ANSI codes (subset)
_CODES: dict[str, str] = {
    "bold": "\x1b[1m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "cyan": "\x1b[36m",
    "reset": "\x1b[0m",
}


def color(style: str, text: str, enabled: bool = True) -> str:
    """Wrap ``text`` in an ANSI escape for ``style``; no-op if disabled."""
    if not enabled or style not in _CODES:
        return text
    return f"{_CODES[style]}{text}{_CODES['reset']}"


def human_size(num_bytes: int) -> str:
    """Human-readable byte size (B / KB / MB / GB / TB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def table(headers: list[str], rows: list[list[str]]) -> str:
    """Render an aligned table. Empty rows produce a single ``(none)`` line."""
    if not rows:
        return "(none)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    def fmt(r: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) if i < len(widths) else cell
                         for i, cell in enumerate(r))

    lines = [fmt(headers)]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


def section(title: str) -> str:
    """Render a section header with an underline."""
    return f"{title}\n{'-' * len(title)}"


def status(level: str, message: str, enabled: bool = True) -> str:
    """Render a status line like ``ok  Cleaned 3 items``."""
    color_map = {"ok": "green", "warn": "yellow", "error": "red", "info": "cyan"}
    label = color(color_map.get(level, "info"), level, enabled=enabled)
    return f"{label}  {message}"


def dryrun_banner(enabled: bool = True) -> str:
    """Render the dry-run notice shown when nothing is being deleted."""
    return color("yellow", "dry-run: nothing will be deleted", enabled=enabled)
