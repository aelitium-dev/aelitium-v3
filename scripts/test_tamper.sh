#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: test_tamper.sh <input.json>"
  exit 2
fi

INPUT="$1"
if [[ ! -f "$INPUT" ]]; then
  echo "TAMPER_STATUS=FAIL reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

OUT="$TMP/out"
mkdir -p "$OUT"

python3 engine/cli.py pack --input "$INPUT" --out "$OUT"

cp "$OUT/evidence_pack.json" "$OUT/evidence_pack.tampered.json"

python3 - "$OUT/evidence_pack.tampered.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
obj = json.loads(path.read_text(encoding="utf-8"))
obj["hash"] = ("f" * 64)
path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
PY

set +e
python3 engine/cli.py verify --manifest "$OUT/manifest.json" --evidence "$OUT/evidence_pack.tampered.json" >/dev/null 2>&1
RC=$?
set -e

if [[ "$RC" -ne 2 ]]; then
  echo "TAMPER_STATUS=FAIL reason=TAMPER_NOT_DETECTED rc=$RC"
  exit 2
fi

echo "TAMPER_STATUS=PASS"
echo "TAMPER_RC=2"
