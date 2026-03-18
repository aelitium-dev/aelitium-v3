#!/usr/bin/env bash
set -euo pipefail

patterns=(
  "proves what the model actually"
  "what the model actually said"
  "what the model actually returned"
  "exactly what the model generated"
  "closes the trust gap"
  "no trust gap"
  "captured at call time"
  "after capture"
  "since capture"
  "at generation time"
  "verify --out"
  "any OpenAI-compatible"
  "No config"
  "exactly when"
)

files=()

while IFS= read -r f; do
  files+=("$f")
done < <(
  {
    [ -f README.md ] && printf '%s\n' README.md
    find docs -type f -name '*.md' \
      ! -name 'MESSAGING_GUARDRAILS.md' \
      ! -name 'RELEASE_AUDIT_CHECKLIST.md' \
      2>/dev/null
  } | sort -u
)

if [ "${#files[@]}" -eq 0 ]; then
  echo "[FAIL] no markdown files matched guardrail scope"
  exit 1
fi

fail=0

for pattern in "${patterns[@]}"; do
  if grep -nF -- "${pattern}" "${files[@]}"; then
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "[FAIL] public-claims guardrail failed"
  exit 1
fi

echo "[PASS] no overclaim patterns found"
