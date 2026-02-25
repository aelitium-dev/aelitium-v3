#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export TZ=UTC

ZIP="${1:-dist/release_output.zip}"
META="${2:-dist/release_metadata.json}"

test -f "$ZIP"
test -f "$META"

expected="$(python3 - <<PY
import json
with open("$META","r",encoding="utf-8") as f:
  print(json.load(f)["zip_sha256"])
PY
)"
actual="$(sha256sum "$ZIP" | awk '{print $1}')"

if [[ "$expected" != "$actual" ]]; then
  echo "VERIFY_ZIP_STATUS=NO_GO reason=SHA_MISMATCH expected=$expected actual=$actual"
  exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

python3 - <<PY
import zipfile
with zipfile.ZipFile("$ZIP","r") as z:
  z.extractall("$tmp")
print("EXTRACT=OK")
PY

bash "$tmp/offline_verifier/offline_verify.sh" "$tmp/payload"
echo "VERIFY_ZIP_STATUS=GO"
