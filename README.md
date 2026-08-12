# cleanmac

A free, CLI-only replacement for [MacCleaner Pro](https://nektony.com/mac-cleaner-pro) — the paid 6-tool macOS cleanup suite by Nektony. `cleanmac` replicates its entire feature set from the terminal, with no GUI, no telemetry, and no cost.

It combines a battle-tested **bash junk-cleanup engine** with a **Python toolkit** for the heavier tools (app uninstall, duplicate finding, disk analysis, memory, hidden-file toggling). A single `cleanmac` dispatcher routes to the right engine automatically.

---

## Feature map

| MacCleaner Pro tool | `cleanmac` command | Engine | Description |
|---|---|---|---|
| Junk Cleanup | `cleanmac` (legacy) | Bash | Caches, logs, trash, snapshots, Homebrew, dev caches, DNS/RAM, periodic maintenance |
| App Cleaner & Uninstaller | `cleanmac app` | Python | List, remove (with leftovers), reset, startup agents, extensions, updates |
| Duplicate File Finder | `cleanmac dup` | Python | Duplicate scan, similar-photo grouping, folder merging |
| Disk Space Analyzer | `cleanmac disk` | Python | Scan, top largest, summary, system-data breakdown, HTML treemap report |
| Memory Cleaner | `cleanmac mem` | Python | Free inactive RAM, list heavy consumers |
| Funter (hidden files) | `cleanmac hidden` | Python | Show/hide hidden files in Finder |

---

## Installation

`cleanmac` requires **bash 3.2+** (macOS default) and **Python 3.10+**.

```bash
cd utils/cleanmac

# 1. Create a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the Python package in editable mode (with dev/test deps)
pip install -e "py/[dev]"

# 3. Add the bin/ directory to your PATH
export PATH="$HOME/projects/utils/cleanmac/bin:$PATH"
```

After setup, `cleanmac` is available everywhere:

```bash
cleanmac              # legacy bash junk cleanup
cleanmac app list     # Python app uninstaller
```

> **Optional photo support:** `cleanmac dup similar-photos` uses [Pillow](https://python-pillow.org/) for perceptual hashing when available, and falls back to the built-in macOS `sips` tool otherwise. To install Pillow:
> ```bash
> pip install -e "py/[photos]"
> ```

---

## The dispatcher

`bin/cleanmac` is a thin dispatcher with two modes. Routing is decided by the **first argument**:

- **Legacy mode** — no args, or the first arg is not one of the five known subcommands (`app`, `dup`, `disk`, `mem`, `hidden`). Forwards to `bin/legacy_cleanmac.sh` (the bash junk-cleanup engine).
- **Python mode** — the first arg is a known subcommand. Forwards all args to `python3 -m maccleaner.cli`.

```
cleanmac                      → bash junk cleanup (live)
cleanmac --dry-run            → bash junk cleanup (dry-run)
cleanmac --app X              → bash legacy leftover search
cleanmac app list             → Python app uninstaller
cleanmac dup scan ~/Downloads → Python duplicate finder
```

The two modes parse their own flags independently — `--dry-run` means different things on each side (see [Safety model](#safety-model)).

---

## Legacy junk cleanup (bash)

The original `cleanmac` engine: an 8-step observable cleanup that runs caches, logs, trash, Homebrew, dev caches, DNS/RAM, and macOS maintenance. It asks for `sudo` **once** up front, then uses `sudo -n` for all elevated steps.

### Usage

```bash
cleanmac                # live run (deletes for real)
cleanmac --dry-run      # preview only, delete nothing
cleanmac --verbose      # detailed per-file logging in the console
cleanmac --app <name>   # search & remove leftovers of an uninstalled app
cleanmac -h | --help     # show help
```

### The 8 steps

| # | Step | What it cleans |
|---|---|---|
| 1 | User Caches | `~/Library/Caches/*` |
| 2 | System Caches | `/Library/Caches`, `/System/Library/Caches` (sudo) |
| 3 | Logs | `~/Library/Logs/*`, `/private/var/log`, `/var/log` (sudo) |
| 4 | Trash & Snapshots | `~/.Trash`, volume `.Trashes`, Time Machine local snapshots |
| 5 | Homebrew | `brew cleanup --prune=all`, `brew autoremove` |
| 6 | Dev Caches | Xcode DerivedData, Docker, npm, pip caches |
| 7 | DNS & RAM | `dscacheUtil -flushcache`, `killall mDNSResponder`, `purge` |
| 8 | Periodic | `sudo periodic daily weekly monthly` |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Usage error |
| `3` | One or more steps failed |

---

## Python subcommands

All Python subcommands share two **global flags** that must appear before the subcommand:

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | **on** (default) | Preview only, delete nothing |
| `--commit` | off | Actually delete. Without this, nothing is removed. |

```bash
cleanmac --commit app remove Slack     # real deletion
cleanmac app remove Slack              # dry-run (default) — lists what would be deleted
```

### `cleanmac app` — App Cleaner & Uninstaller

Bundle-ID-first leftover discovery: apps are matched by their `CFBundleIdentifier` (parsed from `Info.plist`), falling back to exact `CFBundleName`. Short, dangerous names (`r`, `go`, `ui`, etc.) require `--force` to prevent matching half of `~/Library`.

| Subcommand | Description |
|---|---|
| `app list` | List installed apps with bundle id + size |
| `app remove <app> [--force]` | Remove an app and its leftovers (user + system) |
| `app reset <app>` | Reset app settings (keeps the app) |
| `app startup list` | List LaunchAgents/LaunchDaemons with running state |
| `app startup disable <label>` | Stop and disable a startup agent (modern `launchctl bootout`) |
| `app extensions` | List Chrome/Safari/Firefox extensions |
| `app update` | Check for outdated apps (`mas outdated`, `brew outdated --cask`) |

```bash
cleanmac app list
cleanmac app remove Slack
cleanmac app remove slack --force
cleanmac app reset Slack
cleanmac app startup list
cleanmac app startup disable com.example.updater
cleanmac app extensions
cleanmac app update
```

`app remove` scans 17 user-level and 5 system-level leftover path patterns (Application Support, Caches, Preferences, Containers, Group Containers, Saved State, WebKit, HTTPStorages, Cookies, LaunchAgents, Services, Quicklook, Spotlight, LaunchDaemons, receipts, etc.). System-level leftovers are removed via `sudo`.

### `cleanmac dup` — Duplicate File Finder

Size-first grouping, streaming hash, hard-link/symlink skipping, and a SQLite incremental cache for fast re-scans.

| Subcommand | Description |
|---|---|
| `dup scan <dir> [--min-size 1M] [--hash sha256\|md5]` | Find duplicate files |
| `dup similar-photos <dir>` | Find similar photos (dHash perceptual hashing) |
| `dup merge-folders <a> <b>` | Merge folder `b` into `a` (reports conflicts) |

```bash
cleanmac dup scan ~/Downloads
cleanmac dup scan ~/Downloads --min-size 10M --hash md5
cleanmac dup similar-photos ~/Pictures
cleanmac dup merge-folders ~/Photos/2023 ~/Photos/2024
```

`dup scan` groups files by size first, then hashes only equal-size groups in 1 MB streaming chunks. Hard links (`st_nlink > 1`) are de-duplicated by inode so deleting one copy never breaks the other. The SQLite cache (`dup-index.db`) keys on `(path, st_ino, st_dev, st_mtime_ns, st_size)` and skips re-hashing unchanged files. The oldest copy in each group is kept by default.

`dup similar-photos` computes a 64-bit dHash (9×8 grayscale → 64-bit) and groups photos with Hamming distance ≤ 10. Uses Pillow when installed, otherwise falls back to `sips`.

### `cleanmac disk` — Disk Space Analyzer

Iterative (non-recursive) traversal so deep trees never hit `RecursionError`. Skips sockets, FIFOs, devices, symlinks, and network mounts (nfs/smbfs/afpfs/webdav/autofs).

| Subcommand | Description |
|---|---|
| `disk scan <dir>` | Scan directory sizes (top 10 largest) |
| `disk top` | Top 25 largest files/folders under home |
| `disk summary` | Top-level directory sizes (the "what's eating my disk" view) |
| `disk system-data` | Break down system data (caches, logs, containers, Docker, Xcode, npm, pip, iOS backups) |
| `disk report <dir> [--out FILE]` | Generate a self-contained HTML treemap report |

```bash
cleanmac disk scan ~/projects
cleanmac disk top
cleanmac disk summary
cleanmac disk system-data
cleanmac disk report ~/projects --out projects-treemap.html
```

`disk report` writes a single self-contained HTML file with an inline squarified treemap, hover tooltips, and click-to-drill-down navigation. Open it in any browser.

### `cleanmac mem` — Memory Cleaner

| Subcommand | Description |
|---|---|
| `mem free` | Purge inactive RAM (requires `sudo`) |
| `mem heavy` | List top 10 CPU/RAM consumers; optionally kill by PID |

```bash
cleanmac mem free
cleanmac mem heavy
```

`mem free` runs `sudo purge` and reports free memory before/after. `mem heavy` sorts processes by resident set size (RSS); if run in a TTY it offers to send `TERM` to a PID.

### `cleanmac hidden` — Hidden Files Toggle

| Subcommand | Description |
|---|---|
| `hidden show` | Show hidden files in Finder |
| `hidden hide` | Hide hidden files in Finder |

```bash
cleanmac hidden show
cleanmac hidden hide
```

Sets `com.apple.finder.AppleShowAllFiles` and restarts Finder.

---

## Safety model

`cleanmac` is designed so that **nothing is ever deleted by accident**.

### Dry-run by default (Python subcommands)

Every Python subcommand runs in **dry-run mode by default**. Deletion only happens when you explicitly pass `--commit`:

```bash
cleanmac app remove Slack          # dry-run — lists what would be deleted, deletes nothing
cleanmac --commit app remove Slack # real deletion
```

This is enforced at the leaf, not just the CLI layer: the `Deleter` class in `core.py` is a no-op unless `commit=True`, so every code path that reaches deletion is gated.

> **Note:** the legacy bash engine is **live by default** (backward compatible). Pass `--dry-run` to preview. This asymmetry is intentional — the bash engine predates the Python toolkit.

### `safe_rm` — protected roots

Every deletion goes through `is_safe_path()`, which resolves symlinks via `realpath` and refuses anything outside a known-safe whitelist:

- **Protected roots** (never deleted): `/`, `/System`, `/Library`, `/Applications`, `/Users`, `/usr`, `/bin`, `/etc`, `/private`, `/var`, `/opt`, `/sbin`, `/dev`, `/tmp`
- **Protected home subdirs**: `.ssh`, `.aws`, `.gnupg`, `.config`, `.Trash`
- **Safe prefixes** (deletable): your home directory, `/Applications`, `/Volumes`, `/tmp`, and the macOS temp sandbox (`/private/var/folders`)

Any path that doesn't live under a known-safe prefix is refused, regardless of `--commit`.

### Per-path confirmation

In `--commit` mode, each path (or group) requires interactive `y/N` confirmation when stdin is a TTY. Unsafe paths are never touched — they are audited as `refused`.

### One sudo prompt

Both engines ask for `sudo` **once** per invocation (`sudo -v`), then use `sudo -n` for all subsequent elevated commands. If elevation is unavailable, elevated steps are skipped gracefully rather than failing the run.

---

## Observability

Every run produces structured, machine-readable artifacts.

### Bash engine

| Artifact | Location | Format |
|---|---|---|
| Structured logs | `~/.local/state/cleanmac/logs/cleanmac-<ts>.jsonl` | JSONL — one event per line |
| Audit trail | `~/.local/state/cleanmac/audit/audit-<ts>.jsonl` | JSONL — every delete/action |
| Run report | `~/.local/state/cleanmac/report-<ts>.json` | JSON — summary with per-step freed bytes, duration, exit code |

The console shows an `[n/8]` step counter, a progress bar, per-step freed bytes + time, and a final summary table.

### Python engine

| Artifact | Location | Format |
|---|---|---|
| Audit trail | `~/.local/state/cleanmac/audit/audit-<ts>.jsonl` | JSONL — same format as bash |

The Python `Auditor` writes the same JSONL audit format, so bash and Python audit records are unified.

### Retention

Logs and audits are auto-pruned to **30 days** after each bash run.

---

## State directory layout

```
~/.local/state/cleanmac/
├── logs/
│   └── cleanmac-<ts>.jsonl     # bash structured logs
├── audit/
│   └── audit-<ts>.jsonl        # audit trail (bash + Python)
├── report-<ts>.json            # bash run reports
└── dup-index.db                # Python duplicate-finder SQLite cache
```

### Environment overrides

| Variable | Default | Purpose |
|---|---|---|
| `CLEANMAC_STATE_DIR` | `~/.local/state/cleanmac` | State directory root |
| `CLEANMAC_LOG_DIR` | `$CLEANMAC_STATE_DIR/logs` | Bash log directory |
| `CLEANMAC_AUDIT_DIR` | `$CLEANMAC_STATE_DIR/audit` | Audit directory |
| `CLEANMAC_HOME` | `$HOME` | Home directory (Python — for tests) |
| `CLEANMAC_SYS_CACHES` / `CLEANMAC_SYS_CACHES2` | `/Library/Caches`, `/System/Library/Caches` | System cache dirs (bash — for tests) |
| `CLEANMAC_SYS_LOGS` / `CLEANMAC_SYS_LOGS2` | `/private/var/log`, `/var/log` | System log dirs (bash — for tests) |

---

## Project structure

```
cleanmac/
├── bin/
│   ├── cleanmac              # dispatcher: legacy bash OR Python subcommands
│   └── legacy_cleanmac.sh    # legacy bash junk cleanup (8 steps)
├── lib/
│   ├── log.sh                # JSONL logging, audit, report, step framing, retention
│   └── steps.sh              # one function per cleanup step (idempotent, self-reporting)
├── py/
│   ├── pyproject.toml        # Python project config (setuptools, pytest, ruff)
│   ├── src/maccleaner/
│   │   ├── __init__.py        # version
│   │   ├── cli.py             # argparse dispatcher (--dry-run/--commit + subcommands)
│   │   ├── core.py            # shared safety core (safe_rm, Deleter, Auditor, Sudo)
│   │   ├── app_uninstaller.py # app list/remove/reset/startup/extensions/update
│   │   ├── disk_analyzer.py   # disk scan/top/summary/system-data/report
│   │   ├── duplicates.py      # dup scan/similar-photos/merge-folders
│   │   ├── memory.py          # mem free/heavy
│   │   └── hidden_files.py    # hidden show/hide
│   └── tests/
│       ├── test_core.py
│       ├── test_app_uninstaller.py
│       ├── test_disk_analyzer.py
│       ├── test_duplicates.py
│       ├── test_hidden_files.py
│       └── test_memory.py
├── tests/
│   └── run_tests.sh          # bash test suite (zero-dependency, sandboxed)
├── README.md
└── .gitignore
```

---

## Testing

### Python tests

```bash
cd py
pytest                    # run all Python tests
pytest tests/test_core.py # run a single test module
```

The Python test suite covers: `safe_rm` refusing all protected roots and symlink aliases, audit writing valid JSONL, dry-run guard blocking deletes, app uninstaller finding all leftover patterns with bundle-ID matching, duplicate finder correctness (min-size, hard links, symlinks), disk analyzer iterative traversal on deep trees, and hidden-files toggle.

### Bash tests

```bash
tests/run_tests.sh
```

The bash suite is zero-dependency: it sandboxes `HOME`, stubs `sudo`/`brew`/`docker`/`npm`/`pip`/`tmutil`, and verifies exit codes, dry-run deletes nothing, live runs free space, logs/audit/report content, and console observability.

---

## Subcommand reference

| Command | Subcommands |
|---|---|
| `cleanmac` (legacy) | *(no subcommand)* — `--dry-run`, `--verbose`, `--app <name>`, `-h`/`--help` |
| `cleanmac app` | `list`, `remove`, `reset`, `startup`, `extensions`, `update` |
| `cleanmac dup` | `scan`, `similar-photos`, `merge-folders` |
| `cleanmac disk` | `scan`, `top`, `summary`, `system-data`, `report` |
| `cleanmac mem` | `free`, `heavy` |
| `cleanmac hidden` | `show`, `hide` |

Global Python flags: `--dry-run` (default), `--commit`, `--version`.
