# Implementation Plan: Deep interactive uninstall (`cleanmac app uninstall`)

## Overview

A deep, interactive uninstall that removes an app AND every fingerprint it
leaves behind — the exact failure pattern seen with Adobe/Avast/Box/OneDrive/
Zoom (app gone but LaunchDaemons, background items, and support dirs linger).

Native-mac API based, no regex, no brand lists.

## Architecture decisions

- New subcommand: `cleanmac app uninstall` (interactive picker) with
  `--name <app>` for non-interactive/scripted use.
- Reuse existing building blocks: `list_apps()`, `_find_app()`,
  `_user_paths()`, `_system_paths()`, `_run_remove()`, `_orphans_purge()`.
- Fingerprint scan is the key addition: given an app, find every launch
  plist (via plistlib glob across ~/Library/LaunchAgents, /Library/LaunchAgents,
  /Library/LaunchDaemons) whose label/executable matches the app's bundle id
  or name, plus any BBA items (via `sfltool dumpbtm`) whose bundle id matches.
- Dry-run by default (`--commit` to act). One sudo prompt.
- Interactive picker only shows when TTY; `--name` bypasses it.

## Task list (TDD)

1. RED: `_build_fingerprint(app)` returns launch plists + BBA items owned by the app.
2. RED: `_run_uninstall(args)` deep flow (app + leftovers + launch + BBA).
3. RED: CLI wires `app uninstall` with `--name` and interactive picker.
4. GREEN: implement each to pass.
5. Tests use fixtures (tmp paths, fake sfltool dump, fake inventory). No real /Library.

## Risks

- Matching an app to launch plists must be mechanical (bundle id == label, or
  exe path under the app bundle), never substring brand guessing.
- BBA items keyed by label vs app's bundle id need a clear match rule.
- sudo prompt once for system-scope items.
