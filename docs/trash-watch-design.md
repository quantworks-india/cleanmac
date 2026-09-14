# Trash Watch Daemon + v2 Backlog

## 1. Daemon lifecycle
- SMAppService user agent, registered only after explicit user approval in UI.
- Never XPC elevation, never SMJobBless. No privileged helper.
- Start on login if approved; stop cleanly on logout/termination; no relaunch loops.

## 2. Sleep / battery
- Observe sleep/wake notifications; pause scans during sleep.
- Coalesce work on battery; defer to power adapter when possible.
- No polling faster than 60s; use FSEvents, not timers.

## 3. TCC
- No FDA required for v1. Trash-only scope (`~/.Trash`); no Photos/Mail/Contacts access.
- If TCC denied, degrade to manual mode with explicit string.

## 4. v2 backlog acceptance bars
- Mail cleanup FDA bar: explicit FDA grant + per-account dry-run diff; never deletes without preview.
- Cloud sync-safety bar: prove no active upload/download (bird, fileproviderd idle) + quarantine window; else "unknown".
- Local AI model manager: model dirs excluded by default; opt-in allowlist only; size + hash shown before any action.

## Non-goals
- No UI surfaces in this task. No Policy.swift changes.
