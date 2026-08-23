# Implementation Plan: CLI performance

## Overview

Measure-first. On this machine the product commands that feel slow are not
the view layer — they are unbounded filesystem walks and N+1 Apple CLI
calls. This plan cuts those costs with the same native tools (`du`,
`launchctl`, `sfltool`), then re-measures. Neutral changes get reverted.

Replaces the completed CLI-output plan (shipped). One live plan set only.

## Baseline (this host, 2026-08-23)

| Command | Wall | What actually ran |
|---------|------|-------------------|
| `disk summary` (home) | **35.5s** | Python walk of **936,608** paths, then rollup — to print ~60 top-level rows |
| `disk top` / `disk scan` | ~35s | Same full walk |
| `disk system-data` | **7.4s** | Sequential `du -sk` of large Library trees |
| `app startup list` | **2.5s** | `system_profiler` (~1.6s) + **one `launchctl print` per user plist** (no timeout) |
| `app list` | **0.84s** | 21 apps × `du -sk` |
| `app uninstall --name Code` | 0.44s | OK |
| `mem heavy` / `hidden show` | 0.08s | OK |
| `app orphans list` | **30s fail** | `sfltool dumpbtm` hung; timeout already added |

`system_profiler` cold = 1.57s, cache hit = 0.000s (already cached per process).

## Architecture decisions

- Stay on `feat/observability`.
- **Match work to the question.** `disk summary` needs only immediate children. `disk top` needs a full size map but must not keep every file path in RAM.
- Prefer one native `du` over a Python walk of 900k nodes.
- Do not call `system_profiler` unless orphan detection needs the name set.
- Do not N+1 `launchctl print`. One dump or skip live state.
- `sfltool` stays official; cache the dump in-process; keep a hard timeout (consider 8s, fail closed).
- No new deps. No disk cache of profiler JSON in v1 (PII + staleness).
- Re-measure the same command after each task. If delta is inside noise, revert.
- Log attempts in `tasks/perf-ledger.md` (kept and reverted).

## Target budgets

| Command | Budget |
|---------|--------|
| `disk summary` home | < 3s |
| `disk top` home | < 15s (hard; still a full size job) |
| `disk system-data` | < 4s |
| `app startup list` | < 0.8s |
| `app list` | < 0.4s |
| `app orphans list` | fail in ≤ 8s if BTM hung; < 3s when `sfltool` is healthy |
| Interactive picker | no `du` of every app before first paint |

## Task list

See `tasks/todo.md`.

### Phase 1: Disk (the 35s problem)
- Task 1: `disk summary` = depth-1 only
- Task 2: `disk top`/`scan` = dir-only rollup or one `du`, no 936k-path dict

### Checkpoint: Disk
- Re-measure summary and top vs baseline
- Tests + ruff

### Phase 2: N+1 CLI
- Task 3: `startup list` — no profiler unless orphans; no per-plist `launchctl`
- Task 4: `list_apps` — lazy/skip size for picker; one-pass sizes for `app list`
- Task 5: `sfltool` in-process cache + shorter timeout

### Checkpoint: Interactive
- Re-measure startup list, app list, orphans
- Tests + ruff

### Phase 3: Guard
- Task 6: `disk system-data` one-pass / parallel `du`; perf ledger + a cheap regression test

### Checkpoint: Complete
- Ledger filled; budgets met or documented as remaining

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `du` output locale/path spaces | Med | `du -sk --` + split on first whitespace (existing pattern) |
| Depth-1 summary misses nested “where is my space” | Low | That is `disk top`’s job |
| Skipping launchctl state looks like a feature loss | Med | Keep a `?` or one `launchctl print gui/UID` parse |
| Shorter sfltool timeout false-fails | Med | 8s; fail closed; message already exists |
| Parallel `du` thrashes disk | Med | Sequential one-level `du` first; parallel only if still > budget |

## Open questions

None that block Task 1. Default: no disk cache for profiler.

## Parallelization

- Tasks 1–2 share `disk_analyzer.py` — serialize.
- Tasks 3–4 share `app_uninstaller.py` — serialize.
- Task 5 (`bba.py`) can follow Task 3 (orphans uses both).
- Task 6 after disk tasks.

## Verification (plan-level)

- Every task has a re-measure step with the same command as the baseline
- Neutral result = revert
- Human approves before implementation
