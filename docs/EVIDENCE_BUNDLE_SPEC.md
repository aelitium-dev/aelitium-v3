# Evidence Bundle Specification

**Version:** 1.1
**Status:** Draft Standard
**Last updated:** 2026-03-10

> This specification is intended to be implemented by any tool that produces or verifies AI output evidence bundles. It is not specific to AELITIUM. AELITIUM is the reference implementation.
>
> Feedback and alternative implementations are welcome.

---

## Overview

An **evidence bundle** is a self-contained, verifiable artefact that proves an AI output payload has not been altered since it was created.

Verification requires no network access, no external service, and no trust in the original infrastructure. Any conforming implementation can verify any conforming bundle.

This is analogous to what Docker images did for software environments, or what SBOM documents did for software supply chains — except applied to AI outputs.

---

## Design goals

| Goal | Description |
|------|-------------|
| **Deterministic** | Same input always produces the same bundle hash, on any machine |
| **Self-contained** | Bundle includes everything needed for verification |
| **Offline-first** | Verification never requires network access |
| **Extensible** | Schema versioning allows forward evolution |
| **Language-agnostic** | Bundle format is plain files; verifiable by any implementation |

---

## Bundle structure

An evidence bundle is a ZIP archive with the following layout:

```
bundle.zip
├── canonical.json       ← canonicalized payload (RFC 8785 JSON Canonicalization)
├── ai_manifest.json     ← bundle metadata, hash, schema version
└── receipt.json         ← optional: Ed25519 authority signature
```

### canonical.json

The canonicalized form of the original AI output payload. Canonicalization is applied before hashing to ensure determinism across machines, language runtimes, and JSON serializers.

Canonicalization method: `json-canonical-v1` (RFC 8785: sort keys, no insignificant whitespace, UTF-8).

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

The same input always produces the same `ai_hash_sha256`, regardless of:
- Operating system
- Python version (3.10+)
- Machine architecture
- Time of execution

This is verified by `scripts/verify_repro.sh`, which packs the example twice in a clean environment and asserts the hashes match.

---

## Trust boundary

An evidence bundle proves:

- The payload has not changed since the bundle was created
- The hash in the manifest matches the canonical payload
- (With receipt) An authority with the corresponding private key signed this hash

An evidence bundle does **not** prove:

- That the model actually produced the output (requires capture-layer integration)
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
