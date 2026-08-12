#!/usr/bin/env bash
# cleanmac — observable macOS cleanup. See lib/log.sh for the observability core.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for lib in log steps; do
  # shellcheck source=/dev/null
  source "${HERE}/../lib/${lib}.sh" || { echo "fatal: cannot load lib/${lib}.sh" >&2; exit 1; }
done

# ── arg parsing ─────────────────────────────────────────────────────
MODE="live"
VERBOSE=false
CLEAN_APPS=false
APP_NAME=""
HELP=false
while (( $# > 0 )); do
  case "$1" in
    --dry-run) MODE="dry-run" ;;
    --verbose) VERBOSE=true ;;
    --app) CLEAN_APPS=true; APP_NAME="${2:-}"; shift ;;
    -h|--help) HELP=true ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if $HELP; then
  cat <<'EOF'
cleanmac — observable macOS cleanup

USAGE:
  cleanmac [--dry-run] [--verbose] [--app <name>]

OPTIONS:
  --dry-run     Preview only, delete nothing
  --verbose     Detailed per-file logging
  --app <name>  Search & remove leftovers of an uninstalled app

EXIT CODES:
  0  success
  2  usage error
  3  one or more steps failed
EOF
  exit 0
fi

# ── counters / globals ──────────────────────────────────────────────
TOTAL_STEPS=8
CURRENT=1
FAILED_STEPS=0
EXIT_CODE=0
CURRENT_STEP=""
START_TS=$(date +%s)
BEFORE_BYTES=0
AFTER_BYTES=0
DISK_FREED_BYTES=0
BEFORE_FREE=""
AFTER_FREE=""

# ── init observability ──────────────────────────────────────────────
log_init || { echo "fatal: cannot initialize state dir" >&2; exit 1; }

disk_bytes() { df -k / 2>/dev/null | awk 'NR==2{print $4}'; }
disk_free_human() { df -h / 2>/dev/null | awk 'NR==2{print $4}'; }
BEFORE_KB=$(disk_bytes)
BEFORE_BYTES=$(( BEFORE_KB * 1024 ))
BEFORE_FREE=$(disk_free_human)

log_json "info" "run_start" "cleanmac v${CLEANMAC_VERSION} started" \
  "{\"mode\":\"$MODE\",\"verbose\":$VERBOSE,\"disk_free_bytes\":$BEFORE_BYTES}"

printf '\n%s Cleanmac %s— Observable Edition%s %slog: %s%s\n' \
  "$C_BOLD" "$CLEANMAC_VERSION" "$C_NC" "$C_DIM" "$LOG_FILE" "$C_NC"
printf '%s Started: %s  |  Disk free: %s%s%s  |  Mode: %s%s%s%s\n' \
  "$C_DIM" "$(date '+%Y-%m-%d %H:%M:%S')" "$C_BOLD" "$BEFORE_FREE" "$C_NC" \
  "$C_NC" "$([[ "$MODE" == "dry-run" ]] && echo "${C_YELLOW}DRY-RUN${C_NC}" || echo "${C_GREEN}LIVE${C_NC}")" "$C_NC"

# ── sudo: ask ONCE for all elevated steps ──────────────────────────
if [[ "$MODE" == "live" ]]; then
  printf '%s Elevation check — enter your password once (used for caches, logs, DNS, snapshots, periodic)%s\n' "$C_DIM" "$C_NC"
  if ensure_sudo; then
    printf '  %s Sudo credentials cached — no more prompts.%s\n' "$C_GREEN" "$C_NC"
  else
    printf '  %s Sudo unavailable — elevated steps will be skipped.%s\n' "$C_YELLOW" "$C_NC"
    log_json "warn" "sudo_unavailable" "sudo credentials not obtained" "{}"
  fi
else
  log_json "info" "dry_run_no_sudo" "dry-run: skipping elevation" "{}"
fi

# ── run steps ───────────────────────────────────────────────────────
with_step "user_caches"    "User Caches  ~/Library/Caches"          step_user_caches
with_step "system_caches"  "System Caches  /Library/Caches"         step_system_caches
with_step "logs"           "Logs  ~/Library/Logs + /private/var/log" step_logs
with_step "trash"          "Trash & Local Snapshots"                step_trash
with_step "homebrew"       "Homebrew Cleanup"                       step_homebrew
with_step "dev_caches"     "Dev Caches  (Xcode, Docker, npm, pip)"  step_dev_caches
with_step "dns_ram"        "Flush DNS & Purge Inactive RAM"         step_dns_ram
with_step "periodic"       "macOS Maintenance (periodic)"           step_periodic

# ── finalize ────────────────────────────────────────────────────────
AFTER_KB=$(disk_bytes)
AFTER_BYTES=$(( AFTER_KB * 1024 ))
DISK_FREED_BYTES=$(( AFTER_BYTES - BEFORE_BYTES ))
[[ $DISK_FREED_BYTES -lt 0 ]] && DISK_FREED_BYTES=0
AFTER_FREE=$(disk_free_human)

if (( FAILED_STEPS > 0 )); then EXIT_CODE=3; fi
write_report
print_summary
log_prune 30 "$CLEANMAC_LOG_DIR"
log_prune 30 "$CLEANMAC_AUDIT_DIR"

log_json "info" "run_end" "cleanmac finished" \
  "{\"duration_s\":$(( $(date +%s) - START_TS )),\"failed_steps\":$FAILED_STEPS,\"exit_code\":$EXIT_CODE}"

exit "$EXIT_CODE"
