# Implementation Plan: Uninstall matrix + brew/helper scanners

## Overview

Two changes, one uninstall slice:

1. **Boolean matrix output** — the uninstall plan becomes one row per
   app, one column per documented leftover store, cell = `Y` (present +
   will delete) / `N` (absent) / `—` (not addressable). App-gone-but-
   leftovers remains obvious at a glance.
2. **Two new cleaners** — `brew` (Homebrew Caskroom/Cellar) and `helpers`
   (PrivilegedHelperTools) — because the matrix is a *view* and today we
   only *scan+delete* nine stores; these two have no code behind them.

Locked column set (docs-backed, union of Apple Library table + App Store
receipt + SMAppService + Homebrew Cask uninstall/zap):

```
app  mas  pkg  brew  support  cache  prefs  container  saved  agents  daemons  helpers
```

- `mas` (receipt) lives **inside** the `.app`; dies with the bundle. Rendered
  `Y` only while the app is alive, else `—`. No separate delete.
- `kext`, BTM/login items (`sfltool`), Keychain, TCC: **not addressable** —
  render as `—`, never in the delete set.
- `pkg` receipts, support/cache/prefs/container/saved/agents/daemons: already
  cleaned today.

Same command surface: `cleanmac uninstall [target]`, one `y/N` gate.

## Current state

| Column | Clean today? |
|---|---|
| app | yes — bundle delete |
| support / cache / prefs / byhost / container / group / saved / webkit / http / cookies / logs / services / quicklook / spotlight | yes — USER_PATTERNS |
| agents (user) | yes — quarantine |
| daemons | yes — sudo quarantine |
| pkg receipts | yes — SYSTEM_PATTERNS |
| **brew** | **no code** |
| **helpers** | **no code** |

## Architecture decisions

- `brew` clean = remove matching entry under `$(brew --prefix)/Caskroom`
  (the installed cask) and any `Cellar/<name>` for a formula with the same
  name. Homebrew keeps these trees; removing them is what a cask zap does
  for Homebrew's own install directory. Treated as user-writable (brew is
  user-owned by default).
- `helpers` = scan `/Library/PrivilegedHelperTools` (and `~/Library/...` if
  present) for executables whose name or embedded bundle id matches the
  target vendor prefix or name. Requires sudo to delete.
- Both scanners share the vendor-prefix rule (`us.zoom.xos` → `us.zoom.`).
- Matrix is data: a dict of column → (present, path|None). Human prints the
  transposed one-row form; JSON emits the same keys so it stays byte-identical
  in shape.

## Task List

### Task 1: brew scanner
- Add `brew_paths(bundle, name)` → matching Caskroom + Cellar entries
- Add to fingerprint `fp["brew"]`
- Tests: sandboxed fake Caskroom

### Task 2: helpers scanner
- Add `helper_paths(bundle, name)` under PrivilegedHelperTools
- Add to fingerprint `fp["helpers"]`
- Tests: sandboxed fake helpers dir

### Checkpoint: fingerprint union complete

### Task 3: boolean matrix render (human + JSON)
- `uninstall.py` builds column dict, prints one-row matrix
- JSON identical shape
- Tests: row string + JSON

### Task 4: clean brew + helpers on `y`
- Wire brew (user) + helpers (sudo) into the delete set
- Tests: no-commit no-op; commit deletes

### Checkpoint: uninstall removes all addressable stores

### Task 5: README + column legend
- Document the row + which are `—`

## Risks

| Risk | Mitigation |
|---|---|
| Brew paths vary by prefix | resolve `brew --prefix` once; fall back to `/opt/homebrew`/`/usr/local` |
| Caskroom match ambiguity | match exact Caskroom/<name> + Cellar/<name>; do not fuzzy glob whole prefix |
| Helpers name drift | match vendor prefix + bundle-id-derived names; no brand list |
| Never touch kext/BTM/login | exclude from delete set; render as `—` |

## Out of scope

kext, BTM/slogin items, Keychain, TCC, per-app brand maps.
