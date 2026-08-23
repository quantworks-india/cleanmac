# cleanmac

A battle-tested, CLI-first macOS system utility suite — free, zero-telemetry, no GUI.

Clean every layer: junk caches, app leftovers, duplicate files, disk space, memory, and hidden files — entirely from the terminal.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-1e1e1e.svg)](https://macos.com)

---

## Why cleanmac?

| Feature | Engine |
|---|---|
| **Junk cleanup** | Bash — 8-step observable cleanup (caches, logs, trash, Homebrew, dev caches, DNS/RAM, maintenance) |
| **App uninstaller** | Python — bundle-ID-first leftover removal, startup agents, extensions, updates |
| **Duplicate finder** | Python — size-first grouping, streaming hashes, hard-link/symlink-aware, SQLite cache |
| **Disk analyzer** | Python — iterative scan, top largest, summary, system-data breakdown, HTML treemap report |
| **Memory cleaner** | Python — purge inactive RAM, list top CPU/RAM consumers |
| **Hidden files** | Python — show/hide in Finder with a single command |

---

## Quick start

```bash
# 1. Clone & enter
git clone git@github.com:quantworks-india/cleanmac.git
cd cleanmac

# 2. Python venv (3.10+)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode (with dev deps)
pip install -e "py/[dev]"

# 4. Add to PATH
export PATH="$HOME/projects/utils/cleanmac/bin:$PATH"

# 5. Try it
cleanmac                    # live 8-step junk cleanup
cleanmac --dry-run          # preview only
cleanmac app list           # list installed apps
cleanmac dup scan ~/Downloads  # find duplicates
cleanmac disk summary       # disk usage breakdown
cleanmac mem free           # purge inactive RAM
cleanmac hidden show        # show hidden files
```

---

## Subcommand reference

| Command | What it does |
|---|---|
| `cleanmac` (no args) | Bash junk cleanup (live) |
| `cleanmac --dry-run` | Bash junk cleanup (preview) |
| `cleanmac app list` | List installed apps with bundle ID + size |
| `cleanmac app remove <name>` | Remove app + leftovers (dry-run by default) |
| `cleanmac app remove <name> --force` | Allow dangerous short names |
| `cleanmac dup scan <dir>` | Find duplicate files |
| `cleanmac dup similar-photos <dir>` | Find similar photos (dHash) |
| `cleanmac disk scan <dir>` | Scan directory sizes |
| `cleanmac disk top` | Top 25 largest under home |
| `cleanmac disk summary` | Top-level directory breakdown |
| `cleanmac disk system-data` | System data breakdown (Docker, Xcode, npm, pip, etc.) |
| `cleanmac disk report <dir> --out <file>` | HTML treemap report |
| `cleanmac mem free` | Purge inactive RAM (sudo) |
| `cleanmac mem heavy` | List top CPU/RAM consumers |
| `cleanmac hidden show` | Show hidden files in Finder |
| `cleanmac hidden hide` | Hide hidden files in Finder |
| `cleanmac app startup list` | List all LaunchAgents/LaunchDaemons with state |
| `cleanmac app startup list --orphans-only` | **List only orphaned agents from apps you no longer have installed** |
| `cleanmac app orphans` | Shortcut for the above |
| `cleanmac app orphans list` | Same as `cleanmac app orphans` |
| `cleanmac app orphans purge` | Bootout + move orphaned plists to `~/Library/LaunchAgents-disabled` (dry-run; use `--commit` to act) |
| `cleanmac app bba list` | Show Background App Activity items whose app/daemon is uninstalled (uses Apple `sfltool dumpbtm`) |
| `cleanmac app bba purge` | Bootout + quarantine BAA orphans (dry-run; use `--commit` to act) |
| `cleanmac app startup disable <label>` | Safely disable one (moves plist + launchctl bootout) |


Global flags (must appear before subcommand):

| Flag | Default | Description |
|---|---|---|
| `--dry-run` | **on** | Preview only, delete nothing |
| `--commit` | off | Actually delete. Without this, nothing is removed |
| `--json` | off | Emit one structured JSON event per line on stdout (pipe to `jq`) |
| `--verbose` | off | Print debug-level progress (file-by-file, scan counters) |

### JSON output

`--json` rewrites stdout as newline-delimited JSON events:

```bash
cleanmac --json hidden show | jq .
# {"level": "info", "event": "hidden_files_toggled", "state": "shown"}
```

Use it from scripts:

```bash
duplicates=$(cleanmac --json dup scan ~/Downloads | jq -c 'select(.event=="dup_scan_complete") | .reclaimable_bytes')
```

The existing JSONL audit log in `~/.local/state/cleanmac/audit/` is unchanged — `--json` only affects stdout.

### Verbose output

`--verbose` adds debug-level events (hash progress, scan counters). Useful for long-running scans:

```bash
cleanmac --verbose dup scan ~/Downloads
```

Bash `--verbose` is forwarded to Python so a single flag enables verbose output across both engines.

---

## Safety model

**Nothing is ever deleted by accident.**

- **Dry-run by default** (Python subcommands). Delete only with `--commit`.
- **`safe_rm`** — every path resolved via `realpath` and checked against a whitelist. Protected roots (`/`, `/System`, `/Library`, `/Applications`, `/Users`, `/usr`, `/bin`, `/etc`, `/private`, `/var`, `/opt`, `/sbin`, `/dev`, `/tmp`) and protected home subdirs (`.ssh`, `.aws`, `.gnupg`, `.config`, `.Trash`) are never deleted.
- **One `sudo` prompt** per invocation, then `sudo -n` for all elevated steps. If elevation unavailable, elevated steps are skipped gracefully.
- **Per-path confirmation** in `--commit` mode when stdin is a TTY.

---

## State directory

```
~/.local/state/cleanmac/
├── logs/           # bash structured logs (auto-pruned to 30 days)
├── audit/          # JSONL audit trail (bash + Python unified)
├── report-<ts>.json  # bash run report
└── dup-index.db    # Python duplicate-finder SQLite cache
```

Audit JSONL schema (one event per line):

| Field | Type | Notes |
|---|---|---|
| `ts` | ISO 8601 UTC | Timestamp of the event |
| `run` | string | Run ID (correlates with bash run) |
| `mode` | `dry-run` or `live` | |
| `step` | string | e.g. `dup_scan`, `app_remove` |
| `action` | string | e.g. `deleted`, `would_delete`, `refused` |
| `path` | string | Absolute path |
| `size_bytes` | int | Size in bytes (for delete events) |
| `duration_ms` | int | Only present when the operation recorded timing |

Query the audit log with `jq`:

```bash
# all dup_scan deletions from today
jq 'select(.step=="dup_scan" and .action=="deleted")' ~/.local/state/cleanmac/audit/*.jsonl

# timing of completed scans
jq 'select(.duration_ms) | {step, duration_ms}' ~/.local/state/cleanmac/audit/*.jsonl
```

Environment variables: `CLEANMAC_STATE_DIR`, `CLEANMAC_HOME`, `CLEANMAC_SYS_CACHES`, `CLEANMAC_SYS_LOGS`.

---

## Installation

`cleanmac` requires **bash 3.2+** (macOS default) and **Python 3.10+**.

```bash
# Create venv & activate (see Quick start steps 2-4 above)
pip install -e "py/[dev]"
export PATH="$HOME/projects/utils/cleanmac/bin:$PATH"
```

---

## Development

```bash
# Run all Python tests
cd py && .venv/bin/pytest

# Lint
ruff check py/src/ py/tests/

# Format
ruff format py/src/ py/tests/
```

---

## License

MIT. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

Inspired by the feature set of [MacCleaner Pro](https://nektony.com/mac-cleaner-pro) — cleanmac replicates its entire toolset from the terminal, free, with no GUI and no telemetry.