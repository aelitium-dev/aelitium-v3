#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

STUB_BIN="$TMP/stub_bin"
GIT_LOG="$TMP/git_calls.log"
PY_LOG="$TMP/python_calls.log"
EVIDENCE_LOG_FIXTURE="$TMP/EVIDENCE_LOG.md"
mkdir -p "$STUB_BIN"

cat > "$STUB_BIN/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "${SELFTEST_GIT_LOG:?}"

MODE="${SELFTEST_MODE:-default}"
FAKE_SHA="${SELFTEST_FAKE_SHA:-505c2562bd1559e0a7b23f56c47945ed6fd6f502}"

cmd="${1:-}"
shift || true

case "$cmd" in
  status)
    if [[ "$MODE" == "dirty" ]]; then
      echo " M selftest"
    fi
    exit 0
    ;;
  fetch)
    exit 0
    ;;
  rev-parse)
    if [[ "${1:-}" == "HEAD" ]]; then
      echo "$FAKE_SHA"
      exit 0
    fi
    if [[ "${1:-}" == "origin/main" ]]; then
      echo "$FAKE_SHA"
      exit 0
    fi
    if [[ "${1:-}" == "-q" && "${2:-}" == "--verify" && "${3:-}" == refs/tags/* ]]; then
      if [[ "$MODE" == "tag_exists" ]]; then
        echo "$FAKE_SHA"
        exit 0
      fi
      exit 1
    fi
    echo "$FAKE_SHA"
    exit 0
    ;;
  ls-remote)
    exit 0
    ;;
  config)
    exit 0
    ;;
  tag)
    if [[ "${1:-}" == "-v" ]]; then
      echo 'Good "git" signature for aelitium-release@machine-b with ED25519 key SHA256:TESTSIGNERFPR'
    fi
    exit 0
    ;;
  push)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
EOF
chmod +x "$STUB_BIN/git"

cat > "$STUB_BIN/ssh-add" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-l" ]]; then
  exit 0
fi
exit 0
EOF
chmod +x "$STUB_BIN/ssh-add"

cat > "$STUB_BIN/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "${SELFTEST_PY_LOG:?}"
if [[ "${1:-}" == "scripts/validate_evidence_log.py" ]]; then
  exit "${SELFTEST_PY_RC:-0}"
fi
exec /usr/bin/python3 "$@"
EOF
chmod +x "$STUB_BIN/python3"

cat > "$EVIDENCE_LOG_FIXTURE" <<'EOF'
## EVIDENCE_ENTRY v1 | tag=v0.1.2-rc1
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v0.1.2-rc1",
  "ts_utc": "2026-02-27T19:00:00Z",
  "input_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "manifest_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evidence_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verification_keys_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "bundle_sha_run1": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "bundle_sha_run2": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "A",
  "machine_id": "A|selftest|machine-id",
  "sync_mode": "remote",
  "bundle_sha256": null
}
```
EOF

run_case_expect_fail() {
  local mode="$1"
  local tag="$2"
  local reason="$3"
  local py_rc="${4:-0}"
  local out rc
  : > "$GIT_LOG"
  : > "$PY_LOG"

  set +e
  out="$(
    cd "$ROOT" && \
    PATH="$STUB_BIN:$PATH" \
    SELFTEST_MODE="$mode" \
    SELFTEST_GIT_LOG="$GIT_LOG" \
    SELFTEST_PY_LOG="$PY_LOG" \
    SELFTEST_PY_RC="$py_rc" \
    AEL_EVIDENCE_LOG_PATH="$EVIDENCE_LOG_FIXTURE" \
    ./scripts/sign_tag_b.sh "$tag" 2>&1
  )"
  rc=$?
  set -e

  if [[ "$rc" -ne 2 ]]; then
    echo "SELFTEST_SIGN_TAG_B=FAIL reason=EXPECTED_FAIL_RC mode=$mode rc=$rc"
    echo "$out"
    exit 2
  fi
  if ! grep -q "reason=$reason" <<<"$out"; then
    echo "SELFTEST_SIGN_TAG_B=FAIL reason=EXPECTED_FAIL_REASON mode=$mode want=$reason"
    echo "$out"
    exit 2
  fi
}

run_case_expect_fail "dirty" "v9.9.8-rc1" "DIRTY_GIT_TREE"
run_case_expect_fail "tag_exists" "v9.9.8-rc2" "TAG_ALREADY_EXISTS_LOCAL"
run_case_expect_fail "default" "v9.9.8-rc3" "EVIDENCE_INVALID" "2"
if ! grep -q '^scripts/validate_evidence_log.py ' "$PY_LOG"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=VALIDATOR_NOT_CALLED_ON_EVIDENCE_FAIL"
  cat "$PY_LOG"
  exit 2
fi

# Happy-path dry-run with stubs: verify script requires validator call and tag -v before GO.
: > "$GIT_LOG"
: > "$PY_LOG"
OUT_OK="$(
  cd "$ROOT" && \
  PATH="$STUB_BIN:$PATH" \
  SELFTEST_MODE="default" \
  SELFTEST_GIT_LOG="$GIT_LOG" \
  SELFTEST_PY_LOG="$PY_LOG" \
  SELFTEST_PY_RC="0" \
  AEL_EVIDENCE_LOG_PATH="$EVIDENCE_LOG_FIXTURE" \
  ./scripts/sign_tag_b.sh "v0.1.2-rc1" 2>&1
)"

if ! grep -q '^SIGN_STATUS=GO tag=v0.1.2-rc1$' <<<"$OUT_OK"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=GO_NOT_REACHED"
  echo "$OUT_OK"
  exit 2
fi
if ! grep -q '^scripts/validate_evidence_log.py ' "$PY_LOG"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=VALIDATOR_NOT_CALLED_ON_GO_PATH"
  cat "$PY_LOG"
  exit 2
fi
if ! grep -q '^tag -v v0.1.2-rc1$' "$GIT_LOG"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=TAG_VERIFY_NOT_CALLED"
  cat "$GIT_LOG"
  exit 2
fi
if ! grep -q '^add '"$EVIDENCE_LOG_FIXTURE"'$' "$GIT_LOG"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=ATTESTATION_NOT_STAGED"
  cat "$GIT_LOG"
  exit 2
fi
if ! grep -q '"machine_role": "B"' "$EVIDENCE_LOG_FIXTURE"; then
  echo "SELFTEST_SIGN_TAG_B=FAIL reason=B_ATTESTATION_NOT_WRITTEN"
  cat "$EVIDENCE_LOG_FIXTURE"
  exit 2
fi

echo "SELFTEST_SIGN_TAG_B=PASS"
