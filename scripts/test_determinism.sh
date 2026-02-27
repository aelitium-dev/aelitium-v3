#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: test_determinism.sh <input.json>"
  exit 2
fi

INPUT="$1"
if [[ ! -f "$INPUT" ]]; then
  echo "DETERMINISM_STATUS=FAIL reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

OUT1="$TMP/run1"
OUT2="$TMP/run2"
mkdir -p "$OUT1" "$OUT2"

python3 engine/cli.py pack --input "$INPUT" --out "$OUT1"
python3 engine/cli.py pack --input "$INPUT" --out "$OUT2"
python3 engine/cli.py verify --manifest "$OUT1/manifest.json" --evidence "$OUT1/evidence_pack.json" >/dev/null
python3 engine/cli.py verify --manifest "$OUT2/manifest.json" --evidence "$OUT2/evidence_pack.json" >/dev/null

hash_bundle() {
  local dir="$1"
  (cd "$dir" && sha256sum manifest.json evidence_pack.json verification_keys.json | awk '{print $1}' | sha256sum | awk '{print $1}')
}

RUN1_HASH="$(hash_bundle "$OUT1")"
RUN2_HASH="$(hash_bundle "$OUT2")"

if [[ "$RUN1_HASH" != "$RUN2_HASH" ]]; then
  echo "DETERMINISM_STATUS=FAIL reason=HASH_MISMATCH"
  echo "BUNDLE_SHA_RUN1=$RUN1_HASH"
  echo "BUNDLE_SHA_RUN2=$RUN2_HASH"
  exit 2
fi

echo "DETERMINISM_STATUS=PASS"
echo "BUNDLE_SHA_RUN1=$RUN1_HASH"
echo "BUNDLE_SHA_RUN2=$RUN2_HASH"
