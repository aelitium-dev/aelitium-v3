#!/usr/bin/env bash
set -euo pipefail

echo "== AELITIUM release audit =="

echo
echo "## Public claims guardrail"
./scripts/guardrail_public_claims.sh

echo
echo "## Capture adapter call-time claims"
if grep -RIn --exclude='*.bak' -e "captured at call time" engine/capture ; then
  echo
  echo "[FAIL] Capture adapter call-time claims"
  exit 1
else
  echo "[PASS] Capture adapter call-time claims"
fi

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
echo "[PASS] Release audit passed"
