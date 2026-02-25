#!/usr/bin/env bash
set -euo pipefail

echo "=== AELITIUM Machine B Validation ==="
mkdir -p ~/machine_b/logs

echo "[1] PACK"
python3 engine/cli.py pack \
  --input tests/fixtures/input_min.json \
  --out release_output |& tee ~/machine_b/logs/pack.txt

echo "[2] VERIFY"
python3 engine/cli.py verify \
  --manifest release_output/manifest.json \
  --evidence release_output/evidence_pack.json |& tee ~/machine_b/logs/verify.txt
rc_verify=${PIPESTATUS[0]}
echo "RC_VERIFY=$rc_verify" | tee -a ~/machine_b/logs/verify.txt

echo "[3] REPRO"
python3 engine/cli.py repro \
  --input tests/fixtures/input_min.json |& tee ~/machine_b/logs/repro.txt
rc_repro=${PIPESTATUS[0]}
echo "RC_REPRO=$rc_repro" | tee -a ~/machine_b/logs/repro.txt

echo "[4] TAMPER"
cp release_output/evidence_pack.json release_output/evidence_pack.tampered.json
python3 - <<'PY'
import json
p="release_output/evidence_pack.tampered.json"
d=json.load(open(p,"r",encoding="utf-8"))
d["canonical_payload"]=d["canonical_payload"].replace("42","43")
json.dump(d, open(p,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
PY

# --- TAMPER verify (expected to fail) ---
set +e
python3 engine/cli.py verify \
  --manifest release_output/manifest.json \
  --evidence release_output/evidence_pack.tampered.json |& tee ~/machine_b/logs/tamper_verify.txt
rc_tamper=${PIPESTATUS[0]}
set -e

echo "RC_TAMPER=$rc_tamper" | tee -a ~/machine_b/logs/tamper_verify.txt
echo "=== SUMMARY ==="
echo "RC_VERIFY=$rc_verify"
echo "RC_REPRO=$rc_repro"
echo "RC_TAMPER=$rc_tamper"

if [[ "$rc_verify" -eq 0 && "$rc_repro" -eq 0 && "$rc_tamper" -ne 0 ]]; then
  echo "RESULT: PASS"
  exit 0
else
  echo "RESULT: FAIL"
  exit 1
fi
