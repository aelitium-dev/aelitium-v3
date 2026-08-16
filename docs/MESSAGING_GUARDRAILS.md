# AELITIUM — Messaging Guardrails

This document is the public-claims guidance for the current AI evidence bundle v1
surface. It summarizes implemented behavior; it is not a separate runtime,
schema, or architecture authority.

---

## Canonical v1 claim

> AELITIUM v1 verifies the internal consistency of the AI evidence bundle being
> inspected, offline and under a governed schema and canonicalization contract.

Current verification can establish:

- a valid `ai_output_v1` payload structure
- governed canonical serialization and manifest identifiers
- consistency between the canonical payload and `ai_hash_sha256`
- consistency among stored v1 request, response, and binding hash fields when
  binding evidence is present
- mathematical Ed25519 signature validity when verification material is present

It does not by itself establish:

- complete provider invocation identity
- historical non-modification without an independently trusted external anchor
- trusted signer identity
- freshness or authorization
- semantic truth, safety, or correctness of the AI output

---

## Assurance dimensions

Do not collapse the current assurance result into a single authenticity claim.

| Dimension | Current meaning |
|---|---|
| `payload_integrity` | Schema, canonical bytes, manifest contract, and payload-hash consistency |
| `binding_field_consistency` | Consistency among stored v1 binding fields, or `ABSENT` |
| `signature_validity` | Mathematical validity of bundled Ed25519 material, or `ABSENT` |
| `trusted_signer_identity` | `UNESTABLISHED` for current bundled verification material |
| `freshness` | `NOT_EVALUATED` |
| `authorization` | `NOT_EVALUATED` |

A valid bundled signature does not authenticate a producer or establish that its
key belongs to an externally trusted party.

Unsigned and unbound bundles remain valid by default. Callers that require those
dimensions must use `--require-signature` and `--require-binding`; absence then
causes verification to fail.

---

## Request and binding boundary

`request_hash` is a v1 selected-field request identity. Current capture paths hash
the model and messages used by that v1 path. Behavior-affecting parameters such as
`temperature` and `max_tokens` can be forwarded without changing `request_hash`.

`binding_hash` may be described as a cryptographic commitment over the stored
`request_hash` and `response_hash` pair. Verification checks consistency among
those stored fields. It does not independently reconstruct source request or
response material, a provider invocation, an action, or an authorization decision.

---

## Historical trust boundary

Verification detects modifications that are inconsistent with the bundle's
recorded contract, hashes, and any present signature material. A fully
self-consistent artifact replacement can still verify unless the verifier has an
independently trusted external hash, key identity, receipt, or equivalent anchor.

---

## Recommended wording

| Use this | Avoid |
|---|---|
| internal consistency of the inspected bundle | proof the bundle was never altered |
| v1 selected-field request identity | exact request or full invocation identity |
| stored binding-field consistency | proof that a real-world request produced a response |
| mathematical signature validity | authentic origin or authenticated producer |
| signer identity is not established by bundled key material | verified signer or trusted signer |
| detects changes inconsistent with a trusted external anchor | tamper-proof or immutable record |
| offline, fail-closed verification | secure AI or trustworthy AI |

The phrase “no trust gap” is not approved: current v1 deliberately exposes trust
dimensions that remain unestablished or unevaluated.

---

## Boundary statement for public surfaces

> AELITIUM v1 validates the schema, canonical representation, and internal hash,
> binding-field, and optional signature consistency of the bundle being inspected.
> It does not by itself establish complete invocation identity, historical
> non-modification, signer identity, freshness, authorization, or output truth.

---

## Demo framing

Demonstrations may show that editing a canonical artifact without consistently
updating its governed evidence causes verification to fail. They must not imply
that bundle-only verification detects a fully self-consistent replacement or
authenticates the original producer.
