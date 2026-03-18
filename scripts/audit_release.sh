#!/usr/bin/env bash
set -euo pipefail

echo "== AELITIUM release audit =="

fail=0

scan_no_matches() {
  local label="$1"
  shift
  echo
  echo "## $label"
  if grep -RIn --exclude='*.bak' --exclude='RELEASE_AUDIT_CHECKLIST.md' "$@" ; then
    echo
    echo "[FAIL] $label"
    fail=1
  else
    echo "[PASS] $label"
  fi
}

scan_no_matches "Positive overclaim scan" \
  -e "proves what the model actually" \
  -e "what the model actually said" \
  -e "what the model actually returned" \
  -e "exactly what the model generated" \
  -e "closes the trust gap" \
  -e "no trust gap" \
  -e "captured at call time" \
  -e "after capture" \
  -e "since capture" \
  -e "at generation time" \
  README.md docs engine/capture

scan_no_matches "CLI drift in docs" \
  -e "verify --out" \
  README.md docs

scan_no_matches "Capture adapter call-time claims" \
  -e "captured at call time" \
  engine/capture

echo
echo "## CLI help validation"
if command -v aelitium >/dev/null 2>&1; then
  aelitium --help >/dev/null
  aelitium verify-bundle --help >/dev/null
  echo "[PASS] CLI help validation"
else
  python3 -m engine.ai_cli --help >/dev/null
  python3 -m engine.ai_cli verify-bundle --help >/dev/null
  echo "[PASS] CLI help validation via python3 -m engine.ai_cli"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "[FAIL] Release audit failed"
  exit 1
fi

echo "[PASS] Release audit passed"
