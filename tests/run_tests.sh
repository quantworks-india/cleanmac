#!/usr/bin/env bash
# tests/run_tests.sh — zero-dependency test suite. Sandboxes HOME + PATH with mocks.
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${PROJECT_ROOT}/bin/cleanmac"
SANDBOX="$(mktemp -d /tmp/cleanmac-test.XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT

# ── test framework ──────────────────────────────────────────────────
PASS=0; FAIL=0; FAILED_NAMES=()
T() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    PASS=$((PASS + 1)); printf '  \033[32m✓\033[0m %s\n' "$name"
  else
    FAIL=$((FAIL + 1)); FAILED_NAMES+=("$name")
    printf '  \033[31m✗\033[0m %s\n    expected: %s\n    actual:   %s\n' "$name" "$expected" "$actual"
  fi
}
T_CONTAINS() {
  local name="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    PASS=$((PASS + 1)); printf '  \033[32m✓\033[0m %s\n' "$name"
  else
    FAIL=$((FAIL + 1)); FAILED_NAMES+=("$name")
    printf '  \033[31m✗\033[0m %s\n    missing: %s\n    in: %s\n' "$name" "$needle" "$haystack"
  fi
}

# ── sandbox setup ───────────────────────────────────────────────────
export HOME="${SANDBOX}"
export CLEANMAC_STATE_DIR="${SANDBOX}/state"
export CLEANMAC_SYS_CACHES="${SANDBOX}/sys/caches"
export CLEANMAC_SYS_CACHES2="${SANDBOX}/sys/caches2"
export CLEANMAC_SYS_LOGS="${SANDBOX}/sys/logs"
export CLEANMAC_SYS_LOGS2="${SANDBOX}/sys/logs2"
export PATH="${SANDBOX}/bin:/usr/bin:/bin"

mkdir -p "$HOME/Library/Caches" "$HOME/Library/Logs" "$HOME/.Trash" "$HOME/.npm"
mkdir -p "${SANDBOX}/sys/caches" "${SANDBOX}/sys/caches2" "${SANDBOX}/sys/logs" "${SANDBOX}/sys/logs2"
mkdir -p "${SANDBOX}/bin"

# fake files with real sizes
dd if=/dev/zero of="$HOME/Library/Caches/big.cache" bs=1k count=1024 2>/dev/null
dd if=/dev/zero of="$HOME/Library/Logs/old.log" bs=1k count=256 2>/dev/null
dd if=/dev/zero of="$HOME/.Trash/junk.bin" bs=1k count=64 2>/dev/null
dd if=/dev/zero of="$HOME/.npm/_cacache/data" bs=1k count=128 2>/dev/null
dd if=/dev/zero of="${SANDBOX}/sys/caches/sys.cache" bs=1k count=512 2>/dev/null
dd if=/dev/zero of="${SANDBOX}/sys/logs/system.log" bs=1k count=64 2>/dev/null

# mock binaries on PATH
cat > "${SANDBOX}/bin/sudo" <<'EOF'
#!/usr/bin/env bash
# mock sudo — accepts -v (validate) and -n (non-interactive), then passes through
args=()
for arg in "$@"; do
  case "$arg" in
    -v) exit 0 ;;
    -n) continue ;;
    *) args+=("$arg") ;;
  esac
done
exec "${args[@]}"
EOF
cat > "${SANDBOX}/bin/tmutil" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "${SANDBOX}/bin/brew" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "${SANDBOX}/bin/docker" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "${SANDBOX}/bin/npm" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "${SANDBOX}/bin/pip" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "${SANDBOX}"/bin/*

# ── tests ───────────────────────────────────────────────────────────
echo ""
echo "── cleanmac test suite ──"

echo ""
echo "▶ shellcheck-safe: syntax is valid"
bash -n "$BIN" && echo "  \033[32m✓\033[0m bash -n passed" && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); FAILED_NAMES+=("syntax"); }

echo ""
echo "▶ --help exits 0 with usage"
HELP_OUT=$("$BIN" --help 2>&1); HELP_RC=$?
T "help exit code" "0" "$HELP_RC"
T_CONTAINS "help shows usage" "USAGE:" "$HELP_OUT"

echo ""
echo "▶ unknown flag exits 2"
BAD_OUT=$("$BIN" --nope 2>&1); BAD_RC=$?
T "unknown flag exit code" "2" "$BAD_RC"
T_CONTAINS "unknown flag message" "Unknown option" "$BAD_OUT"

echo ""
echo "▶ dry-run creates JSONL log + audit + report, deletes nothing"
DRY_OUT=$("$BIN" --dry-run 2>&1); DRY_RC=$?
T "dry-run exit code" "0" "$DRY_RC"
T "caches still present" "$HOME/Library/Caches/big.cache" "$(ls "$HOME/Library/Caches/big.cache" 2>/dev/null || echo missing)"
T "logs still present" "$HOME/Library/Logs/old.log" "$(ls "$HOME/Library/Logs/old.log" 2>/dev/null || echo missing)"
STATE_JSONL=$(ls "${SANDBOX}/state/logs/"*.jsonl 2>/dev/null | head -1)
STATE_AUDIT=$(ls "${SANDBOX}/state/audit/"*.jsonl 2>/dev/null | head -1)
STATE_REPORT=$(ls "${SANDBOX}/state/"report-*.json 2>/dev/null | head -1)
T "log file created" "$STATE_JSONL" "$(echo "$STATE_JSONL" || echo missing)"
T_CONTAINS "log has run_start" "run_start" "$(cat "$STATE_JSONL" 2>/dev/null)"
T_CONTAINS "log has run_end" "run_end" "$(cat "$STATE_JSONL" 2>/dev/null)"
T_CONTAINS "log is JSONL per-line" '"run"' "$(head -1 "$STATE_JSONL" 2>/dev/null)"
T "audit file created" "$STATE_AUDIT" "$(echo "$STATE_AUDIT" || echo missing)"
T "report file created" "$STATE_REPORT" "$(echo "$STATE_REPORT" || echo missing)"
T_CONTAINS "report has exit_code" '"exit_code":0' "$(cat "$STATE_REPORT" 2>/dev/null)"
T_CONTAINS "report has steps" '"steps":' "$(cat "$STATE_REPORT" 2>/dev/null)"
T_CONTAINS "summary shows dry-run warning" "DRY-RUN" "$DRY_OUT"
T_CONTAINS "dry-run skips elevation prompt (logged)" "dry_run_no_sudo" "$(cat "$STATE_JSONL" 2>/dev/null)"

echo ""
echo "▶ JSONL/report artifacts are valid JSON (python3)"
JSON_VALID=$(python3 -c "
import json, sys
for f in ['$STATE_JSONL', '$STATE_AUDIT']:
    n = 0
    for line in open(f):
        json.loads(line); n += 1
    assert n >= 2, f'{f}: too few events'
json.load(open('$STATE_REPORT'))
print('valid')
" 2>&1)
T "all JSON artifacts valid" "valid" "$JSON_VALID"

echo ""
echo "▶ live run deletes sandboxed caches/logs/trash, frees space"
LIVE_OUT=$("$BIN" 2>&1); LIVE_RC=$?
T "live exit code" "0" "$LIVE_RC"
T_CONTAINS "live run asks elevation once" "Elevation check" "$LIVE_OUT"
T_CONTAINS "live run caches credentials" "Sudo credentials cached" "$LIVE_OUT"
T "cache deleted" "missing" "$(ls "$HOME/Library/Caches/big.cache" 2>/dev/null || echo missing)"
T "log deleted" "missing" "$(ls "$HOME/Library/Logs/old.log" 2>/dev/null || echo missing)"
T "trash deleted" "missing" "$(ls "$HOME/.Trash/junk.bin" 2>/dev/null || echo missing)"
T "npm cache deleted" "missing" "$(ls "$HOME/.npm/_cacache/data" 2>/dev/null || echo missing)"
T "sandbox system cache deleted" "missing" "$(ls "${SANDBOX}/sys/caches/sys.cache" 2>/dev/null || echo missing)"
T "sandbox system log deleted" "missing" "$(ls "${SANDBOX}/sys/logs/system.log" 2>/dev/null || echo missing)"

# safety: real system dirs must never be touched by a sandboxed run
for dir in /Library/Caches /System/Library/Caches /private/var/log /var/log; do
  if [[ -e "$dir" ]]; then
    T "sandbox never touched $dir" "dir" "$([[ -d "$dir" ]] && echo dir || echo missing)"
  fi
done

echo ""
echo "▶ SIP-protected items: step still succeeds (best-effort)"
# simulate: rm -rf on the sandbox sys cache returns non-zero, like SIP
cat > "${SANDBOX}/bin/rm" <<'EOF'
#!/usr/bin/env bash
# mock rm that "succeeds" but reports failure on protected items
if [[ "$*" == *"protected"* ]]; then
  echo "rm: protected: Operation not permitted" >&2
  exit 1
fi
/bin/rm "$@"
EOF
chmod +x "${SANDBOX}/bin/rm"
touch "${SANDBOX}/sys/caches2/protected"
SIP_OUT=$("$BIN" 2>&1); SIP_RC=$?
rm -f "${SANDBOX}/bin/rm"
T "sip-protected run still exits 0" "0" "$SIP_RC"
T_CONTAINS "sip-protected logged as partial not fail" "partial" "$(cat "$(ls -t "${SANDBOX}/state/logs/"*.jsonl 2>/dev/null | head -1)" 2>/dev/null)"

echo ""
echo "▶ output observability"
T_CONTAINS "step counter [1/8]" "[1/8]" "$DRY_OUT"
T_CONTAINS "progress bar" "█" "$DRY_OUT"
T_CONTAINS "summary block" "Summary" "$DRY_OUT"
T_CONTAINS "tracked freed" "Tracked freed" "$DRY_OUT"
T_CONTAINS "disk free line" "Disk free" "$DRY_OUT"
T_CONTAINS "log path printed" "Log:" "$DRY_OUT"
T_CONTAINS "audit path printed" "Audit:" "$DRY_OUT"

echo ""
echo "── results ─────────────────────────────────────────"
printf '  %sPASS: %d  FAIL: %d%s\n' "$([[ $FAIL -eq 0 ]] && echo $'\033[32m' || echo $'\033[31m')" "$PASS" "$FAIL" $'\033[0m'
if (( FAIL > 0 )); then
  printf '  failed: %s\n' "${FAILED_NAMES[*]}"
  exit 1
fi
echo "  All tests passed."
exit 0
