# Implementation Plan: CleanMac native Swift app (reconciled order)

## Overview

Native macOS Swift app: menu-bar shell + full window, built from safety rails
outward. Task list lives in `tasks/todo.md` (Tasks 1–27); this file holds
phases, checkpoints, non-goals, and decisions. TDD + thin slices on every
task: failing test first (`swift test --filter`), verify + review per slice.
`Sources/` + `Tests/` + `Package.swift` are the current tree; legacy `py/` +
`bin/` are archived (done — see resolved questions).

## Standing commitments

- **Free forever, MIT, zero telemetry.** No analytics SDKs, no accounts, no
  upsell. The only network carve-outs: user-initiated update checks (Sparkle
  on-demand, never background) and subprocess calls the user explicitly
  invoked (`mas`, `brew`). Task 1 enforces this in code.
- **Funding honesty:** no revenue; maintenance is donated time (sponsors/
  donations stated openly, never assumed).
- **Assumptions:** single-user Mac, APFS boot volume, Spotlight on.
- **Destructive contract:** dry-run by default, trash-first, pending-vs-freed
  accounting, one review gate with full path list, JSONL audit.

## Non-goals (explicit — six, reconciled)

Photos bodies, Mail bodies, iCloud bodies, boot-volume operations,
running-app deletes, MDM-managed machines. Anything outside the assumptions
degrades to read-only or refuses (Task 2 asserts the exact list).

## Sensitivity model

Tiers are evidence thresholds with false-positive budgets — never "deeper =
better" (Task 3). Higher tiers require stronger evidence, not broader
heuristics.

## Architecture Decisions

- **Engine first per slice, UI second behind the same slice** (`CleanMacCore`
  testable headless via `swift test`).
- **Safety rails block everything destructive** (Tasks 4–7): protected/ignore
  lists → review contract → trash-first + accounting → rollback.
- **APFS-correct scanning** (Tasks 8–11): clones/hardlinks/sparse never
  double-counted; purgeable + snapshots are separate categories; no silent
  gaps (unknown, never zero-filled).
- **Evidence-bar uninstall** (Tasks 13–14): bundle-id > team-id >
  anchored-name; shared folders never auto-flagged; `/System` +
  `com.apple.*` refused.
- **Menu bar = `MenuBarExtra` + `.window` style** (decided; SwiftUI-native per
  project rule). `NSStatusItem` path rejected. Popover Esc-dismissal has no
  official contract — verified by manual on-host test, recorded in the PR.
- **Liquid Glass correction:** `.fullSizeContentView` gives edge-to-edge
  content only — it does not by itself deliver Liquid Glass. Glass arrives
  via latest SDK + macOS 26+ runtime + standard components
  (`NavigationSplitView`, toolbars), custom glass only through `glassEffect` /
  `NSGlassEffectView`. `scrollEdgeEffectStyle` is macOS 26+ — always
  `@available`-guarded with fallback. (Sources: developer.apple.com
  technologyoverviews/adopting-liquid-glass, scrolledgeeffectstyle,
  fullsizecontentview.)
- **Privileged work = `SMAppService` daemon (root) with user approval.**
  `SMJobBless` is deprecated — do not use. XPC services cannot escalate;
  trash-watch daemon design comes before any daemon code (Task 27).
- **No direct launchd plist drops** — `SMAppService.{agent,daemon,loginItem}`
  with `.requiresApproval` handling + `openSystemSettingsLoginItems()`.
  (Source: developer.apple.com servicemanagement/smappservice.)
- **Xcode 27 note:** `@State` is a macro (not "SDK 27" — Xcode 27, TN3211).
  Init non-`@State` stored props first; never assign over an inline default;
  no composed wrappers; explicit memberwise init where needed.
- **Hard boundaries:** installers = `.dmg`/`.pkg` only, receipts untouched
  (Task 23, grep-audited); translations = `.lproj` only, no `lipo`
  (Task 24, grep-audited); updater = brew/Sparkle only, no MAS claims
  (Task 21, grep-audited); maintenance space-vs-health split with no false
  space claims (Task 22).
- **`tmutil` is UNVERIFIED as blessed API** (CLI only, no developer docs
  page) — treat its output as untrusted text with parse-failure fallback.
- **Experimental ships gated + off by default** with kill criteria
  (Tasks 25–26). v2 candidates deferred with preconditions (Task 27).
- **FDA has no prompt API.** Pre-explain, deep-link to System Settings >
  Privacy & Security > Full Disk Access, re-probe on return, degrade with
  visible disclaimer. (Sources: Apple support pages, not developer docs.)

## Phases (mirror `tasks/todo.md`)

### Phase A — Foundations (Tasks 1–7)

Policy, non-goals, evidence tiers, ignore/protected lists, review contract,
trash-first + accounting, rollback.

### Checkpoint: Safety rails

- [ ] `swift test --filter 'PolicyTests|ProtectedPathsTests|ReviewGateTests|TrashTests|RollbackTests|SensitivityTests'` green
- [ ] `swift build` clean
- [ ] Human review: rails hold before any deleter is built — nothing below starts until signed

### Phase B — Scanner infra (Tasks 8–11)

APFS-correct analyzer + FDA onboarding; purgeable space + snapshot handling.

### Checkpoint: Scanner infra

- [ ] `swift test --filter 'DiskAnalyzerTests|FDAOnboardingTests|PurgeableTests|SnapshotTests'` green
- [ ] `swift build` clean
- [ ] Totals reconcile with APFS reality; FDA-denied scan degrades with disclaimer

### Phase C — Flagship (Tasks 12–16)

Menu-bar shell + frame first, then evidence-threshold uninstaller (depends on
rails + sizing), orphan sweep, startup manager, Clean Install capture.

### Checkpoint: Flagship

- [ ] `swift test --filter 'ShellTests|UninstallTests|OrphanTests|StartupTests|InstallCaptureTests'` green
- [ ] `swift build` clean
- [ ] Uninstall one real app end-to-end in a sandbox home
- [ ] Human review of picker + plan screens

### Phase D — Upkeep (Tasks 17–24)

Dev caches + process primitive, project purge, large&old (never preselect),
exact-hash duplicates (fixture oracle), updater, maintenance split,
installers sweep, translation pruning.

### Checkpoint: System upkeep

- [ ] `swift test --filter 'DevCacheTests|ProjectPurgeTests|LargeOldTests|DuplicatesTests|UpdaterTests|MaintenanceTests|InstallersTests|TranslationsTests'` green
- [ ] `swift build` clean
- [ ] Grep audits (receipts, lipo, MAS) all empty — paste outputs in PR
- [ ] Human review before experimental phase

### Phase E — Experimental, gated (Tasks 25–26)

AI-tool artifact cleanup (caches only, per-model opt-in) + on-device file
explanations (describe-only, never asserts safety, macOS 26+ gate).
Off by default, kill criteria armed.

### Checkpoint: Experimental

- [ ] `swift test --filter 'AICacheTests|ExplainTests'` green
- [ ] `swift build` clean
- [ ] Explicit human go/no-go per feature before wider exposure

### Phase F — v2 candidates, deferred (Task 27)

Trash-watch daemon (architecture designed up front via
`docs/trash-watch-design.md`, no code before it), Mail cleanup, cloud
cleanup (sync-safety bar), local AI model manager. Record only.

### Checkpoint: Complete

- [ ] All acceptance criteria met
- [ ] Grep audits empty, suites green, build clean
- [ ] Ready for human review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Evidence bar too lax → false-positive delete | High | FP budgets per tier (Task 3); trash-first + rollback (Tasks 6–7) |
| APFS sizing lies (clones/snapshots) | High | Clone-aware math + separate purgeable/snapshot categories (Tasks 8–11) |
| Experimental AI output misleads | High | Describe-only + kill criteria + off by default (Tasks 25–26) |
| Privilege-model mistakes (XPC/SMJobBless) | High | SMAppService daemon only; SMJobBless banned; XPC never for elevation |
| Scope creep per slice | Med | One task = one shippable slice ≤ M; v2 list is a deferral record |
| No funding → burnout (Pearcleaner precedent) | Med | Funding stated openly; every item must earn lifetime maintenance |

## Open Questions

- Distribution beyond signed DMG (Homebrew cask? Sparkle updates?) — v2.
  (Sparkle v1 decision made: user-initiated checks only, Task 1 carve-out.)
- Menu-bar-only mode vs always-a-Dock-icon — default?

## Resolved

- Minimum macOS version: **15** (per `Package.swift` `.macOS(.v15)`).
- `py/` + `bin/` fate: **archived** (skeleton slim commit; `Sources/` is canonical).
- Menu bar vehicle: **`MenuBarExtra` + `.window`** (AppKit path rejected).
- Updater scope: **brew/Sparkle only**, user-initiated; no MAS claims.
