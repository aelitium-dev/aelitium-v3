# AELITIUM Compare v1 Result Contract

**Status:** IMPLEMENTATION-ALIGNED
**Contract identifier:** `aelitium-compare-v1`

`aelitium-compare-v1` is the existing v0.4.0 comparison contract. This work does
not rename or redesign it. The JSON surface is hardened additively so a consumer
can recover input verification, selected basis, comparability, response
relationship, and claim boundaries from one object.

The packaged JSON Schema is
[`engine/schemas/compare_result_v1.json`](../engine/schemas/compare_result_v1.json).

## Decision pipeline

```text
verify left bundle       verify right bundle
          \                 /
           validated assurance
                    |
             select mode/basis
                    |
             comparability gate
                    |
     UNCHANGED / CHANGED / NOT_COMPARABLE
```

If either input fails verification or violates a comparison-input invariant,
the operation returns `INVALID_BUNDLE` before making a comparability decision.
The verifier never falls back from invalid evidence.

## Modes and bases

| `comparison_mode` | Basis rule |
|---|---|
| `INVOCATION_FIRST` | Select `INVOCATION_IDENTITY_V1` only when both valid inputs have `invocation_identity_consistency=VALID` and `invocation_binding_consistency=VALID`; otherwise select visible `REQUEST_HASH_V1_FALLBACK`. |
| `STRICT_INVOCATION` | Select `INVOCATION_IDENTITY_V1` when usable on both sides; otherwise select `NONE`, report required basis `INVOCATION_IDENTITY_V1`, and return `NOT_COMPARABLE`. |
| `LEGACY_REQUEST_HASH_V1` | Select `REQUEST_HASH_V1_LEGACY` after both inputs verify, reproducing the v0.3.x selected request-hash decision. |

CLI selection remains:

- no mode flag: `INVOCATION_FIRST`;
- `--require-invocation-evidence`: `STRICT_INVOCATION`; and
- `--legacy-request-hash-v1`: `LEGACY_REQUEST_HASH_V1`.

The two mode flags remain mutually exclusive.

## Results and exit codes

| `status` | `comparability_result` | `response_relationship` | Exit code | Meaning |
|---|---|---|---:|---|
| `UNCHANGED` | `UNCHANGED` | `SAME` | 0 | Selected comparison identity and selected response hashes match under the reported basis. |
| `CHANGED` | `CHANGED` | `DIFFERENT` | 2 | Selected comparison identity hashes match and selected response hashes differ under the reported basis. No cause is identified. |
| `NOT_COMPARABLE` | `NOT_COMPARABLE` | null | 1 | Required or selected identities differ or are unavailable, so no response relationship is asserted. |
| `INVALID_BUNDLE` | null | null | 2 | Comparison was not performed because an input failed verification or a comparison-input invariant. Basis is `NONE`. |

`NOT_COMPARABLE` is a successful semantic refusal, not a crash and not an
invalid-bundle alias. Its nonzero code preserves the existing CLI contract for
automation.

## Basis-specific decisions

For `INVOCATION_IDENTITY_V1`:

1. both input bundles must be valid;
2. both invocation identity and invocation binding dimensions must be `VALID`;
3. each selected response hash must be a 64-character lowercase hexadecimal
   SHA-256 value;
4. different invocation identity hashes yield `NOT_COMPARABLE`;
5. matching invocation identity hashes plus matching response hashes yield
   `UNCHANGED`; and
6. matching invocation identity hashes plus different response hashes yield
   `CHANGED`.

For either request-hash basis:

1. both input bundles must be valid;
2. missing selected request identity yields `NOT_COMPARABLE` with reason
   `REQUEST_HASH_UNAVAILABLE`;
3. malformed selected request or response hashes are an input invariant failure;
4. different request hashes yield `NOT_COMPARABLE`;
5. matching request hashes plus matching response hashes yield `UNCHANGED`; and
6. matching request hashes plus different response hashes yield `CHANGED`.

The original `binding_hash` and invocation-binding hash remain diagnostics and
assurance inputs. Neither is a comparison identity.

## Machine-readable fields

Existing JSON keys remain present. The hardened result additionally standardizes:

| Field | Meaning |
|---|---|
| `comparability_result` | The three-way comparability conclusion, or null for `INVALID_BUNDLE` |
| `response_relationship` | `SAME` or `DIFFERENT` only after comparability succeeds; otherwise null |
| `required_comparison_basis` | `INVOCATION_IDENTITY_V1` only when strict mode cannot obtain its required basis; otherwise null |
| `left.evidence_ref`, `right.evidence_ref` | Bounded bundle component references and canonical-payload digest when established |
| `left.verification`, `right.verification` | Per-side `VALID`/`INVALID`, reason, and all eight assurance states |
| `claim_boundary_contract` | Exact value `aelitium-claim-boundary-v1` |
| `claim_boundaries` | Stable comparison non-claim codes |

The flat historical keys, including `status`, `rc`, mode, basis, reason,
identity relations, selected hashes, timestamp displays, detail, hint, and
interpretation, are retained for compatibility.

For a non-comparable result, the historical `response_hash` diagnostic can
still describe equality of the two stored hash strings. It is not a response
relationship conclusion. Consumers must use `response_relationship`, which is
null for `NOT_COMPARABLE` and `INVALID_BUNDLE`, and must not promote the legacy
diagnostic into `SAME` or `DIFFERENT` when the comparability gate refused.

## Fail-closed comparison-input invariants

Before basis selection, each successful verifier result must contain canonical
and manifest objects consistent with its invocation assurance states. A present
invocation identity or binding cannot disagree with its reported state, and a
usable invocation identity must carry a well-formed hash. An impossible input
becomes `INVALID_BUNDLE` with reason
`COMPARISON_INPUT_INVARIANT_FAILED`; it never triggers fallback.

## Claim boundaries

The result does not establish model drift, regression, quality degradation,
semantic equivalence, response causation, provider fault, provider execution,
or complete invocation identity. `CHANGED` is a selected hash relationship, not
an explanation. `UNCHANGED` does not establish unchanged provider behavior or
unrecorded configuration. `NOT_COMPARABLE` does not assert that the underlying
interactions differ.

The exact codes and the rule against converting non-claims into negative
findings are documented in
[`CLAIM_BOUNDARIES_V1.md`](CLAIM_BOUNDARIES_V1.md).

## Compatibility and versioning

Normal human-readable output, old JSON keys, mode selection, basis selection,
reason codes, and exit codes are unchanged. The new nested fields and claim
boundaries are additive only under `compare --json`.

Changing basis selection, the meaning of any outcome, or the status/exit-code
mapping requires a new comparison-contract version. A different JSON layout
alone must not disguise a semantic change under `aelitium-compare-v1`.
