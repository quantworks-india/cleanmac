# Implementation Plan: CleanMac native Swift app (menu bar + window), full parity

## Overview

Rewrite CleanMac as a native macOS Swift app: menu-bar icon with popover for
quick actions plus a full window for detail screens. v1 replicates all eight
Python/bash tools with behavioral parity: deep uninstall, junk cleanup,
duplicate finder, disk analyzer, memory cleaner, hidden-files toggle,
startup/orphan (BBA) management, and app inventory. Dry-run-by-default,
single-confirm destructive flows, JSONL audit, and the sudo-once model carry
over unchanged. The Python implementation in `py/` + `bin/` + `lib/` is the
executable spec — every slice below cites the source behavior it ports.

## Architecture Decisions

- **Native-first, no custom reinvention.** Use SwiftUI/AppKit/Foundation
  capabilities before writing custom code: `List`/`Table`, `NSStatusItem`
  popover, `FileManager` enumeration, `Process` for system tools, `SMAppService`
  for privilege, ` partijen`… (no third-party UI or utility dependencies in v1;
  every proposed dependency needs a written justification).
- **Liquid Glass design language throughout.** Translucent layered surfaces,
  depth over chrome, system materials (`.ultraThinMaterial` and friends),
  SF Symbols, native light/dark adaptation — no custom-drawn lookalikes of
  system components.
- **TDD + incremental delivery on every task.** Failing test first
  (`swift test --filter`), thin vertical slices, verify + commit per slice.
  Scaffold/config files are the documented TDD exception.

- **SwiftUI for UI, AppKit bridges where SwiftUI can't reach** (menu-bar
  `NSStatusItem` popover needs AppKit; tables/lists are SwiftUI). Rationale:
  fastest to working UI, native look, Xcode previews for visual review.
- **Swift Package Manager layout, one `CleanMac` app target + `CleanMacCore`
  library target.** Rationale: engine testable without launching the app;
  mirrors `py/src/maccleaner` module boundaries (Core, Uninstall, Scanners…).
- **Engine first per slice, UI second, always behind the same slice.**
  Rationale: keeps every task shippable and testable headless via
  `swift test`.
- **Safety core is Task 1 and blocks everything destructive.** The
  realpath-allowlist, commit gate, single-confirm, and audit writer port
  first; every later slice reuses them instead of reimplementing.
- **Privileged work via SMAppService helper (modern) not raw sudo.**
  Rationale: `sudo` prompts don't belong in a GUI app; a privileged helper
  with `SMAuthorizedWork` is the Apple-blessed path. Falls back to
  per-action auth prompt when the helper isn't installed.
- **No Sparkle/Homebrew distribution in v1.** Signed + notarized DMG from
  Xcode; auto-update is explicitly out of scope (open question below).

## Task List

### Phase 1: Safe slices (read-only or user-level temp cleanup first)

- [ ] Task 0: Xcode project + SPM layout + CI build
- [ ] Task 1: Safety core port (allowlist, commit gate, audit, dry-run)
- [ ] Task 6: Junk cleanup engine + screen (8 steps, progress, report)
      — also establishes the menu-bar shell + window used by all later UI
- [ ] Task 8: Disk analyzer engine + screen (scan, top, treemap or bar view)
- [ ] Task 7: Duplicate finder engine + screen (hash, groups table)
- [ ] Task 9: Memory engine + screen (free, heavy list, guarded kill)

### Checkpoint: Safe tools
- [ ] Junk/disk/dup/memory all work dry-run with zero destructive paths
- [ ] Human review of menu-bar shell + one screen before proceeding

### Phase 2: Destructive slices (uninstall flagship + startup)

- [ ] Task 2: App inventory (system_profiler JSON + fallback glob)
- [ ] Task 3: Leftover fingerprint (user/system/launch/brew/helpers, matrix)
- [ ] Task 4: Uninstall flow (plan → single confirm → delete → quarantine)
- [ ] Task 5: Uninstall window (picker list, plan table) in the Phase 1 shell
- [ ] Task 10: Hidden-files toggle + startup/orphan (BBA) screens

### Checkpoint: Flagship
- [ ] Uninstall one real app end-to-end in a sandbox home
- [ ] Human review of picker + plan screens before proceeding

### Phase 3: Ship

- [ ] Task 11: Privileged helper (SMAppService) for system-scope deletes
- [ ] Task 12: Signing, notarization, DMG, first-run permission onboarding

### Checkpoint: Complete
- [ ] Notarized DMG installs on a clean Mac, all flows work
- [ ] Ready for review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Full parity is 11 tasks; scope creep per tool | High | Vertical slices with per-slice acceptance; cut a tool to v1.1, never half-ship it |
| Privileged helper + notarization friction (entitlements, TCC) | High | Task 11 early-spikes the helper with a throwaway target; Task 12 last |
| SwiftUI menu-bar popover quirks (focus, Esc, screen edges) | Med | AppKit `NSPopover` bridge from day one; Esc-to-close test in Task 5 |
| system_profiler/sfltool latency on first launch | Med | Lazy + cached inventory (port the lru_cache pattern); progress UI |
| Diverging from Python behavior silently | Med | Each slice cites source files; audit-event names stay identical |

## Open Questions

- Distribution beyond signed DMG (Homebrew cask? Sparkle updates?) — v2.
- Minimum macOS version (propose 14 Sonoma for SMAppService + modern SwiftUI).
- What happens to `py/` + `bin/` — archive, or keep as reference CLI?
- Menu-bar-only mode vs always-a-Dock-icon — default?
