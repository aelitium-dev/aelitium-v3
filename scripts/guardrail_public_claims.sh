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

require_literal() {
  local file="$1"
  local literal="$2"
  if ! grep -qF -- "$literal" "$file"; then
    echo "[FAIL] required public-contract text missing from $file: $literal"
    fail=1
  fi
}

forbid_literal() {
  local file="$1"
  local literal="$2"
  if grep -qF -- "$literal" "$file"; then
    echo "[FAIL] stale public-contract text remains in $file: $literal"
    fail=1
  fi
}

contract_docs=(
  "README.md"
  "docs/ONE_PAGER.md"
  "docs/TRUST_BOUNDARY.md"
  "docs/MESSAGING_GUARDRAILS.md"
  "docs/ARCHITECTURE.md"
  "docs/TRUST_MODEL.md"
  "FEATURE_MATRIX.md"
)

assurance_dimensions=(
  "payload_integrity"
  "binding_field_consistency"
  "invocation_identity_consistency"
  "invocation_binding_consistency"
  "signature_validity"
  "trusted_signer_identity"
  "freshness"
  "authorization"
)

for file in "${contract_docs[@]}"; do
  for dimension in "${assurance_dimensions[@]}"; do
    require_literal "$file" "$dimension"
  done
  require_literal "$file" "NOT_EVALUATED"
done

for dimension in "${assurance_dimensions[@]}"; do
  require_literal "docs/AI_INTEGRITY_DEMO.md" "${dimension^^}="
done

require_literal "README.md" "--freshness-max-age-seconds"
require_literal "README.md" "--freshness-reference-time-utc"
for file in docs/TRUST_BOUNDARY.md docs/MESSAGING_GUARDRAILS.md; do
  require_literal "$file" "freshness_max_age_seconds"
  require_literal "$file" "freshness_reference_time_utc"
done

require_literal "pyproject.toml" "Internally consistent, offline-verifiable"
forbid_literal "pyproject.toml" 'description = "Tamper-evident evidence bundles for AI outputs"'

unreleased_changelog="$(sed -n '/^## \[Unreleased\]/,/^## \[0\.4\.0\]/p' CHANGELOG.md)"
for stale_literal in \
  "14c8202626f85637d44bc7209ed64f3ba7f646ce" \
  "CI test-suite gate (PR #21)" \
  "459 tests" \
  '`freshness` remains `NOT_EVALUATED`.'
do
  if [[ "$unreleased_changelog" == *"$stale_literal"* ]]; then
    echo "[FAIL] stale claim remains in current Unreleased section: $stale_literal"
    fail=1
  fi
done
require_literal "docs/RELEASE_PROCESS.md" "release_commit_sha"
require_literal "docs/RELEASE_PROCESS.md" "Explicit human approval is required before each"
require_literal "docs/RELEASE_PROCESS.md" "PyPI Trusted Publishing is the preferred publication mechanism"
require_literal "docs/RELEASE_PROCESS.md" "do not silently fall back to Twine"
require_literal "docs/RELEASE_PROCESS.md" "annotated, unsigned tag is sufficient"
require_literal "docs/RELEASE_PROCESS.md" "final release-state changes may be prepared on a release branch"
require_literal "docs/RELEASE_PROCESS.md" "git pull --ff-only origin main"
require_literal "docs/RELEASE_PROCESS.md" "git rev-parse HEAD"
require_literal "docs/RELEASE_PROCESS.md" 'exact `main` `HEAD` commit that first contains the'
require_literal "docs/RELEASE_PROCESS.md" "merge commit, squash merge, or rebased commit"
require_literal "docs/RELEASE_PROCESS.md" "Do not tag the release-readiness PR SHA."
require_literal "docs/RELEASE_PROCESS.md" 'Do not tag the pre-merge `release/v0.4.0-final` branch SHA.'
require_literal "docs/RELEASE_PROCESS.md" 'The annotated `v0.4.0` tag must target exactly `release_commit_sha`.'
require_literal "docs/RELEASE_PROCESS.md" '`HEAD == release_commit_sha`'
forbid_literal "docs/RELEASE_PROCESS.md" 'an ambiguously named “merge SHA.”'
require_literal "docs/RELEASE_CHECKLIST_v0.2.0.md" "historical record, not current release instructions"
require_literal "CHANGELOG.md" '**Release status.** The repository and package baseline is `0.3.0`, released'
require_literal "FEATURE_MATRIX.md" "inventory of the released 0.4.0 surface"
require_literal "README.md" '`v0.4.0` is the current published GitHub and PyPI release'
require_literal "docs/ONE_PAGER.md" "Current published release: **v0.4.0**"
require_literal "docs/RELEASE_PROCESS.md" 'current published release is `v0.4.0`'
require_literal "SECURITY.md" '`v0.4.0` is the current'
require_literal "SECURITY.md" '| 0.3.x   | Superseded (latest release: `v0.3.0`) | ❌ |'
require_literal "CHANGELOG.md" "## [0.4.0] — 2026-09-03"
require_literal "CHANGELOG.md" "### Breaking / Compatibility"
require_literal "CHANGELOG.md" "same rich bundle pair can move from"
forbid_literal "README.md" "unreleased **v0.4.0** development"
forbid_literal "SECURITY.md" "Pending release line"
forbid_literal "docs/ONE_PAGER.md" "development version: **0.4.0** (unreleased)"
forbid_literal "CHANGELOG.md" "This remains unreleased"

compare_contract_docs=(
  "README.md"
  "docs/MODEL_BEHAVIOR_CHANGE.md"
  "docs/CANONICAL_REQUEST.md"
  "docs/INVOCATION_ASSURANCE.md"
  "docs/MESSAGING_GUARDRAILS.md"
  "docs/ONE_PAGER.md"
)

for file in "${compare_contract_docs[@]}"; do
  require_literal "$file" 'Comparison basis in v0.3.x: `request_hash` v1'
  require_literal "$file" 'Comparison contract in v0.4.0: `aelitium-compare-v1`'
done

require_literal "docs/MESSAGING_GUARDRAILS.md" 'does not use `invocation_identity`'
require_literal "CHANGELOG.md" "## [Unreleased]"
require_literal "FEATURE_MATRIX.md" 'Comparison contract in v0.4.0: `aelitium-compare-v1`'
for file in README.md docs/ONE_PAGER.md docs/TRUST_BOUNDARY.md docs/MESSAGING_GUARDRAILS.md; do
  require_literal "$file" "Reachable states in v0.4.0"
done
require_literal "engine/ai_cli.py" 'COMPARISON_CONTRACT = "aelitium-compare-v1"'
require_literal "engine/ai_cli.py" 'COMPARISON_BASIS_INVOCATION_IDENTITY_V1 = "INVOCATION_IDENTITY_V1"'
require_literal "engine/ai_cli.py" 'COMPARISON_BASIS_REQUEST_HASH_V1_FALLBACK = "REQUEST_HASH_V1_FALLBACK"'
require_literal "engine/ai_cli.py" 'COMPARISON_BASIS_REQUEST_HASH_V1_LEGACY = "REQUEST_HASH_V1_LEGACY"'
require_literal "engine/ai_cli.py" '"--require-invocation-evidence"'
require_literal "engine/ai_cli.py" '"--legacy-request-hash-v1"'
for file in README.md docs/MODEL_BEHAVIOR_CHANGE.md docs/MESSAGING_GUARDRAILS.md docs/ONE_PAGER.md; do
  require_literal "$file" "AELITIUM establishes internal consistency of recorded"
done
forbid_literal "examples/drift_demo/generate_bundles.py" "simulates model drift"
forbid_literal "examples/drift_demo/run_demo.sh" "The change came from the model"
forbid_literal "docs/AAR_EVIDENCE_REF_MAPPING.md" "drift detection across runs"
forbid_literal "docs/SECURITY_MODEL.md" "drift detection signals"

forbid_literal "README.md" "Export bundle in compliance format"
forbid_literal "docs/ONE_PAGER.md" "Tamper-resistant logs for high-risk AI"
forbid_literal "docs/AI_INTEGRITY_DEMO.md" "| Regulatory compliance |"
forbid_literal "engine/compliance.py" "return EU AI Act Article 12 format"

require_literal "docs/VERIFICATION_RESULT_V1.md" "**Status:** IMPLEMENTATION-ALIGNED"
require_literal "docs/VERIFICATION_RESULT_V1.md" "aelitium-verification-result-v1"
require_literal "docs/ASSURANCE_RESULT_V1.md" "**Status:** IMPLEMENTATION-ALIGNED"
require_literal "docs/ASSURANCE_RESULT_V1.md" "aelitium-assurance-result-v1"
require_literal "docs/CLAIM_BOUNDARIES_V1.md" "**Status:** IMPLEMENTATION-ALIGNED"
require_literal "docs/CLAIM_BOUNDARIES_V1.md" "aelitium-claim-boundary-v1"
require_literal "docs/COMPARE_RESULT_V1.md" "**Status:** IMPLEMENTATION-ALIGNED"
require_literal "docs/COMPARE_RESULT_V1.md" "aelitium-compare-v1"
require_literal "docs/CONTRACT_DEMO.md" "**Status:** NON-NORMATIVE"
require_literal "docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md" "**Status:** RESEARCH"
require_literal "docs/interop/SCITT_AI_AGENT_RECEIPT_01.md" "**Status:** EXPERIMENTAL"
require_literal "docs/interop/SCITT_AI_AGENT_RECEIPT_01.md" "**Implementation status:** BLOCKED"
require_literal "docs/interop/SCITT_AI_AGENT_RECEIPT_01.md" "draft-noa-scitt-ai-agent-receipt-01"
require_literal "conformance/README.md" "**Status:** IMPLEMENTATION-ALIGNED"
require_literal "conformance/manifest.json" '"case_count": 44'

for dimension in "${assurance_dimensions[@]}"; do
  require_literal "docs/ASSURANCE_RESULT_V1.md" "$dimension"
  require_literal "docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md" "$dimension"
done

claim_boundary_codes=(
  "authorization_not_established"
  "capture_completeness_not_established"
  "complete_invocation_identity_not_established"
  "historical_non_modification_not_established"
  "historical_occurrence_not_established"
  "legal_compliance_not_established"
  "model_drift_not_established"
  "provider_execution_not_established"
  "provider_fault_not_established"
  "quality_degradation_not_established"
  "regression_not_established"
  "response_causation_not_established"
  "semantic_equivalence_not_established"
  "semantic_truth_not_established"
  "trusted_historical_time_not_established"
  "trusted_signer_identity_not_established_by_signature"
)

for code in "${claim_boundary_codes[@]}"; do
  require_literal "docs/CLAIM_BOUNDARIES_V1.md" "$code"
  require_literal "engine/result_contracts.py" "$code"
done

for basis in \
  "INVOCATION_IDENTITY_V1" \
  "REQUEST_HASH_V1_FALLBACK" \
  "REQUEST_HASH_V1_LEGACY" \
  "NONE"
do
  require_literal "docs/COMPARE_RESULT_V1.md" "$basis"
done

if [ "$fail" -ne 0 ]; then
  echo "[FAIL] public-contract reconciliation checks failed"
  exit 1
fi

echo "[PASS] public-contract reconciliation checks passed"

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
    [ -f conformance/README.md ] && printf '%s\n' conformance/README.md
    [ -f conformance/manifest.json ] && printf '%s\n' conformance/manifest.json
    find conformance -mindepth 2 -maxdepth 2 -type f -name '*.json' \
      2>/dev/null
    find docs -type f -name '*.md' \
      ! -name 'MESSAGING_GUARDRAILS.md' \
      ! -name 'RELEASE_AUDIT_CHECKLIST.md' \
      ! -name 'EVIDENCE_BUNDLE_SPEC.md' \
      ! -name 'EVIDENCE_MODEL.md' \
      ! -name 'ENGINE_CONTRACT.md' \
      ! -name 'OFFLINE_VERIFIER.md' \
      2>/dev/null
    find docs/interop -type f -name '*.mapping.json' \
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
    if [[ "$match" == *'"--require-trusted-signer"'* ]]; then
      # A literal CLI option in a machine-readable vector is not a trust claim.
      continue
    fi
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
