#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

TAG="v9.9.9-rc1"
INPUT="$ROOT/inputs/minimal_input_v1.json"
GIT_LOG="$TMP/git_calls.log"
STUB_BIN="$TMP/stub_bin"
mkdir -p "$STUB_BIN"

cat > "$STUB_BIN/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "${GIT_STUB_LOG:?}"
if [[ "${1:-}" == "status" ]]; then
  echo " M selftest"
fi
exit 0
EOF
chmod +x "$STUB_BIN/git"

# Case 1: invalid evidence must fail before any git call
INVALID_LOG="$TMP/invalid_evidence.md"
printf '# empty log\n' > "$INVALID_LOG"

set +e
OUT1="$(
  cd "$ROOT" && \
  PATH="$STUB_BIN:$PATH" GIT_STUB_LOG="$GIT_LOG" \
  AEL_EVIDENCE_LOG_PATH="$INVALID_LOG" \
  ./scripts/gate_release.sh "$TAG" "$INPUT" 2>&1
)"
RC1=$?
set -e

if [[ "$RC1" -ne 2 ]]; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=INVALID_LOG_RC rc=$RC1"
  exit 2
fi
if ! grep -q 'reason=EVIDENCE_INVALID' <<<"$OUT1"; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=INVALID_LOG_REASON"
  exit 2
fi
if [[ -s "$GIT_LOG" ]]; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=GIT_CALLED_BEFORE_EVIDENCE_CHECK"
  exit 2
fi

# Case 2: valid evidence must pass barrier and reach git checks
VALID_LOG="$TMP/valid_evidence.md"
cat > "$VALID_LOG" <<'EOF'
## EVIDENCE_ENTRY v1 | tag=v9.9.9-rc1
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v9.9.9-rc1",
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

: > "$GIT_LOG"
set +e
OUT2="$(
  cd "$ROOT" && \
  PATH="$STUB_BIN:$PATH" GIT_STUB_LOG="$GIT_LOG" \
  AEL_EVIDENCE_LOG_PATH="$VALID_LOG" \
  ./scripts/gate_release.sh "$TAG" "$INPUT" 2>&1
)"
RC2=$?
set -e

if [[ "$RC2" -ne 2 ]]; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=VALID_LOG_EXPECTED_DIRTY_TREE rc=$RC2"
  exit 2
fi
if ! grep -q 'reason=DIRTY_GIT_TREE' <<<"$OUT2"; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=VALID_LOG_DID_NOT_REACH_GIT_CHECK"
  exit 2
fi
if ! grep -q '^status --porcelain=v1$' "$GIT_LOG"; then
  echo "SELFTEST_GATE_EVIDENCE=FAIL reason=GIT_STATUS_NOT_CALLED"
  exit 2
fi

echo "SELFTEST_GATE_EVIDENCE=PASS"
