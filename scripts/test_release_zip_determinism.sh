#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./use_test_signing_key.sh
source "$ROOT/scripts/use_test_signing_key.sh"
INPUT="${1:-$ROOT/tests/fixtures/input_min.json}"
TMP=""

if [[ ! -f "$INPUT" ]]; then
  echo "ZIP_TEST_STATUS=FAIL reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

cleanup() {
  local target="${TMP:-}"
  if [[ -n "$target" && -d "$target" ]]; then
    rm -rf -- "$target"
  fi
}
trap cleanup EXIT

fail() {
  echo "$1"
  exit 2
}

TMP="$(mktemp -d)"
PAYLOAD_DIR="$TMP/payload"
OUT1="$TMP/dist1"
OUT2="$TMP/dist2"

python3 "$ROOT/engine/cli.py" pack --input "$INPUT" --out "$PAYLOAD_DIR"

if ! AEL_ZIP_PAYLOAD_DIR="$PAYLOAD_DIR" AEL_ZIP_OUTDIR="$OUT1" "$ROOT/scripts/make_release_zip.sh" >/dev/null; then
  fail "ZIP_BUILD=FAIL run=1"
fi

if ! AEL_ZIP_PAYLOAD_DIR="$PAYLOAD_DIR" AEL_ZIP_OUTDIR="$OUT2" "$ROOT/scripts/make_release_zip.sh" >/dev/null; then
  fail "ZIP_BUILD=FAIL run=2"
fi

ZIP1="$OUT1/release_output.zip"
ZIP2="$OUT2/release_output.zip"
META1="$OUT1/release_metadata.json"

SHA1="$(sha256sum "$ZIP1" | awk '{print $1}')"
SHA2="$(sha256sum "$ZIP2" | awk '{print $1}')"

if [[ "$SHA1" != "$SHA2" ]]; then
  fail "ZIP_DETERMINISM=FAIL sha1=$SHA1 sha2=$SHA2"
fi
echo "ZIP_DETERMINISM=PASS"
echo "ZIP_SHA256=$SHA1"

if ! "$ROOT/scripts/verify_release_zip.sh" "$ZIP1" "$META1" >/dev/null; then
  fail "ZIP_VERIFY=FAIL"
fi
echo "ZIP_VERIFY=PASS"
echo "ZIP_TEST_STATUS=PASS"
