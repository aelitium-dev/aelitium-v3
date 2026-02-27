#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTH="$ROOT/scripts/authority_status.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
OUT_GO="$TMP/out_go.txt"
OUT_MISMATCH="$TMP/out_mismatch.txt"
OUT_SHORT_REMOTE="$TMP/out_short_remote.txt"
mkdir -p "$BIN"

FULL_SHA="11460945dd86193667560c24190f5b895a8a4593"
SHORT_SHA="1146094"
MACHINE_ID_REAL="6cf43cdaa0784741ae3e87878fe7e009"
MACHINE_ID_REAL_SHA="75a1d1565ace872283ab28f54fb063c64ada1e787f1226d72685efd55b3ab01b"

cat > "$BIN/git" <<'EOF_GIT'
#!/usr/bin/env bash
set -euo pipefail
FULL_SHA="11460945dd86193667560c24190f5b895a8a4593"
SHORT_SHA="1146094"
MODE="${SELFTEST_GIT_MODE:-normal}"

if [[ "${1:-}" == "rev-parse" && "${2:-}" == "HEAD" ]]; then
  echo "$FULL_SHA"
  exit 0
fi
if [[ "${1:-}" == "status" && "${2:-}" == "--porcelain=v1" ]]; then
  exit 0
fi
if [[ "${1:-}" == "ls-remote" ]]; then
  if [[ "$MODE" == "short_remote" ]]; then
    echo "$SHORT_SHA	refs/heads/main"
  else
    echo "$FULL_SHA	refs/heads/main"
  fi
  exit 0
fi

echo "unexpected git invocation: $*" >&2
exit 99
EOF_GIT
chmod +x "$BIN/git"

run_auth() {
  local machine_id_file="$1"
  local out_file="$2"
  local git_mode="${3:-normal}"
  set +e
  (
    cd "$ROOT"
    PATH="$BIN:$PATH" \
    AEL_MACHINE="A" \
    AEL_MACHINE_ID_PATH="$machine_id_file" \
    AEL_AUTHORITY_IDENTITY_PATH="$TMP/machine_b.identity.json" \
    SELFTEST_GIT_MODE="$git_mode" \
    "$AUTH"
  ) >"$out_file" 2>&1
  RUN_RC=$?
  set -e
}

cat > "$TMP/machine_b.identity.json" <<EOF_ID
{
  "schema": "aelitium_authority_identity_v1",
  "machine_role": "B",
  "machine_id_sha256": "$MACHINE_ID_REAL_SHA"
}
EOF_ID

echo -n "$MACHINE_ID_REAL" > "$TMP/machine-id-ok"
echo -n "deadbeefdeadbeefdeadbeefdeadbeef" > "$TMP/machine-id-bad"

# Case 1: AEL_MACHINE spoofed as A should still pass if identity hash matches.
run_auth "$TMP/machine-id-ok" "$OUT_GO" "normal"
if [[ "${RUN_RC:-}" -ne 0 ]]; then
  echo "SELFTEST=FAIL reason=EXPECTED_GO rc=${RUN_RC:-NA}"
  exit 2
fi
if ! grep -q "AUTHORITY_STATUS=GO" "$OUT_GO"; then
  echo "SELFTEST=FAIL reason=MISSING_GO_STATUS"
  exit 2
fi

# Case 2: machine-id mismatch must fail-closed.
run_auth "$TMP/machine-id-bad" "$OUT_MISMATCH" "normal"
if [[ "${RUN_RC:-}" -ne 2 ]]; then
  echo "SELFTEST=FAIL reason=EXPECTED_MISMATCH_FAIL rc=${RUN_RC:-NA}"
  exit 2
fi
if ! grep -q "reason=MACHINE_ID_HASH_MISMATCH" "$OUT_MISMATCH"; then
  echo "SELFTEST=FAIL reason=MISSING_MACHINE_ID_MISMATCH_REASON"
  exit 2
fi

# Case 3: truncated remote SHA must fail.
run_auth "$TMP/machine-id-ok" "$OUT_SHORT_REMOTE" "short_remote"
if [[ "${RUN_RC:-}" -ne 2 ]]; then
  echo "SELFTEST=FAIL reason=EXPECTED_SHORT_REMOTE_FAIL rc=${RUN_RC:-NA}"
  exit 2
fi
if ! grep -q "reason=INVALID_REMOTE_MAIN_SHA" "$OUT_SHORT_REMOTE"; then
  echo "SELFTEST=FAIL reason=MISSING_INVALID_REMOTE_SHA_REASON"
  exit 2
fi

echo "SELFTEST=PASS"
