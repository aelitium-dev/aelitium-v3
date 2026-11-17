#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./use_test_signing_key.sh
source "$ROOT/scripts/use_test_signing_key.sh"
INPUT="${1:-$ROOT/tests/fixtures/input_min.json}"
TMP=""

if [[ ! -f "$INPUT" ]]; then
  echo "FLOW_STATUS=FAIL reason=INPUT_MISSING input=$INPUT"
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

snapshot_dir() {
  local dir="$1"
  (
    cd "$dir"
    while IFS= read -r file; do
      sha256sum "$file"
    done < <(find . -type f -print | LC_ALL=C sort)
  )
}

TMP="$(mktemp -d)"
BUNDLE_DIR="$TMP/bundle"
ZIP_PATH="$TMP/bundle.zip"
TAMPER_ZIP="$TMP/tampered.zip"

if ! "$ROOT/scripts/test_determinism.sh" "$INPUT" >/dev/null; then
  fail "DETERMINISM=FAIL"
fi
echo "DETERMINISM=PASS"

python3 "$ROOT/engine/cli.py" pack --input "$INPUT" --out "$BUNDLE_DIR"

DIR_BEFORE="$(snapshot_dir "$BUNDLE_DIR")"
if ! "$ROOT/scripts/offline_verify.sh" "$BUNDLE_DIR" >/dev/null; then
  fail "DIR_VERIFY=FAIL"
fi
DIR_AFTER="$(snapshot_dir "$BUNDLE_DIR")"
if [[ "$DIR_BEFORE" != "$DIR_AFTER" ]]; then
  fail "DIR_VERIFY=FAIL reason=INPUT_MUTATED"
fi
echo "DIR_VERIFY=PASS"

python3 - "$BUNDLE_DIR" "$ZIP_PATH" <<'PY'
import sys
import zipfile
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

with zipfile.ZipFile(dst, "w") as zf:
    for path in sorted(p for p in src.iterdir() if p.is_file()):
        zf.write(path, arcname=path.name)
PY

if ! "$ROOT/scripts/offline_verify.sh" "$ZIP_PATH" >/dev/null; then
  fail "ZIP_VERIFY=FAIL"
fi
echo "ZIP_VERIFY=PASS"

cp -a "$ZIP_PATH" "$TAMPER_ZIP"
python3 - "$TAMPER_ZIP" <<'PY'
import json
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
tmp_path = zip_path.with_suffix(".tmp.zip")

with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():
        data = zin.read(info.filename)
        if info.filename == "evidence_pack.json":
            obj = json.loads(data.decode("utf-8"))
            obj["hash"] = "f" * 64
            data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        zout.writestr(info, data)

tmp_path.replace(zip_path)
PY

if "$ROOT/scripts/offline_verify.sh" "$TAMPER_ZIP" >/dev/null 2>&1; then
  fail "TAMPER=FAIL"
fi
echo "TAMPER=PASS"
echo "FLOW_STATUS=PASS"
