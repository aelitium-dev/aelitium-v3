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
- trusted signer identity, unless an external trust store is explicitly
  supplied for that verification invocation and the verified signing key's
  fingerprint is present in it
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
| `trusted_signer_identity` | `UNESTABLISHED` by default; `VALID` only when an external trust store is explicitly supplied for that invocation and the verified signing key's fingerprint is present in it |
| `freshness` | `NOT_EVALUATED` |
| `authorization` | `NOT_EVALUATED` |

A valid bundled signature alone does not authenticate a producer or establish
that its key belongs to an externally trusted party. `trusted_signer_identity`
becomes `VALID` only through comparison against a local trust store supplied
independently of the inspected bundle, via `--trust-store PATH`; without one,
verification behaves exactly as it did before this capability existed.

Unsigned and unbound bundles remain valid by default. Callers that require those
dimensions must use `--require-signature` and `--require-binding`; absence then
causes verification to fail.

---

## Trusted signer identity (explicit external trust store)

`--trust-store PATH` supplies a strict, local `aelitium-trust-v1` JSON file
of trusted Ed25519 public-key fingerprints, independent of the inspected
bundle. Records contain `algorithm` (`ed25519`), `public_key_b64`, and an
optional, non-authoritative `label`; the verifier derives the fingerprint
itself from the raw key bytes — it never reads a stored fingerprint field,
because the format has none. There is no signer_id, revocation, expiry,
delegation, remote distribution, or ambient/default trust-store discovery.

`--require-trusted-signer` additionally rejects verification unless the
verified signing key's fingerprint is present in that trust store. Without
`--require-trusted-signer`, a valid signature from an unknown key still
verifies as `STATUS=VALID` with `trusted_signer_identity=UNESTABLISHED` — a
bundle is not made invalid merely because the caller did not require this
dimension.

Failure reasons are distinct and are never collapsed into one generic trust
failure:

| Reason | Meaning |
|---|---|
| `TRUST_INPUT_NOT_PROVIDED` | `--require-trusted-signer` was requested but no `--trust-store` was supplied |
| `TRUST_STORE_INVALID` | the explicitly supplied trust store could not be read, parsed, or validated |
| `TRUSTED_SIGNER_NOT_FOUND` | a valid trust store and a valid signature exist, but the verified key is not in it |
| `SIGNATURE_REQUIRED` | trusted signer identity was required but the bundle is unsigned |
| `SIGNATURE_INVALID` | signature material exists but cryptographic verification failed |

`trusted_signer_identity = VALID` means only that the verified signature's
public-key fingerprint is present in the trust store supplied to this
verification invocation. It does not mean verified human, legal, or
organizational identity; organizational role; authorization; freshness;
revocation status; provider identity; or model execution proof. A fully
rewritten, internally self-consistent artifact signed with an attacker's own
key can still report `payload_integrity=VALID` and `signature_validity=VALID`
— trusted signer identity does not create a historical external payload
anchor by itself; `--require-trusted-signer` rejects such an artifact only
because its key is absent from the supplied trust store, not because the
rewrite itself is detected.

See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for the full contract.

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
| signer identity is not established by bundled key material alone | verified signer or trusted signer |
| an explicitly supplied external trust store can establish `trusted_signer_identity = VALID` for a matching key | automatic, implicit, or ambient trusted signer |
| detects changes inconsistent with a trusted external anchor | tamper-proof or immutable record |
| offline, fail-closed verification | secure AI or trustworthy AI |

The phrase “no trust gap” is not approved: current v1 deliberately exposes trust
dimensions that remain unestablished or unevaluated.

---

## Boundary statement for public surfaces

> AELITIUM v1 validates the schema, canonical representation, and internal hash,
> binding-field, and optional signature consistency of the bundle being inspected.
> It does not by itself establish complete invocation identity, historical
> non-modification, freshness, authorization, or output truth. Trusted signer
> identity is established only when an external trust store is explicitly
> supplied for that verification invocation and the verified key matches it.

---

## Demo framing

Demonstrations may show that editing a canonical artifact without consistently
updating its governed evidence causes verification to fail. They must not imply
that bundle-only verification detects a fully self-consistent replacement or
authenticates the original producer.
