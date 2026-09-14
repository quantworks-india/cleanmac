# CleanMac — handoff (resume in a fresh chat from here)

## Project
Free, open-source, native macOS Swift cleaner (CleanMyMac competitor, MIT,
zero telemetry, no account, no upsell). Repo: `/Users/sandeep/projects/utils/cleanmac`.

## Branch map — read this first
- `main` — Swift skeleton ONLY (structure, no features). Do not build features here.
- `feat/safety-core` (current, pushed, in sync with remote) — active build branch.
  All feature slices land here via TDD, one commit per slice.
- Tag `backup/feat-ux-human-screens` — frozen archive of the entire old
  history (Python CLI era + early Swift slices + all research docs below).
  Cherry-pick from it when re-cutting; never develop on it.
- `~/projects/archive/cleanmac-python/` — Python CLI source outside git.
- Old remote feature branch deleted; remote has only `main` + `feat/safety-core`.

## Research docs (in the backup tag under tasks/, NOT in current tree)
`competitive-analysis.md`, `features-plan.md`, `superset-features.md`
(30 ranked features — superseded by the reconciled plan, read for context),
`wireframes.html`, `comps.html`, `icon-concepts*.html`, old `handover.md`
(stale — this file replaces it). Read via
`git show backup/feat-ux-human-screens:tasks/<file>`.

## Locked plan (tasks/plan.md + tasks/todo.md, 27 tasks) — status
- Plan lockdown commit `4a2fb06` + doubt cycle 1 reconciled (reconcile log at
  bottom of `tasks/superset-features.md` in backup tag). Cross-model review
  was offered and dismissed — treat as skipped, announced.
- **Done: Task 1** (Policy free-forever/telemetry/carve-outs, commit `47e85d3`).
- **Next: Task 2** (non-goals + assumptions, XS), then Task 3.
- Standing commitments (override everything): FREE forever/MIT/zero telemetry;
  trust wedge (no placebos, no security theatre, no inflated counts);
  safety rails before deleters; TDD red-first; thin slices; commit+push/slice.
- Open questions ONLY the user can answer: distribution beyond DMG;
  menu-bar-only vs Dock default.

## Environment — critical, read carefully
- **Full Xcode is GONE** (`/Applications/Xcode.app` vanished; `xcode-select`
  points at CommandLineTools). User must reinstall Xcode + run
  `sudo xcode-select -s /Applications/Xcode.app`. Until then:
  - `swift build` works for macro-free targets only.
  - `swift test` is BROKEN two ways: TestingMacros plugin missing AND XCTest
    module unresolvable under CLT. Do not "fix" code for this.
  - **Workaround (proven):** keep XCTest files in-tree for CI, verify locally
    by compiling sources + a `@main` harness directly:
    `swiftc Sources/CleanMacCore/*.swift /tmp/xxx_check.swift -o /tmp/xxx_check && /tmp/xxx_check`
    (harness needs `@main struct`; top-level expressions are rejected when
    compiling multiple files). Revert to `swift test` the moment Xcode returns.
  - **CI (`.github/workflows/ci.yml`, macos-15 runners) is the source of truth
    for green until Xcode is back.**
- Toolchain flakes seen repeatedly: macro-plugin "not found" → `rm -rf .build`
  (stronger than `swift package clean`); stale `libCleanMacCore.a` confusing
  the linker → compile sources directly; `swift test` output interleaves →
  rerun cleanly before trusting a failure line.
- `.build/` is gitignored. `run.sh` builds + bundles + launches detached.

## Key technical facts (do not rediscover)
- `URL.resolvingSymlinksInPath` does NOT resolve `/var→/private/var` on this
  OS — use POSIX `realpath(3)` (see backup tag `Safety.swift`, to be re-cut).
- Swift 6 strict concurrency: no shared mutable statics (use computed
  properties); `NetworkCallKind` must be `Sendable`.
- `MenuBarExtra` suppresses the `WindowGroup` launch window → needs
  `.defaultLaunchBehavior(.presented)` (macOS 15 floor, do not lower it).
- Raw SPM binaries get no windows/menu slots — always launch via `run.sh`
  (builds minimal `.app` bundle). GUI apps don't exit; `swift run` blocks.
- `iconutil` requires the folder to be literally named `*.iconset`.
- Icon decision made: **Lattice C** (`Resources/AppIcon.icns` tracked,
  `scripts/render-icon.swift` is source of truth).
- Design: Liquid Glass (macOS 26+), light+dark peers. Full Glass window
  chrome needs `NSWindowController` + `.fullSizeContentView` —
  a SwiftUI `Window` scene cannot render it. `@State` is a macro in Xcode 27
  (TN3211 — never "fix" by reordering inits).
- `SMJobBless` is deprecated — privileged work = `SMAppService` daemon with
  user approval. No direct launchd plist drops. FDA has no prompt API
  (deep-link + re-probe + degrade visibly).

## User conventions (hard constraints)
- Brief, direct, pragmatic. Truth over pleasantries. No emojis unless asked.
- All code/comments/identifiers in English.
- Conventional commits, imperative mood (`feat(swift): ...`). Push per slice.
- Verify by executing; never narrate intent. Evidence before assertions.
- Web policy: websearch first for versions/changelogs/APIs (Exa enabled);
  cite full URLs; never state versions from memory; say explicitly if
  websearch is unavailable.
- If ambiguous: state assumptions OR ask exactly one clarifying question.
- User runs MonoCode on top of opencode; `OPENCODE_ENABLE_EXA=1` is set.

## Installed skills (~/.config/opencode/skills)
TDD, incremental-implementation, planning-and-task-breakdown,
code-review-and-quality, code-simplification, source-driven-development,
doubt-driven-development, verification-before-completion, macos-build,
macos-patterns, macos-settings-ui, macos-release, macos-auto-update,
macos-notch-ui, swiftui-specialist, swiftui-whats-new-27 (Apple-official),
test-modernizer, audit-xcode-security-settings, impeccable, cli-tui-design-language.
