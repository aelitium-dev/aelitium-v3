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
- consistency of stored versioned invocation identity fields when present
- consistency of the stored invocation identity hash-to-response hash link when
  invocation binding evidence is present
- mathematical Ed25519 signature validity when verification material is present
- declared-time recency of `ai_canonical.json.ts_utc` under an explicitly
  supplied Freshness policy

It does not by itself establish:

- complete provider invocation identity
- provider execution or response causation from invocation consistency
- historical non-modification without an independently trusted external anchor
- trusted signer identity, unless an external trust store is explicitly
  supplied for that verification invocation and the verified signing key's
  fingerprint is present in it
- trusted historical time or authorization
- semantic truth, safety, or correctness of the AI output

---

## Assurance dimensions

Do not collapse the current assurance result into a single authenticity claim.

| Dimension | Reachable states in v0.3.0 | Current meaning |
|---|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Schema, canonical bytes, manifest contract, and payload-hash consistency |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Consistency among stored v1 request/response/binding fields |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Consistency of stored versioned invocation identity fields; not provider execution |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Consistency of the stored invocation identity hash-to-response hash link; not provider execution or causation |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Mathematical validity of bundled Ed25519 material |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | Match against an explicitly supplied external trust store |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | Declared-time recency under the explicit policy pair defined by the Trust Boundary |
| `authorization` | `NOT_EVALUATED` only | No authorization decision is implemented in v0.3.0 |

A valid bundled signature alone does not authenticate a producer or establish
that its key belongs to an externally trusted party. `trusted_signer_identity`
becomes `VALID` only through comparison against a local trust store supplied
independently of the inspected bundle, via `--trust-store PATH`; without one,
verification behaves exactly as it did before this capability existed.

Unsigned and unbound bundles remain valid by default. Callers that require those
dimensions must use `--require-signature` and `--require-binding`; absence then
causes verification to fail.

---

## Freshness wording

Use `freshness = VALID` only for declared-time recency: the strict UTC
whole-second value declared in `ai_canonical.json.ts_utc` lies inside the
inclusive window supplied by the verifier through
`freshness_max_age_seconds` and `freshness_reference_time_utc`. See
[TRUST_BOUNDARY.md](TRUST_BOUNDARY.md#freshness-declared-time-recency) for
the complete normative definition, state mapping, excluded time sources,
and non-claims.

Do not shorten that meaning to “the evidence is fresh,” “the event happened
recently,” “the provider response is recent,” or “the invocation occurred
within the window” unless the same statement immediately preserves the
declared canonical timestamp and explicit verifier-policy boundary.

In particular, `freshness = VALID` is not trusted historical time and does
not establish historical occurrence, historical non-modification, provider
receipt or execution, response causation, trusted provider identity,
authorization, legal or regulatory compliance, or semantic truth or
correctness. Authorization remains `NOT_EVALUATED`.

Freshness, mathematical signature validity, and trusted signer identity are
independent dimensions. A trusted signer does not make the declared
canonical timestamp a trusted time authority. A valid signature
authenticates signed bytes under the existing signature semantics; it does
not prove that a timestamp inside those bytes is historically true.

---

## Trusted signer identity (explicit external trust store)

`--trust-store PATH` supplies a strict, local `aelitium-trust-v1` JSON file
containing trusted Ed25519 public keys, independent of the inspected bundle.
Records contain `algorithm` (`ed25519`), `public_key_b64`, and an optional,
non-authoritative `label`; the verifier derives each fingerprint itself from
the decoded raw key bytes — it never reads a stored fingerprint field,
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
organizational identity; organizational role; authorization; trusted
historical time; revocation status; provider identity; or model execution
proof. A fully
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

The separate versioned invocation identity and invocation binding fields preserve
more of the recorded call boundary. Their assurance dimensions establish stored
field consistency only; they do not establish provider receipt or execution,
response causation, or complete reconstruction of a real-world invocation.

### Compare boundary in v0.3.x

**Comparison basis in v0.3.x: `request_hash` v1.** The v0.3.x `compare` command
does not use `invocation_identity` or `invocation_binding` as its comparison
basis.

| Status | Approved meaning |
|---|---|
| `UNCHANGED` | Same selected v1 `request_hash` and same `response_hash` over selected recorded response fields |
| `CHANGED` | Same selected v1 `request_hash` and different selected `response_hash` values |
| `NOT_COMPARABLE` | Different selected v1 `request_hash` values or missing required `request_hash` capture metadata; invalid bundles are reported separately as `INVALID_BUNDLE` |

`request_hash` is not a complete invocation identity. Equality does not
establish equality of every invocation parameter, mode, provider route, client
configuration, or execution context. `invocation_identity` is a separate,
broader recorded identity when present. `CHANGED` does not by itself establish
model drift or explain causation. `UNCHANGED` does not establish that the full
invocation configuration was unchanged.

### Compare boundary in v0.4 development

**Comparison contract in v0.4 development: `aelitium-compare-v1`.** The default
mode is `INVOCATION_FIRST` and every comparison result reports its mode, basis,
and reason.

| Condition | Basis | Approved result meaning |
|---|---|---|
| Both bundles have identity and binding consistency `VALID`; invocation hashes match; response hashes match | `INVOCATION_IDENTITY_V1` | `UNCHANGED`: selected comparison identity and selected response hashes match under the reported basis |
| Both bundles have identity and binding consistency `VALID`; invocation hashes match; response hashes differ | `INVOCATION_IDENTITY_V1` | `CHANGED`: selected comparison identity hashes match and selected response hashes differ; no cause is identified |
| Both bundles have identity and binding consistency `VALID`; invocation hashes differ | `INVOCATION_IDENTITY_V1` | `NOT_COMPARABLE`: no response-change conclusion is made |
| One or both valid bundles lack usable invocation evidence | `REQUEST_HASH_V1_FALLBACK` | Apply the historical selected request/response hash decision with the downgrade visible |
| Strict mode lacks usable invocation evidence | `NONE` | `NOT_COMPARABLE`; required basis is `INVOCATION_IDENTITY_V1` |
| Either bundle fails verification | `NONE` | `INVALID_BUNDLE`; never fall back from invalid evidence |

`--legacy-request-hash-v1` explicitly selects basis
`REQUEST_HASH_V1_LEGACY`. `--require-invocation-evidence` explicitly selects
strict invocation mode and disables fallback. Invocation-binding hashes are
diagnostic and gated assurance evidence; they are not the comparison identity.

Safe interpretation boundaries:

- Invocation identity equality: the validated `aelitium-invocation-v1` hash
  values match. This describes equality only under the fields selected by that
  recorded identity format; it does not establish a complete real-world
  invocation.
- Fallback equality: `request_hash` v1 values match under the fallback basis.
  They cover selected canonical model and messages fields, not every invocation
  parameter, mode, route, client configuration, or execution context.
- `CHANGED`: under the reported basis, selected comparison identity hashes
  match and selected response hashes differ. This does not identify a cause.
- `UNCHANGED`: under the reported basis, selected comparison identity hashes
  and selected response hashes match. This does not establish unchanged
  invocation configuration or unchanged model behavior.
- `NOT_COMPARABLE`: no response-change conclusion is made because the selected
  comparison identity hashes differ or required evidence is unavailable.

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
| same selected v1 request hash and same selected response hash | same invocation or behavior unchanged |
| same selected v1 request hash and different selected response hash | model drift detected or proof of change |
| matching validated invocation-identity hashes under `aelitium-invocation-v1` | complete invocation equality |
| visible `REQUEST_HASH_V1_FALLBACK` basis | silent equivalence of complete call configuration |
| selected response hashes differ under the reported basis | model behavior changed or provider caused the difference |
| stored binding-field consistency | proof that a real-world request produced a response |
| mathematical signature validity | authentic origin or authenticated producer |
| signer identity is not established by bundled key material alone | verified signer or trusted signer |
| an explicitly supplied external trust store can establish `trusted_signer_identity = VALID` for a matching key | automatic, implicit, or ambient trusted signer |
| declared-time recency under an explicit verifier-supplied window | the evidence/event/provider response is fresh or happened recently |
| detects changes inconsistent with a trusted external anchor | tamper-proof or immutable record |
| offline, fail-closed verification | secure AI or trustworthy AI |

The phrase “no trust gap” is not approved: current v1 deliberately exposes trust
dimensions that remain unestablished or unevaluated.

---

## Boundary statement for public surfaces

> AELITIUM v1 validates the schema, canonical representation, and internal hash,
> binding-field, invocation-identity, invocation-binding, and optional signature
> consistency of the bundle being inspected. Under an explicit policy pair it can
> also evaluate declared-time recency of `ai_canonical.json.ts_utc`; that result is
> not trusted historical time. It does not by itself establish complete invocation
> identity, historical occurrence or non-modification, authorization, provider
> execution, response causation, or output truth. Trusted signer identity is
> established only when an external trust store is explicitly supplied for that
> verification invocation and the verified key matches it.

For compare specifically: AELITIUM establishes internal consistency of recorded
evidence on the validated surface. It does not establish provider execution,
causation, full invocation completeness, model drift, output truth,
authorization, or legal compliance.

---

## Demo framing

Demonstrations may show that editing a canonical artifact without consistently
updating its governed evidence causes verification to fail. They must not imply
that bundle-only verification detects a fully self-consistent replacement or
authenticates the original producer.
