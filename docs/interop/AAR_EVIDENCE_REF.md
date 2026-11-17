# Proposed AAR `evidenceRef` mapping

**Status:** NON-NORMATIVE / EXPERIMENTAL

This note summarizes an unresolved reference proposal. It does not define a
schema-conformant AAR conversion, a canonical mapping, or an AAR verification
procedure. See
[`AAR_EVIDENCE_REF_MAPPING.md`](../AAR_EVIDENCE_REF_MAPPING.md) for the full
analysis.

The current upstream
[`receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/schema/receipt.json)
describes `evidenceRef.hash` as the content hash of the referenced evidence
artifact and describes `hash.digest` as Base64URL-encoded digest bytes. Its
current
[`evidence-ref-receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/examples/evidence-ref-receipt.json)
uses `aelitium/binding-bundle` as an example `type` value.

The presence of that type name does not resolve the following gaps:

| Field or concept | Upstream AAR | Current AELITIUM | Status |
|---|---|---|---|
| `type` | Includes `aelitium/binding-bundle` as an example. | The proposed notes reuse that name. | Naming example only. |
| `hash.alg` | Allows `sha256`. | `binding_hash` uses SHA-256. | Algorithm name aligns. |
| `hash.digest` encoding | Described as Base64URL digest bytes. | Printed as 64 lowercase hexadecimal characters. | No direct string comparison. |
| Hashed subject | Content hash of the referenced evidence artifact. | Commitment to selected recorded request/response hashes. | Semantics are not equivalent. |

## AELITIUM construction

```text
binding_hash = SHA256(canonical({request_hash, response_hash}))
```

`binding_hash` deterministically commits to the recorded selected
`request_hash`/`response_hash` pair under the AELITIUM v1 construction. It is not
a content hash or identifier of the complete bundle.

## Proposed reference fragment

```json
{
  "evidenceRef": [
    {
      "type": "aelitium/binding-bundle",
      "hash": {
        "alg": "sha256",
        "digest": "<Base64URL content hash of an agreed referenced artifact>"
      },
      "uri": "https://example.invalid/evidence/artifact"
    }
  ]
}
```

This fragment is illustrative only. The artifact boundary, byte serialization,
digest derivation, and any relationship to AELITIUM `binding_hash` remain
undefined. This pass deliberately introduces no conversion rule or new format.

## Current verification boundary

`aelitium verify-bundle ./bundle` can verify the documented internal consistency
of an available AELITIUM bundle. It does not validate AAR schema or signatures,
resolve a URI, or establish a match with an AAR artifact digest. In particular,
the printed `BINDING_HASH` must not be compared directly with the current
upstream `evidenceRef[].hash.digest`.

## Repository example

[`examples/aar_evidence_ref_receipt.json`](../../examples/aar_evidence_ref_receipt.json)
is a conceptual AAR-style sketch and is explicitly not schema-conformant. It
uses simplified string fields in place of several required upstream objects and
shows an illustrative AELITIUM-side hex digest. It is not a complete receipt or
an interoperability test vector.
