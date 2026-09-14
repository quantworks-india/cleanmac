# CleanMac Swift rewrite — task list

Source: `tasks/plan.md`. Vertical slices; each task is independently
verifiable. Python sources cited are the executable spec for the slice.

## Task 0: Xcode project + SPM layout + CI build

**Description:** New `swift/` tree: SPM package with `CleanMacCore`
(library) + `CleanMac` (app) targets, XCTest target, CI job running
`swift build` + `swift test`. No features.
**Acceptance criteria:**
- [ ] `swift build` succeeds on a clean checkout
- [ ] `swift test` runs (even with zero tests) in CI
- [ ] Bundle id reserved (`com.cleanmac.app` or owner choice)
**Verification:**
- [ ] Tests pass: `swift test`
- [ ] Build succeeds: `swift build -c release`
**Dependencies:** None
**Files likely touched:**
- `swift/Package.swift`
- `swift/Sources/CleanMacCore/`
- `swift/Sources/CleanMac/CleanMacApp.swift`
- `.github/workflows/swift.yml`
**Estimated scope:** Medium (3-5 files)


## Task 1: Safety core port

**Description:** Port the safety contract from `py/src/maccleaner/core.py`:
realpath allowlist (`is_safe_path`), commit gate (dry-run default),
JSONL audit writer, single-confirm hook. Everything destructive later
depends on this.
**Acceptance criteria:**
- [ ] Refuses `/`, `/System`, `/Library`, `/Applications` bare,
      `~/.ssh`, `/dev/null` symlink escapes (mirror `test_core.py` cases)
- [ ] Dry-run deletes nothing, audits `would_delete`
- [ ] Audit JSONL schema identical to Python (`ts/run/mode/step/action/path`)
**Verification:**
- [ ] Tests pass: `swift test --filter SafetyTests`
- [ ] Manual check: attempt delete of `/etc/hosts` path → refused, audited
**Dependencies:** Task 0
**Files likely touched:**
- `swift/Sources/CleanMacCore/Safety.swift`
- `swift/Sources/CleanMacCore/Audit.swift`
- `swift/Tests/CleanMacCoreTests/SafetyTests.swift`
**Estimated scope:** Medium (3-5 files)


## Task 6: Junk cleanup engine + screen (FIRST UI SLICE)

**Description:** Port `lib/steps.sh` 8 steps (user/system caches, logs,
trash+snapshots, Homebrew, dev caches, DNS/RAM, periodic) with per-step
progress, skip-vs-fail (rc 2 = skip), dotfile handling, ambient-vs-
reclaimed disk wording. ALSO builds the menu-bar shell (`NSStatusItem`
popover) + window frame every later screen plugs into.
**Acceptance criteria:**
- [ ] Dry-run changes nothing; report matches bash report fields
- [ ] Missing brew → step shows skipped, exit stays 0
- [ ] Live progress shows current unit of work per step
- [ ] Menu-bar icon + popover + empty window shell work (light + dark)
**Verification:**
- [ ] Tests pass: `swift test --filter JunkTests` (sandboxed paths)
- [ ] Manual check: dry-run on host, compare with bash output
**Dependencies:** Task 1
**Files likely touched:**
- `swift/Sources/CleanMacCore/Junk.swift`
- `swift/Sources/CleanMac/MenuBar.swift`
- `swift/Sources/CleanMac/JunkView.swift`
- `swift/Tests/CleanMacCoreTests/JunkTests.swift`
**Estimated scope:** Large (5-8 files — split engine vs shell if needed)


## Task 8: Disk analyzer engine + screen

**Description:** Port `disk_analyzer.py`: iterative walk (network-mount
subtree skip), top/summary/system-data, treemap or bar visualization,
single-line progress.
**Acceptance criteria:**
- [ ] Totals match `du` within 5% on a fixture tree
- [ ] Network mount subtree never descended
- [ ] Zero-size trees render without layout breaks
**Verification:**
- [ ] Tests pass: `swift test --filter DiskTests`
- [ ] Manual check: scan home, compare top-10 with Python
**Dependencies:** Task 1
**Files likely touched:**
- `swift/Sources/CleanMacCore/Disk.swift`
- `swift/Sources/CleanMac/DiskView.swift`
- `swift/Tests/CleanMacCoreTests/DiskTests.swift`
**Estimated scope:** Medium (3-5 files)


## Task 7: Duplicate finder engine + screen

**Description:** Port `duplicates.py`: size-first grouping, streaming
hash (skip unreadable), groups table (Keep/Duplicates/Reclaimable),
merge-folders behind commit gate.
**Acceptance criteria:**
- [ ] Identical groups to Python on a fixture tree
- [ ] Unreadable file skips, never aborts the scan
- [ ] Merge honors dry-run (the Python bug class must not recur)
**Verification:**
- [ ] Tests pass: `swift test --filter DuplicatesTests`
- [ ] Manual check: scan ~/Downloads dry-run
**Dependencies:** Task 1
**Files likely touched:**
- `swift/Sources/CleanMacCore/Duplicates.swift`
- `swift/Sources/CleanMac/DuplicatesView.swift`
- `swift/Tests/CleanMacCoreTests/DuplicatesTests.swift`
**Estimated scope:** Medium (3-5 files)


## Task 9: Memory engine + screen

**Description:** Port `memory.py`: sysctl free bytes, heavy list with
byte units, kill guarded (never self/parent/0-2, confirm with comm).
**Acceptance criteria:**
- [ ] Free bytes equals (free+speculative)×pagesize
- [ ] Kill of own pid refused even if requested
- [ ] Kill behind explicit confirm, never in dry-run/list context
**Verification:**
- [ ] Tests pass: `swift test --filter MemoryTests`
- [ ] Manual check: free + heavy list on host
**Dependencies:** Task 1
**Files likely touched:**
- `swift/Sources/CleanMacCore/Memory.swift`
- `swift/Sources/CleanMac/MemoryView.swift`
- `swift/Tests/CleanMacCoreTests/MemoryTests.swift`
**Estimated scope:** Small (1-2 files)


## Checkpoint: Safe tools

- [ ] Junk/disk/dup/memory all work dry-run with zero destructive paths
- [ ] Human review of menu-bar shell + one screen before proceeding


## Task 2: App inventory

**Description:** Port `py/src/maccleaner/inventory.py`: `system_profiler
SPApplicationsDataType -json` via `Process`, cached, glob fallback.
**Acceptance criteria:**
- [ ] Lists every installed app regardless of owner/location
- [ ] Excludes nothing; system filtering happens at uninstall layer, not here
- [ ] Cache invalidates on rescan request
**Verification:**
- [ ] Tests pass: `swift test --filter InventoryTests` (canned JSON fixture)
- [ ] Manual check: count matches `system_profiler` output
**Dependencies:** Task 0
**Files likely touched:**
- `swift/Sources/CleanMacCore/Inventory.swift`
- `swift/Tests/CleanMacCoreTests/InventoryTests.swift`
**Estimated scope:** Small (1-2 files)


## Task 3: Leftover fingerprint + matrix

**Description:** Port `app_uninstaller.py` discovery: user/system patterns,
launch ownership (exact/prefix/bundle-boundary, NOT substring), brew +
helpers matching (anchored), `_classify_store` table, Y/N/— matrix.
**Acceptance criteria:**
- [ ] Matrix columns identical to Python set (app/mas/pkg/brew/support/
      cache/prefs/container/saved/agents/daemons/helpers/kext/btm)
- [ ] `Foo.app2` exe never attributed to `Foo.app`
- [ ] Substring helper/name matches rejected (port the `*_rejects_substring`
      test cases from `py/tests/`)
**Verification:**
- [ ] Tests pass: `swift test --filter FingerprintTests`
- [ ] Manual check: matrix for Firefox matches Python output
**Dependencies:** Tasks 1, 2
**Files likely touched:**
- `swift/Sources/CleanMacCore/Fingerprint.swift`
- `swift/Sources/CleanMacCore/Matrix.swift`
- `swift/Tests/CleanMacCoreTests/FingerprintTests.swift`
**Estimated scope:** Medium (3-5 files)


## Task 4: Uninstall flow (engine)

**Description:** Port `uninstall.py` + `_run_uninstall`: resolve (with
evidence guard + `system_app_refused` for `/System`/`com.apple.*`),
plan model, single confirm gate, bundle delete with sudo path,
quarantine for launch plists, honest failure (`uninstall_failed`, rc).
**Acceptance criteria:**
- [ ] Unknown app with zero leftovers → error, no prompt
- [ ] System app → `system_app_refused`, nothing touched
- [ ] Failed bundle delete → failure result, never false "deleted"
- [ ] Audit events named exactly as Python (`uninstall_complete`, …)
**Verification:**
- [ ] Tests pass: `swift test --filter UninstallTests` (sandbox home)
- [ ] Manual check: dry-run uninstall of a test app, inspect audit log
**Dependencies:** Tasks 1, 3
**Files likely touched:**
- `swift/Sources/CleanMacCore/Uninstall.swift`
- `swift/Sources/CleanMacCore/Quarantine.swift`
- `swift/Tests/CleanMacCoreTests/UninstallTests.swift`
**Estimated scope:** Medium (3-5 files)


## Task 5: Uninstall window (plugs into Phase 1 shell)

**Description:** SwiftUI window content (Task 6 built the menu-bar shell):
searchable app list (leftover flags, `--all` equivalent toggle), plan
table (Kind/Path, ≤80-col-equivalent layout), single confirm dialog,
progress + result states. Esc closes; light AND dark mode contrast
(marker + bold selection identity, never bare reverse video).
**Acceptance criteria:**
- [ ] Picker → plan → one confirm → result, end to end
- [ ] After one uninstall, control returns to the list (session loop)
- [ ] Empty/filter-no-match states explain + offer next action
- [ ] Light mode: selected row readable (assert in UI test / preview)
**Verification:**
- [ ] Tests pass: `swift test --filter UninstallUITests`
- [ ] Build succeeds: Xcode archive
- [ ] Manual check: human review of picker + plan screens (both modes)
**Dependencies:** Task 4 (flow) + Task 6 (shell)
**Files likely touched:**
- `swift/Sources/CleanMac/UninstallView.swift`
- `swift/Sources/CleanMac/AppListView.swift`
**Estimated scope:** Large (5-8 files — split picker vs plan if needed)


## Task 10: Hidden-files toggle + startup/orphan screens

**Description:** Port `hidden_files.py` (commit-gated toggle),
`spotlight.py`/`bba.py`/`attributions.py` orphan pipeline (exact/dot-
anchored matching only), startup list/disable via quarantine.
**Acceptance criteria:**
- [ ] Toggle is a no-op in dry-run
- [ ] Orphan = missing exe AND no installed-name match (no substrings)
- [ ] Disable quarantines (reversible), never hard-deletes
**Verification:**
- [ ] Tests pass: `swift test --filter StartupTests`
- [ ] Manual check: toggle + orphans list on host
**Dependencies:** Tasks 1, 2
**Files likely touched:**
- `swift/Sources/CleanMacCore/Startup.swift`
- `swift/Sources/CleanMac/StartupView.swift`
- `swift/Tests/CleanMacCoreTests/StartupTests.swift`
**Estimated scope:** Medium (3-5 files)


## Checkpoint: Flagship

- [ ] Uninstall one real app end-to-end in a sandbox home
- [ ] Human review of picker + plan screens before proceeding


## Task 11: Privileged helper (SMAppService)

**Description:** System-scope deletes (helpers, daemons, system caches)
move from sudo-prompts to an `SMAppService` privileged helper.
**Acceptance criteria:**
- [ ] Helper installs with user approval, uninstalls cleanly
- [ ] Without helper: per-action auth prompt, graceful skip on denial
- [ ] No password ever stored; auth per Apple guidelines
**Verification:**
- [ ] Tests pass: helper protocol tests with mock XPC layer
- [ ] Manual check: daemon quarantine on host, helper absent case
**Dependencies:** Tasks 4, 6, 10
**Files likely touched:**
- `swift/Sources/CleanMacHelper/main.swift`
- `swift/Sources/CleanMacCore/Privileged.swift`
- `swift/launchd/com.cleanmac.helper.plist`
**Estimated scope:** Large (5-8 files — split helper vs client if needed)


## Task 12: Signing, notarization, DMG, onboarding

**Description:** Developer ID signing, notarization stapling, DMG build,
first-run onboarding (Full Disk Access guidance, helper install,
dry-run-default explanation).
**Acceptance criteria:**
- [ ] Notarized DMG installs + launches on a clean Mac (2 machines)
- [ ] First run explains each permission before the OS prompt
- [ ] No destructive action reachable before onboarding completes
**Verification:**
- [ ] Build succeeds: full archive + notarize + staple
- [ ] Manual check: clean-Mac install walkthrough
**Dependencies:** All tasks
**Files likely touched:**
- `swift/Sources/CleanMac/OnboardingView.swift`
- `scripts/package-dmg.sh`
- `swift/CleanMac.entitlements`
**Estimated scope:** Medium (3-5 files)


## Checkpoint: Complete

- [ ] All acceptance criteria met
- [ ] Ready for review
