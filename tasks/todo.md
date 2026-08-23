# Native inventory — task list

Source plan: `tasks/plan.md`

## Phase 1: Foundation

## Task 1: Installed-app inventory via system_profiler JSON

**Description:** Add a small module (or functions in a new `inventory.py`) that loads installed apps from `system_profiler SPApplicationsDataType -json` and returns structured records (name, path, bundle id if present). Cache once per process. Tests inject fixture JSON so CI never calls the real profiler.

**Acceptance criteria:**
- [ ] Public API: `list_installed_apps()` / `installed_app_names()` used by callers
- [ ] Uses `json.loads` only — no regex, no `*.app` glob in the happy path
- [ ] Process-level cache; tests can reset/inject
- [ ] Fallback glob documented and only used if profiler fails

**Verification:**
- [ ] `pytest py/tests/test_inventory.py` (new) passes
- [ ] `ruff check py/src/ py/tests/`

**Dependencies:** None

**Files likely touched:**
- `py/src/maccleaner/inventory.py` (new)
- `py/tests/test_inventory.py` (new)

**Estimated scope:** S

## Task 2: Helper→parent map via attributions.plist

**Description:** Load Apple’s attributions plist with `plistlib` and expose `parent_bundles_for_label(label) -> list[str]` / team-id lookup. Tests use a tiny fixture plist, not the system file.

**Acceptance criteria:**
- [ ] No brand dictionary in production code
- [ ] Missing/unreadable system plist → empty map, no crash
- [ ] Lookup by launchd label and by program path when the plist provides them

**Verification:**
- [ ] `pytest py/tests/test_attributions.py` passes
- [ ] `ruff check`

**Dependencies:** None (can land with Task 1)

**Files likely touched:**
- `py/src/maccleaner/attributions.py` (new)
- `py/tests/test_attributions.py` (new)
- `py/tests/fixtures/attributions.plist` (tiny, generic)

**Estimated scope:** S

### Checkpoint: Foundation
- [ ] All new tests pass
- [ ] Ruff clean
- [ ] Human review: cache + fixture look right

---

## Phase 2: Cheap native replacements

## Task 3: Memory free-bytes via sysctl

**Description:** Replace `_parse_vm_stat` regex with `sysctl -n` integer reads (`hw.pagesize`, `vm.page_free_count`, `vm.page_speculative_count`). Drop `import re` from `memory.py`.

**Acceptance criteria:**
- [ ] No `re` in `memory.py`
- [ ] Free bytes = (free + speculative) * pagesize
- [ ] Existing `mem free` tests updated to mock `sysctl`, not `vm_stat` text

**Verification:**
- [ ] `pytest py/tests/test_memory.py`
- [ ] `ruff check`

**Dependencies:** None

**Files likely touched:**
- `py/src/maccleaner/memory.py`
- `py/tests/test_memory.py`

**Estimated scope:** S

## Task 4: Network mounts via diskutil plist

**Description:** Replace `mount(8)` line splitting in `_network_mount_points` with `diskutil list -plist` + `diskutil info -plist` and `plistlib`.

**Acceptance criteria:**
- [ ] No string-split of `mount` output
- [ ] Network FS types still skipped (nfs, smbfs, afpfs, webdav, autofs, cifs)
- [ ] Existing disk tests still pass (mock diskutil plist)

**Verification:**
- [ ] `pytest py/tests/test_disk_analyzer.py`
- [ ] `ruff check`

**Dependencies:** None

**Files likely touched:**
- `py/src/maccleaner/disk_analyzer.py`
- `py/tests/test_disk_analyzer.py`

**Estimated scope:** S

### Checkpoint: Cheap replacements
- [ ] Memory + disk tests green
- [ ] No `re` in `memory.py`
- [ ] No `mount` scraper in `disk_analyzer.py`

---

## Phase 3: BAA / orphans

## Task 5: Line-state dumpbtm parser (delete regex)

**Description:** Rewrite `_parse_dumpbtm` to walk lines: detect `Records for UID`, item headers `#N:`, and `Key: value` via `partition(":")`. Delete all `re` usage in `bba.py`. Keep `sfltool dumpbtm` as the source.

**Acceptance criteria:**
- [ ] `import re` gone from `bba.py`
- [ ] Existing BBA fixture dump still produces the same 4 items
- [ ] Associated bundle IDs parsed without regex (strip `[]` and split on comma)

**Verification:**
- [ ] `pytest py/tests/test_bba.py`
- [ ] `ruff check`

**Dependencies:** None (parser-only)

**Files likely touched:**
- `py/src/maccleaner/bba.py`
- `py/tests/test_bba.py`

**Estimated scope:** S

## Task 6: Mechanical orphan rule

**Description:** Replace `_is_bba_orphan` / `_is_orphan` brand heuristics with: attributions parent + inventory paths + executable/plist existence. Delete `ORPHAN_BRANDS`.

**Acceptance criteria:**
- [ ] `ORPHAN_BRANDS` deleted
- [ ] Orphan iff no parent bundle exists and (exe missing or plist missing)
- [ ] Installed Hermes/Zoom-class fixtures are not flagged; missing Avast-class fixtures are

**Verification:**
- [ ] `pytest py/tests/test_bba.py py/tests/test_app_uninstaller.py`
- [ ] `ruff check`

**Dependencies:** Task 1, Task 2, Task 5

**Files likely touched:**
- `py/src/maccleaner/bba.py`
- `py/src/maccleaner/app_uninstaller.py`
- `py/tests/test_bba.py`
- `py/tests/test_app_uninstaller.py`

**Estimated scope:** M

## Task 7: Collapse dual orphan engines + CLI

**Description:** `find_orphans()` becomes a thin wrapper over BAA inventory (sfltool). Remove plist-directory walk as the primary path. Keep `app orphans list|purge`; make `app bba` an alias (or remove after README update).

**Acceptance criteria:**
- [ ] One orphan implementation path
- [ ] `cleanmac app orphans list` and `cleanmac app bba list` same results
- [ ] Purge still dry-run by default; one sudo prompt on `--commit`
- [ ] Launch-plist walk only if `sfltool` missing (if we keep fallback)

**Verification:**
- [ ] `pytest py/tests/`
- [ ] Manual: `cleanmac app orphans list` and `cleanmac app bba list`

**Dependencies:** Task 6

**Files likely touched:**
- `py/src/maccleaner/app_uninstaller.py`
- `py/src/maccleaner/cli.py`
- `py/tests/test_app_uninstaller.py`
- `py/tests/test_cli.py`

**Estimated scope:** M

### Checkpoint: Orphans
- [ ] `import re` gone from `bba.py`
- [ ] `ORPHAN_BRANDS` gone
- [ ] Full pytest + ruff green
- [ ] Human review before CLI alias removal

---

## Phase 4: Close-out

## Task 8: README + residual ps cleanup

**Description:** Document native sources. Optional: `ps -o pid=,rss=,comm=` (no header) in `memory.py`. No bash rewrite in this plan.

**Acceptance criteria:**
- [ ] README lists `system_profiler`, `sfltool dumpbtm`, `sysctl`, `diskutil -plist`, attributions plist
- [ ] `app bba` documented as alias if kept
- [ ] Full suite green

**Verification:**
- [ ] `pytest py/tests/`
- [ ] `ruff check py/src/ py/tests/`

**Dependencies:** Task 7

**Files likely touched:**
- `README.md`
- `py/src/maccleaner/memory.py` (optional ps tweak)
- `py/tests/test_memory.py`

**Estimated scope:** S

### Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Ready for review / PR update on `feat/observability`

## Parallelization notes

- After Task 1 lands: Tasks 3, 4, 5 can run in parallel (disjoint files).
- Tasks 2, 6, 7 all touch orphan logic — **serialize**; do not parallel-edit `app_uninstaller.py`.
