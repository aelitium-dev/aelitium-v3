#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: offline_verify.sh <release_output_dir | bundle.zip>"
  exit 2
fi

SRC="$1"
WORK=""
cleanup() { [[ -n "${WORK:-}" && -d "$WORK" ]] && rm -rf "$WORK"; }
trap cleanup EXIT

if [[ -d "$SRC" ]]; then
  WORK="$SRC"
elif [[ -f "$SRC" ]]; then
  WORK="$(mktemp -d)"
  case "$SRC" in
    *.zip)
      python3 - <<PY
import zipfile, sys
zf = zipfile.ZipFile(sys.argv[1])
zf.extractall(sys.argv[2])
print("EXTRACT=OK")
PY
      "$SRC" "$WORK"
      ;;
    *)
      echo "VERIFY_STATUS=NO_GO reason=UNSUPPORTED_BUNDLE_FORMAT path=$SRC"
      exit 2
      ;;
  esac
else
  echo "VERIFY_STATUS=NO_GO reason=NOT_FOUND path=$SRC"
  exit 2
fi

MANIFEST="$WORK/manifest.json"
EVIDENCE="$WORK/evidence_pack.json"
VK="$WORK/verification_keys.json"

for f in "$MANIFEST" "$EVIDENCE" "$VK"; do
  if [[ ! -f "$f" ]]; then
    echo "VERIFY_STATUS=NO_GO reason=MISSING_FILE file=$f"
    exit 2
  fi
done

# hashes for audit (offline)
echo "MANIFEST_SHA256=$(sha256sum "$MANIFEST" | awk "{print \$1}")"
echo "EVIDENCE_SHA256=$(sha256sum "$EVIDENCE" | awk "{print \$1}")"
echo "VK_SHA256=$(sha256sum "$VK" | awk "{print \$1}")"

# deterministic verify (fail-closed)
python3 engine/cli.py verify \
  --manifest "$MANIFEST" \
  --evidence "$EVIDENCE"

echo "VERIFY_STATUS=GO"
