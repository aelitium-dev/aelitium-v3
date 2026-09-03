# Proposed AELITIUM ↔ AAR `evidenceRef` mapping

**Status:** NON-NORMATIVE / EXPERIMENTAL

**Purpose:** Record a possible relationship between AELITIUM evidence and the
Agent Action Receipt (AAR) `evidenceRef` field without claiming schema
conformance, a complete conversion, or implemented AAR verification.

**Upstream review:** 2026-09-03, against the current upstream
[`schema/receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/schema/receipt.json)
and
[`examples/evidence-ref-receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/examples/evidence-ref-receipt.json)
on `Cyberweasel777/agent-action-receipt-spec` `main`.

## What the upstream material establishes

The reviewed AAR schema defines `evidenceRef` as an optional array whose entries
contain a `type` and `hash`. Its `hash` uses the upstream `hashObject`, where
`digest` is described as Base64URL-encoded digest bytes. The `evidenceRef.hash`
description calls for a content hash of the referenced evidence artifact.

The reviewed upstream example includes `aelitium/binding-bundle` as one example
value for `evidenceRef[].type`. That shared type name is useful evidence of
naming alignment. It does not define how an AELITIUM value becomes the upstream
artifact content hash, and it does not demonstrate schema-level interoperability.

## What AELITIUM `binding_hash` means

AELITIUM v1 uses these selected-field constructions:

```text
request_hash  = SHA256(canonical({model, messages}))
response_hash = SHA256(canonical({content, model}))
binding_hash  = SHA256(canonical({request_hash, response_hash}))
```

`binding_hash` deterministically commits to the recorded selected
`request_hash`/`response_hash` pair under the AELITIUM v1 construction. AELITIUM
exposes it as 64 lowercase hexadecimal SHA-256 characters.

It is not a content hash of the complete AELITIUM bundle, bundle directory, or
archive. It must not be described as the identifier of all bundle contents.

## Unresolved interoperability gaps

| Dimension | Current upstream AAR material | Current AELITIUM material | Consequence |
|---|---|---|---|
| Digest encoding | `hashObject.digest` is described as Base64URL-encoded digest bytes. | `binding_hash` is emitted as a 64-hex SHA-256 digest. | The strings must not be compared directly. |
| Hashed subject | `evidenceRef.hash` is described as the content hash of the referenced evidence artifact. | `binding_hash` commits to the selected request/response hash pair. | Substituting `binding_hash` would not satisfy the same stated artifact-hash semantics. |
| Receipt shape | The schema requires structured receipt, identity, action, scope, hash, cost, signature, and metadata fields. | The repository example uses a simplified AAR-style sketch. | The local example is not an upstream-schema-valid receipt or conformance vector. |

Resolving only the text encoding would not resolve the hashed-subject mismatch.
This document therefore does not specify a hex-to-Base64URL conversion, select a
bundle serialization to hash, or define a new interoperability format.

## Proposed reference fragment

The following fragment shows only the field placement under discussion. The
placeholder describes the upstream role; AELITIUM does not currently produce a
claimed-compatible value for it.

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

This is a proposed reference shape, not a complete receipt, schema test vector,
or canonical mapping. The exact referenced artifact, its byte representation,
and its digest derivation remain unresolved.

## Verification responsibilities remain separate

Given an AELITIUM bundle, the shipped CLI can evaluate that bundle under the
documented AELITIUM verification contract:

```bash
aelitium verify-bundle ./bundle
```

That command does not validate an AAR receipt, verify an AAR signature, fetch an
`evidenceRef`, or establish that an AAR digest refers to the inspected bundle.
No direct digest-comparison procedure is defined here.

Likewise, the presence of an AAR receipt or signature does not import the
underlying evidence's assurance semantics. Receipt verification and evidence
verification remain distinct operations with distinct trust inputs.

## Status of the repository example

[`examples/aar_evidence_ref_receipt.json`](../examples/aar_evidence_ref_receipt.json)
is intentionally labeled as a conceptual AAR-style sketch. Against the reviewed
upstream schema it:

- omits required `receiptId`, `principal`, `scope`, `cost`, and `metadata`
  fields;
- includes the explanatory `_comment` property even though the upstream receipt
  object disallows additional top-level properties;
- represents `agent`, `action`, `inputHash`, `outputHash`, and `signature` as
  strings where the upstream schema requires structured objects; and
- shows the AELITIUM-side 64-hex form in `evidenceRef.hash.digest`, while the
  upstream field is described as Base64URL-encoded artifact-digest bytes.

It must not be presented as schema-valid AAR, a signed receipt, or demonstrated
interoperability.

## Summary

- Upstream AAR currently includes `aelitium/binding-bundle` as an example
  `evidenceRef` type name.
- AELITIUM `binding_hash` is a deterministic commitment to a selected recorded
  request/response hash pair, not a hash of the complete bundle.
- Upstream digest encoding and artifact-hash semantics do not currently match a
  direct use of the printed AELITIUM `binding_hash`.
- The proposed mapping remains documentation-only, non-normative, experimental,
  and unresolved.
