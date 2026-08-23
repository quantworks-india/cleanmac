# Implementation Plan: Native inventory (zero custom parsers)

## Overview

Replace hand-rolled regex, brand dictionaries, and text scrapers with Apple/stdlib structured APIs. Goal: **zero regex, zero `ORPHAN_BRANDS`, zero `vm_stat`/`mount` scrapers**. Two thin line-readers remain because Apple does not publish JSON for `sfltool dumpbtm` or `launchctl print`.

This is a refactor of existing `app orphans` / `app bba` / memory / disk behavior — not a new product surface.

## Architecture Decisions

- **Stay on `feat/observability`.** One consolidated feature branch.
- **Installed apps** come from `system_profiler SPApplicationsDataType -json` (`json.loads`). Cache once per process. Fallback: current two-dir glob only if profiler fails (tests can inject a fake list).
- **Helper → parent app** comes from Apple’s `attributions.plist` via `plistlib` (documented in Apple Platform Deployment). Path is resolved at runtime; tests inject a fixture plist.
- **BAA inventory source stays `sfltool dumpbtm`.** Official, text-only. Parse with a line state machine (`splitlines` + `partition(":")`). No `re`.
- **Launchd live state** stays `launchctl print`. One `startswith("state")` / `partition("=")` line. No `re`.
- **Memory free bytes** from `sysctl -n hw.pagesize`, `vm.page_free_count`, `vm.page_speculative_count`. Integers only.
- **Network mounts** from `diskutil list -plist` + `diskutil info -plist` (`plistlib`).
- **Single orphan engine.** After native inventory works, `find_orphans()` (plist walk + brands) is deleted or reduced to a `sfltool`-missing fallback. CLI: keep `app orphans` as the user command; `app bba` becomes an alias or is removed in the last slice.
- **Orphan rule (mechanical):** resolve BTM URL / executable / associated bundle IDs; map helper via attributions; live if parent bundle or executable exists; else orphan. No brand substring lists.
- **Do not** parse `backgrounditems.btm` binaries, add PyObjC/SMAppService enumeration, or parse `launchctl dumpstate`.
- **PII:** no home-directory or personal paths in tests/docs. Use `tmp_path` and relative paths.

## Task List

Tasks live in `tasks/todo.md` (this repo has no external tracker).

### Phase 1: Foundation (identity)

- Task 1: Installed-app inventory via `system_profiler -json`
- Task 2: Helper→parent map via `attributions.plist`

### Checkpoint: Foundation

- Tests pass, ruff clean
- Review: profiler cache + attributions fixture look right

### Phase 2: Cheap native replacements

- Task 3: Memory via `sysctl -n`
- Task 4: Disk mounts via `diskutil … -plist`

### Checkpoint: Cheap replacements

- Existing memory/disk tests updated and green
- No `re` in `memory.py`; no `mount(8)` string split in `disk_analyzer.py`

### Phase 3: BAA / orphans

- Task 5: Line-state `dumpbtm` parser (delete regex)
- Task 6: Mechanical orphan rule (attributions + inventory)
- Task 7: Collapse dual orphan engines + CLI

### Checkpoint: Orphans

- `cleanmac app orphans list` uses sfltool inventory
- `ORPHAN_BRANDS` gone
- `import re` gone from `bba.py`

### Phase 4: Close-out

- Task 8: README + residual `ps` cleanup
- Checkpoint: Complete — ready for review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `system_profiler -json` is slow (~1s) | Med | Cache per process; tests inject fixture JSON |
| `attributions.plist` lives under PrivateFrameworks | Med | Apple documents it; wrap load; empty map if missing |
| `sfltool dumpbtm` format drifts | High | Line parser + golden fixture from a captured dump (no host PII) |
| Dual CLI (`orphans` vs `bba`) confuses users mid-refactor | Low | Keep both working until Task 7; then alias |
| `diskutil info -plist` per volume is N calls | Low | Only inspect volumes from `diskutil list -plist` |
| Tests currently mock regex parser | Med | Rewrite BBA tests against fixture dump text, not regex internals |

## Open Questions

- Keep `app bba` as a documented alias after collapse, or remove it?
- Fail closed (no orphans listed) if `sfltool` missing, or fall back to launch-plist walk?
- Cache `system_profiler` only in-process, or also on disk under the state dir?

## Parallelization

- Tasks 3 and 4 are independent of each other and of Task 5 **after** Task 1 exists (they do not share files with BBA).
- Do **not** parallel-edit `app_uninstaller.py` (Tasks 2, 6, 7 overlap). Serialize those.
- Task 5 can start after Task 1 if `bba.py` only *calls* the inventory module, not `app_uninstaller`.

## Verification (plan-level)

- Every task has acceptance criteria in `tasks/todo.md`
- Dependencies ordered foundation → cheap replacements → BAA → collapse
- No task is XL
- Human approves this plan before implementation
