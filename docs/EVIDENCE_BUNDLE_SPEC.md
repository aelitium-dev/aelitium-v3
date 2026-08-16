# Evidence Bundle Specification

**Version:** 1.1
**Status:** CONCEPTUAL_DRAFT_NON_NORMATIVE
**Last updated:** 2026-03-10

> **Quarantine notice:** This document is a conceptual draft specification. It is
> **not** the current AELITIUM AI evidence bundle v1 runtime contract, and AELITIUM
> is not currently a reference implementation of this draft. Current implemented
> assurance semantics are documented in
> [MESSAGING_GUARDRAILS.md](MESSAGING_GUARDRAILS.md) and
> [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md).
>
> The formats, version lineage, identity rules, and conformance language below are
> proposed draft semantics unless a section explicitly says otherwise. Feedback
> and alternative implementations are welcome.

---

## Overview

This draft models an **evidence bundle** as a self-contained artefact whose
internal consistency can be verified under the proposed rules.

The draft proposes offline verification without an external service. Cross-language
conformance remains a design goal of this draft, not a demonstrated property of
the current AELITIUM AI v1 runtime.

This is analogous to what Docker images did for software environments, or what SBOM documents did for software supply chains — except applied to AI outputs.

---

## Design goals

| Goal | Description |
|------|-------------|
| **Deterministic** | Same input produces the same bundle hash in validated configurations |
| **Self-contained** | Bundle includes everything needed for verification |
| **Offline-first** | Verification never requires network access |
| **Extensible** | Schema versioning allows forward evolution |
| **Language-agnostic** | Bundle format is plain files; verifiable by any implementation |

---

## Proposed bundle structure

This draft proposes a ZIP archive with the following layout. These filenames and
the ZIP container are not the current AELITIUM AI v1 bundle contract.

```
bundle.zip
├── canonical.json       ← canonicalized payload (deterministic JSON serialization as implemented)
├── ai_manifest.json     ← bundle metadata, hash, schema version
└── receipt.json         ← optional: Ed25519 authority signature
```

### canonical.json

The canonicalized form of the original AI output payload. Canonicalization is applied before hashing to ensure deterministic hashing in validated configurations.

Canonicalization method: `json_sorted_keys_no_whitespace_utf8` (deterministic JSON serialization as implemented).

### ai_manifest.json

```json
{
  "schema": "1.1",
  "ts_utc": "2026-03-10T14:32:00Z",
  "ai_hash_sha256": "<sha256 of canonical.json>",
  "canonicalization": "json_sorted_keys_no_whitespace_utf8",
  "input_schema": "ai_output_v1"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema` | string | Bundle schema version |
| `ts_utc` | ISO 8601 | Timestamp of pack operation |
| `ai_hash_sha256` | hex string | SHA-256 of canonical.json |
| `canonicalization` | string | Canonicalization method identifier |
| `input_schema` | string | Schema used to validate the original input |

### receipt.json (optional)

Present when the bundle was signed by an authority using Ed25519.

```json
{
  "schema": "1.1",
  "ai_hash_sha256": "<hash>",
  "ts_utc": "<timestamp>",
  "signature_b64": "<base64-encoded Ed25519 signature>",
  "pubkey_b64": "<base64-encoded Ed25519 public key>"
}
```

Verification: `aelitium verify-receipt --receipt receipt.json --pubkey authority.pub`

---

## Proposed input schema: ai_output_v1

The draft proposes the following input shape. It is not the authoritative schema
enforced by the current AELITIUM AI v1 runtime.

**Required fields:**

```json
{
  "model": "gpt-4",
  "prompt": "...",
  "output": "...",
  "timestamp": "2026-03-10T14:32:00Z"
}
```

**Optional fields:**

```json
{
  "provider": "openai",
  "sdk": "openai-python-1.x",
  "request_hash": "<sha256 of raw request>",
  "response_hash": "<sha256 of raw response>",
  "temperature": 0.7,
  "max_tokens": 1024,
  "tags": ["production", "finance"]
}
```

All fields are preserved in canonical.json after canonicalization.

---

## Proposed verification algorithm

The following algorithm belongs to this draft format. It is not a description of
the current AELITIUM AI v1 verification kernel.

```
1. Unzip bundle
2. Read ai_manifest.json → extract ai_hash_sha256
3. Canonicalize canonical.json using json_sorted_keys_no_whitespace_utf8
4. Compute SHA-256 of canonical.json bytes
5. Compare computed hash with manifest hash
6. If match → STATUS=VALID (rc=0)
7. If mismatch → STATUS=INVALID (rc=2, reason=HASH_MISMATCH)
```

Optional:
```
8. If receipt.json present → verify Ed25519 signature
```

---

## Reproducibility guarantee

The same input is expected to produce the same `ai_hash_sha256` in validated configurations using the same canonicalization rules.

This is verified by `scripts/verify_repro.sh`, which packs the example twice in a clean environment and asserts the hashes match.

---

## Draft trust boundary

Under this draft model, verification can establish:

- The inspected payload and manifest hash are internally consistent under the
  proposed draft rules
- An optional receipt signature is mathematically valid under the verification
  material supplied to the verifier

The draft does **not** by itself establish:

- That the model actually produced the output (requires stronger provenance than the bundle alone)
- That the prompt or output is correct, safe, or unbiased
- That the system that created the bundle was trustworthy
- Historical non-modification without an independently trusted external anchor
- Trusted signer identity merely from verification material packaged with an artefact

See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for full analysis.

---

## Proposed schema evolution

| Version | Status | Changes |
|---------|--------|---------|
| 1.0 | Deprecated | Initial schema |
| 1.1 | Draft baseline | Added `canonicalization` field to the proposed manifest |
| 2.0 | Draft proposal | Capture layer fields: `request_hash`, `response_hash`, `provider`, `sdk` |

Within this draft, schema version is stored in `ai_manifest.json` → `schema` and
draft-conforming verifiers reject unrecognised draft versions. This table is not
AELITIUM runtime or release lineage.

---

## Proposed hash algorithm upgrade path

This draft specifies SHA-256 for its content hashes and treats the proposed
manifest fields as extension points for future algorithm changes.

**Draft hash fields:**

```json
{
  "canonicalization": "json_sorted_keys_no_whitespace_utf8",
  "ai_hash_sha256": "<sha256 hex>"
}
```

**Design rule:** the manifest field name (`ai_hash_sha256`) encodes the algorithm. If the hash algorithm changes, a new field name is added alongside the old one during the transition period:

```json
{
  "canonicalization": "json_sorted_keys_no_whitespace_utf8",
  "ai_hash_sha256": "<sha256 hex>",
  "ai_hash_sha3_256": "<sha3-256 hex>"
}
```

**Proposed migration policy:**

1. A new schema version (e.g. `2.x`) introduces the new hash field as optional, alongside SHA-256
2. A subsequent version (`3.0`) deprecates the old hash field; verifiers warn but still accept
3. A final version removes the old hash field; only the new algorithm is required

**Why not an algorithm identifier string?** Encoding the algorithm in the field name makes it impossible to silently change the algorithm without changing the manifest schema — any verifier that only knows SHA-256 will reject a bundle that omits `ai_hash_sha256`, rather than silently accepting a hash it cannot verify.

**SHA-256 status in this draft:** No migration is currently proposed. This section
records a conceptual upgrade path if the draft's algorithm requirements change.

---

## Proposed reference semantics

This section describes a conceptual identity model. Current AELITIUM AI v1 uses a
selected-field request identity and verifies consistency among stored binding
fields; it does not independently reconstruct source request or response material.

### Bundle identifier

```
bundle_id = binding_hash
```

In this draft, `binding_hash` is the proposed bundle identifier. It is a
deterministic commitment over the supplied request and response hash pair; it does
not by itself establish real-world request-to-response causation.

```
binding_hash = sha256(canonical({"request_hash": ..., "response_hash": ...}))
```

External systems **SHOULD** reference bundles using `binding_hash` as the identifier.

**Required properties:**

- Two valid bundles describing the same canonical request and response **MUST** produce the same `binding_hash`
- The bundle identifier **MUST** equal `binding_hash` — not `request_hash`, not `response_hash`, not `ai_hash_sha256`
- The identifier is deterministic, globally unique, offline-derivable, and provider-independent

**Why `binding_hash` and not the other hashes:**

| Field | What it identifies |
|-------|-------------------|
| `request_hash` | The input only |
| `response_hash` | The output only |
| `binding_hash` | The request ↔ response relationship — the evidence object itself |

The neutral artifact is the *pairing*, not either side independently.

### Verification determinism

A conforming implementation verifying an AELITIUM evidence bundle **MUST produce the same verification result** as any other conforming implementation given the same bundle and canonicalization rules.

Verification **MUST depend only on the normative fields defined in this specification**:

```
request_hash
response_hash
binding_hash
canonical_request
canonical_response
```

Non-normative metadata fields (e.g. `ts_utc`, `provider_metadata`, `captured_at_utc`) **MUST NOT affect verification outcomes**.

Implementations **MUST treat unknown fields as non-normative metadata** unless explicitly defined by this specification.

Verification **MUST fail closed**: if any required normative field is missing or malformed, the result MUST be `STATUS=INVALID`. Partial acceptance is not permitted.

Verification **MUST be a pure function** of the bundle contents and the canonicalization rules — it MUST NOT depend on execution environment, system time, external state, or any input not present in the bundle itself.

---

### Reference patterns

How external layers should reference a bundle:

**Agent receipt:**
```json
{
  "action": "publish_report",
  "evidenceRef": {
    "type": "aelitium/binding-bundle",
    "hash": { "algorithm": "sha256", "digest": "<binding_hash>" }
  }
}
```

**Payment reference:**
```json
{
  "paid_inference": true,
  "evidenceRef": "<binding_hash>"
}
```

**Audit log:**
```json
{
  "evidence": "<binding_hash>",
  "verified": true
}
```

### Proposed content-addressed identity

Under this draft model, the content-addressed identity is determined by
`binding_hash`.

If the canonical request or canonical response differ, the resulting `binding_hash` **MUST** differ except with negligible probability due to hash collisions. Therefore:

- Two bundles with the same `binding_hash` **MUST** represent the same canonical request–response pair.
- Any bundle that produces a different `binding_hash` **MUST** be treated as a distinct evidence object.
- Implementations **MUST** treat bundles with different `binding_hash` values as distinct evidence objects.

The proposed identifier is content-addressed and stable for the same supplied hash
pair. That property is not evidence of historical non-modification without an
independently trusted anchor.

Note: the draft allows non-normative fields (e.g. `ts_utc`, `provider_metadata`,
`captured_at_utc`) that do not affect its proposed identity. Identity stability in
this model applies to `request_hash`, `response_hash`, and `binding_hash` only —
not to metadata fields.

---

### What this spec does NOT define

To preserve layer neutrality, this spec does not define:

- Payment schemas or protocols
- Agent receipt formats
- Transport envelope structures

It defines only how evidence is identified and referenced. Each layer chooses its own referencing structure; the `binding_hash` is the common anchor.

---

## Reserved Extensions

> **Status: Non-normative. Not currently implemented. This section reserves field names only.**

The following fields are reserved for optional, non-normative use by higher layers. They are **not part of the primitive core** and **MUST NOT be included in the `binding_hash` computation**.

| Field | Status | Purpose |
|-------|--------|---------|
| `agent_state_hash` | Reserved / non-normative | Optional hash of agent state snapshot as defined by an adjacent layer. Semantics are not defined here. |
| `delegation_warrant_ref` | Reserved / non-normative | Optional reference to a delegation credential or warrant identifying who authorised the call. Relevant to agent receipt layers, not to the evidence primitive. |

**Constraints — these hold without exception:**

- Neither field alters the canonical identity of the bundle.
- `binding_hash = sha256(canonical({request_hash, response_hash}))` is unchanged by these fields.
- Implementations MUST treat these fields as non-normative metadata — they MUST NOT affect bundle identity or core bundle verification outcomes.
- A bundle that includes these fields MUST produce the same `binding_hash` as a bundle that omits them, given the same `request_hash` and `response_hash`.

These fields belong to context layers that sit above or adjacent to the evidence primitive. See [EVIDENCE_MODEL.md](EVIDENCE_MODEL.md) for layer separation.

---

## Draft implementations and conformance

No implementation is currently designated as the reference implementation of this
draft. The current AELITIUM AI v1 runtime does not claim conformance to this draft
format.

Future implementations claiming conformance to this draft would need to agree on
the proposed verification algorithm and reference vector before interoperable
conformance could be claimed.

---

## Relation to other standards

| Standard | Relation |
|----------|----------|
| SBOM (CycloneDX, SPDX) | Analogous concept applied to AI outputs instead of software components |
| OpenTelemetry | Complementary — OTEL provides observability; this draft proposes portable evidence-consistency semantics |
| Sigstore | Similar trust model; AELITIUM is offline-first and AI-specific |
| JWT | Similar signed-artefact concept; bundles include full payload, not just claims |

---

## Proposed draft reference vector

Proposed demo input (`examples/ai_output_min.json`):

```
ai_hash_sha256 = 8b647717b14ad030fe8a641a9dcd63202e70aca170071d96040908e8354ef842
```

This value is retained as a draft example. It is not a current cross-language or
cross-version AELITIUM conformance guarantee.
