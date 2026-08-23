# Performance ledger

Baseline host: 2026-08-23. Same commands after each change.

| Idea | Baseline → Result | Verdict | Why |
|------|-------------------|---------|-----|
| `disk summary` depth-1 `du` (no `scan()`) | 35.5s → 26.9s | kept | No 936k-node Python walk. Remaining ~27s is one pass over Library/.colima — physical I/O. Budget <3s not met without skipping real sizes. |
| `dir_sizes` directory-only map | (memory) 936k file keys → dirs only | kept | Same totals; HTML report no longer tiles individual files. |
| `startup list` skip profiler + N+1 launchctl | 2.46s → **0.07s** | kept | State column is `?` unless `--orphans-only`. |
| `list_apps` skip `du` by default | picker no longer pays N× du; `app list` still 0.78s (sizes on) | kept | First paint unblocked. |
| `sfltool` cache + 8s timeout | hung 30s → fail ≤8s; 2nd call free | kept | Fail closed. |
| `system-data` one `du` for all roots | 7.43s → 7.05s | kept | Inside noise for wall clock; fewer processes, same I/O. Budget <4s not met (Library walks dominate). |
