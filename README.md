# CleanMac

A native macOS cleaner — free, zero-telemetry, no account. Menu-bar app plus
a full window. Built entirely with Apple frameworks (SwiftUI, AppKit,
Foundation); no third-party dependencies.

## Status

Skeleton. `main` holds only the canonical project structure; features land
as deliberate slices per `tasks/todo.md`, each with failing-first tests.

## Requirements

- macOS 15 or later
- Full Xcode (SwiftUI macros do not build under Command Line Tools)

## Build, test, run

```bash
swift build            # compile
swift test             # engine tests
./run.sh               # build, bundle, and launch the app
```

## Layout

```
Package.swift              SPM manifest (CleanMacCore + CleanMac + tests)
Sources/CleanMacCore/      Engine library (safety, deletion, scanners)
Sources/CleanMac/          SwiftUI app
Tests/CleanMacCoreTests/   Engine tests
scripts/render-icon.swift  App icon source of truth (CoreGraphics)
Resources/AppIcon.icns     Generated icon (tracked)
tasks/plan.md, todo.md     Build plan + task list
DESIGN.md                  Design direction (Liquid Glass)
```

## Standing rules

- **Dry-run by default.** Nothing is deleted without an explicit commit gate
  plus confirmation.
- **Allowlist safety.** Every path through `realpath(3)` before any check.
- **Everything audited** to JSONL (`ts/run/mode/step/action/path`).
- **Free forever, MIT.** No telemetry, no upsell, no dark patterns.

## License

MIT — see [LICENSE](LICENSE).
