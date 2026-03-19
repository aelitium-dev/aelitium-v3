#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEST_KEY_PATH="tests/fixtures/ed25519_test_private_key.b64"

section() {
  printf '\n== %s ==\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    fail "$label (missing: $needle)"
  fi
}

run_capture() {
  local __var_name="$1"
  shift
  local output
  if ! output="$("$@" 2>&1)"; then
    printf '%s\n' "$output"
    fail "command failed: $*"
  fi
  printf '%s\n' "$output"
  printf -v "$__var_name" '%s' "$output"
}

run_expect_rc() {
  local __var_name="$1"
  local expected_rc="$2"
  shift 2
  local output
  local rc=0
  set +e
  output="$("$@" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$output"
  if [[ "$rc" -ne "$expected_rc" ]]; then
    fail "expected rc=$expected_rc, got rc=$rc for: $*"
  fi
  printf -v "$__var_name" '%s' "$output"
}

make_valid_receipt() {
  local tmpdir="$1"
  export AEL_ED25519_PRIVKEY_B64
  export TMPDIR="$tmpdir"
  python3 - <<'PY'
import json
import os
from pathlib import Path
from p3.server.signing import authority_public_key_b64, sign_receipt

tmp = Path(os.environ["TMPDIR"])
receipt = sign_receipt(subject_hash="b" * 64, subject_type="ai_output_v1")
(tmp / "receipt.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
(tmp / "pubkey.b64").write_text(authority_public_key_b64(), encoding="utf-8")
PY
}

make_invalid_receipt() {
  local tmpdir="$1"
  export AEL_ED25519_PRIVKEY_B64
  export TMPDIR="$tmpdir"
  python3 - <<'PY'
import json
import os
from pathlib import Path
from p3.server.signing import authority_public_key_b64, sign_receipt

tmp = Path(os.environ["TMPDIR"])
receipt = sign_receipt(subject_hash="b" * 64, subject_type="ai_output_v1")
receipt["subject_hash_sha256"] = "c" * 64
(tmp / "receipt.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
(tmp / "pubkey.b64").write_text(authority_public_key_b64(), encoding="utf-8")
PY
}

if [[ ! -f "$TEST_KEY_PATH" ]]; then
  fail "missing test key fixture: $TEST_KEY_PATH"
fi

AEL_ED25519_PRIVKEY_B64="$(tr -d '\n' < "$TEST_KEY_PATH")"
export AEL_ED25519_PRIVKEY_B64

section "Test 1 - Same input, same binding hash"
run_capture out1 python3 -m unittest tests.test_capture_litellm.TestCaptureLiteLLM.test_binding_hash_deterministic -v
assert_contains "$out1" "OK" "deterministic binding-hash unit test"

section "Test 2 - Tamper => INVALID"
tmp2="$(mktemp -d)"
trap 'rm -rf "${tmp2:-}" "${tmp5:-}" "${tmp6:-}"' EXIT
cp -R examples/drift_demo/bundle_a "$tmp2/bundle"
run_capture out2a python3 -m engine.ai_cli verify-bundle "$tmp2/bundle"
assert_contains "$out2a" "STATUS=VALID rc=0" "pre-tamper verify-bundle"
sed -i 's/sky is blue/SKY IS BLUE/' "$tmp2/bundle/ai_canonical.json"
run_expect_rc out2b 2 python3 -m engine.ai_cli verify-bundle "$tmp2/bundle"
assert_contains "$out2b" "STATUS=INVALID rc=2" "post-tamper invalid status"
assert_contains "$out2b" "reason=HASH_MISMATCH" "post-tamper hash mismatch"

section "Test 3 - Offline verify-bundle"
run_capture out3 python3 -m engine.ai_cli verify-bundle examples/drift_demo/bundle_a
assert_contains "$out3" "STATUS=VALID rc=0" "offline verify-bundle status"
assert_contains "$out3" "AI_HASH_SHA256=" "offline verify-bundle hash"
assert_contains "$out3" "BINDING_HASH=" "offline verify-bundle binding hash"

section "Test 4 - Compare => UNCHANGED / CHANGED"
run_capture out4a python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a
assert_contains "$out4a" "STATUS=UNCHANGED rc=0" "compare unchanged status"
assert_contains "$out4a" "REQUEST_HASH=SAME" "compare unchanged request hash"
assert_contains "$out4a" "RESPONSE_HASH=SAME" "compare unchanged response hash"
run_expect_rc out4b 2 python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_b
assert_contains "$out4b" "STATUS=CHANGED rc=2" "compare changed status"
assert_contains "$out4b" "REQUEST_HASH=SAME" "compare changed request hash"
assert_contains "$out4b" "RESPONSE_HASH=DIFFERENT" "compare changed response hash"

section "Test 5 - Receipt verification (valid)"
tmp5="$(mktemp -d)"
make_valid_receipt "$tmp5"
run_capture out5 python3 -m engine.ai_cli verify-receipt \
  --receipt "$tmp5/receipt.json" \
  --pubkey "$tmp5/pubkey.b64" \
  --hash "$(python3 - <<'PY'
print('b' * 64)
PY
)"
assert_contains "$out5" "STATUS=VALID rc=0" "valid receipt status"
assert_contains "$out5" "SUBJECT_HASH_SHA256=" "valid receipt subject hash"
assert_contains "$out5" "RECEIPT_ID=" "valid receipt id"

section "Test 6 - Receipt verification => INVALID signature"
tmp6="$(mktemp -d)"
make_invalid_receipt "$tmp6"
run_expect_rc out6 2 python3 -m engine.ai_cli verify-receipt \
  --receipt "$tmp6/receipt.json" \
  --pubkey "$tmp6/pubkey.b64" \
  --hash "$(python3 - <<'PY'
print('c' * 64)
PY
)"
assert_contains "$out6" "STATUS=INVALID rc=2" "invalid receipt status"
assert_contains "$out6" "reason=SIGNATURE_INVALID" "invalid receipt signature failure"

printf '\n[PASS] TEST_MATRIX flows completed successfully\n'
