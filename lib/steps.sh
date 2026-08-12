#!/usr/bin/env bash
# lib/steps.sh — each cleanup step as an idempotent, self-reporting function.
# Sourced from bin/cleanmac after lib/log.sh.

# size_kb PATH — safe du wrapper (returns 0 on missing)
size_kb() {
  local p="$1"
  [[ -e "$p" ]] || { echo 0; return 0; }
  du -sk "$p" 2>/dev/null | cut -f1 || echo 0
}

# ── sudo handling: ask ONCE, then use -n everywhere ────────────────
# ensure_sudo — prompts for the password up front (caches credentials),
# sets SUDO_READY=1 on success. After this, sudo -n never re-prompts.
SUDO_READY=0
ensure_sudo() {
  command -v sudo >/dev/null 2>&1 || return 1
  sudo -v 2>>"$LOG_FILE" && SUDO_READY=1 || return 1
  return 0
}

# run_sudo CMD... — executes via sudo if credentials are cached,
# otherwise falls back to a plain run (so non-elevated setups still work).
run_sudo() {
  if (( SUDO_READY == 1 )); then
    # Re-validate timestamp cheaply; skip if expired (avoid a password prompt).
    sudo -n -v 2>>"$LOG_FILE" || { log_json "debug" "sudo_expired" "sudo timestamp expired, skipping elevated op" "{}"; return 1; }
    sudo -n "$@" 2>>"$LOG_FILE"
  else
    "$@" 2>>"$LOG_FILE"
  fi
}

# with_step STEP_ID TITLE FUNCTION — times + records a step
with_step() {
  local step_id="$1" title="$2" fn="$3" t0 secs
  step_begin "$step_id" "$title"
  t0=$(date +%s)
  if "$fn"; then
    secs=$(( $(date +%s) - t0 ))
    step_end "${STEP_FREED:-0}" "$secs" "ok"
  else
    secs=$(( $(date +%s) - t0 ))
    step_end 0 "$secs" "fail"
    FAILED_STEPS=$((FAILED_STEPS + 1))
  fi
}

# ── Step 1: user caches ─────────────────────────────────────────────
step_user_caches() {
  local before after freed
  before=$(size_kb "$HOME/Library/Caches")
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_delete" "~/$USER/Library/Caches/*" "{\"size_bytes\":$((before*1024))}"
  else
    if [[ -d "$HOME/Library/Caches" ]]; then
      rm -rf "$HOME/Library/Caches/"* 2>>"$LOG_FILE" || { log_json "warn" "delete_failed" "user caches"; return 1; }
    fi
  fi
  after=$(size_kb "$HOME/Library/Caches")
  freed=$(( before - after )); [[ $freed -lt 0 ]] && freed=0
  STEP_FREED="$freed"
  audit_write "$MODE" "user_caches" "delete" "$HOME/Library/Caches" $((freed*1024))
  return 0
}

# ── Step 2: system caches (sudo) ────────────────────────────────────
# Paths are env-overridable so tests (and custom roots) can sandbox them.
SYS_CACHE_DIRS=(
  "${CLEANMAC_SYS_CACHES:-/Library/Caches}"
  "${CLEANMAC_SYS_CACHES2:-/System/Library/Caches}"
)
step_system_caches() {
  local before after freed dir
  before=0; after=0
  for dir in "${SYS_CACHE_DIRS[@]}"; do
    before=$(( before + $(size_kb "$dir") ))
  done
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_delete" "system caches" "{\"dirs\":\"${SYS_CACHE_DIRS[*]}\",\"size_bytes\":$((before*1024))}"
  else
    for dir in "${SYS_CACHE_DIRS[@]}"; do
      if [[ -d "$dir" ]]; then
        # Best-effort: SIP-protected items may refuse deletion even as root.
        # Failure to remove a protected entry is expected, not a step failure.
        if run_sudo rm -rf "$dir/"*; then
          log_json "debug" "deleted" "system caches: $dir" "{}"
        else
          log_json "warn" "partial" "system caches: $dir — some items protected (SIP), continuing" "{}"
        fi
      fi
    done
  fi
  for dir in "${SYS_CACHE_DIRS[@]}"; do
    after=$(( after + $(size_kb "$dir") ))
  done
  freed=$(( before - after )); [[ $freed -lt 0 ]] && freed=0
  STEP_FREED="$freed"
  audit_write "$MODE" "system_caches" "delete" "${SYS_CACHE_DIRS[*]}" $((freed*1024))
  return 0
}

# ── Step 3: logs ────────────────────────────────────────────────────
SYS_LOG_DIRS=(
  "${CLEANMAC_SYS_LOGS:-/private/var/log}"
  "${CLEANMAC_SYS_LOGS2:-/var/log}"
)
step_logs() {
  local before after freed dir
  before=0; after=0
  for dir in "$HOME/Library/Logs" "${SYS_LOG_DIRS[@]}"; do
    before=$(( before + $(size_kb "$dir") ))
  done
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_delete" "logs" "{\"size_bytes\":$((before*1024))}"
  else
    rm -rf "$HOME/Library/Logs/"* 2>>"$LOG_FILE" || true
    for dir in "${SYS_LOG_DIRS[@]}"; do
      [[ -d "$dir" ]] && run_sudo rm -rf "$dir/"* || true
    done
  fi
  after=0
  for dir in "$HOME/Library/Logs" "${SYS_LOG_DIRS[@]}"; do
    after=$(( after + $(size_kb "$dir") ))
  done
  freed=$(( before - after )); [[ $freed -lt 0 ]] && freed=0
  STEP_FREED="$freed"
  audit_write "$MODE" "logs" "delete" "$HOME/Library/Logs ${SYS_LOG_DIRS[*]}" $((freed*1024))
  return 0
}

# ── Step 4: trash + local snapshots ─────────────────────────────────
step_trash() {
  local trash_kb snap_count freed
  trash_kb=$(size_kb "$HOME/.Trash")
  snap_count=0
  if command -v tmutil >/dev/null 2>&1; then
    snap_count=$(tmutil listlocalsnapshots / 2>/dev/null | grep -c "com.apple.TimeMachine" 2>/dev/null || true)
  fi
  [[ "$snap_count" =~ ^[0-9]+$ ]] || snap_count=0
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_delete" "trash + snapshots" "{\"trash_bytes\":$((trash_kb*1024)),\"snapshots\":$snap_count}"
  else
    if (( trash_kb > 0 )); then
      rm -rf "$HOME/.Trash/"* 2>>"$LOG_FILE" || true
      run_sudo rm -rf /Volumes/*/.Trashes || true
    fi
    if (( snap_count > 0 )); then
      run_sudo tmutil thinlocalsnapshots / 10000000000 4 || log_json "warn" "snapshot_thin_failed" "tmutil"
    fi
  fi
  freed=$(size_kb "$HOME/.Trash")
  STEP_FREED=$(( trash_kb - freed ))
  [[ $STEP_FREED -lt 0 ]] && STEP_FREED=0
  audit_write "$MODE" "trash" "delete" "$HOME/.Trash" $((STEP_FREED*1024))
  return 0
}

# ── Step 5: homebrew ────────────────────────────────────────────────
step_homebrew() {
  local before after freed
  command -v brew >/dev/null 2>&1 || { STEP_FREED=0; return 2; }  # 2 = skip
  before=$(( $(size_kb "$HOME/Library/Caches/Homebrew") + $(size_kb /Library/Caches/Homebrew) ))
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_run" "brew cleanup --prune=all" "{}"
  else
    brew cleanup --prune=all >>"$LOG_FILE" 2>&1 || true
    brew autoremove >>"$LOG_FILE" 2>&1 || true
  fi
  after=$(( $(size_kb "$HOME/Library/Caches/Homebrew") + $(size_kb /Library/Caches/Homebrew) ))
  freed=$(( before - after )); [[ $freed -lt 0 ]] && freed=0
  STEP_FREED="$freed"
  audit_write "$MODE" "homebrew" "clean" "Homebrew caches" $((freed*1024))
  return 0
}

# ── Step 6: dev caches (xcode, docker, npm, pip) ────────────────────
step_dev_caches() {
  local before after freed xcode_after npm_after pip_after
  before=$(( $(size_kb "$HOME/Library/Developer/Xcode/DerivedData") + $(size_kb "$HOME/.npm") + $(size_kb "$HOME/Library/Caches/pip") ))
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_delete" "dev caches" "{\"size_bytes\":$((before*1024))}"
  else
    if [[ -d "$HOME/Library/Developer/Xcode/DerivedData" ]]; then
      rm -rf "$HOME/Library/Developer/Xcode/DerivedData/"* 2>>"$LOG_FILE" || true
    fi
    if command -v docker >/dev/null 2>&1; then
      docker system prune -af --volumes >>"$LOG_FILE" 2>&1 || log_json "warn" "docker_prune_failed" "docker"
    fi
    if command -v npm >/dev/null 2>&1; then
      npm cache clean --force >>"$LOG_FILE" 2>&1 || true
      # npm cache clean --force removes the cache dir contents itself; if the
      # mock/real npm leaves files behind (e.g. offline cache), fall back to rm.
      if [[ -d "$HOME/.npm/_cacache" && -n "$(ls -A "$HOME/.npm/_cacache" 2>/dev/null)" ]]; then
        rm -rf "$HOME/.npm/_cacache/"* 2>>"$LOG_FILE" || true
      fi
    fi
    if [[ -d "$HOME/Library/Caches/pip" ]]; then
      pip cache purge >>"$LOG_FILE" 2>&1 || rm -rf "$HOME/Library/Caches/pip/"* 2>>"$LOG_FILE" || true
    fi
  fi
  after=$(( $(size_kb "$HOME/Library/Developer/Xcode/DerivedData") + $(size_kb "$HOME/.npm") + $(size_kb "$HOME/Library/Caches/pip") ))
  freed=$(( before - after )); [[ $freed -lt 0 ]] && freed=0
  STEP_FREED="$freed"
  audit_write "$MODE" "dev_caches" "delete" "DerivedData, npm, pip" $((freed*1024))
  return 0
}

# ── Step 7: DNS + RAM ───────────────────────────────────────────────
step_dns_ram() {
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_run" "dscacheutil flush + purge" "{}"
  else
    run_sudo dscacheutil -flushcache || true
    run_sudo killall -HUP mDNSResponder || true
    run_sudo purge || true
  fi
  STEP_FREED=0
  audit_write "$MODE" "dns_ram" "flush" "dns + ram" 0
  return 0
}

# ── Step 8: periodic maintenance ────────────────────────────────────
step_periodic() {
  if [[ "$MODE" == "dry-run" ]]; then
    log_json "info" "would_run" "sudo periodic daily weekly monthly" "{}"
  else
    run_sudo periodic daily weekly monthly || log_json "warn" "periodic_failed" "periodic"
  fi
  STEP_FREED=0
  audit_write "$MODE" "periodic" "run" "periodic daily/weekly/monthly" 0
  return 0
}
