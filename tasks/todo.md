# CLI performance — task list

Source plan: `tasks/plan.md`  
Baseline: see plan table (disk summary 35.5s, startup list 2.5s, app list 0.84s).

## Phase 1: Disk

## Task 1: disk summary is depth-1

**Description:** `disk summary` currently calls `scan(home)`, which walks ~936k paths (~35s) to print immediate children. Size only the first level (native `du -sk` per child, or `du -d 1`). Do not change `disk top` in this task.

**Acceptance criteria:**
- [ ] `cleanmac disk summary` does not walk the whole tree
- [ ] Same children still appear (Library, .colima, …); sizes within noise of current
- [ ] Existing disk tests updated to the depth-1 contract

**Verification:**
- [ ] Re-measure: `cleanmac disk summary` vs 35.5s baseline (target < 3s)
- [ ] `pytest py/tests/test_disk_analyzer.py`
- [ ] `ruff check`

**Dependencies:** None

**Files likely touched:**
- `py/src/maccleaner/disk_analyzer.py`
- `py/tests/test_disk_analyzer.py`

**Estimated scope:** S

## Task 2: disk top/scan without a 936k-path map

**Description:** Full-tree size is still needed for `disk top` / `disk scan`, but `_walk` stores every file path then sorts. Keep dir totals only, or one native `du` invocation. Show progress only if still > 5s.

**Acceptance criteria:**
- [ ] Peak structure is dirs (or `du` output), not one dict entry per file
- [ ] Top-N ranking still correct on the existing fixture tree
- [ ] Home `disk top` re-measured; keep only if clearly faster than ~35s

**Verification:**
- [ ] Re-measure `cleanmac disk top` (target < 15s)
- [ ] `pytest py/tests/test_disk_analyzer.py`
- [ ] If within noise: revert

**Dependencies:** Task 1 (same file)

**Files likely touched:**
- `py/src/maccleaner/disk_analyzer.py`
- `py/tests/test_disk_analyzer.py`

**Estimated scope:** M

### Checkpoint: Disk
- [ ] Summary < 3s
- [ ] Top improved or Task 2 reverted
- [ ] Tests + ruff green

---

## Phase 2: N+1 Apple CLI

## Task 3: startup list without N+1 launchctl / profiler

**Description:** `app startup list` loads `system_profiler` for orphan flags and runs `launchctl print` per user plist (no timeout). List view does not need profiler. Live state: one `launchctl print gui/$UID` (or omit state) with a timeout.

**Acceptance criteria:**
- [ ] Default `startup list` does not call `system_profiler`
- [ ] No `launchctl print` per plist
- [ ] `--orphans-only` still uses inventory
- [ ] launchctl calls have a timeout

**Verification:**
- [ ] Re-measure `cleanmac app startup list` vs 2.5s (target < 0.8s)
- [ ] `pytest py/tests/test_app_uninstaller.py`
- [ ] `ruff check`

**Dependencies:** None (disjoint from disk after Phase 1)

**Files likely touched:**
- `py/src/maccleaner/app_uninstaller.py`
- `py/tests/test_app_uninstaller.py`

**Estimated scope:** S

## Task 4: app list / picker without N× du

**Description:** `list_apps()` runs `du -sk` for every `.app` before anything renders (0.75s for 21 apps; worse with more apps). Picker should list names first. `app list` can size after, or skip size unless asked.

**Acceptance criteria:**
- [ ] Interactive picker does not `du` every app before first paint
- [ ] `app list` still shows a size column (compute after listing, or cheaper metadata)
- [ ] `_find_app` does not need sizes

**Verification:**
- [ ] Re-measure `cleanmac app list` vs 0.84s (target < 0.4s)
- [ ] Picker unit tests still pass
- [ ] `ruff check`

**Dependencies:** Task 3 (same file) — serialize

**Files likely touched:**
- `py/src/maccleaner/app_uninstaller.py`
- `py/tests/test_app_uninstaller.py`
- `py/tests/test_picker.py` (only if picker API changes)

**Estimated scope:** S

## Task 5: sfltool cache + faster fail

**Description:** Healthy `dumpbtm` is fine; hung BTM costs 30s per orphans/bba call. Cache dump in-process. Drop timeout toward 8s. Fail closed (empty list + error), no hang.

**Acceptance criteria:**
- [ ] Second `find_bba_orphans()` in one process does not re-run `sfltool`
- [ ] Timeout ≤ 8s; tests cover timeout + cache
- [ ] Human error still names BTM / sfltool

**Verification:**
- [ ] `pytest py/tests/test_bba.py`
- [ ] Manual: `cleanmac app orphans list` fails in ≤ 8s while BTM is wedged
- [ ] `ruff check`

**Dependencies:** None (can follow Task 3)

**Files likely touched:**
- `py/src/maccleaner/bba.py`
- `py/tests/test_bba.py`

**Estimated scope:** S

### Checkpoint: Interactive
- [ ] Startup list < 0.8s
- [ ] App list < 0.4s
- [ ] Orphans fail-fast ≤ 8s if BTM hung
- [ ] Tests + ruff

---

## Phase 3: Guard

## Task 6: system-data + ledger + regression hook

**Description:** `disk system-data` is 7.4s of sequential `du` on overlapping Library trees. Size only the listed roots (already) but avoid redundant walks; one `du -sk` list if possible. Add `tasks/perf-ledger.md` with this baseline and each attempt. Add one test that `disk summary` uses the depth-1 path (so we cannot silently revert to `scan(home)`).

**Acceptance criteria:**
- [ ] `disk system-data` re-measured; keep only if < 4s or clearly better than 7.4s
- [ ] `tasks/perf-ledger.md` exists with baseline + Task 1–5 results
- [ ] A test fails if summary calls full `scan()` again

**Verification:**
- [ ] Re-measure `cleanmac disk system-data`
- [ ] Full `pytest py/tests/`
- [ ] `ruff check py/src/ py/tests/`

**Dependencies:** Tasks 1–2

**Files likely touched:**
- `py/src/maccleaner/disk_analyzer.py`
- `py/tests/test_disk_analyzer.py`
- `tasks/perf-ledger.md`

**Estimated scope:** S

### Checkpoint: Complete
- [ ] Budgets met or leftover gaps written in the ledger
- [ ] Ready for review on `feat/observability`

## Parallelization notes

- After Task 1: Task 5 can run in parallel with Task 2 if nobody else edits `bba.py`.
- Do not parallel-edit `disk_analyzer.py` or `app_uninstaller.py`.
