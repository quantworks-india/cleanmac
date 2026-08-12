#!/usr/bin/env bash
# lib/log.sh — structured JSONL logging, audit trail, retention, step framing, report.
# Sourced from bin/cleanmac. Bash 3.2 compatible (macOS default).

CLEANMAC_VERSION="2.0.0"

# ── state layout (env-overridable for tests / custom roots) ─────────
: "${CLEANMAC_STATE_DIR:="${HOME}/.local/state/cleanmac"}"
CLEANMAC_LOG_DIR="${CLEANMAC_LOG_DIR:-${CLEANMAC_STATE_DIR}/logs}"
CLEANMAC_AUDIT_DIR="${CLEANMAC_AUDIT_DIR:-${CLEANMAC_STATE_DIR}/audit}"

LOG_IS_TTY=false
LOG_QUIET=false
LOG_FILE=""
AUDIT_FILE=""
REPORT_FILE=""
RUN_ID=""
LOG_COUNT=0

# ── colors (empty when not a TTY) ───────────────────────────────────
if [[ -t 1 ]]; then
  LOG_IS_TTY=true
  C_RED=$'\033[0;31m';  C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_BLUE=$'\033[0;34m'; C_CYAN=$'\033[0;36m';  C_DIM=$'\033[2m'
  C_BOLD=$'\033[1m';    C_NC=$'\033[0m'
else
  C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_CYAN=''; C_DIM=''; C_BOLD=''; C_NC=''
fi

# ── step accounting (filled by runner / step_end) ───────────────────
declare -a STEP_NAMES=()
declare -a STEP_FREED_KB=()
declare -a STEP_STATUS=()
declare -a STEP_SECS=()
TOTAL_FREED_KB=0

# ── json helpers ────────────────────────────────────────────────────
json_escape() {
  local s="$1" out="" ch hex esc
  local i
  for ((i = 0; i < ${#s}; i++)); do
    ch="${s:i:1}"
    case "$ch" in
      '"') out+='\"' ;;
      '\') out+='\\\\' ;;
      $'\n') out+='\n' ;;
      $'\t') out+='\t' ;;
      $'\r') out+='\r' ;;
      *)
        printf -v hex '%02X' "'$ch"
        if (( 16#$hex < 0x20 )); then
          printf -v esc '\\u%04x' $((16#$hex))
          out+="$esc"
        else
          out+="$ch"
        fi
        ;;
    esac
  done
  printf '%s' "$out"
}

# ── human size formatting (bc preferred, awk fallback) ──────────────
kb_to_human() {
  local kb="$1"
  if (( kb < 1024 )); then
    printf '%sK' "$kb"
  elif command -v bc >/dev/null 2>&1; then
    if (( kb < 1048576 )); then printf '%.1fM' "$(bc -l <<< "$kb/1024")"
    else printf '%.2fG' "$(bc -l <<< "$kb/1048576")"; fi
  else
    if (( kb < 1048576 )); then printf '%.1fM' "$(awk -v k="$kb" 'BEGIN{printf "%.1f", k/1024}')"
    else printf '%.2fG' "$(awk -v k="$kb" 'BEGIN{printf "%.2f", k/1048576}')"; fi
  fi
}

# ── lifecycle ───────────────────────────────────────────────────────
log_init() {
  mkdir -p "$CLEANMAC_LOG_DIR" "$CLEANMAC_AUDIT_DIR" || return 1
  RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
  LOG_FILE="${CLEANMAC_LOG_DIR}/cleanmac-${RUN_ID}.jsonl"
  AUDIT_FILE="${CLEANMAC_AUDIT_DIR}/audit-${RUN_ID}.jsonl"
  REPORT_FILE="${CLEANMAC_STATE_DIR}/report-${RUN_ID}.json"
  : > "$LOG_FILE" || return 1
  : > "$AUDIT_FILE" || return 1
  return 0
}

# log_json LEVEL EVENT MSG [DATA_JSON]
log_json() {
  [[ -n "$LOG_FILE" ]] || return 0
  local level="$1" event="$2" msg="$3" data="${4:-{}}"
  local line ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf -v line '{"ts":"%s","level":"%s","run":"%s","step":"%s","event":"%s","msg":"%s","data":%s' \
    "$ts" "$level" "$RUN_ID" "${CURRENT_STEP:-}" \
    "$(json_escape "$event")" "$(json_escape "$msg")" "$data"
  printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null || return 0
  LOG_COUNT=$((LOG_COUNT + 1))
  if $LOG_IS_TTY && ! $LOG_QUIET; then
    case "$level" in
      error) printf '%s✗ %s%s\n' "$C_RED" "$msg" "$C_NC" ;;
      warn)  printf '%s⚠ %s%s\n' "$C_YELLOW" "$msg" "$C_NC" ;;
      debug) if [[ "${VERBOSE:-false}" == "true" ]]; then printf '%s· %s%s\n' "$C_DIM" "$msg" "$C_NC"; fi ;;
      *)     printf '%s✓ %s%s\n' "$C_GREEN" "$msg" "$C_NC" ;;
    esac
  fi
  return 0
}

# audit_write MODE STEP ACTION PATH SIZE_BYTES
audit_write() {
  [[ -n "$AUDIT_FILE" ]] || return 0
  local mode="$1" step="$2" action="$3" path="$4" size_bytes="${5:-0}"
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '{"ts":"%s","run":"%s","mode":"%s","step":"%s","action":"%s","path":"%s","size_bytes":%s}\n' \
    "$ts" "$RUN_ID" "$mode" "$(json_escape "$step")" "$(json_escape "$action")" \
    "$(json_escape "$path")" "$size_bytes" >> "$AUDIT_FILE" 2>/dev/null || true
  return 0
}

# log_prune DAYS DIR — remove files older than DAYS
log_prune() {
  local days="$1" dir="$2"
  [[ -d "$dir" ]] || return 0
  find "$dir" -type f \( -name '*.jsonl' -o -name '*.json' \) -mtime +"$days" -delete 2>/dev/null || true
  return 0
}

# ── progress bar ────────────────────────────────────────────────────
progress_bar() {
  local cur="$1" total="$2" width=28
  local pct filled empty bar
  pct=$(( cur * 100 / total ))
  filled=$(( pct * width / 100 ))
  empty=$(( width - filled ))
  bar=""
  local i
  for ((i = 0; i < filled; i++)); do bar+="█"; done
  for ((i = 0; i < empty; i++));  do bar+="░"; done
  printf '%s[%s%s]%s %3d%%' "$C_DIM" "$bar" "$C_DIM" "$C_NC" "$pct"
}

# ── step framing ────────────────────────────────────────────────────
step_begin() {
  local id="$1" title="$2"
  CURRENT_STEP="$id"
  STEP_NAMES+=("$title")
  if ! $LOG_QUIET; then
    printf '\n%s━━━ [%s/%s] %s ━━━%s  %s %s(%s left)%s\n' \
      "$C_BOLD$C_BLUE" "$CURRENT" "$TOTAL_STEPS" "$title" "$C_NC" \
      "$(progress_bar "$CURRENT" "$TOTAL_STEPS")" "$C_DIM" \
      "$(( TOTAL_STEPS - CURRENT ))" "$C_NC"
  fi
  log_json "info" "step_start" "started $title" "{\"step\":\"$(json_escape "$id")\"}"
}

step_end() {
  local freed_kb="$1" secs="$2" status="$3"
  STEP_FREED_KB+=("$freed_kb")
  STEP_SECS+=("$secs")
  STEP_STATUS+=("$status")
  TOTAL_FREED_KB=$(( TOTAL_FREED_KB + freed_kb ))
  local freed_h
  freed_h=$(kb_to_human "$freed_kb")
  if ! $LOG_QUIET; then
    case "$status" in
      ok)   printf '  %s Freed: %s%s%s %s(%ss)%s\n' "$C_GREEN" "✓" "$C_BOLD" "$freed_h" "$C_DIM" "$secs" "$C_NC" ;;
      skip) printf '  %s Skipped %s(%ss)%s\n' "$C_YELLOW" "⚠" "$C_DIM" "$secs" "$C_NC" ;;
      *)    printf '  %s Failed %s(%ss)%s\n' "$C_RED" "✗" "$C_DIM" "$secs" "$C_NC" ;;
    esac
  fi
  log_json "info" "step_end" "finished ${STEP_NAMES[${#STEP_NAMES[@]}-1]}" \
    "{\"freed_bytes\":$((freed_kb * 1024)),\"secs\":$secs,\"status\":\"$status\"}"
  CURRENT=$((CURRENT + 1))
}

# ── report ──────────────────────────────────────────────────────────
write_report() {
  local steps_json="" row i freed_bytes total_bytes
  total_bytes=$(( TOTAL_FREED_KB * 1024 ))
  for i in "${!STEP_NAMES[@]}"; do
    freed_bytes=$(( STEP_FREED_KB[$i] * 1024 ))
    printf -v row '{"name":"%s","freed_bytes":%s,"secs":%s,"status":"%s"}' \
      "$(json_escape "${STEP_NAMES[$i]}")" "$freed_bytes" "${STEP_SECS[$i]}" "${STEP_STATUS[$i]}"
    steps_json="${steps_json}${steps_json:+,}${row}"
  done
  local ts duration
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  duration=$(( $(date +%s) - START_TS ))
  printf '{"tool":"cleanmac","version":"%s","ts":"%s","run":"%s","mode":"%s","exit_code":%s,"duration_s":%s,"disk":{"before_bytes":%s,"after_bytes":%s,"freed_bytes":%s},"total_freed_bytes":%s,"steps":[%s]}\n' \
    "$CLEANMAC_VERSION" "$ts" "$RUN_ID" "$MODE" "$EXIT_CODE" "$duration" \
    "$BEFORE_BYTES" "$AFTER_BYTES" "$DISK_FREED_BYTES" "$total_bytes" "$steps_json" > "$REPORT_FILE" 2>/dev/null || true
  return 0
}

print_summary() {
  local i freed_h
  printf '\n%s━━━━━━━━━━━━━━━━ Summary ━━━━━━━━━━━━━━━━%s\n' "$C_BOLD" "$C_NC"
  printf '  %s%-28s %10s %6s %s%s\n' "$C_DIM" "Step" "Freed" "Time" "Status" "$C_NC"
  printf '  %s%s%s\n' "$C_DIM" "────────────────────────────────────────────────" "$C_NC"
  for i in "${!STEP_NAMES[@]}"; do
    freed_h=$(kb_to_human "${STEP_FREED_KB[$i]}")
    case "${STEP_STATUS[$i]}" in
      ok)   badge="${C_GREEN}ok${C_NC}" ;;
      skip) badge="${C_YELLOW}skip${C_NC}" ;;
      *)    badge="${C_RED}fail${C_NC}" ;;
    esac
    printf '  %-28s %10s %6ss %b\n' "${STEP_NAMES[$i]:0:28}" "$freed_h" "${STEP_SECS[$i]}" "$badge"
  done
  printf '  %s%s%s\n' "$C_DIM" "────────────────────────────────────────────────" "$C_NC"
  printf '  %sTracked freed (sum):%s %s%s\n' "$C_BOLD" "$C_NC" "$(kb_to_human "$TOTAL_FREED_KB")" "$C_NC"
  printf '  %sDisk free:%s            %s → %s  %s(+%s actual)%s\n' \
    "$C_BOLD" "$C_NC" "$BEFORE_FREE" "$AFTER_FREE" "$C_GREEN" "$(kb_to_human $((DISK_FREED_BYTES / 1024)))" "$C_NC"
  printf '  %sTotal time:%s           %ss\n' "$C_BOLD" "$C_NC" "$(( $(date +%s) - START_TS ))"
  printf '  %sLog:%s %s\n' "$C_DIM" "$C_NC" "$LOG_FILE"
  printf '  %sAudit:%s %s\n' "$C_DIM" "$C_NC" "$AUDIT_FILE"
  printf '  %sReport:%s %s\n' "$C_DIM" "$C_NC" "$REPORT_FILE"
  if [[ "$MODE" == "dry-run" ]]; then
    printf '  %s▶ DRY-RUN — nothing was deleted. Re-run without --dry-run to clean.%s\n' "$C_YELLOW" "$C_NC"
  elif (( EXIT_CODE == 3 )); then
    printf '  %sDone with %s%d failed step(s)%s — see log for details.%s\n' "$C_YELLOW" "$C_NC" "$FAILED_STEPS" "$C_NC" "$C_NC"
  else
    printf '  %sDone! Restart recommended if you purged RAM/caches.%s\n' "$C_GREEN" "$C_NC"
  fi
  printf '\n'
}
