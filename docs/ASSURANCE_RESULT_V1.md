# AELITIUM Assurance Result v1

**Status:** IMPLEMENTATION-ALIGNED
**Contract identifier:** `aelitium-assurance-result-v1`
**Claim-boundary identifier:** `aelitium-claim-boundary-v1`

This contract is a typed projection of the assurance states already produced by
the v0.4-compatible bundle verifier. It adds no assurance dimension, score, or
new evidence interpretation.

The packaged JSON Schema is
[`engine/schemas/assurance_result_v1.json`](../engine/schemas/assurance_result_v1.json).
The implementation-aligned serializer and invariant gate are in
[`engine/result_contracts.py`](../engine/result_contracts.py).

## Object shape

```json
{
  "contract": "aelitium-assurance-result-v1",
  "dimensions": [
    {
      "dimension": "payload_integrity",
      "state": "VALID",
      "basis": "ai_output_v1_canonical_manifest_digest_consistency",
      "evidence_refs": [
        "bundle:ai_canonical.json",
        "bundle:ai_manifest.json"
      ],
      "trust_input_refs": [],
      "policy_ref": null,
      "claim_boundaries": [
        "historical_occurrence_not_established",
        "historical_non_modification_not_established",
        "semantic_truth_not_established",
        "capture_completeness_not_established"
      ]
    }
  ],
  "claim_boundary_contract": "aelitium-claim-boundary-v1",
  "claim_boundaries": [
    "provider_execution_not_established",
    "response_causation_not_established",
    "semantic_truth_not_established",
    "capture_completeness_not_established",
    "historical_occurrence_not_established",
    "historical_non_modification_not_established",
    "authorization_not_established",
    "trusted_historical_time_not_established",
    "legal_compliance_not_established",
    "complete_invocation_identity_not_established"
  ]
}
```

The abbreviated example omits seven dimension entries only; its displayed entry
and operation-wide boundary profile are exact. A conforming result always
contains exactly eight entries in the order defined below. The schema enforces
that order and each dimension's reachable state set.

## State vocabulary

States are interpreted within one named dimension. They must not be promoted to
an aggregate judgment.

| State | Meaning |
|---|---|
| `VALID` | The dimension-specific check completed and its stated basis was satisfied. It says nothing beyond that basis. |
| `INVALID` | Present or selected material was evaluated and failed the dimension-specific check. |
| `ABSENT` | Optional AELITIUM-native evidence for that dimension is not present. Absence is not the same as a failed check. |
| `UNESTABLISHED` | The needed independent trust or complete policy basis was not established. This is not interchangeable with absence, invalidity, or non-evaluation. |
| `NOT_EVALUATED` | The dimension was not evaluated, either because it is unsupported under current semantics, no policy selected it, or an earlier prerequisite prevented evaluation. |

`VALID` always modifies the named dimension. In particular:

- `signature_validity=VALID` does not establish
  `trusted_signer_identity=VALID`;
- `invocation_identity_consistency=VALID` does not establish provider receipt
  or execution;
- `invocation_binding_consistency=VALID` does not establish response causation;
- `freshness=VALID` does not establish trusted historical time; and
- `authorization` remains `NOT_EVALUATED` under v0.4-compatible semantics.

## Dimensions and reachable states

| Ordered position | Dimension | Reachable states | `VALID` basis |
|---:|---|---|---|
| 1 | `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | `ai_output_v1` schema, governed canonical bytes, manifest identifiers, and canonical-payload digest are consistent |
| 2 | `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored request, response, metadata binding, and manifest binding fields are complete, well formed, and mutually consistent |
| 3 | `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | The stored `aelitium-invocation-v1` structure is valid and its hash recomputes from its stored selected fields |
| 4 | `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | The stored `aelitium-invocation-binding-v1` structure recomputes and links this bundle's valid invocation identity hash to its stored response hash |
| 5 | `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Bundled Ed25519 material mathematically verifies the bytes of `ai_manifest.json` |
| 6 | `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | The verified signing-key fingerprint occurs in the explicitly supplied `aelitium-trust-v1` input |
| 7 | `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | Declared `ai_canonical.json.ts_utc` lies in the inclusive window from the complete explicit Freshness policy pair |
| 8 | `authorization` | `NOT_EVALUATED` only | No authorization evaluator exists in v0.4-compatible semantics |

Every other dimension/state pair is unreachable and must be rejected rather
than serialized.

## Entry fields

### `basis`

`basis` is a stable, dimension-specific description code. It names what was
checked; it is not a score or an expansion of the state. The v1 values are:

| Dimension | `basis` |
|---|---|
| `payload_integrity` | `ai_output_v1_canonical_manifest_digest_consistency` |
| `binding_field_consistency` | `stored_request_response_binding_field_consistency` |
| `invocation_identity_consistency` | `aelitium-invocation-v1_recomputation` |
| `invocation_binding_consistency` | `aelitium-invocation-binding-v1_recomputation_and_bundle_linkage` |
| `signature_validity` | `ed25519_manifest_signature_verification` |
| `trusted_signer_identity` | `verified_ed25519_key_fingerprint_membership_in_explicit_aelitium-trust-v1` |
| `freshness` | `declared_canonical_timestamp_recency_under_explicit_policy` |
| `authorization` | `not_implemented_in_v0.4-compatible_semantics` |

### Evidence and input references

`evidence_refs` names bundle-local locations relevant to the dimension. A
reference identifies the expected location or JSON Pointer-like scope; it does
not assert that the referenced optional material was present. Presence and
evaluation are represented by `state`.

`trust_input_refs` is empty except on `trusted_signer_identity` when the caller
explicitly supplied a trust store. Its only v1 value is
`verification-input:trust-store`.

`policy_ref` is null except on `freshness` when at least one explicit Freshness
policy input was supplied. Its only non-null v1 value is
`verification-input:freshness-policy`. An incomplete pair can therefore be
referenced while the state remains `UNESTABLISHED`.

Input references deliberately omit filesystem paths. They identify the role of
an input without leaking a local operator path or pretending that two machines
used the same file solely because their path strings match.

### Claim boundaries

Each entry carries boundaries particularly relevant to that dimension. The
top-level list carries the operation-wide boundary. Both arrays use the closed
vocabulary documented in
[`CLAIM_BOUNDARIES_V1.md`](CLAIM_BOUNDARIES_V1.md).

## Emission invariants

The serializer rejects, at minimum, these impossible combinations:

- `trusted_signer_identity=VALID` unless `signature_validity=VALID` and an
  explicit trust input was supplied;
- `invocation_binding_consistency=VALID` unless
  `invocation_identity_consistency=VALID`;
- evaluated downstream integrity, signature, invocation, binding, or Freshness
  states before `payload_integrity=VALID`;
- a successful verification containing an `INVALID` or `UNESTABLISHED`
  evaluated requirement;
- a successful invocation pair other than `ABSENT/ABSENT`, `VALID/ABSENT`, or
  `VALID/VALID`;
- `authorization` in any state other than `NOT_EVALUATED`; and
- `payload_integrity=VALID` without a 64-character lowercase hexadecimal
  canonical-payload SHA-256 value, or a non-`VALID` payload state carrying that
  digest.

The JSON Schema enforces structure, order, and per-dimension state reachability.
The serializer invariant gate enforces relationships that span entries and
verification inputs. Consumers should apply both layers.

## No aggregate result

The contract has no `score`, percentage, weighted total, minimum dimension, or
`overall_assurance` field. The overall verification status belongs to
`aelitium-verification-result-v1`; it indicates whether the selected bundle
verification operation succeeded, not that every conceivable trust claim was
established.

## Compatibility and versioning

This object is emitted only through the additive `--contract-json` verification
surface or as the embedded `assurance` member of that result. Existing text and
legacy `--json` verification output are unchanged.

Any change to dimension names, order, state meaning, reachable state sets,
bases, or cross-dimension invariants requires a new contract identifier. New
claim-boundary codes likewise require an explicit vocabulary-version decision.
