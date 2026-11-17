#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if ! command -v aelitium >/dev/null 2>&1; then
  printf '%s\n' \
    "ERROR: aelitium is not on PATH. Install and activate the public aelitium==0.4.0 distribution first." \
    >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  printf '%s\n' \
    "ERROR: python is not on PATH. Activate the environment containing aelitium==0.4.0." \
    >&2
  exit 1
fi

PYTHON_BIN="$(command -v python)"
CLI_PATH="$("$PYTHON_BIN" -c 'import os, shutil; print(os.path.realpath(shutil.which("aelitium")))')"
ACTIVE_PYTHON_PATH="$("$PYTHON_BIN" -c 'import os, sys; print(os.path.abspath(sys.executable))')"

if [[ "$(dirname "$CLI_PATH")" != "$(dirname "$ACTIVE_PYTHON_PATH")" ]]; then
  printf 'ERROR: aelitium (%s) and active Python (%s) are from different environments.\n' \
    "$CLI_PATH" "$ACTIVE_PYTHON_PATH" >&2
  exit 1
fi

if ! PACKAGE_VERSION="$(
  "$PYTHON_BIN" -c \
    'from importlib.metadata import version; print(version("aelitium"))' \
    2>/dev/null
)"; then
  printf '%s\n' \
    "ERROR: the active Python environment has no installed aelitium distribution metadata." \
    >&2
  exit 1
fi

if [[ "$PACKAGE_VERSION" != "0.4.0" ]]; then
  printf 'ERROR: %s reports aelitium distribution version %q; expected exactly 0.4.0.\n' \
    "$CLI_PATH" "$PACKAGE_VERSION" >&2
  exit 1
fi

CLI=("$CLI_PATH")

BUNDLE_A="$REPO_ROOT/examples/drift_demo/bundle_a"
BUNDLE_B="$REPO_ROOT/examples/drift_demo/bundle_b"
INVOCATION_A="$REPO_ROOT/tests/fixtures/compare/v030_invocation_a"
INVOCATION_B="$REPO_ROOT/tests/fixtures/compare/v030_invocation_b"
TEMP_ROOT=""
LAST_OUTPUT=""
LAST_RC=0

cleanup() {
  if [[ -n "$TEMP_ROOT" && -d "$TEMP_ROOT" ]]; then
    rm -rf -- "$TEMP_ROOT"
  fi
}
trap cleanup EXIT

section() {
  printf '\n========== %s ==========\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

run_expect_rc() {
  local expected_rc="$1"
  shift

  printf '$'
  printf ' %q' "${CLI[@]}" "$@"
  printf '\n'

  set +e
  LAST_OUTPUT="$("${CLI[@]}" "$@" 2>&1)"
  LAST_RC=$?
  set -e

  printf '%s\n' "$LAST_OUTPUT"
  if [[ "$LAST_RC" -ne "$expected_rc" ]]; then
    fail "expected rc=$expected_rc, observed rc=$LAST_RC"
  fi
}

expect_line() {
  local expected_line="$1"
  if ! grep -Fqx -- "$expected_line" <<<"$LAST_OUTPUT"; then
    fail "expected output line not found: $expected_line"
  fi
}

section "Installed public CLI under test"
printf 'AELITIUM_EXECUTABLE=%s\n' "$CLI_PATH"
printf 'AELITIUM_PACKAGE_VERSION=%s\n' "$PACKAGE_VERSION"
printf 'PYTHON_EXECUTABLE=%s\n' "$ACTIVE_PYTHON_PATH"

section "Known-valid frozen bundle"
run_expect_rc 0 verify-bundle "$BUNDLE_A"
expect_line "STATUS=VALID rc=0"
expect_line "PAYLOAD_INTEGRITY=VALID"
expect_line "BINDING_FIELD_CONSISTENCY=VALID"

section "Identical evidence is UNCHANGED"
run_expect_rc 0 compare "$BUNDLE_A" "$BUNDLE_A"
expect_line "STATUS=UNCHANGED rc=0"
expect_line "COMPARISON_CONTRACT=aelitium-compare-v1"
expect_line "COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK"
expect_line "COMPARISON_REASON=RESPONSE_HASH_SAME"

section "Frozen changed evidence is CHANGED"
run_expect_rc 2 compare "$BUNDLE_A" "$BUNDLE_B"
expect_line "STATUS=CHANGED rc=2"
expect_line "COMPARISON_CONTRACT=aelitium-compare-v1"
expect_line "COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK"
expect_line "COMPARISON_REASON=RESPONSE_HASH_DIFFERENT"

section "Strict invocation mode rejects unavailable evidence"
run_expect_rc 1 compare "$BUNDLE_A" "$BUNDLE_A" --require-invocation-evidence
expect_line "STATUS=NOT_COMPARABLE rc=1"
expect_line "COMPARISON_MODE=STRICT_INVOCATION"
expect_line "COMPARISON_BASIS=NONE"
expect_line "COMPARISON_REASON=INVOCATION_EVIDENCE_UNAVAILABLE"
expect_line "REQUIRED_COMPARISON_BASIS=INVOCATION_IDENTITY_V1"

section "Valid invocation evidence selects INVOCATION_IDENTITY_V1"
run_expect_rc 2 compare "$INVOCATION_A" "$INVOCATION_B"
expect_line "STATUS=CHANGED rc=2"
expect_line "COMPARISON_CONTRACT=aelitium-compare-v1"
expect_line "COMPARISON_BASIS=INVOCATION_IDENTITY_V1"
expect_line "COMPARISON_REASON=RESPONSE_HASH_DIFFERENT"
expect_line "INVOCATION_IDENTITY_CONSISTENCY_A=VALID"
expect_line "INVOCATION_BINDING_CONSISTENCY_A=VALID"
expect_line "INVOCATION_IDENTITY_CONSISTENCY_B=VALID"
expect_line "INVOCATION_BINDING_CONSISTENCY_B=VALID"

section "Tampered temporary copy is INVALID"
TEMP_ROOT="$(mktemp -d)"
TAMPERED_BUNDLE="$TEMP_ROOT/tampered"
cp -R "$BUNDLE_A" "$TAMPERED_BUNDLE"
"$PYTHON_BIN" - "$TAMPERED_BUNDLE/ai_canonical.json" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
original = path.read_text(encoding="utf-8")
changed = original.replace('"output":"The sky', '"output":"Tampered: the sky', 1)
if changed == original:
    raise SystemExit("expected fixture text not found")
path.write_text(changed, encoding="utf-8")
PY
run_expect_rc 2 verify-bundle "$TAMPERED_BUNDLE"
expect_line "STATUS=INVALID rc=2 reason=HASH_MISMATCH"

section "External validation result"
printf '%s\n' "PASS: all expected AELITIUM v0.4.0 offline results were observed."
