# Uninstall matrix + brew/helpers — task list

Source: `tasks/plan.md`

## Task 1: brew scanner
**Description:** Find Homebrew leftovers (Caskroom app, Cellar ref) for the target.

**Acceptance criteria:**
- [ ] `brew_paths(bundle, name)` returns matching Caskroom/Cellar entries
- [ ] Uses `brew --prefix` (fallback /opt/homebrew, /usr/local)
- [ ] No-op when Homebrew absent

**Verification:** sandbox fake Caskroom/Cellar test; full suite.
**Files:** `app_uninstaller.py`, new test.
**Size:** S

## Task 2: helpers scanner
**Description:** Find PrivilegedHelperTools entries for the vendor prefix.

**Acceptance criteria:**
- [ ] `helper_paths(bundle, name)` returns matching helpers
- [ ] Requires sudo flag surfaced
- [ ] No-op when dir absent

**Verification:** sandbox helpers test; full suite.
**Files:** `app_uninstaller.py`, new test.
**Size:** S

## Checkpoint: fingerprint complete (fp has brew + helpers)

## Task 3: boolean matrix render
**Description:** uninstall prints one row per app, columns = stores, Y/N/—.

**Acceptance criteria:**
- [ ] Human prints transposed one-row matrix
- [ ] JSON emits same keys
- [ ] `—` for kext/BTM/mas-when-gone

**Verification:** render test (masked) + JSON shape test.
**Files:** `uninstall.py`, new test.
**Size:** M

## Task 4: clean brew + helpers on `y`
**Description:** on confirm, delete brew (user) and helpers (sudo) paths.

**Acceptance criteria:**
- [ ] brew paths deleted via user deleter
- [ ] helper paths deleted via sudo
- [ ] no `--commit` needed; single `y` gates

**Verification:** no-commit deletes nothing; commit deletes.
**Files:** `uninstall.py`, `cli.py` `_needs_sudo` includes helpers.
**Size:** M

## Checkpoint: all addressable stores cleaned

## Task 5: README + column names
**Description:** document the matrix row and legend.

**Acceptance criteria:**
- [ ] README shows the row and Y/N/— legend
**Files:** `README.md`.
**Size:** XS
