#!/usr/bin/env bash
set -euo pipefail

quarantine_files=(
  "docs/EVIDENCE_BUNDLE_SPEC.md"
  "docs/EVIDENCE_MODEL.md"
  "docs/ENGINE_CONTRACT.md"
  "docs/OFFLINE_VERIFIER.md"
)

quarantine_markers=(
  "CONCEPTUAL_DRAFT_NON_NORMATIVE"
  "CONCEPTUAL_MODEL_NON_NORMATIVE"
  "LEGACY_GENERIC_BUNDLE_COMPATIBILITY"
  "LEGACY_GENERIC_OFFLINE_VERIFIER"
)

fail=0

for i in "${!quarantine_files[@]}"; do
  file="${quarantine_files[$i]}"
  marker="${quarantine_markers[$i]}"

  if [ ! -f "$file" ]; then
    echo "[FAIL] quarantine document missing: $file"
    fail=1
  elif grep -qF -- "**Status:** $marker" "$file"; then
    echo "[PASS] quarantine marker $marker: $file"
  else
    echo "[FAIL] missing quarantine marker $marker: $file"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "[FAIL] public-claims guardrail failed during quarantine checks"
  exit 1
fi

echo "[PASS] required quarantine markers found"

# Phrase-level affirmative patterns only. These intentionally avoid isolated words
# such as "exact", "proof", "trusted", or "immutable".
pattern_labels=(
  "trust-gap completeness"
  "exact or full invocation identity"
  "historical non-modification"
  "proof of permanent non-modification"
  "tamper-proof artefact"
  "trusted signer or authenticated origin"
  "universal JSON support"
  "universal provider coverage"
  "output-text-only determinism"
  "model-output authenticity"
  "capture-time certainty"
  "configuration-free universality"
)

patterns=(
  "no[[:space:]-]+trust[[:space:]-]+gap|closes?[[:space:]]+(the[[:space:]]+)?trust[[:space:]-]+gap"
  "exact[[:space:]-]+request|full[[:space:]-]+invocation"
  "(bundle|record|evidence|payload)[^.!?]*(has|have|was|were)[[:space:]]+not[[:space:]]+(been[[:space:]]+)?(changed|altered|modified)[^.!?]*(since|after)[[:space:]][^.!?]*(pack|captur)"
  "(proof|proves?|proven)[^.!?]*(never|not)[^.!?]*(altered|modified|changed)"
  "tamper[[:space:]-]*proof"
  "verified[[:space:]-]+signer|trusted[[:space:]-]+signer|authenticated[[:space:]-]+producer|authentic[[:space:]-]+origin"
  "(all|every)[[:space:]]+commands?[^.!?]*--json|--json[^.!?]*(all|every)[[:space:]]+commands?"
  "(one|single)[[:space:]]+adapter[^.!?]*(covers?|supports?)[^.!?]*(all|every([[:space:]]+providers?)?)|any[[:space:]]+openai-compatible"
  "same[[:space:]]+(ai[[:space:]]+)?output[^.!?]*(always[[:space:]]+)?produces?[^.!?]*same[[:space:]]+hash"
  "what[[:space:]]+the[[:space:]]+model[[:space:]]+actually[[:space:]]+(said|returned|generated)|exactly[[:space:]]+what[[:space:]]+the[[:space:]]+model[[:space:]]+generated"
  "(proves?|guarantees?|establishes?)[^.!?]*(captured[[:space:]]+at[[:space:]]+call[[:space:]]+time|after[[:space:]]+capture|since[[:space:]]+capture|at[[:space:]]+generation[[:space:]]+time|exactly[[:space:]]+when)"
  "no[[:space:]-]+config(uration)?"
)

is_explicit_negative_guidance() {
  local context="$1"
  local pattern="$2"
  local negative_prefix="does[[:space:]]+not|do[[:space:]]+not|must[[:space:]]+not|cannot|can[[:space:]]+not|not[[:space:]]+approved|avoid([[:space:]]*:)?|disallow(ed)?([[:space:]]*:)?"
  local negative_then_pattern="($negative_prefix)[^.!?]{0,700}($pattern)"
  local pattern_then_negative="($pattern)[^.!?]{0,100}(is|are)[[:space:]]+not[[:space:]]+(approved|established|guaranteed|a[[:space:]]+current[[:space:]]+capability)"

  # The negative guidance must precede the matched phrase in the same nearby
  # clause or Markdown section. Do not suppress a match merely because an
  # unrelated "not" appears somewhere in the context.
  if [[ "$context" =~ $negative_then_pattern ]]; then
    return 0
  fi

  if [[ "$context" =~ $pattern_then_negative ]]; then
    return 0
  fi

  if [[ "$context" =~ no[[:space:]]+(one|single)[[:space:]]+adapter[^.!?]*(covers?|supports?)[^.!?]*(all|every) ]]; then
    return 0
  fi

  return 1
}

files=()

while IFS= read -r file; do
  files+=("$file")
done < <(
  {
    [ -f README.md ] && printf '%s\n' README.md
    find docs -type f -name '*.md' \
      ! -name 'MESSAGING_GUARDRAILS.md' \
      ! -name 'RELEASE_AUDIT_CHECKLIST.md' \
      ! -name 'EVIDENCE_BUNDLE_SPEC.md' \
      ! -name 'EVIDENCE_MODEL.md' \
      ! -name 'ENGINE_CONTRACT.md' \
      ! -name 'OFFLINE_VERIFIER.md' \
      2>/dev/null
  } | sort -u
)

if [ "${#files[@]}" -eq 0 ]; then
  echo "[FAIL] no current/public markdown files matched guardrail scope"
  exit 1
fi

for i in "${!patterns[@]}"; do
  pattern="${patterns[$i]}"
  label="${pattern_labels[$i]}"

  while IFS= read -r match; do
    match_file="${match%%:*}"
    match_remainder="${match#*:}"
    line_number="${match_remainder%%:*}"
    context_start=$((line_number > 8 ? line_number - 8 : 1))
    context_end=$((line_number + 1))
    context="$(sed -n "${context_start},${context_end}p" "$match_file" | tr '\n' ' ')"

    if is_explicit_negative_guidance "${context,,}" "$pattern"; then
      continue
    fi

    echo "[FAIL] affirmative public-claim pattern ($label): $match"
    fail=1
  done < <(grep -HnEi -- "$pattern" "${files[@]}" || true)
done

if [ "$fail" -ne 0 ]; then
  echo "[FAIL] public-claims guardrail failed"
  exit 1
fi

echo "[PASS] no affirmative public-claim overreach found"
