# Evidence Bundle Specification

**Version:** 1.1
**Status:** Draft Standard
**Last updated:** 2026-03-10

> This specification is intended to be implemented by any tool that produces or verifies AI output evidence bundles. It is not specific to AELITIUM. AELITIUM is the reference implementation.
>
> Feedback and alternative implementations are welcome.

---

## Overview

An **evidence bundle** is a self-contained, verifiable artefact that shows a recorded AI output payload has not been altered since it was bundled.

Verification requires no network access, no external service, and no trust in the original infrastructure. Any conforming implementation can verify any conforming bundle.

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

## Bundle structure

An evidence bundle is a ZIP archive with the following layout:

```
bundle.zip
├── canonical.json       ← canonicalized payload (deterministic JSON serialization as implemented)
├── ai_manifest.json     ← bundle metadata, hash, schema version
└── receipt.json         ← optional: Ed25519 authority signature
```

### canonical.json

The canonicalized form of the original AI output payload. Canonicalization is applied before hashing to ensure deterministic hashing in validated configurations.

Canonicalization method: `json-canonical-v1` (deterministic JSON serialization as implemented).

### ai_manifest.json

```json
{
  "schema": "1.1",
  "ts_utc": "2026-03-10T14:32:00Z",
  "ai_hash_sha256": "<sha256 of canonical.json>",
  "canonicalization": "json-canonical-v1",
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

## Input schema: ai_output_v1

The input payload that AELITIUM accepts for packing.

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

## Verification algorithm

```
1. Unzip bundle
2. Read ai_manifest.json → extract ai_hash_sha256
3. Canonicalize canonical.json using json-canonical-v1
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

## Trust boundary

An evidence bundle proves:

- The payload has not changed since the bundle was created
- The hash in the manifest matches the canonical payload
- (With receipt) An authority with the corresponding private key signed this hash

An evidence bundle does **not** prove:

- That the model actually produced the output (requires stronger provenance than the bundle alone)
- That the prompt or output is correct, safe, or unbiased
- That the system that created the bundle was trustworthy

See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for full analysis.

---

## Schema evolution

| Version | Status | Changes |
|---------|--------|---------|
| 1.0 | Deprecated | Initial schema |
| 1.1 | **Current** | Added `canonicalization` field to manifest |
| 2.0 | Planned | Capture layer fields: `request_hash`, `response_hash`, `provider`, `sdk` |

Schema version is stored in `ai_manifest.json` → `schema`. Verifiers must reject bundles with unrecognised schema versions.

---

## Hash algorithm upgrade path

AELITIUM currently uses SHA-256 for all content hashes. The `canonicalization` field in the manifest is the extension point for future algorithm changes.

**Current state:**

```json
{
  "canonicalization": "json-canonical-v1",
  "ai_hash_sha256": "<sha256 hex>"
}
```

**Design rule:** the manifest field name (`ai_hash_sha256`) encodes the algorithm. If the hash algorithm changes, a new field name is added alongside the old one during the transition period:

```json
{
  "canonicalization": "json-canonical-v1",
  "ai_hash_sha256": "<sha256 hex>",
  "ai_hash_sha3_256": "<sha3-256 hex>"
}
```

**Migration policy:**

1. A new schema version (e.g. `2.x`) introduces the new hash field as optional, alongside SHA-256
2. A subsequent version (`3.0`) deprecates the old hash field; verifiers warn but still accept
3. A final version removes the old hash field; only the new algorithm is required

**Why not an algorithm identifier string?** Encoding the algorithm in the field name makes it impossible to silently change the algorithm without changing the manifest schema — any verifier that only knows SHA-256 will reject a bundle that omits `ai_hash_sha256`, rather than silently accepting a hash it cannot verify.

**SHA-256 status:** SHA-256 has no known weaknesses for integrity use cases (collision resistance is not required here — only second-preimage resistance). No migration is planned. This section documents the path if standards change.

---

## Reference semantics

### Bundle identifier

```
bundle_id = binding_hash
```

The `binding_hash` is the canonical identifier of an AELITIUM evidence bundle. It is the deterministic commitment over the canonical request–response pair:

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

### Bundle immutability

The identity of an AELITIUM evidence bundle is fully determined by `binding_hash`.

If the canonical request or canonical response differ, the resulting `binding_hash` **MUST** differ except with negligible probability due to hash collisions. Therefore:

- Two bundles with the same `binding_hash` **MUST** represent the same canonical request–response pair.
- Any bundle that produces a different `binding_hash` **MUST** be treated as a distinct evidence object.
- Implementations **MUST** treat bundles with different `binding_hash` values as distinct evidence objects.

The bundle identifier is **content-addressed and immutable**.

Note: bundles may contain non-normative fields (e.g. `ts_utc`, `provider_metadata`, `captured_at_utc`) that do not affect identity. Immutability applies to `request_hash`, `response_hash`, and `binding_hash` only — not to metadata fields.

---

### What this spec does NOT define

To preserve layer neutrality, this spec does not define:

- Payment schemas or protocols
- Agent receipt formats
- Transport envelope structures

It defines only how evidence is identified and referenced. Each layer chooses its own referencing structure; the `binding_hash` is the common anchor.

---

## Implementations

| Implementation | Language | Status |
|---------------|----------|--------|
| `aelitium` | Python 3.10+ | Reference implementation — [PyPI](https://pypi.org/project/aelitium/) |

To register a third-party implementation, open a pull request adding a row to this table.

The specification is the canonical reference. Implementations must pass the [verification algorithm](#verification-algorithm) and produce the [canonical reference hash](#canonical-reference-hash) from the demo input.

---

## Relation to other standards

| Standard | Relation |
|----------|----------|
| SBOM (CycloneDX, SPDX) | Analogous concept applied to AI outputs instead of software components |
| OpenTelemetry | Complementary — OTEL provides observability, AELITIUM provides tamper-evidence |
| Sigstore | Similar trust model; AELITIUM is offline-first and AI-specific |
| JWT | Similar signed-artefact concept; bundles include full payload, not just claims |

---

## Canonical reference hash

Demo bundle (`examples/ai_output_min.json`):

```
ai_hash_sha256 = 8b647717b14ad030fe8a641a9dcd63202e70aca170071d96040908e8354ef842
```

This value is stable across machines and versions. Use it to verify your implementation.
