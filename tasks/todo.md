# CleanMac — build tasks (reconciled order)

Standing commitments (from tasks/plan.md — every task below must satisfy
them): FREE forever, MIT, zero telemetry; trust wedge (no placebos, no
theatre, no inflated counts). Safety rails precede deleters, always.

## Phase A — Foundations

## Task 1: Free-forever / MIT / telemetry policy
**Description:** Encode the non-negotiable policy as code + docs: no paid
tiers, no upsell surface, no network callbacks except explicit carve-outs.
**Acceptance criteria:**
- [ ] `Policy.swift` exposes `isFreeForever == true`, `allowsTelemetry == false`
- [ ] Carve-out allowlist contains exactly: user-initiated update checks
      (Sparkle on-demand only, never background), `mas`/`brew` subprocess
      calls the user explicitly invoked
- [ ] Any network call outside the carve-out fails `PolicyTests`
**Verification:**
- [ ] `swift test --filter PolicyTests`; `swift build`
- [ ] Manual: `rg -i "http|URLSession|telemetry|analytics" Sources/` shows only carve-out call sites
**Dependencies:** None
**Files likely touched:**
- `Sources/CleanMacCore/Policy.swift`
- `Tests/CleanMacCoreTests/PolicyTests.swift`
**Estimated scope:** S

## Task 2: Non-goals + assumptions (exactly six)
**Description:** Write the exclusion list the engine enforces: Photos bodies,
Mail bodies, iCloud bodies, boot-volume operations, deleting running apps,
MDM-managed machines. Plus stated assumptions: single-user, APFS,
Spotlight-on.
**Acceptance criteria:**
- [ ] `Policy.nonGoals` contains exactly these six strings (Photos, Mail,
      iCloud counted separately — count is six, reconciled)
- [ ] `Policy.assumptions` lists single-user, APFS, Spotlight-on
- [ ] Test asserts the exact list contents (list-level test, not behavior)
**Verification:**
- [ ] `swift test --filter PolicyTests`; `swift build`
**Dependencies:** Task 1
**Files likely touched:**
- `Sources/CleanMacCore/Policy.swift`
- `Tests/CleanMacCoreTests/PolicyTests.swift`
**Estimated scope:** XS

## Task 3: Sensitivity tiers as data
**Description:** Strict/Enhanced/Deep defined as a thresholds table
(evidence required per level + false-positive budget), never as "scan
depth" marketing. Future flagging sites are out of scope here.
**Acceptance criteria:**
- [ ] `Sensitivity` enum with per-tier `requiredEvidence` + `maxFalsePositiveRate`
- [ ] Test asserts table contents for all three tiers
- [ ] No tier is defined by depth, coverage %, or found-count
**Verification:**
- [ ] `swift test --filter SensitivityTests`; `swift build`
**Dependencies:** Tasks 1, 2
**Files likely touched:**
- `Sources/CleanMacCore/Sensitivity.swift`
- `Tests/CleanMacCoreTests/SensitivityTests.swift`
**Estimated scope:** S

## Task 4: Ignore + protected lists
**Description:** User-editable ignore lists and the built-in protected set
(system paths, `/System`, `com.apple.*`). System roots are refused even
when explicitly requested; `/Applications` user targets are allowed only
via explicit per-target confirm (see Task 13).
**Acceptance criteria:**
- [ ] `ProtectedPaths.isRefused(_:)` covers system roots + `com.apple.*`
- [ ] User-requested `/Applications/<Name>.app` is NOT refused (overbroad
      block would kill the flagship)
- [ ] Ignore list persists across launches (JSON in app support dir)
**Verification:**
- [ ] `swift test --filter ProtectedPathsTests`; `swift build`
**Dependencies:** Tasks 1, 2
**Files likely touched:**
- `Sources/CleanMacCore/ProtectedPaths.swift`
- `Sources/CleanMacCore/IgnoreList.swift`
- `Tests/CleanMacCoreTests/ProtectedPathsTests.swift`
**Estimated scope:** S

## Task 5: Per-path review contract (gate logic)
**Description:** The review gate as testable view-model logic: every
destructive screen shows every path before the gate; exactly one confirm
control commits; per-item toggles select scope but never themselves delete.
Rendering (light/dark, monochrome) is a manual checklist, not a unit test.
**Acceptance criteria:**
- [ ] `ReviewGate` view-model: paths listed → one `confirm()` → committed
      state; toggles change scope, never trigger deletion
- [ ] Zero-evidence case returns "nothing found + what was searched",
      and no gate control is presented (documented exception to "show paths")
- [ ] Rendering checklist exists (light, dark, monochrome, 80-col table)
**Verification:**
- [ ] `swift test --filter ReviewGateTests`; `swift build`
- [ ] Manual: rendering checklist signed off in the task PR
**Dependencies:** Tasks 3, 4
**Files likely touched:**
- `Sources/CleanMacCore/ReviewGate.swift`
- `Tests/CleanMacCoreTests/ReviewGateTests.swift`
**Estimated scope:** S

## Task 6: Trash primitive + pending-vs-freed accounting
**Description:** `FileManager.trashItem`-based deletion (rollback handle via
`resultingItemURL`) plus honest accounting: moved-to-trash counts as
*pending*, freed only on explicit empty. Same-volume moves free 0 bytes —
the UI must say so.
**Acceptance criteria:**
- [ ] `trashItem` used; resulting URL recorded per item
- [ ] `pendingBytes` vs `freedBytes` reported separately, never summed
      into a "reclaimed" headline
- [ ] Explicit empty-trash is a separate user action, never implicit
**Verification:**
- [ ] `swift test --filter TrashTests` (fixture dir, real trash on temp volume OK)
- [ ] `swift build`
**Dependencies:** Tasks 4, 5
**Files likely touched:**
- `Sources/CleanMacCore/Trash.swift`
- `Sources/CleanMacCore/Accounting.swift`
- `Tests/CleanMacCoreTests/TrashTests.swift`
**Estimated scope:** M

## Task 7: Rollback / restore
**Description:** Restore trashed items from recorded URLs; partial-failure
semantics defined (per-item success/failure, resumable).
**Acceptance criteria:**
- [ ] Restore returns each item or reports per-item failure
- [ ] Restoring a rebuilt-over path never overwrites silently (suffix + warn)
**Verification:**
- [ ] `swift test --filter RollbackTests`; `swift build`
**Dependencies:** Task 6
**Files likely touched:**
- `Sources/CleanMacCore/Rollback.swift`
- `Tests/CleanMacCoreTests/RollbackTests.swift`
**Estimated scope:** S

## Checkpoint: Safety rails
- [ ] `swift test --filter 'PolicyTests|ProtectedPathsTests|ReviewGateTests|TrashTests|RollbackTests|SensitivityTests'` green
- [ ] `swift build` clean
- [ ] Human review: rails hold before any deleter is built — nothing below starts until signed

## Phase B — Scanner infra

## Task 8: APFS-correct disk analyzer engine
**Description:** Iterative walk with clone/hardlink/sparse-aware accounting
(never over-counts), symlink-loop and firmlink safe, TCC-denied paths
reported as unknown (never zero-filled silently).
**Acceptance criteria:**
- [ ] Fixture tree with hardlinks + APFS clones: reported total within 5%
      of `statfs` physical, never above it
- [ ] Symlink loop terminates; denied paths marked unknown with count
- [ ] Top-N by physical size
**Verification:**
- [ ] `swift test --filter DiskAnalyzerTests` (fixture oracle: knownsizes tree)
- [ ] `swift build`; manual: compare top-10 against Finder on host
**Dependencies:** Checkpoint Safety rails
**Files likely touched:**
- `Sources/CleanMacCore/DiskAnalyzer.swift`
- `Tests/CleanMacCoreTests/DiskAnalyzerTests.swift`
**Estimated scope:** M

## Task 9: Full Disk Access onboarding flow
**Description:** Pre-explain each permission, deep-link to System
Settings > Privacy & Security > Full Disk Access, re-probe access on
return, and run degraded (partial scan + visible disclaimer) on denial.
There is no FDA prompt API — never claim otherwise.
**Acceptance criteria:**
- [ ] Denied state shows exactly which locations are unscanned
- [ ] Re-probe after Settings return flips state without relaunch
- [ ] Degraded scans carry a visible "partial" banner (no silent gaps)
**Verification:**
- [ ] `swift test --filter FDAOnboardingTests` (mocked access states)
- [ ] `swift build`; manual: deny/allow round-trip on host
**Dependencies:** Task 8
**Files likely touched:**
- `Sources/CleanMac/OnboardingView.swift`
- `Sources/CleanMacCore/FDAAccess.swift`
- `Tests/CleanMacCoreTests/FDAOnboardingTests.swift`
**Estimated scope:** M

## Task 10: Purgeable space handling
**Description:** Report purgeable vs truly-free separately using
`statfs`/`URLResourceValues(volumeAvailableCapacityForImportantUsageKey)`;
offer only OS-blessed release (no raw `tmutil` parsing as blessed API —
UNVERIFIED, treat `tmutil` output as untrusted text).
**Acceptance criteria:**
- [ ] Free / purgeable / unavailable reported as three distinct numbers
- [ ] Release path uses only documented APIs; `tmutil` (if used) is
      best-effort with parse-failure fallback, never trusted
- [ ] Never deletes snapshots silently; thinning is explicit + confirmed
**Verification:**
- [ ] `swift test --filter PurgeableTests`; `swift build`
**Dependencies:** Task 8
**Files likely touched:**
- `Sources/CleanMacCore/Purgeable.swift`
- `Tests/CleanMacCoreTests/PurgeableTests.swift`
**Estimated scope:** S

## Task 11: Snapshot awareness (read-only)
**Description:** Detect APFS/Time Machine local snapshots occupying space;
report only. Deletion stays behind the Task 10 confirm path.
**Acceptance criteria:**
- [ ] Snapshots listed with size + age; never auto-selected
- [ ] Deleting a snapshot requires the same gate as any delete (Task 5)
**Verification:**
- [ ] `swift test --filter SnapshotTests`; `swift build`
**Dependencies:** Task 10
**Files likely touched:**
- `Sources/CleanMacCore/Snapshots.swift`
- `Tests/CleanMacCoreTests/SnapshotTests.swift`
**Estimated scope:** S

## Checkpoint: Scanner infra
- [ ] `swift test --filter 'DiskAnalyzerTests|FDAOnboardingTests|PurgeableTests|SnapshotTests'` green
- [ ] `swift build` clean
- [ ] Human review: numbers are honest (no over-count anywhere) before flagship

## Phase C — Flagship (uninstall)

## Task 12: Menu-bar shell + app frame
**Description:** `MenuBarExtra` + `.window` popover style (decided over
`NSStatusItem`; SwiftUI-native per project rule) with template icon,
plus the `NavigationSplitView` app frame all screens plug into. Esc
behavior verified by manual test (no official Esc-dismissal contract
exists — UNVERIFIED at doc level, so test it on-host).
**Acceptance criteria:**
- [ ] Template icon adapts light/dark (manual checklist)
- [ ] Popover Esc-dismiss verified manually on host, recorded in PR
- [ ] Frame exposes a screen-registration point used by later tasks
**Verification:**
- [ ] `swift test --filter ShellTests` (view-model: registration/routing only)
- [ ] `swift build`; manual: light/dark + Esc checklist
**Dependencies:** Checkpoint Safety rails
**Files likely touched:**
- `Sources/CleanMac/MenuBar.swift`
- `Sources/CleanMac/AppFrame.swift`
- `Tests/CleanMacCoreTests/ShellTests.swift`
**Estimated scope:** M

## Task 13: Uninstaller with evidence thresholds
**Description:** Fingerprint engine (`Fingerprint.swift`, in scope here):
bundle-id/name/team-id matching with evidence levels from Task 3;
long-tail exotic installers are explicit non-goals. Single gate per
Task 5; `/Applications` user targets allowed via explicit confirm.
**Acceptance criteria:**
- [ ] Zero-evidence app → error naming what was searched, no gate shown
- [ ] `Foo.app2` never attributed to `Foo.app` (separator-boundary test)
- [ ] Substring-only matches (helper/name/orphan) rejected by test
- [ ] Depends on Tasks 4 (protected), 5 (gate), 8 (sizing ground truth)
**Verification:**
- [ ] `swift test --filter UninstallTests` (sandbox home fixtures)
- [ ] `swift build`; manual: dry-run uninstall of a test app
**Dependencies:** Tasks 4, 5, 8, 12
**Files likely touched:**
- `Sources/CleanMacCore/Fingerprint.swift`
- `Sources/CleanMacCore/Uninstall.swift`
- `Sources/CleanMac/UninstallView.swift`
- `Tests/CleanMacCoreTests/UninstallTests.swift`
**Estimated scope:** M (split view/engine further if it grows)

## Task 14: Orphan sweep
**Description:** Leftovers of already-deleted apps, same evidence engine;
shared folders (Electron/Sparkle/fonts/containers) never auto-flagged.
Owns `OrphansView.swift` (Task 15 owns `StartupView.swift` — no shared UI file).
**Acceptance criteria:**
- [ ] Shared-location files require two independent evidence hits
- [ ] Orphan list shows evidence per row (why flagged)
**Verification:**
- [ ] `swift test --filter OrphanTests`; `swift build`
**Dependencies:** Task 13
**Files likely touched:**
- `Sources/CleanMacCore/Orphans.swift`
- `Sources/CleanMac/OrphansView.swift`
- `Tests/CleanMacCoreTests/OrphanTests.swift`
**Estimated scope:** S

## Task 15: Startup / login manager
**Description:** `SMAppService` agent/daemon/loginItem management with
`.requiresApproval` handling + `openSystemSettingsLoginItems()`. Never
write plists directly. Owns `StartupView.swift`.
**Acceptance criteria:**
- [ ] Disable is reversible (quarantine, never hard delete)
- [ ] Approval-denied state explains + deep-links to Settings
**Verification:**
- [ ] `swift test --filter StartupTests` (mocked service states)
- [ ] `swift build`; manual: disable/enable round-trip
**Dependencies:** Task 14
**Files likely touched:**
- `Sources/CleanMacCore/Startup.swift`
- `Sources/CleanMac/StartupView.swift`
- `Tests/CleanMacCoreTests/StartupTests.swift`
**Estimated scope:** M

## Task 16: Clean Install capture
**Description:** Snapshot-before/after diff of an install footprint;
reports confidence per file; never auto-deletes from a diff; reboot,
daemon, helper, and SIP paths called out, not silently missed.
**Acceptance criteria:**
- [ ] Diff lists added files with per-file confidence
- [ ] Reboot-required and SIP-covered paths flagged unknown, not clean
- [ ] No delete path consumes diff output without a gate
**Verification:**
- [ ] `swift test --filter InstallCaptureTests` (synthetic footprint fixtures)
- [ ] `swift build`
**Dependencies:** Task 13
**Files likely touched:**
- `Sources/CleanMacCore/InstallCapture.swift`
- `Tests/CleanMacCoreTests/InstallCaptureTests.swift`
**Estimated scope:** M

## Checkpoint: Flagship
- [ ] `swift test --filter 'UninstallTests|OrphanTests|StartupTests|InstallCaptureTests|ShellTests'` green
- [ ] `swift build` clean
- [ ] Uninstall one real app end-to-end in a sandbox home; human review of picker + plan screens

## Phase D — Upkeep

## Task 17: Dev caches with guards
**Description:** Versioned detector table (brew/npm/pip/cargo/go/docker/
xcode/jetbrains/vscode + running-process guard + project-aware guard);
simulators and toolchains require explicit opt-in. Includes the
process-listing primitive (no prior task builds it — in scope here).
**Acceptance criteria:**
- [ ] Detector table is data (add tool = add row + test, no logic change)
- [ ] Running-process tool skipped with reason, never killed
- [ ] In-use simulator/toolchain never auto-selected
**Verification:**
- [ ] `swift test --filter DevCacheTests`; `swift build`
**Dependencies:** Checkpoint Flagship; Task 6 (gate), Task 8 (sizing)
**Files likely touched:**
- `Sources/CleanMacCore/DevCaches.swift`
- `Sources/CleanMac/DevCacheView.swift`
- `Tests/CleanMacCoreTests/DevCacheTests.swift`
**Estimated scope:** M

## Task 18: Project artifact purge
**Description:** `node_modules`/`.venv`/`target`/`Pods`/`DerivedData` etc.
with project-root detection; `.venv`/conda and non-reproducible envs are
NEVER preselected; metered-network cost noted where re-download is large.
**Acceptance criteria:**
- [ ] Non-reproducible envs excluded from preselect by test
- [ ] Project root shown per group (user knows what each artifact belongs to)
**Verification:**
- [ ] `swift test --filter ProjectPurgeTests` (fixture monorepo)
- [ ] `swift build`
**Dependencies:** Task 17
**Files likely touched:**
- `Sources/CleanMacCore/ProjectPurge.swift`
- `Tests/CleanMacCoreTests/ProjectPurgeTests.swift`
**Estimated scope:** S

## Task 19: Large & old files (never preselect)
**Description:** Size/age browser; age ≠ unwanted, so selection is always
manual. iCloud-evicted, Time Machine, other-user, and external-volume
files called out, never silently counted.
**Acceptance criteria:**
- [ ] Nothing preselected, ever (test asserts empty selection on fresh scan)
- [ ] Evicted/backup/foreign files labeled, excluded from totals
**Verification:**
- [ ] `swift test --filter LargeOldTests`; `swift build`
**Dependencies:** Task 8
**Files likely touched:**
- `Sources/CleanMacCore/LargeOld.swift`
- `Tests/CleanMacCoreTests/LargeOldTests.swift`
**Estimated scope:** S

## Task 20: Exact-hash duplicates
**Description:** Size → partial-hash → full-hash pipeline against a
fixture-tree oracle (defined here: `Tests/Fixtures/DupTree/` with known
hashes). Perceptual similar-images explicitly excluded (see Phase E notes).
**Acceptance criteria:**
- [ ] Identical groups to the fixture oracle, byte-exact
- [ ] Hardlink/APFS-clone pairs reported once, never double-counted
**Verification:**
- [ ] `swift test --filter DuplicatesTests`; `swift build`
**Dependencies:** Task 8
**Files likely touched:**
- `Sources/CleanMacCore/Duplicates.swift`
- `Tests/CleanMacCoreTests/DuplicatesTests.swift`
- `Tests/Fixtures/DupTree/`
**Estimated scope:** M

## Task 21: Updater (brew/Sparkle only)
**Description:** `brew upgrade` orchestration + Sparkle appcast checks for
installed apps. No MAS update API is used (none exists). Major-version
bumps require explicit per-app confirm; never auto-update another
vendor's app. Sparkle is user-initiated only (Task 1 carve-out).
**Acceptance criteria:**
- [ ] Dry-run lists exactly what would change per app
- [ ] Major bumps gated individually, minors batchable
- [ ] No MAS code paths exist — verified by grep audit in verification
**Verification:**
- [ ] `swift test --filter UpdaterTests`; `swift build`
- [ ] Manual: `rg -i "mas\.|itunes|appstoreapi" Sources/` returns nothing
**Dependencies:** Task 13 (app identity reuse only — updater does not need uninstaller logic)
**Files likely touched:**
- `Sources/CleanMacCore/Updater.swift`
- `Tests/CleanMacCoreTests/UpdaterTests.swift`
**Estimated scope:** M

## Task 22: Maintenance, split in two files
**Description:** (a) Space ops: purgeable release + snapshot thinning behind
Task 5 gates, using Task 10/11 primitives. (b) Health ops: DNS flush,
spotlight reindex, periodic scripts — labeled health, zero space claims,
each with reversibility + privilege needs documented.
**Acceptance criteria:**
- [ ] No health op reports bytes; no space op reports health
- [ ] Privilege escalation path documented per op (auth prompt, never silent)
**Verification:**
- [ ] `swift test --filter MaintenanceTests`; `swift build`
**Dependencies:** Tasks 10, 11 (space ops); Task 6 (gates)
**Files likely touched:**
- `Sources/CleanMacCore/MaintenanceSpace.swift`
- `Sources/CleanMacCore/MaintenanceHealth.swift`
- `Tests/CleanMacCoreTests/MaintenanceTests.swift`
**Estimated scope:** M

## Task 23: Installers sweep (.dmg/.pkg only)
**Description:** Stale installer files by age + download source. PKG
*receipts* DB is never read or written (would sabotage future uninstalls).
**Acceptance criteria:**
- [ ] Only `.dmg`/`.pkg`/`.xip` under user download dirs considered
- [ ] Zero code paths touch receipts — verified by grep audit in verification
**Verification:**
- [ ] `swift test --filter InstallersTests`; `swift build`
- [ ] Manual: `rg -i "receipts|/private/var/db" Sources/` returns nothing
**Dependencies:** Task 19 (browser reuse)
**Files likely touched:**
- `Sources/CleanMacCore/Installers.swift`
- `Tests/CleanMacCoreTests/InstallersTests.swift`
**Estimated scope:** S

## Task 24: Translation pruning (no lipo)
**Description:** Unused `.lproj` pruning with per-app safelist. Binary
thinning (`lipo`) is forbidden: breaks signatures, forces re-downloads.
**Acceptance criteria:**
- [ ] Signed apps re-verify after prune in test (or prune refused for them)
- [ ] No binary-thinning code exists — verified by grep audit in verification
**Verification:**
- [ ] `swift test --filter TranslationsTests`; `swift build`
- [ ] Manual: `rg -i "lipo|thin.*binary|architectures" Sources/` returns nothing
**Dependencies:** Task 13 (app identity)
**Files likely touched:**
- `Sources/CleanMacCore/Translations.swift`
- `Tests/CleanMacCoreTests/TranslationsTests.swift`
**Estimated scope:** S

## Checkpoint: System upkeep
- [ ] `swift test --filter 'DevCacheTests|ProjectPurgeTests|LargeOldTests|DuplicatesTests|UpdaterTests|MaintenanceTests|InstallersTests|TranslationsTests'` green
- [ ] `swift build` clean
- [ ] Grep audits (receipts, lipo, MAS) all empty — paste outputs in PR
- [ ] Human review before experimental phase

## Phase E — Experimental (gated, kill criteria mandatory)

## Task 25: AI-tool artifact cleanup (caches only)
**Description:** Versioned detector table for Claude/Cursor/Ollama/Copilot
caches. Multi-GB model downloads are NEVER touched without per-model
explicit opt-in. Detector layouts versioned (paths churn monthly).
**Acceptance criteria:**
- [ ] Default scope is caches + logs only (test asserts model dirs excluded)
- [ ] Stale detector version degrades to "unknown", never to aggressive
**Verification:**
- [ ] `swift test --filter AICacheTests`; `swift build`
**Dependencies:** Task 17 (detector-table pattern)
**Files likely touched:**
- `Sources/CleanMacCore/AICaches.swift`
- `Tests/CleanMacCoreTests/AICacheTests.swift`
**Estimated scope:** S

## Task 26: On-device file explanations (describe-only)
**Description:** Explain unknown files using on-device inference only,
gated on macOS 26+ availability (`FoundationModels`), graceful fallback
below. Output schema is fixed: kind/owner-app/age only. Kill criteria:
unmeasurable hallucination rate or any safety assertion in output.
**Acceptance criteria:**
- [ ] Output validates against fixed schema (no free-text safety claims possible)
- [ ] Adversarial fixture (random hash names, signed bundles) never yields
      a safety assertion
- [ ] Below macOS 26: feature absent with explanation, never broken
**Verification:**
- [ ] `swift test --filter ExplainTests`; `swift build`
- [ ] Manual: run on macOS 26+ host; residual risk explicitly noted in PR
**Dependencies:** Task 8 (file/scanner ground truth)
**Files likely touched:**
- `Sources/CleanMacCore/Explain.swift`
- `Tests/CleanMacCoreTests/ExplainTests.swift`
**Estimated scope:** M

## Checkpoint: Experimental
- [ ] `swift test --filter 'AICacheTests|ExplainTests'` green
- [ ] `swift build` clean
- [ ] Kill criteria evaluated honestly per feature — cut what fails

## Phase F — Deferred (v2 backlog, no code)

## Task 27: v2 backlog note (no UI surfaces, no Policy.swift touches)
**Description:** Record-only: trash-watch daemon (requires `docs/trash-watch-design.md`
written first — daemon lifecycle/sleep/TCC/battery; root needs
`SMAppService` daemon with user approval, never XPC elevation), mail
cleanup (FDA/privacy/version-churn bar), cloud cleanup (sync-safety bar:
evict-vs-delete must be unconfusable), local AI model manager. No code,
no surfaces, no changes to existing files beyond this note.
**Acceptance criteria:**
- [ ] Backlog lists all four with their acceptance bars
- [ ] `docs/trash-watch-design.md` exists before any v2 daemon work
- [ ] Verification re-runs existing suites only (nothing new to test)
**Verification:**
- [ ] `swift test` (full suite green); `swift build`
**Dependencies:** None (record only)
**Files likely touched:**
- `docs/trash-watch-design.md` (new, v2 prerequisite)
**Estimated scope:** XS

## Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Grep audits empty, suites green, build clean
- [ ] Ready for human review
