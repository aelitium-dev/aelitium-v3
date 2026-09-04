# AELITIUM Claim Boundaries v1

**Status:** IMPLEMENTATION-ALIGNED
**Contract identifier:** `aelitium-claim-boundary-v1`

This contract is a small, closed vocabulary of machine-readable non-claim
codes. Verification and comparison results embed its identifier and applicable
code arrays. A separate claim-boundary result object is unnecessary because no
independent operation evaluates these boundaries; they qualify the result in
which they appear.

The authoritative implementation-aligned vocabulary is exposed by
[`engine/result_contracts.py`](../engine/result_contracts.py), and each packaged
result schema repeats the closed enum. This vocabulary is specific to AELITIUM.
It is not presented as an external or industry standard.

## Interpretation rule

A code says that the result, evidence, and explicit inputs do not establish the
named claim. It does not assert the opposite fact.

For example, `authorization_not_established` means the operation reached no
authorization conclusion. It does not mean an interaction was unauthorized.
Likewise, `provider_execution_not_established` does not mean a provider failed
to execute; it means the inspected basis cannot answer that question.

Consumers must preserve that distinction in filtering, display, indexing, and
downstream decisions. A non-claim must not be converted into a negative finding.

## Closed vocabulary

| Code | Bounded meaning |
|---|---|
| `authorization_not_established` | The result does not establish that an accountable party authorized an interaction or action. |
| `capture_completeness_not_established` | The result does not establish that every relevant interaction, request, response, route, or event was captured. |
| `complete_invocation_identity_not_established` | The result does not establish equality or reconstruction of every behavior-affecting invocation field or execution-context value. |
| `historical_non_modification_not_established` | Internal consistency alone does not establish that a self-consistent artifact was never replaced or rewritten before comparison with an independently accepted anchor. |
| `historical_occurrence_not_established` | The result does not establish that a recorded interaction or event occurred in the external world. |
| `legal_compliance_not_established` | Technical verification does not determine legal or regulatory compliance. |
| `model_drift_not_established` | A comparison result does not establish model drift. |
| `provider_execution_not_established` | Invocation or bundle consistency does not establish that a provider received or executed the recorded invocation. |
| `provider_fault_not_established` | A comparison result does not attribute a difference or failure to a provider. |
| `quality_degradation_not_established` | A selected hash difference does not establish lower output quality. |
| `regression_not_established` | A selected hash difference does not establish a software or model regression. |
| `response_causation_not_established` | A stored binding or matching identity does not establish that a particular invocation caused the recorded response. |
| `semantic_equivalence_not_established` | Hash equality or inequality does not establish semantic equivalence or non-equivalence. |
| `semantic_truth_not_established` | Verification does not establish truth, correctness, or safety of recorded content. |
| `trusted_historical_time_not_established` | Declared-time recency does not establish a trusted historical timestamp or event time. |
| `trusted_signer_identity_not_established_by_signature` | Mathematical validity under bundled key material does not establish external acceptance of the signing key or the real-world identity behind it. |

## Operation profiles

`aelitium-verification-result-v1` emits these operation-wide codes, in stable
order:

1. `provider_execution_not_established`
2. `response_causation_not_established`
3. `semantic_truth_not_established`
4. `capture_completeness_not_established`
5. `historical_occurrence_not_established`
6. `historical_non_modification_not_established`
7. `authorization_not_established`
8. `trusted_historical_time_not_established`
9. `legal_compliance_not_established`
10. `complete_invocation_identity_not_established`

The embedded assurance entries add the codes relevant to their individual
bases. In particular, the signature entry carries
`trusted_signer_identity_not_established_by_signature`, and the Freshness entry
carries `trusted_historical_time_not_established`.

`aelitium-compare-v1` JSON emits these operation-wide codes, in stable order:

1. `model_drift_not_established`
2. `regression_not_established`
3. `quality_degradation_not_established`
4. `semantic_equivalence_not_established`
5. `response_causation_not_established`
6. `provider_fault_not_established`
7. `provider_execution_not_established`
8. `complete_invocation_identity_not_established`

The arrays are boundaries on every outcome, including `VALID`, `UNCHANGED`,
`CHANGED`, `NOT_COMPARABLE`, and `INVALID_BUNDLE`. They are not warnings that
appear only after failure.

## Consumer requirements

A consumer of a v1 result must:

- interpret codes as limits of the named result basis;
- keep non-claims distinct from negative findings;
- retain the `claim_boundary_contract` identifier when storing or forwarding
  the codes;
- reject unknown codes inside a closed v1 result rather than silently assigning
  them a guessed meaning; and
- avoid using absence of a code as proof that the corresponding external-world
  claim was established.

Consumers may render additional explanatory prose outside the closed result
object. Such prose cannot widen the underlying claim.

## Versioning

Changing the meaning of an existing code is forbidden within v1. Adding,
renaming, or removing codes requires an explicit vocabulary-version decision
and corresponding result-schema update. A future contract can reference a new
vocabulary; it must not silently reinterpret arrays labeled
`aelitium-claim-boundary-v1`.
