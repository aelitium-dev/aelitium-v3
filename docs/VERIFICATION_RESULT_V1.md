# AELITIUM Verification Result v1

**Status:** IMPLEMENTATION-ALIGNED
**Contract identifier:** `aelitium-verification-result-v1`

This contract describes one offline AELITIUM bundle-verification operation. It
projects the existing verifier result and explicit caller inputs without
copying the evidence bundle or making a stronger claim than the verifier.

The packaged JSON Schema is
[`engine/schemas/verification_result_v1.json`](../engine/schemas/verification_result_v1.json).
The implementation-aligned construction is in
[`engine/result_contracts.py`](../engine/result_contracts.py).

## CLI surface

```bash
aelitium verify-bundle ./bundle --contract-json
aelitium verify --out ./bundle --contract-json
```

`--contract-json` is mutually exclusive with the legacy `--json` option. It
emits one JSON object for both success and failure:

| Verification status | Exit code |
|---|---:|
| `VALID` | 0 |
| `INVALID` | 2 |

The existing human-readable output and legacy `--json` behavior remain
unchanged. In particular, invalid verification under the old `--json` option
continues to use its compatibility text form.

## Required fields

| Field | Meaning |
|---|---|
| `contract` | Exact value `aelitium-verification-result-v1` |
| `artifact` | Bounded references to expected bundle components and, when established, the canonical-payload digest |
| `status` | `VALID` or `INVALID` for this verification operation |
| `rc` | CLI-equivalent code, bound to `status` by the schema |
| `reason` | Stable verifier reason code; `OK` only for `VALID` |
| `detail` | Non-normative elaboration or null; consumers must not pattern-match it |
| `assurance` | Complete embedded `aelitium-assurance-result-v1` |
| `verification_inputs` | Boolean choices that selected current verifier requirements |
| `trust_inputs` | Reference to an explicitly supplied local trust input, or an empty array |
| `policy_inputs` | The explicitly supplied Freshness policy values, or an empty array |
| `claim_boundary_contract` | Exact value `aelitium-claim-boundary-v1` |
| `claim_boundaries` | Operation-wide bounded non-claim codes |

## Artifact reference

The artifact object is deliberately a component reference, not a copy of the
bundle:

```json
{
  "artifact_type": "ai_evidence_bundle",
  "expected_payload_schema": "ai_output_v1",
  "expected_manifest_schema": "ai_pack_manifest_v1",
  "canonical_ref": "bundle:ai_canonical.json",
  "manifest_ref": "bundle:ai_manifest.json",
  "canonical_payload_digest": {
    "algorithm": "sha256",
    "scope": "canonical_payload",
    "value": "<64 lowercase hexadecimal characters>"
  }
}
```

`canonical_payload_digest` is null when verification fails before a canonical
payload digest is established. When present, it is the SHA-256 digest of the
governed canonical payload bytes. It is not a digest of the directory, the
manifest, optional signature material, or an external event.

The result does not include the caller's bundle path. Bundle-local stable
references make repeated output independent of checkout location and avoid
turning a local path into artifact identity.

## Verification inputs

`verification_inputs` contains exactly:

- `validate_manifest_timestamp`;
- `require_signature`;
- `require_binding`; and
- `require_trusted_signer`.

`trust_inputs` contains at most one object. If a trust-store path was supplied,
the object identifies its role as `verification-input:trust-store`, format
`aelitium-trust-v1`, and source `explicit_local_file`. The filesystem path and
trust-store contents are not copied into the result.

`policy_inputs` contains at most one object. If either Freshness option was
supplied, it records:

- reference `verification-input:freshness-policy`;
- kind `declared_time_freshness_v1`;
- `maximum_age_seconds`; and
- `reference_time_utc`.

Recording an incomplete pair does not make it valid. The associated assurance
state remains `UNESTABLISHED` and the verification reason is
`FRESHNESS_POLICY_INVALID`.

No ambient trust store, system clock, network service, or hidden policy input is
consulted.

## Overall status and partial assurance

`status=VALID` means the bundle passed the existing verification pipeline under
the selected inputs. It does not mean that all eight dimensions are `VALID`:
optional evidence can be `ABSENT`, independent signer trust can be
`UNESTABLISHED`, Freshness can be `NOT_EVALUATED`, and authorization is always
`NOT_EVALUATED` under current semantics.

`status=INVALID` identifies a failed verification operation and preserves the
verifier's deterministic reason precedence. Its embedded assurance result shows
the states reached before or during the failure. A state of `NOT_EVALUATED`
must not be rewritten as `INVALID`, `ABSENT`, or `UNESTABLISHED`.

The assurance object's cross-dimension invariants are defined in
[`ASSURANCE_RESULT_V1.md`](ASSURANCE_RESULT_V1.md). The detailed verification
order and reason-reproduction requirements for an independent implementation
are in
[`INDEPENDENT_VERIFIER_REQUIREMENTS.md`](INDEPENDENT_VERIFIER_REQUIREMENTS.md).

## Serialization and determinism

The CLI emits UTF-8 JSON with keys sorted lexicographically and one terminal
newline. Array order is contract-defined. Repeated execution over identical
bundle bytes and identical explicit inputs produces identical result bytes.

Determinism does not turn a self-consistent result into evidence of historical
occurrence or historical non-modification. Those boundaries remain explicit in
the result.

## Claim boundary

Every result embeds the `aelitium-claim-boundary-v1` identifier and applicable
codes. At minimum, bundle verification does not establish provider execution,
response causation, semantic truth, capture completeness, historical
occurrence, historical non-modification, authorization, trusted historical
time, legal compliance, or complete invocation identity.

See [`CLAIM_BOUNDARIES_V1.md`](CLAIM_BOUNDARIES_V1.md) for exact code meanings.

## Compatibility and versioning

This contract is additive. It does not change evidence schemas, hashing,
signing, trust evaluation, Freshness, reason precedence, text output, legacy
JSON keys, or verification exit codes.

Removing a required field, changing a field's meaning, changing the status/code
mapping, or changing embedded assurance semantics requires a new verification
contract identifier. Additive consumer-specific annotations must not be emitted
inside this closed v1 object.
