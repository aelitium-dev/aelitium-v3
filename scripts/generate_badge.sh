#!/usr/bin/env bash
set -euo pipefail

cd ~/aelitium-v3

set +e
OUT="$(./scripts/gate_release.sh v3.0.0-rc3 tests/fixtures/input_min.json 2>&1)"
RC=$?
set -e

STATUS="FAIL"
REASON="UNKNOWN"
if [[ $RC -eq 0 ]]; then
  STATUS="PASS"
  REASON="OK"
else
  # captura o reason se existir
  if echo "$OUT" | grep -q "reason="; then
    REASON="$(echo "$OUT" | grep -oE 'reason=[A-Z0-9_]+' | head -n1 | cut -d= -f2)"
  fi
fi

printf "%s\n" "$STATUS" > governance/dashboard/badge.txt
printf "%s\n" "$REASON" > governance/dashboard/badge_reason.txt

echo "Badge: $STATUS (reason=$REASON rc=$RC)"
exit 0
