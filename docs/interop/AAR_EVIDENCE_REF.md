# AAR evidenceRef mapping

AELITIUM bundles can be referenced from AAR-style receipts using a minimal evidenceRef mapping.

This document defines the canonical reference shape. It does not define a complete interoperability verification procedure, and it does not add trust semantics beyond normal AELITIUM bundle verification.

For full layer analysis and design rationale, see [AAR_EVIDENCE_REF_MAPPING.md](../AAR_EVIDENCE_REF_MAPPING.md).

---

## Purpose

An AAR (Agent Action Receipt) records that an agent took a specific action. When that action involved an LLM call, the receipt can reference an AELITIUM evidence bundle to allow independent verification of the recorded LLM interaction.

The reference is a typed hash pointer — not an embed. Verification of the bundle is a separate step, independent of the receipt issuer.

---

## Field mapping

| Field | Value | Required |
|-------|-------|----------|
| `type` | `"aelitium/binding-bundle"` | yes |
| `hash.alg` | `"sha256"` | yes |
| `hash.digest` | `binding_hash` from the bundle manifest | yes |
| `uri` | retrieval location (path, URL, IPFS, etc.) | no |

### Why `binding_hash`

```
binding_hash = sha256(canonical({request_hash, response_hash}))
```

The `binding_hash` uniquely identifies the request ↔ response pairing. Using `request_hash` or `response_hash` alone would not identify the full recorded interaction.

---

## Canonical reference shape

```json
{
  "evidenceRef": [
    {
      "type": "aelitium/binding-bundle",
      "hash": {
        "alg": "sha256",
        "digest": "<binding_hash>"
      },
      "uri": "optional://location/of/bundle"
    }
  ]
}
```

---

## What this guarantees

- `binding_hash` is a stable, deterministic identifier for the AELITIUM bundle
- Anyone with the bundle can verify it offline: `aelitium verify-bundle ./bundle`
- Verification is independent of the receipt issuer and does not require network access

## What this does not guarantee

- That the model actually produced the recorded output (see [TRUST_BOUNDARY.md](../TRUST_BOUNDARY.md))
- That the receipt itself is trustworthy — receipt trust depends on the receipt's own signature and issuer
- That the bundle is retrievable — the `uri` field is advisory only

---

## Verification flow

1. Obtain the AELITIUM bundle (via `uri` or other means)
2. Run `aelitium verify-bundle ./bundle`
3. If `STATUS=VALID`, note the `BINDING_HASH=<digest>` printed to output
4. Compare that digest with `evidenceRef[].hash.digest` in the receipt
5. If they match, the bundle referenced in the receipt has not been modified since packing

---

## Example receipt

See [`../../examples/aar_evidence_ref_receipt.json`](../../examples/aar_evidence_ref_receipt.json) for a complete example.
