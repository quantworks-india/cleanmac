# cleanmac

Observable macOS cleanup: caches, logs, trash, snapshots, brew, dev caches, DNS/RAM, periodic maintenance — with structured logging, an audit trail, and per-step reporting.

## Usage

```bash
bin/cleanmac              # live run
bin/cleanmac --dry-run    # preview only, delete nothing
bin/cleanmac --verbose    # per-file detail in the console
bin/cleanmac --app <name> # find & remove leftovers of an uninstalled app
```

Optional: add the wrapper to your PATH.

```bash
export PATH="$HOME/projects/tooling/bin:$PATH"
```

## Observability

- **Structured logs** — every event as JSONL: `~/.local/state/cleanmac/logs/cleanmac-<ts>.jsonl`
- **Audit trail** — every delete/action: `~/.local/state/cleanmac/audit/audit-<ts>.jsonl`
- **Report** — machine-readable run summary: `~/.local/state/cleanmac/report-<ts>.json`
- **Console** — `[n/8]` step counter, progress bar, per-step freed bytes + time, final summary
- **Retention** — logs/audits auto-pruned after 30 days
- **Exit codes** — `0` ok, `2` usage error, `3` one or more steps failed

Override state dir with `CLEANMAC_STATE_DIR` (tests use this).

## Structure

```
cleanmac/
  bin/cleanmac      # thin runner
  lib/log.sh        # logging, audit, report, framing
  lib/steps.sh      # one function per cleanup step
  tests/            # zero-dependency test suite
```

## Tests

```bash
tests/run_tests.sh
```

Sandboxes `HOME`, stubs `sudo/brew/docker/npm/pip/tmutil`, and verifies: exit codes, dry-run deletes nothing, live run frees space, logs/audit/report content, and console observability.
